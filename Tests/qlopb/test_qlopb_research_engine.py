import ast
import hashlib
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd

import _qlopb_helpers as _helpers
from qlopb.analysis.affinity_engine import score_window
from qlopb.analysis.interaction_engine import build_interaction_records, detect_interaction_episodes
from qlopb.config.settings import MAResearchSettings, SettingsError
from qlopb.core.data_engine import load_file
from qlopb.core.research_engine import ResearchError, run_full_pipeline, run_ma_affinity
from qlopb.references.moving_average import calc_sma

NAN = float("nan")


# ── 1. Interaction definitions on tiny hand-made examples ───────────────────
class InteractionDefinitions(unittest.TestCase):
    ma = np.full(12, 100.0)
    low = np.array([110, 110, 100, 100, 110, 100, 110, 100, 110, 110, 110, 110], float)
    high = low + 2        # in zone [97,103] on bars 2,3,5,7

    def test_entries_are_rising_edges_only(self):
        ev, _, _ = detect_interaction_episodes(self.high, self.low, self.ma, 0, 11, 11, 0, 3.0, 1)
        self.assertEqual(ev, [2, 5, 7])             # bar 3 is the same visit as bar 2

    def test_cooldown(self):
        ev, _, _ = detect_interaction_episodes(self.high, self.low, self.ma, 0, 11, 11, 0, 3.0, 3)
        self.assertEqual(ev, [2, 5])                # 7-5=2 < 3 -> skipped

    def test_primary_window_must_fit_in_period(self):
        ev, _, _ = detect_interaction_episodes(self.high, self.low, self.ma, 0, 11, 11, 5, 3.0, 1)
        self.assertEqual(ev, [2, 5])                # record_end = 11-5 = 6, so bar 7 is not eligible
        ev, _, _ = detect_interaction_episodes(self.high, self.low, self.ma, 0, 11, 11, 4, 3.0, 1)
        self.assertEqual(ev, [2, 5, 7])             # record_end = 7

    def test_zone_edges_are_inclusive(self):
        ma = np.array([100.0] * 4)
        low = np.array([103.0, 110, 110, 110]); high = low + 1       # low == upper edge exactly
        ev, _, _ = detect_interaction_episodes(high, low, ma, 0, 3, 3, 0, 3.0, 1)
        self.assertEqual(ev, [0])
        low = np.array([103.01, 110, 110, 110]); high = low + 1
        ev, _, _ = detect_interaction_episodes(high, low, ma, 0, 3, 3, 0, 3.0, 1)
        self.assertEqual(ev, [])

    def test_nan_ma_is_never_in_zone(self):
        ma = np.array([np.nan, np.nan, 100, 100.0])
        low = np.array([100, 100, 110, 100.0]); high = low + 1
        ev, _, _ = detect_interaction_episodes(high, low, ma, 0, 3, 3, 0, 3.0, 1)
        self.assertEqual(ev, [3])


class SideAndOutcome(unittest.TestCase):
    def rec(self, close, ev, fwd=(2, 4), fwd_end=None, ma=100.0):
        n = len(close)
        close = np.array(close, float)
        idx = pd.date_range("2025-01-01", periods=n, freq="D")
        return build_interaction_records(ev, np.full(n, ma), "SMA", 5, fwd_end if fwd_end is not None else n - 1,
                                         close, close + 1, close - 1, idx, np.full(n, np.nan), list(fwd))

    close = [100, 98, 101, 103, 99, 97, 95, 102, 104, 100]

    def test_neutral_support_resistance(self):
        r = self.rec(self.close, [1, 2, 3])
        self.assertEqual([x["side"] for x in r], ["Neutral", "Resistance", "Support"])   # prev==MA -> Neutral
        self.assertEqual(r[0]["outcome_2"], "Neutral")

    def test_forward_return_and_success(self):
        r = self.rec(self.close, [2])[0]       # Resistance at close 101; close[4]=99, close[6]=95
        self.assertAlmostEqual(r["fwd_2"], (99 - 101) / 101 * 100, places=9)
        self.assertEqual(r["outcome_2"], "Success")            # resistance succeeds when price falls
        self.assertAlmostEqual(r["fwd_4"], (95 - 101) / 101 * 100, places=9)
        s = self.rec(self.close, [3])[0]       # Support at 103; close[5]=97 -> failure
        self.assertEqual(s["outcome_2"], "Failure")

    def test_zero_return_is_failure(self):
        r = self.rec([101, 100, 100, 100, 100, 100], [1], fwd=(1,))[0]      # Support, return exactly 0
        self.assertEqual(r["side"], "Support")
        self.assertEqual(r["fwd_1"], 0.0)
        self.assertEqual(r["outcome_1"], "Failure")

    def test_window_crossing_period_end_is_nodata_not_zero(self):
        r = self.rec(self.close, [6, 7], fwd_end=8)
        self.assertEqual(r[0]["outcome_2"], "Success" if r[0]["fwd_2"] < 0 else "Failure")   # 6+2=8 fits
        self.assertEqual(r[0]["outcome_4"], "NoData")
        self.assertTrue(np.isnan(r[0]["fwd_4"]))
        self.assertEqual(r[1]["outcome_2"], "NoData")


