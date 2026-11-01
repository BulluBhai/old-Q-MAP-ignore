"""Permanent / Temporary storage: safe moves, user-controlled deletion, protection of raw files, crash recovery."""

from __future__ import annotations

import sqlite3

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest
from qmap.core.runs import finish_run, start_run
from qmap.storage.files import sha256_file
from qmap.storage.recovery import recover_incomplete, verify_registry
from qmap.storage.storage_class import (assess_delete, assess_move, delete_temporary_file, move_dataset,
                                        temporary_path_for)


@pytest.fixture
def loaded(run, src):
    path = write_delimited(src / "daily.csv", HEADER, daily_rows(30))
    before = sha256_file(path)
    res = do_ingest(run, path)
    assert res.outcome == "accepted"
    return {"dataset_id": res.dataset_ids[0], "raw_id": res.raw_dataset_id, "source": path, "source_sha": before}


def _row(db, i):
    return db.one("SELECT * FROM datasets WHERE dataset_id = ?", (i,))


def test_a_new_dataset_is_permanent(db, loaded):
    assert _row(db, loaded["dataset_id"])["storage_class"] == "permanent"
    assert _row(db, loaded["raw_id"])["storage_class"] == "permanent"


def test_move_to_temporary_and_back_keeps_the_data_identical(settings, db, run, loaded):
    i = loaded["dataset_id"]
    before = _row(db, i)
    res = move_dataset(run, i, "temporary", reason="exploratory")
    assert res.ok, res.message
    after = _row(db, i)
    assert after["storage_class"] == "temporary"
    assert after["relative_path"] == temporary_path_for(before["relative_path"])
    assert after["relative_path"].startswith("Temporary_Data/Cleaned_Data/")
    assert sha256_file(settings.data_path(after["relative_path"])) == before["sha256"]
    assert not settings.data_path(before["relative_path"]).exists()  # no duplicate left behind
    act = db.one("SELECT * FROM storage_actions WHERE action_id = ?", (res.action_id,))
    assert (act["status"], act["from_class"], act["to_class"], act["reason"]) == ("completed", "permanent", "temporary",
                                                                                  "exploratory")
    back = move_dataset(run, i, "permanent")
    assert back.ok
    assert _row(db, i)["relative_path"] == before["relative_path"]
    assert sha256_file(settings.data_path(before["relative_path"])) == before["sha256"]
    report = verify_registry(settings, db)
    assert not report.missing_files and not report.checksum_mismatches


def test_the_original_source_file_is_never_touched(run, loaded):
    move_dataset(run, loaded["dataset_id"], "temporary")
    delete_temporary_file(run, loaded["dataset_id"])
    assert sha256_file(loaded["source"]) == loaded["source_sha"]


def test_raw_files_cannot_be_moved_or_deleted(settings, db, run, loaded):
    raw = loaded["raw_id"]
    a = assess_move(settings, db, raw, "temporary")
    assert not a.allowed and "original source file" in a.blockers[0]
    assert not move_dataset(run, raw, "temporary").ok
    assert not delete_temporary_file(run, raw).ok
    with pytest.raises(sqlite3.IntegrityError):  # enforced by the database too
        with db.transaction() as conn:
            conn.execute("UPDATE datasets SET storage_class = 'temporary' WHERE dataset_id = ?", (raw,))


def test_only_temporary_datasets_can_be_deleted(settings, db, run, loaded):
    i = loaded["dataset_id"]
    a = assess_delete(settings, db, i)
    assert not a.allowed and any("Only Temporary" in b for b in a.blockers)
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("UPDATE datasets SET file_deleted_at = 'x' WHERE dataset_id = ?", (i,))


def test_delete_keeps_the_record_and_is_final(settings, db, run, loaded):
    i = loaded["dataset_id"]
    move_dataset(run, i, "temporary")
    path = settings.data_path(_row(db, i)["relative_path"])
    res = delete_temporary_file(run, i, reason="no longer needed")
    assert res.ok
    row = _row(db, i)
    assert row is not None and row["file_deleted_at"] and not path.exists()
    assert db.one("SELECT COUNT(*) FROM ingest_attempts")[0] >= 1  # history kept
    assert not move_dataset(run, i, "permanent").ok
    assert not delete_temporary_file(run, i).ok
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("UPDATE datasets SET file_deleted_at = NULL WHERE dataset_id = ?", (i,))
    report = verify_registry(settings, db)
    assert row["relative_path"] not in report.missing_files  # deleted on purpose is not "missing"


def test_a_dataset_used_by_a_research_run_needs_explicit_confirmation(settings, db, run, loaded):
    i = loaded["dataset_id"]
    move_dataset(run, i, "temporary")
    with db.transaction() as conn:
        conn.execute("INSERT INTO run_inputs(run_id, dataset_id) VALUES (?, ?)", (run.run_id, i))
    a = assess_delete(settings, db, i)
    assert a.allowed and run.run_id in a.run_uses and any("explicit confirmation" in w for w in a.warnings)
    refused = delete_temporary_file(run, i)
    assert not refused.ok and "confirm" in refused.message
    assert delete_temporary_file(run, i, confirm_run_inputs=True).ok


