"""
Moving-average reference calculations: SMA, EMA, WMA, HMA, RMA.

Rules that every function follows
  * Causal: the value at bar i uses only closes at bar i and EARLIER.
  * Bars that do not yet have enough history are NaN (never zero).
  * Input is a 1-D sequence of closes, output is a numpy array of the same length.
  * These functions know nothing about interactions, scoring or reports.

The formulas are the ones used by MA Affinity Scanner V2 and have not been
changed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

STATUS = "implemented"


def _as_float_array(close) -> np.ndarray:
    arr = np.asarray(close, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("close must be a one-dimensional sequence of prices.")
    return arr


def _check_period(period) -> int:
    if isinstance(period, bool) or not isinstance(period, (int, np.integer)):
        raise ValueError(f"MA period must be a whole number, got {period!r}.")
    if period < 1:
        raise ValueError(f"MA period must be 1 or more, got {period}.")
    return int(period)


def calc_sma(close, period) -> np.ndarray:
    """Simple MA: plain average of the last `period` closes."""
    period = _check_period(period)
    arr = _as_float_array(close)
    return pd.Series(arr).rolling(period, min_periods=period).mean().to_numpy()


def calc_ema(close, period) -> np.ndarray:
    """Exponential MA: alpha = 2/(n+1), seeded with the SMA of the first n bars."""
    period = _check_period(period)
    arr = _as_float_array(close)
    n = len(arr)
    out = np.full(n, np.nan)
    if n >= period:
        out[period - 1] = float(np.mean(arr[:period]))
        alpha = 2.0 / (period + 1)
        for i in range(period, n):
            out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    return out


def _wma_core(values, period) -> np.ndarray:
    """Linearly weighted MA: oldest bar weight 1 ... newest bar weight `period`.
    Any NaN inside a window makes that window's result NaN."""
    arr = np.asarray(values, dtype=np.float64)
    n = len(arr)
    out = np.full(n, np.nan)
    if n < period:
        return out
    weights = np.arange(1.0, period + 1.0)
    # convolve with reversed weights so the NEWEST bar gets the largest weight
    conv = np.convolve(arr, weights[::-1], mode="full")
    out[period - 1:] = conv[period - 1:n] / weights.sum()
    return out


def calc_wma(close, period) -> np.ndarray:
    """Weighted MA (linear weights, newest bar weighs most)."""
    period = _check_period(period)
    return _wma_core(_as_float_array(close), period)


def calc_hma(close, period) -> np.ndarray:
    """Hull MA = WMA( 2*WMA(n/2) - WMA(n), sqrt(n) ).
    V2 'frozen' lengths: n1 = max(2, n//2), n_sqrt = max(2, floor(sqrt(n)))."""
    period = _check_period(period)
    arr = _as_float_array(close)
    n_half = max(2, period // 2)
    n_sqrt = max(2, int(np.floor(np.sqrt(period))))
    raw = 2.0 * _wma_core(arr, n_half) - _wma_core(arr, period)
    return _wma_core(raw, n_sqrt)


def calc_rma(close, period) -> np.ndarray:
    """Wilder / RMA: alpha = 1/n, seeded with the SMA of the first n bars."""
    period = _check_period(period)
    arr = _as_float_array(close)
    n = len(arr)
    out = np.full(n, np.nan)
    if n >= period:
        out[period - 1] = float(np.mean(arr[:period]))
        alpha = 1.0 / period
        for i in range(period, n):
            out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    return out


MA_CALCULATORS = {
    "SMA": calc_sma,
    "EMA": calc_ema,
    "WMA": calc_wma,
    "HMA": calc_hma,
    "RMA": calc_rma,
}


def compute_ma(close, ma_type: str, period: int) -> np.ndarray:
    """Calculate one moving average by name, e.g. compute_ma(closes, 'SMA', 50)."""
    try:
        fn = MA_CALCULATORS[ma_type]
    except KeyError:
        raise ValueError(
            f"Unknown MA type '{ma_type}'. Allowed: {', '.join(MA_CALCULATORS)}.")
    return fn(close, period)
