"""MA Affinity V2, batch 1 (owner decisions 10-Nov-26): chance test (block shuffle, 200 shuffles by default, fixed seed)
and drift baseline (reported alongside the 50% benchmark; the score is unchanged).

- V2 keeps every V1 number: IS scores, ranks, frozen Top-N and OOS results equal QLOPB V1 on the same data.
- The fast scorer used on shuffled series gives exactly the same status and score as QLOPB's score_window.
- The block shuffle keeps every bar's own shape, the first and last close, and whole blocks of consecutive bars.
- The chance p-value and verdict follow the documented formula; a planted MA bounce stands out, a random walk does not.
- The drift baseline equals a direct count; the Q-MAP run writes the V2 tables, records the chance test in
  Run_Metadata, refuses bad V2 parameters and too few blocks, and reproduces identically.
"""

from __future__ import annotations

import csv
import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from fixtures.profiles import do_ingest
from qlopb.analysis.affinity_engine import score_window
from qlopb.analysis.interaction_engine import build_interaction_records, detect_interaction_episodes
from qlopb.config.settings import MAResearchSettings
from qlopb.core.research_engine import run_ma_affinity
from qlopb.references.moving_average import compute_ma
from qmap.analytical_engine import ANALYSES, INVALID_INPUT, MA_AFFINITY_V2, check_analysis, run_analysis
from qmap.analytical_engine import ma_affinity_v2_method as V
from qmap.analytical_engine.reproduce import reproduce_run


def random_walk(n=900, seed=3, drift=0.0):
    r = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(r.normal(drift, 0.018, n)))
    o = np.r_[c[0], c[:-1]] * np.exp(r.normal(0, 0.003, n))
    wick = np.abs(r.normal(0, 0.008, n)) * c
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + wick, "low": np.minimum(o, c) - wick, "close": c,
                         "volume": 1e6}, index=pd.bdate_range("2019-01-01", periods=n))


def bouncing(n=700, seed=1, period=20, push=0.006):
    """A random walk with a planted MA effect: after price comes within 0.5% of its 20-bar SMA it is pushed away again,
    in the direction it came from, for 5 bars."""
    r = np.random.default_rng(seed)
    c = list(100 * np.exp(np.cumsum(r.normal(0, 0.01, period))))
    boost, sign = 0, 0
    for _ in range(period, n):
        sma, prev = np.mean(c[-period:]), c[-1]
        if boost == 0 and abs(prev / sma - 1) < 0.005:
            sign, boost = (1 if c[-2] > sma else -1), 5
        c.append(prev * np.exp(r.normal(0, 0.01) + (sign * push if boost > 0 else 0)))
        boost = max(0, boost - 1)
    c = np.array(c)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.002, "low": np.minimum(o, c) * 0.998, "close": c,
                         "volume": 1.0}, index=pd.bdate_range("2020-01-01", periods=n))


PLANTED = dict(ma_start=10, ma_end=40, proximity_pct=0.5, min_interactions=5, regime_ma=20, fwd_windows=(3, 5),
               chance_shuffles=39)


# ---- V1 numbers are kept ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("types", [("SMA",), ("EMA", "WMA", "HMA", "RMA")])
def test_v2_keeps_every_v1_number(types):
    df = random_walk()
    kw = dict(ma_types=types, ma_start=10, ma_end=80, oos_scope="all")
    v1 = run_ma_affinity(df, MAResearchSettings(**kw))
    v2 = V.run_ma_affinity_v2(df, V.MAAffinityV2Settings(**kw, chance_shuffles=3))
    assert v2.frozen_top == v1.frozen_top
    for a, b in zip(v2.results, v1.results):
        for key, value in b.items():
            if key.startswith("nbr_") or key in ("is_fwd_stats", "oos_fwd_stats", "is_score_components",
                                                 "oos_score_components"):
                continue
            assert a[key] == value or (value != value and a[key] != a[key]), (a["ma_label"], key)
    pd.testing.assert_frame_equal(v2.interactions, v1.interactions)


