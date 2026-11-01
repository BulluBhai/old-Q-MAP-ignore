"""Temporary-folder transition (Project Owner decision OD-8, schema migration 7): new Temporary data go to
Q-MAP_DATA/Temporary/; datasets already in the pre-OD-8 folder Temporary_Data/ stay valid, are never moved or rewritten
automatically, and can be relocated through the normal audited moves."""

from __future__ import annotations

import sqlite3

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest
from qmap.catalog import DataRequirement, check_readiness
from qmap.core.config import load_settings
from qmap.storage.files import sha256_file
from qmap.storage.recovery import find_storage_inconsistencies, recover_incomplete, verify_registry
from qmap.storage.storage_class import delete_temporary_file, move_dataset


def _path(db, i):
    return db.one("SELECT relative_path FROM datasets WHERE dataset_id = ?", (i,))[0]


@pytest.fixture
def legacy(settings, src, monkeypatch):
    """A database left by the earlier PR #4 code: schema 6, Temporary datasets under Temporary_Data/."""
    import qmap.storage.db as dbmod
    import qmap.storage.storage_class as sc
    from qmap.core.runs import run_context
    from qmap.storage.db import open_database
    from qmap.storage.schema import MIGRATIONS

    monkeypatch.setattr(dbmod, "MIGRATIONS", MIGRATIONS[:6])
    monkeypatch.setattr(sc, "TEMPORARY_FOLDER", "Temporary_Data")
    old = open_database(settings.db_path)
    with run_context(settings, old, "FOUND", area="Ingestion") as r:
        kept = do_ingest(r, write_delimited(src / "a.csv", HEADER, daily_rows(10, 1))).dataset_ids[0]
        gone = do_ingest(r, write_delimited(src / "b.csv", HEADER, daily_rows(10, 2))).dataset_ids[0]
        original = _path(old, kept)
        assert move_dataset(r, kept, "temporary").ok and move_dataset(r, gone, "temporary").ok
        assert delete_temporary_file(r, gone).ok
        finished_run = r.run_id
    assert _path(old, kept) == "Temporary_Data/" + original
    old.close()
    stray = settings.legacy_temporary_dir / "manual" / "note.txt"  # something the user put there by hand
    stray.parent.mkdir(parents=True)
    stray.write_bytes(b"mine")
    leftover = settings.legacy_temporary_dir / "_incoming" / f"{finished_run}.abc.tmp"  # an interrupted copy
    leftover.parent.mkdir(parents=True, exist_ok=True)
    leftover.write_bytes(b"partial")
    file_sha = sha256_file(settings.data_path(_path_from_file(settings, original)))
    monkeypatch.setattr(dbmod, "MIGRATIONS", MIGRATIONS)
    monkeypatch.setattr(sc, "TEMPORARY_FOLDER", "Temporary")
    db = open_database(settings.db_path)  # upgrade to schema 7
    from qmap.core.runs import finish_run, start_run

    run = start_run(settings, db, "DBM", area="Data_Management", recover=False)
    yield {"db": db, "run": run, "kept": kept, "gone": gone, "original": original, "stray": stray,
           "leftover": leftover, "file_sha": file_sha}
    finish_run(run, "completed")
    db.close()


def _path_from_file(settings, original):
    return "Temporary_Data/" + original


def test_a_fresh_installation_creates_only_the_new_temporary_folder(roots):
    s = load_settings(None, env={"QMAP_DATA_ROOT": str(roots["data"]), "QMAP_OUTPUT_ROOT": str(roots["output"])},
                      code_root=roots["code"])
    assert (s.data_root / "Temporary").is_dir() and not (s.data_root / "Temporary_Data").exists()


def test_new_moves_go_to_the_blueprint_folder(settings, db, run, src):
    i = do_ingest(run, write_delimited(src / "a.csv", HEADER, daily_rows(10))).dataset_ids[0]
    perm = _path(db, i)
    assert move_dataset(run, i, "temporary").ok
    assert _path(db, i) == "Temporary/" + perm and settings.data_path(_path(db, i)).is_file()
    assert move_dataset(run, i, "permanent").ok and _path(db, i) == perm
    assert find_storage_inconsistencies(db) == []


