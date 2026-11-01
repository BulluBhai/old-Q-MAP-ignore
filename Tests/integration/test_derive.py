"""Derived timeframes from registered daily data: aggregation rules, look-ahead protection, provenance, refusals."""

from __future__ import annotations

from datetime import date

import pyarrow as pa
import pytest

from fixtures.builders import HEADER, daily_rows, intraday_utc, ohlcv, write_delimited
from fixtures.profiles import do_ingest, make_profile
from qmap.data_engine.derive import (FLAG_PERIOD_MAY_BE_INCOMPLETE, PROCESSING_VERSION, DerivationError,
                                     aggregate_daily, assess_derivation, derive_timeframe, period_bounds)
from qmap.storage.parquet_io import read_canonical, read_canonical_metadata
from qmap.storage.recovery import verify_registry


def _daily_table(days, rows, volume=True):
    return pa.table({
        "session_date": pa.array(days, type=pa.date32()),
        "open": [r[0] for r in rows], "high": [r[1] for r in rows], "low": [r[2] for r in rows],
        "close": [r[3] for r in rows],
        "volume": pa.array([r[4] for r in rows] if volume else [None] * len(rows), type=pa.float64()),
        "quality_flags": pa.array([0] * len(rows), type=pa.int64()),
    })


@pytest.mark.parametrize("d, tf, start, end", [
    (date(2026, 1, 7), "1W", date(2026, 1, 5), date(2026, 1, 11)),
    (date(2024, 2, 10), "1M", date(2024, 2, 1), date(2024, 2, 29)),  # leap year
    (date(2026, 11, 1), "1Q", date(2026, 10, 1), date(2026, 12, 31)),
    (date(2026, 5, 5), "1Y", date(2026, 1, 1), date(2026, 12, 31)),
    (date(2026, 1, 1), "1W", date(2025, 12, 29), date(2026, 1, 4)),  # ISO week crossing the year
])
def test_calendar_periods(d, tf, start, end):
    assert period_bounds(d, tf) == (start, end)


def test_weekly_aggregation_follows_ohlcv_conventions():
    days = [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 12), date(2026, 1, 13)]
    rows = [[10, 12, 9, 11, 100], [11, 15, 10, 14, 200], [14, 14, 8, 9, 300], [9, 10, 7, 8, 50], [8, 9, 6, 7, 60]]
    agg = aggregate_daily(_daily_table(days, rows), "1W")
    c = agg.columns
    assert c["open"] == [10, 9] and c["high"] == [15, 10] and c["low"] == [8, 6] and c["close"] == [9, 7]
    assert c["volume"] == [600, 110]
    # look-ahead protection: a bar is dated by the LAST session it contains, never the period start
    assert c["session_date"] == [date(2026, 1, 7), date(2026, 1, 13)]
    assert c["first_session_date"] == [date(2026, 1, 5), date(2026, 1, 12)]
    assert c["bars_in_period"] == [3, 2]
    # first week starts on its Monday and is not the last period -> not flagged; last week ends Tuesday -> flagged
    assert not c["quality_flags"][0] & FLAG_PERIOD_MAY_BE_INCOMPLETE
    assert c["quality_flags"][1] & FLAG_PERIOD_MAY_BE_INCOMPLETE
    assert agg.edge_flags == 1


def test_edge_period_flags_precisely():
    days = [date(2026, 1, 1), date(2026, 1, 30), date(2026, 2, 2), date(2026, 3, 2), date(2026, 3, 31)]
    flags = aggregate_daily(_daily_table(days, ohlcv(5)), "1M").columns["quality_flags"]
    assert [bool(f & FLAG_PERIOD_MAY_BE_INCOMPLETE) for f in flags] == [False, False, False]
    days = [date(2026, 1, 2), date(2026, 2, 2), date(2026, 3, 30)]
    flags = aggregate_daily(_daily_table(days, ohlcv(3)), "1M").columns["quality_flags"]
    assert [bool(f & FLAG_PERIOD_MAY_BE_INCOMPLETE) for f in flags] == [True, False, True]


def test_a_missing_volume_never_gives_a_partial_sum():
    days = [date(2026, 1, 5), date(2026, 1, 6)]
    t = _daily_table(days, [[1, 2, 1, 2, 10], [2, 3, 1, 2, 10]])
    t = t.set_column(t.schema.get_field_index("volume"), "volume", pa.array([10.0, None]))
    agg = aggregate_daily(t, "1W")
    assert agg.columns["volume"] == [None] and agg.volume_missing_periods == 1
    no_volume = aggregate_daily(_daily_table(days, [[1, 2, 1, 2, 0]] * 2, volume=False), "1W")
    assert no_volume.columns["volume"] == [None] and no_volume.volume_missing_periods == 0


