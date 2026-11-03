"""180-minute (3h) bars: CRYPTO_RIVERUSD, 180.csv (PR #9 acceptance finding F-02).

Superseded and settled by DQ-7 (03-Nov-26): timeframes are open-ended and measured from the data, so 180-minute bars
are 3h like any other interval. These tests keep the owner's RIVERUSD case covered. All data are SYNTHETIC.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from fixtures.builders import ohlcv, write_delimited
from qmap.catalog import (INTRADAY_TIMEFRAMES, TIMEFRAME_ORDER, DataRequirement, check_readiness, get_dataset,
                          list_datasets, timeframe_label)
from qmap.core.runs import run_context
from qmap.data_engine import auto_interpret as A
from qmap.data_engine import discovery as D
from qmap.data_engine.ingest import ingest_file
from qmap.data_engine.profiles import ALLOWED_TIMEFRAMES, INTRADAY_MINUTES, is_timeframe

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    f.mkdir()
    return f


def _source(settings, db, folder):
    return D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE")


def scan(settings, db, source):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, source.source_id)


def result_for(res, rel):
    return next(f for f in res.files if f[0] == rel)


def _load(run, path, interp):
    o = interp.overrides
    return ingest_file(run, path, interp.profile, exchange=o.get("exchange"), symbol=o.get("symbol"),
                       timeframe=o.get("timeframe"))


def _stored(settings, db, dataset_id):
    import pyarrow.parquet as pq

    rel = db.one("SELECT relative_path FROM datasets WHERE dataset_id = ?", (dataset_id,))[0]
    return pq.read_table(settings.data_path(rel))


@pytest.mark.parametrize("stem, expected", [("CRYPTO_RIVERUSD, 180", "3h"), ("ABC_180min", "3h"), ("ABC_3h", "3h"),
                                            ("ABC_3H", "3h")])
def test_3h_tokens_in_file_names(stem, expected):
    assert A.timeframe_from_name(stem) == expected


def three_hourly(path, n=40, seed=2):
    t0 = datetime(2025, 9, 22, 9, 0, tzinfo=timezone.utc)  # 14:30 +05:30, 24/7 market
    times = [t0 + timedelta(minutes=180 * i) for i in range(n)]
    header = ["time", "open", "high", "low", "close", "ATR in %"]
    rows = [[t.astimezone(IST).isoformat()] + r[:4] + [""] for t, r in zip(times, ohlcv(n, seed, volume=False))]
    return write_delimited(path, header, rows, newline="\n"), times


def test_3h_is_a_registered_intraday_timeframe():
    assert "3h" in ALLOWED_TIMEFRAMES and INTRADAY_MINUTES["3h"] == 180 and is_timeframe("3h")
    assert "3h" in INTRADAY_TIMEFRAMES and "3h" in TIMEFRAME_ORDER and timeframe_label("3h") == "3 hours"
    assert ALLOWED_TIMEFRAMES.index("1h") < ALLOWED_TIMEFRAMES.index("3h") < ALLOWED_TIMEFRAMES.index("4h")


def test_180_minute_bars_are_kept_as_3h_never_4h_and_the_crypto_venue_is_asked(settings, run, db, src):
    p, times = three_hourly(src / "CRYPTO_RIVERUSD, 180.csv")
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata", default_exchange="NSE")
    assert it.status == A.NEEDS_ANSWER and [q.key for q in it.questions] == ["exchange"]  # NOT NSE
    assert "CRYPTO_ prefix" in it.questions[0].text and it.overrides == {}
    assert any("default exchange (NSE) is not applied" in e for e in it.evidence)
    assert it.decisions["timeframe"] == "3h" and it.decisions["identity"] == {"symbol": "RIVERUSD"}
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata", default_exchange="NSE",
                          answers={"exchange": "BINANCE"})
    assert it.status == A.READY and it.overrides == {"exchange": "BINANCE", "symbol": "RIVERUSD", "timeframe": "3h"}
    assert any("A-9 timeframe 3h" in e for e in it.evidence) and any("file name agrees (3h)" in e for e in it.evidence)
    res = _load(run, p, it)
    assert res.ok
    ds = get_dataset(db, res.dataset_ids[0])
    assert (ds.instrument, ds.timeframe, ds.row_count) == ("BINANCE:RIVERUSD", "3h", 40)
    stored = _stored(settings, db, ds.dataset_id)
    assert stored.column("timestamp_utc").to_pylist() == times  # no resampling, relabelling or aggregation
    spacing = db.one("SELECT passed FROM quality_checks WHERE check_name = 'timeframe_spacing' AND attempt_id = ?",
                     (res.attempt_id,))
    assert spacing is not None and spacing["passed"] == 1
    assert check_readiness(settings, db, ds.dataset_id, DataRequirement(timeframes=TIMEFRAME_ORDER, min_rows=2)).ready


def test_the_symbol_option_never_turns_the_prefix_of_a_180_minute_file_into_a_symbol(settings, src):
    p, _ = three_hourly(src / "CRYPTO_RIVERUSD, 180.csv")
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata", default_exchange="NSE",
                          symbol_from_filename=True)
    assert it.decisions["identity"] == {"symbol": "RIVERUSD"} and [q.key for q in it.questions] == ["exchange"]


def test_a_recorded_4h_answer_for_180_minute_bars_is_not_used(settings, src):
    p, _ = three_hourly(src / "CRYPTO_RIVERUSD, 180.csv")
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata",
                          answers={"exchange": "BINANCE", "timeframe": "4h"})
    assert it.status == A.READY and it.overrides["timeframe"] == "3h"
    assert any("earlier answer (4h) is not used" in w for w in it.warnings)
