"""Storage integrity (PR #4 review, schema migration 6): the registry's storage class, path and deletion state can only
change through a recorded storage action, and always agree with each other.

Each "direct" test changes the database the way a script or a person with a database tool could, bypassing Q-MAP.
"""

from __future__ import annotations

import sqlite3

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest
from qmap.storage.recovery import find_storage_inconsistencies, recover_incomplete, verify_registry
from qmap.storage.storage_class import delete_temporary_file, move_dataset, temporary_path_for


@pytest.fixture
def ids(run, src):
    perm = do_ingest(run, write_delimited(src / "a.csv", HEADER, daily_rows(10, 1)))
    temp = do_ingest(run, write_delimited(src / "b.csv", HEADER, daily_rows(10, 2)))
    assert move_dataset(run, temp.dataset_ids[0], "temporary").ok
    return {"perm": perm.dataset_ids[0], "temp": temp.dataset_ids[0], "raw": perm.raw_dataset_id}


def _path(db, i):
    return db.one("SELECT relative_path FROM datasets WHERE dataset_id = ?", (i,))[0]


def _refused(db, sql, args=()):
    before = [tuple(r) for r in db.query("SELECT * FROM datasets ORDER BY dataset_id")]
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute(sql, args)
    assert [tuple(r) for r in db.query("SELECT * FROM datasets ORDER BY dataset_id")] == before  # nothing changed


def _open_action(db, run, i, action, to_class=None, from_path=None, to_path=None):
    row = db.one("SELECT storage_class, relative_path FROM datasets WHERE dataset_id = ?", (i,))
    with db.transaction() as conn:
        return conn.execute(
            "INSERT INTO storage_actions(run_id, dataset_id, action, from_class, to_class, from_path, to_path, status, "
            "started_at) VALUES (?,?,?,?,?,?,?, 'started', 'x')",
            (run.run_id, i, action, row["storage_class"], to_class, from_path or row["relative_path"], to_path)).lastrowid


# ---- invalid direct updates are refused ---------------------------------------------------------------------------
def test_class_cannot_change_without_its_path(db, ids):
    _refused(db, "UPDATE datasets SET storage_class = 'temporary' WHERE dataset_id = ?", (ids["perm"],))
    _refused(db, "UPDATE datasets SET storage_class = 'permanent' WHERE dataset_id = ?", (ids["temp"],))


def test_path_cannot_change_on_its_own(db, ids):
    _refused(db, "UPDATE datasets SET relative_path = 'Cleaned_Data/elsewhere.parquet' WHERE dataset_id = ?", (ids["perm"],))


def test_class_and_path_cannot_change_without_a_recorded_move(db, ids):
    to = temporary_path_for(_path(db, ids["perm"]))
    _refused(db, "UPDATE datasets SET storage_class = 'temporary', relative_path = ? WHERE dataset_id = ?", (to, ids["perm"]))


def test_a_recorded_move_does_not_allow_a_different_path(db, run, ids):
    to = temporary_path_for(_path(db, ids["perm"]))
    _open_action(db, run, ids["perm"], "move", "temporary", to_path=to)
    _refused(db, "UPDATE datasets SET storage_class = 'temporary', relative_path = 'Temporary_Data/other.parquet' "
                 "WHERE dataset_id = ?", (ids["perm"],))
    _refused(db, "UPDATE datasets SET storage_class = 'temporary', relative_path = 'Somewhere/x.parquet' "
                 "WHERE dataset_id = ?", (ids["perm"],))


def test_a_move_recorded_for_another_dataset_does_not_count(db, run, ids):
    _open_action(db, run, ids["temp"], "move", "permanent", to_path=_path(db, ids["temp"])[len("Temporary_Data/"):])
    to = temporary_path_for(_path(db, ids["perm"]))
    _refused(db, "UPDATE datasets SET storage_class = 'temporary', relative_path = ? WHERE dataset_id = ?", (to, ids["perm"]))


def test_deletion_cannot_be_marked_without_a_recorded_delete(db, ids):
    _refused(db, "UPDATE datasets SET file_deleted_at = '2026-11-01' WHERE dataset_id = ?", (ids["temp"],))


def test_a_recorded_delete_still_only_applies_to_temporary_data(db, run, ids):
    _open_action(db, run, ids["perm"], "delete_file")
    _refused(db, "UPDATE datasets SET file_deleted_at = '2026-11-01' WHERE dataset_id = ?", (ids["perm"],))


def test_a_completed_deletion_cannot_be_reversed_or_moved(db, run, ids):
    assert delete_temporary_file(run, ids["temp"]).ok
    _refused(db, "UPDATE datasets SET file_deleted_at = NULL WHERE dataset_id = ?", (ids["temp"],))
    _refused(db, "UPDATE datasets SET file_deleted_at = '2030-01-01' WHERE dataset_id = ?", (ids["temp"],))
    to = _path(db, ids["temp"])[len("Temporary_Data/"):]
    _open_action(db, run, ids["temp"], "move", "permanent", to_path=to)
    _refused(db, "UPDATE datasets SET storage_class = 'permanent', relative_path = ? WHERE dataset_id = ?", (to, ids["temp"]))


def test_raw_datasets_stay_protected_even_with_a_recorded_move(db, run, ids):
    to = temporary_path_for(_path(db, ids["raw"]))
    _open_action(db, run, ids["raw"], "move", "temporary", to_path=to)
    _refused(db, "UPDATE datasets SET storage_class = 'temporary', relative_path = ? WHERE dataset_id = ?", (to, ids["raw"]))
    _refused(db, "UPDATE datasets SET storage_class = 'temporary' WHERE dataset_id = ?", (ids["raw"],))


