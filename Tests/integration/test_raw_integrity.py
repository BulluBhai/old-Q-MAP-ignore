"""A registered raw file is verified against its registered SHA-256 before it is reused or processed.

File size is not proof of integrity. A same-size corruption of the stored copy must be detected, the
corrupt copy must never be processed, overwritten or deleted, and recovery must be explicit and audited.
"""

import os
import threading

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest, make_profile
from qmap.cli import main
from qmap.core.errors import IngestError
from qmap.core.runs import finish_run, start_run
from qmap.storage import registry as reg
from qmap.storage.faults import InjectedFault, inject
from qmap.storage.files import is_read_only, sha256_file
from qmap.storage.recovery import recover_incomplete, verify_registry
from qmap.storage.registry import receive_file, restore_raw_file

ROWS = daily_rows(8)


@pytest.fixture
def good(src):
    return write_delimited(src / "good.csv", HEADER, ROWS)


def corrupt_same_size(path):
    """Flip one bit in the middle of the file: identical size, different content."""
    mode = path.stat().st_mode
    size = path.stat().st_size
    os.chmod(path, 0o600)
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0x01
    path.write_bytes(bytes(data))
    os.chmod(path, mode)
    assert path.stat().st_size == size
    return bytes(data)


def stored_path(settings, rec):
    return settings.data_path(rec.relative_path)


def events(db):
    return db.query("SELECT * FROM ingest_events ORDER BY event_id")


def raw_rows(db):
    return db.query("SELECT * FROM datasets WHERE layer='raw'")


def quarantined(settings):
    return sorted(settings.raw_quarantine_dir.glob("*.corrupt"))


# ---- normal reuse ----------------------------------------------------------------------------------------
def test_intact_registered_file_is_reused_only_after_its_hash_is_verified(run, settings, db, good, monkeypatch):
    first = receive_file(run, good)
    hashed = []
    real = reg.sha256_file
    monkeypatch.setattr(reg, "sha256_file", lambda p: (hashed.append(os.fspath(p)), real(p))[1])
    again = receive_file(run, good)
    assert again.status == "reused_existing" and again.raw_dataset_id == first.raw_dataset_id
    assert "verified" in again.detail
    assert os.fspath(stored_path(settings, first)) in hashed  # the STORED copy was hashed, not just sized
    assert len(raw_rows(db)) == 1 and len(events(db)) == 2


def test_intact_reuse_leaves_the_stored_file_untouched(run, settings, db, good):
    first = receive_file(run, good)
    stored = stored_path(settings, first)
    before = (stored.read_bytes(), stored.stat().st_mtime_ns, stored.stat().st_mode)
    receive_file(run, good)
    assert (stored.read_bytes(), stored.stat().st_mtime_ns, stored.stat().st_mode) == before


# ---- same-size corruption ------------------------------------------------------------------------------
def test_same_size_corruption_is_detected_and_the_stored_file_is_not_touched(run, settings, db, good):
    first = receive_file(run, good)
    stored = stored_path(settings, first)
    corrupted = corrupt_same_size(stored)
    mode_before = stored.stat().st_mode

    rec = receive_file(run, good)

    assert rec.status == "failed" and not rec.ok
    assert rec.detail.startswith("E_RAW_CORRUPT") and f"--dataset-id {first.raw_dataset_id}" in rec.detail
    assert "restore-raw" in rec.detail and "NOT used, overwritten or deleted" in rec.detail
    assert stored.read_bytes() == corrupted and stored.stat().st_mode == mode_before  # not overwritten, not repaired
    assert not quarantined(settings)  # detection alone moves nothing
    assert len(raw_rows(db)) == 1 and not list(settings.raw_incoming_dir.iterdir())
    ev = events(db)[-1]
    assert ev["status"] == "failed" and ev["raw_dataset_id"] == first.raw_dataset_id
    assert ev["detail"] == rec.detail and ev["sha256"] == first.sha256
    assert verify_registry(settings, db).checksum_mismatches == [first.relative_path]


def test_truncated_stored_file_is_refused_the_same_way(run, settings, db, good):
    first = receive_file(run, good)
    stored = stored_path(settings, first)
    os.chmod(stored, 0o600)
    stored.write_bytes(stored.read_bytes()[:-5])
    rec = receive_file(run, good)
    assert rec.status == "failed" and rec.detail.startswith("E_RAW_CORRUPT")
    assert len(raw_rows(db)) == 1


