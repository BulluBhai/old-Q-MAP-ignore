"""Dataset Summary (analysis `dataset_summary`, version 1).

A UTILITY, not a research methodology: it describes the data and proves the research path end to end (readiness,
Run ID, recorded inputs, outputs, metadata). It makes no market judgement and defines no signal.

For each selected dataset, within the optional period:
  bars, first and last bar date, calendar days covered, longest gap between consecutive bars (calendar days),
  first and last close, change from first to last close (%), bar-to-bar close returns (count, mean, standard
  deviation, smallest, largest, in %), bars with any quality flag, bars with volume, average volume.

Bar-to-bar return = close / previous close - 1, using only consecutive bars of the same dataset, so no value uses
information from a later bar than the one it is reported for. Standard deviation uses n - 1 (sample).
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from ..catalog import DataRequirement, TIMEFRAME_ORDER, fmt_date, get_dataset, read_dataset
from .base import AnalysisSpec, Parameter, RunContext

COLUMNS = ("Dataset", "Instrument", "Timeframe", "Storage", "Validation", "Bars", "First bar", "Last bar",
           "Calendar days covered", "Longest gap (days)", "First close", "Last close", "Change first-last close %",
           "Returns counted", "Mean return %", "Std dev return %", "Smallest return %", "Largest return %",
           "Bars with quality flags", "Bars with volume", "Average volume")


def _r(x, nd=4):
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def summarise(ctx: RunContext, dataset_id: int) -> dict:
    d = get_dataset(ctx.db, dataset_id)
    t = read_dataset(ctx.settings, ctx.db, dataset_id, date_from=ctx.params.get("date_from"),
                     date_to=ctx.params.get("date_to"))
    dates = t.column("session_date").to_pylist()
    close = np.asarray(t.column("close").to_numpy(zero_copy_only=False), dtype=float)
    vol = t.column("volume")
    vol_ok = np.asarray(vol.is_valid().to_numpy(zero_copy_only=False), dtype=bool)
    flags = np.asarray(t.column("quality_flags").to_numpy(zero_copy_only=False), dtype=np.int64)
    n = len(dates)
    rets = (close[1:] / close[:-1] - 1.0) * 100.0 if n > 1 else np.array([])
    gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if a and b]
    volumes = np.asarray(vol.to_numpy(zero_copy_only=False), dtype=float)[vol_ok] if vol_ok.any() else np.array([])
    return {
        "Dataset": dataset_id, "Instrument": d.instrument, "Timeframe": d.timeframe_label, "Storage": d.storage_label,
        "Validation": "Passed with warnings" if d.warnings else "Passed", "Bars": n,
        "First bar": fmt_date(dates[0]) if n else "", "Last bar": fmt_date(dates[-1]) if n else "",
        "Calendar days covered": (dates[-1] - dates[0]).days + 1 if n else 0,
        "Longest gap (days)": max(gaps) if gaps else "",
        "First close": _r(close[0]) if n else "", "Last close": _r(close[-1]) if n else "",
        "Change first-last close %": _r((close[-1] / close[0] - 1) * 100) if n > 1 else "",
        "Returns counted": int(rets.size),
        "Mean return %": _r(rets.mean()) if rets.size else "",
        "Std dev return %": _r(rets.std(ddof=1)) if rets.size > 1 else "",
        "Smallest return %": _r(rets.min()) if rets.size else "",
        "Largest return %": _r(rets.max()) if rets.size else "",
        "Bars with quality flags": int((flags != 0).sum()), "Bars with volume": int(vol_ok.sum()),
        "Average volume": _r(volumes.mean(), 2) if volumes.size else "",
    }


def execute(ctx: RunContext) -> list[Path]:
    rows = []
    for i in ctx.dataset_ids:
        ctx.log(f"Summarising dataset {i}...")
        rows.append(summarise(ctx, i))
    out = ctx.output(f"Dataset_Summary_{ctx.stamp}.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    ctx.log(f"Wrote {out.name} ({len(rows)} row(s)).")
    return [out]


SPEC = AnalysisSpec(
    analysis_id="dataset_summary", name="Dataset Summary", version=1,
    description="Coverage and descriptive statistics of prepared datasets (bars, dates, gaps, bar-to-bar returns, "
                "volume). A utility that checks data before research; it is not a research methodology.",
    run_prefix="DSUM",
    requirement=DataRequirement(timeframes=TIMEFRAME_ORDER, min_rows=2),
    execute=execute,
    parameters=(Parameter("date_from", "Start date", "date", help="Optional, e.g. 01-Jan-24. Empty = from the first bar."),
                Parameter("date_to", "End date", "date", help="Optional. Empty = to the last bar.")),
    min_datasets=1, max_datasets=50,
    kind_note="descriptive statistics only - no signals, rankings or methodology",
)
