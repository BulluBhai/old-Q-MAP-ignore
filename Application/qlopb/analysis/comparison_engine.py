"""
Comparison engine: puts the frozen Top-N lists of several instruments side by side.
Purely descriptive. Different instruments may have different lengths and
timeframes, so each row carries its own bar count and period.
"""
from __future__ import annotations

import pandas as pd


def top_n_table(result) -> pd.DataFrame:
    rows = []
    for r in result.frozen_top_results():
        rows.append({
            "instrument": result.label, "rank": r["rank"], "ma_label": r["ma_label"],
            "is_affinity": r["is_affinity_score"], "is_n": r["is_n"], "is_sr_pct": r["is_overall_sr"],
            "oos_status": r.get("oos_status"), "oos_n": r.get("oos_n"),
            "oos_sr_pct": r.get("oos_overall_sr"),
            "consistency_status": r.get("is_oos_consistency_status"),
            "n_bars": result.data_info["n_bars"],
            "period": f"{result.data_info['first']} to {result.data_info['last']}",
            "timeframe": result.data_info["frequency"]})
    return pd.DataFrame(rows)


def compare_instruments(results: dict) -> dict:
    """results: {label: ResearchResult}. Returns {'top_n': DataFrame, 'shared': DataFrame}."""
    tables = [top_n_table(r) for r in results.values()]
    tables = [t for t in tables if len(t)]
    top = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    if top.empty:
        return {"top_n": top, "shared": pd.DataFrame()}
    shared = (top.groupby("ma_label")["instrument"].agg(["count", lambda s: ", ".join(s)])
              .rename(columns={"count": "n_instruments", "<lambda_0>": "instruments"}))
    shared = shared[shared["n_instruments"] > 1].reset_index()
    return {"top_n": top, "shared": shared}
