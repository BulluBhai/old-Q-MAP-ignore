"""Date/time parsing: every rule explicit; ambiguity reported, never guessed."""

from datetime import date, datetime, timezone

import pytest

from qmap.core.errors import IngestError
from qmap.data_engine.datetime_parse import parse_times
from qmap.data_engine.profiles import DatetimeSpec
from qmap.data_engine.results import Collector

TODAY = date(2026, 10, 31)
IST = "Asia/Kolkata"


def parse(settings, values, timeframe="1D", time_values=None, **spec):
    col = Collector()
    p = parse_times(values, DatetimeSpec(**spec), timeframe=timeframe, settings=settings, collector=col,
                    time_values=time_values, today=TODAY)
    return p, col


def bad_rows(col, check="datetime_parseable"):
    return col.rows_for(check)


# ---- ISO ---------------------------------------------------------------------------------------
def test_iso_dates(settings):
    p, col = parse(settings, ["2026-01-05", "2026-01-06"], kind="iso")
    assert p.session_dates == [date(2026, 1, 5), date(2026, 1, 6)] and not p.is_instant and not col.issues


def test_iso_timestamp_with_offset_converts_to_utc_and_derives_session_date(settings):
    p, col = parse(settings, ["2026-01-05T09:15:00+05:30", "2026-01-05T15:29:00+05:30"], "1m", kind="iso",
                   exchange_timezone=IST)
    assert p.ts_utc[0] == datetime(2026, 1, 5, 3, 45, tzinfo=timezone.utc)
    assert p.session_dates == [date(2026, 1, 5)] * 2
    assert p.provenance["source_utc_offsets"] == ["5:30:00"] and p.provenance["session_date_derived"]


def test_iso_z_suffix(settings):
    p, _ = parse(settings, ["2026-01-05T03:45:00Z"], "5m", kind="iso", exchange_timezone=IST)
    assert p.ts_utc[0] == datetime(2026, 1, 5, 3, 45, tzinfo=timezone.utc)


def test_session_date_uses_exchange_zone_not_utc(settings):
    # 20:00 UTC on 4 Jan is already 5 Jan in India
    p, _ = parse(settings, ["2026-01-04T20:00:00+00:00"], "1D", kind="iso", exchange_timezone=IST)
    assert p.session_dates == [date(2026, 1, 5)]


def test_naive_iso_timestamp_uses_declared_zone(settings):
    p, _ = parse(settings, ["2026-01-05T09:15:00"], "1m", kind="iso", timezone=IST, exchange_timezone=IST)
    assert p.ts_utc[0] == datetime(2026, 1, 5, 3, 45, tzinfo=timezone.utc)
    assert p.provenance["timezone_applied"] == IST


def test_naive_timestamp_without_declared_zone_is_an_error_not_a_guess(settings):
    with pytest.raises(IngestError) as e:
        parse(settings, ["2026-01-05T09:15:00"], "1m", kind="iso", exchange_timezone=IST)
    assert e.value.code == "E_TZ_REQUIRED" and e.value.check == "timezone_declared"


def test_instants_need_an_exchange_zone(settings):
    with pytest.raises(IngestError) as e:
        parse(settings, ["2026-01-05T09:15:00+05:30"], "1m", kind="iso")
    assert e.value.code == "E_TZ_REQUIRED"


def test_mixed_offset_and_naive_is_rejected(settings):
    with pytest.raises(IngestError) as e:
        parse(settings, ["2026-01-05T09:15:00+05:30", "2026-01-05T09:20:00"], "5m", kind="iso", timezone=IST,
              exchange_timezone=IST)
    assert e.value.code == "E_MIXED_TIMEZONE"


def test_mixed_date_and_datetime_is_rejected(settings):
    with pytest.raises(IngestError) as e:
        parse(settings, ["2026-01-05", "2026-01-06T09:15:00+05:30"], "1D", kind="iso", exchange_timezone=IST)
    assert e.value.code == "E_MIXED_DATETIME"


@pytest.mark.parametrize("value", ["05/01/2026", "2026/01/05", "5 Jan 2026", "20260105", "2026-1-5", "2026-13-01"])
def test_non_iso_text_is_flagged_not_guessed(settings, value):
    p, col = parse(settings, ["2026-01-05", value], kind="iso")
    assert bad_rows(col) == [2] and p.session_dates[1] is None


def test_missing_value_flagged(settings):
    p, col = parse(settings, ["2026-01-05", "", None], kind="iso")
    assert bad_rows(col) == [2, 3]


def test_intraday_timeframe_with_date_only_values_is_rejected(settings):
    with pytest.raises(IngestError) as e:
        parse(settings, ["2026-01-05"], "5m", kind="iso")
    assert e.value.code == "E_TIMEFRAME_MISMATCH"