def test_unreadable_stored_file_is_refused_not_trusted(run, settings, db, good, monkeypatch):
    first = receive_file(run, good)
    stored = os.fspath(stored_path(settings, first))
    real = reg.sha256_file

    def flaky(p):
        if os.fspath(p) == stored:
            raise PermissionError("simulated read failure")
        return real(p)

    monkeypatch.setattr(reg, "sha256_file", flaky)
    rec = receive_file(run, good)
    assert rec.status == "failed" and "E_RAW_CORRUPT" in rec.detail and "unreadable" in rec.detail


# ---- the corrupt copy is never processed -----------------------------------------------------------------
def test_ingestion_refuses_to_process_a_corrupt_copy_even_after_an_accepted_attempt(run, settings, db, good):
    first = do_ingest(run, good)
    assert first.outcome == "accepted"
    raw = db.one("SELECT * FROM datasets WHERE layer='raw'")
    corrupt_same_size(settings.data_path(raw["relative_path"]))

    again = do_ingest(run, good)
    assert again.outcome == "failed" and "E_RAW_CORRUPT" in again.message  # NOT 'reused'
    assert not again.ok
    assert len(db.query("SELECT 1 FROM ingest_attempts")) == 1  # nothing was processed or recorded as processed
    assert len(db.query("SELECT 1 FROM datasets WHERE layer='cleaned'")) == 1

    # a new profile version would normally reprocess: it must be refused too, and must not supersede anything
    v2 = do_ingest(run, good, make_profile(profile_version=2))
    assert v2.outcome == "failed"
    assert len(db.query("SELECT 1 FROM ingest_attempts")) == 1
    assert [r["status"] for r in db.query("SELECT status FROM datasets WHERE layer='cleaned'")] == ["active"]


def test_a_corrupt_copy_is_not_processed_for_a_first_ever_attempt_either(run, settings, db, good):
    rec = receive_file(run, good)  # registered, never processed
    corrupt_same_size(stored_path(settings, rec))
    res = do_ingest(run, good)
    assert res.outcome == "failed"
    assert not db.query("SELECT 1 FROM ingest_attempts") and not db.query("SELECT 1 FROM datasets WHERE layer='cleaned'")


# ---- explicit, safe recovery ------------------------------------------------------------------------------
def test_restore_refuses_without_a_written_reason(run, settings, db, good):
    rec = receive_file(run, good)
    corrupted = corrupt_same_size(stored_path(settings, rec))
    for reason in ("", "   ", None):
        with pytest.raises(IngestError) as e:
            restore_raw_file(run, rec.raw_dataset_id, good, reason=reason)
        assert e.value.code == "E_REASON_REQUIRED"
    assert stored_path(settings, rec).read_bytes() == corrupted and not quarantined(settings)


def test_restore_refuses_a_file_that_does_not_match_the_registered_checksum(run, settings, db, good, src):
    rec = receive_file(run, good)
    corrupted = corrupt_same_size(stored_path(settings, rec))
    wrong = write_delimited(src / "other.csv", HEADER, daily_rows(8, seed=99))
    n_events = len(events(db))
    with pytest.raises(IngestError) as e:
        restore_raw_file(run, rec.raw_dataset_id, wrong, reason="trying the wrong file")
    assert e.value.code == "E_RESTORE_MISMATCH"
    assert stored_path(settings, rec).read_bytes() == corrupted and not quarantined(settings)
    assert len(events(db)) == n_events  # nothing recorded as a restore, nothing changed


def test_restore_refuses_when_the_stored_file_is_intact_or_the_dataset_is_unknown(run, settings, db, good):
    rec = receive_file(run, good)
    with pytest.raises(IngestError) as e:
        restore_raw_file(run, rec.raw_dataset_id, good, reason="no reason to")
    assert e.value.code == "E_RAW_INTACT"
    with pytest.raises(IngestError) as e2:
        restore_raw_file(run, 9999, good, reason="x")
    assert e2.value.code == "E_DATASET_NOT_FOUND"
    with pytest.raises(IngestError) as e3:
        restore_raw_file(run, rec.raw_dataset_id, good.parent / "nope.csv", reason="x")
    assert e3.value.code == "E_RESTORE_SOURCE"


