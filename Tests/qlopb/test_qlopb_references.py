import unittest

import numpy as np

import _qlopb_helpers as _helpers  # noqa: F401  (sets sys.path)
from qlopb.references import REFERENCE_STATUS
from qlopb.references.moving_average import calc_ema, calc_hma, calc_rma, calc_sma, calc_wma, compute_ma


def nan_eq(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return a.shape == b.shape and np.allclose(a, b, equal_nan=True, atol=1e-4)


class KnownAnswers(unittest.TestCase):
    close = [1, 2, 3, 4, 5, 6]

    def test_sma(self):
        self.assertTrue(nan_eq(calc_sma(self.close, 3), [np.nan, np.nan, 2, 3, 4, 5]))

    def test_wma(self):
        # (1*1+2*2+3*3)/6 = 2.3333 ...
        self.assertTrue(nan_eq(calc_wma(self.close, 3), [np.nan, np.nan, 2.3333, 3.3333, 4.3333, 5.3333]))

    def test_ema_seeded_with_sma(self):
        self.assertTrue(nan_eq(calc_ema(self.close, 3), [np.nan, np.nan, 2, 3, 4, 5]))

    def test_rma(self):
        # seed 2; then (1/3)*4 + (2/3)*2 = 2.6667; ...
        self.assertTrue(nan_eq(calc_rma(self.close, 3), [np.nan, np.nan, 2, 2.6667, 3.4444, 4.2963]))

    def test_hma_of_linear_series_equals_series(self):
        # hand derivation: for a straight line the Hull MA equals the line itself
        out = calc_hma([1, 2, 3, 4, 5, 6, 7, 8], 4)
        self.assertTrue(nan_eq(out, [np.nan] * 4 + [5, 6, 7, 8]))

    def test_leading_values_are_nan_not_zero(self):
        for t in ("SMA", "EMA", "WMA", "HMA", "RMA"):
            out = compute_ma(np.arange(1, 30, dtype=float), t, 10)
            self.assertTrue(np.isnan(out[:9]).all(), t)

    def test_short_series_gives_all_nan(self):
        self.assertTrue(np.isnan(calc_sma([1, 2], 5)).all())
        self.assertTrue(np.isnan(calc_wma([1, 2], 5)).all())

    def test_bad_inputs_raise(self):
        with self.assertRaises(ValueError):
            compute_ma([1, 2, 3], "XYZ", 2)
        with self.assertRaises(ValueError):
            calc_sma([1, 2, 3], 0)
        with self.assertRaises(ValueError):
            calc_sma([1, 2, 3], 2.5)


class Causality(unittest.TestCase):
    def test_changing_the_future_never_changes_the_past(self):
        rng = np.random.default_rng(1)
        base = 100 + np.cumsum(rng.normal(0, 1, 300))
        changed = base.copy()
        changed[200:] += 50          # alter everything from bar 200 onwards
        for t in ("SMA", "EMA", "WMA", "HMA", "RMA"):
            a = compute_ma(base, t, 20)
            b = compute_ma(changed, t, 20)
            self.assertTrue(nan_eq(a[:200], b[:200]), f"{t} uses future data")
            self.assertFalse(nan_eq(a[200:], b[200:]), f"{t} test is not sensitive")


class Placeholders(unittest.TestCase):
    def test_only_moving_average_is_implemented(self):
        for k, v in REFERENCE_STATUS.items():
            self.assertEqual(v, "implemented" if k.startswith("Moving averages") else "placeholder", k)

    def test_placeholders_refuse_to_calculate(self):
        from qlopb.references import pivot_points, cpr, camarilla, bollinger_bands, previous_levels, other_references
        for mod in (pivot_points, cpr, camarilla, bollinger_bands, previous_levels, other_references):
            fn = [getattr(mod, n) for n in dir(mod) if n.startswith("compute_")][0]
            with self.assertRaises(NotImplementedError):
                fn()


if __name__ == "__main__":
    unittest.main(verbosity=2)