def test_fast_scorer_and_fast_records_equal_qlopb():
    df = random_walk(seed=11)
    c, h, l = (df[k].to_numpy() for k in ("close", "high", "low"))
    s = V.MAAffinityV2Settings(ma_types=("SMA", "EMA", "HMA"), ma_start=5, ma_end=120, min_interactions=8)
    is_end = 629
    checked = 0
    for mt in s.ma_types:
        for p in range(s.ma_start, s.ma_end + 1, 3):
            ma = compute_ma(c, mt, p)
            ev, _, _ = detect_interaction_episodes(h, l, ma, 0, is_end, is_end, s.primary_window, s.proximity_pct,
                                                   s.cooldown_bars, initial_in_zone=False, last_event_bar=-(p + 1))
            full = build_interaction_records(ev, ma, mt, p, is_end, c, h, l, df.index, np.full(len(c), np.nan),
                                             list(s.fwd_windows))
            fast = V._fast_records(ev, ma, c, is_end, list(s.fwd_windows))
            assert len(full) == len(fast)
            for r, f in zip(full, fast):
                for k, v in f.items():
                    assert r[k] == v or (isinstance(v, float) and np.isnan(v) and np.isnan(r[k])), (mt, p, k)
            ref = score_window(full, s)
            status, score = V.affinity_only(fast, s)
            assert status == ref["status"]
            assert score == ref["affinity_score"] or (np.isnan(score) and np.isnan(ref["affinity_score"]))
            checked += 1
    assert checked > 100


# ---- block shuffle ------------------------------------------------------------------------------------------------
def test_block_shuffle_keeps_bar_shapes_endpoints_and_blocks():
    df = random_walk(400, seed=8)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    so, sh, sl, sc = V.block_shuffle_ohlc(o, h, l, c, 15, np.random.default_rng(4))
    assert (sh >= np.maximum(so, sc) - 1e-9).all() and (sl <= np.minimum(so, sc) + 1e-9).all()
    assert sc[0] == c[0] and sc[-1] == pytest.approx(c[-1], rel=1e-9)
    ret, sret = np.diff(np.log(c)), np.diff(np.log(sc))
    assert np.allclose(np.sort(ret), np.sort(sret))  # the same bar moves, in another order
    assert not np.allclose(ret, sret)
    # blocks of consecutive bars survive: most 15-bar runs of the shuffled moves appear in the original order
    pos = {round(x, 12): i for i, x in enumerate(ret)}
    idx = np.array([pos[round(x, 12)] for x in sret])
    assert (np.diff(idx) == 1).mean() > 0.85
    again = V.block_shuffle_ohlc(o, h, l, c, 15, np.random.default_rng(4))
    assert all(np.array_equal(a, b) for a, b in zip(again, (so, sh, sl, sc)))  # same seed -> same series


# ---- chance p-value and verdict -----------------------------------------------------------------------------------
def test_chance_summary_follows_the_documented_formula():
    tops = [50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0, np.nan]
    ch = V.chance_summary(80.0, tops, 10, 15, 1)
    assert ch["p_value"] == round((1 + 3) / 11, 4) and ch["percentile"] == 70.0  # the empty shuffle counts below
    assert ch["verdict"] == V.NOT_DISTINGUISHABLE and ch["null_max"] == 90.0
    many = [50.0] * 199
    assert V.chance_summary(80.0, many, 199, 15, 1)["p_value"] == 0.005
    assert V.chance_summary(80.0, many, 199, 15, 1)["verdict"] == V.STANDS_OUT
    assert V.chance_summary(80.0, [], 0, 15, 1)["verdict"] == V.NOT_RUN
    assert V.chance_summary(np.nan, many, 199, 15, 1)["verdict"].startswith("NO RANKED CANDIDATE")
    assert V.chance_p_for(60.0, tops, 10) == round((1 + 7) / 11, 4)


