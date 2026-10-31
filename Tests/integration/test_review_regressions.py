"""Regression tests for the defects found in the independent PR #1 review (31-Oct-26).

Each test names its finding ID (see docs/decision_log.md, D2-22 onwards). Every test here failed on the code
as first submitted and passes after the fix.
"""

import dataclasses
import os
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest
from qmap.core.config import load_settings
from qmap.core.errors import ConfigError, QmapError
from qmap.core.runs import finish_run, mark_interrupted_runs, start_run
from qmap.storage import recovery as recovery_mod
from qmap.storage import registry as reg
from qmap.storage.db import Database, open_database
from qmap.storage.faults import InjectedFault, inject
from qmap.storage.files import sha256_file
from qmap.storage.recovery import recover_incomplete, verify_registry
from qmap.storage.registry import receive_file

ROWS = daily_rows(8)


@pytest.fixture
def good(src):
    return write_delimited(src / "good.csv", HEADER, ROWS)


def raw_rows(db):
    return db.query("SELECT * FROM datasets WHERE layer='raw'")


def events(db):
    return db.query("SELECT * FROM ingest_events ORDER BY event_id")


# ---- R-01 destination race: a file appearing after the "does it exist?" check is never replaced ------------
def test_r01_destination_created_after_the_existence_check_is_not_overwritten(run, settings, db, good, monkeypatch):
    digest = sha256_file(good)
    final = settings.data_root / "Raw_Data" / digest[:2] / f"{digest}.txt"
    real_exists = Path.exists

    def racing_exists(self):
        # Simulate another process creating the destination right after the check said "absent".
        if self == final:
            final.parent.mkdir(parents=True, exist_ok=True)
            if not real_exists(final):
                final.write_bytes(b"another process's different content")
            return False
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", racing_exists)
    # Also cover implementations without an existence check: create the squatter as soon as the copy is verified.
    real_sha = reg.sha256_file

    def sha_then_squat(path):
        out = real_sha(path)
        if Path(path).parent == settings.raw_incoming_dir:
            final.parent.mkdir(parents=True, exist_ok=True)
            if not real_exists(final):
                final.write_bytes(b"another process's different content")
        return out

    monkeypatch.setattr(reg, "sha256_file", sha_then_squat)
    rec = receive_file(run, good)
    monkeypatch.undo()
    assert final.read_bytes() == b"another process's different content"  # NOT replaced
    assert rec.status == "failed" and "NOT overwritten" in rec.detail
    assert not raw_rows(db)
    assert not list(settings.raw_incoming_dir.iterdir())


def test_r01_identical_content_appearing_concurrently_is_adopted_not_replaced(run, settings, db, good, monkeypatch):
    digest = sha256_file(good)
    final = settings.data_root / "Raw_Data" / digest[:2] / f"{digest}.txt"
    real_sha = reg.sha256_file
    placed = {}

    def sha_then_twin(path):
        out = real_sha(path)
        if Path(path).parent == settings.raw_incoming_dir and not final.exists():
            final.parent.mkdir(parents=True, exist_ok=True)
            final.write_bytes(good.read_bytes())
            placed["ino"] = os.stat(final).st_ino
        return out

    monkeypatch.setattr(reg, "sha256_file", sha_then_twin)
    rec = receive_file(run, good)
    monkeypatch.undo()
    assert rec.status == "registered_new"
    assert os.stat(final).st_ino == placed["ino"]  # the other writer's file was kept, not swapped
    assert sha256_file(final) == digest and len(raw_rows(db)) == 1
    assert not list(settings.raw_incoming_dir.iterdir())


