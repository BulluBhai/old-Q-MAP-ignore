"""Reproduction refuses a damaged or incomplete historical record (beta closure, 09-Nov-26).

Each case damages ONE thing about an earlier, genuine MA Affinity run (its Run_Metadata file, its folder, its result
tables, or the registry rows reproduction relies on) and asks Q-MAP to reproduce it. Every case must:
  * be refused with a plain reason naming what is wrong (no Python error reaches the user);
  * create NO run: the runs table and the Research_Reports folder are unchanged;
  * leave the earlier run's files exactly as they were before the request (checked by SHA-256)."""

from __future__ import annotations

import json
import shutil
from datetime import date

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.analytical_engine import MA_AFFINITY, run_analysis
from qmap.analytical_engine import reproduce as R
from qmap.catalog import list_datasets
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap.storage.files import sha256_file

PARAMS = {"ma_types": "SMA", "ma_end": "40", "fwd_windows": "5,10"}


@pytest.fixture
def earlier(settings, db, tmp_path):
    folder = tmp_path / "files"
    folder.mkdir()
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(600, date(2021, 1, 4)), ohlcv(600, seed=8, base=200.0))]
    write_delimited(folder / "NSE_REFUSE.csv", HEADER, rows)
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE")
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        D.scan_source(run, src.source_id)
    (ds,) = list_datasets(db)
    res = run_analysis(settings, db, MA_AFFINITY, [ds.dataset_id], PARAMS)
    assert res.ok, res.message
    return res


def _edit_meta(res, change):
    data = json.loads(res.metadata_path.read_text(encoding="utf-8"))
    change(data)
    res.metadata_path.write_text(json.dumps(data), encoding="utf-8")


def _drop(key):
    return lambda m: m.pop(key)


def _set(key, value):
    return lambda m: m.__setitem__(key, value)


def _raw(change):
    return lambda m: change(m["raw_parameters"])


def _ds(change):
    return lambda m: change(m["input_datasets"][0])


