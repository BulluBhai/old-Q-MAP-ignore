"""Dataset Summary (analysis `dataset_summary`, version 1).

A UTILITY, not a research methodology: it describes the data and proves the research path end to end (readiness,
Run ID, recorded inputs, outputs, metadata). It makes no market judgement and defines no signal.

For each selected dataset, within the optional period:
  bars, first and last bar date, calendar days covered, longest gap between consecutive bars (calendar days),
  first and last close, change from first to last close (%), bar-to-bar close returns (count, mean, standard
  deviation, smallest, largest, in %), bars with any quality flag, bars with volume, average volume; and, kept separate, conflicting timestamps,
  conflicting observation rows, returns between two observations of one timestamp, derived bars built from conflicts,
  and exact duplicate rows removed at load, with a plain note when results are potentially misleading.

Bar-to-bar return = close / previous close - 1, using only consecutive bars of the same dataset, so no value uses
information from a later bar than the one it is reported for. Standard deviation uses n - 1 (sample).
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from ..catalog import DataRequirement, fmt_date, get_dataset, read_dataset
from ..data_engine import canonical as C
from .base import AnalysisSpec, Parameter, RunContext

COLUMNS = ("Dataset", "Instrument", "Timeframe", "Storage", "Validation", "Bars", "First bar", "Last bar",
           "Calendar days covered", "Longest gap (days)", "First close", "Last close", "Change first-last close %",
           "Returns counted", "Mean return %", "Std dev return %", "Smallest return %", "Largest return %",
           "Bars with quality flags", "Conflicting timestamps", "Conflicting observation rows",
           "Returns between conflicting observations", "Derived bars built from conflicting observations",
           "Exact duplicate rows removed at load", "Conflict note", "Bars with volume", "Average volume")


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
    # DQ-10: rows sharing a timestamp with different values are all kept; they are counted here, never resolved.
    # The statistics below are unchanged: they treat every stored row as a bar.
    keys = t.column("timestamp_utc").to_pylist() if "timestamp_utc" in t.column_names else dates
    keys = [k if k is not None else d for k, d in zip(keys, dates)]
    flagged = (flags & C.FLAG_CONFLICTING_OBSERVATION) != 0
    derived = d.layer == "timeframe"
    # Three different quantities, never added together (review 03-Nov-26):
    #   conflicting timestamps = distinct times that hold more than one different observation;
    #   conflicting observation rows = the stored rows at those times (always >= 2 per timestamp);
    #   exact duplicate rows removed = identical copies dropped at load (they are NOT in the dataset).
    # In a DERIVED dataset the flag marks a period built from conflicting daily observations instead.
    conflicted = set() if derived else {k for k, f in zip(keys, flagged) if f}
    conflict_rows = 0 if derived else int(flagged.sum())
    # bar-to-bar returns whose two rows are observations of the SAME timestamp: potentially misleading
    same_time_returns = 0 if derived else sum(1 for a, b in zip(keys, keys[1:]) if a == b and a in conflicted)
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
        "Bars with quality flags": int((flags != 0).sum()),
        "Conflicting timestamps": "" if derived else len(conflicted),
        "Conflicting observation rows": "" if derived else conflict_rows,
        "Returns between conflicting observations": "" if derived else same_time_returns,
        "Derived bars built from conflicting observations": int(flagged.sum()) if derived else "",
        "Exact duplicate rows removed at load": "" if derived else _duplicates_removed(ctx, d),
        "Conflict note": _conflict_note(derived, len(conflicted), conflict_rows, same_time_returns, int(flagged.sum())),
        "Bars with volume": int(vol_ok.sum()),
        "Average volume": _r(volumes.mean(), 2) if volumes.size else "",
    }


def _duplicates_removed(ctx: RunContext, d) -> int:
    row = ctx.db.one("SELECT q.rows_failed FROM datasets x JOIN quality_checks q ON q.attempt_id = x.created_by_attempt_id "
                     "WHERE x.dataset_id = ? AND q.check_name = 'exact_duplicates_removed'", (d.dataset_id,))
    return int(row["rows_failed"]) if row else 0


def _conflict_note(derived: bool, timestamps: int, rows: int, same_time_returns: int, derived_bars: int) -> str:
    if derived:
        return ("" if not derived_bars else f"{derived_bars} derived bar(s) were built from daily data with conflicting "
                "observations (existing rules applied to every row); treat them as potentially misleading.")
    if not timestamps:
        return ""
    return (f"Potentially misleading: {timestamps} timestamp(s) hold {rows} conflicting observations; every stored row "
            f"counts as a bar, so {same_time_returns} bar-to-bar return(s) compare two observations of the same time. "
            "Q-MAP has not chosen between them.")


def execute(ctx: RunContext) -> list[Path]:
    rows = []
    for i in ctx.dataset_ids:
        ctx.log(f"Summarising dataset {i}...")
        rows.append(summarise(ctx, i))
        if rows[-1]["Conflict note"]:
            ctx.log(f"WARNING dataset {i}: {rows[-1]['Conflict note']}")
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
    # any timeframe (DQ-7: 75m, 2h ... included); MIXED allowed with a visible warning, the statistics unchanged
    requirement=DataRequirement(timeframes=None, min_rows=2, allow_mixed=True),
    execute=execute,
    parameters=(Parameter("date_from", "Start date", "date",
                          help="Optional. Type 25/02/26, 25-02-26, 25-Feb-26 or 250226, or use Calendar. "
                               "Empty = from the first bar."),
                Parameter("date_to", "End date", "date",
                          help="Optional, same formats. Empty = to the last bar.")),
    min_datasets=1, max_datasets=50,
    kind_note="descriptive statistics only - no signals, rankings or methodology",
    result_tables=("Dataset_Summary_",),
)