def test_a_new_dataset_cannot_be_inserted_with_class_and_path_disagreeing(db, ids):
    row = db.one("SELECT * FROM datasets WHERE dataset_id = ?", (ids["perm"],))
    cols = ("layer, instrument_id, timeframe, relative_path, sha256, parent_dataset_id, processing_version, volume_status, "
            "requirement_set, created_by_attempt_id, config_fingerprint, created_at, storage_class")
    vals = ("cleaned", row["instrument_id"], "1W", "Cleaned_Data/fake.parquet", "x", row["parent_dataset_id"], "p@1+c9",
            "mapped", "price_only", row["created_by_attempt_id"], "vs1:x", "t", "temporary")
    _refused(db, f"INSERT INTO datasets({cols}) VALUES ({', '.join('?' * len(vals))})", vals)


# ---- the audit trail cannot be faked ------------------------------------------------------------------------------
def test_an_action_must_be_recorded_as_started(db, run, ids):
    for status in ("completed", "failed"):
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                conn.execute("INSERT INTO storage_actions(run_id, dataset_id, action, from_class, to_class, from_path, "
                             "to_path, status, started_at) VALUES (?, ?, 'move', 'permanent', 'temporary', 'a', 'b', ?, 'x')",
                             (run.run_id, ids["perm"], status))


def test_only_one_unfinished_action_per_dataset(db, run, ids):
    _open_action(db, run, ids["perm"], "delete_file")
    with pytest.raises(sqlite3.IntegrityError):
        _open_action(db, run, ids["perm"], "delete_file")


def test_an_action_cannot_be_completed_unless_it_took_effect(db, run, ids):
    action = _open_action(db, run, ids["perm"], "move", "temporary", to_path=temporary_path_for(_path(db, ids["perm"])))
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("UPDATE storage_actions SET status = 'completed' WHERE action_id = ?", (action,))
    with db.transaction() as conn:  # recording it as failed is truthful and allowed
        conn.execute("UPDATE storage_actions SET status = 'failed' WHERE action_id = ?", (action,))


def test_an_action_that_took_effect_cannot_be_recorded_as_failed(db, run, ids):
    action = _open_action(db, run, ids["temp"], "delete_file")
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("UPDATE datasets SET file_deleted_at = 'x' WHERE dataset_id = ?", (ids["temp"],))
            conn.execute("UPDATE storage_actions SET status = 'failed' WHERE action_id = ?", (action,))


# ---- normal application workflows still work and leave a consistent audit trail ---------------------------------
def test_application_workflows_leave_a_consistent_registry(settings, db, run, ids):
    i = ids["perm"]
    original = _path(db, i)
    assert move_dataset(run, i, "temporary").ok
    assert move_dataset(run, i, "permanent").ok and _path(db, i) == original
    assert move_dataset(run, i, "temporary").ok
    assert delete_temporary_file(run, i, reason="done").ok
    acts = db.query("SELECT action, status, from_class, to_class FROM storage_actions WHERE dataset_id = ? "
                    "ORDER BY action_id", (i,))
    assert [tuple(a) for a in acts] == [("move", "completed", "permanent", "temporary"),
                                        ("move", "completed", "temporary", "permanent"),
                                        ("move", "completed", "permanent", "temporary"),
                                        ("delete_file", "completed", "temporary", None)]
    assert find_storage_inconsistencies(db) == []
    report = verify_registry(settings, db)
    assert not report.storage_inconsistencies and not report.missing_files and not report.checksum_mismatches


# ---- rows changed before migration 6 are reported (never repaired) -----------------------------------------------
def test_tampering_done_before_migration_6_is_reported(settings, roots, src, monkeypatch):
    import qmap.storage.db as dbmod
    from qmap.core.runs import run_context
    from qmap.storage.db import open_database
    from qmap.storage.schema import MIGRATIONS

    monkeypatch.setattr(dbmod, "MIGRATIONS", MIGRATIONS[:5])  # a database still at schema 5
    old = open_database(settings.db_path)
    with run_context(settings, old, "FOUND", area="Ingestion") as r:
        a = do_ingest(r, write_delimited(src / "a.csv", HEADER, daily_rows(10, 1))).dataset_ids[0]
        b = do_ingest(r, write_delimited(src / "b.csv", HEADER, daily_rows(10, 2))).dataset_ids[0]
        assert move_dataset(r, b, "temporary").ok
    with old.transaction() as conn:  # allowed by schema 5: the gap this review found
        conn.execute("UPDATE datasets SET storage_class = 'temporary' WHERE dataset_id = ?", (a,))
        conn.execute("UPDATE datasets SET file_deleted_at = 'x' WHERE dataset_id = ?", (b,))
    old.close()
    monkeypatch.setattr(dbmod, "MIGRATIONS", MIGRATIONS)
    db = open_database(settings.db_path)
    assert db.current_version() == 6
    found = recover_incomplete(settings, db).storage_inconsistencies
    assert any(f"dataset {a}: storage class temporary does not match" in f for f in found)
    assert any(f"dataset {a}: Temporary without a recorded move" in f for f in found)
    assert any(f"dataset {b}: marked deleted without a recorded delete action" in f for f in found)
    assert db.one("SELECT storage_class FROM datasets WHERE dataset_id = ?", (a,))[0] == "temporary"  # reported only
    db.close()