def test_a_dataset_with_dependents_cannot_be_deleted(settings, db, run, loaded):
    from qmap.data_engine.derive import derive_timeframe

    i = loaded["dataset_id"]
    move_dataset(run, i, "temporary")
    assert derive_timeframe(run, i, "1W").ok
    a = assess_delete(settings, db, i)
    assert not a.allowed and any("built from this one" in b for b in a.blockers)


def test_reloading_a_deleted_dataset_says_so(settings, db, run, src, loaded):
    i = loaded["dataset_id"]
    move_dataset(run, i, "temporary")
    delete_temporary_file(run, i)
    again = do_ingest(run, loaded["source"])
    assert again.outcome == "reused" and "was deleted by the user" in again.message


def test_the_destination_is_never_overwritten(settings, db, run, loaded):
    i = loaded["dataset_id"]
    dest = settings.data_path(temporary_path_for(_row(db, i)["relative_path"]))
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"someone else's file")
    a = assess_move(settings, db, i, "temporary")
    assert not a.allowed and "never overwritten" in a.blockers[0]
    assert dest.read_bytes() == b"someone else's file"


def test_a_damaged_file_is_not_moved(settings, db, run, loaded):
    i = loaded["dataset_id"]
    path = settings.data_path(_row(db, i)["relative_path"])
    path.write_bytes(path.read_bytes() + b"x")
    res = move_dataset(run, i, "temporary")
    assert not res.ok and "checksum" in res.message
    assert _row(db, i)["storage_class"] == "permanent"
    assert db.one("SELECT status FROM storage_actions WHERE action_id = ?", (res.action_id,))["status"] == "failed"


# ---- crash recovery ---------------------------------------------------------------------------------------------
def _crashed_move(settings, db, i, *, copy_placed: bool):
    """Simulate a mover that recorded its intent (and maybe placed the copy) and then died."""
    dead = start_run(settings, db, "DBM", area="Data_Management", recover=False)
    row = _row(db, i)
    to = temporary_path_for(row["relative_path"])
    with db.transaction() as conn:
        conn.execute("INSERT INTO storage_actions(run_id, dataset_id, action, from_class, to_class, from_path, to_path, "
                     "status, started_at) VALUES (?, ?, 'move', 'permanent', 'temporary', ?, ?, 'started', 'x')",
                     (dead.run_id, i, row["relative_path"], to))
    if copy_placed:
        dest = settings.data_path(to)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(settings.data_path(row["relative_path"]).read_bytes())
    return dead, to


def test_recovery_never_deletes_the_destination_of_a_live_move(settings, db, loaded):
    live, to = _crashed_move(settings, db, loaded["dataset_id"], copy_placed=True)  # its lock is still held
    recover_incomplete(settings, db, stale_minutes=1)
    assert settings.data_path(to).exists()
    assert db.one("SELECT status FROM storage_actions WHERE run_id = ?", (live.run_id,))["status"] == "started"
    finish_run(live, "completed")


def test_recovery_undoes_an_interrupted_move_and_keeps_the_registered_file(settings, db, loaded):
    i = loaded["dataset_id"]
    dead, to = _crashed_move(settings, db, i, copy_placed=True)
    dead._release_lock()  # the process "died"
    with db.transaction() as conn:
        conn.execute("UPDATE runs SET status = 'failed' WHERE run_id = ?", (dead.run_id,))
    report = recover_incomplete(settings, db)
    row = _row(db, i)
    assert row["storage_class"] == "permanent" and settings.data_path(row["relative_path"]).is_file()
    assert not settings.data_path(to).exists()
    assert db.one("SELECT status FROM storage_actions WHERE run_id = ?", (dead.run_id,))["status"] == "failed"
    assert report.storage_actions_closed
    assert move_dataset(start_run(settings, db, "DBM", area="Data_Management"), i, "temporary").ok  # usable again


def test_recovery_removes_an_old_copy_left_by_a_completed_move(settings, db, run, loaded):
    i = loaded["dataset_id"]
    old_rel = _row(db, i)["relative_path"]
    content = settings.data_path(old_rel).read_bytes()
    assert move_dataset(run, i, "temporary").ok
    settings.data_path(old_rel).write_bytes(content)  # as if the removal had failed (file locked on Windows)
    recover_incomplete(settings, db)
    assert not settings.data_path(old_rel).exists()


def test_unregistered_files_in_temporary_area_are_reported_not_deleted(settings, db):
    stray = settings.temporary_dir / "somewhere" / "stray.parquet"
    stray.parent.mkdir(parents=True)
    stray.write_bytes(b"x")
    report = recover_incomplete(settings, db, stale_minutes=1)
    assert "Temporary_Data/somewhere/stray.parquet" in report.unregistered_temporary_files
    assert stray.exists() and report.needs_attention
