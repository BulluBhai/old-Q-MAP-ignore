"""DQ-7 independent review (04-Nov-26): daily, weekly, monthly, quarterly and yearly intervals must not agree with one
another merely because each is counted as "1" of its own unit.

Before the fix every daily-or-longer label had base unit 1, so a block measured in weeks (steps 1, 1, 1 weeks) looked
like whole multiples of a daily interval in which the daily interval itself "occurred"; a file with a daily and a
weekly section was CONSISTENT 1D. Each mixed case below asserts that the sampled blocks really land in BOTH sections,
so the test exercises the comparison, not the sampling. Ordinary gaps (weekends, holidays, missing sessions, missing
weeks or months) must still be CONSISTENT. All data are synthetic and deterministic.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from fixtures.builders import HEADER, ohlcv, write_delimited
from qmap.analytical_engine import MA_AFFINITY, check_analysis
from qmap.catalog import get_dataset, list_datasets
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap.data_engine.timeframe_infer import CONSISTENT, MIXED_STATUS, infer_interval


def weekdays(start: date, n: int, skip: set | None = None) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5 and d not in (skip or set()):
            out.append(d)
        d += timedelta(days=1)
    return out


def fridays(start: date, n: int) -> list[date]:
    d = start + timedelta(days=(4 - start.weekday()) % 7)
    return [d + timedelta(weeks=i) for i in range(n)]


def month_ends(start: date, n: int) -> list[date]:
    out, y, m = [], start.year, start.month
    for _ in range(n):
        nxt = date(y + m // 12, m % 12 + 1, 1)
        out.append(nxt - timedelta(days=1))
        y, m = nxt.year, nxt.month
    return out


def quarter_ends(start: date, n: int) -> list[date]:
    return month_ends(start, 3 * n)[2::3]


def year_ends(start_year: int, n: int) -> list[date]:
    return [date(start_year + i, 12, 31) for i in range(n)]


def after(d: date) -> date:
    return d + timedelta(days=1)


D400 = weekdays(date(2015, 1, 5), 400)
MIXED_CASES = {
    "daily then weekly": (D400 + fridays(after(D400[-1]), 200), {"1D", "1W"}),
    "weekly then daily": (fridays(date(2010, 1, 1), 400) + weekdays(date(2017, 9, 1), 200), {"1W", "1D"}),
    "daily then monthly": (D400 + month_ends(after(D400[-1]), 200), {"1D", "1M"}),
    "monthly then daily": (month_ends(date(1990, 1, 1), 300) + weekdays(date(2015, 2, 2), 150), {"1M", "1D"}),
    "weekly then monthly": (fridays(date(2000, 1, 7), 400) + month_ends(date(2008, 1, 1), 200), {"1W", "1M"}),
    "monthly then weekly": (month_ends(date(1980, 1, 1), 300) + fridays(date(2005, 2, 4), 150), {"1M", "1W"}),
    "monthly then quarterly": (month_ends(date(1970, 1, 1), 300) + quarter_ends(date(1995, 1, 1), 100), {"1M", "1Q"}),
    "quarterly then yearly": (quarter_ends(date(1600, 1, 1), 200) + year_ends(1650, 150), {"1Q", "1Y"}),
    "daily then yearly": (D400 + year_ends(2017, 150), {"1D", "1Y"}),
}


@pytest.mark.parametrize("name", list(MIXED_CASES))
def test_materially_different_calendar_intervals_are_mixed(name):
    keys, both = MIXED_CASES[name]
    res = infer_interval(keys, zone=None)
    sampled = {b.interval for b in res.blocks}
    assert both <= sampled, f"{name}: the blocks did not land in both sections ({sampled}); fix the test data"
    assert res.status == MIXED_STATUS and res.timeframe == "MIXED", (name, [(b.interval, b.agrees) for b in res.blocks])
    assert set(res.patterns) == both
    # the blocks of the minority unit are the ones that disagree, and only they
    dominant = max(res.patterns, key=res.patterns.get)
    for b in res.blocks:
        assert b.agrees == (b.interval == dominant), (name, b)


def _holiday_daily() -> list[date]:
    rnd = random.Random(42)
    holidays = {d for d in (date(2012, 1, 2) + timedelta(days=i) for i in range(4000)) if rnd.random() < 0.04}
    holidays |= {date(2016, 10, 31) + timedelta(days=i) for i in range(5)}  # a whole holiday week
    return weekdays(date(2012, 1, 2), 2500, skip=holidays)


def _holiday_weekly() -> list[date]:
    rnd = random.Random(7)
    out = []
    for d in fridays(date(2001, 1, 5), 700):
        if rnd.random() < 0.05:
            continue  # a missing week
        out.append(d - timedelta(days=1) if rnd.random() < 0.08 else d)  # Friday holiday: Thursday close
    return out


def _gappy_monthly() -> list[date]:
    rnd = random.Random(3)
    return [d - timedelta(days=rnd.choice((0, 0, 1, 2))) for d in month_ends(date(1985, 1, 1), 450) if rnd.random() > 0.05]


UNIFORM_CASES = {
    "daily with weekends, random holidays and a holiday week": (_holiday_daily(), "1D"),
    "weekly with missing weeks and Thursday closes": (_holiday_weekly(), "1W"),
    "monthly with missing months and varying month-end days": (_gappy_monthly(), "1M"),
    "quarterly": (quarter_ends(date(1950, 1, 1), 250), "1Q"),
    "yearly": (year_ends(1700, 200), "1Y"),
}


@pytest.mark.parametrize("name", list(UNIFORM_CASES))
def test_uniform_files_with_ordinary_gaps_stay_consistent(name):
    keys, tf = UNIFORM_CASES[name]
    res = infer_interval(keys, zone=None)
    assert res.status == CONSISTENT and res.timeframe == tf, (name, [(b.interval, b.agreeing_share) for b in res.blocks])


def test_classification_is_reproducible():
    keys, _ = MIXED_CASES["daily then weekly"]
    a, b = infer_interval(keys, zone=None), infer_interval(keys, zone=None)
    assert a.seed == b.seed and [x.start_row for x in a.blocks] == [x.start_row for x in b.blocks]
    assert (a.status, a.timeframe) == (b.status, b.timeframe)


def test_end_to_end_a_daily_file_with_a_weekly_section_is_registered_mixed_and_refused(settings, db, tmp_path):
    keys, _ = MIXED_CASES["daily then weekly"]
    folder = tmp_path / "files"
    folder.mkdir()
    write_delimited(folder / "NSE_DAYWEEK.csv", HEADER, [[d.isoformat()] + r for d, r in zip(keys, ohlcv(len(keys)))])
    src = D.add_folder_source(settings, db, folder)
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        D.scan_source(run, src.source_id)
    (ds,) = list_datasets(db)
    info = get_dataset(db, ds.dataset_id)
    assert info.timeframe == "MIXED" and any(w.startswith("mixed_intervals") for w in info.warnings)
    chk = check_analysis(settings, db, MA_AFFINITY, [ds.dataset_id], {})
    assert not chk.ready and any("MIXED" in f.detail for r in chk.reports for f in r.failures)
