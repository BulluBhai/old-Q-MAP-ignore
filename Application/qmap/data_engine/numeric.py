"""Strict numeric parsing. Nothing is guessed and nothing is silently coerced to a number."""

from __future__ import annotations

import math
import re
from decimal import Decimal

OK, MISSING, INVALID = "ok", "missing", "invalid"

_PLAIN = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_NONFINITE = {"nan": math.nan, "+nan": math.nan, "-nan": math.nan, "inf": math.inf, "+inf": math.inf,
              "-inf": -math.inf, "infinity": math.inf, "+infinity": math.inf, "-infinity": -math.inf}


def parse_number(value, decimal: str = ".", thousands: str = "") -> tuple[float, str]:
    """Return (number, status). status: ok | missing | invalid.

    A non-finite result (NaN/inf, from a file value or a text token) is returned as such with
    status 'ok' so that the dedicated finiteness check can report it.
    """
    if value is None:
        return math.nan, MISSING
    if isinstance(value, bool):
        return math.nan, INVALID
    if isinstance(value, (int, float, Decimal)):
        try:
            return float(value), OK
        except (OverflowError, ValueError):
            return math.nan, INVALID
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return math.nan, MISSING
        if s.lower() in _NONFINITE:
            return _NONFINITE[s.lower()], OK
        if thousands:
            s = s.replace(thousands, "")
        if decimal != ".":
            s = s.replace(decimal, ".")
        if _PLAIN.match(s):
            return float(s), OK
        return math.nan, INVALID
    try:  # numpy scalars and similar
        return float(value), OK
    except (TypeError, ValueError):
        return math.nan, INVALID
