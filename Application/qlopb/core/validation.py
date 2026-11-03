"""
Validation helpers shared by the data engine and the research engine.

These functions only CHECK things and report plain-English problems. They never
change prices and never calculate research results.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("open", "high", "low", "close")


def ohlc_inconsistent_mask(open_, high, low, close) -> np.ndarray:
    """True where a bar breaks the basic rule: high must be the highest value
    and low the lowest value of that bar. NaN comparisons give False (those rows
    are caught by the 'missing price' check instead)."""
    o = np.asarray(open_, dtype=float)
    h = np.asarray(high, dtype=float)
    l = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    with np.errstate(invalid="ignore"):
        return (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)


def validate_ohlc_frame(df: pd.DataFrame) -> list:
    """Check that a frame is ready for research. Returns a list of problems
    (empty list = fine). Used on every frame before any calculation."""
    problems = []
    if not isinstance(df, pd.DataFrame):
        return ["Input is not a table of prices."]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        problems.append("Missing required column(s): " + ", ".join(missing) + ".")
        return problems
    if not isinstance(df.index, pd.DatetimeIndex):
        problems.append("The index must be dates/times.")
        return problems
    if df.index.tz is not None:
        problems.append("Timestamps must be timezone-naive (the loader removes offsets).")
    if len(df) == 0:
        problems.append("The table has no rows.")
        return problems
    if not df.index.is_monotonic_increasing:
        problems.append("Dates are not in ascending order.")
    if df.index.has_duplicates:
        problems.append("Duplicate timestamps are present.")
    for col in REQUIRED_COLUMNS:
        vals = pd.to_numeric(df[col], errors="coerce")
        if vals.isna().any():
            problems.append(f"Column '{col}' contains missing or non-numeric values.")
        elif np.isinf(vals).any():
            problems.append(f"Column '{col}' contains infinite (inf / -inf) values.")
        elif (vals <= 0).any():
            problems.append(f"Column '{col}' contains zero or negative prices.")
    if not problems:
        bad = ohlc_inconsistent_mask(df["open"], df["high"], df["low"], df["close"])
        if bad.any():
            problems.append(f"{int(bad.sum())} bar(s) have High/Low inconsistent with Open/Close.")
    return problems


def check_data_for_settings(df: pd.DataFrame, settings) -> tuple:
    """Compare the data length with the chosen settings.

    Returns (errors, warnings). Errors stop the run; warnings are shown in the
    report. 'Not enough data' is always reported as such, never as a bad result.
    """
    errors, warnings = [], []
    n = len(df)
    is_end = int(n * settings.is_pct / 100) - 1       # same rule as V2
    is_bars = is_end + 1
    oos_bars = n - is_bars
    pw = settings.primary_window
    if is_bars < settings.ma_start + pw + 1:
        errors.append(
            f"The in-sample part has only {is_bars} bars, which is too few for the "
            f"shortest MA ({settings.ma_start}) plus the primary forward window ({pw}).")
    elif is_bars < settings.ma_end + pw:
        warnings.append(
            f"The in-sample part has {is_bars} bars; MAs longer than about "
            f"{max(is_bars - pw, 0)} have no in-sample history and will be reported "
            f"as 'insufficient data'.")
    if oos_bars < pw + 1:
        warnings.append(
            f"The out-of-sample part has only {oos_bars} bars (primary window {pw}); "
            f"out-of-sample results will be 'insufficient data'.")
    if settings.regime_ma > n:
        warnings.append(f"Regime MA ({settings.regime_ma}) is longer than the data ({n} bars).")
    longest = max(settings.fwd_windows)
    if longest >= is_bars:
        warnings.append(f"The longest forward window ({longest}) is not shorter than the "
                        f"in-sample period ({is_bars} bars).")
    return errors, warnings
