"""Timeframe values (owner instruction DQ-7, 03-Nov-26). Shared by data preparation AND analysis, so it lives in core.

Timeframes are open-ended: any whole number of minutes ("3m", "75m") or hours ("2h"), 1D, 1W, 1M (1Q, 1Y for derived
data), other day periods ("2d", inferred only), and MIXED for a file whose sampled blocks show materially different
intervals. The bar interval is inferred from the data (data_engine/timeframe_infer.py).
"""

from __future__ import annotations

import re

MIXED = "MIXED"
PERIOD_TIMEFRAMES = ("1D", "1W", "1M", "1Q", "1Y")
_INTRADAY_TF = re.compile(r"^([1-9]\d{0,3})(m|h)$")


_DAY_TF = re.compile(r"^([2-9]|[1-9]\d{1,2})d$")  # other identifiable periods in days, e.g. 2d (inferred only)


def timeframe_minutes(tf: str | None) -> int | None:
    """Minutes of an intraday timeframe ("75m" -> 75, "2h" -> 120); None for 1D/1W/1M/MIXED/anything else."""
    m = _INTRADAY_TF.match(tf or "")
    if not m:
        return None
    minutes = int(m.group(1)) * (60 if m.group(2) == "h" else 1)
    return minutes if minutes < 24 * 60 else None


def minutes_label(minutes: int) -> str:
    """The one canonical label for an interval: whole hours as "<n>h", otherwise "<n>m" (60 -> 1h, 75 -> 75m)."""
    return f"{minutes // 60}h" if minutes % 60 == 0 else f"{minutes}m"


def canonical_timeframe(tf: str | None) -> str | None:
    """"60m" -> "1h", "120m" -> "2h", "1D" -> "1D"; None if not a valid timeframe."""
    if tf in PERIOD_TIMEFRAMES or tf == MIXED or _DAY_TF.match(tf or ""):
        return tf
    m = timeframe_minutes(tf)
    return minutes_label(m) if m else None


def is_timeframe(tf: str | None) -> bool:
    return canonical_timeframe(tf) is not None
