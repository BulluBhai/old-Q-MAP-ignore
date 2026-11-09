"""
In-sample / out-of-sample (IS/OOS) rules.

Order of work (never changed):
   1. score every candidate on the IS period only
   2. rank on IS scores only
   3. FREEZE the Top-N list
   4. score the frozen candidates on the OOS period, independently
OOS numbers never change a rank, a score or the Top-N list.
"""
from __future__ import annotations

import numpy as np


def compute_split(n_bars: int, is_pct: int) -> tuple:
    """Return (is_end_bar, oos_start_bar). Same rule as V2: is_end = int(n*pct/100) - 1."""
    is_end = int(n_bars * is_pct / 100) - 1
    return is_end, is_end + 1


def forward_window_fits(bar: int, window: int, period_end_bar: int, n_bars: int) -> bool:
    """True if the forward window ends inside the period (cannot cross its boundary)."""
    return (bar + window) <= period_end_bar and (bar + window) < n_bars


def rank_candidates(results: list) -> list:
    """Rank candidates with is_status == 'OK' by their (2-decimal) IS affinity score,
    highest first; equal scores keep the original candidate order (stable).
    Adds 'rank' (None for non-OK candidates) and 'rank_tie' (True if the score equals
    a neighbour's score, so the order between them is arbitrary). Returns the list."""
    for r in results:
        r["rank"] = None
        r["rank_tie"] = False
    ok = [(i, r) for i, r in enumerate(results) if r.get("is_status") == "OK"]
    ok.sort(key=lambda x: -x[1]["is_affinity_score"])
    for pos, (_, r) in enumerate(ok, 1):
        r["rank"] = pos
    for k in range(len(ok)):
        s = ok[k][1]["is_affinity_score"]
        if (k > 0 and ok[k - 1][1]["is_affinity_score"] == s) or \
                (k + 1 < len(ok) and ok[k + 1][1]["is_affinity_score"] == s):
            ok[k][1]["rank_tie"] = True
    return results


def freeze_top_n(results: list, top_n: int) -> list:
    """Return the labels of the Top-N ranked candidates, in rank order (a frozen copy)."""
    ranked = sorted((r for r in results if r.get("rank")), key=lambda r: r["rank"])
    return [(r["ma_type"], r["ma_period"]) for r in ranked[:top_n]]


def consistency(is_sr, oos_sr, oos_outcomes: int, min_oos_outcomes: int) -> dict:
    """IS/OOS consistency (report only, never part of the score).

    consistency = max(0, 1 - 2*|IS SR - OOS SR|/100) * 100      (V2 formula)
    `value` is only given when the OOS sample has at least `min_oos_outcomes` outcomes;
    the un-gated V2 number is always kept in `raw` so nothing is hidden.
    """
    def nan(x):
        return x is None or (isinstance(x, float) and np.isnan(x))
    if nan(is_sr) or nan(oos_sr):
        return {"diff": np.nan, "raw": np.nan, "value": np.nan, "status": "NOT_AVAILABLE"}
    diff = round(abs(float(is_sr) - float(oos_sr)), 2)
    raw = round(float(max(0.0, 1.0 - 2 * (diff / 100))) * 100, 2)
    if oos_outcomes < min_oos_outcomes:
        return {"diff": diff, "raw": raw, "value": np.nan, "status": "INSUFFICIENT_OOS_EVIDENCE"}
    return {"diff": diff, "raw": raw, "value": raw, "status": "OK"}
