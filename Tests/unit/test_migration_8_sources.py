"""Schema migration 8 (folder sources): upgrade from a populated schema-7 registry, rollback of a failed migration,
and the append-only / immutability rules of the four new tables (PR #9 review, 08-Nov-26).

Written without assuming that 8 is the latest version, so later migrations do not invalidate these tests.
"""

from __future__ import annotations

import sqlite3

import pytest

from qmap.storage import db as db_mod
from qmap.storage.db import Database, open_database
from qmap.storage.schema import MIGRATIONS

NOW = "2026-11-08T00:00:00Z"
NEW_TABLES = ("data_sources", "source_scans", "source_file_observations", "source_answers")


def _upgrade_to(monkeypatch, path, version):
    monkeypatch.setattr(db_mod, "MIGRATIONS", [m for m in MIGRATIONS if m[0] <= version])
    database = open_database(path)
    assert database.current_version() == version
    database.close()
    monkeypatch.setattr(db_mod, "MIGRATIONS", MIGRATIONS)


def _tables(conn) -> set:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'trigger', 'index')")}


def _dump(conn, tables) -> dict:
    return {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in sorted(tables)}


def _populate_v7(path):
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("INSERT INTO modules VALUES ('FOUND','Foundation','0.1','active')")
    conn.execute("INSERT INTO runs(run_id,module_code,status) VALUES ('R1','FOUND','completed')")
    conn.execute("INSERT INTO source_profiles VALUES ('p',1,'h','text',?)", (NOW,))
    conn.execute("INSERT INTO instruments(exchange,symbol) VALUES ('NSE','TEST')")
    raw = conn.execute("INSERT INTO datasets(layer,file_format,relative_path,sha256,created_at) "
                       "VALUES ('raw','delimited_text','Raw_Data/aa/a.txt','a',?)", (NOW,)).lastrowid
    ev = conn.execute("INSERT INTO ingest_events(run_id,received_at,original_path,original_filename,sha256,status,"
                      "raw_dataset_id) VALUES ('R1',?,'/x/a.csv','a.csv','a','registered_new',?)", (NOW, raw)).lastrowid
    att = conn.execute(
        "INSERT INTO ingest_attempts(event_id,run_id,raw_dataset_id,outcome,profile_id,profile_version,processing_version,"
        "detected_format,extension_matches,reader,config_fingerprint,created_at) "
        "VALUES (?,'R1',?,'accepted','p',1,'p@1+c1','delimited_text',1,'csv','vs1:x',?)", (ev, raw, NOW)).lastrowid
    conn.execute("INSERT INTO datasets(layer,instrument_id,timeframe,relative_path,sha256,parent_dataset_id,"
                 "processing_version,canonical_schema_version,volume_status,requirement_set,created_by_attempt_id,"
                 "config_fingerprint,created_at) "
                 "VALUES ('cleaned',1,'1D','Cleaned_Data/c.parquet','c',?,'p@1+c1',1,'absent','price_only',?,'vs1:x',?)",
                 (raw, att, NOW))
    conn.close()


def test_a_populated_schema_7_registry_upgrades_and_keeps_every_record(tmp_path, monkeypatch):
    path = tmp_path / "v7.sqlite"
    _upgrade_to(monkeypatch, path, 7)
    _populate_v7(path)
    conn = sqlite3.connect(path)
    before_objects = _tables(conn)
    old_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    before = _dump(conn, old_tables - {"schema_version"})
    conn.close()
    assert not set(NEW_TABLES) & before_objects

    database = open_database(path)
    conn = database.connection()
    assert database.current_version() == MIGRATIONS[-1][0] >= 8
    assert 8 in {r["version"] for r in database.query("SELECT version FROM schema_version")}
    assert _dump(conn, old_tables - {"schema_version"}) == before  # nothing existing changed
    assert before_objects <= _tables(conn)  # no earlier table, index or trigger removed
    for t in NEW_TABLES:
        assert database.query(f"SELECT * FROM {t}") == []
    versions = [r["version"] for r in database.query("SELECT version FROM schema_version ORDER BY version")]
    database.close()
    again = open_database(path)  # re-opening an upgraded registry changes nothing
    assert [r["version"] for r in again.query("SELECT version FROM schema_version ORDER BY version")] == versions
    again.close()


