"""Beta reproducibility and provenance (T7, T8, 09-Nov-26).

A completed run can be repeated from its Run ID: Q-MAP re-runs it as a NEW run with the recorded datasets and the
parameters exactly as entered, checks the data first, and compares the result tables with the earlier run's
recorded checksums. The earlier run is never changed. Run_Metadata records the bars used and the split."""

from __future__ import annotations

import csv
import json
from datetime import date

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.analytical_engine import DATASET_SUMMARY, MA_AFFINITY, run_analysis
from qmap.analytical_engine import reproduce as R
from qmap.catalog import get_dataset, list_datasets
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap.storage.files import sha256_file

PARAMS = {"ma_types": "SMA,EMA", "ma_end": "45", "fwd_windows": "5,10", "date_from": "15-Mar-21",
          "date_to": "30/09/23"}


@pytest.fixture
def dataset(settings, db, tmp_path):
    folder = tmp_path / "files"
    folder.mkdir()
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(800, date(2021, 1, 4)), ohlcv(800, seed=21, base=250.0))]
    write_delimited(folder / "NSE_REPRO.csv", HEADER, rows)
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE")
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        D.scan_source(run, src.source_id)
    (ds,) = list_datasets(db)
    return ds.dataset_id


def _meta(result):
    return json.loads(result.metadata_path.read_text(encoding="utf-8"))


def _folder_hashes(folder):
    return {p.name: sha256_file(p) for p in folder.iterdir() if p.is_file()}


def test_provenance_records_parameters_as_entered_the_bars_used_and_the_split(settings, db, dataset):
    res = run_analysis(settings, db, MA_AFFINITY, [dataset], PARAMS)
    assert res.ok, res.message
    meta = _meta(res)
    assert meta["run_id"] == res.run_id and meta["analysis_id"] == "ma_affinity" and meta["analysis_version"] == 1
    assert meta["raw_parameters"]["ma_end"] == "45" and meta["raw_parameters"]["date_to"] == "30/09/23"
    assert meta["raw_parameters"]["proximity_pct"] is None  # left empty: the default applies, recorded as such
    assert meta["parameters"]["qlopb_settings"]["proximity_pct"] == 3.0
    used = meta["analysis_details"]["bars_used"]
    assert used["first"] >= "2021-03-15" and used["last"] <= "2023-09-30"
    assert used["count"] == meta["input_datasets"][0]["rows_in_window"]
    split = meta["analysis_details"]["split"]
    assert split["is_bars"] + split["oos_bars"] == used["count"]
    assert meta["analysis_details"]["frozen_top"] and meta["method_source"].startswith("MA Affinity")
    d = meta["input_datasets"][0]
    assert d["sha256"] == get_dataset(db, dataset).sha256 and d["lineage"] and meta["build"]["source_fingerprint"]


def test_a_run_is_reproduced_from_its_run_id_with_identical_result_tables(settings, db, dataset):
    first = run_analysis(settings, db, MA_AFFINITY, [dataset], PARAMS)
    before = _folder_hashes(first.run_dir)
    again = R.reproduce_run(settings, db, first.run_id)
    assert again.ok, again.message
    assert again.run_id != first.run_id and again.run_dir != first.run_dir
    assert again.reproduction["identical"] is True and again.reproduction["of_run_id"] == first.run_id
    assert _meta(again)["reproduction"]["identical"] is True
    report = next(again.run_dir.glob("Reproducibility_Report_*.csv"))
    rows = list(csv.reader(report.open(encoding="utf-8")))
    assert rows[-1][-1] == f"REPRODUCED: every result table is identical to run {first.run_id}"
    assert sum(r[-1] == "IDENTICAL" for r in rows) == len(MA_AFFINITY.result_tables)
    assert _folder_hashes(first.run_dir) == before  # the earlier run is never touched


def test_dataset_summary_is_reproducible_too(settings, db, dataset):
    first = run_analysis(settings, db, DATASET_SUMMARY, [dataset], {})
    again = R.reproduce_run(settings, db, first.run_id)
    assert again.ok and again.reproduction["identical"], again.message


def test_reproduction_can_use_preserved_superseded_dataset_but_new_runs_cannot(settings, db, dataset):
    first = run_analysis(settings, db, MA_AFFINITY, [dataset], PARAMS)
    assert first.ok, first.message
    original_hashes = _folder_hashes(first.run_dir)

    # Simulate a later processing run superseding this dataset while preserving its file and registry checksum.
    with db.transaction() as conn:
        conn.execute("UPDATE datasets SET status = 'superseded' WHERE dataset_id = ?", (dataset,))

    reproduced = R.reproduce_run(settings, db, first.run_id)
    assert reproduced.ok, reproduced.message
    assert reproduced.reproduction["identical"] is True
    assert any("SUPERSEDED" in warning for warning in reproduced.readiness.warnings)
    assert _folder_hashes(first.run_dir) == original_hashes

    # The exception is limited to reproduction; an ordinary new analysis must still be blocked.
    fresh = run_analysis(settings, db, MA_AFFINITY, [dataset], PARAMS)
    assert fresh.outcome == "blocked"
    assert "SUPERSEDED" in fresh.message


