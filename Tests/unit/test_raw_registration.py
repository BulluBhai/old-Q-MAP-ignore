"""Raw registration, provenance of every receipt, recovery and concurrency."""

import os
import threading

import pytest

from fixtures.builders import HEADER, ohlcv, standard_columns, weekdays, write_delimited, write_parquet, write_xlsx
from qmap.core.runs import finish_run
from qmap.storage import faults
from qmap.storage.faults import InjectedFault, inject
from qmap.storage.files import is_read_only, sha256_file
from qmap.storage.recovery import recover_incomplete, verify_registry
from qmap.storage.registry import receive_file

ROWS = [[d.isoformat()] + r for d, r in zip(weekdays(5), ohlcv(5))]


@pytest.fixture
def csv(src):
    return write_delimited(src / "a.csv", HEADER, ROWS)


def events(db):
    return db.query("SELECT * FROM ingest_events ORDER BY event_id")


def raw_rows(db):
    return db.query("SELECT * FROM datasets WHERE layer='raw'")


def test_new_file_is_registered_content_addressed_and_read_only(run, settings, db, csv):
    before = sha256_file(csv)
    rec = receive_file(run, csv, source_label="unit-test")
    assert rec.status == "registered_new" and rec.raw_dataset_id
    stored = settings.data_path(rec.relative_path)
    assert rec.relative_path == f"Raw_Data/{before[:2]}/{before}.txt"
    assert sha256_file(stored) == before
    assert is_read_only(stored)
    assert sha256_file(csv) == before  # the source is untouched
    ev = events(db)[0]
    assert ev["status"] == "registered_new" and ev["original_filename"] == "a.csv"
    assert ev["source_label"] == "unit-test" and ev["sha256"] == before
    assert not list(settings.raw_incoming_dir.iterdir())  # no temp files


def test_identical_content_different_name_and_extension_stored_once_with_two_receipts(run, settings, db, src, csv):
    other_dir = src / "elsewhere"
    other_dir.mkdir()
    twin = other_dir / "renamed_copy.TXT"
    twin.write_bytes(csv.read_bytes())
    r1 = receive_file(run, csv, source_label="vendor A", note="first")
    r2 = receive_file(run, twin, source_label="vendor B", note="second")
    assert r1.status == "registered_new" and r2.status == "reused_existing"
    assert r1.raw_dataset_id == r2.raw_dataset_id
    assert len(raw_rows(db)) == 1
    stored = [p for p in (settings.data_root / "Raw_Data").rglob("*") if p.is_file()]
    assert len(stored) == 1  # no duplicate raw copy
    ev = events(db)
    assert len(ev) == 2
    assert (ev[0]["original_filename"], ev[0]["source_label"], ev[0]["note"]) == ("a.csv", "vendor A", "first")
    assert (ev[1]["original_filename"], ev[1]["source_label"], ev[1]["note"]) == ("renamed_copy.TXT", "vendor B", "second")
    assert ev[1]["original_path"] != ev[0]["original_path"]
    assert ev[1]["raw_dataset_id"] == ev[0]["raw_dataset_id"]


def test_same_file_received_twice_keeps_both_receipts(run, db, csv):
    receive_file(run, csv)
    receive_file(run, csv)
    assert len(events(db)) == 2 and len(raw_rows(db)) == 1


def test_different_content_same_filename_creates_new_raw(run, db, src):
    p = src / "same_name.csv"
    write_delimited(p, HEADER, ROWS)
    a = receive_file(run, p)
    write_delimited(p, HEADER, ROWS[:-1])
    b = receive_file(run, p)
    assert a.raw_dataset_id != b.raw_dataset_id and len(raw_rows(db)) == 2


def test_same_content_different_formats_are_distinct_files(run, db, src):
    a = receive_file(run, write_delimited(src / "a.csv", HEADER, ROWS))
    b = receive_file(run, write_xlsx(src / "a.xlsx", HEADER, ROWS))
    c = receive_file(run, write_parquet(src / "a.parquet", standard_columns(["x"], [[1.0, 2.0, 0.5, 1.5, 10]])))
    assert len({a.raw_dataset_id, b.raw_dataset_id, c.raw_dataset_id}) == 3
    kinds = {r["file_format"] for r in raw_rows(db)}
    assert kinds == {"delimited_text", "xlsx", "parquet"}


def test_unsupported_file_is_recorded_not_copied(run, settings, db, src):
    p = src / "x.json"
    p.write_text('{"a": 1}')
    rec = receive_file(run, p)
    assert rec.status == "unsupported" and "JSON" in rec.detail
    assert events(db)[0]["status"] == "unsupported"
    assert not raw_rows(db)
    assert not [f for f in (settings.data_root / "Raw_Data").rglob("*") if f.is_file()]


def test_missing_file_is_recorded_as_failed(run, db, src):
    rec = receive_file(run, src / "does_not_exist.csv")
    assert rec.status == "failed"
    ev = events(db)[0]
    assert ev["status"] == "failed" and ev["original_filename"] == "does_not_exist.csv"


