"""MA Affinity in the Analytical Workbench (owner decisions 2-5, 03-Nov-26).

- Same results as QLOPB standalone on the same data (real QLOPB sample file and synthetic data): methodology preserved.
- Only registered datasets are read; the engine never aggregates (daily, weekly, monthly registered datasets only).
- Eligibility: genuine conflicting observations and MIXED block; overlap with other datasets, gaps and edge periods only
  warn; exact duplicates removed at load do not block. Dataset Summary keeps its existing behaviour (DQ rules unchanged).
- Safeguards S-1 (infinite prices) and S-2 (weights) are applied in the integrated route.
- Outputs only in the Run ID folder, with build and method provenance; source files unchanged.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fixtures.builders import HEADER, daily_rows, ohlcv, weekdays, write_delimited
from fixtures.profiles import do_ingest, make_profile
from qlopb.config.settings import MAResearchSettings
from qlopb.core.data_engine import load_file
from qlopb.core.research_engine import run_ma_affinity
from qmap.analytical_engine import ANALYSES, DATASET_SUMMARY, MA_AFFINITY, check_analysis, run_analysis
from qmap.analytical_engine import ma_affinity as M
from qmap.catalog import get_dataset, list_datasets
from qmap.core.build import current_build
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap.data_engine.derive import derive_timeframe

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "qlopb_data"
SMALL = {"ma_start": "5", "ma_end": "40", "min_interactions": "5", "fwd_windows": "3,5,10", "regime_ma": "20"}
SMALL_SETTINGS = MAResearchSettings(ma_start=5, ma_end=40, min_interactions=5, fwd_windows=(3, 5, 10), regime_ma=20)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _scan(settings, db, folder):
    src = next((s for s in D.list_sources(db) if Path(s.location).resolve() == folder.resolve()), None)
    src = src or D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE")
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, src.source_id)


def _long_daily(path: Path, n: int = 900, seed: int = 3) -> Path:
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(n, date(2021, 1, 4)), ohlcv(n, seed=seed, base=500.0))]
    return write_delimited(path, HEADER, rows)


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "Q-MAP_TEST_FILES"
    f.mkdir()
    return f


def test_ma_affinity_is_registered_with_the_agreed_scope():
    assert ANALYSES["ma_affinity"] is MA_AFFINITY
    req = MA_AFFINITY.requirement
    assert req.timeframes == ("1D", "1W", "1M") and req.allow_mixed is False
    assert (MA_AFFINITY.min_datasets, MA_AFFINITY.max_datasets) == (1, 1)
    assert "6cbadc7" in MA_AFFINITY.method_source and "unchanged" in MA_AFFINITY.method_source
    defaults = {p.key: p.default for p in MA_AFFINITY.parameters}
    d = MAResearchSettings()
    assert defaults["ma_start"] == str(d.ma_start) and defaults["fwd_windows"] == ",".join(map(str, d.fwd_windows))
    assert defaults["w_forward"] == str(d.weight_forward_return) and defaults["oos_scope"] == d.oos_scope


def test_real_daily_file_same_results_as_qlopb_standalone(settings, db, folder, roots):
    src = folder / "Nifty500 Healthcare.txt"
    shutil.copy2(FIXTURES / src.name, src)
    before = sha(src)
    _scan(settings, db, folder)
    (ds,) = list_datasets(db)
    res = run_analysis(settings, db, MA_AFFINITY, [ds.dataset_id], SMALL)
    assert res.outcome == "completed", res.message
    assert sha(src) == before
    ours = list(csv.DictReader(open(next(res.run_dir.glob("MA_Affinity_Candidates_*.csv")), encoding="utf-8")))
    standalone = run_ma_affinity(load_file(FIXTURES / src.name).df, SMALL_SETTINGS, label="x")
    expected = pd.DataFrame(standalone.results)
    got = pd.DataFrame(ours)
    assert list(got.columns) == list(expected.columns) and len(got) == len(expected)
    for col in expected.columns:
        for a, b in zip(got[col], expected[col]):
            if isinstance(b, float) and not isinstance(b, bool):
                assert (math.isnan(b) and a in ("", "nan")) or math.isclose(float(a), b, rel_tol=0, abs_tol=1e-12), col
            else:
                assert a == str(b), col
    assert any(r["is_status"] == "OK" for r in ours)


def test_synthetic_daily_default_settings_identical_to_standalone_and_full_outputs(settings, db, folder, roots):
    p = _long_daily(folder / "NSE_LONGD.csv")
    _scan(settings, db, folder)
    (ds,) = list_datasets(db)
    res = run_analysis(settings, db, MA_AFFINITY, [ds.dataset_id], {})
    assert res.outcome == "completed", res.message
    names = {q.name for q in res.outputs}
    assert any(n.startswith("QLOPB_MA_Affinity_") and n.endswith(".xlsx") for n in names)
    assert any(n.startswith("QLOPB_MA_Affinity_Report_") and n.endswith(".pdf") for n in names)
    assert any(n.endswith(".png") for n in names)
    assert all(q.parent == res.run_dir for q in res.outputs)
    meta = json.loads(res.metadata_path.read_text(encoding="utf-8"))
    assert meta["analysis_id"] == "ma_affinity" and meta["build"] == current_build()
    assert meta["method_source"] == M.METHOD_SOURCE
    assert meta["parameters"]["qlopb_settings"]["timeframe"] == "as_loaded"  # the engine never aggregates
    assert meta["input_datasets"][0]["sha256"] == get_dataset(db, ds.dataset_id).sha256
    assert not any(roots["code"].rglob("*")), "nothing may be written into the code folder"
    standalone = run_ma_affinity(load_file(p).df, MAResearchSettings(), label="x")
    got = pd.read_csv(next(res.run_dir.glob("MA_Affinity_Candidates_*.csv")))
    want = pd.DataFrame(standalone.results)
    assert list(got["ma_label"]) == list(want["ma_label"])
    np.testing.assert_allclose(got["is_affinity_score"].astype(float), want["is_affinity_score"].astype(float),
                               rtol=0, atol=1e-12, equal_nan=True)
    assert len(standalone.frozen_top) > 0
    np.testing.assert_array_equal(got["rank"].fillna(-1).to_numpy(), pd.Series(want["rank"]).fillna(-1).astype(float).to_numpy())


def test_weekly_and_monthly_registered_datasets_run_and_are_not_aggregated_again(settings, db, folder, run):
    _long_daily(folder / "NSE_LONGW.csv", n=1500)
    _scan(settings, db, folder)
    (daily,) = list_datasets(db)
    for tf in ("1W", "1M"):
        derive_timeframe(run, daily.dataset_id, tf)
    weekly = next(d for d in list_datasets(db) if d.timeframe == "1W")
    res = run_analysis(settings, db, MA_AFFINITY, [weekly.dataset_id], {**SMALL, "ma_end": "30"})
    assert res.outcome == "completed", res.message
    meta = json.loads(res.metadata_path.read_text(encoding="utf-8"))
    assert meta["input_datasets"][0]["timeframe"] == "1W"
    log = (res.run_dir / "run_log.txt").read_text(encoding="utf-8")
    assert "Phase 1/3" in log and "Aggregated" not in log  # QLOPB's own aggregation is never used


def test_intraday_and_quarterly_datasets_are_refused_with_the_reason(settings, db, folder, run):
    shutil.copy2(FIXTURES / "NSE_SBIN, 60.csv", folder / "NSE_SBIN, 60.csv")
    _long_daily(folder / "NSE_LONGQ.csv", n=1200)
    _scan(settings, db, folder)
    daily = next(d for d in list_datasets(db) if d.timeframe == "1D")
    derive_timeframe(run, daily.dataset_id, "1Q")
    for d in list_datasets(db):
        if d.timeframe in ("1h", "1Q"):
            chk = check_analysis(settings, db, MA_AFFINITY, [d.dataset_id], {})
            assert not chk.ready
            assert any("not supported here" in f.detail for r in chk.reports for f in r.failures)
            res = run_analysis(settings, db, MA_AFFINITY, [d.dataset_id], {})
            assert res.outcome == "blocked" and res.run_id is None


# ---- eligibility (decision 4) ----------------------------------------------------------------------------------
def _conflicted(src, run, n=60, at=(30,)):
    rows = [list(r) for r in daily_rows(n)]
    for i in sorted(at, reverse=True):
        rows.insert(i + 1, [rows[i][0], rows[i][1], rows[i][2] + 1, rows[i][3], rows[i][4] + 0.5, rows[i][5]])
    res = do_ingest(run, write_delimited(src / "conflicts.csv", HEADER, rows))
    assert res.outcome == "accepted", res.message
    return res.dataset_ids[0], rows


def test_genuine_conflicting_observations_block_with_dates_named(settings, db, run, src):
    ds, rows = _conflicted(src, run)
    chk = check_analysis(settings, db, MA_AFFINITY, [ds], SMALL)
    assert not chk.ready
    (fail,) = [f for r in chk.reports for f in r.failures]
    assert fail.name == "ma_affinity_conflicts" and "1 timestamp(s)" in fail.detail
    assert date.fromisoformat(rows[30][0]).strftime("%d-%b-%y") in fail.detail
    res = run_analysis(settings, db, MA_AFFINITY, [ds], SMALL)
    assert res.outcome == "blocked" and "exactly one bar per time" in res.message
    # existing DQ behaviour unchanged: Dataset Summary still runs on the same dataset, with its warning
    assert run_analysis(settings, db, DATASET_SUMMARY, [ds], {}).outcome == "completed"


def test_conflicts_outside_the_chosen_period_do_not_block(settings, db, run, src):
    ds, rows = _conflicted(src, run, n=80, at=(70,))
    period = {**SMALL, "date_to": date.fromisoformat(rows[60][0]).strftime("%d-%m-%y")}
    chk = check_analysis(settings, db, MA_AFFINITY, [ds], period)
    item = next(i for r in chk.reports for i in r.items if i.name == "ma_affinity_conflicts")
    assert item.status == "pass"


def test_weekly_bars_built_from_conflicting_days_block(settings, db, run, src):
    ds, _ = _conflicted(src, run, n=200, at=(100,))
    derive_timeframe(run, ds, "1W")
    weekly = next(d for d in list_datasets(db) if d.timeframe == "1W")
    chk = check_analysis(settings, db, MA_AFFINITY, [weekly.dataset_id], {**SMALL, "ma_end": "10"})
    fail = next(f for r in chk.reports for f in r.failures if f.name == "ma_affinity_conflicts")
    assert "built from daily data with conflicting observations" in fail.detail


def test_exact_duplicates_removed_at_load_do_not_block(settings, db, run, src):
    rows = [list(r) for r in daily_rows(60)]
    rows.insert(20, list(rows[19]))
    res = do_ingest(run, write_delimited(src / "dups.csv", HEADER, rows))
    chk = check_analysis(settings, db, MA_AFFINITY, [res.dataset_ids[0]], SMALL)
    assert chk.ready, [f.detail for r in chk.reports for f in r.failures]
    item = next(i for r in chk.reports for i in r.items if i.name == "ma_affinity_conflicts")
    assert item.status == "pass" and "exact duplicates" in item.detail


def test_overlap_with_another_dataset_only_warns(settings, db, folder):
    rows = ohlcv(80)
    days = weekdays(80)
    write_delimited(folder / "NSE_ABC.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, rows)])
    _scan(settings, db, folder)
    revised = [list(r) for r in rows]
    revised[3][3] = round(revised[3][3] + 0.5, 2)
    revised[3][1] = max(revised[3][1], revised[3][3])
    write_delimited(folder / "NSE_ABC provider2.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, revised)])
    _scan(settings, db, folder)
    warned = 0
    for d in list_datasets(db):
        chk = check_analysis(settings, db, MA_AFFINITY, [d.dataset_id], SMALL)
        assert chk.ready, [f.detail for r in chk.reports for f in r.failures]
        items = {i.name: i for r in chk.reports for i in r.items}
        assert items["ma_affinity_conflicts"].status == "pass"
        warned += items.get("conflicts") is not None and items["conflicts"].status == "warn"
    assert warned >= 1  # the overlap is shown as a warning, never as a block


def test_mixed_timeframe_blocks(settings, db, run, src):
    from test_dq7_timeframe_inference import session_times  # the existing DQ-7 helper

    times = session_times(1, days=8) + session_times(15, days=8, start=date(2026, 3, 2))
    rows = [[t.isoformat()] + r for t, r in zip(times, ohlcv(len(times)))]
    prof = make_profile(instrument={"timeframe": "ingest"}, datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, write_delimited(src / "NSE_MIX.csv", HEADER, rows), prof)
    chk = check_analysis(settings, db, MA_AFFINITY, [res.dataset_ids[0]], SMALL)
    assert not chk.ready and any("MIXED" in f.detail for r in chk.reports for f in r.failures)


def test_too_short_for_the_settings_is_refused_before_a_run(settings, db, run, src):
    res = do_ingest(run, write_delimited(src / "short.csv", HEADER, daily_rows(15)))
    chk = check_analysis(settings, db, MA_AFFINITY, [res.dataset_ids[0]], {})
    assert not chk.ready
    assert any(f.name == "ma_affinity_history" and "too few" in f.detail for r in chk.reports for f in r.failures)
    assert run_analysis(settings, db, MA_AFFINITY, [res.dataset_ids[0]], {}).run_id is None


# ---- safeguards S-1 and S-2 in the integrated route --------------------------------------------------------------
@pytest.mark.parametrize("weights,needle", [
    ({"w_forward": "nan"}, "finite"), ({"w_forward": "inf"}, "finite"), ({"w_success": "-1"}, "negative"),
    ({"w_interaction": "0", "w_success": "0", "w_forward": "0", "w_stability": "0"}, "above 0"),
    ({"w_interaction": "1e308", "w_success": "1e308"}, "finite"),
])
def test_s2_invalid_weights_are_refused(settings, db, run, src, weights, needle):
    res = do_ingest(run, write_delimited(src / "d.csv", HEADER, daily_rows(60)))
    chk = check_analysis(settings, db, MA_AFFINITY, [res.dataset_ids[0]], {**SMALL, **weights})
    assert not chk.ready and any(needle in p for p in chk.input_problems), chk.input_problems


def test_other_parameter_problems_are_explained(settings, db, run, src):
    res = do_ingest(run, write_delimited(src / "d.csv", HEADER, daily_rows(60)))
    chk = check_analysis(settings, db, MA_AFFINITY, [res.dataset_ids[0]],
                         {**SMALL, "ma_types": "SMA,SMX", "ma_start": "50", "ma_end": "10", "oos_scope": "some"})
    text = " | ".join(chk.input_problems)
    assert "SMX" in text and not chk.ready
    ok = check_analysis(settings, db, MA_AFFINITY, [res.dataset_ids[0]], {**SMALL, "ma_types": "sma, ema"})
    assert ok.ready and ok.params["qlopb_settings"]["ma_types"] == ("SMA", "EMA")


def test_s1_infinite_prices_are_refused_even_if_they_reached_a_dataset(settings, db, run, src, monkeypatch):
    res = do_ingest(run, write_delimited(src / "d.csv", HEADER, daily_rows(60)))
    real = M._frame

    def with_inf(*a, **k):
        frame, table = real(*a, **k)
        frame.iloc[10, frame.columns.get_loc("high")] = np.inf
        return frame, table

    monkeypatch.setattr(M, "_frame", with_inf)
    chk = check_analysis(settings, db, MA_AFFINITY, [res.dataset_ids[0]], SMALL)
    assert not chk.ready
    assert any(f.name == "ma_affinity_prices" and "infinite" in f.detail for r in chk.reports for f in r.failures)


# ---- the acceptance file used in the v0.1 Windows guide (check V8) -------------------------------------------------
def test_acceptance_file_conflictdaily_is_imported_and_refused_with_its_date(settings, db, folder):
    name = "NSE_CONFLICTDAILY.csv"
    src = Path(__file__).resolve().parents[2] / "docs" / "acceptance_testing" / "v01_files_03_Nov_26" / name
    shutil.copy2(src, folder / name)
    # exactly as in the guide: no market time zone, no default exchange (the exchange comes from the file name)
    D.add_folder_source(settings, db, folder)
    res = _scan(settings, db, folder)
    assert [f[3] for f in res.files] == ["imported"], res.files
    (ds,) = list_datasets(db)
    assert (ds.instrument, ds.timeframe, ds.row_count) == ("NSE:CONFLICTDAILY", "1D", 301)
    chk = check_analysis(settings, db, MA_AFFINITY, [ds.dataset_id], {})
    (fail,) = [f for r in chk.reports for f in r.failures]
    assert "1 timestamp(s)" in fail.detail and "29-Jul-24" in fail.detail
    ok = check_analysis(settings, db, MA_AFFINITY, [ds.dataset_id], {"date_to": "26-07-24", "ma_end": "60"})
    assert ok.ready, [f.detail for r in ok.reports for f in r.failures]
    assert run_analysis(settings, db, DATASET_SUMMARY, [ds.dataset_id], {}).outcome == "completed"


# ---- audit 03-Nov-26: repeatability and what the reports say -------------------------------------------------------
def test_the_same_run_twice_gives_identical_results(settings, db, folder):
    _long_daily(folder / "NSE_REPEAT.csv")
    _scan(settings, db, folder)
    (ds,) = list_datasets(db)
    a = run_analysis(settings, db, MA_AFFINITY, [ds.dataset_id], {"ma_end": "60"})
    b = run_analysis(settings, db, MA_AFFINITY, [ds.dataset_id], {"ma_end": "60"})
    assert a.run_id != b.run_id and a.run_dir != b.run_dir  # a repeated run never overwrites the earlier one
    for pattern in ("MA_Affinity_Candidates_*.csv", "MA_Affinity_Interactions_*.csv"):
        assert next(a.run_dir.glob(pattern)).read_bytes() == next(b.run_dir.glob(pattern)).read_bytes()


def test_reports_carry_run_build_dataset_and_the_q_map_data_notes(settings, db, folder):
    import openpyxl

    rows = ohlcv(400)
    days = weekdays(400, date(2023, 1, 2))
    write_delimited(folder / "NSE_REP.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, rows)])
    _scan(settings, db, folder)
    revised = [list(r) for r in rows]
    revised[3][3] = round(revised[3][3] + 0.5, 2)
    revised[3][1] = max(revised[3][1], revised[3][3])
    write_delimited(folder / "NSE_REP provider2.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, revised)])
    _scan(settings, db, folder)
    warned = next(d for d in list_datasets(db)
                  if any(w.startswith("conflicts_with_existing_dataset") for w in get_dataset(db, d.dataset_id).warnings))
    res = run_analysis(settings, db, MA_AFFINITY, [warned.dataset_id], {"ma_end": "60"})
    assert res.outcome == "completed", res.message
    wb = openpyxl.load_workbook(next(res.run_dir.glob("QLOPB_MA_Affinity_*.xlsx")))
    summary = [tuple(r[:2]) for r in wb["Summary"].iter_rows(values_only=True)]
    text = " | ".join(str(v) for r in summary for v in r if v is not None)
    assert f"Run {res.run_id}" in text and f"dataset {warned.dataset_id}" in text
    assert "Q-MAP data:" in text and "conflicting observations" in text  # the overlap NOTE reaches the report
    assert "Daily (Q-MAP registered dataset; not re-aggregated)" in text  # bar size, not "as loaded"
    quality = " | ".join(str(v) for r in wb["Data_Quality"].iter_rows(values_only=True) for v in r if v is not None)
    build = current_build()
    assert build["source_fingerprint"] in quality and get_dataset(db, warned.dataset_id).sha256 in quality
    assert res.run_id in quality and "Lineage:" in quality and "NSE_REP" in quality
    # the calculation is unchanged by the notes: same candidates as a run on the same bars without them
    from qlopb.core.research_engine import run_ma_affinity as engine
    frame, _ = M._frame(settings, db, warned.dataset_id, {})
    plain = engine(frame, MAResearchSettings(ma_end=60), label="x")
    got = pd.read_csv(next(res.run_dir.glob("MA_Affinity_Candidates_*.csv")))
    np.testing.assert_allclose(got["is_affinity_score"].astype(float),
                               pd.DataFrame(plain.results)["is_affinity_score"].astype(float), rtol=0, atol=1e-12,
                               equal_nan=True)


def _pdf_text(path) -> str:
    """All text of a generated PDF, whitespace removed (long hashes may be wrapped across lines)."""
    from pypdf import PdfReader

    return "".join("".join((page.extract_text() or "").split()) for page in PdfReader(str(path)).pages)


def _nows(text: str) -> str:
    return "".join(str(text).split())


def test_pdf_and_excel_and_metadata_carry_the_full_provenance(settings, db, folder):
    """Closure review 04-Nov-26: verify the ACTUAL generated PDF, not only the workbook."""
    import openpyxl

    rows = ohlcv(400)
    days = weekdays(400, date(2023, 1, 2))
    write_delimited(folder / "NSE_M&M.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, rows)])  # '&' in a name
    _scan(settings, db, folder)
    revised = [list(r) for r in rows]
    revised[3][3] = round(revised[3][3] + 0.5, 2)
    revised[3][1] = max(revised[3][1], revised[3][3])
    write_delimited(folder / "NSE_M&M provider2.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, revised)])
    _scan(settings, db, folder)
    ds = next(d for d in list_datasets(db) if get_dataset(db, d.dataset_id).warnings)
    info = get_dataset(db, ds.dataset_id)
    res = run_analysis(settings, db, MA_AFFINITY, [ds.dataset_id], {"ma_end": "60"})
    assert res.outcome == "completed", res.message
    build = current_build()
    note = next(item.detail for rep in res.readiness.reports for item in rep.warnings if item.name == "conflicts")
    required = {
        "run_id": res.run_id, "version": build["version"], "fingerprint": build["source_fingerprint"],
        "dataset": f"dataset {ds.dataset_id}", "instrument": info.instrument, "checksum": info.sha256,
        "validation_warning": info.warnings[0][:60], "readiness_note": note[:60],
    }
    pdf = _pdf_text(next(res.run_dir.glob("QLOPB_MA_Affinity_Report_*.pdf")))
    wb = openpyxl.load_workbook(next(res.run_dir.glob("QLOPB_MA_Affinity_*.xlsx")))
    quality = _nows(" ".join(str(v) for r in wb["Data_Quality"].iter_rows(values_only=True) for v in r if v is not None))
    meta = _nows(res.metadata_path.read_text(encoding="utf-8"))
    for key, value in required.items():
        assert _nows(value) in pdf, f"PDF lacks {key}"
        assert _nows(value) in quality, f"Excel Data_Quality lacks {key}"
    for key in ("run_id", "version", "fingerprint", "instrument", "checksum", "validation_warning", "readiness_note"):
        assert _nows(required[key]) in meta, f"Run_Metadata lacks {key}"
    assert "M&M" in pdf and "&amp;" not in pdf  # the name is shown as written, not as markup
    assert "Q-MAPbuild:" in pdf and "Q-MAPdata:" in pdf and "Q-MAPdatasetvalidationwarning:" in pdf
