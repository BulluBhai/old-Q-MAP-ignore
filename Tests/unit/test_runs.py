import json
import multiprocessing
import threading
from datetime import datetime, timedelta, timezone

import pytest

from qmap.core.runs import finish_run, mark_interrupted_runs, run_context, start_run
from qmap.storage.db import Database
from qmap.storage.files import sha256_file

FIXED = datetime(2026, 10, 31, 13, 58, 0, tzinfo=timezone.utc)


def test_run_id_format_and_folder(settings, db):
    run = start_run(settings, db, "FOUND", area="Ingestion", now=FIXED)
    assert run.run_id == "FOUND_20261031_135800"
    assert run.dir == settings.output_root / "Ingestion" / run.run_id
    assert run.dir.is_dir()
    finish_run(run)


def test_same_second_gets_numeric_suffix_and_nothing_is_overwritten(settings, db):
    a = start_run(settings, db, "FOUND", area="Ingestion", now=FIXED)
    (a.dir / "keep.txt").write_text("first")
    b = start_run(settings, db, "FOUND", area="Ingestion", now=FIXED)
    c = start_run(settings, db, "FOUND", area="Ingestion", now=FIXED)
    assert [a.run_id, b.run_id, c.run_id] == ["FOUND_20261031_135800", "FOUND_20261031_135800_02",
                                              "FOUND_20261031_135800_03"]
    assert (a.dir / "keep.txt").read_text() == "first"
    for r in (a, b, c):
        finish_run(r)


def test_id_already_used_in_another_area_moves_to_next_suffix_and_cleans_up(settings, db):
    a = start_run(settings, db, "FOUND", area="AreaA", now=FIXED)
    b = start_run(settings, db, "FOUND", area="AreaB", now=FIXED)  # folder is free in AreaB, but the ID is taken
    assert b.run_id == "FOUND_20261031_135800_02"
    assert not (settings.output_root / "AreaB" / "FOUND_20261031_135800").exists()  # released empty folder
    finish_run(a)
    finish_run(b)


def test_concurrent_threads_get_unique_ids(settings, db):
    ids, errors = [], []
    lock = threading.Lock()

    def go():
        try:
            r = start_run(settings, db, "FOUND", area="Ingestion", now=FIXED, recover=False)
            with lock:
                ids.append(r.run_id)
            finish_run(r)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=go) for _ in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert len(ids) == len(set(ids)) == 20
    assert len({p.name for p in (settings.output_root / "Ingestion").iterdir()}) == 20


def _proc(args):
    data_root, out_root, code_root = args
    from qmap.core.config import load_settings

    s = load_settings(None, env={"QMAP_DATA_ROOT": data_root, "QMAP_OUTPUT_ROOT": out_root}, code_root=code_root)
    d = Database(s.db_path)
    r = start_run(s, d, "FOUND", area="Ingestion", now=FIXED, recover=False)
    finish_run(r)
    return r.run_id


def test_concurrent_processes_get_unique_ids(settings, db, roots):
    args = (str(settings.data_root), str(settings.output_root), str(roots["code"]))
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(4) as pool:
        ids = pool.map(_proc, [args] * 12)
    assert len(set(ids)) == 12


def test_manifest_lists_outputs_with_matching_hashes(settings, db):
    run = start_run(settings, db, "FOUND", area="Ingestion", params={"a": 1}, now=FIXED)
    (run.dir / "summary.csv").write_text("x,y\n1,2\n")
    run.logger.info("hello")
    manifest_path = finish_run(run)
    m = json.loads(manifest_path.read_text())
    assert m["run_id"] == run.run_id and m["status"] == "completed" and m["parameters"] == {"a": 1}
    paths = {o["relative_path"]: o for o in m["outputs"]}
    assert set(paths) == {"summary.csv", "run_log.txt"}
    assert paths["summary.csv"]["sha256"] == sha256_file(run.dir / "summary.csv")
    assert "hello" in (run.dir / "run_log.txt").read_text()
    assert run.run_id in (run.dir / "run_log.txt").read_text()
    # registry association
    rows = {r["relative_path"]: r for r in db.query("SELECT * FROM run_outputs WHERE run_id=?", (run.run_id,))}
    rel = run.relative_dir
    assert set(rows) == {f"{rel}/summary.csv", f"{rel}/run_log.txt", f"{rel}/run_manifest.json"}
    assert rows[f"{rel}/summary.csv"]["sha256"] == paths["summary.csv"]["sha256"]
    assert rows[f"{rel}/run_manifest.json"]["sha256"] == sha256_file(manifest_path)
    run_row = db.one("SELECT * FROM runs WHERE run_id=?", (run.run_id,))
    assert run_row["status"] == "completed" and run_row["output_path"] == rel


def test_no_temp_files_left_after_manifest(settings, db):
    run = start_run(settings, db, "FOUND", area="Ingestion", now=FIXED)
    finish_run(run)
    assert not [p for p in run.dir.iterdir() if p.name.endswith(".tmp")]


def test_failed_run_keeps_folder_log_and_manifest(settings, db):
    with pytest.raises(RuntimeError):
        with run_context(settings, db, "FOUND", area="Ingestion", now=FIXED) as run:
            raise RuntimeError("boom")
    row = db.one("SELECT * FROM runs WHERE run_id=?", (run.run_id,))
    assert row["status"] == "failed" and "boom" in row["error_message"]
    assert (run.dir / "run_manifest.json").is_file() and (run.dir / "run_log.txt").is_file()


def test_finish_twice_is_harmless(settings, db):
    run = start_run(settings, db, "FOUND", area="Ingestion", now=FIXED)
    finish_run(run)
    finish_run(run)
    assert db.one("SELECT status FROM runs WHERE run_id=?", (run.run_id,))["status"] == "completed"


def test_interrupted_runs_are_marked_failed(settings, db):
    run = start_run(settings, db, "FOUND", area="Ingestion", now=FIXED)  # never finished: simulated crash
    assert mark_interrupted_runs(db, stale_minutes=60) == []  # still fresh
    later = datetime.now(timezone.utc) + timedelta(minutes=61)
    assert mark_interrupted_runs(db, stale_minutes=60, now=later) == [run.run_id]
    row = db.one("SELECT * FROM runs WHERE run_id=?", (run.run_id,))
    assert row["status"] == "failed" and row["error_message"] == "interrupted"
    assert run.dir.is_dir()  # folder kept


def test_invalid_final_status_rejected(settings, db):
    run = start_run(settings, db, "FOUND", area="Ingestion", now=FIXED)
    with pytest.raises(ValueError):
        finish_run(run, "running")
    finish_run(run)


def test_concurrent_runs_in_one_process_keep_separate_logs(settings, db):
    runs, errors = {}, []
    barrier = threading.Barrier(2)

    def go(tag):
        try:
            r = start_run(settings, db, "FOUND", area="Ingestion", now=FIXED, recover=False)
            runs[tag] = r
            barrier.wait()
            for i in range(30):
                r.logger.info("message from %s #%d", tag, i)
            finish_run(r)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    ts = [threading.Thread(target=go, args=(t,)) for t in ("alpha", "beta")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors
    for tag, other in (("alpha", "beta"), ("beta", "alpha")):
        text = (runs[tag].dir / "run_log.txt").read_text()
        assert text.count(f"message from {tag}") == 30 and f"message from {other}" not in text
        assert runs[tag].run_id in text
