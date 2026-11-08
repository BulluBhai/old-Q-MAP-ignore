"""Schema behaviour: constraints, uniqueness, append-only audit trail, migrations."""

import sqlite3
import threading

import pytest

from qmap.storage.db import Database, open_database
from qmap.storage.schema import LATEST_VERSION

NOW = "2026-01-01T00:00:00Z"
FP = "vs1:0000000000000000"


@pytest.fixture
def conn(db):
    c = db.connection()
    c.execute("INSERT INTO modules VALUES ('FOUND','Foundation','0.1','active')")
    c.execute("INSERT INTO runs(run_id,module_code,status) VALUES ('R1','FOUND','completed')")
    c.execute("INSERT INTO source_profiles VALUES ('p',1,'h1','t',?)", (NOW,))
    c.execute("INSERT INTO source_profiles VALUES ('p',2,'h2','t',?)", (NOW,))
    c.execute("INSERT INTO instruments(exchange,symbol) VALUES ('NSE','NIFTY')")
    return c


def raw(conn, sha, rel=None, fmt="delimited_text"):
    return conn.execute("INSERT INTO datasets(layer,file_format,relative_path,sha256,created_at) VALUES ('raw',?,?,?,?)",
                        (fmt, rel or f"Raw_Data/{sha}", sha, NOW)).lastrowid


def event(conn, sha="S1", status="started", raw_id=None):
    return conn.execute(
        "INSERT INTO ingest_events(run_id,received_at,original_path,original_filename,sha256,status,raw_dataset_id) "
        "VALUES ('R1',?,?,?,?,?,?)", (NOW, "/x/a.csv", "a.csv", sha, status, raw_id)).lastrowid


def attempt(conn, event_id, raw_id, outcome="accepted", pv="p@1+c1", pver=1, **kw):
    return conn.execute(
        "INSERT INTO ingest_attempts(event_id,run_id,raw_dataset_id,outcome,profile_id,profile_version,processing_version,"
        "detected_format,extension_matches,reader,created_at,revalidation_of_attempt_id,reused_of_attempt_id,force_reason,"
        "config_fingerprint) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (event_id, "R1", raw_id, outcome, "p", pver, pv, "delimited_text", 1, "csv", NOW,
         kw.get("revalidation_of"), kw.get("reused_of"), kw.get("force_reason"), kw.get("fp", FP))).lastrowid


def cleaned(conn, parent, attempt_id, pv="p@1+c1", sha="C1", rel=None, instrument=1, timeframe="1D", **kw):
    return conn.execute(
        "INSERT INTO datasets(layer,instrument_id,timeframe,relative_path,sha256,parent_dataset_id,processing_version,"
        "canonical_schema_version,volume_status,requirement_set,created_by_attempt_id,created_at,config_fingerprint) "
        "VALUES ('cleaned',?,?,?,?,?,?,1,'absent','price_only',?,?,?)",
        (instrument, timeframe, rel or f"Cleaned_Data/{pv}/{sha}", sha, parent, pv, attempt_id, NOW,
         kw.get("fp", FP))).lastrowid


def test_migrations_applied_and_idempotent(db):
    assert db.current_version() == LATEST_VERSION
    assert db.migrate() == LATEST_VERSION


def test_concurrent_migration_is_safe(tmp_path):
    path = tmp_path / "m.sqlite"
    errors = []

    def go():
        try:
            Database(path).migrate()
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert Database(path).current_version() == LATEST_VERSION


def test_instrument_identity_is_exchange_plus_symbol(conn):
    conn.execute("INSERT INTO instruments(exchange,symbol) VALUES ('BSE','NIFTY')")  # same symbol, other exchange
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO instruments(exchange,symbol) VALUES ('NSE','NIFTY')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO instruments(exchange,symbol) VALUES ('NSE','nifty')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO instruments(exchange,symbol) VALUES (NULL,'X')")


def test_identical_raw_content_registers_once(conn):
    raw(conn, "S1")
    with pytest.raises(sqlite3.IntegrityError):
        raw(conn, "S1", rel="Raw_Data/other")


def test_event_for_reused_content_needs_a_dataset(conn):
    r = raw(conn, "S1")
    event(conn, "S1", "reused_existing", r)
    with pytest.raises(sqlite3.IntegrityError):
        event(conn, "S1", "reused_existing", None)


def test_raw_record_cannot_carry_processing_version(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO datasets(layer,file_format,relative_path,sha256,processing_version,created_at) "
                     "VALUES ('raw','parquet','Raw_Data/q','S9','p@1+c1',?)", (NOW,))


def test_events_are_immutable_and_never_deleted(conn):
    e = event(conn)
    conn.execute("UPDATE ingest_events SET status='failed' WHERE event_id=?", (e,))  # status may change
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        conn.execute("UPDATE ingest_events SET original_filename='zzz' WHERE event_id=?", (e,))
    with pytest.raises(sqlite3.DatabaseError, match="never deleted"):
        conn.execute("DELETE FROM ingest_events WHERE event_id=?", (e,))


