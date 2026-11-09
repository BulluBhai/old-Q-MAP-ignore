"""Files holding several instruments (review of 04-Nov-26, item C4).

DQ-7 measures the bar interval on the whole file before rows are grouped by instrument. Investigation showed two
misleading results: a short weekly instrument after a long daily one was registered as 1D (no warning), and two
instruments that are each consistent (one daily, one weekly) were both registered as MIXED. Now each instrument is
measured on its own rows as well; if any differs from the file's result nothing from the file is registered and the
check explains why. Files whose instruments all share the file's interval are unaffected.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from fixtures.profiles import do_ingest, make_profile

PROFILE = {"instrument": {"symbol_from": "column", "symbol_column": "Symbol", "symbol": None}}
START = date(2022, 1, 3)


def weekly(n):
    return [START + timedelta(days=7 * i) for i in range(n)]


def rows_for(symbol, days, seed):
    return [[symbol, d.isoformat()] + r for d, r in zip(days, ohlcv(len(days), seed))]


def ingest(src, run, name, rows, pid):
    p = write_delimited(src / name, ["Symbol"] + HEADER, rows)
    return do_ingest(run, p, make_profile(profile_id=pid, **PROFILE))


def check(res, name):
    return next((c for c in res.checks if c.name == name), None)


def cleaned(db):
    return [tuple(r) for r in db.query("SELECT i.symbol, d.timeframe FROM datasets d JOIN instruments i "
                                        "USING (instrument_id) WHERE d.layer = 'cleaned' ORDER BY i.symbol")]


@pytest.mark.parametrize("layout", ["stacked", "interleaved", "short_weekly_section"])
def test_instruments_with_different_intervals_are_refused(src, run, db, layout):
    a = rows_for("AAA", weekdays(120, START), 1)
    b = rows_for("BBB", weekly(120 if layout != "short_weekly_section" else 8), 2)
    rows = a + b if layout != "interleaved" else sorted(a + b, key=lambda r: (r[1], r[0]))
    res = ingest(src, run, f"{layout}.csv", rows, f"m_{layout}")
    assert res.outcome == "rejected"
    c = check(res, "instrument_timeframes_differ")
    assert c is not None and c.is_error and "NSE:AAA: 1D" in c.detail and "NSE:BBB: 1W" in c.detail
    assert "split the file" in c.detail.lower()
    assert cleaned(db) == []  # nothing registered: no instrument gets another one's timeframe, nor MIXED


def test_instruments_with_the_same_interval_are_loaded_as_before(src, run, db):
    rows = sorted(rows_for("AAA", weekdays(60, START), 1) + rows_for("BBB", weekdays(60, START), 2),
                  key=lambda r: (r[1], r[0]))
    res = ingest(src, run, "same.csv", rows, "m_same")
    assert res.outcome == "accepted", res.message
    assert check(res, "instrument_timeframes_agree").passed
    assert cleaned(db) == [("AAA", "1D"), ("BBB", "1D")]


def test_an_instrument_too_short_to_measure_is_reported_not_silently_assumed(src, run, db):
    rows = rows_for("AAA", weekdays(60, START), 1) + rows_for("BBB", weekdays(2, START), 2)
    res = ingest(src, run, "short.csv", rows, "m_short")
    assert res.outcome == "accepted", res.message
    c = check(res, "instrument_timeframe_not_verified")
    assert c is not None and not c.passed and not c.is_error and "NSE:BBB" in c.detail


def test_single_instrument_files_are_not_affected(src, run, db):
    rows = rows_for("AAA", weekdays(60, START), 1)
    res = ingest(src, run, "one.csv", rows, "m_one")
    assert res.outcome == "accepted"
    assert not any(c.name.startswith("instrument_timeframe") for c in res.checks)