# ── 2. Scoring against hand calculations ────────────────────────────────────
def mk(side, fwd, w=5):
    ok = (fwd > 0) if side == "Support" else (fwd < 0)
    return {"side": side, f"fwd_{w}": fwd, f"outcome_{w}": "Success" if ok else "Failure"}


class ScoringHandCalc(unittest.TestCase):
    s = MAResearchSettings(fwd_windows=(5,), min_interactions=4)

    def test_full_score_hand_calculation(self):
        recs = [mk("Support", x) for x in (2, 1, -1, 3)] + [mk("Resistance", x) for x in (-2, -1, 1, -3)]
        r = score_window(recs, self.s)
        self.assertEqual((r["status"], r["n"], r["n_outcomes"]), ("OK", 8, 8))
        self.assertEqual(r["overall_sr"], 75.0)
        self.assertEqual(r["score_components"]["interaction_strength"], 40.0)    # 8/20
        self.assertEqual(r["score_components"]["success_rate"], 50.0)            # (0.75-0.5)/0.5
        self.assertEqual(r["score_components"]["forward_return_directed_ir"], 100.0)   # mean/std=0.845 -> +0.5 -> clipped
        self.assertEqual(r["score_components"]["stability"], 0.0)                # chunks of 2 < 3
        self.assertTrue(np.isnan(r["stability"]))                                 # missing, shown as such
        self.assertEqual(r["affinity_score"], round((20 * .4 + 25 * .5 + 25 * 1.0 + 15 * 0) / 85 * 100, 2))
        self.assertEqual(r["p_value"], round(37 / 256, 4))
        self.assertEqual(r["reliability"], 0.0)

    def test_stability_hand_calculation(self):
        # 4 chunks of 3: success counts 3,2,1,0 -> SRs 1, 2/3, 1/3, 0 -> std 0.372678 -> 1-2*std = 0.25464
        pattern = [3, 2, 1, 0]
        recs = []
        for k in pattern:
            for j in range(3):
                recs.append(mk("Support", 1.0 if j < k else -1.0))
        r = score_window(recs, self.s)
        self.assertAlmostEqual(r["stability"], 25.46, places=2)

    def test_weights_are_normalised(self):
        recs = [mk("Support", x) for x in (2, 1, -1, 3)] + [mk("Resistance", x) for x in (-2, -1, 1, -3)]
        a = score_window(recs, MAResearchSettings(fwd_windows=(5,), min_interactions=4))
        b = score_window(recs, MAResearchSettings(fwd_windows=(5,), min_interactions=4,
                                                  weight_interaction_strength=200, weight_success_rate=250,
                                                  weight_forward_return=250, weight_stability=150))
        c = score_window(recs, MAResearchSettings(fwd_windows=(5,), min_interactions=4,
                                                  weight_interaction_strength=1, weight_success_rate=1,
                                                  weight_forward_return=1, weight_stability=1))
        self.assertEqual(a["affinity_score"], b["affinity_score"])
        self.assertEqual(c["affinity_score"], round((40 + 50 + 100 + 0) / 4, 2))

    def test_invalid_weights_stop_scoring(self):
        recs = [mk("Support", x) for x in (2, 1, -1, 3)] + [mk("Resistance", x) for x in (-2, -1, 1, -3)]
        for bad in (float("nan"), float("inf"), -1.0):
            s = MAResearchSettings(fwd_windows=(5,), min_interactions=4, weight_success_rate=bad)
            with self.assertRaises(SettingsError):
                score_window(recs, s)
        zero = MAResearchSettings(fwd_windows=(5,), min_interactions=4, weight_interaction_strength=0,
                                  weight_success_rate=0, weight_forward_return=0, weight_stability=0)
        with self.assertRaises(SettingsError):
            score_window(recs, zero)
        huge = MAResearchSettings(fwd_windows=(5,), min_interactions=4, weight_interaction_strength=1e308,
                                  weight_success_rate=1e308, weight_forward_return=1e308,
                                  weight_stability=1e308)
        with self.assertRaises(SettingsError):
            score_window(recs, huge)

    def test_invalid_weights_rejected_even_with_no_records(self):
        for bad in (float("nan"), float("inf"), -1.0):
            s = MAResearchSettings(fwd_windows=(5,), min_interactions=4, weight_stability=bad)
            with self.assertRaises(SettingsError):
                score_window([], s)
        self.assertEqual(score_window([], MAResearchSettings(fwd_windows=(5,)))["status"], "NO_INTERACTIONS")

    def test_statuses_insufficient_vs_none_vs_poor(self):
        none = score_window([], self.s)
        self.assertEqual(none["status"], "NO_INTERACTIONS")
        self.assertTrue(np.isnan(none["affinity_score"]))                         # missing, not 0
        few = score_window([mk("Support", 1), mk("Support", 2)], self.s)
        self.assertEqual(few["status"], "INSUFFICIENT_DATA")
        poor = score_window([mk("Support", -1)] * 6, self.s)
        self.assertEqual(poor["status"], "OK")                                    # poor result is still a result
        self.assertEqual(poor["affinity_score"], round((20 * .3) / 85 * 100, 2))  # only interaction strength counts

    def test_neutral_interactions_count_in_n_but_not_in_outcomes(self):
        recs = [mk("Support", 1)] * 3 + [{"side": "Neutral", "fwd_5": 1.0, "outcome_5": "Neutral"}] * 2
        r = score_window(recs, self.s)
        self.assertEqual((r["n"], r["n_outcomes"]), (5, 3))

    def test_forward_stats_use_sample_std(self):
        recs = [mk("Support", x) for x in (1.0, 2.0, 3.0, 4.0)]
        r = score_window(recs, self.s)
        self.assertAlmostEqual(r["fwd_stats"][5]["std"], np.std([1, 2, 3, 4], ddof=1))
        self.assertAlmostEqual(r["fwd_stats"][5]["mean"], 2.5)


