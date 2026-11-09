"""
Statistical helpers. Same formulas as MA Affinity Scanner V2 (unchanged).

IMPORTANT: p-values here are plain one-sided binomial tests of one candidate
against a 50% success rate. They are NOT adjusted for the many candidates that
are tested, so they must not be read as proof.
"""
from __future__ import annotations

import math

from scipy import stats as sci_stats

Z_95 = 1.96


def wilson_lower_bound(successes: int, n: int, z: float = Z_95) -> float:
    """Lower end of the Wilson 95% interval for a success rate (0..1)."""
    if n <= 0:
        return float("nan")
    p = successes / n
    den = 1 + z ** 2 / n
    centre = p + z ** 2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2))
    return (centre - margin) / den


def reliability_score(successes: int, n: int) -> float:
    """V2 'Reliability' (0-100): Wilson lower bound rescaled so 50% -> 0 and 100% -> 100.
    Only calculated when there are at least 5 outcomes; otherwise NaN (not zero)."""
    if n < 5:
        return float("nan")
    wlo = wilson_lower_bound(successes, n)
    return float(max(0.0, min(1.0, (wlo - 0.5) / 0.5))) * 100


def binomial_pvalue_greater(successes: int, n: int) -> float:
    """One-sided p-value that the true success rate is above 50%. NaN if n < 5."""
    if n < 5:
        return float("nan")
    return float(sci_stats.binomtest(int(successes), int(n), p=0.5, alternative="greater").pvalue)
