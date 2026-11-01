"""Shared data catalogue, readiness checks and the analytical run pipeline (Run ID, inputs, outputs, metadata)."""

from __future__ import annotations

import csv
import json
from datetime import date

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest, make_profile
from qmap.analytical_engine import ANALYSES, DATASET_SUMMARY, check_analysis, run_analysis
from qmap.catalog import DataRequirement, check_readiness, list_datasets, overview, provenance, read_dataset
from qmap.data_engine.derive import derive_timeframe
from qmap.storage.storage_class import delete_temporary_file, move_dataset


@pytest.fixture
def daily(run, src):
    return do_ingest(run, write_delimited(src / "d.csv", HEADER, daily_rows(30))).dataset_ids[0]


def test_catalogue_lists_datasets_with_distinct_validation_and_storage(db, run, daily):
    weekly = derive_timeframe(run, daily, "1W").dataset_id
    infos = {d.dataset_id: d for d in list_datasets(db)}
    assert set(infos) == {daily, weekly}  # raw originals are not analysis datasets
    d = infos[daily]
    assert (d.instrument, d.timeframe_label, d.storage_label, d.state_label) == ("NSE:TEST", "Daily", "Permanent", "Active")
    assert d.validation_status in ("passed", "passed_with_warnings") and d.source_files == ["d.csv"]
    assert infos[weekly].validation_status == "passed_with_warnings"  # the edge period warning
    ov = overview(db)
    assert ov.datasets_active == 2 and ov.by_timeframe == {"1D": 1, "1W": 1} and ov.raw_files == 1


def test_provenance_reaches_the_original_file(db, run, daily):
    weekly = derive_timeframe(run, daily, "1W").dataset_id
    lines = provenance(db, weekly)
    assert lines[0].startswith("Derived Weekly") and "Standardised Daily" in lines[1] and "d.csv" in lines[2]


def test_readiness_passes_for_suitable_data(settings, db, daily):
    rep = check_readiness(settings, db, daily, DataRequirement(timeframes=("1D",), min_rows=10))
    assert rep.ready, [i.detail for i in rep.failures]
    assert rep.rows_in_window == 30


@pytest.mark.parametrize("req, expected", [
    (DataRequirement(timeframes=("5m",)), "timeframe"),
    (DataRequirement(timeframes=("1D",), min_rows=100), "history"),
    (DataRequirement(timeframes=("1D",), date_from=date(2030, 1, 1)), "history"),
])
def test_readiness_explains_what_is_missing(settings, db, daily, req, expected):
    rep = check_readiness(settings, db, daily, req)
    assert not rep.ready and expected in {f.name for f in rep.failures}


def test_registration_alone_is_not_readiness(settings, db, run, daily):
    raw = db.one("SELECT parent_dataset_id FROM datasets WHERE dataset_id = ?", (daily,))[0]
    assert not check_readiness(settings, db, raw, DataRequirement(timeframes=("1D",))).ready
    path = settings.data_path(db.one("SELECT relative_path FROM datasets WHERE dataset_id = ?", (daily,))[0])
    path.write_bytes(path.read_bytes()[:-3] + b"xyz")  # damaged
    rep = check_readiness(settings, db, daily, DataRequirement(timeframes=("1D",)))
    assert not rep.ready and rep.failures[0].name in ("file_readable", "checksum")


def test_volume_requirement(settings, db, run, src):
    profile = make_profile(volume={"rule": "none", "requirement_set": "price_only"})
    res = do_ingest(run, write_delimited(src / "nv.csv", HEADER[:5], [r[:5] for r in daily_rows(10)]), profile)
    assert res.ok, res.message
    rep = check_readiness(settings, db, res.dataset_ids[0], DataRequirement(timeframes=("1D",), require_volume=True))
    assert "volume" in {f.name for f in rep.failures}


def test_temporary_and_deleted_datasets(settings, db, run, daily):
    move_dataset(run, daily, "temporary")
    rep = check_readiness(settings, db, daily, DataRequirement(timeframes=("1D",)))
    assert rep.ready and "storage" in {w.name for w in rep.warnings}
    delete_temporary_file(run, daily)
    rep = check_readiness(settings, db, daily, DataRequirement(timeframes=("1D",)))
    assert not rep.ready and rep.failures[0].name == "file_present"


def test_read_dataset_returns_only_quantitative_columns_for_a_window(settings, db, daily):
    t = read_dataset(settings, db, daily, date_from=date(2026, 1, 12), date_to=date(2026, 1, 16))
    assert t.num_rows == 5 and not any(c.startswith("x_") for c in t.column_names)


# ---- analytical runs --------------------------------------------------------------------------------------------
def test_only_genuinely_runnable_analyses_are_registered():
    assert list(ANALYSES) == ["dataset_summary"]
    assert "not a research methodology" in DATASET_SUMMARY.description