# ---- explicit formats ------------------------------------------------------------------------------
def test_yyyymmdd_text_and_integer_agree(settings):
    a, _ = parse(settings, ["20260105", "20260106"], kind="format", format="%Y%m%d")
    b, _ = parse(settings, [20260105, 20260106.0], kind="format", format="%Y%m%d")
    assert a.session_dates == b.session_dates == [date(2026, 1, 5), date(2026, 1, 6)]


def test_ddmmyy_with_declared_pivot(settings):
    p, col = parse(settings, ["050126", "311225"], kind="format", format="%d%m%y", two_digit_year_pivot=69)
    assert p.session_dates == [date(2026, 1, 5), date(2025, 12, 31)] and not bad_rows(col)


def test_ddmmyy_integer_lost_its_leading_zero_only_parses_when_padding_is_declared(settings):
    p, col = parse(settings, [50126], kind="format", format="%d%m%y", two_digit_year_pivot=69)
    assert bad_rows(col) == [1]  # '50126' is ambiguous; it is not guessed
    p, col = parse(settings, [50126, 311225], kind="format", format="%d%m%y", two_digit_year_pivot=69, zero_pad_width=6)
    assert p.session_dates == [date(2026, 1, 5), date(2025, 12, 31)] and not bad_rows(col)
    assert p.provenance["zero_padded_values"] == 1


def test_dd_mm_yy_day_first_is_verified_by_a_day_over_12(settings):
    p, col = parse(settings, ["25-09-26", "01-10-26", "28-09-26"], kind="format", format="%d-%m-%y",
                   two_digit_year_pivot=69)
    assert p.session_dates[0] == date(2026, 9, 25) and p.session_dates[1] == date(2026, 10, 1)
    assert not p.date_order_unverified and p.ambiguous_rows == set()
    assert p.provenance["order_audit"]["verified"]


def test_dd_mm_yy_with_all_days_12_or_less_is_flagged_unverified(settings):
    p, col = parse(settings, ["01-10-26", "05-10-26", "07-10-26", "06-06-26"], kind="format", format="%d-%m-%y",
                   two_digit_year_pivot=69)
    assert p.date_order_unverified
    assert p.ambiguous_rows == {0, 1, 2}  # 06-06-26 reads the same either way
    assert col.count("date_order_unverified") == 1


def test_same_text_under_the_two_declared_orders_gives_different_dates(settings):
    day_first, _ = parse(settings, ["03-04-26"], kind="format", format="%d-%m-%y", two_digit_year_pivot=69)
    month_first, _ = parse(settings, ["03-04-26"], kind="format", format="%m-%d-%y", two_digit_year_pivot=69)
    assert day_first.session_dates != month_first.session_dates  # never auto-corrected either way


def test_value_contradicting_the_declared_order_is_flagged(settings):
    p, col = parse(settings, ["05-13-25", "05-12-25"], kind="format", format="%d-%m-%y", two_digit_year_pivot=69)
    assert bad_rows(col) == [1] and p.session_dates[1] == date(2025, 12, 5)


def test_unpadded_values_are_not_silently_accepted(settings):
    p, col = parse(settings, ["5-1-26"], kind="format", format="%d-%m-%y", two_digit_year_pivot=69)
    assert bad_rows(col) == [1]


def test_pivot_decides_the_century_and_the_plausible_range_catches_a_wrong_one(settings):
    p, col = parse(settings, ["05-01-70"], kind="format", format="%d-%m-%y", two_digit_year_pivot=69)  # 1970
    assert col.rows_for("date_in_range") == [1]
    p, col = parse(settings, ["05-01-70"], kind="format", format="%d-%m-%y", two_digit_year_pivot=71)  # 2070
    assert col.rows_for("date_in_range") == [1]


def test_separate_date_and_time_columns(settings):
    p, col = parse(settings, ["2026-01-05", "2026-01-05"], "5m", time_values=["09:15:00", "09:20:00"], kind="iso",
                   time_format="%H:%M:%S", timezone=IST, exchange_timezone=IST)
    assert p.ts_utc[1] == datetime(2026, 1, 5, 3, 50, tzinfo=timezone.utc) and not col.issues
    assert p.provenance["date_and_time_columns_combined"]


def test_bad_time_value_is_flagged(settings):
    p, col = parse(settings, ["2026-01-05", "2026-01-05"], "5m", time_values=["09:15:00", "9:20"], kind="iso",
                   time_format="%H:%M:%S", timezone=IST, exchange_timezone=IST)
    assert bad_rows(col) == [2]


def test_date_and_time_in_one_field(settings):
    p, _ = parse(settings, ["05-01-2026 09:15"], "5m", kind="format", format="%d-%m-%Y %H:%M", timezone=IST,
                 exchange_timezone=IST)
    assert p.ts_utc[0] == datetime(2026, 1, 5, 3, 45, tzinfo=timezone.utc)