def test_same_bytes_allowed_in_cleaned_layer_under_different_versions(conn):
    r = raw(conn, "S1")
    e = event(conn, "S1", "registered_new", r)
    a1 = attempt(conn, e, r, pv="p@1+c1", pver=1)
    a2 = attempt(conn, e, r, pv="p@2+c1", pver=2)
    d1 = cleaned(conn, r, a1, pv="p@1+c1", sha="SAME")
    conn.execute("UPDATE datasets SET status='superseded' WHERE dataset_id=?", (d1,))
    cleaned(conn, r, a2, pv="p@2+c1", sha="SAME")  # identical bytes, new version: allowed


def test_same_derivation_twice_is_blocked(conn):
    r = raw(conn, "S1")
    a = attempt(conn, event(conn, "S1", "registered_new", r), r)
    cleaned(conn, r, a)
    with pytest.raises(sqlite3.IntegrityError):
        cleaned(conn, r, a, sha="C2", rel="Cleaned_Data/dup")


def test_second_active_version_blocked_until_first_superseded(conn):
    r = raw(conn, "S1")
    e = event(conn, "S1", "registered_new", r)
    a1, a2 = attempt(conn, e, r, pv="p@1+c1", pver=1), attempt(conn, e, r, pv="p@2+c1", pver=2)
    d1 = cleaned(conn, r, a1, pv="p@1+c1", sha="C1")
    with pytest.raises(sqlite3.IntegrityError):
        cleaned(conn, r, a2, pv="p@2+c1", sha="C2")
    conn.execute("UPDATE datasets SET status='superseded' WHERE dataset_id=?", (d1,))
    d2 = cleaned(conn, r, a2, pv="p@2+c1", sha="C2")
    conn.execute("UPDATE datasets SET superseded_by_dataset_id=? WHERE dataset_id=?", (d2, d1))


@pytest.mark.parametrize("pv", [None, "  ", "v2", "@1+c1", "p@+c1"])
def test_cleaned_requires_valid_processing_version(conn, pv):
    r = raw(conn, "S1")
    a = attempt(conn, event(conn, "S1", "registered_new", r), r)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO datasets(layer,instrument_id,timeframe,relative_path,sha256,parent_dataset_id,processing_version,"
            "canonical_schema_version,volume_status,requirement_set,created_by_attempt_id,created_at) "
            "VALUES ('cleaned',1,'1D','Cleaned_Data/x','C9',?,?,1,'absent','price_only',?,?)", (r, pv, a, NOW))


def test_cleaned_requires_instrument_parent_and_timeframe(conn):
    r = raw(conn, "S1")
    a = attempt(conn, event(conn, "S1", "registered_new", r), r)
    with pytest.raises(sqlite3.IntegrityError):
        cleaned(conn, r, a, instrument=None)
    with pytest.raises(sqlite3.IntegrityError):
        cleaned(conn, None, a)


def test_audit_trail_is_append_only(conn):
    r = raw(conn, "S1")
    e = event(conn, "S1", "registered_new", r)
    a = attempt(conn, e, r, outcome="rejected")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE ingest_attempts SET outcome='accepted' WHERE attempt_id=?", (a,))
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM ingest_attempts WHERE attempt_id=?", (a,))
    conn.execute("INSERT INTO quality_checks(run_id,attempt_id,check_name,severity,passed,checked_at) "
                 "VALUES ('R1',?, 'low_le_high','error',0,?)", (a, NOW))
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE quality_checks SET passed=1")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM quality_checks")


def test_quality_check_needs_an_owner(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO quality_checks(run_id,check_name,severity,passed,checked_at) "
                     "VALUES ('R1','x','error',1,?)", (NOW,))


def test_reused_attempt_needs_pointer_to_original(conn):
    r = raw(conn, "S1")
    e = event(conn, "S1", "registered_new", r)
    with pytest.raises(sqlite3.IntegrityError):
        attempt(conn, e, r, outcome="reused")
    first = attempt(conn, e, r, outcome="accepted")
    attempt(conn, e, r, outcome="reused", reused_of=first)


def test_datasets_are_immutable_and_never_deleted(conn):
    r = raw(conn, "S1")
    a = attempt(conn, event(conn, "S1", "registered_new", r), r)
    d = cleaned(conn, r, a)
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        conn.execute("UPDATE datasets SET sha256='X' WHERE dataset_id=?", (d,))
    with pytest.raises(sqlite3.DatabaseError, match="never deleted"):
        conn.execute("DELETE FROM datasets WHERE dataset_id=?", (d,))
    conn.execute("UPDATE datasets SET status='superseded' WHERE dataset_id=?", (d,))
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        conn.execute("UPDATE datasets SET status='active' WHERE dataset_id=?", (d,))


def test_open_database_creates_file_in_metadata(settings):
    d = open_database(settings.db_path)
    assert settings.db_path.is_file()
    d.close()
