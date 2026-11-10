"""MA Affinity V2 release-candidate review (10-Nov-26): the safeguards the consolidated instruction asks for, beyond
the merge package's own tests.

- Block shuffle: every shuffled series is a valid OHLC history (finite, positive, low <= open/close <= high), for many
  seeds and block lengths; with MA warm-up the bars before the analysis period are kept exactly.
- The FULL candidate scan is repeated on every shuffle (every candidate, every shuffle).
- The fast scorer equals score_window also with the relative strength reference V2 uses.
- MA warm-up: with earlier history the MAs use it, but no interaction, outcome, baseline bar or split is counted
  before the analysis start; without it V2 is exactly as before; insufficient warm-up is reported in readiness.
- No look-ahead: changing out-of-sample prices changes no in-sample result, rank, frozen Top-N or chance-test number.
- The Executive interpretation answers its eight questions with numbers taken from the results, and never claims more
  than the verdict allows.
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from fixtures.profiles import do_ingest
from qlopb.analysis.interaction_engine import build_interaction_records
from qlopb.references.moving_average import compute_ma
from qlopb.validation.is_oos import compute_split
from qmap.analytical_engine import MA_AFFINITY_V2, check_analysis, run_analysis
from qmap.analytical_engine import ma_affinity_v2 as A
from qmap.analytical_engine import ma_affinity_v2_method as V

from beta.test_ma_affinity_v2_chance_and_baseline import bouncing, random_walk

SET = dict(ma_types=("SMA", "EMA"), ma_start=10, ma_end=60, min_interactions=5, regime_ma=20, fwd_windows=(3, 5))


# ---- block shuffle validity --------------------------------------------------------------------------------------
@pytest.mark.parametrize("block", [2, 5, 15, 40])
def test_every_shuffled_series_is_a_valid_ohlc_history(block):
    df = random_walk(500, seed=21)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    rng = np.random.default_rng(99)
    for _ in range(25):
        so, sh, sl, sc = V.block_shuffle_ohlc(o, h, l, c, block, rng)
        for x in (so, sh, sl, sc):
            assert np.isfinite(x).all() and (x > 0).all()
        assert (sl <= np.minimum(so, sc) * (1 + 1e-12)).all() and (sh >= np.maximum(so, sc) * (1 - 1e-12)).all()
        assert sc[-1] == pytest.approx(c[-1], rel=1e-9) and sc[0] == c[0]
        # every bar keeps its own shape: the multiset of body and wick ratios is unchanged
        body, sbody = np.sort(c[1:] / o[1:]), np.sort(sc[1:] / so[1:])
        assert np.allclose(body, sbody, rtol=1e-9)


def test_the_full_candidate_scan_is_repeated_on_every_shuffle(monkeypatch):
    seen = []
    real = V._is_top_score

    def spy(o, h, l, c, s, candidates, is_end, start=0):
        seen.append((len(candidates), len(c), start))
        return real(o, h, l, c, s, candidates, is_end, start)

    monkeypatch.setattr(V, "_is_top_score", spy)
    s = V.MAAffinityV2Settings(**SET, chance_shuffles=7)
    res = V.run_ma_affinity_v2(random_walk(700, seed=5), s)
    assert len(seen) == 7 and all(n == s.n_candidates for n, _, _ in seen)
    assert len(res.chance["null_top_scores"]) == 7


def test_fast_scorer_equals_score_window_with_the_relative_reference():
    df = random_walk(seed=31)
    c, h, l = (df[k].to_numpy() for k in ("close", "high", "low"))
    s = V.MAAffinityV2Settings(**SET)
    zone = V._Zone(s, h, l, c)
    for mt in s.ma_types:
        for p in range(s.ma_start, s.ma_end + 1, 5):
            ma = compute_ma(c, mt, p)
            ev, _, _ = zone.detect(ma, 0, 600, 600, False, -(p + 1))
            full = build_interaction_records(ev, ma, mt, p, 600, c, h, l, df.index, np.full(len(c), np.nan),
                                             list(s.fwd_windows))
            fast = V._fast_records(ev, ma, c, 600, list(s.fwd_windows))
            for ref in (7.0, 12.5, 30.0):
                sc = V.score_v2(full, s, ref)
                status, score = V.affinity_only(fast, s, ref)
                if sc["status"] == "NO_INTERACTIONS":
                    assert status == "NO_INTERACTIONS"
                    continue
                assert status == sc["status"] and score == sc["affinity_score"], (mt, p, ref)


# ---- MA warm-up --------------------------------------------------------------------------------------------------
def test_without_earlier_history_v2_is_unchanged():
    df = random_walk(600, seed=12)
    s = V.MAAffinityV2Settings(**SET, chance_shuffles=5)
    a = V.run_ma_affinity_v2(df, s)
    b = V.run_ma_affinity_v2(df, s, analysis_start=0)
    assert a.frozen_top == b.frozen_top and a.chance["null_top_scores"] == b.chance["null_top_scores"]
    pd.testing.assert_frame_equal(a.interactions, b.interactions)


def test_warm_up_uses_earlier_bars_for_the_mas_only():
    df = random_walk(900, seed=14)
    start = 250
    s = V.MAAffinityV2Settings(**SET, chance_shuffles=5)
    res = V.run_ma_affinity_v2(df, s, analysis_start=start)
    di = res.data_info
    n = len(df) - start
    is_end, oos_start = compute_split(n, s.is_pct)
    assert di["warmup_bars"] == start and di["n_bars"] == n and di["is_bars"] == is_end + 1
    assert di["oos_bars"] == n - oos_start and di["first"] == V._stamp(df.index[start])
    inter = res.interactions
    assert not inter.empty and (inter["bar_idx"] >= start).all()  # nothing counted before the analysis start
    # the MA at each recorded interaction is the MA of the FULL history (it did not restart at the start date)
    c = df["close"].to_numpy()
    for mt in ("EMA", "SMA"):
        ma_full = compute_ma(c, mt, 60)
        recs = inter[(inter["ma_type"] == mt) & (inter["ma_period"] == 60)]
        assert len(recs)
        for _, r in recs.iterrows():
            assert r["ma_value"] == pytest.approx(round(float(ma_full[int(r["bar_idx"])]), 4))
    # the same analysis period without warm-up (V1 behaviour) differs for a long EMA, as expected
    cut = V.run_ma_affinity_v2(df.iloc[start:], s)
    assert cut.data_info["is_bars"] == di["is_bars"] and cut.data_info["first"] == di["first"]
    by = lambda r: {x["ma_label"]: x for x in r.results}  # noqa: E731
    assert by(res)["EMA-60"]["is_n"] >= by(cut)["EMA-60"]["is_n"]


def test_warm_up_bars_stay_real_in_the_chance_test(monkeypatch):
    df = random_walk(800, seed=15)
    start = 200
    got = []
    real = V._is_top_score

    def spy(o, h, l, c, s, candidates, is_end, a=0):
        got.append((c.copy(), a))
        return real(o, h, l, c, s, candidates, is_end, a)

    monkeypatch.setattr(V, "_is_top_score", spy)
    V.run_ma_affinity_v2(df, V.MAAffinityV2Settings(**SET, chance_shuffles=3), analysis_start=start)
    c = df["close"].to_numpy()
    for sc, a in got:
        assert a == start and np.array_equal(sc[:start], c[:start])  # warm-up untouched (anchor bar included)
        assert not np.allclose(sc[start:start + 100], c[start:start + 100])  # in-sample bars shuffled


# ---- no look-ahead -----------------------------------------------------------------------------------------------
def test_out_of_sample_prices_change_no_in_sample_result_and_no_chance_number():
    df = random_walk(700, seed=17)
    s = V.MAAffinityV2Settings(**SET, chance_shuffles=9)
    is_end, oos_start = compute_split(len(df), s.is_pct)
    other = df.copy()
    k = other.index[oos_start:]
    other.loc[k, ["open", "high", "low", "close"]] *= np.linspace(1.0, 1.6, len(k))[:, None]
    a, b = V.run_ma_affinity_v2(df, s), V.run_ma_affinity_v2(other, s)
    assert a.frozen_top == b.frozen_top and a.chance == b.chance
    for x, y in zip(a.results, b.results):
        for key in x:
            if key.startswith("is_") and not key.startswith("is_oos"):
                assert x[key] == y[key] or (x[key] != x[key] and y[key] != y[key]), (x["ma_label"], key)
        assert x["rank"] == y["rank"]


# ---- executive interpretation ------------------------------------------------------------------------------------
@pytest.mark.parametrize("make,shuffles", [(lambda: bouncing(), 39), (lambda: random_walk(700, seed=3), 19),
                                           (lambda: random_walk(700, seed=3), 0)])
def test_the_executive_interpretation_uses_the_calculated_numbers(make, shuffles):
    s = V.MAAffinityV2Settings(ma_types=("SMA",), ma_start=10, ma_end=40, proximity_pct=0.5, min_interactions=5,
                               regime_ma=20, fwd_windows=(3, 5), chance_shuffles=shuffles)
    res = V.run_ma_affinity_v2(make(), s)
    parts = A.executive_interpretation("NSE:TEST Daily", res)
    assert [h.split(".")[0] for h, _ in parts] == [str(i) for i in range(1, 9)]
    text = " ".join(t for _, t in parts)
    top, ch = res.frozen_top_results()[0], res.chance
    assert top["ma_label"] in text and A._num(top["is_affinity_score"]) in text
    assert A._num(top["is_overall_sr"]) in text and A._num(top["is_baseline_sr"]) in text
    assert A._num(top["is_edge_vs_baseline"]) in text
    assert "not a probability or a forecast" in text and "provisional" in text
    if ch["verdict"] == V.STANDS_OUT:
        assert "not proof of a profitable or lasting edge" in text and A._num(ch["p_value"], "{:.4f}") in text
    elif ch["verdict"] == V.NOT_DISTINGUISHABLE:
        assert "treated as unproven" in text and "do not rely on this ranking" in text.lower()
    else:
        assert "chance test was not run" in text and "Chance shuffles above 0" in text
    if shuffles:
        assert f"{1 / (shuffles + 1):.4f}" in text  # the p-value resolution is stated


def test_no_ranked_candidate_is_explained_as_insufficient_data():
    s = V.MAAffinityV2Settings(ma_types=("SMA",), ma_start=10, ma_end=12, min_interactions=500, chance_shuffles=3)
    res = V.run_ma_affinity_v2(random_walk(400, seed=2), s)
    text = " ".join(t for _, t in A.executive_interpretation("X", res))
    assert "nothing was ranked" in text and "not poor results" in text


# ---- the Workbench analysis: warm-up readiness and record -----------------------------------------------------
SMALL = {"ma_start": "5", "ma_end": "40", "min_interactions": "5", "fwd_windows": "3,5,10", "regime_ma": "20",
         "chance_shuffles": "9"}


@pytest.fixture
def dataset(run, src):
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(700, date(2021, 1, 4)), ohlcv(700, seed=9, base=250.0))]
    res = do_ingest(run, write_delimited(src / "NSE_V2WARM.csv", HEADER, rows))
    assert res.outcome == "accepted", res.message
    return res.dataset_ids[0]


def _line(rd, name):
    return next(f for r in rd.reports for f in r.items if f.name == name)


def test_warm_up_readiness_and_run_record(settings, db, dataset):
    start = date(2021, 6, 1)  # about 105 weekdays of earlier history
    params = {**SMALL, "date_from": "01-Jun-21"}
    ready = check_analysis(settings, db, MA_AFFINITY_V2, [dataset], params)
    assert ready.ready, ready.problems
    line = _line(ready, "ma_affinity_v2_warmup")
    assert line.status == "pass" and "used to calculate the moving averages" in line.detail
    res = run_analysis(settings, db, MA_AFFINITY_V2, [dataset], params)
    assert res.ok, res.message
    meta = json.loads(res.metadata_path.read_text(encoding="utf-8"))
    w = meta["analysis_details"]["ma_warmup"]
    assert w["rule"] == "earlier" and w["bars_before_start"] > 100
    assert meta["analysis_details"]["bars_used"]["first"] >= start.isoformat()
    findings = next(res.run_dir.glob("MA_Affinity_V2_Findings_*.txt")).read_text(encoding="utf-8")
    assert findings.index("EXECUTIVE INTERPRETATION") < findings.index("DETAILED FINDINGS")
    assert "earlier bar(s)" in findings
    # 'none' is the V1 behaviour and says so; too little earlier history is a warning, not a failure
    none = check_analysis(settings, db, MA_AFFINITY_V2, [dataset], {**params, "ma_warmup": "none"})
    assert none.ready and _line(none, "ma_affinity_v2_warmup").status == "warn"
    short = check_analysis(settings, db, MA_AFFINITY_V2, [dataset],
                           {**SMALL, "date_from": "20-Jan-21"})
    assert short.ready and "only" in _line(short, "ma_affinity_v2_warmup").detail
    bad = check_analysis(settings, db, MA_AFFINITY_V2, [dataset], {**params, "ma_warmup": "x"})
    assert not bad.ready and any("MA warm-up" in p for p in bad.input_problems)


def test_without_a_start_date_or_with_none_the_frame_is_v1s(settings, db, dataset):
    from qmap.analytical_engine import ma_affinity as v1

    s = V.MAAffinityV2Settings(ma_warmup="none")
    p = {"date_from": date(2021, 6, 1), "date_to": None}
    frame, _, a = A._frame_with_warmup(settings, db, dataset, p, s)
    ref, _ = v1._frame(settings, db, dataset, p)
    assert a == 0 and frame.equals(ref)
    frame, _, a = A._frame_with_warmup(settings, db, dataset, {"date_from": None, "date_to": None},
                                       V.MAAffinityV2Settings())
    assert a == 0 and frame.equals(v1._frame(settings, db, dataset, {})[0])