META_CASES = {
    # file-level damage
    "invalid JSON": (lambda r: r.metadata_path.write_text("{not json", encoding="utf-8"), "damaged (not valid JSON"),
    "empty file": (lambda r: r.metadata_path.write_text("  \n", encoding="utf-8"), "is empty"),
    "not UTF-8": (lambda r: r.metadata_path.write_bytes(b"\xff\xfe\x00{"), "cannot be read"),
    "a JSON list": (lambda r: r.metadata_path.write_text("[1, 2]", encoding="utf-8"), "does not hold a run record"),
    "unreadable (a folder)": (lambda r: (r.metadata_path.unlink(), r.metadata_path.mkdir()), "cannot be read"),
    "two metadata files": (lambda r: shutil.copy2(r.metadata_path, r.run_dir / "Run_Metadata_extra.json"),
                           "has 2 Run_Metadata files"),
    "no metadata file": (lambda r: r.metadata_path.unlink(), "has no Run_Metadata file"),
    # missing or wrong fields
    "analysis_id missing": (lambda r: _edit_meta(r, _drop("analysis_id")), "'analysis_id' is missing or not an analysis name"),
    "analysis_id empty": (lambda r: _edit_meta(r, _set("analysis_id", "  ")), "'analysis_id' is missing or not an analysis name"),
    "analysis_id null": (lambda r: _edit_meta(r, _set("analysis_id", None)), "'analysis_id' is missing or not an analysis name"),
    "analysis_id a number": (lambda r: _edit_meta(r, _set("analysis_id", 7)), "'analysis_id' is missing or not an analysis name"),
    "analysis_id true": (lambda r: _edit_meta(r, _set("analysis_id", True)), "'analysis_id' is missing or not an analysis name"),
    "analysis_id a list": (lambda r: _edit_meta(r, _set("analysis_id", ["ma_affinity"])), "'analysis_id' is missing or not an analysis name"),
    "analysis_id an object": (lambda r: _edit_meta(r, _set("analysis_id", {"id": "ma_affinity"})), "'analysis_id' is missing or not an analysis name"),
    "analysis_id unknown": (lambda r: _edit_meta(r, _set("analysis_id", "no_such_analysis")),
                            "('no_such_analysis') is not available in this program"),
    "analysis_version missing": (lambda r: _edit_meta(r, _drop("analysis_version")), "'analysis_version' is missing or not a version number"),
    "analysis_version as text": (lambda r: _edit_meta(r, _set("analysis_version", "1")), "'analysis_version' is missing or not a version number"),
    "analysis_version true": (lambda r: _edit_meta(r, _set("analysis_version", True)), "'analysis_version' is missing or not a version number"),
    "analysis_version a list": (lambda r: _edit_meta(r, _set("analysis_version", [1])), "'analysis_version' is missing or not a version number"),
    "analysis_version an object": (lambda r: _edit_meta(r, _set("analysis_version", {"v": 1})), "'analysis_version' is missing or not a version number"),
    "analysis_version 1.0": (lambda r: _edit_meta(r, _set("analysis_version", 1.0)), "'analysis_version' is missing or not a version number"),
    "analysis_version another number": (lambda r: _edit_meta(r, _set("analysis_version", 2)), "changed method"),
    "run_id of another run": (lambda r: _edit_meta(r, _set("run_id", "MAAF_20000101_000000")),
                              "'run_id' does not name this run"),
    "raw_parameters missing": (lambda r: _edit_meta(r, _drop("raw_parameters")), "exactly as entered"),
    "raw_parameters a list": (lambda r: _edit_meta(r, _set("raw_parameters", ["SMA"])),
                              "'raw_parameters' is not a list of named values"),
    "raw_parameters missing a key": (lambda r: _edit_meta(r, _raw(lambda p: p.pop("ma_end"))), "(missing: ma_end)"),
    "raw_parameters unknown key": (lambda r: _edit_meta(r, _raw(lambda p: p.__setitem__("leverage", "9"))),
                                   "(unknown: leverage)"),
    "raw_parameters value not text": (lambda r: _edit_meta(r, _raw(lambda p: p.__setitem__("ma_end", 40))),
                                      "'raw_parameters.ma_end' is not text as entered"),
    "input_datasets missing": (lambda r: _edit_meta(r, _drop("input_datasets")), "'input_datasets' is missing or empty"),
    "input_datasets empty": (lambda r: _edit_meta(r, _set("input_datasets", [])), "'input_datasets' is missing or empty"),
    "dataset record not an object": (lambda r: _edit_meta(r, _set("input_datasets", ["2"])),
                                     "'input_datasets[1]' is not a dataset record"),
    "dataset_id missing": (lambda r: _edit_meta(r, _ds(lambda d: d.pop("dataset_id"))),
                           "'input_datasets[1].dataset_id' is missing or not a dataset number"),
    "dataset_id as text": (lambda r: _edit_meta(r, _ds(lambda d: d.__setitem__("dataset_id", "2"))),
                           "'input_datasets[1].dataset_id' is missing or not a dataset number"),
    "dataset checksum missing": (lambda r: _edit_meta(r, _ds(lambda d: d.pop("sha256"))),
                                 "'input_datasets[1].sha256' is missing or not a SHA-256 checksum"),
    "dataset checksum not SHA-256": (lambda r: _edit_meta(r, _ds(lambda d: d.__setitem__("sha256", "abc"))),
                                     "'input_datasets[1].sha256' is missing or not a SHA-256 checksum"),
    "outputs missing": (lambda r: _edit_meta(r, _drop("outputs")), "'outputs' is missing"),
    "outputs with a path": (lambda r: _edit_meta(r, _set("outputs", ["../MA_Affinity_Candidates_x.csv"])),
                            "'outputs' is missing or names something other than plain file names"),
    "result table not listed": (lambda r: _edit_meta(r, lambda m: m.__setitem__(
        "outputs", [n for n in m["outputs"] if not n.startswith("MA_Affinity_Candidates_")])),
        "has no recorded result table 'MA_Affinity_Candidates_...'"),
    "build not a record": (lambda r: _edit_meta(r, _set("build", "x")), "'build' is not a build record"),
    # the earlier result tables and the folder
    "earlier result table deleted": (lambda r: next(r.run_dir.glob("MA_Affinity_Candidates_*.csv")).unlink(),
                                     "cannot be read"),
    "earlier result table edited": (lambda r: next(r.run_dir.glob("MA_Affinity_Interactions_*.csv")).open("a").write("x"),
                                    "was changed after the run"),
}


def _snapshot(settings, db, res):
    files = {p.name: sha256_file(p) for p in res.run_dir.iterdir() if p.is_file()} if res.run_dir.is_dir() else None
    folders = sorted(p.name for p in (settings.output_root / "Research_Reports").iterdir())
    return files, folders, db.one("SELECT COUNT(*) AS n FROM runs")["n"]


def _refused(settings, db, run_id, needle, before, res):
    again = R.reproduce_run(settings, db, run_id)
    assert again.outcome == "blocked", again.message
    assert again.message.startswith("Not reproduced: ") and needle in again.message, again.message
    assert "Traceback" not in again.message and again.run_id is None and again.run_dir is None
    assert _snapshot(settings, db, res) == before  # nothing new, nothing changed


@pytest.mark.parametrize("case", list(META_CASES))
def test_a_damaged_or_incomplete_record_is_refused_and_nothing_is_run(settings, db, earlier, case):
    damage, needle = META_CASES[case]
    damage(earlier)
    before = _snapshot(settings, db, earlier)
    hash_checked = case not in {"unreadable (a folder)", "two metadata files", "no metadata file"}
    expected = "does not match the SHA-256 checksum recorded" if hash_checked else needle
    _refused(settings, db, earlier.run_id, expected, before, earlier)


