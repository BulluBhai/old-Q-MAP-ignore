"""End to end (assignment scenarios 33-38; Blueprint v1.3 §8.5.10): a file in a user folder -> folder scan ->
automatic interpretation -> registered dataset -> Workbench readiness -> Dataset Summary run -> output checked
against figures computed INDEPENDENTLY from the original file text.

The independent calculation below uses only the csv module, float() and the statistics module on the source text.
It does not call any Q-MAP reader, parser, catalogue or analysis function.
"""

from __future__ import annotations

import csv
import json
import statistics
from datetime import date, datetime, timedelta

import pytest

from fixtures.builders import ohlcv
from qmap.analytical_engine import DATASET_SUMMARY, run_analysis
from qmap.catalog import list_datasets
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D

DAYS = [date(2025, 12, 1) + timedelta(days=i) for i in range(60) if (date(2025, 12, 1) + timedelta(days=i)).weekday() < 5]


@pytest.fixture
def scanned(settings, db, tmp_path):
    folder = tmp_path / "Q-MAP_TEST_FILES"
    folder.mkdir()
    rows = ohlcv(len(DAYS), seed=7, base=22000.0)
    path = folder / "NSE_NIFTY, 1D.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:  # the owner's DD-MM-YY layout with a Net Volume column
        w = csv.writer(fh)
        w.writerow(["time", "open", "high", "low", "close", "Volume", "Net Volume"])
        for i, (d, r) in enumerate(zip(DAYS, rows)):
            w.writerow([d.strftime("%d-%m-%y")] + r + [-(i * 11)])
    source_bytes = path.read_bytes()
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata")
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        result = D.scan_source(run, src.source_id)
    return {"path": path, "bytes": source_bytes, "result": result, "src": src}


def _independent(path, start=None, end=None):
    """Expected Dataset Summary figures from the source TEXT only."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))[1:]
    bars = []
    for r in rows:
        d = datetime.strptime(r[0], "%d-%m-%y").date()  # all years here are 2025-2026: no century question
        if (start is None or d >= start) and (end is None or d <= end):
            bars.append((d, float(r[4]), float(r[5])))
    bars.sort()
    closes = [c for _, c, _ in bars]
    rets = [(b / a - 1) * 100 for a, b in zip(closes, closes[1:])]
    gaps = [(b[0] - a[0]).days for a, b in zip(bars, bars[1:])]
    return {"Bars": len(bars), "First bar": bars[0][0], "Last bar": bars[-1][0],
            "Calendar days covered": (bars[-1][0] - bars[0][0]).days + 1, "Longest gap (days)": max(gaps),
            "First close": closes[0], "Last close": closes[-1],
            "Change first-last close %": (closes[-1] / closes[0] - 1) * 100, "Returns counted": len(rets),
            "Mean return %": statistics.fmean(rets), "Std dev return %": statistics.stdev(rets),
            "Smallest return %": min(rets), "Largest return %": max(rets),
            "Average volume": statistics.fmean(v for _, _, v in bars)}


def test_folder_file_to_verified_analysis(settings, db, scanned):
    # ingestion: one dataset, read automatically, source untouched
    rel, change, action, outcome, detail = scanned["result"].files[0]
    assert (rel, outcome) == ("NSE_NIFTY, 1D.csv", "imported"), detail
    assert scanned["path"].read_bytes() == scanned["bytes"]
    datasets = list_datasets(db)
    assert len(datasets) == 1
    ds = datasets[0]
    assert (ds.instrument, ds.timeframe, ds.row_count) == ("NSE:NIFTY", "1D", len(DAYS))
    assert ds.processing_version.startswith("auto_") and ds.source_files == ["NSE_NIFTY, 1D.csv"]

    # analysis over a sub-period, through the Workbench's engine
    start, end = DAYS[5], DAYS[-6]
    res = run_analysis(settings, db, DATASET_SUMMARY, [ds.dataset_id],
                       {"date_from": start.strftime("%d/%m/%y"), "date_to": end.strftime("%d-%b-%y")})
    assert res.ok, res.message
    out = next(p for p in res.outputs if p.name.startswith("Dataset_Summary_"))
    with open(out, newline="", encoding="utf-8") as fh:
        got = next(csv.DictReader(fh))

    exp = _independent(scanned["path"], start, end)
    assert int(got["Bars"]) == exp["Bars"] and int(got["Returns counted"]) == exp["Returns counted"]
    assert int(got["Calendar days covered"]) == exp["Calendar days covered"]
    assert int(got["Longest gap (days)"]) == exp["Longest gap (days)"]
    assert got["First bar"] == exp["First bar"].strftime("%d-%b-%y") and got["Last bar"] == exp["Last bar"].strftime("%d-%b-%y")
    for k in ("First close", "Last close", "Change first-last close %", "Mean return %", "Std dev return %",
              "Smallest return %", "Largest return %"):
        assert float(got[k]) == pytest.approx(exp[k], abs=0.00005), k  # the output is rounded to 4 decimals
    assert float(got["Average volume"]) == pytest.approx(exp["Average volume"], abs=0.005)

    # provenance: Run ID, parameters, dataset identity and outputs are recorded
    run = db.one("SELECT * FROM runs WHERE run_id = ?", (res.run_id,))
    assert res.run_id.startswith("DSUM_") and run["status"] == "completed"
    assert [r[0] for r in db.query("SELECT dataset_id FROM run_inputs WHERE run_id = ?", (res.run_id,))] == [ds.dataset_id]
    outputs = {r[0] for r in db.query("SELECT relative_path FROM run_outputs WHERE run_id = ?", (res.run_id,))}
    assert any(p.endswith(out.name) for p in outputs)
    meta = json.loads(res.metadata_path.read_text(encoding="utf-8"))
    assert meta["run_id"] == res.run_id
    assert [d["dataset_id"] for d in meta["input_datasets"]] == [ds.dataset_id]
    assert meta["input_datasets"][0]["sha256"] == ds.sha256
    assert meta["input_datasets"][0]["processing_version"] == ds.processing_version
    assert meta["parameters"]["date_from"] == start.isoformat() and meta["parameters"]["date_to"] == end.isoformat()
    assert meta["outputs"] == [out.name]


def test_a_refused_request_creates_no_run_and_no_output(settings, db, scanned):
    ds = list_datasets(db)[0]
    runs_before = db.one("SELECT COUNT(*) FROM runs")[0]
    folders_before = sorted(p.name for p in (settings.output_root / "Research_Reports").glob("*")) \
        if (settings.output_root / "Research_Reports").exists() else []
    res = run_analysis(settings, db, DATASET_SUMMARY, [ds.dataset_id], {"date_from": "01/01/30"})
    assert not res.ok and res.run_id is None
    assert db.one("SELECT COUNT(*) FROM runs")[0] == runs_before
    after = sorted(p.name for p in (settings.output_root / "Research_Reports").glob("*")) \
        if (settings.output_root / "Research_Reports").exists() else []
    assert after == folders_before
