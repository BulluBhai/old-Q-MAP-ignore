"""IS/OOS boundary and cooldown (beta closure, 09-Nov-26): a controlled case worked out by hand from the APPROVED
QLOPB V2 definitions (BulluBhai/QLOPB README at the migrated commit 6cbadc7, "Research definitions"):

  * "Interaction: the first bar of a visit to the zone (rising edge). Staying inside is the same visit. Two RECORDED
    interactions must be at least cooldown bars apart. An interaction is recorded only if the primary forward window
    still fits inside its period (IS or OOS)."
  * "Forward return ... Missing if the window would cross the end of the period (never filled with zero)."
  * "The 'in zone' state and cooldown at the split are carried into OOS so no artificial first OOS interaction
    appears."

So an entry near the end of the in-sample period whose primary window does not fit is NOT recorded and therefore does
NOT start a cooldown; the cooldown carried into OOS is that of the last RECORDED interaction; and price already in the
zone at the split does not create an OOS interaction on the first OOS bar. The engine (unchanged, identical to 6cbadc7
apart from imports) is checked end to end with a hand-made MA, and the independent reference (Tests/beta) is checked on
the same arrays. No calculation is changed by this test.

Layout: 40 bars, IS 50 % -> IS bars 0-19, OOS bars 20-39; MA constant 100; proximity 3 % (zone 97-103); primary
forward window 3; second window 10; cooldown 5. A bar is in the zone when low 99 / high 101 / close 100, out of it at
120.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "qlopb"))
import _qlopb_helpers  # noqa: E402,F401  (sets the qlopb path)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ma_affinity_reference as REF  # noqa: E402

import qlopb.core.research_engine as RE  # noqa: E402
from qlopb.config.settings import MAResearchSettings  # noqa: E402

N, IS_END, PW, COOLDOWN = 40, 19, 3, 5


def _frame(in_zone_bars):
    close = np.full(N, 120.0)
    close[list(in_zone_bars)] = 100.0
    high, low = close + 1.0, close - 1.0
    idx = pd.date_range("2020-01-01", periods=N, freq="B")
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": 1000.0}, index=idx)


def _run(df, monkeypatch):
    monkeypatch.setattr(RE, "compute_ma", lambda close, mt, p: np.full(len(close), 100.0))
    s = MAResearchSettings(ma_types=("SMA",), ma_start=10, ma_end=10, proximity_pct=3.0, cooldown_bars=COOLDOWN,
                           fwd_windows=(PW, 10), min_interactions=1, is_pct=50, regime_ma=200, top_n=1,
                           oos_scope="all")
    res = RE.run_ma_affinity(df, s)
    inter = res.interactions
    return {p: inter[inter["period_type"] == p] for p in ("IS", "OOS")}


def _reference(df):
    ma = [100.0] * N
    hi, lo = df["high"].tolist(), df["low"].tolist()
    is_ev, iz, last = REF.events(hi, lo, ma, 0, IS_END, IS_END, PW, 3.0, COOLDOWN, False, -11)
    oos_ev, _, _ = REF.events(hi, lo, ma, IS_END + 1, N - 1, N - 1, PW, 3.0, COOLDOWN, iz, last)
    return is_ev, oos_ev


def test_an_unrecorded_boundary_entry_does_not_start_a_cooldown(monkeypatch):
    # entries (rising edges) at 10, 16, 18, 21, 24; each visit lasts one bar
    df = _frame([10, 16, 18, 21, 24])
    got = _run(df, monkeypatch)
    # IS: 10 recorded; 16 recorded (16 - 10 >= 5 and 16 + 3 = 19 reaches the IS end exactly);
    #     18 NOT recorded: 18 + 3 = 21 crosses the IS end (and it is also within the cooldown of 16)
    assert got["IS"]["bar_idx"].tolist() == [10, 16]
    # OOS: 21 recorded (21 - 16 = 5 >= cooldown from the last RECORDED IS interaction); 24 suppressed (24 - 21 = 3)
    assert got["OOS"]["bar_idx"].tolist() == [21]
    assert _reference(df) == ([10, 16], [21])
    # forward windows: the 10-bar window of bar 10 would end at 20, past the IS end -> missing, never 0
    first = got["IS"].iloc[0]
    assert first["outcome_3"] in ("Success", "Failure") and np.isnan(first["fwd_10"]) and first["outcome_10"] == "NoData"


def test_an_entry_excluded_only_for_its_window_does_not_block_the_next_oos_entry(monkeypatch):
    # 10 recorded; 17 is >= 5 bars after 10 (cooldown fine) but 17 + 3 = 20 crosses the IS end -> NOT recorded.
    # 21 is only 4 bars after 17 but 11 after the last RECORDED one (10) -> recorded in OOS.
    df = _frame([10, 17, 21])
    got = _run(df, monkeypatch)
    assert got["IS"]["bar_idx"].tolist() == [10]
    assert got["OOS"]["bar_idx"].tolist() == [21]
    assert _reference(df) == ([10], [21])


def test_price_already_in_the_zone_at_the_split_creates_no_artificial_oos_interaction(monkeypatch):
    # a visit starting at 17 (not recorded: window crosses the IS end) lasts until bar 22, across the split at 19/20;
    # bar 20 (first OOS bar) is in the zone but is NOT a new interaction; the next visit starts at 25 -> recorded.
    df = _frame([10, 17, 18, 19, 20, 21, 22, 25])
    got = _run(df, monkeypatch)
    assert got["IS"]["bar_idx"].tolist() == [10]
    assert got["OOS"]["bar_idx"].tolist() == [25]
    assert _reference(df) == ([10], [25])


def test_an_oos_entry_inside_the_carried_cooldown_is_suppressed(monkeypatch):
    # recorded IS entry at 16; OOS entry at 20 is 4 bars later (< cooldown 5) -> suppressed; 21 would be allowed,
    # but 20-21 is one visit, so the next rising edge is 26 -> recorded.
    df = _frame([16, 20, 21, 26])
    got = _run(df, monkeypatch)
    assert got["IS"]["bar_idx"].tolist() == [16]
    assert got["OOS"]["bar_idx"].tolist() == [26]
    assert _reference(df) == ([16], [26])