# ---- R-02 a live run is never treated as interrupted merely because it is old ---------------------------
def test_r02_live_run_older_than_the_stale_limit_is_not_marked_interrupted(run, settings, db, good):
    with pytest.raises(InjectedFault):
        with inject("after_temp_copy"):
            receive_file(run, good)
    # The run's process is still alive (it holds its run lock), even though the stale limit has passed.
    report = recover_incomplete(settings, db, stale_minutes=0)
    assert run.run_id not in report.interrupted_runs
    assert not report.failed_events and not report.deleted_temp_files
    assert db.one("SELECT status FROM runs WHERE run_id=?", (run.run_id,))["status"] == "running"
    assert events(db)[0]["status"] == "started"
    assert list(settings.raw_incoming_dir.iterdir())  # its temp file survives


_CHILD = textwrap.dedent("""
    import os, sys
    from qmap.core.config import load_settings
    from qmap.core.runs import start_run
    from qmap.storage.db import Database
    s = load_settings(None, env={"QMAP_DATA_ROOT": sys.argv[1], "QMAP_OUTPUT_ROOT": sys.argv[2]}, code_root=sys.argv[3])
    r = start_run(s, Database(s.db_path), "FOUND", area="Ingestion", recover=False)
    print(r.run_id, flush=True)
    sys.stdin.readline()          # wait until the parent has checked
    os._exit(0)                   # die without finishing the run (a crash)
""")


def test_r02_run_of_another_live_process_is_left_alone_and_recovered_after_it_dies(settings, db, roots):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    child = subprocess.Popen([sys.executable, "-c", _CHILD, str(settings.data_root), str(settings.output_root),
                              str(roots["code"])], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    try:
        run_id = child.stdout.readline().strip()
        assert run_id
        assert mark_interrupted_runs(db, 0, settings=settings) == []  # alive: lock held by the other process
        child.stdin.write("\n")
        child.stdin.flush()
        child.wait(timeout=60)
    finally:
        if child.poll() is None:  # pragma: no cover
            child.kill()
    assert mark_interrupted_runs(db, 0, settings=settings) == [run_id]  # dead: lock released by the OS


# ---- R-03 recovery never deletes the temp file of an ingest that started while recovery was running -------
def test_r03_temp_file_of_an_event_created_during_recovery_is_not_deleted(run, settings, db, good, monkeypatch):
    other = start_run(settings, db, "FOUND", area="Ingestion", recover=False)
    real_query = Database.query
    created = {}

    def query_then_new_ingest(self, sql, params=()):
        rows = real_query(self, sql, params)
        if "e.status = 'started'" in sql and not created:
            # another process begins an ingest right after recovery listed the live events
            created["eid"] = reg._insert_event(db, other, original_path="/x/y.csv", original_filename="y.csv",
                                               original_extension=".csv", file_size=1, file_mtime=None,
                                               source_label=None, note=None, sha256="ab" * 32,
                                               detected_format="delimited_text",
                                               intended_relative_path="Raw_Data/ab/" + "ab" * 32 + ".txt",
                                               status="started")
            (settings.raw_incoming_dir / f"{created['eid']}.tmp").write_bytes(b"being written")
        return rows

    monkeypatch.setattr(Database, "query", query_then_new_ingest)
    recover_incomplete(settings, db, stale_minutes=0)
    monkeypatch.undo()
    assert (settings.raw_incoming_dir / f"{created['eid']}.tmp").exists()
    finish_run(other)


# ---- R-04 an override the profile does not use must not make a repeat ingest crash -----------------------
def test_r04_unused_override_is_not_a_different_request_and_does_not_crash(run, db, good):
    first = do_ingest(run, good)  # profile has a fixed timeframe 1D
    second = do_ingest(run, good, timeframe="1D")  # the same request in substance
    third = do_ingest(run, good, symbol="IGNORED")  # the profile's symbol is fixed, so this is not used
    assert first.outcome == "accepted"
    assert (second.outcome, third.outcome) == ("reused", "reused")
    assert len(db.query("SELECT * FROM datasets WHERE layer='cleaned'")) == 1


# ---- R-05 a finished receipt can never be rewritten -------------------------------------------------------
def test_r05_a_finalised_event_cannot_be_finalised_again(run, settings, db, good):
    rec = receive_file(run, good)
    with pytest.raises((sqlite3.IntegrityError, RuntimeError)):
        reg._commit_registration(db, rec.event_id, rec.sha256, rec.detected, rec.relative_path, None)
    with pytest.raises(sqlite3.IntegrityError):
        db.connection().execute("UPDATE ingest_events SET status='failed', raw_dataset_id=NULL WHERE event_id=?",
                                (rec.event_id,))
    assert events(db)[0]["status"] == "registered_new"


# ---- R-06 the stored profile snapshot (historical explanation) cannot be rewritten ------------------------
def test_r06_profile_snapshots_are_immutable(run, db, good):
    do_ingest(run, good)
    conn = db.connection()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE source_profiles SET content_text = 'rewritten'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM source_profiles")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM runs")