def test_upgrade_moves_and_rewrites_nothing(settings, legacy):
    db = legacy["db"]
    assert db.current_version() == 7
    path = _path(db, legacy["kept"])
    assert path.startswith("Temporary_Data/")  # registry unchanged
    assert sha256_file(settings.data_path(path)) == legacy["file_sha"]  # file unchanged, still in the old folder
    assert not (settings.temporary_dir / "Cleaned_Data").exists()  # nothing was copied to the new folder
    gone = db.one("SELECT relative_path, file_deleted_at FROM datasets WHERE dataset_id = ?", (legacy["gone"],))
    assert gone["relative_path"].startswith("Temporary_Data/") and gone["file_deleted_at"]  # deletion stays final


def test_legacy_datasets_stay_valid_readable_and_consistent(settings, legacy):
    db = legacy["db"]
    assert find_storage_inconsistencies(db) == []
    report = verify_registry(settings, db)
    assert not report.missing_files and not report.checksum_mismatches and not report.storage_inconsistencies
    assert report.legacy_temporary_datasets == [f"dataset {legacy['kept']}: {_path(db, legacy['kept'])}"]
    rep = check_readiness(settings, db, legacy["kept"], DataRequirement(timeframes=("1D",)))
    assert rep.ready, [f.detail for f in rep.failures]


def test_recovery_in_the_old_folder_reports_user_files_and_cleans_only_interrupted_copies(settings, legacy):
    report = recover_incomplete(settings, legacy["db"])
    assert legacy["stray"].exists() and "Temporary_Data/manual/note.txt" in report.unregistered_temporary_files
    assert not legacy["leftover"].exists()  # an interrupted copy of a finished run (reproducible, never registered)


def test_a_legacy_dataset_is_relocated_only_through_audited_moves(settings, legacy):
    db, i, run = legacy["db"], legacy["kept"], legacy["run"]
    old_location = settings.data_path(_path(db, i))
    assert move_dataset(run, i, "permanent").ok
    assert _path(db, i) == legacy["original"] and not old_location.exists()
    assert move_dataset(run, i, "temporary").ok
    assert _path(db, i) == "Temporary/" + legacy["original"]
    assert sha256_file(settings.data_path(_path(db, i))) == legacy["file_sha"]
    moves = [tuple(r) for r in db.query("SELECT from_path, to_path, status FROM storage_actions WHERE dataset_id = ? "
                                        "AND action = 'move' ORDER BY action_id", (i,))]
    assert moves[-2:] == [("Temporary_Data/" + legacy["original"], legacy["original"], "completed"),
                          (legacy["original"], "Temporary/" + legacy["original"], "completed")]
    assert find_storage_inconsistencies(db) == []
    assert verify_registry(settings, db).legacy_temporary_datasets == []


def test_the_details_screen_text_explains_a_legacy_location(settings, legacy):
    from qmap_gui.registry_services import details

    text = "".join(t for t, _ in details(settings, legacy["kept"]))
    assert "OLD folder Temporary_Data" in text and "Make Permanent, then Move to Temporary" in text


def test_nothing_new_can_be_put_in_the_old_folder(settings, legacy):
    db, i, run = legacy["db"], legacy["kept"], legacy["run"]
    assert move_dataset(run, i, "permanent").ok
    perm = _path(db, i)
    with db.transaction() as conn:
        conn.execute("INSERT INTO storage_actions(run_id, dataset_id, action, from_class, to_class, from_path, to_path, "
                     "status, started_at) VALUES (?, ?, 'move', 'permanent', 'temporary', ?, ?, 'started', 'x')",
                     (run.run_id, i, perm, "Temporary_Data/" + perm))
    with pytest.raises(sqlite3.IntegrityError):  # even with a matching recorded action
        with db.transaction() as conn:
            conn.execute("UPDATE datasets SET storage_class = 'temporary', relative_path = ? WHERE dataset_id = ?",
                         ("Temporary_Data/" + perm, i))
    row = db.one("SELECT * FROM datasets WHERE dataset_id = ?", (i,))
    cols = ("layer, instrument_id, timeframe, relative_path, sha256, parent_dataset_id, processing_version, volume_status, "
            "requirement_set, created_by_attempt_id, config_fingerprint, created_at, storage_class")
    for path, cls in (("Temporary_Data/Cleaned_Data/x.parquet", "temporary"), ("Temporary_Data/x.parquet", "permanent")):
        vals = ("cleaned", row["instrument_id"], "1W", path, "x", row["parent_dataset_id"], "p@1+c9", "mapped",
                "price_only", row["created_by_attempt_id"], "vs1:x", "t", cls)
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                conn.execute(f"INSERT INTO datasets({cols}) VALUES ({', '.join('?' * len(vals))})", vals)
