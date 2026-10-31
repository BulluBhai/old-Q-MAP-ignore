"""No-overwrite placement primitive and schema upgrade (independent PR #1 review, R-01 and R-05/R-06/R-08)."""

import errno
import multiprocessing
import os
import sqlite3

import pytest

from qmap.storage import files as files_mod
from qmap.storage.db import Database, open_database
from qmap.storage.files import place_without_overwrite
from qmap.storage.schema import LATEST_VERSION, MIGRATION_1, MIGRATION_2, MIGRATIONS


def test_placement_moves_the_file_when_the_target_is_free(tmp_path):
    tmp, final = tmp_path / "a.tmp", tmp_path / "final.txt"
    tmp.write_bytes(b"data")
    place_without_overwrite(tmp, final)
    assert final.read_bytes() == b"data" and not tmp.exists()


def test_placement_never_replaces_an_existing_file(tmp_path):
    tmp, final = tmp_path / "a.tmp", tmp_path / "final.txt"
    tmp.write_bytes(b"incoming")
    final.write_bytes(b"already here")
    with pytest.raises(FileExistsError):
        place_without_overwrite(tmp, final)
    assert final.read_bytes() == b"already here" and tmp.read_bytes() == b"incoming"


def test_os_replace_would_have_overwritten(tmp_path):
    """Documents why os.replace is not used for registered files: it silently replaces the target."""
    tmp, final = tmp_path / "a.tmp", tmp_path / "final.txt"
    tmp.write_bytes(b"incoming")
    final.write_bytes(b"already here")
    os.replace(tmp, final)
    assert final.read_bytes() == b"incoming"


@pytest.mark.skipif(os.name == "nt", reason="the hard-link fallback exists only on macOS/Linux")
def test_fallback_without_hard_links_still_never_overwrites(tmp_path, monkeypatch):
    def no_links(src, dst):
        raise OSError(errno.EPERM, "hard links not supported on this volume")

    monkeypatch.setattr(files_mod.os, "link", no_links)
    tmp, final = tmp_path / "a.tmp", tmp_path / "final.txt"
    tmp.write_bytes(b"data")
    place_without_overwrite(tmp, final)
    assert final.read_bytes() == b"data" and not tmp.exists()
    tmp2 = tmp_path / "b.tmp"
    tmp2.write_bytes(b"other")
    with pytest.raises(FileExistsError):
        place_without_overwrite(tmp2, final)
    assert final.read_bytes() == b"data"


def _race(args):
    folder, i = args
    from pathlib import Path

    from qmap.storage.files import place_without_overwrite as place

    tmp = Path(folder) / f"{i}.tmp"
    tmp.write_bytes(f"writer {i}".encode() * 1000)
    try:
        place(tmp, Path(folder) / "final.txt")
        return i
    except FileExistsError:
        return None


def test_many_processes_racing_for_one_destination_exactly_one_wins(tmp_path):
    with multiprocessing.get_context("spawn").Pool(4) as pool:
        winners = [w for w in pool.map(_race, [(str(tmp_path), i) for i in range(12)]) if w is not None]
    assert len(winners) == 1
    assert (tmp_path / "final.txt").read_bytes() == f"writer {winners[0]}".encode() * 1000


# ---- migrations -------------------------------------------------------------------------------------------
def _v1_database(path):
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, description TEXT)")
    conn.executescript("BEGIN;" + MIGRATION_1 + "INSERT INTO schema_version VALUES (1, 'x', 'v1'); COMMIT;")
    conn.execute("INSERT INTO modules VALUES ('FOUND','Foundation','0.1','active')")
    conn.execute("INSERT INTO runs(run_id,module_code,status) VALUES ('R1','FOUND','completed')")
    conn.execute("INSERT INTO source_profiles VALUES ('p',1,'h','text','2026-01-01')")
    conn.close()


def test_a_version_1_database_is_upgraded_in_place_and_keeps_its_data(tmp_path):
    path = tmp_path / "old.sqlite"
    _v1_database(path)
    db = open_database(path)
    assert db.current_version() == LATEST_VERSION == 4
    assert [r["version"] for r in db.query("SELECT version FROM schema_version ORDER BY version")] == [1, 2, 3, 4]
    assert db.one("SELECT content_text FROM source_profiles")["content_text"] == "text"
    cols = {r["name"] for r in db.query("PRAGMA table_info(ingest_attempts)")}
    assert {"validation_settings_json", "config_fingerprint"} <= cols
    assert "config_fingerprint" in {r["name"] for r in db.query("PRAGMA table_info(datasets)")}
    with pytest.raises(sqlite3.IntegrityError):
        db.connection().execute("UPDATE source_profiles SET content_text='changed'")
    assert open_database(path).current_version() == 4  # re-opening changes nothing
    assert len(db.query("SELECT * FROM schema_version")) == 4


