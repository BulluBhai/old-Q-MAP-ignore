"""Regression tests for the findings of the owner's sample-file test (01-Nov-26).

All data here is SYNTHETIC (generated); only the layouts mirror the owner's samples. Results obtained with the
owner's actual files are reported separately, in docs/sample_file_testing/.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from fixtures.builders import HEADER, daily_rows, intraday_utc, ohlcv, write_delimited, write_xlsx
from fixtures.profiles import do_ingest, failed_names, make_profile, read_group
from qmap.data_engine.format_detect import detect_format
from qmap.data_engine.process import filename_identity_problem
from qmap.data_engine.profiles import load_profile
from qmap.data_engine.readers import read_source

IST = timezone(timedelta(hours=5, minutes=30))
NET_HEADER = HEADER + ["Net Volume"]
EXAMPLES = Path(__file__).resolve().parents[2] / "Configuration" / "source_profiles"
FROM_NAME = {"exchange_from": "filename_pattern", "symbol_from": "filename_pattern", "exchange": None, "symbol": None,
             "filename_pattern": "^(?P<exchange>[A-Za-z]+)_(?P<symbol>[A-Za-z0-9&]+)_"}


def iso_rows(n=12, step=5, seed=3):
    times = intraday_utc(n, step_minutes=step)
    return [[t.astimezone(IST).isoformat()] + r + [-(r[4] // 3)] for t, r in zip(times, ohlcv(n, seed))]


def iso_profile(**kw):
    base = dict(datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"},
                volume={"rule": "use_column", "column": "Volume", "preserved_not_volume": ["Net Volume"],
                        "requirement_set": "price_only"})
    base.update(kw)
    return make_profile(**base)


# ---- A. Exchange and symbol from the file name ------------------------------------------------------------
@pytest.mark.parametrize("name, fits", [("NSE_NIFTY_5m.csv", True), ("NSE_NIFTY_.csv", True),
                                        ("NSE_NIFTY, 1(1).csv", False), ("xls headers iso.csv", False),
                                        ("NIFTY.csv", False)])
def test_whether_a_file_name_fits_the_profile_pattern_is_known_before_loading(name, fits):
    prof = make_profile(instrument=FROM_NAME)
    problem = filename_identity_problem(prof, name)
    assert (problem is None) == fits
    if not fits:
        assert name in problem and "file-name pattern" in problem and "Rename the file" in problem


def test_a_profile_that_asks_for_identity_never_has_a_file_name_problem():
    prof = make_profile(instrument={"exchange_from": "ingest", "symbol_from": "ingest", "exchange": None, "symbol": None})
    assert filename_identity_problem(prof, "anything at all.csv") is None


def test_a_name_that_does_not_fit_is_rejected_with_advice_that_can_be_followed(src, run):
    p = write_delimited(src / "NSE_NIFTY, 1(1).csv", NET_HEADER, iso_rows())
    res = do_ingest(run, p, iso_profile(instrument={**FROM_NAME, "timeframe": "5m"}), exchange="NSE", symbol="NIFTY")
    assert res.outcome == "rejected" and failed_names(res) == {"instrument_declared"}
    assert "supply the value when ingesting" not in res.message  # impossible for a file-name profile (D2-26)
    assert "a value typed when loading is not used" in res.message and "Rename the file" in res.message
    assert "exchange_from and symbol_from = \"ingest\"" in res.message


def test_a_name_that_fits_still_gives_the_identity_from_the_name_not_from_what_was_typed(src, run, db):
    p = write_delimited(src / "NSE_NIFTY_5m.csv", NET_HEADER, iso_rows())
    res = do_ingest(run, p, iso_profile(instrument={**FROM_NAME, "timeframe": "5m"}), exchange="BSE", symbol="OTHER")
    assert res.outcome == "accepted", res.message
    assert dict(db.one("SELECT exchange, symbol FROM instruments")) == {"exchange": "NSE", "symbol": "NIFTY"}


# ---- B. Header setting that does not match the file ------------------------------------------------------
def test_a_headered_profile_on_a_headerless_file_says_the_first_row_looks_like_data(src, run):
    p = write_delimited(src / "noheader.csv", None, iso_rows())
    res = do_ingest(run, p, iso_profile(instrument={"timeframe": "5m"}))
    assert res.outcome == "rejected" and failed_names(res) == {"required_columns"}
    assert "looks like data, not column names" in res.message and "header = false" in res.message


def test_a_genuinely_missing_column_keeps_the_ordinary_message(src, run):
    p = write_delimited(src / "renamed.csv", ["when"] + NET_HEADER[1:], iso_rows())
    res = do_ingest(run, p, iso_profile(instrument={"timeframe": "5m"}))
    assert "Column 'time' for 'date' was not found. Columns found:" in res.message
    assert "looks like data" not in res.message


def test_a_headerless_profile_on_a_headered_file_warns_that_row_1_looks_like_names(src, run):
    p = write_delimited(src / "with_header.csv", NET_HEADER, iso_rows())
    prof = load_profile(EXAMPLES / "example_csv_noheaders_iso_offset.toml")
    res = do_ingest(run, p, prof, exchange="NSE", symbol="X", timeframe="5m")
    assert res.outcome == "rejected"  # row 1 is still data, as declared, and fails its own checks
    hint = [c for c in res.checks if c.name == "first_row_looks_like_header"][0]
    assert not hint.passed and hint.severity == "warning" and "'time'" in hint.detail


def test_a_correct_headerless_file_keeps_its_first_row_as_data(src, run, settings, db):
    rows = iso_rows()
    p = write_delimited(src / "noheader.csv", None, rows)
    prof = load_profile(EXAMPLES / "example_csv_noheaders_iso_offset.toml")
    res = do_ingest(run, p, prof, exchange="NSE", symbol="X", timeframe="5m")
    assert res.outcome == "accepted", res.message
    assert [c for c in res.checks if c.name == "first_row_looks_like_header"][0].passed
    g = read_group(settings, db, res.dataset_ids[0])
    assert len(g["open"]) == len(rows) and min(g["src_row"]) == 1 and g["open"][0] == rows[0][1]
    assert g["volume"][0] == rows[0][5] and g["x_col6"][0] == str(rows[0][6])  # Net Volume kept as source text, never volume


# ---- D. Physical format decides; a profile for another format is named as such ----------------------------
def test_a_profile_for_another_file_type_is_reported_as_a_mismatch_not_as_unsupported(src, run, db):
    p = write_xlsx(src / "book.xlsx", NET_HEADER, iso_rows())
    res = do_ingest(run, p, iso_profile(file={"header": True, "expected_format": "delimited_text"},
                                        instrument={"timeframe": "5m"}))
    assert res.outcome == "rejected" and "E_FORMAT_MISMATCH" in res.message
    assert failed_names(res) == {"format_matches_profile"}
    assert db.one("SELECT check_name FROM quality_checks WHERE passed = 0")["check_name"] == "format_matches_profile"


def test_an_excel_workbook_with_a_csv_ending_is_read_by_its_content(src):
    rows = iso_rows()
    p = write_xlsx(src / "book.xlsx", NET_HEADER, rows).rename(src / "really_excel.csv")
    det = detect_format(p)
    assert det.kind == "xlsx" and not det.extension_matches
    table = read_source(p, det.kind, iso_profile(file={"header": True, "expected_format": "xlsx"}).file)
    assert table.n_rows == len(rows) and table.names[:2] == ["time", "open"]


# ---- E. A daily/weekly/monthly timeframe on finer data is reported ----------------------------------------
def test_five_minute_bars_declared_daily_are_reported(src, run):
    p = write_delimited(src / "five_min.csv", NET_HEADER, iso_rows(n=150))  # two sessions of 75 five-minute bars
    res = do_ingest(run, p, iso_profile(instrument={"timeframe": "1D"}))
    chk = [c for c in res.checks if c.name == "one_bar_per_period"][0]
    assert not chk.passed and chk.severity == "warning" and "finer than the declared timeframe 1D" in chk.detail
    assert res.outcome == "accepted"  # report-only (owner decision pending); the timeframe is never changed


def test_one_bar_per_day_at_the_session_open_passes(src, run):
    times = [datetime(2026, 1, d, 3, 45, tzinfo=timezone.utc) for d in (5, 6, 7, 8, 9, 12)]  # Unix-style daily bars
    rows = [[int(t.timestamp())] + r for t, r in zip(times, ohlcv(6))]
    p = write_delimited(src / "daily_unix.csv", HEADER, rows)
    res = do_ingest(run, p, make_profile(datetime={"kind": "unix_s", "exchange_timezone": "Asia/Kolkata"}))
    assert res.outcome == "accepted", res.message
    assert [c for c in res.checks if c.name == "one_bar_per_period"][0].passed


def test_two_bars_in_one_week_declared_weekly_are_reported(src, run):
    rows = [[d.isoformat()] + r for d, r in zip([date(2026, 1, 5), date(2026, 1, 7), date(2026, 1, 12)], ohlcv(3))]
    p = write_delimited(src / "weekly.csv", HEADER, rows)
    res = do_ingest(run, p, make_profile(instrument={"timeframe": "1W"}))
    chk = [c for c in res.checks if c.name == "one_bar_per_period"][0]
    assert not chk.passed and "2026-W02: 2 bars" in chk.detail


def test_date_only_daily_data_is_left_to_the_duplicate_check(src, run):
    p = write_delimited(src / "daily.csv", HEADER, daily_rows(6))
    res = do_ingest(run, p, make_profile())
    assert res.outcome == "accepted" and not [c for c in res.checks if c.name == "one_bar_per_period"]


# ---- New example profiles: synthetic files in each layout load and keep every row --------------------------
@pytest.mark.parametrize("example, writer, header", [
    ("example_xlsx_headers_iso_offset", "xlsx", True),
    ("example_xlsx_noheaders_iso_offset", "xlsx", False),
    ("example_csv_noheaders_iso_offset", "csv", False),
])
def test_new_intraday_examples_load_synthetic_files_in_their_layout(src, run, settings, db, example, writer, header):
    rows = iso_rows(n=20)
    name = src / f"sample.{writer}"
    p = write_xlsx(name, NET_HEADER if header else None, rows) if writer == "xlsx" else \
        write_delimited(name, NET_HEADER if header else None, rows)
    res = do_ingest(run, p, load_profile(EXAMPLES / f"{example}.toml"), exchange="NSE", symbol="X", timeframe="5m")
    assert res.outcome == "accepted", res.message
    g = read_group(settings, db, res.dataset_ids[0])
    first = datetime.fromisoformat(rows[0][0]).astimezone(timezone.utc)
    assert len(g["open"]) == 20 and g["timestamp_utc"][0] == first and g["close"][-1] == rows[-1][4]


def test_new_daily_unix_example_loads_a_headerless_file(src, run, settings, db):
    times = [datetime(2026, 1, d, 3, 45, tzinfo=timezone.utc) for d in (5, 6, 7, 8, 9)]
    rows = [[int(t.timestamp())] + r + [-r[4]] for t, r in zip(times, ohlcv(5))]
    p = write_delimited(src / "daily.csv", None, rows)
    res = do_ingest(run, p, load_profile(EXAMPLES / "example_csv_noheaders_unix_seconds.toml"),
                    exchange="NSE", symbol="X", timeframe="1D")
    assert res.outcome == "accepted", res.message
    g = read_group(settings, db, res.dataset_ids[0])
    assert [d.isoformat() for d in g["session_date"]] == ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08",
                                                         "2026-01-09"]


def test_new_excel_date_example_loads_real_date_cells(src, run, settings, db):
    rows = [[datetime(2026, 1, d)] + r + [r[4] // 2] for d, r in zip((5, 6, 7, 8), ohlcv(4))]
    p = write_xlsx(src / "daily.xlsx", NET_HEADER, rows)
    res = do_ingest(run, p, load_profile(EXAMPLES / "example_xlsx_headers_native_date.toml"),
                    exchange="NSE", symbol="X", timeframe="1D")
    assert res.outcome == "accepted", res.message
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["session_date"][0] == date(2026, 1, 5) and g["timestamp_utc"][0] is None