# ---- R-07 validation settings are recorded (their effect on reuse: Tests/integration/test_config_fingerprint.py) --
def test_r07_validation_settings_are_recorded_with_every_attempt(run, db, good):
    import json

    first = do_ingest(run, good)
    att = db.one("SELECT validation_settings_json FROM ingest_attempts WHERE attempt_id=?", (first.attempt_id,))
    recorded = json.loads(att["validation_settings_json"])
    assert recorded["min_rows"] == 1 and recorded["max_daily_move_pct"] == 25.0 and "today" in recorded


# ---- R-08 a failed migration leaves no open transaction and nothing half-applied -------------------------
def test_r08_failed_migration_rolls_back_and_leaves_the_connection_usable(tmp_path, monkeypatch):
    from qmap.storage import db as dbmod

    bad = [(1, "first", "CREATE TABLE t(x INTEGER CHECK (x > 0));"),
           (2, "second", "CREATE TABLE u(y);\nINSERT INTO t VALUES (-1);")]
    monkeypatch.setattr(dbmod, "MIGRATIONS", bad)
    d = Database(tmp_path / "m.sqlite")
    with pytest.raises(sqlite3.Error):
        d.migrate()
    assert not d.connection().in_transaction
    assert d.current_version() == 1
    assert not d.query("SELECT name FROM sqlite_master WHERE name='u'")  # nothing of migration 2 remains
    with d.transaction() as conn:  # the connection still works
        conn.execute("INSERT INTO t VALUES (1)")


def test_r08_database_from_newer_code_is_refused(tmp_path):
    d = open_database(tmp_path / "m.sqlite")
    with d.transaction() as conn:
        conn.execute("INSERT INTO schema_version(version, applied_at, description) VALUES (999, 'x', 'future')")
    with pytest.raises(QmapError, match="newer"):
        Database(tmp_path / "m.sqlite").migrate()


# ---- R-09 relative paths in the configuration file do not depend on the launch folder --------------------
def test_r09_relative_config_paths_resolve_against_the_config_file_not_the_working_folder(tmp_path, monkeypatch):
    base = tmp_path / "cfgdir"
    (base / "D").mkdir(parents=True)
    (base / "O").mkdir()
    code = tmp_path / "code"
    code.mkdir()
    cfg = base / "qmap.local.toml"
    cfg.write_text('[paths]\ndata_root = "D"\noutput_root = "O"\n', encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "D").mkdir(parents=True)
    (elsewhere / "O").mkdir()
    monkeypatch.chdir(elsewhere)  # e.g. IDLE started in another folder
    s = load_settings(cfg, env={}, code_root=code)
    assert s.data_root == (base / "D").resolve() and s.output_root == (base / "O").resolve()


