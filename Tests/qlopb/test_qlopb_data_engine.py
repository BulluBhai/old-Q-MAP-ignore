import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import _qlopb_helpers as _helpers
from qlopb.core.data_engine import (AmbiguousDateError, ColumnMappingError, DataLoadError, LoadOptions, load_file,
                              save_processed, sha256_of_file)
from qlopb.core.timeframe_engine import TimeframeError, resample_ohlc

HDR = "date,open,high,low,close,volume\n"


def rows(n=20, start="2025-01-01"):
    out = []
    for i, d in enumerate(pd.date_range(start, periods=n, freq="B")):
        out.append(f"{d:%Y-%m-%d},{100+i},{102+i},{99+i},{101+i},{1000+i}")
    return out


class SyntheticFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def f(self, text, name="t.csv"):
        return _helpers.write_text(self.dir / name, text)

    def test_headered_basic(self):
        r = load_file(self.f(HDR + "\n".join(rows())))
        self.assertEqual(len(r.df), 20)
        self.assertEqual(list(r.df.columns), ["open", "high", "low", "close", "volume"])
        self.assertTrue(r.df.index.is_monotonic_increasing)
        self.assertEqual(r.report.rows_rejected, 0)
        self.assertTrue(r.report.header_detected)

    def test_infinite_prices_rejected_in_csv(self):
        for tok in ("inf", "-inf", "Infinity"):
            lines = rows(30)
            parts = lines[5].split(",")
            parts[4] = tok                      # close column
            lines[5] = ",".join(parts)
            r = load_file(self.f(HDR + "\n".join(lines)))
            self.assertEqual(len(r.df), 29, tok)
            self.assertEqual(r.report.reject_counts.get("infinite_price"), 1, tok)
            self.assertTrue(np.isfinite(r.df[["open", "high", "low", "close"]].to_numpy()).all())

    def test_infinite_prices_rejected_in_parquet(self):
        base = _helpers.synthetic_ohlc(40)
        for bad in (np.inf, -np.inf):
            d = base.copy()
            d.iloc[7, d.columns.get_loc("close")] = bad
            p = self.dir / "t.parquet"
            d.to_parquet(p)
            r = load_file(p)
            self.assertEqual(len(r.df), 39)
            self.assertEqual(r.report.reject_counts.get("infinite_price"), 1)
        base.to_parquet(self.dir / "ok.parquet")
        self.assertEqual(len(load_file(self.dir / "ok.parquet").df), 40)

    def test_row_with_too_few_columns_rejected(self):
        lines = rows(40)
        lines[25] = "2025-01-07,100,102,99"
        r = load_file(self.f(HDR + "\n".join(lines)))
        self.assertEqual(len(r.df), 39)
        self.assertEqual(r.report.reject_counts.get("wrong_column_count"), 1)

    def test_row_with_extra_columns_rejected_not_ignored(self):
        lines = rows(40)
        lines[25] = lines[25] + ",999,888"
        r = load_file(self.f(HDR + "\n".join(lines)))
        self.assertEqual(len(r.df), 39)
        self.assertEqual(r.report.reject_counts.get("wrong_column_count"), 1)
        self.assertIn("999", r.rejected.loc[r.rejected["reason"] == "wrong_column_count", "raw_row"].iloc[0])

    def test_alias_columns_and_semicolon(self):
        txt = "Date;Open Price;High;Low;Closing;Vol\n" + "\n".join(x.replace(",", ";") for x in rows())
        r = load_file(self.f(txt))
        self.assertEqual(len(r.df), 20)
        self.assertEqual(r.report.delimiter, ";")

    def test_headerless_order_confirmed_from_data(self):
        r = load_file(self.f("\n".join(rows())))
        self.assertFalse(r.report.header_detected)
        self.assertEqual(len(r.df), 20)
        self.assertTrue(any("CONFIRMED" in n for n in r.report.structure_notes))

    def test_headerless_wrong_order_is_refused(self):
        # columns are date, close, open, high, low -> does not fit O,H,L,C
        bad = [f"{d:%Y-%m-%d},{101+i},{100+i},{102+i},{99+i}" for i, d in
               enumerate(pd.date_range("2025-01-01", periods=20, freq="B"))]
        with self.assertRaises(ColumnMappingError):
            load_file(self.f("\n".join(bad)))

    def test_ambiguous_dates_refused_then_resolved(self):
        body = "\n".join(f"{(i % 12) + 1:02d}/{(i // 12) + 1:02d}/2025,{100+i},{102+i},{99+i},{101+i},1000"
                         for i in range(20))
        p = self.f(HDR + body)
        with self.assertRaises(AmbiguousDateError):
            load_file(p)
        r = load_file(p, LoadOptions(dayfirst=True))
        self.assertGreater(len(r.df), 0)

    def test_unambiguous_dayfirst_detected(self):
        body = "\n".join(f"{(i % 28) + 1:02d}/01/2025,{100+i},{102+i},{99+i},{101+i},1000" for i in range(20))
        r = load_file(self.f(HDR + body))
        self.assertEqual(r.df.index[0], pd.Timestamp("2025-01-01"))
        self.assertIn(pd.Timestamp("2025-01-20"), r.df.index)

    def test_mixed_timezone_offsets_refused(self):
        lines = [f"2025-01-{i + 1:02d}T10:00:00{'+05:30' if i % 2 else '+00:00'},{100+i},{102+i},{99+i},{101+i}"
                 for i in range(20)]
        with self.assertRaises(DataLoadError):
            load_file(self.f("time,open,high,low,close\n" + "\n".join(lines)))

    def test_uniform_offset_removed_and_recorded(self):
        lines = [f"2025-01-{i + 1:02d}T10:00:00+05:30,{100+i},{102+i},{99+i},{101+i}" for i in range(20)]
        r = load_file(self.f("time,open,high,low,close\n" + "\n".join(lines)))
        self.assertEqual(r.df.index[0], pd.Timestamp("2025-01-01 10:00"))
        self.assertIsNone(r.df.index.tz)
        self.assertIn("+05:30", r.report.timezone_note)
        self.assertFalse(r.report.volume_available)

    def test_bad_rows_rejected_with_reasons(self):
        r_ = rows(30)
        r_[3] = "not-a-date,1,2,3,4,5"
        r_[5] = "2025-01-08,abc,102,99,101,1000"
        r_[7] = "2025-01-10,100,99,101,100,1000"      # high < low
        r_[9] = r_[8]                                   # duplicate timestamp
        r = load_file(self.f(HDR + "\n".join(r_)))
        reasons = set(r.rejected["reason"])
        self.assertEqual(reasons, {"unparseable_date", "missing_or_non_numeric_price", "ohlc_inconsistent",
                                   "duplicate_timestamp"})
        self.assertEqual(r.report.rows_accepted + r.report.rows_rejected, 30)
        self.assertEqual(len(r.rejected), 4)
        self.assertEqual(r.report.duplicates_found, 1)

    def test_too_many_rejected_stops(self):
        r_ = rows(30)
        for i in range(12):
            r_[i] = f"junk{i},x,y,z,w,v"
        with self.assertRaises(DataLoadError):
            load_file(self.f(HDR + "\n".join(r_)))

    def test_too_many_ohlc_inconsistent_means_wrong_columns(self):
        bad = [f"{d:%Y-%m-%d},{100+i},{99+i},{102+i},{101+i},1000" for i, d in
               enumerate(pd.date_range("2025-01-01", periods=30, freq="B"))]
        with self.assertRaises(ColumnMappingError):
            load_file(self.f(HDR + "\n".join(bad)))

    def test_too_few_rows(self):
        with self.assertRaises(DataLoadError):
            load_file(self.f(HDR + "\n".join(rows(5))))

    def test_missing_required_column(self):
        with self.assertRaises(ColumnMappingError):
            load_file(self.f("date,open,high,low\n" + "\n".join(r.rsplit(",", 2)[0] for r in rows())))

    def test_two_close_columns_is_ambiguous(self):
        with self.assertRaises(ColumnMappingError):
            load_file(self.f("date,open,high,low,close,c\n" + "\n".join(rows())))

    def test_unsorted_rows_are_sorted_and_reported(self):
        r_ = rows(20)[::-1]
        r = load_file(self.f(HDR + "\n".join(r_)))
        self.assertTrue(r.df.index.is_monotonic_increasing)
        self.assertGreater(r.report.out_of_order_rows, 0)

    def test_no_default_date_filter(self):
        r = load_file(self.f(HDR + "\n".join(rows(20, start="1999-01-04"))))
        self.assertEqual(r.df.index[0], pd.Timestamp("1999-01-04"))

    def test_flags_reported_not_corrected(self):
        r_ = rows(30)
        r_[10] = "2025-01-15,300,305,295,300,1"        # +~190% jump and volume 1
        r = load_file(self.f(HDR + "\n".join(r_)))
        names = {k: v["count"] for k, v in r.report.flags.items()}
        self.assertTrue(any(c >= 1 for k, c in names.items() if "move above" in k))
        self.assertTrue(any(c >= 1 for k, c in names.items() if "volume at or below" in k))
        self.assertIn(300.0, r.df["open"].values)       # not removed or altered

    def test_original_file_untouched_and_processed_copy_written(self):
        p = self.f(HDR + "\n".join(rows()))
        before = sha256_of_file(p)
        r = load_file(p)
        paths = save_processed(r, self.dir / "processed", "11_Oct_26_120000")
        self.assertEqual(sha256_of_file(p), before)
        self.assertTrue(paths["clean"].exists())
        self.assertRegex(paths["clean"].name, r"\d{2}_[A-Za-z]{3}_\d{2}_\d{6}\.csv$")
        back = pd.read_csv(paths["clean"])
        self.assertEqual(len(back), len(r.df))

    def test_missing_file(self):
        with self.assertRaises(DataLoadError):
            load_file(self.dir / "nope.csv")

    def test_parquet_if_available(self):
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            self.skipTest("pyarrow is not installed - Parquet NOT tested")
        df = _helpers.synthetic_ohlc(40).reset_index()
        p = self.dir / "t.parquet"
        df.to_parquet(p)
        self.assertEqual(len(load_file(p).df), 40)