# ---- Unix timestamps ---------------------------------------------------------------------------------
def test_unix_seconds_and_milliseconds_give_the_same_instants(settings):
    s, _ = parse(settings, ["1738381500", 1738554300], "1D", kind="unix_s", exchange_timezone=IST)
    ms, _ = parse(settings, ["1738381500000", 1738554300000], "1D", kind="unix_ms", exchange_timezone=IST)
    assert s.ts_utc == ms.ts_utc
    assert s.session_dates == [date(2025, 2, 1), date(2025, 2, 3)]  # 09:15 IST bars


def test_unix_milliseconds_declared_as_seconds_is_an_error_with_a_hint(settings):
    p, col = parse(settings, ["1738381500000"], "1D", kind="unix_s", exchange_timezone=IST)
    msgs = [i.message for i in col.issues]
    assert bad_rows(col) == [1] and "MILLISECONDS" in msgs[0]


def test_unix_seconds_declared_as_milliseconds_is_an_error_with_a_hint(settings):
    p, col = parse(settings, ["1738381500"], "1D", kind="unix_ms", exchange_timezone=IST)
    assert col.rows_for("date_in_range") == [1]
    assert "SECONDS" in col.issues[0].message


def test_unix_non_numeric_value_flagged(settings):
    p, col = parse(settings, ["1738381500", "abc", "1e400", "nan"], "1D", kind="unix_s", exchange_timezone=IST)
    assert bad_rows(col) == [2, 3, 4]


def test_unix_mixed_precision_warns(settings):
    p, col = parse(settings, ["1738381500", "1738381500000"], "1D", kind="unix_s", exchange_timezone=IST)
    assert any(i.severity == "warning" and "mixed digit lengths" in i.message for i in col.issues)


# ---- Excel serial and native values ------------------------------------------------------------------
def test_excel_serial_dates_and_times(settings):
    p, _ = parse(settings, [46027, 46028.0], "1D", kind="excel_serial")
    assert p.session_dates == [date(2026, 1, 5), date(2026, 1, 6)] and not p.is_instant
    p, _ = parse(settings, [46027.385417, 46027.388889], "5m", kind="excel_serial", timezone=IST, exchange_timezone=IST)
    assert p.ts_utc[0] == datetime(2026, 1, 5, 3, 45, tzinfo=timezone.utc)
    assert p.provenance["excel_serial_has_time_of_day"]


def test_native_datetime_with_declared_precision(settings):
    p, _ = parse(settings, [datetime(2026, 1, 5), datetime(2026, 1, 6)], "1D", kind="native", precision="date")
    assert p.session_dates == [date(2026, 1, 5), date(2026, 1, 6)]
    p, _ = parse(settings, [date(2026, 1, 5)], "1D", kind="native", precision="date")
    assert p.session_dates == [date(2026, 1, 5)]
    p, _ = parse(settings, [datetime(2026, 1, 5, 9, 15)], "5m", kind="native", precision="datetime", timezone=IST,
                 exchange_timezone=IST)
    assert p.ts_utc[0] == datetime(2026, 1, 5, 3, 45, tzinfo=timezone.utc)
    p, _ = parse(settings, [datetime(2026, 1, 5, 3, 45, tzinfo=timezone.utc)], "5m", kind="native",
                 precision="datetime", exchange_timezone=IST)
    assert p.session_dates == [date(2026, 1, 5)]


def test_native_with_time_but_date_precision_is_flagged(settings):
    p, col = parse(settings, [datetime(2026, 1, 5, 9, 15)], "1D", kind="native", precision="date")
    assert bad_rows(col) == [1]


def test_native_text_is_flagged(settings):
    p, col = parse(settings, ["2026-01-05"], "1D", kind="native", precision="date")
    assert bad_rows(col) == [1]


# ---- DST and plausible range ----------------------------------------------------------------------
def test_ambiguous_and_nonexistent_local_times_are_flagged_not_guessed(settings):
    p, col = parse(settings, ["2026-11-01T01:30:00", "2026-03-08T02:30:00", "2026-06-01T10:00:00"], "1h",
                   kind="iso", timezone="America/New_York", exchange_timezone="America/New_York")
    assert bad_rows(col) == [1, 2] and p.ts_utc[2] is not None


@pytest.mark.parametrize("value", ["1970-01-01", "2026-11-05", "1989-12-31"])
def test_implausible_dates_flagged(settings, value):
    p, col = parse(settings, [value], kind="iso")
    assert col.rows_for("date_in_range") == [1]


def test_tomorrow_is_still_plausible(settings):
    p, col = parse(settings, ["2026-11-01"], kind="iso")
    assert not col.issues
