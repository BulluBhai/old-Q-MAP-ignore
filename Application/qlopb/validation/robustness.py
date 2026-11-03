"""
Robustness descriptions (facts only - no new scores, no recommendations).

Neighbouring MA periods are almost the same indicator, so a good result at one
period should usually be surrounded by similar results. These helpers describe
how a ranked candidate compares with its neighbours and whether the Top-N list
contains near-duplicates. They are informational and never change a ranking.
"""
from __future__ import annotations

import numpy as np


def neighbour_summary(results: list, ma_type: str, period: int, width: int = 3) -> dict:
    """IS affinity of the same MA type at period +/- `width` (OK candidates only)."""
    scores = []
    for r in results:
        if (r["ma_type"] == ma_type and r["ma_period"] != period
                and abs(r["ma_period"] - period) <= width and r.get("is_status") == "OK"):
            scores.append(r["is_affinity_score"])
    own = next((r["is_affinity_score"] for r in results
                if r["ma_type"] == ma_type and r["ma_period"] == period), np.nan)
    if not scores:
        return {"n_neighbours": 0, "neighbour_mean": np.nan, "neighbour_min": np.nan,
                "own_minus_neighbour_mean": np.nan}
    return {"n_neighbours": len(scores), "neighbour_mean": round(float(np.mean(scores)), 2),
            "neighbour_min": round(float(np.min(scores)), 2),
            "own_minus_neighbour_mean": round(float(own - np.mean(scores)), 2)}


def near_duplicate_pairs(frozen: list, width: int = 3) -> list:
    """Pairs in the frozen Top-N with the same MA type and periods within `width`."""
    pairs = []
    for i in range(len(frozen)):
        for j in range(i + 1, len(frozen)):
            (t1, p1), (t2, p2) = frozen[i], frozen[j]
            if t1 == t2 and abs(p1 - p2) <= width:
                pairs.append((f"{t1}-{p1}", f"{t2}-{p2}"))
    return pairs