# ── 3. Independent brute-force re-implementation vs the engine ──────────────
def brute_force_is(close, high, low, period, prox, cooldown, pw, is_end):
    """Slow, loop-only version of the V2 rules written separately from the engine."""
    n_is = is_end + 1
    sma = [None] * n_is
    for i in range(period - 1, n_is):
        sma[i] = sum(close[i - period + 1:i + 1]) / period
    last, prev_in = -(period + 1), False
    n_events = wins = losses = 0
    for i in range(n_is):
        inz = sma[i] is not None and low[i] <= sma[i] * (1 + prox / 100) and high[i] >= sma[i] * (1 - prox / 100)
        entry = inz and not prev_in
        prev_in = inz
        if entry and i + pw <= is_end and i - last >= cooldown:
            last = i
            n_events += 1
            side_prev = close[i - 1] if i > 0 else close[i]
            fr = (close[i + pw] - close[i]) / close[i]
            if side_prev > sma[i]:
                wins, losses = (wins + 1, losses) if fr > 0 else (wins, losses + 1)
            elif side_prev < sma[i]:
                wins, losses = (wins + 1, losses) if fr < 0 else (wins, losses + 1)
    return n_events, wins, losses


class BruteForceAgreement(unittest.TestCase):
    def check(self, df, periods):
        s = MAResearchSettings(ma_start=min(periods), ma_end=max(periods), fwd_windows=(5, 10), min_interactions=5)
        res = run_ma_affinity(df, s, "bf")
        is_end = res.data_info["is_bars"] - 1
        c, h, l = (df[k].to_numpy(float) for k in ("close", "high", "low"))
        by = {r["ma_period"]: r for r in res.results}
        for p in periods:
            n, w, lo = brute_force_is(c, h, l, p, 3.0, 5, 5, is_end)
            r = by[p]
            self.assertEqual(r["is_n"], n, f"period {p}: interaction count")
            if w + lo:
                self.assertEqual(r["is_overall_sr"], round(w / (w + lo) * 100, 2), f"period {p}: success rate")
                self.assertEqual(r["is_n_outcomes"], w + lo)

    def test_synthetic(self):
        self.check(_helpers.synthetic_ohlc(900, seed=5), [10, 20, 50, 100, 150])

    def test_sample_hourly(self):
        if not _helpers.SBIN_FILE.exists():
            self.skipTest("SBIN sample not present")
        self.check(load_file(_helpers.SBIN_FILE).df, [20, 50, 97, 141, 195])

    def test_sample_daily(self):
        if not _helpers.NIFTY_FILE.exists():
            self.skipTest("Nifty sample not present")
        self.check(load_file(_helpers.NIFTY_FILE).df, [10, 20, 30, 45])


