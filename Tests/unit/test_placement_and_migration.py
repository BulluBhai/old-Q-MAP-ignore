"""No-overwrite placement primitive and schema upgrade (independent PR #1 review, R-01 and R-05/R-06/R-08)."""

import errno
import multiprocessing
import os
import sqlite3

import pytest

from qmap.storage import files as files_mod
from qmap.storage.db import Database, open_database
from qmap.storage.files import place_without_overwrite
from qmap.storage.schema import LATEST_VERSION, MIGRATION_1


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
    assert db.current_version() == LATEST_VERSION == 3
    assert [r["version"] for r in db.query("SELECT version FROM schema_version ORDER BY version")] == [1, 2, 3]
    assert db.one("SELECT content_text FROM source_profiles")["content_text"] == "text"
    cols = {r["name"] for r in db.query("PRAGMA table_info(ingest_attempts)")}
    assert {"validation_settings_json", "config_fingerprint"} <= cols
    assert "config_fingerprint" in {r["name"] for r in db.query("PRAGMA table_info(datasets)")}
    with pytest.raises(sqlite3.IntegrityError):
        db.connection().execute("UPDATE source_profiles SET content_text='changed'")
    assert open_database(path).current_version() == 3  # re-opening changes nothing
    assert len(db.query("SELECT * FROM schema_version")) == 3


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