def test_more_than_one_bar_per_date_is_refused():
    d = date(2026, 1, 5)
    with pytest.raises(DerivationError, match="one bar per trading date"):
        aggregate_daily(_daily_table([d, d], ohlcv(2)), "1W")


def test_derive_registers_a_dataset_with_full_provenance(settings, db, run, src):
    res = do_ingest(run, write_delimited(src / "d.csv", HEADER, daily_rows(40)))
    daily = res.dataset_ids[0]
    out = derive_timeframe(run, daily, "1W")
    assert out.outcome == "created", out.message
    row = db.one("SELECT * FROM datasets WHERE dataset_id = ?", (out.dataset_id,))
    assert (row["layer"], row["timeframe"], row["parent_dataset_id"], row["processing_version"]) == (
        "timeframe", "1W", daily, PROCESSING_VERSION)
    assert row["relative_path"].startswith("Timeframe_Data/NSE/TEST/1W/") and row["row_count"] == 8
    deriv = db.one("SELECT * FROM dataset_derivations WHERE dataset_id = ?", (out.dataset_id,))
    assert deriv["source_dataset_id"] == daily and deriv["run_id"] == run.run_id
    assert db.one("SELECT 1 FROM run_inputs WHERE run_id = ? AND dataset_id = ?", (run.run_id, daily))
    meta = read_canonical_metadata(settings.data_path(row["relative_path"]))
    assert meta["method"] == "ohlcv_period_aggregation" and meta["source_dataset_id"] == daily
    table = read_canonical(settings.data_path(row["relative_path"])).to_pydict()
    daily_t = read_canonical(settings.data_path(
        db.one("SELECT relative_path FROM datasets WHERE dataset_id = ?", (daily,))["relative_path"])).to_pydict()
    assert table["open"][0] == daily_t["open"][0] and table["close"][-1] == daily_t["close"][-1]
    assert max(daily_t["high"]) == max(table["high"]) and min(daily_t["low"]) == min(table["low"])
    assert sum(daily_t["volume"]) == pytest.approx(sum(table["volume"]))
    assert not verify_registry(settings, db).checksum_mismatches


def test_deriving_again_reuses_and_never_duplicates(db, run, src):
    daily = do_ingest(run, write_delimited(src / "d.csv", HEADER, daily_rows(20))).dataset_ids[0]
    first = derive_timeframe(run, daily, "1M")
    again = derive_timeframe(run, daily, "1M")
    assert again.outcome == "reused" and again.dataset_id == first.dataset_id
    assert db.one("SELECT COUNT(*) FROM datasets WHERE layer = 'timeframe'")[0] == 1


@pytest.mark.parametrize("tf", ["1W", "1M", "1Q", "1Y"])
def test_every_derived_timeframe_can_be_built(run, src, tf):
    daily = do_ingest(run, write_delimited(src / "d.csv", HEADER, daily_rows(60))).dataset_ids[0]
    assert derive_timeframe(run, daily, tf).ok


def test_intraday_source_is_refused_with_a_reason(settings, db, run, src):
    times = intraday_utc(30, step_minutes=5)
    rows = [[t.isoformat()] + r for t, r in zip(times, ohlcv(30))]
    profile = make_profile(instrument={"exchange_from": "fixed", "exchange": "NSE", "symbol_from": "fixed",
                                       "symbol": "INTRA", "timeframe": "5m"},
                           datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, write_delimited(src / "i.csv", HEADER, rows), profile)
    assert res.outcome == "accepted", res.message
    a = assess_derivation(settings, db, res.dataset_ids[0], "1W")
    assert not a.allowed and "DAILY" in a.blockers[0]
    assert derive_timeframe(run, res.dataset_ids[0], "1W").outcome == "refused"


def test_unknown_timeframe_and_raw_source_are_refused(settings, db, run, src):
    res = do_ingest(run, write_delimited(src / "d.csv", HEADER, daily_rows(10)))
    assert not assess_derivation(settings, db, res.dataset_ids[0], "1D").allowed
    assert not assess_derivation(settings, db, res.raw_dataset_id, "1W").allowed
