"""Automatic interpretation (Blueprint v1.3 §8.5.4; audit rules A-1 ... A-9).

Every READY result is also loaded through the normal ingestion pipeline and the stored values are compared with the
values written into the fixture, so "interpreted" always means "read correctly", not just "a profile was produced".
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pyarrow.parquet as pq
import pytest

from fixtures.builders import HEADER, intraday_utc, ohlcv, weekdays, write_delimited, write_parquet, write_xlsx
from qmap.data_engine import auto_interpret as A
from qmap.data_engine.ingest import ingest_file

IST = timezone(timedelta(hours=5, minutes=30))
H7 = ["time", "open", "high", "low", "close", "Volume", "Net Volume"]


def _rows7(n, seed=1):
    return [r + [(-1) ** i * (i * 7 + 3)] for i, r in enumerate(ohlcv(n, seed))]  # Net Volume can be negative


def _load(run, path, interp):
    o = interp.overrides
    return ingest_file(run, path, interp.profile, exchange=o.get("exchange"), symbol=o.get("symbol"),
                       timeframe=o.get("timeframe"))


def _stored(settings, db, dataset_id):
    rel = db.one("SELECT relative_path FROM datasets WHERE dataset_id = ?", (dataset_id,))[0]
    return pq.read_table(settings.data_path(rel))


# ---- 2, 6, 8, 9: headered CSV, names, extra fields -------------------------------------------------------------

def test_headered_csv_with_iso_offsets_is_read_and_loaded_exactly(settings, run, db, src):
    times = [t.astimezone(IST) for t in intraday_utc(60, step_minutes=5)]
    rows = _rows7(60)
    p = write_delimited(src / "NSE_NIFTY, 5.csv", H7, [[t.isoformat()] + r for t, r in zip(times, rows)])
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata")
    assert it.status == A.READY, it.message
    assert it.overrides == {"exchange": "NSE", "symbol": "NIFTY", "timeframe": "5m"}
    assert it.profile.status == "auto" and it.profile.profile_id.startswith("auto_")
    assert it.decisions["mapping"]["volume"] == {"position": 5, "name": "Volume"}
    res = _load(run, p, it)
    assert res.outcome == "accepted", res.message
    t = _stored(settings, db, res.dataset_ids[0])
    assert t.column("close").to_pylist() == [r[3] for r in rows]
    assert t.column("volume").to_pylist() == [float(r[4]) for r in rows]
    assert t.column("x_net_volume").to_pylist() == [str(r[5]) for r in rows]  # kept, not used as volume
    assert t.column("timestamp_utc").to_pylist()[0] == intraday_utc(1)[0]


@pytest.mark.parametrize("names", [
    ["Date", "Open", "High", "Low", "Close", "Volume"],
    ["DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOL"],
    ["timestamp", "o", "h", "l", "c", "qty"],
    ["trade_date", "open_price", "high_price", "low_price", "close_price", "quantity"],
])
def test_supported_column_names_are_mapped(settings, src, names):
    days = weekdays(10)
    p = write_delimited(src / "NSE_ABC.csv", names, [[d.isoformat()] + r for d, r in zip(days, ohlcv(10))])
    it = A.interpret_file(p, settings)
    assert it.status == A.READY, it.message
    assert {k: v["position"] for k, v in it.decisions["mapping"].items()} == \
        {"date": 0, "open": 1, "high": 2, "low": 3, "close": 4, "volume": 5}


def test_close_beats_last_and_adj_close_is_never_close(settings, src):
    p = write_delimited(src / "NSE_ABC.csv", ["Date", "Open", "High", "Low", "Adj Close", "Last", "Close"],
                        [[d.isoformat()] + r[:3] + [r[3] * 0.9, r[3], r[3]] for d, r in zip(weekdays(10), ohlcv(10))])
    it = A.interpret_file(p, settings)
    assert it.status == A.READY and it.decisions["mapping"]["close"]["name"] == "Close"


def test_two_candidate_columns_for_one_field_are_rejected(settings, src):
    p = write_delimited(src / "NSE_ABC.csv", ["date", "open", "high", "low", "close", "Volume", "vol"],
                        [[d.isoformat()] + r + [r[4]] for d, r in zip(weekdays(10), ohlcv(10))])
    it = A.interpret_file(p, settings)
    assert it.status == A.REJECTED and "volume" in it.message


# ---- 3, 4, 5: TXT, Excel, Parquet ----------------------------------------------------------------------------------

def test_semicolon_text_file(settings, run, src):
    p = write_delimited(src / "NSE_ABC.txt", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(10), ohlcv(10))],
                        delimiter=";")
    it = A.interpret_file(p, settings)
    assert it.status == A.READY and it.decisions["delimiter"] == ";"
    assert _load(run, p, it).outcome == "accepted"


def test_excel_with_date_cells(settings, run, db, src):
    days = weekdays(12)
    rows = ohlcv(12)
    p = write_xlsx(src / "NSE_ABC.xlsx", H7[:6], [[datetime(d.year, d.month, d.day)] + r for d, r in zip(days, rows)])
    it = A.interpret_file(p, settings)
    assert it.status == A.READY and it.overrides["timeframe"] == "1D"
    res = _load(run, p, it)
    assert res.outcome == "accepted"
    assert _stored(settings, db, res.dataset_ids[0]).column("session_date").to_pylist() == days


def test_parquet_with_naive_timestamps_uses_the_confirmed_market_zone(settings, run, db, src):
    utc = intraday_utc(30)
    rows = ohlcv(30)
    naive_ist = [t.astimezone(IST).replace(tzinfo=None) for t in utc]
    p = write_parquet(src / "NSE_BANKNIFTY_1m.parquet", {"Date": naive_ist, "Open": [r[0] for r in rows],
                                                          "High": [r[1] for r in rows], "Low": [r[2] for r in rows],
                                                          "Close": [r[3] for r in rows], "Volume": [r[4] for r in rows]})
    assert A.interpret_file(p, settings).questions[0].key == "market_timezone"  # never assumed
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata")
    assert it.status == A.READY and it.overrides["timeframe"] == "1m"
    res = _load(run, p, it)
    assert _stored(settings, db, res.dataset_ids[0]).column("timestamp_utc").to_pylist() == utc


# ---- 7: headerless ------------------------------------------------------------------------------------------------

def test_headerless_file_uses_the_documented_positional_rule(settings, run, db, src):
    rows = _rows7(10)
    p = write_delimited(src / "NSE_ABC.csv", None, [[d.isoformat()] + r for d, r in zip(weekdays(10), rows)])
    it = A.interpret_file(p, settings)
    assert it.status == A.READY and it.decisions["header"] is False
    assert it.decisions["mapping"]["volume"]["position"] == 5
    assert any(e.startswith("A-5") for e in it.evidence)
    res = _load(run, p, it)
    assert _stored(settings, db, res.dataset_ids[0]).column("open").to_pylist() == [r[0] for r in rows]  # row 1 is data


def test_headerless_file_whose_columns_do_not_behave_like_ohlc_is_rejected(settings, src):
    rows = [[r[0], r[2], r[1], r[3], r[4]] for r in ohlcv(10)]  # high and low swapped
    p = write_delimited(src / "NSE_ABC.csv", None, [[d.isoformat()] + r for d, r in zip(weekdays(10), rows)])
    it = A.interpret_file(p, settings)
    assert it.status == A.REJECTED and "order cannot be confirmed" in it.message


def test_headerless_sixth_column_with_negative_values_is_not_volume(settings, src):
    rows = [r[:4] + [-5 if i % 2 else 7] for i, r in enumerate(ohlcv(10))]
    p = write_delimited(src / "NSE_ABC.csv", None, [[d.isoformat()] + r for d, r in zip(weekdays(10), rows)])
    it = A.interpret_file(p, settings)
    assert it.status == A.READY and "volume" not in it.decisions["mapping"]


# ---- 10, 11: dates ----------------------------------------------------------------------------------------------

def test_day_month_two_digit_year_with_time_is_resolved_by_file_order(settings, run, db, src):
    """'09-01-15 09:15' style: DD-MM-YY and YY-MM-DD both parse every value; only DD-MM-YY keeps file order."""
    start = datetime(2015, 1, 9, 9, 15)
    times = [start + timedelta(days=d, minutes=m) for d in range(25) for m in range(0, 60, 15)]
    rows = ohlcv(len(times))
    p = write_delimited(src / "NSE_ABC.csv", HEADER, [[t.strftime("%d-%m-%y %H:%M")] + r for t, r in zip(times, rows)])
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata")
    assert it.status == A.READY, it.message
    assert it.decisions["date_layout"] == "format:%d-%m-%y %H:%M" and it.overrides["timeframe"] == "15m"
    res = _load(run, p, it)
    t = _stored(settings, db, res.dataset_ids[0])
    assert t.column("session_date").to_pylist()[0] == date(2015, 1, 9)
    assert t.column("timestamp_utc").to_pylist()[0] == datetime(2015, 1, 9, 3, 45, tzinfo=timezone.utc)


def test_dates_that_fit_day_first_and_month_first_ask_the_user(settings, run, src):
    days = [date(2026, 1, 1) + timedelta(days=31 * i) for i in range(10)]
    p = write_delimited(src / "NSE_ABC.csv", HEADER, [[d.strftime("%d/%m/%Y")] + r for d, r in zip(days, ohlcv(10))])
    it = A.interpret_file(p, settings)
    assert it.status == A.NEEDS_ANSWER and it.profile is None
    q = next(q for q in it.questions if q.key == "date_format")
    assert set(q.options) == {"format:%d/%m/%Y", "format:%m/%d/%Y"}
    it2 = A.interpret_file(p, settings, answers={"date_format": "format:%d/%m/%Y", "timeframe": "1M"})
    assert it2.status == A.READY and any("chosen by the user" in e for e in it2.evidence)
    assert it2.signature == it.signature  # the answer is tied to this structure


def test_an_answer_that_does_not_fit_the_data_is_not_used(settings, src):
    days = [date(2026, 1, 1) + timedelta(days=31 * i) for i in range(10)]
    p = write_delimited(src / "NSE_ABC.csv", HEADER, [[d.strftime("%d/%m/%Y")] + r for d, r in zip(days, ohlcv(10))])
    it = A.interpret_file(p, settings, answers={"date_format": "iso"})
    assert it.status == A.NEEDS_ANSWER


def test_unix_seconds_and_milliseconds(settings, src):
    utc = intraday_utc(20)
    for unit, mult in (("unix_s", 1), ("unix_ms", 1000)):
        p = write_delimited(src / f"NSE_ABC_{unit}.csv", HEADER,
                            [[int(t.timestamp()) * mult] + r for t, r in zip(utc, ohlcv(20))])
        it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata")
        assert it.status == A.READY and it.decisions["date_layout"] == unit


def test_unreadable_dates_are_rejected_with_the_supported_layouts(settings, src):
    p = write_delimited(src / "NSE_ABC.csv", HEADER, [["Mon 5th"] + r for r in ohlcv(5)])
    it = A.interpret_file(p, settings)
    assert it.status == A.REJECTED and "Supported" in it.message


# ---- A-8, A-9: identity and timeframe -------------------------------------------------------------------------------

def test_identity_is_asked_when_neither_the_file_nor_its_name_gives_it(settings, src):
    """With file-name identification switched OFF for the folder, an unidentified file is asked about. With it ON (the
    default since DQ-8), the cleaned name is a provisional identity with a warning."""
    p = write_delimited(src / "csv headers std.csv", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(10), ohlcv(10))])
    it = A.interpret_file(p, settings, symbol_from_filename=False)
    assert [q.key for q in it.questions] == ["identity"]
    assert A.interpret_file(p, settings, symbol_from_filename=False,
                            answers={"exchange": "nse", "symbol": "nifty"}).overrides["symbol"] == "NIFTY"
    it = A.interpret_file(p, settings)
    assert it.status == A.READY and it.overrides["symbol"] == "CSV_HEADERS_STD"
    assert any(w.startswith("Provisional instrument CSV_HEADERS_STD") for w in it.warnings)


def test_unknown_exchange_prefix_in_a_name_is_not_identity(settings, src):
    p = write_delimited(src / "CSV_HEADERS.csv", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(10), ohlcv(10))])
    assert A.interpret_file(p, settings, symbol_from_filename=False).questions[0].key == "identity"
    it = A.interpret_file(p, settings)  # "CSV" is never taken as an exchange; the whole name is provisional
    assert it.overrides["exchange"] == "NSE" and it.overrides["symbol"] == "CSV_HEADERS" and it.warnings


def test_plain_symbol_file_names_only_when_enabled_for_the_source(settings, src):
    p = write_delimited(src / "RELIANCE.csv", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(10), ohlcv(10))])
    assert A.interpret_file(p, settings, default_exchange="NSE", symbol_from_filename=False).status == A.NEEDS_ANSWER
    it = A.interpret_file(p, settings, default_exchange="NSE")  # ON by default since DQ-8
    assert it.status == A.READY and it.overrides["symbol"] == "RELIANCE"


def test_symbol_column_is_content_and_a_contradicting_name_is_reported(settings, src):
    rows = [[d.isoformat(), "INFY"] + r for d, r in zip(weekdays(10), ohlcv(10))]
    ok = write_delimited(src / "data.csv", ["date", "symbol", "open", "high", "low", "close", "volume"], rows)
    it = A.interpret_file(ok, settings, default_exchange="NSE")
    assert it.status == A.READY and it.overrides == {"exchange": "NSE", "timeframe": "1D"}
    bad = write_delimited(src / "NSE_TCS.csv", ["date", "symbol", "open", "high", "low", "close", "volume"], rows)
    it = A.interpret_file(bad, settings)  # DQ-8: reported with both values, the column is used (never overridden)
    assert it.status == A.READY and "symbol" not in it.overrides
    assert any("says symbol TCS" in w and "INFY" in w for w in it.warnings)


def test_a_file_name_timeframe_that_contradicts_the_data_is_reported_not_used(settings, src):
    p = write_delimited(src / "NSE_ABC, 1D.csv", HEADER,
                        [[t.isoformat()] + r for t, r in zip(intraday_utc(30, step_minutes=5), ohlcv(30))])
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata")  # DQ-7: the data decide, the name is reported
    assert it.status == A.READY and it.overrides["timeframe"] == "5m"
    assert any("file name says 1D" in w for w in it.warnings)


@pytest.mark.parametrize("step, expected", [(1, "1m"), (15, "15m"), (60, "1h")])
def test_intraday_timeframe_from_the_bar_interval(settings, src, step, expected):
    p = write_delimited(src / "NSE_ABC.csv", HEADER,
                        [[t.isoformat()] + r for t, r in zip(intraday_utc(20, step_minutes=step), ohlcv(20))])
    assert A.interpret_file(p, settings, market_timezone="Asia/Kolkata").overrides["timeframe"] == expected


def test_weekly_and_monthly_bars(settings, src):
    for gap, tf in ((7, "1W"), (30, "1M")):
        days = [date(2025, 1, 6) + timedelta(days=gap * i) for i in range(10)]
        p = write_delimited(src / f"NSE_ABC_{tf}.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, ohlcv(10))])
        assert A.interpret_file(p, settings).overrides.get("timeframe") == tf


def test_too_few_bars_to_tell_the_timeframe_is_asked(settings, src):
    p = write_delimited(src / "NSE_ABC.csv", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(2), ohlcv(2))])
    assert A.interpret_file(p, settings).questions[0].key == "timeframe"


# ---- 12: unsupported and malformed --------------------------------------------------------------------------------

@pytest.mark.parametrize("content, words", [
    (b"%PDF-1.4 hello", "PDF"),
    (b'{"a": 1}', "JSON"),
    (b"", "empty"),
    (b"date,close\n2026-01-05,10\n2026-01-06,11\n", "separated"),
    (b"date,open,high,low,close\n2026-01-05,1,2,0.5,1\n2026-01-06,1,2\n", "separated"),
])
def test_unsupported_or_malformed_files_are_rejected_with_a_reason(settings, src, content, words):
    p = src / "NSE_ABC.csv"
    p.write_bytes(content)
    it = A.interpret_file(p, settings)
    assert it.status == A.REJECTED and words in it.message


def test_same_layout_gives_the_same_profile_and_a_different_layout_does_not(settings, src):
    a = write_delimited(src / "NSE_A.csv", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(10), ohlcv(10, 1))])
    b = write_delimited(src / "NSE_B.csv", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(12), ohlcv(12, 2))])
    c = write_delimited(src / "NSE_C.csv", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(10), ohlcv(10))],
                        delimiter=";")
    pa_, pb, pc = (A.interpret_file(p, settings).profile for p in (a, b, c))
    assert pa_.profile_id == pb.profile_id and pa_.content_sha256 == pb.content_sha256
    assert pc.profile_id != pa_.profile_id


def test_interpretation_never_changes_the_file(settings, src):
    p = write_delimited(src / "NSE_ABC.csv", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(10), ohlcv(10))])
    before = (p.read_bytes(), p.stat().st_mtime_ns)
    A.interpret_file(p, settings)
    assert (p.read_bytes(), p.stat().st_mtime_ns) == before