def test_restore_preserves_the_corrupt_copy_restores_the_original_and_keeps_the_audit_trail(run, settings, db, good):
    first = do_ingest(run, good)
    assert first.outcome == "accepted"
    raw = db.one("SELECT * FROM datasets WHERE layer='raw'")
    stored = settings.data_path(raw["relative_path"])
    original = stored.read_bytes()
    corrupted = corrupt_same_size(stored)
    failed = do_ingest(run, good)
    assert failed.outcome == "failed"

    receipt = restore_raw_file(run, raw["dataset_id"], good, reason="bit rot on the data drive; restored from the vendor file")

    # the stored file is the original again, read-only, and registered identity is unchanged
    assert stored.read_bytes() == original and sha256_file(stored) == raw["sha256"] and is_read_only(stored)
    after = db.one("SELECT * FROM datasets WHERE dataset_id=?", (raw["dataset_id"],))
    assert dict(after) == dict(raw) and len(raw_rows(db)) == 1
    # the corrupt copy was PRESERVED, byte for byte, not deleted
    q = quarantined(settings)
    assert len(q) == 1 and q[0].read_bytes() == corrupted and q[0].name.startswith(raw["sha256"])
    # audit trail: registration, the failed receipt and the restore are all still there, in order
    ev = events(db)
    assert [e["status"] for e in ev] == ["registered_new", "failed", "reused_existing"]
    assert ev[1]["detail"].startswith("E_RAW_CORRUPT")
    assert ev[2]["source_label"] == "restore-raw" and "bit rot" in ev[2]["note"]
    assert "RESTORED" in ev[2]["detail"] and settings.to_relative(q[0]) in ev[2]["detail"]
    assert receipt.status == "reused_existing"
    # everything is consistent again; the quarantined evidence is not reported as an orphan
    report = verify_registry(settings, db)
    assert not report.needs_attention and not report.orphan_raw_files
    assert not list(settings.raw_incoming_dir.iterdir())
    # the earlier accepted result is still valid and a normal re-ingest works again
    assert do_ingest(run, good).outcome == "reused"
    assert [a["outcome"] for a in db.query("SELECT outcome FROM ingest_attempts ORDER BY attempt_id")] == ["accepted", "reused"]


def test_restore_when_the_stored_file_is_missing_needs_no_quarantine(run, settings, db, good):
    rec = receive_file(run, good)
    stored = stored_path(settings, rec)
    os.chmod(stored, 0o600)
    stored.unlink()
    out = restore_raw_file(run, rec.raw_dataset_id, good, reason="file was deleted by mistake")
    assert sha256_file(stored) == rec.sha256 and not quarantined(settings) and "had been missing" in out.detail


@pytest.mark.parametrize("step", ["restore_after_quarantine", "restore_after_replace"])
def test_a_crash_during_restore_is_recoverable_and_loses_no_evidence(step, run, settings, db, good):
    rec = receive_file(run, good)
    stored = stored_path(settings, rec)
    corrupted = corrupt_same_size(stored)
    with pytest.raises(InjectedFault):
        with inject(step):
            restore_raw_file(run, rec.raw_dataset_id, good, reason="crash test")

    recover_incomplete(settings, db, stale_minutes=0)
    assert not list(settings.raw_incoming_dir.iterdir())
    assert all(e["status"] != "started" for e in events(db))
    q = quarantined(settings)
    assert len(q) == 1 and q[0].read_bytes() == corrupted  # the evidence survives the crash

    # whichever step it stopped at, ingesting the original again ends in a verified, consistent registry
    again = receive_file(run, good)
    assert again.ok
    assert sha256_file(stored) == rec.sha256
    assert not verify_registry(settings, db).needs_attention and len(raw_rows(db)) == 1


# ---- legitimate use and concurrency are not broken --------------------------------------------------------
def test_concurrent_receipts_of_an_intact_registered_file(run, settings, db, good):
    rec = receive_file(run, good)
    results, errors = [], []
    barrier = threading.Barrier(8)

    def go():
        try:
            barrier.wait()
            results.append(receive_file(run, good))
        except Exception as exc:  # pragma: no cover
            errors.append(repr(exc))

    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and all(r.status == "reused_existing" for r in results)
    assert len(raw_rows(db)) == 1 and len(events(db)) == 9
    assert sha256_file(stored_path(settings, rec)) == rec.sha256


