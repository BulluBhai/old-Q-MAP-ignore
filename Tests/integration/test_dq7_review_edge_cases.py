"""PR #10 review (03-Nov-26): timeframe inference edge cases, and the full-file check that complements sampling.

Each case records the seed, the sampled block positions, the rows examined and the result (see `_report`), so a
failure explains itself. All data are SYNTHETIC; no exchange calendar is used (weekdays 09:15-15:30 IST only).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from fixtures.builders import HEADER, ohlcv, write_delimited
from fixtures.profiles import do_ingest, make_profile
from qmap.data_engine import timeframe_infer as T

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc


def sess(step, start, days):
    out, d = [], start
    while (d - start).days < days:
        if d.weekday() < 5:
            m = 9 * 60 + 15
            while m < 15 * 60 + 30:
                out.append(datetime(d.year, d.month, d.day, m // 60, m % 60, tzinfo=IST).astimezone(UTC))
                m += step
        d += timedelta(days=1)
    return out


def daily_stamps(start, n):
    return [datetime(start.year, start.month, start.day, 3, 45, tzinfo=UTC) + timedelta(days=i) for i in range(n)]


def _report(res):
    return {"status": res.status, "timeframe": res.timeframe, "seed": res.seed, "rows_examined": res.rows_examined,
            "rows_total": res.rows_total, "blocks": [(b.start_row, b.interval, b.agrees) for b in res.blocks],
            "patterns": res.patterns}


def infer(keys):
    return T.infer_interval(keys, zone="Asia/Kolkata")


# ---- sampling --------------------------------------------------------------------------------------------------
def test_an_interval_change_that_covers_a_material_part_of_the_file_is_mixed():
    first = sess(1, date(2025, 1, 1), 300)
    keys = first[:int(len(first) * 0.7)] + sess(5, date(2026, 3, 2), 90)
    res = infer(keys)
    assert (res.status, res.timeframe) == ("mixed", "MIXED"), _report(res)
    assert set(res.patterns) == {"1m", "5m"} and res.rows_examined == 620


def test_an_unrepresentative_start_changes_only_the_number_of_blocks_not_the_result():
    keys = sess(5, date(2025, 1, 1), 1)[:25] + sess(1, date(2025, 1, 2), 200)  # the first 25 rows are 5-minute
    res = infer(keys)
    assert res.candidate == "5m" and len(res.blocks) == 15  # candidate from the first rows: 15 blocks, not 20
    assert (res.status, res.timeframe) == ("consistent", "1m"), _report(res)


@pytest.mark.parametrize("order", ["intraday_then_daily", "daily_then_intraday"])
def test_mixed_intraday_and_daily_sections_are_mixed_when_a_block_lands_in_them(order):
    intraday = sess(1, date(2025, 1, 1), 100) if order == "intraday_then_daily" else sess(15, date(2025, 1, 1), 200)
    daily = daily_stamps(date(2025, 6, 1) if order == "intraday_then_daily" else date(2020, 1, 1),
                         400 if order == "intraday_then_daily" else 1500)
    keys = intraday + daily if order == "intraday_then_daily" else daily + intraday
    res = infer(keys)
    assert (res.status, res.timeframe) == ("mixed", "MIXED"), _report(res)
    assert "1D" in res.patterns  # review fix: a daily block is measured as daily, never skipped or matched to minutes


def test_a_block_in_days_never_agrees_with_a_minute_interval():
    block = T.Block(1, 30, "1D", 29)
    assert T._is_minutes("1m") and T._is_minutes("2h") and not T._is_minutes("1D") and not T._is_minutes("1M")
    assert block.interval == "1D"


@pytest.mark.parametrize("name, keys_fn", [
    ("repeated timestamps", lambda base: [k for i, k in enumerate(base) for _ in range(2 if i % 10 == 0 else 1)]),
    ("out-of-order section", lambda base: base[:1000] + list(reversed(base[1000:1100])) + base[1100:]),
    ("descending file", lambda base: list(reversed(base))),
])
def test_repeated_and_out_of_order_timestamps_do_not_change_the_interval(name, keys_fn):
    res = infer(keys_fn(sess(5, date(2025, 1, 1), 60)))
    assert (res.status, res.timeframe) == ("consistent", "5m"), (name, _report(res))


@pytest.mark.parametrize("n", [3, 15, 59])
def test_small_files_are_examined_completely(n):
    res = infer(sess(5, date(2025, 1, 1), 5)[:n])
    assert len(res.blocks) == 1 and res.blocks[0].rows == n and res.rows_examined == n
    assert res.timeframe == "5m", _report(res)


def test_the_same_file_gives_the_same_blocks_and_seed():
    keys = sess(1, date(2025, 1, 1), 300)
    a, b = infer(keys), infer(list(keys))
    assert _report(a) == _report(b)


# ---- short sections between blocks: missed by sampling (known limit), caught by the full-file check ---------------
def _load(src, run, keys, name):
    rows = [[k.isoformat()] + r for k, r in zip(keys, ohlcv(len(keys)))]
    prof = make_profile(profile_id=name, instrument={"timeframe": "infer"},
                        datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    return do_ingest(run, write_delimited(src / f"{name}.csv", HEADER, rows), prof)


@pytest.mark.parametrize("case", ["tail_5m", "middle_7m_2000_rows", "middle_7m_300_rows", "daily_tail"])
def test_short_sections_missed_by_sampling_are_reported_by_validation(src, run, db, case):
    base = sess(1, date(2025, 1, 1), 300)
    mid = len(base) // 2
    keys = {
        "tail_5m": base[:int(len(base) * 0.97)] + sess(5, date(2026, 3, 2), 8),
        "middle_7m_2000_rows": base[:mid] + sess(7, date(2026, 1, 1), 60)[:2000] + base[mid:],
        "middle_7m_300_rows": base[:mid] + sess(7, date(2026, 1, 1), 10)[:300] + base[mid:],
        "daily_tail": base + daily_stamps(date(2026, 3, 1), 60),
    }[case]
    sampled = infer(sorted(keys))
    assert sampled.timeframe == "1m", _report(sampled)  # the known sampling limit: the section is not sampled
    res = _load(src, run, sorted(keys), case)
    assert res.outcome == "accepted", res.message
    chk = next(c for c in res.checks if c.name == "interval_change_detected")
    assert not chk.passed and chk.severity == "warning" and "source rows" in chk.detail
    assert ("one bar each" in chk.detail) if case == "daily_tail" else ("consecutive steps of" in chk.detail)


def test_the_full_file_check_does_not_fire_on_an_illiquid_but_uniform_file(src, run):
    import random

    rnd = random.Random(11)
    keys = [k for k in sess(1, date(2025, 1, 1), 40) if rnd.random() > 0.5]  # half of the minutes missing
    res = _load(src, run, keys, "illiquid")
    assert next(c for c in res.checks if c.name == "interval_change_detected").passed