# ── 4. Engine behaviour ─────────────────────────────────────────────────────
class EngineBehaviour(unittest.TestCase):
    def test_rejects_unusable_input_clearly(self):
        s = MAResearchSettings()
        df = _helpers.synthetic_ohlc(500)
        bad = df.copy(); bad.iloc[5, 3] = np.nan
        with self.assertRaises(ResearchError):
            run_ma_affinity(bad, s, "x")
        with self.assertRaises(ResearchError):
            run_ma_affinity(df.iloc[:12], s, "x")
        from qlopb.config.settings import SettingsError
        with self.assertRaises(SettingsError):
            run_ma_affinity(df, MAResearchSettings(is_pct=0), "x")

    def test_no_silent_date_filter_all_bars_used(self):
        df = _helpers.synthetic_ohlc(400, start="2001-01-01")
        res = run_ma_affinity(df, MAResearchSettings(ma_start=10, ma_end=40), "x")
        self.assertEqual(res.data_info["n_bars"], 400)
        self.assertEqual(res.data_info["first"], "01-Jan-01")

    def test_long_ma_without_history_is_no_interactions_not_poor(self):
        res = run_ma_affinity(_helpers.synthetic_ohlc(300), MAResearchSettings(ma_start=10, ma_end=250), "x")
        none = [r for r in res.results if r["is_status"] == "NO_INTERACTIONS"]
        self.assertTrue(none)
        self.assertTrue(all(np.isnan(r["is_affinity_score"]) and r["rank"] is None for r in none))

    def test_progress_log_and_cancel(self):
        calls, logs = [], []
        run_ma_affinity(_helpers.synthetic_ohlc(700), MAResearchSettings(ma_start=10, ma_end=30, min_interactions=5), "x",
                        progress=lambda d, t, m: calls.append((d, t)), log=logs.append)
        self.assertTrue(calls and calls[-1][0] == calls[-1][1])
        self.assertTrue(any("Phase 2/3" in x for x in logs))
        from qlopb.core.research_engine import RunCancelled
        with self.assertRaises(RunCancelled):
            run_ma_affinity(_helpers.synthetic_ohlc(300), MAResearchSettings(ma_start=10, ma_end=30), "x",
                            cancel=lambda: True)

    def test_multiple_ma_types_compete_in_one_ranking(self):
        s = MAResearchSettings(ma_types=("SMA", "EMA", "HMA"), ma_start=10, ma_end=40, min_interactions=5)
        res = run_ma_affinity(_helpers.synthetic_ohlc(700, seed=9), s, "x")
        self.assertEqual(len(res.results), 93)
        ranks = sorted(r["rank"] for r in res.results if r["rank"])
        self.assertEqual(ranks, list(range(1, len(ranks) + 1)))

    def test_timeframe_weekly(self):
        res = run_ma_affinity(_helpers.synthetic_ohlc(1500, freq="B"),
                              MAResearchSettings(ma_start=5, ma_end=20, timeframe="W", min_interactions=5), "x")
        self.assertLess(res.data_info["n_bars"], 400)
        self.assertTrue(any("Aggregated" in n for n in res.notes))


