"""DQ-7 (owner instruction 03-Nov-26): timeframe inference by sampling, any interval, MIXED, file name as a cross-check.

All data are SYNTHETIC. Intraday sessions are generated without any exchange calendar (weekdays 09:15-15:30 IST, plus
24/7 data); holidays and missing bars are cut out at random to prove that gaps are not mistaken for another interval.
"""

from __future__ import annotations

import csv
import random
import time
from datetime import date, datetime, timedelta, timezone

import pytest

from fixtures.builders import HEADER, ohlcv, write_delimited
from fixtures.profiles import do_ingest, make_profile
from qmap.analytical_engine import DATASET_SUMMARY, run_analysis
from qmap.catalog import DataRequirement, check_readiness, get_dataset, list_datasets, timeframe_label
from qmap.core.config import load_settings
from qmap.core.runs import run_context
from qmap.data_engine import auto_interpret as A
from qmap.data_engine import discovery as D
from qmap.data_engine import timeframe_infer as T
from qmap.data_engine.profiles import MIXED, canonical_timeframe, is_timeframe, minutes_label, timeframe_minutes

IST = timezone(timedelta(hours=5, minutes=30))


def session_times(step, days=30, start=date(2026, 1, 5), session=(9 * 60 + 15, 15 * 60 + 30)):
    """Bar start times every `step` minutes inside 09:15-15:30 IST on weekdays (no calendar: weekends only)."""
    out, d = [], start
    while len(out) == 0 or (d - start).days < days:
        if d.weekday() < 5:
            m = session[0]
            while m < session[1]:
                out.append(datetime(d.year, d.month, d.day, m // 60, m % 60, tzinfo=IST).astimezone(timezone.utc))
                m += step
        d += timedelta(days=1)
    return out


def continuous_times(step, n, start=datetime(2025, 9, 22, 9, 0, tzinfo=timezone.utc)):
    return [start + timedelta(minutes=step * i) for i in range(n)]


def infer(keys, zone="Asia/Kolkata", **cfg):
    return T.infer_interval(keys, zone=zone, config=cfg or None)


# ---- intervals --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("step, label", [(1, "1m"), (3, "3m"), (5, "5m"), (15, "15m"), (75, "75m"), (60, "1h"),
                                         (120, "2h")])
def test_intraday_session_intervals(step, label):
    res = infer(session_times(step, days=40 if step >= 60 else 10))
    assert (res.status, res.timeframe) == ("consistent", label), res.as_dict()


@pytest.mark.parametrize("step, label", [(180, "3h"), (240, "4h"), (120, "2h"), (60, "1h")])
def test_round_the_clock_intervals(step, label):
    res = infer(continuous_times(step, 3000))
    assert (res.status, res.timeframe) == ("consistent", label)