@pytest.mark.parametrize("case, sql, args, needle", [
    ("registry checksum of a result table invalid",
     "UPDATE run_outputs SET sha256 = 'x' WHERE run_id = ? AND relative_path LIKE ?", ("%MA_Affinity_Candidates_%",),
     "does not agree with its run manifest"),
    ("run folder recorded outside Q-MAP_OUTPUT", "UPDATE runs SET output_path = ? WHERE run_id = ?",
     ("../../outside",), "is not inside the Q-MAP_OUTPUT folder"),
    ("run not completed", "UPDATE runs SET status = 'failed' WHERE run_id = ?", (), "did not complete"),
])
def test_damaged_registry_rows_are_refused(settings, db, earlier, case, sql, args, needle):
    params = (earlier.run_id, *args) if "run_outputs" in sql or "status" in sql else (*args, earlier.run_id)
    with db.transaction() as conn:
        conn.execute(sql, params)
    before = _snapshot(settings, db, earlier)
    _refused(settings, db, earlier.run_id, needle, before, earlier)


def test_a_dataset_registry_path_leading_outside_q_map_data_is_refused(settings, db, earlier, monkeypatch):
    """The registry's own triggers forbid rewriting a dataset path, so the unsafe path is simulated where Q-MAP turns a
    registry path into a file path: its refusal (UnsafeDataPath) must become a plain reproduction refusal."""
    from qmap.core.config import UnsafeDataPath

    def unsafe(self, relative_path):
        raise UnsafeDataPath(f"not a valid registry path inside Q-MAP_DATA: {relative_path!r}")

    monkeypatch.setattr(type(settings), "data_path", unsafe)
    before = _snapshot(settings, db, earlier)
    _refused(settings, db, earlier.run_id, "not a valid registry path inside Q-MAP_DATA", before, earlier)


def test_a_moved_run_folder_and_an_empty_run_id_are_refused(settings, db, earlier):
    moved = earlier.run_dir.with_name(earlier.run_dir.name + "_moved")
    earlier.run_dir.rename(moved)
    before = _snapshot(settings, db, earlier)
    _refused(settings, db, earlier.run_id, "is missing; it was moved or deleted", before, earlier)
    _refused(settings, db, "   ", "No Run ID was given.", before, earlier)


def test_a_programming_defect_is_not_disguised_as_a_refusal(settings, db, earlier, monkeypatch):
    """Only expected record and file problems become refusals; an unexpected error (a bug) is raised as it is, so it
    can be diagnosed. In the Workbench, ReproduceJob shows one plain line and writes the traceback to the log."""
    def bug(*a, **k):
        raise TypeError("a deliberate defect")

    monkeypatch.setattr(R, "_validated", bug)
    with pytest.raises(TypeError, match="a deliberate defect"):
        R.reproduce_run(settings, db, earlier.run_id)


def test_the_workbench_job_logs_the_traceback_of_a_defect(settings, db, earlier, monkeypatch, caplog):
    from qmap_gui.workbench_services import ReproduceJob

    monkeypatch.setattr(R, "_validated", lambda *a, **k: (_ for _ in ()).throw(TypeError("a deliberate defect")))
    with caplog.at_level("ERROR", logger="qmap"):
        result = ReproduceJob(settings, earlier.run_id).run()
    assert result.outcome == "failed" and result.message == "Unexpected problem (TypeError): a deliberate defect"
    assert any(r.exc_info and "Reproduction of" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("edit", [
    lambda m: m.__setitem__("analysis_name", "tampered but valid JSON"),
    lambda m: m["parameters"].__setitem__("ma_end", m["parameters"]["ma_end"] + 1),
    lambda m: m["input_datasets"][0].__setitem__("dataset_id", m["input_datasets"][0]["dataset_id"] + 1000),
])
def test_valid_json_metadata_tampering_is_refused_before_a_new_run(settings, db, earlier, edit):
    # The JSON remains readable and structurally plausible. Its original registered SHA-256 must still protect it.
    metadata = json.loads(earlier.metadata_path.read_text(encoding="utf-8"))
    edit(metadata)
    earlier.metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    before = _snapshot(settings, db, earlier)
    _refused(settings, db, earlier.run_id, "does not match the SHA-256 checksum recorded", before, earlier)


def test_changed_registry_parameters_are_refused_before_a_new_run(settings, db, earlier):
    row = db.one("SELECT params_json FROM runs WHERE run_id = ?", (earlier.run_id,))
    params = json.loads(row["params_json"])
    params["parameters"]["ma_end"] += 1
    with db.transaction() as conn:
        conn.execute("UPDATE runs SET params_json = ? WHERE run_id = ?",
                     (json.dumps(params, sort_keys=True), earlier.run_id))
    before = _snapshot(settings, db, earlier)
    _refused(settings, db, earlier.run_id, "registry parameters", before, earlier)