# ── 5. Reports ──────────────────────────────────────────────────────────────
class Reports(unittest.TestCase):
    def test_chart_shows_real_zero_not_fifty(self):
        from qlopb.reports import chart_report
        captured = []
        top = [{"ma_label": "SMA-10", "rank": 1, "is_overall_sr": 60.0, "oos_overall_sr": 0.0,
                "oos_n_outcomes": 12}]
        fake = SimpleNamespace(label="x", settings=MAResearchSettings())
        with mock.patch.object(chart_report, "_save", lambda fig, folder, name, stamp: captured.append(fig)):
            chart_report._is_oos_chart(fake, top, ".", "s")
        heights = [round(p.get_height(), 6) for p in captured[0].axes[0].patches]
        self.assertIn(0.0, heights)
        self.assertNotIn(50.0, heights)          # the V2 bug turned a real 0% into 50%
        import matplotlib.pyplot as plt
        plt.close("all")

    def test_pipeline_outputs_and_content(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "my data.csv"
            _helpers.synthetic_ohlc(300).to_csv(src)
            # captured BEFORE the run (review 04-Nov-26, D7): the source must be byte-identical afterwards
            original_bytes = src.read_bytes()
            original_sha = hashlib.sha256(original_bytes).hexdigest()
            original_mtime = src.stat().st_mtime_ns
            out = run_full_pipeline(src, MAResearchSettings(ma_start=10, ma_end=250, min_interactions=3),
                                   output_root=Path(d) / "o")
            self.assertIn(out["status"], ("SUCCESS", "COMPLETED WITH WARNINGS"))
            for k in ("excel", "pdf", "clean", "log"):
                self.assertTrue(out[k].exists(), k)
                self.assertRegex(out[k].name, r"\d{2}_[A-Za-z]{3}_\d{2}_\d{6}\.\w+$")
            self.assertTrue(out["pdf"].read_bytes().startswith(b"%PDF"))
            self.assertTrue(len(out["charts"]) >= 4)
            import openpyxl
            wb = openpyxl.load_workbook(out["excel"])
            self.assertEqual(wb.sheetnames, ["Summary", "Top_N", "Rankings", "Interactions", "Forward_Returns",
                                             "Settings", "Data_Quality", "Charts"])
            text = " ".join(str(c.value) for row in wb["Summary"].iter_rows() for c in row if c.value)
            self.assertIn("historical data only", text)            # disclaimer
            self.assertIn("multiple comparisons", text)            # limitations
            self.assertIn("Candidates tested", text)               # sample sizes
            rk = wb["Rankings"]
            head = [c.value for c in rk[1]]
            i_status, i_score = head.index("IS status"), head.index("IS affinity")
            seen_none = False
            for row in rk.iter_rows(min_row=2, values_only=True):
                if row[i_status] == "NO_INTERACTIONS":
                    seen_none = True
                    self.assertIsNone(row[i_score])               # missing is EMPTY, never 0
            self.assertTrue(seen_none, "test data should include candidates with no interactions")
            self.assertTrue(all("₹" not in str(c.value) for row in rk.iter_rows(min_row=2) for c in row))
            self.assertEqual(src.read_bytes(), original_bytes)
            self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(), original_sha)
            self.assertEqual(src.stat().st_mtime_ns, original_mtime)

    def test_failed_input_is_reported_not_crashed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.csv"
            p.write_text("a,b\n1,2\n")
            out = run_full_pipeline(p, MAResearchSettings(), output_root=Path(d) / "o")
            self.assertEqual(out["status"], "FAILED")
            self.assertTrue(out["log"].exists())

    def test_sample_files_end_to_end(self):
        for p in (_helpers.SBIN_FILE, _helpers.NIFTY_FILE):
            if not p.exists():
                continue
            with tempfile.TemporaryDirectory() as d:
                out = run_full_pipeline(p, MAResearchSettings(), output_root=d)
                self.assertIn(out["status"], ("SUCCESS", "COMPLETED WITH WARNINGS"), f"{p.name}: {out.get('error')}")
                self.assertTrue(out["excel"].exists() and out["pdf"].exists())


# Section 6 of the QLOPB original (GUI wiring of gui/main_window.py with a fake tkinter, 6 tests) is not
# migrated: Q-MAP uses the Analytical Workbench instead of QLOPB's own window.


if __name__ == "__main__":
    unittest.main(verbosity=2)