def test_a_failing_migration_8_is_rolled_back_completely(tmp_path, monkeypatch):
    path = tmp_path / "v7.sqlite"
    _upgrade_to(monkeypatch, path, 7)
    _populate_v7(path)
    v8 = next(m for m in MIGRATIONS if m[0] == 8)
    broken = [m for m in MIGRATIONS if m[0] < 8] + [(8, v8[1], v8[2] + "\nCREATE TABLE data_sources (x);")]
    monkeypatch.setattr(db_mod, "MIGRATIONS", broken)
    database = Database(path)
    with pytest.raises(sqlite3.Error):
        database.migrate()
    assert database.current_version() == 7
    assert not database.connection().in_transaction
    assert not set(NEW_TABLES) & _tables(database.connection())  # nothing half-applied
    assert database.one("SELECT COUNT(*) AS n FROM datasets")["n"] == 2
    database.close()
    monkeypatch.setattr(db_mod, "MIGRATIONS", MIGRATIONS)
    fixed = open_database(path)  # the correct migration then applies normally
    assert set(NEW_TABLES) <= _tables(fixed.connection())
    fixed.close()


@pytest.fixture
def conn(tmp_path):
    database = open_database(tmp_path / "m8.sqlite")
    c = database.connection()
    c.execute("INSERT INTO modules VALUES ('SCAN','Folder scan','0.1','active')")
    c.execute("INSERT INTO runs(run_id,module_code,status) VALUES ('R1','SCAN','completed')")
    c.execute("INSERT INTO data_sources(kind,location,label,created_at,updated_at) VALUES ('folder','/m','M',?,?)",
              (NOW, NOW))
    c.execute("INSERT INTO source_scans(source_id,run_id,started_at,settings_json,status) "
              "VALUES (1,'R1',?,'{}','running')", (NOW,))
    c.execute("INSERT INTO source_file_observations(scan_id,source_id,relative_path,change,action,outcome,observed_at) "
              "VALUES (1,1,'a.csv','new','processed','imported',?)", (NOW,))
    c.execute("INSERT INTO source_answers(source_id,relative_path,structure_signature,answers_json,answered_at) "
              "VALUES (1,'a.csv','sig','{}',?)", (NOW,))
    yield c
    database.close()


@pytest.mark.parametrize("sql, message", [
    ("DELETE FROM data_sources", "never deleted"),
    ("UPDATE data_sources SET location = '/elsewhere'", "keeps its identity"),
    ("UPDATE data_sources SET kind = 'api'", "keeps its identity"),
    ("UPDATE data_sources SET created_at = 'x'", "keeps its identity"),
    ("DELETE FROM source_scans", "never deleted"),
    ("UPDATE source_scans SET run_id = 'R2'", "identity cannot change"),
    ("UPDATE source_file_observations SET outcome = 'failed'", "append-only"),
    ("DELETE FROM source_file_observations", "append-only"),
    ("UPDATE source_answers SET answers_json = '{\"symbol\": \"X\"}'", "append-only"),
    ("DELETE FROM source_answers", "append-only"),
])
def test_records_are_protected(conn, sql, message):
    with pytest.raises(sqlite3.DatabaseError, match=message):
        conn.execute(sql)


def test_a_scan_is_finished_exactly_once(conn):
    conn.execute("UPDATE source_scans SET status = 'completed', finished_at = ? WHERE scan_id = 1", (NOW,))
    with pytest.raises(sqlite3.DatabaseError, match="finished once"):
        conn.execute("UPDATE source_scans SET status = 'failed' WHERE scan_id = 1")


def test_source_settings_may_change_and_a_source_may_be_marked_removed(conn):
    conn.execute("UPDATE data_sources SET label = 'New', market_timezone = 'Asia/Kolkata', default_exchange = 'NSE', "
                 "status = 'removed', updated_at = ? WHERE source_id = 1", (NOW,))
    assert conn.execute("SELECT status FROM data_sources").fetchone()[0] == "removed"


@pytest.mark.parametrize("sql", [
    "INSERT INTO data_sources(kind,location,label,created_at,updated_at) VALUES ('api','/n','N','t','t')",
    "INSERT INTO data_sources(kind,location,label,created_at,updated_at) VALUES ('folder','/m','dup','t','t')",
    "INSERT INTO data_sources(kind,location,label,default_exchange,created_at,updated_at) "
    "VALUES ('folder','/n','N','nse','t','t')",
    "INSERT INTO data_sources(kind,location,label,created_at,updated_at) VALUES ('folder','  ','N','t','t')",
    "INSERT INTO source_file_observations(scan_id,source_id,relative_path,change,action,outcome,observed_at) "
    "VALUES (1,1,'b.csv','new','processed','merged','t')",
    "INSERT INTO source_file_observations(scan_id,source_id,relative_path,change,action,outcome,observed_at) "
    "VALUES (99,1,'b.csv','new','processed','imported','t')",
    "INSERT INTO source_scans(source_id,run_id,started_at,settings_json,status) VALUES (1,'NO_RUN','t','{}','running')",
])
def test_invalid_records_are_refused(conn, sql):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)