def test_foreign_keys_are_enforced_on_every_connection(tmp_path):
    db = open_database(tmp_path / "f.sqlite")
    assert db.one("PRAGMA foreign_keys")[0] == 1
    other = Database(tmp_path / "f.sqlite")
    assert other.one("PRAGMA foreign_keys")[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        other.connection().execute("INSERT INTO runs(run_id,module_code,status) VALUES ('R','NOPE','running')")


def test_a_failed_write_transaction_leaves_nothing_behind(tmp_path):
    db = open_database(tmp_path / "t.sqlite")
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO modules VALUES ('M','m','1','active')")
            conn.execute("INSERT INTO runs(run_id,module_code,status) VALUES ('R','M','bogus')")
    assert not db.query("SELECT * FROM modules") and not db.connection().in_transaction


# ---- follow-up review: upgrade from the schema written by the previous PR commit, and frozen migrations ----------
NOW = "2026-01-01T00:00:00Z"


def _v2_database_with_a_cleaned_result(path):
    """A registry as written at schema version 2 (commit 3a49980): one raw, one accepted attempt, one cleaned dataset."""
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, description TEXT)")
    conn.executescript("BEGIN;" + MIGRATION_1 + MIGRATION_2
                       + "INSERT INTO schema_version VALUES (1,'x','v1'); INSERT INTO schema_version VALUES (2,'x','v2'); COMMIT;")
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
        "detected_format,extension_matches,reader,validation_settings_json,created_at) "
        "VALUES (?,'R1',?,'accepted','p',1,'p@1+c1','delimited_text',1,'csv','{\"min_rows\": 1}',?)", (ev, raw, NOW)).lastrowid
    conn.execute("INSERT INTO datasets(layer,instrument_id,timeframe,relative_path,sha256,parent_dataset_id,"
                 "processing_version,canonical_schema_version,volume_status,requirement_set,created_by_attempt_id,created_at) "
                 "VALUES ('cleaned',1,'1D','Cleaned_Data/c.parquet','c',?,'p@1+c1',1,'absent','price_only',?,?)",
                 (raw, att, NOW))
    conn.close()
    return raw, att


def test_a_version_2_registry_with_results_upgrades_and_keeps_every_record(tmp_path):
    path = tmp_path / "v2.sqlite"
    raw, att = _v2_database_with_a_cleaned_result(path)
    db = open_database(path)
    assert db.current_version() == LATEST_VERSION
    old = db.one("SELECT * FROM datasets WHERE layer='cleaned'")
    assert old["config_fingerprint"] is None and old["status"] == "active"  # history kept, never rewritten
    assert db.one("SELECT validation_settings_json FROM ingest_attempts")["validation_settings_json"] == '{"min_rows": 1}'
    conn = db.connection()
    # a new result for the same derivation under a fingerprint is allowed alongside the legacy row ...
    att2 = conn.execute(
        "INSERT INTO ingest_attempts(event_id,run_id,raw_dataset_id,outcome,profile_id,profile_version,processing_version,"
        "detected_format,extension_matches,reader,config_fingerprint,created_at) "
        "VALUES (1,'R1',?,'accepted','p',1,'p@1+c1','delimited_text',1,'csv','vs1:x',?)", (raw, NOW)).lastrowid
    conn.execute("UPDATE datasets SET status='superseded' WHERE dataset_id=?", (old["dataset_id"],))
    ins = ("INSERT INTO datasets(layer,instrument_id,timeframe,relative_path,sha256,parent_dataset_id,processing_version,"
           "canonical_schema_version,volume_status,requirement_set,created_by_attempt_id,config_fingerprint,created_at) "
           "VALUES ('cleaned',1,'1D',?,'d',?,'p@1+c1',1,'absent','price_only',?,?,?)")
    conn.execute(ins, ("Cleaned_Data/d.parquet", raw, att2, "vs1:x", NOW))
    # ... but the same derivation twice under one fingerprint is not, and a fingerprint can no longer be left out
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(ins, ("Cleaned_Data/e.parquet", raw, att2, "vs1:x", NOW))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(ins, ("Cleaned_Data/f.parquet", raw, att2, None, NOW))


def test_applied_migrations_are_frozen():
    """An applied migration must never be edited (add a new one instead). These hashes pin migrations 1-4."""
    import hashlib

    pinned = {
        1: "219c00acaf9edf4ff90ebe1fc25a9454a222d6837ab7ad5e5cff3f0b8934c662",
        2: "7e58647827776ffa218ee612b4b1d7bfdb7480bcc0dab226071af3d18042a27e",
        3: "79bb18bbcf3fcb42c554a533fefae9bbb15a98079c57eaa09a4250a59c396e0e",
        4: "3dc564ae6db0c51277e9c51ff62433ee6816cbd8d76118f7a07f303dbcf02253",
    }
    actual = {v: hashlib.sha256(sql.encode("utf-8")).hexdigest() for v, _, sql in MIGRATIONS}
    assert [v for v, _, _ in MIGRATIONS] == list(range(1, len(MIGRATIONS) + 1))  # numbered without gaps
    for v, h in pinned.items():
        assert actual[v] == h, f"migration {v} was edited after it was released; add a new migration instead"