def test_daily_weekly_and_monthly():
    days = [d for d in (date(2020, 1, 1) + timedelta(days=i) for i in range(1500)) if d.weekday() < 5]
    assert infer(days).timeframe == "1D"
    weeks = [date(2020, 1, 3) + timedelta(days=7 * i) for i in range(200)]
    assert infer(weeks).timeframe == "1W"
    months = [date(2010 + i // 12, i % 12 + 1, 28) for i in range(150)]
    assert infer(months).timeframe == "1M"
    # daily bars written with a time of day (one bar per date) are daily, not intraday
    stamped = [datetime(d.year, d.month, d.day, 3, 45, tzinfo=timezone.utc) for d in days[:300]]
    assert infer(stamped).timeframe == "1D"


# ---- gaps ---------------------------------------------------------------------------------------------------------
def test_missing_bars_that_are_multiples_of_the_interval_do_not_change_it():
    rnd = random.Random(7)
    times = [t for t in session_times(5, days=60) if rnd.random() > 0.3]  # 30 % of bars missing at random
    res = infer(times)
    assert (res.status, res.timeframe) == ("consistent", "5m")
    assert all(b.agreeing_share == 1.0 for b in res.blocks)  # every step is a whole multiple of 5 minutes


def test_overnight_weekend_and_holiday_gaps_are_ignored_without_a_calendar():
    holidays = {date(2026, 1, 26), date(2026, 2, 17), date(2026, 3, 3), date(2026, 3, 4)}
    times = [t for t in session_times(15, days=90) if t.astimezone(IST).date() not in holidays]
    res = infer(times)
    assert (res.status, res.timeframe) == ("consistent", "15m")
    assert "no exchange calendar" in res.as_dict()["method"]


def test_no_exchange_calendar_or_network_is_used():
    """The inference module imports nothing beyond the standard library and Q-MAP's own timeframe helpers."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(T))
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
        {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imported <= {"__future__", "hashlib", "json", "random", "collections", "dataclasses", "datetime",
                        "zoneinfo", "core.timeframes"}
    # a weekday "holiday" and a 24/7 market need no calendar to be read correctly
    assert infer(continuous_times(5, 5000)).timeframe == "5m"


def test_an_illiquid_one_minute_stock_is_still_one_minute():
    rnd = random.Random(3)
    times = [t for t in session_times(1, days=20) if rnd.random() > 0.55]  # more than half of the minutes missing
    assert infer(times).timeframe == "1m"


# ---- mixed -----------------------------------------------------------------------------------------------------
def test_mixed_intervals_in_different_parts_of_a_file_are_mixed_not_forced():
    first = session_times(1, days=10)
    second = session_times(5, days=10, start=date(2026, 3, 2))
    res = infer(first + second)
    assert res.status == "mixed" and res.timeframe == MIXED
    assert set(res.patterns) == {"1m", "5m"} and "Mixed" in res.summary


def test_a_mixed_file_is_imported_classified_warned_and_not_treated_as_uniform(src, run, settings, db):
    times = session_times(1, days=8) + session_times(15, days=8, start=date(2026, 3, 2))
    rows = [[t.isoformat()] + r for t, r in zip(times, ohlcv(len(times)))]
    p = write_delimited(src / "NSE_MIX.csv", HEADER, rows)
    prof = make_profile(instrument={"timeframe": "ingest"}, datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, p, prof)
    assert res.outcome == "accepted", res.message  # kept, not discarded
    ds = get_dataset(db, res.dataset_ids[0])
    assert ds.timeframe == MIXED and ds.row_count == len(rows) and timeframe_label(MIXED) == "Mixed intervals"
    assert any(w.startswith("mixed_intervals") for w in ds.warnings)
    # an analysis that assumes one interval refuses it with the reason; Dataset Summary runs and says so
    strict = check_readiness(settings, db, ds.dataset_id, DataRequirement(min_rows=2))
    assert not strict.ready and "cannot use it safely" in strict.failures[0].detail
    rep = check_readiness(settings, db, ds.dataset_id, DATASET_SUMMARY.requirement)
    assert rep.ready and any(i.name == "timeframe" and i.status == "warn" for i in rep.items)
    assert run_analysis(settings, db, DATASET_SUMMARY, [ds.dataset_id], {}).ok


# ---- file name and declared values are cross-checks ---------------------------------------------------------------
def test_file_name_says_15_minutes_data_are_5_minutes(settings, db, tmp_path):
    folder = tmp_path / "f"
    folder.mkdir()
    times = session_times(5, days=5)
    write_delimited(folder / "NSE_ABC, 15.csv", HEADER, [[t.isoformat()] + r for t, r in zip(times, ohlcv(len(times)))])
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata")
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        res = D.scan_source(run, src.source_id)
    assert res.files[0][3] == "imported"  # accepted by default, no question
    (ds,) = list_datasets(db)
    assert ds.timeframe == "5m"
    (state,) = D.file_states(db, src.source_id)
    assert any("file name says 15m" in w for w in state.interpretation["warnings"])
    assert state.interpretation["decisions"]["timeframe_inference"]["status"] == "consistent"


def test_a_profile_declaring_15m_for_5_minute_data_registers_5m_with_a_warning(src, run, db):
    times = session_times(5, days=5)
    p = write_delimited(src / "d.csv", HEADER, [[t.isoformat()] + r for t, r in zip(times, ohlcv(len(times)))])
    prof = make_profile(instrument={"timeframe": "15m"}, datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, p, prof)
    assert db.one("SELECT timeframe FROM datasets WHERE layer='cleaned'")[0] == "5m"
    chk = next(c for c in res.checks if c.name == "timeframe_declared_differs")
    assert "says 15m" in chk.detail and "registered as 5m" in chk.detail
    info = next(c for c in res.checks if c.name == "timeframe_inferred")
    assert info.passed and "Consistent across" in info.detail


# ---- sampling: size, adaptation, reproducibility -----------------------------------------------------------------
def test_small_files_adapt_the_number_of_blocks():
    res = infer(session_times(5, days=1)[:40])  # 40 rows, less than two blocks of 30
    assert len(res.blocks) == 1 and res.blocks[0].rows == 40 and res.timeframe == "5m"
    res = infer(session_times(5, days=2))  # 150 rows: at most 5 blocks of 30
    assert 1 < len(res.blocks) <= 5
    assert infer(session_times(5, days=1)[:2]).status == "insufficient"


@pytest.mark.parametrize("step, blocks", [(1, 20), (2, 20), (5, 15), (15, 15), (30, 10), (60, 10)])
def test_number_of_blocks_follows_the_candidate_interval(step, blocks):
    res = infer(session_times(step, days=400))
    assert len(res.blocks) == blocks and res.timeframe == minutes_label(step)


def test_daily_and_weekly_use_five_blocks():
    days = [date(2000, 1, 3) + timedelta(days=i) for i in range(6000)]
    assert len(infer([d for d in days if d.weekday() < 5]).blocks) == 5
    assert len(infer(days[::7]).blocks) == 5


def test_sampling_is_reproducible_and_depends_on_data_and_configuration():
    times = session_times(5, days=200)
    a, b = infer(times), infer(list(times))
    assert a.seed == b.seed and [x.start_row for x in a.blocks] == [x.start_row for x in b.blocks]
    c = infer(times, seed=1)
    assert c.seed != a.seed and [x.start_row for x in c.blocks] != [x.start_row for x in a.blocks]
    assert infer(times[1:]).seed != a.seed
    starts = [x.start_row for x in a.blocks]
    assert starts == sorted(starts) and starts[0] < len(times) / 10 and starts[-1] > len(times) * 0.9  # whole file


def test_configured_block_counts_are_used(roots, tmp_path):
    cfg = tmp_path / "qmap.local.toml"
    cfg.write_text(f'[paths]\ndata_root = "{roots["data"].as_posix()}"\noutput_root = "{roots["output"].as_posix()}"\n'
                   "[timeframe_sampling]\nblocks_3_15m = 7\nblock_rows = 40\n")
    settings = load_settings(cfg)
    assert settings.timeframe_sampling == {"blocks_3_15m": 7, "block_rows": 40}
    res = infer(session_times(5, days=200), **settings.timeframe_sampling)
    assert len(res.blocks) == 7 and all(b.rows == 40 for b in res.blocks)


def test_one_million_rows_are_sampled_not_scanned():
    times = continuous_times(1, 1_000_000)
    t0 = time.perf_counter()
    res = infer(times)
    elapsed = time.perf_counter() - t0
    assert res.timeframe == "1m" and len(res.blocks) == 20
    assert res.rows_examined <= 20 * 30 + 20  # blocks plus the initial rows: well under 0.1 % of the file
    assert elapsed < 5.0


# ---- labels -----------------------------------------------------------------------------------------------------
def test_timeframe_values_are_open_ended_and_canonical():
    assert [canonical_timeframe(t) for t in ("60m", "120m", "75m", "1h", "3h", "1D", "MIXED", "2d")] == \
        ["1h", "2h", "75m", "1h", "3h", "1D", "MIXED", "2d"]
    assert timeframe_minutes("75m") == 75 and timeframe_minutes("2h") == 120 and timeframe_minutes("1D") is None
    assert not is_timeframe("5x") and not is_timeframe("1440m") and not is_timeframe("0m")
    assert [timeframe_label(t) for t in ("3m", "75m", "2h", "1h")] == ["3 minutes", "75 minutes", "2 hours", "Hourly"]


def test_inferred_75_minute_file_loads_end_to_end_through_the_scan(settings, db, tmp_path):
    folder = tmp_path / "f"
    folder.mkdir()
    times = session_times(75, days=30)
    write_delimited(folder / "NSE_ABC.csv", HEADER, [[t.isoformat()] + r for t, r in zip(times, ohlcv(len(times)))])
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata")
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        D.scan_source(run, src.source_id)
    (ds,) = list_datasets(db)
    assert ds.timeframe == "75m" and ds.timeframe_label == "75 minutes"
    spacing = [w for w in ds.warnings if w.startswith("timeframe_spacing")]
    assert not spacing  # the spacing check understands any interval