def test_missing_historical_dataset_file_is_refused_before_anything_runs(settings, db, dataset):
    first = run_analysis(settings, db, MA_AFFINITY, [dataset], PARAMS)
    assert first.ok, first.message
    path = settings.data_path(get_dataset(db, dataset).relative_path)
    path.unlink()
    runs_before = db.one("SELECT COUNT(*) AS n FROM runs")["n"]

    again = R.reproduce_run(settings, db, first.run_id)
    assert again.outcome == "blocked"
    assert f"Dataset {dataset}" in again.message and "missing" in again.message
    assert db.one("SELECT COUNT(*) AS n FROM runs")["n"] == runs_before


def test_changed_data_are_refused_before_anything_runs(settings, db, dataset):
    first = run_analysis(settings, db, MA_AFFINITY, [dataset], PARAMS)
    path = settings.data_path(get_dataset(db, dataset).relative_path)
    path.write_bytes(path.read_bytes() + b"\0")  # the stored data no longer match the recorded checksum
    runs_before = db.one("SELECT COUNT(*) AS n FROM runs")["n"]
    again = R.reproduce_run(settings, db, first.run_id)
    assert again.outcome == "blocked" and f"Dataset {dataset}" in again.message and "checksum" in again.message
    assert db.one("SELECT COUNT(*) AS n FROM runs")["n"] == runs_before  # no run, no folder


def test_a_different_result_is_reported_as_not_reproduced(settings, db, dataset, monkeypatch):
    """The reproduction's calculation is made to give one different affinity score (as a changed engine would): the
    comparison must say NOT REPRODUCED and name the differing table; the earlier run stays untouched."""
    import qlopb.core.research_engine as RE

    first = run_analysis(settings, db, MA_AFFINITY, [dataset], PARAMS)
    before = _folder_hashes(first.run_dir)
    real = RE.run_ma_affinity

    def changed(*a, **k):
        res = real(*a, **k)
        res.results[0]["is_affinity_score"] = round(res.results[0]["is_affinity_score"] + 1.0, 2)
        return res

    monkeypatch.setattr(RE, "run_ma_affinity", changed)
    again = R.reproduce_run(settings, db, first.run_id)
    assert again.ok and again.reproduction["identical"] is False
    assert again.reproduction["verdict"].startswith("NOT REPRODUCED")
    rows = list(csv.reader(next(again.run_dir.glob("Reproducibility_Report_*.csv")).open(encoding="utf-8")))
    verdicts = {r[0]: r[-1] for r in rows}
    assert verdicts["Result table MA_Affinity_Candidates_..."] == "DIFFERENT"
    assert verdicts["Result table MA_Affinity_Interactions_..."] == "IDENTICAL"
    assert _folder_hashes(first.run_dir) == before


def test_a_different_code_build_is_stated(settings, db, dataset, monkeypatch):
    first = run_analysis(settings, db, MA_AFFINITY, [dataset], PARAMS)
    real = R.current_build()
    monkeypatch.setattr(R, "current_build", lambda: dict(real, source_fingerprint="0" * 64))
    again = R.reproduce_run(settings, db, first.run_id)
    assert again.reproduction["same_build"] is False and again.reproduction["identical"] is True
    rows = list(csv.reader(next(again.run_dir.glob("Reproducibility_Report_*.csv")).open(encoding="utf-8")))
    assert rows[1][0] == "Code build" and rows[1][-1] == "DIFFERENT"


@pytest.mark.parametrize("case", ["unknown", "old", "version"])
def test_runs_that_cannot_be_reproduced_say_why(settings, db, dataset, case, monkeypatch):
    if case == "unknown":
        again = R.reproduce_run(settings, db, "MAAF_19990101_000000")
        assert again.outcome == "blocked" and "no run" in again.message
        return
    first = run_analysis(settings, db, MA_AFFINITY, [dataset], PARAMS)
    if case == "old":
        m = first.metadata_path
        data = json.loads(m.read_text(encoding="utf-8"))
        del data["raw_parameters"]
        m.write_text(json.dumps(data), encoding="utf-8")
        assert "exactly as entered" in R.reproduce_run(settings, db, first.run_id).message
    else:
        monkeypatch.setattr(MA_AFFINITY, "version", 2)
        assert "changed method" in R.reproduce_run(settings, db, first.run_id).message


def test_the_findings_file_states_the_question_and_the_frozen_top_n_from_the_engine_numbers(settings, db, dataset):
    res = run_analysis(settings, db, MA_AFFINITY, [dataset], PARAMS)
    text = next(res.run_dir.glob("MA_Affinity_Findings_*.txt")).read_text(encoding="utf-8")
    meta = _meta(res)
    assert "Research question" in text and meta["analysis_details"]["research_question"] in text
    rows = list(csv.DictReader(next(res.run_dir.glob("MA_Affinity_Candidates_*.csv")).open(encoding="utf-8")))
    top = sorted((r for r in rows if r["rank"]), key=lambda r: int(r["rank"]))[:5]
    assert [f"{r['ma_type']}-{r['ma_period']}" for r in top] == meta["analysis_details"]["frozen_top"]
    for r in top:  # each line quotes the engine's own figures for that candidate
        assert f"{r['rank']}. {r['ma_type']}-{r['ma_period']}: affinity {float(r['is_affinity_score']):.2f}" in text
        assert f"in-sample {float(r['is_overall_sr']):.2f}% success over {r['is_n_outcomes']} outcome(s)" in text
    assert "not corrected" in text and "not a trading signal" in text
