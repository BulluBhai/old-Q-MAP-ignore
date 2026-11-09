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


# ---- which DQ-7 comparison classified a dataset (independent review 04-Nov-26) ------------------------------------
# The DQ-7 correction of 04-Nov-26 (commit 1291d63) stops daily, weekly, monthly, quarterly and yearly sampled blocks
# from agreeing with one another. It is not a new processing version (that would reprocess and supersede every
# dataset; not authorised), so the inference record of every NEW classification carries this marker instead. A stored
# record WITHOUT it was made by the earlier comparison. Only daily-or-longer results can be affected: minute and
# day-or-longer blocks were already kept apart.
INFERENCE_LOGIC = "dq7-units-2026-11-04"
CORRECTED, EARLIER_SAME, EARLIER_CHANGED = "corrected", "earlier_same", "earlier_changed"
EARLIER_CHANGED_NOTE = (
    "Its timeframe was classified before the DQ-7 correction of 04-Nov-26. The sampled blocks recorded at that time "
    "show sections measured in different calendar units ({units}), so the corrected logic would classify this file "
    "as MIXED, not {tf}. The registered classification is kept unchanged (no reprocessing, OW-41); analyses that need "
    "one uniform bar interval treat it as mixed.")
EARLIER_SAME_NOTE = ("Its timeframe was classified before the DQ-7 correction of 04-Nov-26; the sampled blocks recorded "
                     "then are all in one unit, so the corrected logic gives the same result.")

_CALENDAR_UNITS = {"1W": "week", "1M": "month", "1Q": "quarter", "1Y": "year"}
_UNIT_WORDS = {"minute": "intraday", "day": "daily", "week": "weekly", "month": "monthly", "quarter": "quarterly",
               "year": "yearly"}


def is_minutes_label(label: str | None) -> bool:
    return bool(label) and (label.endswith("m") or label.endswith("h")) and label != "1M"


def measuring_unit(label: str) -> str:
    """The unit in which DQ-7 counts a sampled block's steps: minute, day (1D and 'Nd'), week, month, quarter, year.
    Steps can only be compared with an interval measured in the same unit (DQ-7 correction 04-Nov-26)."""
    return "minute" if is_minutes_label(label) else _CALENDAR_UNITS.get(label, "day")


def is_calendar_timeframe(tf: str | None) -> bool:
    """1D, 1W, 1M, 1Q, 1Y or an inferred day period such as 2d."""
    return bool(tf) and (tf in PERIOD_TIMEFRAMES or bool(_DAY_TF.match(tf)))


def classification_logic(record: dict | None) -> tuple[str | None, str]:
    """Read-only judgement of a STORED DQ-7 inference record: (CORRECTED | EARLIER_SAME | EARLIER_CHANGED | None, note).

    EARLIER_CHANGED: made before the correction, a single daily-or-longer timeframe, and its own recorded blocks span
    more than one measuring unit - exactly the case the correction changes (to MIXED). EARLIER_SAME: made before the
    correction but its recorded blocks are all in one unit, so the corrected comparison gives the same result. None: no
    DQ-7 sampling record, or a result the correction cannot change (intraday, MIXED, insufficient)."""
    if not record:
        return None, ""
    if record.get("logic") == INFERENCE_LOGIC:
        return CORRECTED, "Timeframe measured with the corrected DQ-7 comparison (04-Nov-26)."
    tf = record.get("timeframe")
    if record.get("status") != "consistent" or not is_calendar_timeframe(tf):
        return None, ""
    units = sorted({measuring_unit(b["interval"]) for b in record.get("blocks") or [] if b.get("interval")})
    if len(units) > 1:
        return EARLIER_CHANGED, EARLIER_CHANGED_NOTE.format(units=", ".join(_UNIT_WORDS[u] for u in units), tf=tf)
    return EARLIER_SAME, EARLIER_SAME_NOTE
