"""
Interaction engine: finds the moments when price interacts with a moving average
and records what happened afterwards.

These are the V2 definitions, kept unchanged:
  * ZONE      : a bar is "in the zone" if  low <= MA*(1+prox)  and  high >= MA*(1-prox).
  * ENTRY     : the first bar of a visit - in the zone now, NOT in the zone on the
                previous bar. Staying inside the zone does not create new events.
  * COOLDOWN  : two recorded events must be at least `cooldown` bars apart.
  * ELIGIBLE  : an event is recorded only if  bar + primary_window  is still inside
                the period (so the forward window never crosses the period end).
  * SIDE      : previous close above the MA = Support, below = Resistance, equal = Neutral.
  * OUTCOME   : Support succeeds if the forward return is above 0; Resistance succeeds
                if it is below 0. A forward return of exactly 0 counts as Failure.
  * FORWARD RETURN = (close[i+w] - close[i]) / close[i] * 100, only if i+w is inside
                the period, otherwise the window is "NoData" (missing, not zero).
Nothing here looks at bars after the period end, so there is no look-ahead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from qlopb.config import settings as cfg


def detect_interaction_episodes(high, low, ma_vals, start_bar, end_bar, fwd_end_bar,
                                primary_window, proximity_pct, cooldown_bars,
                                initial_in_zone=False, last_event_bar=-999999):
    """Return (event_bar_indexes, final_in_zone, final_last_event_bar).

    `initial_in_zone` / `last_event_bar` carry the state across the IS->OOS
    boundary so that no artificial 'first OOS interaction' is created when price
    is already inside the zone at the split.
    """
    n = len(ma_vals)
    prox = proximity_pct / 100.0
    scan_s = max(start_bar, 0)
    scan_e = min(end_bar, n - 1)
    if scan_s > scan_e:
        return [], initial_in_zone, last_event_bar

    ma_s = ma_vals[scan_s: scan_e + 1]
    hi_s = high[scan_s: scan_e + 1]
    lo_s = low[scan_s: scan_e + 1]
    valid = ~np.isnan(ma_s)
    zone_up = np.where(valid, ma_s * (1.0 + prox), np.inf)
    zone_lo = np.where(valid, ma_s * (1.0 - prox), -np.inf)
    in_zone = valid & (lo_s <= zone_up) & (hi_s >= zone_lo)

    previous = np.concatenate([[initial_in_zone], in_zone[:-1]])
    entries = in_zone & ~previous
    final_in_zone = bool(in_zone[-1])

    record_end = min(scan_e, fwd_end_bar - primary_window)
    events, last_ev = [], last_event_bar
    for local_i in np.where(entries)[0]:
        i = int(local_i) + scan_s
        if i > record_end:
            continue
        if (i - last_ev) >= cooldown_bars:
            events.append(i)
            last_ev = i
    return events, final_in_zone, last_ev


def _stamp_text(ts) -> str:
    ts = pd.Timestamp(ts)
    if ts.hour == 0 and ts.minute == 0 and ts.second == 0:
        return ts.strftime(cfg.DATE_FMT)
    return ts.strftime(cfg.DATETIME_FMT)


def build_interaction_records(event_idx, ma_vals, ma_type, period, fwd_end_bar,
                              close, high, low, index, regime_ma, fwd_windows):
    """Turn event bar numbers into one record (dict) per interaction."""
    n = len(close)
    records = []
    slope_w = cfg.SLOPE_LOOKBACK_BARS
    flat = cfg.SLOPE_FLAT_THRESHOLD_PCT
    for i in event_idx:
        ma = float(ma_vals[i])
        cl = float(close[i])
        prev = float(close[i - 1]) if i > 0 else cl
        side = "Support" if prev > ma else "Resistance" if prev < ma else "Neutral"
        slope_dir = "Unknown"
        if i >= slope_w and not np.isnan(ma_vals[i - slope_w]):
            sp = (ma - float(ma_vals[i - slope_w])) / (ma * slope_w) * 100
            slope_dir = "Rising" if sp > flat else "Declining" if sp < -flat else "Flat"
        rv = float(regime_ma[i])
        regime = "Unknown" if np.isnan(rv) else "Bullish" if cl > rv else "Bearish"
        frets, fouts = {}, {}
        for w in fwd_windows:
            fi = i + w
            if fi <= fwd_end_bar and fi < n:
                fr = (float(close[fi]) - cl) / cl * 100
                frets[f"fwd_{w}"] = fr
                if side == "Support":
                    fouts[f"outcome_{w}"] = "Success" if fr > 0 else "Failure"
                elif side == "Resistance":
                    fouts[f"outcome_{w}"] = "Success" if fr < 0 else "Failure"
                else:
                    fouts[f"outcome_{w}"] = "Neutral"
            else:
                frets[f"fwd_{w}"] = np.nan
                fouts[f"outcome_{w}"] = "NoData"
        records.append({
            "ma_type": ma_type, "ma_period": period, "ma_label": f"{ma_type}-{period}",
            "bar_idx": int(i), "date": _stamp_text(index[i]),
            "close": round(cl, 4), "high": round(float(high[i]), 4), "low": round(float(low[i]), 4),
            "ma_value": round(ma, 4), "distance_pct": round((cl - ma) / ma * 100, 4),
            "side": side, "ma_slope": slope_dir, "regime": regime, **frets, **fouts})
    return records