def test_a_planted_ma_bounce_stands_out_and_a_random_walk_does_not():
    planted = V.run_ma_affinity_v2(bouncing(seed=1), V.MAAffinityV2Settings(**PLANTED))
    assert planted.chance["verdict"] == V.STANDS_OUT and planted.chance["p_value"] <= 0.05
    assert all(abs(p - 20) <= 8 for _t, p in planted.frozen_top)  # it finds periods around the planted 20
    noise = V.run_ma_affinity_v2(random_walk(700, seed=21), V.MAAffinityV2Settings(**PLANTED))
    assert noise.chance["verdict"] == V.NOT_DISTINGUISHABLE
    assert any("NOT distinguishable from chance" in w for w in noise.warnings)
    leaders = noise.frozen_top_results()
    assert all(r["chance_p"] >= noise.chance["p_value"] for r in leaders)  # lower scores never look stronger
    assert all(r["chance_p"] != r["chance_p"] for r in noise.results if r["rank"] is None or r["rank"] > 5)


def test_zero_shuffles_runs_without_the_test_and_says_so():
    res = V.run_ma_affinity_v2(random_walk(500), V.MAAffinityV2Settings(ma_end=60, chance_shuffles=0))
    assert res.chance["verdict"] == V.NOT_RUN and res.chance["null_top_scores"] == []
    assert any("chance test was not run" in w for w in res.warnings)


def test_cancel_stops_the_run():
    with pytest.raises(Exception, match="cancelled"):
        V.run_ma_affinity_v2(random_walk(500), V.MAAffinityV2Settings(ma_end=60, chance_shuffles=5),
                             cancel=lambda: True)


# ---- drift baseline -----------------------------------------------------------------------------------------------
def test_baseline_rates_equal_a_direct_count():
    c = random_walk(300, seed=2)["close"].to_numpy()
    b = V._Baseline(c, 5)
    for first, last in ((0, 100), (37, 250), (200, 294)):
        idx = range(first, last + 1)
        up = sum(c[i + 5] > c[i] for i in idx) / len(idx)
        down = sum(c[i + 5] < c[i] for i in idx) / len(idx)
        assert b.rates(first, last)[:2] == pytest.approx((up, down))


def test_candidate_baseline_weights_support_and_resistance_and_does_not_change_the_score():
    df = random_walk(700, seed=5, drift=0.001)  # an up-trending stock: the Support baseline is above 50%
    res = V.run_ma_affinity_v2(df, V.MAAffinityV2Settings(ma_end=60, chance_shuffles=0))
    c = df["close"].to_numpy()
    r = res.frozen_top_results()[0]
    recs = res.interactions[(res.interactions.period_type == "IS") & (res.interactions.ma_label == r["ma_label"])]
    out = recs[recs["outcome_5"].isin(["Success", "Failure"])]
    n_sup, n_res = (out.side == "Support").sum(), (out.side == "Resistance").sum()
    ma = compute_ma(c, r["ma_type"], r["ma_period"])
    first = int(np.flatnonzero(~np.isnan(ma))[0])
    last = res.data_info["is_bars"] - 1 - 5
    up = np.mean([c[i + 5] > c[i] for i in range(first, last + 1)])
    down = np.mean([c[i + 5] < c[i] for i in range(first, last + 1)])
    assert up > 0.5
    expected = (n_sup * up + n_res * down) / (n_sup + n_res) * 100
    assert r["is_baseline_sr"] == round(expected, 2)
    assert r["is_edge_vs_baseline"] == pytest.approx(r["is_overall_sr"] - expected, abs=0.02)
    assert 0 <= r["is_p_vs_baseline"] <= 1
    v1 = run_ma_affinity(df, MAResearchSettings(ma_end=60))
    assert r["is_affinity_score"] == v1.frozen_top_results()[0]["is_affinity_score"]  # reported only


# ---- the Q-MAP analysis ------------------------------------------------------------------------------------------
SMALL = {"ma_start": "5", "ma_end": "40", "min_interactions": "5", "fwd_windows": "3,5,10", "regime_ma": "20",
         "chance_shuffles": "19"}


@pytest.fixture
def dataset(run, src):
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(600, date(2021, 1, 4)), ohlcv(600, seed=7, base=300.0))]
    res = do_ingest(run, write_delimited(src / "NSE_V2TEST.csv", HEADER, rows))
    assert res.outcome == "accepted", res.message
    return res.dataset_ids[0]


