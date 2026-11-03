"""
Timeframe engine: build coarser bars (Daily / Weekly / Monthly / Quarterly) from
finer bars. It never invents finer bars from coarser ones.

Labelling rule: each new bar is labelled with the date/time of the LAST source
bar inside the period, so a label never points to a time before the information
in that bar was known.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qlopb.core.data_engine import infer_frequency

_RULES = {"D": "D", "W": "W", "M": "M", "Q": "Q"}
_RANK = {"D": 1440.0, "W": 7 * 1440.0, "M": 28 * 1440.0, "Q": 90 * 1440.0}


class TimeframeError(ValueError):
    pass


def resample_ohlc(df: pd.DataFrame, timeframe: str) -> tuple:
    """Return (new_df, notes). timeframe: 'as_loaded' | D | W | M | Q."""
    notes = []
    if timeframe in (None, "as_loaded"):
        return df, notes
    if timeframe not in _RULES:
        raise TimeframeError(f"Unknown timeframe '{timeframe}'. Use as_loaded, D, W, M or Q.")
    label, minutes = infer_frequency(df.index)
    if np.isnan(minutes):
        raise TimeframeError("Cannot tell the source bar size (too few rows).")
    if _RANK[timeframe] < minutes * 0.99:
        raise TimeframeError(
            f"The data is {label}; it cannot be turned into a finer timeframe ({timeframe}).")
    if timeframe == "D" and minutes >= 1440:
        return df, ["Source is already daily; no aggregation applied."]

    key = df.index.normalize() if timeframe == "D" else df.index.to_period(_RULES[timeframe])
    grp = df.groupby(key, sort=True)
    out = pd.DataFrame({
        "open": grp["open"].first(),
        "high": grp["high"].max(),
        "low": grp["low"].min(),
        "close": grp["close"].last(),
        "volume": grp["volume"].sum(min_count=1),
        "bars_in_period": grp["close"].size(),
    })
    last_ts = pd.Series(df.index, index=df.index).groupby(key, sort=True).last()
    new_index = pd.DatetimeIndex(last_ts.to_numpy())
    if timeframe != "D" or minutes < 1440:
        # coarser-than-intraday labels are dates (last bar's date)
        new_index = new_index.normalize()
    out.index = new_index
    out.index.name = "datetime"
    out["boundary_period"] = False
    if len(out) >= 1:
        out.iloc[0, out.columns.get_loc("boundary_period")] = True
        out.iloc[-1, out.columns.get_loc("boundary_period")] = True
    notes.append(
        f"Aggregated {len(df)} bars into {len(out)} {timeframe} bars (label = date of the last bar "
        "in the period). The first and last periods are marked boundary_period because they may be "
        "incomplete.")
    return out[["open", "high", "low", "close", "volume", "bars_in_period", "boundary_period"]], notes
