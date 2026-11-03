import unittest

import numpy as np

import _qlopb_helpers as _helpers
from qlopb.analysis.interaction_engine import detect_interaction_episodes
from qlopb.config.settings import MAResearchSettings
from qlopb.core.research_engine import run_ma_affinity
from qlopb.validation.is_oos import compute_split, consistency, forward_window_fits, freeze_top_n, rank_candidates
from qlopb.validation.statistical_tests import binomial_pvalue_greater, reliability_score, wilson_lower_bound


class Split(unittest.TestCase):
    def test_split_rule(self):
        self.assertEqual(compute_split(100, 70), (69, 70))
        self.assertEqual(compute_split(2812, 70), (1967, 1968))
        self.assertEqual(compute_split(228, 70), (158, 159))

    def test_forward_window_boundary(self):
        self.assertTrue(forward_window_fits(10, 5, 15, 100))
        self.assertFalse(forward_window_fits(11, 5, 15, 100))
        self.assertFalse(forward_window_fits(98, 5, 200, 100))


def cand(label, status, score):
    return {"ma_type": "SMA", "ma_period": label, "ma_label": f"SMA-{label}", "is_status": status,
            "is_affinity_score": score}


class Ranking(unittest.TestCase):
    def test_only_ok_ranked_in_score_order_ties_stable(self):
        rs = [cand(10, "OK", 50.0), cand(11, "INSUFFICIENT_DATA", 99.0), cand(12, "OK", 60.0),
              cand(13, "OK", 50.0), cand(14, "NO_INTERACTIONS", float("nan"))]
        rank_candidates(rs)
        self.assertEqual([r["rank"] for r in rs], [2, None, 1, 3, None])
        # equal scores: earlier candidate first, both flagged as ties
        self.assertTrue(rs[0]["rank_tie"] and rs[3]["rank_tie"])
        self.assertFalse(rs[2]["rank_tie"])
        self.assertEqual(freeze_top_n(rs, 2), [("SMA", 12), ("SMA", 10)])

    def test_insufficient_never_enters_top_n_even_with_high_score(self):
        rs = [cand(1, "INSUFFICIENT_DATA", 99.0), cand(2, "OK", 10.0)]
        rank_candidates(rs)
        self.assertEqual(freeze_top_n(rs, 5), [("SMA", 2)])

    def test_top_n_larger_than_available(self):
        rs = [cand(1, "OK", 10.0)]
        rank_candidates(rs)
        self.assertEqual(len(freeze_top_n(rs, 5)), 1)


class Consistency(unittest.TestCase):
    def test_formula(self):
        c = consistency(60.0, 50.0, 20, 10)
        self.assertEqual((c["diff"], c["raw"], c["value"], c["status"]), (10.0, 80.0, 80.0, "OK"))
        self.assertEqual(consistency(60.0, 60.0, 20, 10)["value"], 100.0)
        self.assertEqual(consistency(100.0, 0.0, 20, 10)["value"], 0.0)       # floor at 0

    def test_small_oos_sample_is_not_reported_as_a_number(self):
        c = consistency(60.0, 0.0, 3, 10)
        self.assertTrue(np.isnan(c["value"]))
        self.assertEqual(c["status"], "INSUFFICIENT_OOS_EVIDENCE")
        self.assertEqual(c["raw"], 0.0)                 # V2 number kept visible, not hidden

    def test_missing_is_not_zero(self):
        c = consistency(60.0, float("nan"), 0, 10)
        self.assertTrue(np.isnan(c["value"]))
        self.assertEqual(c["status"], "NOT_AVAILABLE")


class StateCarriedAcrossBoundary(unittest.TestCase):
    def setUp(self):
        n = 12
        self.ma = np.full(n, 100.0)
        # price is inside the zone [97,103] on bars 5,6,7 and out of it elsewhere
        self.low = np.array([110, 110, 110, 110, 110, 100, 100, 100, 110, 110, 100, 110], float)
        self.high = self.low + 2

    def test_inside_zone_at_split_does_not_create_oos_event(self):
        # IS ends at bar 5 (inside the zone); OOS starts at bar 6 which is still the same visit
        ev_is, iz, lev = detect_interaction_episodes(self.high, self.low, self.ma, 0, 5, 5, 0, 3.0, 1)
        self.assertTrue(iz)
        ev_carry, _, _ = detect_interaction_episodes(self.high, self.low, self.ma, 6, 11, 11, 0, 3.0, 1,
                                                     initial_in_zone=iz, last_event_bar=lev)
        ev_fresh, _, _ = detect_interaction_episodes(self.high, self.low, self.ma, 6, 11, 11, 0, 3.0, 1,
                                                     initial_in_zone=False, last_event_bar=-999)
        self.assertEqual(ev_carry, [10])            # only the genuinely new visit
        self.assertEqual(ev_fresh, [6, 10])         # without carry-over, bar 6 would be an artificial entry

    def test_cooldown_state_carried(self):
        ev, iz, lev = detect_interaction_episodes(self.high, self.low, self.ma, 0, 5, 5, 0, 3.0, 5)
        self.assertEqual(ev, [5])
        ev2, _, _ = detect_interaction_episodes(self.high, self.low, self.ma, 6, 11, 11, 0, 3.0, 5,
                                                initial_in_zone=False, last_event_bar=lev)
        self.assertEqual(ev2, [10])                 # bar 10 is 5 bars after bar 5 -> allowed
        ev3, _, _ = detect_interaction_episodes(self.high, self.low, self.ma, 6, 11, 11, 0, 3.0, 6,
                                                initial_in_zone=False, last_event_bar=lev)
        self.assertEqual(ev3, [])                   # cooldown 6 blocks it