class Timeframes(unittest.TestCase):
    def test_hourly_to_daily_aggregation_hand_values(self):
        idx = pd.to_datetime(["2025-03-03 09:15", "2025-03-03 10:15", "2025-03-03 11:15",
                              "2025-03-04 09:15", "2025-03-04 10:15", "2025-03-04 11:15",
                              "2025-03-05 09:15", "2025-03-05 10:15", "2025-03-05 11:15"])
        df = pd.DataFrame({"open": [10, 11, 12, 20, 21, 22, 30, 31, 32],
                           "high": [11, 13, 12, 25, 21, 22, 30, 35, 32],
                           "low": [9, 10, 11, 19, 20, 18, 29, 31, 30],
                           "close": [10.5, 12, 11.5, 21, 20.5, 21.5, 31, 34, 31.5],
                           "volume": [1, 2, 3, 4, 5, 6, 7, 8, 9.0]}, index=idx)
        out, notes = resample_ohlc(df, "D")
        self.assertEqual(len(out), 3)
        d1 = out.iloc[0]
        self.assertEqual((d1.open, d1.high, d1.low, d1.close, d1.volume), (10, 13, 9, 11.5, 6))
        self.assertEqual(out.index[0], pd.Timestamp("2025-03-03"))
        self.assertTrue(out["boundary_period"].iloc[0] and out["boundary_period"].iloc[-1])
        self.assertFalse(out["boundary_period"].iloc[1])

    def test_coarser_is_fine_same_is_noop(self):
        df = _helpers.synthetic_ohlc(60)          # daily
        w, _ = resample_ohlc(df, "W")
        self.assertLess(len(w), len(df))
        same, notes = resample_ohlc(df, "D")
        self.assertEqual(len(same), len(df))