def test_r09_relative_environment_paths_and_bad_numbers_are_clear_errors(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    with pytest.raises(ConfigError, match="full path"):
        load_settings(None, env={"QMAP_DATA_ROOT": "D", "QMAP_OUTPUT_ROOT": "O"}, code_root=code)
    (tmp_path / "D").mkdir()
    (tmp_path / "O").mkdir()
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'[paths]\ndata_root = "{(tmp_path / "D").as_posix()}"\noutput_root = "{(tmp_path / "O").as_posix()}"\n'
                   '[recovery]\nstale_minutes = "soon"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="stale_minutes"):
        load_settings(cfg, env={}, code_root=code)


# ---- R-10 cleaned-file cleanup re-checks registration and liveness at the moment of deletion ---------------
def test_r10_cleaned_file_registered_after_the_scan_started_is_not_deleted(run, settings, db, good, monkeypatch):
    res = do_ingest(run, good)
    rel = db.one("SELECT relative_path FROM datasets WHERE dataset_id=?", (res.dataset_ids[0],))["relative_path"]
    path = settings.data_path(rel)
    finish_run(run)
    real_query = Database.query

    def hide_cleaned_registration(self, sql, params=()):
        rows = real_query(self, sql, params)
        if sql.strip() == "SELECT relative_path FROM datasets":
            return [r for r in rows if r["relative_path"] != rel]  # as if it was committed just after this read
        return rows

    monkeypatch.setattr(Database, "query", hide_cleaned_registration)
    report = recover_incomplete(settings, db, stale_minutes=0)
    monkeypatch.undo()
    assert path.exists() and rel not in report.deleted_cleaned_orphans


def test_r10_unregistered_cleaned_file_of_a_live_run_is_not_deleted(run, settings, db, good):
    with pytest.raises(InjectedFault):
        with inject("before_result_commit"):
            do_ingest(run, good)
    files = [p for p in settings.cleaned_dir.rglob("*.parquet") if "_incoming" not in p.parts]
    assert files
    report = recover_incomplete(settings, db, stale_minutes=0)  # run still alive
    assert not report.deleted_cleaned_orphans and all(p.exists() for p in files)


# ---- R-11 recovery and verification survive unreadable or vanishing files ----------------------------------
def test_r11_verify_reports_an_unreadable_registered_file_instead_of_crashing(run, settings, db, good, monkeypatch):
    rec = receive_file(run, good)
    real = recovery_mod.sha256_file

    def unreadable(path):
        if Path(path) == settings.data_path(rec.relative_path):
            raise PermissionError(13, "locked by another program")
        return real(path)

    monkeypatch.setattr(recovery_mod, "sha256_file", unreadable)
    report = verify_registry(settings, db)
    assert any(rec.relative_path in x for x in report.unreadable_files)
    assert report.needs_attention


def test_r11_copy_failure_marks_the_receipt_failed_and_cleans_up(run, settings, db, good, monkeypatch):
    def failing_copy(src, dest):
        dest.write_bytes(b"partial")
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(reg, "copy_durably", failing_copy)
    rec = receive_file(run, good)
    assert rec.status == "failed" and "No space left" in rec.detail
    assert events(db)[0]["status"] == "failed"
    assert not list(settings.raw_incoming_dir.iterdir()) and not raw_rows(db)


# ---- R-12 recovery done at the start of a run is visible in that run's folder -----------------------------
def test_r12_recovery_at_run_start_is_written_to_the_new_run(run, settings, db, good):
    import json

    with pytest.raises(InjectedFault):
        with inject("after_rename"):
            receive_file(run, good)
    run._release_lock()  # the process "died"
    nxt = start_run(dataclasses.replace(settings, stale_minutes=0), db, "FOUND", area="Ingestion")
    report = json.loads((nxt.dir / "recovery_report.json").read_text(encoding="utf-8"))
    assert report["completed_events"] and run.run_id in report["interrupted_runs"]
    finish_run(nxt)
    assert "Recovery before this run" in (nxt.dir / "run_log.txt").read_text(encoding="utf-8")


# ---- R-13 registry paths can never point outside the data folder -------------------------------------------
@pytest.mark.parametrize("bad", ["../escape.txt", "Raw_Data/../../escape.txt", "/etc/passwd", "C:/x.txt", "", "a//b"])
def test_r13_registry_paths_cannot_escape_the_data_root(settings, bad):
    with pytest.raises(ValueError):
        settings.data_path(bad)
