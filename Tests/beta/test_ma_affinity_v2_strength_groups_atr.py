"""MA Affinity V2, batch 2 (owner decision 10-Nov-26: rescale interaction strength; recommendations: group
neighbouring periods into one finding, optional ATR zone).

- Strength reference: never stricter than V1; the median of the same MA type within +/-20% (at least +/-2) periods;
  "v1" keeps the V1 number. On random walks long MAs are no longer marked down for their length.
- Grouping: going down the ranking, same-type candidates within Group % of a leader join its group; the frozen Top-N
  are the leaders of distinct findings; 0 = the V1 Top-N.
- ATR zone: Wilder's ATR equals a direct calculation; the ATR detector with a percentage half-width finds the same
  interactions as V1's detector; an ATR run works end to end, including the chance test.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from fixtures.profiles import do_ingest
from qlopb.analysis.interaction_engine import detect_interaction_episodes
from qlopb.references.moving_average import compute_ma
from qmap.analytical_engine import INVALID_INPUT, MA_AFFINITY_V2, check_analysis, run_analysis
from qmap.analytical_engine import ma_affinity_v2_method as V

from beta.test_ma_affinity_v2_chance_and_baseline import SMALL, random_walk


# ---- interaction strength ------------------------------------------------------------------------------------------
def test_strength_reference_is_the_nearby_median_capped_at_v1():
    s = V.MAAffinityV2Settings(min_interactions=10)  # V1 reference max(30, 20) = 30
    counts = {("SMA", p): n for p, n in zip(range(10, 21), [60, 58, 55, 50, 40, 12, 14, 16, 18, 20, 22])}
    counts[("EMA", 15)] = 2
    refs = V.strength_references(counts, s)
    # SMA-15: neighbours within max(2, 3) = 3 periods: 12..18 -> counts 55, 50, 40, 12, 14, 16, 18 -> median 18
    assert refs[("SMA", 15)] == 18.0
    assert refs[("SMA", 10)] == 30.0  # median 58 is above V1's 30: never stricter than V1
    assert refs[("EMA", 15)] == 2.0  # other MA types are not mixed in
    assert all(v <= 30 for v in refs.values())
    v1 = V.strength_references(counts, V.MAAffinityV2Settings(min_interactions=10, strength_rule="v1"))
    assert set(v1.values()) == {30.0}
    assert V.strength(15, s, 18.0) == pytest.approx(15 / 18) and V.strength(40, s, 18.0) == 1.0
    assert V.strength(15, s, None) == 0.5  # None = the V1 rule


def test_long_mas_are_no_longer_marked_down_for_their_length():
    long_v1, long_rel = [], []
    for seed in (101, 102, 103):
        df = random_walk(1500, seed=seed)
        for rule, bucket in (("v1", long_v1), ("relative", long_rel)):
            res = V.run_ma_affinity_v2(df, V.MAAffinityV2Settings(chance_shuffles=0, strength_rule=rule, group_pct=0))
            bucket += [r["is_score_components"]["interaction_strength"] for r in res.results
                       if r["ma_period"] > 150 and r["is_status"] == "OK"]
    assert np.mean(long_v1) < 90 and np.mean(long_rel) > 95


def test_oos_reference_is_scaled_to_the_shorter_out_of_sample_part():
    res = V.run_ma_affinity_v2(random_walk(900, seed=4), V.MAAffinityV2Settings(ma_end=60, chance_shuffles=0))
    r = res.frozen_top_results()[0]
    assert r["oos_strength_reference"] < r["is_strength_reference"]


# ---- grouping ----------------------------------------------------------------------------------------------------
def _ranked(*labels):
    return [{"ma_type": t, "ma_period": p, "rank": k} for k, (t, p) in enumerate(labels, 1)]


def test_neighbours_join_the_group_of_a_higher_ranked_leader():
    rows = _ranked(("SMA", 40), ("SMA", 43), ("EMA", 41), ("SMA", 37), ("SMA", 36), ("SMA", 100), ("SMA", 108))
    groups = V.group_neighbours(rows, V.MAAffinityV2Settings(group_pct=10))
    labels = [[(r["ma_type"], r["ma_period"]) for r in g] for g in groups]
    # width for SMA-40 is ceil(4.0) = 4: 43, 37 and 36 join; EMA-41 is another type; 108 is within 10 of SMA-100
    assert labels == [[("SMA", 40), ("SMA", 43), ("SMA", 37), ("SMA", 36)], [("EMA", 41)],
                      [("SMA", 100), ("SMA", 108)]]
    assert len(V.group_neighbours(rows, V.MAAffinityV2Settings(group_pct=0))) == len(rows)


def test_the_frozen_top_n_are_distinct_findings_with_their_members():
    df = random_walk(1200, seed=9)
    grouped = V.run_ma_affinity_v2(df, V.MAAffinityV2Settings(ma_types=("SMA", "EMA"), chance_shuffles=0))
    plain = V.run_ma_affinity_v2(df, V.MAAffinityV2Settings(ma_types=("SMA", "EMA"), chance_shuffles=0, group_pct=0))
    top = grouped.frozen_top_results()
    assert [r["finding"] for r in top] == list(range(1, len(top) + 1))
    for a in top:
        for b in top:
            if a is not b and a["ma_type"] == b["ma_type"]:
                assert abs(a["ma_period"] - b["ma_period"]) > max(1, np.ceil(a["ma_period"] * 0.1)) or \
                    abs(a["ma_period"] - b["ma_period"]) > max(1, np.ceil(b["ma_period"] * 0.1))
    assert top[0]["ma_label"] == plain.frozen_top_results()[0]["ma_label"]  # #1 is the same either way
    members = sum(r["group_size"] for r in top)
    assert members >= len(top) and top[0]["group_members"].startswith(top[0]["ma_label"])
    assert [r["rank"] for r in plain.frozen_top_results()] == [1, 2, 3, 4, 5]


# ---- ATR zone ----------------------------------------------------------------------------------------------------
def test_wilder_atr_equals_a_direct_calculation():
    df = random_walk(60, seed=1)
    h, l, c = (df[k].to_numpy() for k in ("high", "low", "close"))
    atr = V.atr_wilder(h, l, c, 14)
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, 60)]
    expect = [np.nan] * 13 + [np.mean(tr[:14])]
    for i in range(14, 60):
        expect.append((expect[-1] * 13 + tr[i]) / 14)
    assert np.isnan(atr[:13]).all() and np.allclose(atr[13:], expect[13:])


def test_the_general_detector_finds_v1_interactions_with_a_percentage_zone():
    df = random_walk(800, seed=6)
    h, l, c = (df[k].to_numpy() for k in ("high", "low", "close"))
    for mt, p in (("SMA", 20), ("EMA", 50), ("HMA", 30), ("RMA", 100)):
        ma = compute_ma(c, mt, p)
        ref = detect_interaction_episodes(h, l, ma, 0, 559, 559, 5, 3.0, 5, last_event_bar=-(p + 1))
        new = V.detect_entries(h, l, ma, ma * 0.03, 0, 559, 559, 5, 5, last_event_bar=-(p + 1))
        assert new == ref
        state = ref[1:]
        assert V.detect_entries(h, l, ma, ma * 0.03, 560, 799, 799, 5, 5, *state) == \
            detect_interaction_episodes(h, l, ma, 560, 799, 799, 5, 3.0, 5, *state)


def test_an_atr_zone_run_works_end_to_end_and_differs_from_the_percent_zone():
    df = random_walk(700, seed=12)
    kw = dict(ma_end=60, chance_shuffles=9)
    atr = V.run_ma_affinity_v2(df, V.MAAffinityV2Settings(**kw, zone_mode="atr", atr_multiple=0.5))
    pct = V.run_ma_affinity_v2(df, V.MAAffinityV2Settings(**kw))
    assert len(atr.interactions) != len(pct.interactions)
    assert len(atr.chance["null_top_scores"]) == 9 and atr.frozen_top


# ---- Workbench parameters ---------------------------------------------------------------------------------------
@pytest.fixture
def dataset(run, src):
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(600, date(2021, 1, 4)), ohlcv(600, seed=7, base=300.0))]
    return do_ingest(run, write_delimited(src / "NSE_V2B.csv", HEADER, rows)).dataset_ids[0]


@pytest.mark.parametrize("key,value,needle", [("zone_mode", "band", "Zone mode"), ("strength_rule", "x", "Strength rule"),
                                              ("group_pct", "ten", "Group %"), ("atr_multiple", "0", "ATR multiple"),
                                              ("atr_period", "1.5", "ATR period")])
def test_bad_batch_2_parameters_are_explained(settings, db, dataset, key, value, needle):
    res = check_analysis(settings, db, MA_AFFINITY_V2, [dataset], {**SMALL, key: value})
    assert res.state == INVALID_INPUT and any(needle in p for p in res.input_problems), res.input_problems


def test_atr_and_grouping_options_reach_the_run_and_its_record(settings, db, dataset):
    res = run_analysis(settings, db, MA_AFFINITY_V2, [dataset],
                       {**SMALL, "zone_mode": "ATR", "atr_multiple": "0.75", "group_pct": "15"})
    assert res.ok, res.message
    import json

    s = json.loads(res.metadata_path.read_text(encoding="utf-8"))["parameters"]["v2_settings"]
    assert (s["zone_mode"], s["atr_multiple"], s["group_pct"], s["strength_rule"]) == ("atr", 0.75, 15.0, "relative")
    findings = next(res.run_dir.glob("MA_Affinity_V2_Findings_*.txt")).read_text(encoding="utf-8")
    assert "0.75 x ATR(14)" in findings and "grouped within 15%" in findings