def test_v2_is_registered_next_to_v1_with_its_own_prefix():
    assert ANALYSES["ma_affinity_v2"] is MA_AFFINITY_V2 and "ma_affinity" in ANALYSES
    assert MA_AFFINITY_V2.run_prefix == "MAA2" and MA_AFFINITY_V2.requirement.timeframes == ("1D", "1W", "1M")
    defaults = {p.key: p.default for p in MA_AFFINITY_V2.parameters}
    assert (defaults["chance_shuffles"], defaults["chance_block"], defaults["chance_seed"]) == ("200", "15", "1")
    assert defaults["ma_start"] == "10" and defaults["proximity_pct"] == "3.0"  # V1 defaults unchanged


def test_v2_run_writes_its_tables_and_records_the_chance_test(settings, db, dataset):
    res = run_analysis(settings, db, MA_AFFINITY_V2, [dataset], SMALL)
    assert res.ok, res.message
    assert res.run_id.startswith("MAA2_")
    names = [p.name for p in res.outputs]
    for prefix in ("MA_Affinity_V2_Candidates_", "MA_Affinity_V2_Interactions_", "MA_Affinity_V2_Chance_Shuffles_",
                   "MA_Affinity_V2_Findings_", "MA_Affinity_V2_Report_", "chance_test_distribution_"):
        assert sum(n.startswith(prefix) for n in names) == 1, prefix
    meta = json.loads(res.metadata_path.read_text(encoding="utf-8"))
    ch = meta["analysis_details"]["chance_test"]
    assert ch["shuffles"] == 19 and ch["block_bars"] == 15 and ch["seed"] == 1
    assert ch["verdict"] in (V.STANDS_OUT, V.NOT_DISTINGUISHABLE)
    shuffles = next(res.run_dir.glob("MA_Affinity_V2_Chance_Shuffles_*.csv"))
    assert len(list(csv.DictReader(shuffles.open(encoding="utf-8")))) == 19
    cand = list(csv.DictReader(next(res.run_dir.glob("MA_Affinity_V2_Candidates_*.csv")).open(encoding="utf-8")))
    assert {"chance_p", "is_baseline_sr", "is_edge_vs_baseline", "oos_baseline_sr"} <= set(cand[0])
    findings = next(res.run_dir.glob("MA_Affinity_V2_Findings_*.txt")).read_text(encoding="utf-8")
    assert "VERDICT: " + ch["verdict"] in findings and "baseline" in findings
    import openpyxl

    wb = openpyxl.load_workbook(next(res.run_dir.glob("MA_Affinity_V2_*.xlsx")), read_only=True)
    assert {"Summary", "Top_N", "Rankings", "Chance_Test", "Interactions", "Settings"} <= set(wb.sheetnames)


def test_v2_parameter_problems_and_too_few_blocks_are_refused(settings, db, dataset):
    bad = check_analysis(settings, db, MA_AFFINITY_V2, [dataset], {**SMALL, "chance_block": "x"})
    assert bad.state == INVALID_INPUT and any("Chance block bars" in p for p in bad.input_problems)
    bad = check_analysis(settings, db, MA_AFFINITY_V2, [dataset], {**SMALL, "chance_shuffles": "-1"})
    assert bad.state == INVALID_INPUT
    few = check_analysis(settings, db, MA_AFFINITY_V2, [dataset], {**SMALL, "chance_block": "120"})
    fail = next(f for r in few.reports for f in r.failures if f.name == "ma_affinity_v2_chance")
    assert "too few to shuffle" in fail.detail
    zero = check_analysis(settings, db, MA_AFFINITY_V2, [dataset], {**SMALL, "chance_shuffles": "0"})
    assert zero.ready and any("chance test will not be run" in w for w in zero.warnings)


def test_v2_run_reproduces_identically(settings, db, dataset):
    first = run_analysis(settings, db, MA_AFFINITY_V2, [dataset], SMALL)
    again = reproduce_run(settings, db, first.run_id)
    assert again.ok and again.reproduction["identical"], again.message
