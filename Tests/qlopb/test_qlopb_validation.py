import unittest

import numpy as np
import pandas as pd

import _qlopb_helpers as _helpers
from qlopb.config.settings import MAResearchSettings, SettingsError
from qlopb.core.validation import check_data_for_settings, ohlc_inconsistent_mask, validate_ohlc_frame
from qlopb.gui.research_controls import parse_settings


class OhlcRules(unittest.TestCase):
    def test_mask(self):
        m = ohlc_inconsistent_mask([10, 10, 10, 10], [12, 9, 12, 11], [9, 8, 11, 9], [11, 9, 10.5, 10])
        # row0 fine; row1 high<open; row2 low>open; row3 fine
        self.assertEqual(m.tolist(), [False, True, True, False])

    def test_good_frame_passes(self):
        self.assertEqual(validate_ohlc_frame(_helpers.synthetic_ohlc(50)), [])

    def test_problems_detected(self):
        df = _helpers.synthetic_ohlc(30)
        d = df.copy(); d.iloc[3, d.columns.get_loc("close")] = np.nan
        self.assertTrue(any("missing" in p for p in validate_ohlc_frame(d)))
        d = df.copy(); d.iloc[3, d.columns.get_loc("low")] = -1
        self.assertTrue(any("negative" in p for p in validate_ohlc_frame(d)))
        d = df.iloc[::-1]
        self.assertTrue(any("ascending" in p for p in validate_ohlc_frame(d)))
        d = pd.concat([df, df.iloc[:1]])
        self.assertTrue(any("Duplicate" in p for p in validate_ohlc_frame(d)))
        d = df.copy(); d.index = d.index.tz_localize("UTC")
        self.assertTrue(any("naive" in p for p in validate_ohlc_frame(d)))
        self.assertTrue(validate_ohlc_frame(df.drop(columns="close")))


class SettingsChecks(unittest.TestCase):
    def test_defaults_are_valid(self):
        s = MAResearchSettings()
        self.assertEqual(s.problems(), [])
        self.assertEqual(s.n_candidates, 241)
        self.assertEqual(s.primary_window, 5)

    def test_bad_values_reported(self):
        cases = [dict(ma_start=1), dict(ma_end=5, ma_start=10), dict(proximity_pct=0), dict(proximity_pct=60),
                 dict(cooldown_bars=-1), dict(fwd_windows=()), dict(fwd_windows=(5, 5)), dict(fwd_windows=(0,)),
                 dict(is_pct=0), dict(is_pct=100), dict(top_n=0), dict(ma_types=()), dict(ma_types=("ZZZ",)),
                 dict(weight_stability=-1), dict(oos_scope="x"), dict(timeframe="H"),
                 dict(weight_interaction_strength=0, weight_success_rate=0, weight_forward_return=0,
                      weight_stability=0)]
        for kw in cases:
            self.assertTrue(MAResearchSettings(**kw).problems(), kw)

    def test_weights_need_not_sum_to_100(self):
        s = MAResearchSettings(weight_interaction_strength=1, weight_success_rate=1,
                               weight_forward_return=1, weight_stability=1)
        self.assertEqual(s.problems(), [])


class InfinitePricesAndWeights(unittest.TestCase):
    def test_infinite_price_rejected_in_research_input(self):
        for bad in (np.inf, -np.inf):
            d = _helpers.synthetic_ohlc(30)
            d.iloc[3, d.columns.get_loc("close")] = bad
            self.assertTrue(any("infinite" in p for p in validate_ohlc_frame(d)), bad)

    def test_finite_prices_still_pass(self):
        self.assertEqual(validate_ohlc_frame(_helpers.synthetic_ohlc(30)), [])

    def test_bad_weights_reported(self):
        names = ("weight_interaction_strength", "weight_success_rate", "weight_forward_return", "weight_stability")
        for bad in (np.nan, np.inf, -np.inf, -1.0):
            for n in names:
                self.assertTrue(MAResearchSettings(**{n: bad}).problems(), (n, bad))

    def test_zero_and_overflowing_total_weight_reported(self):
        zero = {n: 0 for n in ("weight_interaction_strength", "weight_success_rate",
                               "weight_forward_return", "weight_stability")}
        self.assertTrue(MAResearchSettings(**zero).problems())
        huge = {k: 1e308 for k in zero}          # each finite, but the sum is inf
        self.assertTrue(any("finite" in p for p in MAResearchSettings(**huge).problems()))

    def test_valid_weights_still_pass(self):
        self.assertEqual(MAResearchSettings(weight_stability=0).problems(), [])
        self.assertEqual(MAResearchSettings().problems(), [])


class DataVersusSettings(unittest.TestCase):
    def test_short_data_gives_error_or_warning(self):
        s = MAResearchSettings()
        e, w = check_data_for_settings(_helpers.synthetic_ohlc(20), s)
        self.assertTrue(e)
        e, w = check_data_for_settings(_helpers.synthetic_ohlc(300), s)
        self.assertFalse(e)
        self.assertTrue(any("no in-sample history" in x for x in w))


class WindowParsing(unittest.TestCase):
    base = dict(ma_types=["SMA"], ma_start="10", ma_end="50", proximity_pct="3", cooldown_bars="5",
                fwd_windows="5,10,20", min_interactions="10", is_pct="70", regime_ma="200", top_n="5",
                w_interaction="20", w_success="25", w_forward="25", w_stability="15", oos_scope="top_n",
                min_oos="10", timeframe="as_loaded")

    def test_good(self):
        s = parse_settings(self.base)
        self.assertEqual(s.fwd_windows, (5, 10, 20))

    def test_all_errors_listed_together(self):
        bad = dict(self.base, ma_start="abc", proximity_pct="x", fwd_windows="5,,q")
        with self.assertRaises(SettingsError) as cm:
            parse_settings(bad)
        msg = str(cm.exception)
        self.assertIn("MA Start", msg); self.assertIn("Proximity", msg); self.assertIn("Forward Windows", msg)

    def test_range_errors(self):
        with self.assertRaises(SettingsError):
            parse_settings(dict(self.base, is_pct="100"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