def test_filename_with_spaces_and_unicode(run, db, src):
    p = write_delimited(src / "my data ₹ file (1).csv", HEADER, ROWS)
    rec = receive_file(run, p)
    assert rec.ok and events(db)[0]["original_filename"] == "my data ₹ file (1).csv"


@pytest.mark.windows_compat
def test_final_file_already_present_and_read_only_is_not_replaced(run, settings, db, csv, monkeypatch):
    """On Windows os.replace fails over a read-only file; the code must never call it in that case.

    Scenario: a crash after the rename left the (read-only) final file but no database record.
    A plain re-ingest must adopt it without touching it. os.replace is made to fail over any
    existing file, exactly as Windows does.
    """
    import qmap.storage.registry as reg

    with pytest.raises(InjectedFault):
        with inject("after_rename"):
            receive_file(run, csv)
    final = next(p for p in (settings.data_root / "Raw_Data").rglob("*.txt") if "_incoming" not in p.parts)
    os.chmod(final, 0o444)
    real_replace = os.replace

    def windows_like_replace(src, dst):
        if os.path.exists(dst):
            raise PermissionError(13, "Access is denied (simulated Windows read-only target)")
        return real_replace(src, dst)

    monkeypatch.setattr(reg.os, "replace", windows_like_replace)
    rec = receive_file(run, csv)
    assert rec.status == "registered_new"
    assert sha256_file(final) == rec.sha256 and is_read_only(final)
    assert not list(settings.raw_incoming_dir.iterdir())


@pytest.mark.parametrize("step", ["after_hash", "after_event_started", "after_temp_copy", "after_rename",
                                  "before_db_commit", "after_db_commit"])
def test_crash_at_every_step_then_recover_then_reingest_is_consistent(step, run, settings, db, csv):
    digest = sha256_file(csv)
    with pytest.raises(InjectedFault):
        with inject(step):
            receive_file(run, csv)
    run._release_lock()  # the process died: the operating system releases its run lock
    report = recover_incomplete(settings, db, stale_minutes=0)

    # invariant 1: no temp files left behind
    assert not list(settings.raw_incoming_dir.iterdir())
    # invariant 2: every event is in a final state
    assert all(e["status"] != "started" for e in events(db))
    # invariant 3: every raw record has its file with a matching hash
    for row in raw_rows(db):
        assert sha256_file(settings.data_path(row["relative_path"])) == row["sha256"]
    # invariant 4: nothing unregistered is left unaccounted for
    assert not report.orphan_raw_files

    # re-ingesting yields exactly one raw dataset
    again = receive_file(run, csv)
    assert again.ok
    assert len(raw_rows(db)) == 1 and raw_rows(db)[0]["sha256"] == digest
    assert not list(settings.raw_incoming_dir.iterdir())
    assert not verify_registry(settings, db).needs_attention


def test_crash_after_rename_is_completed_by_recovery(run, settings, db, csv):
    with pytest.raises(InjectedFault):
        with inject("after_rename"):
            receive_file(run, csv)
    assert not raw_rows(db)  # database never committed
    run._release_lock()  # the process died: the operating system releases its run lock
    report = recover_incomplete(settings, db, stale_minutes=0)
    assert len(report.completed_events) == 1
    assert len(raw_rows(db)) == 1
    ev = events(db)[0]
    assert ev["status"] == "registered_new" and ev["raw_dataset_id"] == raw_rows(db)[0]["dataset_id"]


def test_crash_before_rename_is_failed_and_cleaned_by_recovery(run, settings, db, csv):
    with pytest.raises(InjectedFault):
        with inject("after_temp_copy"):
            receive_file(run, csv)
    assert list(settings.raw_incoming_dir.iterdir())  # temp file present
    run._release_lock()  # the process died: the operating system releases its run lock
    report = recover_incomplete(settings, db, stale_minutes=0)
    assert len(report.failed_events) == 1 and report.deleted_temp_files
    assert events(db)[0]["status"] == "failed" and not raw_rows(db)


def test_fresh_started_event_of_a_live_run_is_left_alone(run, settings, db, csv):
    with pytest.raises(InjectedFault):
        with inject("after_temp_copy"):
            receive_file(run, csv)
    report = recover_incomplete(settings, db)  # default 60 minute stale limit, run still 'running'
    assert not report.failed_events and not report.completed_events
    assert events(db)[0]["status"] == "started"


def test_orphan_raw_file_is_reported_never_deleted_and_adopted_on_reingest(run, settings, db, csv):
    digest = sha256_file(csv)
    orphan = settings.data_root / "Raw_Data" / digest[:2] / f"{digest}.txt"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(csv.read_bytes())
    report = recover_incomplete(settings, db, stale_minutes=0)
    assert report.orphan_raw_files == [f"Raw_Data/{digest[:2]}/{digest}.txt"]
    assert orphan.exists()
    rec = receive_file(run, csv)
    assert rec.status == "registered_new" and len(raw_rows(db)) == 1
    assert sha256_file(orphan) == digest