class RealSampleFiles(unittest.TestCase):
    """Run only when the owner's real sample files are present in data/raw."""

    def test_sbin_hourly_csv(self):
        if not _helpers.SBIN_FILE.exists():
            self.skipTest("SBIN sample file not present")
        self.assertEqual(sha256_of_file(_helpers.SBIN_FILE), _helpers.SBIN_SHA256, "sample file changed")
        with open(_helpers.SBIN_FILE, newline="", encoding="utf-8-sig") as fh:       # independent count
            data = [r for r in csv.reader(fh) if any(c.strip() for c in r)]
        r = load_file(_helpers.SBIN_FILE)
        self.assertEqual(r.report.rows_in_file, len(data) - 1)
        self.assertEqual(len(r.df), len(data) - 1)
        self.assertEqual(r.report.rows_rejected, 0)
        self.assertTrue(r.report.header_detected)
        self.assertEqual(r.df.index[0], pd.Timestamp("2025-02-11 13:15"))
        self.assertEqual(r.df.index[-1], pd.Timestamp("2026-10-09 14:15"))
        self.assertAlmostEqual(r.df["close"].iloc[0], float(data[1][4]))
        self.assertAlmostEqual(r.df["close"].iloc[-1], float(data[-1][4]))
        self.assertIsNone(r.df.index.tz)
        self.assertIn("+05:30", r.report.timezone_note)
        self.assertFalse(r.report.volume_available)
        self.assertEqual(r.report.unmapped_columns, ["ATR in %", "ATR", "Daily ATR Closing to Closing%"])
        self.assertIn("intraday", r.report.inferred_frequency)
        # the weekend-dated bars (Sunday 01-Feb-26) are reported, not removed
        wk = [v for k, v in r.report.flags.items() if "Saturday" in k][0]
        self.assertGreater(wk["count"], 0)
        self.assertIn(pd.Timestamp("2026-02-01 09:15"), r.df.index)

    def test_nifty_headerless_daily_txt(self):
        if not _helpers.NIFTY_FILE.exists():
            self.skipTest("Nifty sample file not present")
        r = load_file(_helpers.NIFTY_FILE)
        self.assertFalse(r.report.header_detected)
        self.assertEqual(len(r.df), 228)
        self.assertEqual(r.df.index[0], pd.Timestamp("2025-11-10"))
        self.assertEqual(r.df.index[-1], pd.Timestamp("2026-10-09"))
        self.assertAlmostEqual(r.df["close"].iloc[0], 18932.15)
        self.assertAlmostEqual(r.df["close"].iloc[-1], 20679.4)
        self.assertTrue(r.report.volume_available)
        self.assertEqual(r.report.inferred_frequency, "daily")
        lowvol = [v for k, v in r.report.flags.items() if "volume at or below" in k][0]
        self.assertIn("02-Dec-25", lowvol["examples"])
        self.assertTrue(any("CONFIRMED" in n for n in r.report.structure_notes))

    def test_real_files_unchanged_by_loading(self):
        for p in (_helpers.SBIN_FILE, _helpers.NIFTY_FILE):
            if p.exists():
                h = sha256_of_file(p)
                load_file(p)
                self.assertEqual(sha256_of_file(p), h)


class FinerTimeframeRefusal(unittest.TestCase):
    def test_daily_cannot_be_split_into_finer(self):
        # 'D' on daily is a no-op, but a finer request is impossible. Only D/W/M/Q exist, so check
        # weekly data cannot become daily.
        weekly = _helpers.synthetic_ohlc(60, freq="W")
        with self.assertRaises(TimeframeError):
            resample_ohlc(weekly, "D")


if __name__ == "__main__":
    unittest.main(verbosity=2)