def test_analysis_run_writes_outputs_and_reproducibility_metadata(settings, db, run, daily):
    weekly = derive_timeframe(run, daily, "1W").dataset_id
    lines = []
    res = run_analysis(settings, db, DATASET_SUMMARY, [daily, weekly], {"date_from": "05-Jan-26"}, log=lines.append)
    assert res.ok, res.message
    assert res.run_id.startswith("DSUM_") and res.run_dir.parent == settings.output_root / "Research_Reports"
    assert res.run_dir.resolve().is_relative_to(settings.output_root)  # never inside code or data folders
    meta = json.loads(res.metadata_path.read_text())
    assert meta["run_id"] == res.run_id and meta["analysis_version"] == 1
    assert meta["parameters"] == {"date_from": "2026-01-05", "date_to": None}
    ids = [d["dataset_id"] for d in meta["input_datasets"]]
    assert ids == [daily, weekly]
    rec = meta["input_datasets"][0]
    assert rec["sha256"] and rec["processing_version"] and rec["config_fingerprint"] and rec["lineage"]
    assert {r["dataset_id"] for r in db.query("SELECT dataset_id FROM run_inputs WHERE run_id = ?", (res.run_id,))} == {
        daily, weekly}
    assert db.one("SELECT status FROM runs WHERE run_id = ?", (res.run_id,))["status"] == "completed"
    manifest = json.loads((res.run_dir / "run_manifest.json").read_text())
    assert {o["relative_path"] for o in manifest["outputs"]} >= {res.outputs[0].name, res.metadata_path.name}
    with open(res.outputs[0], newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["Bars"] == "30" and rows[0]["First bar"] == "05-Jan-26"  # dd-mmm-yy in the report
    assert rows[1]["Timeframe"] == "Weekly"
    assert any("started" in line for line in lines)


def test_summary_statistics_match_an_independent_calculation(settings, db, run, src):
    rows = daily_rows(12, seed=7)
    daily = do_ingest(run, write_delimited(src / "d.csv", HEADER, rows)).dataset_ids[0]
    res = run_analysis(settings, db, DATASET_SUMMARY, [daily], {})
    with open(res.outputs[0], newline="", encoding="utf-8") as fh:
        got = next(csv.DictReader(fh))
    closes = [r[4] for r in rows]
    rets = [(b / a - 1) * 100 for a, b in zip(closes, closes[1:])]
    mean = sum(rets) / len(rets)
    sd = (sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5
    assert float(got["Mean return %"]) == pytest.approx(mean, abs=1e-4)
    assert float(got["Std dev return %"]) == pytest.approx(sd, abs=1e-4)
    assert float(got["Largest return %"]) == pytest.approx(max(rets), abs=1e-4)
    assert int(got["Returns counted"]) == 11 and float(got["Last close"]) == closes[-1]


def test_two_runs_never_overwrite_each_other(settings, db, daily):
    a = run_analysis(settings, db, DATASET_SUMMARY, [daily], {})
    b = run_analysis(settings, db, DATASET_SUMMARY, [daily], {})
    assert a.run_id != b.run_id and a.run_dir != b.run_dir and a.outputs[0].exists() and b.outputs[0].exists()


def test_analysis_is_blocked_with_a_reason_and_creates_no_run(settings, db, daily):
    runs_before = db.one("SELECT COUNT(*) FROM runs")[0]
    res = run_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": "01-Jan-30"})
    assert res.outcome == "blocked" and "at least 2" in res.message and res.run_id is None
    bad = run_analysis(settings, db, DATASET_SUMMARY, [], {"date_from": "not a date"})
    assert bad.outcome == "blocked" and "not a date" in bad.message and "at least 1" in bad.message
    assert db.one("SELECT COUNT(*) FROM runs")[0] == runs_before


def test_a_failing_analysis_is_recorded_as_failed(settings, db, daily, monkeypatch):
    from dataclasses import replace

    def boom(_ctx):
        raise RuntimeError("calculation error")

    res = run_analysis(settings, db, replace(DATASET_SUMMARY, execute=boom), [daily], {})
    assert res.outcome == "failed" and "calculation error" in res.message
    assert db.one("SELECT status FROM runs WHERE run_id = ?", (res.run_id,))["status"] == "failed"


def test_check_analysis_cleans_parameters(settings, db, daily):
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": "05 Jan 26", "date_to": "2026-02-06"})
    assert r.ready and r.params == {"date_from": date(2026, 1, 5), "date_to": date(2026, 2, 6)}
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": "10-Feb-26", "date_to": "01-Feb-26"})
    assert not r.ready and "after the end date" in r.problems[0]
