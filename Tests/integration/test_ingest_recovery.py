"""Interrupted ingestion: database, stored files and recovery must agree afterwards."""

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest
from qmap.storage.faults import InjectedFault, inject
from qmap.storage.files import sha256_file
from qmap.storage.recovery import recover_incomplete, verify_registry

ROWS = daily_rows(8)


@pytest.fixture
def good(src):
    return write_delimited(src / "good.csv", HEADER, ROWS)


def cleaned_files(settings):
    return [p for p in (settings.data_root / "Cleaned_Data").rglob("*") if p.is_file() and "_incoming" not in p.parts]


def assert_consistent(settings, db):
    """Every registered file exists with the right hash; nothing unregistered is left; no temp files."""
    report = verify_registry(settings, db)
    assert not report.needs_attention, report.summary()
    assert not list(settings.raw_incoming_dir.iterdir()) and not list(settings.cleaned_incoming_dir.iterdir())
    registered = {r["relative_path"] for r in db.query("SELECT relative_path FROM datasets")}
    on_disk = {settings.to_relative(p) for p in cleaned_files(settings)} | {
        settings.to_relative(p) for p in (settings.data_root / "Raw_Data").rglob("*")
        if p.is_file() and "_incoming" not in p.parts}
    assert on_disk == registered


@pytest.mark.parametrize("step", ["after_cleaned_temp", "after_cleaned_rename", "before_result_commit"])
def test_crash_while_registering_the_result_then_recovery_then_retry(step, run, settings, db, good):
    with pytest.raises(InjectedFault):
        with inject(step):
            do_ingest(run, good)
    run._release_lock()  # the process died: the operating system releases its run lock

    # the database never saw half a result
    assert not db.query("SELECT 1 FROM ingest_attempts") and not db.query("SELECT 1 FROM datasets WHERE layer='cleaned'")
    assert not db.query("SELECT 1 FROM quality_checks")
    # the raw file was registered before the crash and stays registered
    assert len(db.query("SELECT 1 FROM datasets WHERE layer='raw'")) == 1

    report = recover_incomplete(settings, db, stale_minutes=0)
    assert not report.needs_attention or report.missing_files == []
    assert not cleaned_files(settings) and not list(settings.cleaned_incoming_dir.iterdir())

    res = do_ingest(run, good)
    assert res.outcome == "accepted", res.message
    assert len(db.query("SELECT 1 FROM datasets WHERE layer='cleaned'")) == 1
    assert_consistent(settings, db)


def test_fresh_orphan_cleaned_file_is_left_alone_until_it_is_stale(run, settings, db, good):
    with pytest.raises(InjectedFault):
        with inject("before_result_commit"):
            do_ingest(run, good)
    assert len(cleaned_files(settings)) == 1
    recover_incomplete(settings, db)  # default 60 minute stale limit: a live writer may still be about to commit
    assert len(cleaned_files(settings)) == 1
    recover_incomplete(settings, db, stale_minutes=0)  # older than the limit, but its run is still live
    assert len(cleaned_files(settings)) == 1
    run._release_lock()  # the process died: the operating system releases its run lock
    recover_incomplete(settings, db, stale_minutes=0)
    assert not cleaned_files(settings)


def test_crash_after_commit_leaves_a_consistent_registry(run, settings, db, good):
    res = do_ingest(run, good)
    assert res.outcome == "accepted"
    assert_consistent(settings, db)


def test_registered_cleaned_files_are_never_deleted_by_recovery(run, settings, db, good):
    do_ingest(run, good)
    recover_incomplete(settings, db, stale_minutes=0)
    assert len(cleaned_files(settings)) == 1 and len(db.query("SELECT 1 FROM datasets WHERE layer='cleaned'")) == 1
    assert_consistent(settings, db)


def test_registered_raw_files_are_never_deleted_by_recovery(run, settings, db, good):
    do_ingest(run, good)
    raw = db.one("SELECT * FROM datasets WHERE layer='raw'")
    recover_incomplete(settings, db, stale_minutes=0)
    assert sha256_file(settings.data_path(raw["relative_path"])) == raw["sha256"]


def test_tampered_cleaned_file_is_detected(run, settings, db, good):
    import os

    do_ingest(run, good)
    f = cleaned_files(settings)[0]
    os.chmod(f, 0o600)
    f.write_bytes(f.read_bytes() + b"x")
    assert verify_registry(settings, db).checksum_mismatches == [settings.to_relative(f)]


def test_a_crashed_run_is_marked_failed_and_the_next_run_recovers(settings, db, good):
    import dataclasses

    from qmap.core.runs import finish_run, start_run

    r1 = start_run(settings, db, "FOUND", area="Ingestion")
    with pytest.raises(InjectedFault):
        with inject("after_rename"):
            do_ingest(r1, good)
    # r1 is never finished (the process "died")
    r1._release_lock()  # the process died: the operating system releases its run lock
    zero = dataclasses.replace(settings, stale_minutes=0)
    r2 = start_run(zero, db, "FOUND", area="Ingestion")
    assert db.one("SELECT status, error_message FROM runs WHERE run_id=?", (r1.run_id,))["error_message"] == "interrupted"
    assert len(db.query("SELECT 1 FROM datasets WHERE layer='raw'")) == 1  # registration finished by recovery
    res = do_ingest(r2, good)
    assert res.outcome == "accepted"
    finish_run(r2)
    assert_consistent(settings, db)