def test_concurrent_receipts_of_a_corrupt_registered_file_all_refuse_and_change_nothing(run, settings, db, good):
    rec = receive_file(run, good)
    corrupted = corrupt_same_size(stored_path(settings, rec))
    results, errors = [], []
    barrier = threading.Barrier(6)

    def go():
        try:
            barrier.wait()
            results.append(receive_file(run, good))
        except Exception as exc:  # pragma: no cover
            errors.append(repr(exc))

    ts = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and all(r.status == "failed" for r in results)
    assert stored_path(settings, rec).read_bytes() == corrupted and len(raw_rows(db)) == 1
    assert not list(settings.raw_incoming_dir.iterdir())


def test_legitimate_new_and_changed_files_still_register_normally(run, settings, db, src):
    p = src / "same_name.csv"
    write_delimited(p, HEADER, ROWS)
    a = receive_file(run, p)
    write_delimited(p, HEADER, ROWS[:-1])
    b = receive_file(run, p)  # different content, same filename: a new raw dataset, not a "corruption"
    assert a.status == b.status == "registered_new" and a.raw_dataset_id != b.raw_dataset_id
    assert not verify_registry(settings, db).needs_attention


# ---- command line ------------------------------------------------------------------------------------------
def test_cli_detects_corruption_and_restores_explicitly(src, roots, tmp_path, capsys):
    from fixtures.profiles import profile_text

    cfg = tmp_path / "qmap.local.toml"
    cfg.write_text(f'[paths]\ndata_root = "{roots["data"].as_posix()}"\noutput_root = "{roots["output"].as_posix()}"\n')
    prof = tmp_path / "p.toml"
    prof.write_text(profile_text(profile_id="cli_p"))
    f = write_delimited(src / "cli.csv", HEADER, ROWS)
    base = ["--config", str(cfg)]
    assert main(base + ["ingest", "--profile", str(prof), str(f)]) == 0
    capsys.readouterr()

    stored = next(p for p in (roots["data"] / "Raw_Data").rglob("*.txt") if "_incoming" not in p.parts)
    corrupt_same_size(stored)

    assert main(base + ["verify"]) == 1
    out = capsys.readouterr().out
    assert "checksum_mismatches" in out and "restore-raw" in out

    assert main(base + ["ingest", "--profile", str(prof), str(f)]) == 1
    out = capsys.readouterr().out
    assert "FAILED" in out and "E_RAW_CORRUPT" in out and "restore-raw --dataset-id 1" in out

    assert main(base + ["restore-raw", "--dataset-id", "1", "--from", str(f), "--reason", "bit rot"]) == 0
    assert "RESTORED" in capsys.readouterr().out
    assert main(base + ["verify"]) == 0
    assert main(base + ["ingest", "--profile", str(prof), str(f)]) == 0
    assert "REUSED" in capsys.readouterr().out


def test_cli_restore_requires_a_reason_and_rejects_the_wrong_file(src, roots, tmp_path, capsys):
    cfg = tmp_path / "qmap.local.toml"
    cfg.write_text(f'[paths]\ndata_root = "{roots["data"].as_posix()}"\noutput_root = "{roots["output"].as_posix()}"\n')
    f = write_delimited(src / "x.csv", HEADER, ROWS)
    other = write_delimited(src / "y.csv", HEADER, daily_rows(8, seed=50))
    with pytest.raises(SystemExit) as e:
        main(["--config", str(cfg), "restore-raw", "--dataset-id", "1", "--from", str(f)])
    assert e.value.code == 2  # --reason is mandatory
    from qmap.core.config import load_settings
    from qmap.storage.db import open_database

    s = load_settings(cfg)
    db = open_database(s.db_path)
    r = start_run(s, db, "FOUND", area="Ingestion")
    rec = receive_file(r, f)
    finish_run(r)
    corrupt_same_size(s.data_path(rec.relative_path))
    assert main(["--config", str(cfg), "restore-raw", "--dataset-id", str(rec.raw_dataset_id), "--from", str(other),
                 "--reason", "wrong file"]) == 2
    assert "E_RESTORE_MISMATCH" in capsys.readouterr().err