class SeparationOfIsAndOos(unittest.TestCase):
    """IS selection -> rank on IS only -> freeze -> independent OOS."""

    def run_on(self, df):
        s = MAResearchSettings(ma_start=10, ma_end=60, fwd_windows=(5, 10), min_interactions=5, top_n=4,
                               oos_scope="all")
        return run_ma_affinity(df, s, "syn")

    @staticmethod
    def is_view(res):
        out = []
        for r in res.results:
            out.append((r["ma_label"], r["rank"], r["is_status"], r["is_n"], r["is_affinity_score"],
                        r["is_overall_sr"], r["is_p_value"]))
        return out

    @staticmethod
    def same(a, b):
        if len(a) != len(b):
            return False
        for x, y in zip(a, b):
            for u, v in zip(x, y):
                if isinstance(u, float) and isinstance(v, float) and np.isnan(u) and np.isnan(v):
                    continue
                if u != v:
                    return False
        return True

    def test_changing_oos_prices_never_changes_is_results_or_top_n(self):
        df = _helpers.synthetic_ohlc(700, seed=11)
        base = self.run_on(df)
        is_end = base.data_info["is_bars"] - 1
        df2 = df.copy()
        df2.iloc[is_end + 1:, :4] = df2.iloc[is_end + 1:, :4].to_numpy() * 1.37 + 5.0   # new regime in OOS
        changed = self.run_on(df2)
        self.assertTrue(self.same(self.is_view(base), self.is_view(changed)))
        self.assertEqual(base.frozen_top, changed.frozen_top)
        oos_a = [r["oos_overall_sr"] for r in base.results]
        oos_b = [r["oos_overall_sr"] for r in changed.results]
        self.assertNotEqual(repr(oos_a), repr(oos_b), "the OOS test data change had no effect (test invalid)")

    def test_ranking_is_identical_whether_oos_scope_is_top_n_or_all(self):
        df = _helpers.synthetic_ohlc(700, seed=12)
        s1 = MAResearchSettings(ma_start=10, ma_end=60, fwd_windows=(5, 10), min_interactions=5, oos_scope="top_n")
        s2 = MAResearchSettings(ma_start=10, ma_end=60, fwd_windows=(5, 10), min_interactions=5, oos_scope="all")
        a, b = run_ma_affinity(df, s1, "x"), run_ma_affinity(df, s2, "x")
        self.assertEqual(a.frozen_top, b.frozen_top)
        self.assertEqual([r["rank"] for r in a.results], [r["rank"] for r in b.results])
        n_eval = sum(1 for r in a.results if r["oos_status"] != "NOT_EVALUATED")
        self.assertEqual(n_eval, len(a.frozen_top))
        self.assertTrue(all(r["oos_status"] != "NOT_EVALUATED" for r in b.results))

    def test_changing_the_future_beyond_is_end_cannot_change_is_interactions(self):
        df = _helpers.synthetic_ohlc(500, seed=3)
        res = self.run_on(df)
        inter = res.interactions
        is_end = res.data_info["is_bars"] - 1
        n = len(df)
        pw = 5
        is_rows = inter[inter["period_type"] == "IS"]
        oos_rows = inter[inter["period_type"] == "OOS"]
        self.assertTrue((is_rows["bar_idx"] + pw <= is_end).all(), "IS primary window crosses the split")
        self.assertTrue((oos_rows["bar_idx"] > is_end).all())
        self.assertTrue((oos_rows["bar_idx"] + pw <= n - 1).all(), "OOS primary window crosses the data end")
        # forward values beyond the IS end must be missing (NoData), not borrowed from OOS
        for w in (5, 10):
            col, out = f"fwd_{w}", f"outcome_{w}"
            late = is_rows[is_rows["bar_idx"] + w > is_end]
            self.assertTrue(late[col].isna().all())
            self.assertTrue((late[out] == "NoData").all())


class Statistics(unittest.TestCase):
    def test_wilson_hand_value(self):
        self.assertAlmostEqual(wilson_lower_bound(6, 8), 0.40927, places=4)
        self.assertEqual(reliability_score(6, 8), 0.0)                   # below 50% after rescale
        self.assertTrue(np.isnan(reliability_score(3, 4)))               # fewer than 5 outcomes -> missing
        self.assertAlmostEqual(reliability_score(40, 50), (wilson_lower_bound(40, 50) - 0.5) / 0.5 * 100, places=6)

    def test_binomial_hand_value(self):
        self.assertAlmostEqual(binomial_pvalue_greater(6, 8), 37 / 256, places=10)
        self.assertAlmostEqual(binomial_pvalue_greater(5, 5), 1 / 32, places=10)
        self.assertTrue(np.isnan(binomial_pvalue_greater(2, 4)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