def test_missing_stored_file_is_reported_and_restored_by_reingest(run, settings, db, csv):
    rec = receive_file(run, csv)
    stored = settings.data_path(rec.relative_path)
    os.chmod(stored, 0o600)
    stored.unlink()
    report = recover_incomplete(settings, db)
    assert report.missing_files == [rec.relative_path]
    again = receive_file(run, csv)
    assert again.status == "reused_existing" and again.raw_dataset_id == rec.raw_dataset_id
    assert sha256_file(stored) == rec.sha256 and len(raw_rows(db)) == 1


def test_verify_detects_a_tampered_raw_file(run, settings, db, csv):
    rec = receive_file(run, csv)
    stored = settings.data_path(rec.relative_path)
    os.chmod(stored, 0o600)
    stored.write_bytes(stored.read_bytes() + b"tamper")
    assert verify_registry(settings, db).checksum_mismatches == [rec.relative_path]


def test_a_different_file_occupying_the_path_is_never_overwritten(run, settings, db, csv):
    digest = sha256_file(csv)
    squatter = settings.data_root / "Raw_Data" / digest[:2] / f"{digest}.txt"
    squatter.parent.mkdir(parents=True)
    squatter.write_bytes(b"something else")
    rec = receive_file(run, csv)
    assert rec.status == "failed" and "NOT overwritten" in rec.detail
    assert squatter.read_bytes() == b"something else"
    assert not raw_rows(db)


def test_source_changing_during_copy_is_detected(run, settings, db, csv, monkeypatch):
    import qmap.storage.registry as reg

    real = reg.copy_durably

    def corrupting_copy(src, dest):
        real(src, dest)
        with open(dest, "ab") as fh:
            fh.write(b"extra")

    monkeypatch.setattr(reg, "copy_durably", corrupting_copy)
    rec = receive_file(run, csv)
    assert rec.status == "failed" and "changed while" in rec.detail
    assert not list(settings.raw_incoming_dir.iterdir()) and not raw_rows(db)


def test_concurrent_ingest_of_identical_content_yields_one_raw_and_all_receipts(run, settings, db, src):
    p = write_delimited(src / "shared.csv", HEADER, ROWS)
    results, errors = [], []
    barrier = threading.Barrier(8)

    def go(i):
        try:
            barrier.wait()
            q = src / f"copy_{i}.csv"
            q.write_bytes(p.read_bytes())
            results.append(receive_file(run, q, note=str(i)))
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert all(r.ok for r in results)
    assert len(raw_rows(db)) == 1
    assert len({r.raw_dataset_id for r in results}) == 1
    assert len(events(db)) == 8 and all(e["status"] in ("registered_new", "reused_existing") for e in events(db))
    assert sum(1 for e in events(db) if e["status"] == "registered_new") == 1
    assert len([f for f in (settings.data_root / "Raw_Data").rglob("*") if f.is_file() and "_incoming" not in f.parts]) == 1
    assert not list(settings.raw_incoming_dir.iterdir())


def _ingest_in_process(args):
    data, out, code, path, idx = args
    from qmap.core.config import load_settings
    from qmap.core.runs import finish_run, start_run
    from qmap.storage.db import Database
    from qmap.storage.registry import receive_file as rf

    s = load_settings(None, env={"QMAP_DATA_ROOT": data, "QMAP_OUTPUT_ROOT": out}, code_root=code)
    d = Database(s.db_path)
    r = start_run(s, d, "FOUND", area="Ingestion", recover=False)
    res = rf(r, path, note=str(idx))
    finish_run(r)
    return res.status


def test_concurrent_processes_ingesting_identical_content(settings, db, roots, src):
    import multiprocessing

    p = write_delimited(src / "shared.csv", HEADER, ROWS)
    args = [(str(settings.data_root), str(settings.output_root), str(roots["code"]), str(p), i) for i in range(6)]
    with multiprocessing.get_context("spawn").Pool(3) as pool:
        statuses = pool.map(_ingest_in_process, args)
    assert sorted(set(statuses)) <= ["registered_new", "reused_existing"]
    assert statuses.count("registered_new") == 1
    assert len(raw_rows(db)) == 1 and len(events(db)) == 6
    assert not list(settings.raw_incoming_dir.iterdir())


def test_start_run_performs_recovery(settings, db, run, csv):
    with pytest.raises(InjectedFault):
        with inject("after_rename"):
            receive_file(run, csv)
    finish_run(run)
    # a later run (after the stale window) finishes the interrupted registration automatically
    from qmap.core import runs as runs_mod

    import dataclasses

    settings_zero = dataclasses.replace(settings, stale_minutes=0)
    nxt = runs_mod.start_run(settings_zero, db, "FOUND", area="Ingestion")
    assert len(raw_rows(db)) == 1
    finish_run(nxt)


def test_faults_are_inert_by_default():
    faults.maybe_fail("after_hash")  # does nothing
    with pytest.raises(ValueError):
        with inject("not_a_step"):
            pass
