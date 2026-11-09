"""Beta numerical validation (T4, 09-Nov-26): the MA Affinity engine agrees with an INDEPENDENT reference
implementation (Tests/beta/ma_affinity_reference.py: plain-Python loops written from the method definitions) on every
candidate and every interaction. Counts, statuses, sides, outcomes, ranks and the frozen Top-N must be identical;
numbers must agree to 1e-9 (relative), or, where the engine reports a value rounded to 2 or 4 decimals, to that
rounding (half a unit in the last place, plus 1e-9)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "qlopb"))
import _qlopb_helpers as H  # noqa: E402  (sets the qlopb path; synthetic data)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ma_affinity_reference as REF  # noqa: E402

from qlopb.config.settings import MAResearchSettings  # noqa: E402
from qlopb.core.research_engine import run_ma_affinity  # noqa: E402

CASES = {
    # name: (data kwargs, settings kwargs)
    "all_ma_types_trending": (dict(n=700, seed=11, drift=0.0006, vol=0.011),
                              dict(ma_types=("SMA", "EMA", "WMA", "HMA", "RMA"), ma_start=5, ma_end=40,
                                   fwd_windows=(5, 10, 20), min_interactions=5, regime_ma=50, top_n=5)),
    "choppy_tight_zone": (dict(n=500, seed=3, drift=0.0, vol=0.015),
                          dict(ma_types=("SMA", "EMA", "HMA"), ma_start=8, ma_end=30, proximity_pct=1.0,
                               cooldown_bars=3, fwd_windows=(3, 7), min_interactions=8, is_pct=60, regime_ma=100,
                               top_n=7, oos_scope="top_n")),
    "unequal_weights_default_windows": (dict(n=900, seed=29, drift=-0.0002, vol=0.009),
                                        dict(ma_types=("WMA", "RMA"), ma_start=20, ma_end=60, min_interactions=6,
                                             regime_ma=200, weight_interaction_strength=1, weight_success_rate=3,
                                             weight_forward_return=0.5, weight_stability=2)),
}


def _close(a, b, digits=None):
    if a is None or (isinstance(a, float) and math.isnan(a)):
        return b is None or (isinstance(b, float) and math.isnan(b))
    if b is None or (isinstance(b, float) and math.isnan(b)):
        return False
    if digits is None:
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return abs(round(a, digits) - b) <= 0.5 * 10 ** -digits + 1e-9 or abs(a - b) <= 0.5 * 10 ** -digits + 1e-9


def _pct(x):
    return None if x is None else x * 100


def _run_both(data_kw, set_kw):
    df = H.synthetic_ohlc(**data_kw)
    s = MAResearchSettings(**set_kw)
    eng = run_ma_affinity(df, s)
    ref = REF.run(df["close"].tolist(), df["high"].tolist(), df["low"].tolist(), ma_types=s.ma_types,
                  ma_start=s.ma_start, ma_end=s.ma_end, proximity_pct=s.proximity_pct, cooldown_bars=s.cooldown_bars,
                  fwd_windows=tuple(s.fwd_windows), min_interactions=s.min_interactions, is_pct=s.is_pct,
                  regime_ma=s.regime_ma, top_n=s.top_n, weights=s.weights,
                  min_oos=s.min_oos_outcomes_for_consistency)
    return df, s, eng, ref


@pytest.mark.parametrize("case", list(CASES))
def test_every_candidate_agrees_with_the_independent_reference(case):
    df, s, eng, ref = _run_both(*CASES[case])
    rows = {(r["ma_type"], r["ma_period"]): r for r in eng.results}
    assert set(rows) == set(ref["candidates"]), "the same candidates are tested"
    assert [tuple(k) for k in eng.frozen_top] == ref["frozen"], "the frozen Top-N is identical"
    n_ok = 0
    for key, rc in ref["candidates"].items():
        r, i = rows[key], rc["is"]
        assert r["is_status"] == i["status"], key
        assert r["rank"] == rc.get("rank"), key
        if i["status"] == "NO_INTERACTIONS":
            assert r["is_n"] == 0 and math.isnan(r["is_affinity_score"]), key
            continue
        n_ok += i["status"] == "OK"
        for f in ("n", "n_support", "n_resistance", "n_outcomes"):
            assert r[f"is_{f}"] == i[f], (key, f)
        assert _close(_pct(i["sr"]), r["is_overall_sr"], 2), key
        assert _close(_pct(i["support_sr"]), r["is_support_sr"], 2), key
        assert _close(_pct(i["resistance_sr"]), r["is_resistance_sr"], 2), key
        assert _close(_pct(i["stability"]), r["is_stability"], 2), key
        assert _close(i["affinity"], r["is_affinity_score"], 2), key
        assert _close(i["reliability"], r["is_reliability"], 2), key
        assert _close(i["p_value"], r["is_p_value"], 4), key
        comp = r["is_score_components"]
        for a, b in (("interaction_strength", "interaction_strength"), ("success_rate", "success_rate"),
                     ("forward_return", "forward_return_directed_ir"), ("stability", "stability")):
            assert _close(i["components"][a] * 100, comp[b], 2), (key, a)
        for w, st in i["fwd"].items():
            e = r["is_fwd_stats"][w]
            assert e["n"] == st["n"], (key, w)
            for f in ("mean", "median", "std", "hit_rate"):
                assert _close(st[f], e[f]), (key, w, f)
    assert n_ok >= s.top_n, "the case must exercise ranking (enough OK candidates)"
    for key in ref["frozen"]:
        r, o = rows[key], ref["candidates"][key]["oos"]
        assert r["oos_status"] == o["status"] and r["oos_n"] == o["n"], key
        if o["status"] != "NO_INTERACTIONS":
            assert r["oos_n_outcomes"] == o["n_outcomes"], key
            assert _close(_pct(o["sr"]), r["oos_overall_sr"], 2), key
            assert _close(o["affinity"], r["oos_affinity_score"], 2), key
        status, raw = ref["candidates"][key]["consistency"]
        assert r["is_oos_consistency_status"] == status, key
        assert _close(raw, r["is_oos_consistency_raw"]), key
    for key, r in rows.items():
        if key not in ref["frozen"]:
            assert r["oos_status"] == "NOT_EVALUATED", key  # OOS is evaluated for the frozen Top-N only


@pytest.mark.parametrize("case", list(CASES))
def test_every_interaction_agrees_with_the_independent_reference(case):
    df, s, eng, ref = _run_both(*CASES[case])
    got = eng.interactions.to_dict("records")
    assert len(got) == len(ref["interactions"]) > 50
    key = lambda r: (r["period_type"], r["ma_type"], r["ma_period"], r["bar_idx"])  # noqa: E731
    got = sorted(got, key=key)
    want = sorted(ref["interactions"], key=key)
    for g, w in zip(got, want):
        assert key(g) == key(w)
        assert (g["side"], g["ma_slope"], g["regime"]) == (w["side"], w["ma_slope"], w["regime"]), key(g)
        assert _close(w["ma_value"], g["ma_value"], 4), key(g)
        for fw in s.fwd_windows:
            gv = g[f"fwd_{fw}"]
            assert _close(w[f"fwd_{fw}"], None if (isinstance(gv, float) and np.isnan(gv)) else gv), (key(g), fw)
            assert g[f"outcome_{fw}"] == w[f"outcome_{fw}"], (key(g), fw)


def test_the_reference_itself_on_hand_worked_values():
    """Known answers worked out by hand, so the reference is not only checked against the engine."""
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert REF.sma(x, 3)[2:] == [2.0, 3.0, 4.0, 5.0]
    assert [round(v, 6) for v in REF.wma(x, 3)[2:]] == [2.333333, 3.333333, 4.333333, 5.333333]  # (1+4+9)/6 ...
    assert REF.ema(x, 3)[2:] == [2.0, 3.0, 4.0, 5.0]  # a straight line: EMA lags by exactly (n-1)/2
    assert [round(v, 4) for v in REF.rma(x, 3)[2:]] == [2.0, 2.6667, 3.4444, 4.2963]
    assert REF.hma([1.0, 2, 3, 4, 5, 6, 7, 8], 4)[4:] == [5.0, 6.0, 7.0, 8.0]  # Hull MA of a straight line = the line
    assert REF.p_value(5, 5) == 1 / 32 and REF.p_value(0, 6) == 1.0
    assert round(REF.wilson_lower(8, 10), 4) == 0.4902


# ---- edge rules that random prices never reach (found by mutation testing of the reference, 09-Nov-26) ---------------
def test_edge_rules_zero_return_neutral_side_and_zero_spread_match_the_reference():
    """Crafted values, exact in binary floating point:
      * a forward return of exactly 0 is a Failure for Support and Resistance;
      * previous close equal to the MA is Neutral, with no outcome;
      * identical directed returns (spread 0) use a spread of 1, so the forward-return component is mean + 0.5."""
    from qlopb.analysis.affinity_engine import score_window
    from qlopb.analysis.interaction_engine import build_interaction_records

    close = [8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0]
    ma = [8.0, 4.0, 8.0, 8.0, 8.0, 16.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0]  # bar 1 below, bar 3 equal, bar 5 above
    idx = H.synthetic_ohlc(n=12).index
    regime = [None] * 12
    for bar, side in ((1, "Support"), (5, "Resistance"), (3, "Neutral")):
        eng = build_interaction_records([bar], np.array(ma), "SMA", 3, 11, np.array(close), np.array(close),
                                        np.array(close), idx, np.full(12, np.nan), [2])[0]
        ref = REF.record(bar, ma, close, 11, [2], regime)
        assert eng["side"] == ref["side"] == side
        assert eng["fwd_2"] == ref["fwd_2"] == 0.0
        assert eng["outcome_2"] == ref["outcome_2"] == ("Neutral" if side == "Neutral" else "Failure")

    # 4 Support interactions, each +0.25 % (exact), and 1 Resistance at -0.25 %: directed returns all +0.25, spread 0
    recs = [{"side": "Support", "fwd_5": 0.25, "outcome_5": "Success"} for _ in range(4)] + \
           [{"side": "Resistance", "fwd_5": -0.25, "outcome_5": "Success"}]
    s = MAResearchSettings(fwd_windows=(5,), min_interactions=3)
    eng = score_window(recs, s)
    ref = REF.score(recs, (5,), 3, s.weights)
    assert ref["components"]["forward_return"] == 0.75  # 0.25 / 1 + 0.5
    assert eng["score_components"]["forward_return_directed_ir"] == 75.0
    assert _close(ref["affinity"], eng["affinity_score"], 2)
