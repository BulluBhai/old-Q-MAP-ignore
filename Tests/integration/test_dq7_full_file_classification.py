"""PR #10 second review (03-Nov-26): the full-file interval check must not mistake missing observations for another
interval, must keep detecting genuine interval changes, and must report what the timestamps cannot decide as
UNCERTAIN instead of asserting a change.

Every case also runs the sampling inference on the same timestamps and records its seed, block positions, rows
examined and result (`_report`), so the two methods can be compared against the sampling consistency rules
(a block agrees when >= 90 % of its steps are whole multiples of the dominant interval AND that interval occurs in
>= 10 % of its steps). All data are SYNTHETIC and seeded; no exchange calendar is used.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

import pytest

from fixtures.builders import HEADER, ohlcv, write_delimited
from fixtures.profiles import do_ingest, make_profile
from qmap.data_engine import timeframe_infer as T
from qmap.data_engine import validation as V

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc


def sess(step, start, days):
    """Weekday sessions 09:15-15:30 IST at `step` minutes, for `days` calendar days from `start`."""
    out, d = [], start
    while (d - start).days < days:
        if d.weekday() < 5:
            m = 9 * 60 + 15
            while m < 15 * 60 + 30:
                out.append(datetime(d.year, d.month, d.day, m // 60, m % 60, tzinfo=IST).astimezone(UTC))
                m += step
        d += timedelta(days=1)
    return out


def weekdays(start, n):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def at(d, hh, mm):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=IST).astimezone(UTC)


def _report(res):
    return {"status": res.status, "timeframe": res.timeframe, "seed": res.seed, "rows_examined": res.rows_examined,
            "rows_total": res.rows_total, "blocks": [(b.start_row, b.interval, b.agrees) for b in res.blocks],
            "patterns": res.patterns}


def infer(keys):
    return T.infer_interval(keys, zone="Asia/Kolkata")


def _load(src, run, keys, name, timeframe="infer"):
    rows = [[k.isoformat()] + r for k, r in zip(keys, ohlcv(len(keys)))]
    prof = make_profile(profile_id=name, instrument={"timeframe": timeframe},
                        datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, write_delimited(src / f"{name}.csv", HEADER, rows), prof)
    assert res.outcome == "accepted", res.message
    return res


def _checks(res):
    det = next(c for c in res.checks if c.name == "interval_change_detected")
    unc = next(c for c in res.checks if c.name == "interval_change_uncertain")
    return det, unc


# ---- 1. 1-minute data with a substantial section of 2-minute gaps --------------------------------------------------
def test_1m_with_a_section_of_randomly_missing_bars_is_not_reported(src, run):
    """Each bar of a 60-day middle section is missing with probability 0.5 (seed 7): about a quarter of its steps are
    2-minute gaps, others 3, 4 ... minutes. Missing bars, not another interval: no warning from either method."""
    base = sess(1, date(2024, 1, 1), 300)
    rnd = random.Random(7)
    lo, hi = len(base) * 2 // 5, len(base) * 3 // 5
    section = [k for k in base[lo:hi] if rnd.random() > 0.5]
    keys = base[:lo] + section + base[hi:]
    steps = [int((b - a).total_seconds() // 60) for a, b in zip(section, section[1:])
             if a.astimezone(IST).date() == b.astimezone(IST).date()]
    assert steps.count(2) > 0.2 * len(steps)  # the section really is full of 2-minute gaps
    sampled = infer(keys)
    assert (sampled.status, sampled.timeframe) == ("consistent", "1m"), _report(sampled)
    det, unc = _checks(_load(src, run, keys, "gaps_1m"))
    assert det.passed and unc.passed, (det.detail, unc.detail)


def test_1m_with_every_other_bar_missing_is_uncertain_not_asserted(src, run):
    """A 5-day section with EVERY other minute missing is a regular 2-minute grid: either 2-minute data or 1-minute
    data with bars missing at regular positions. The timestamps cannot tell: reported as uncertain, never asserted.
    (5 days, about 940 rows: the sampled blocks miss it, so the full-file check is what reports it.)"""
    keys = sess(1, date(2024, 1, 1), 150) + sess(1, date(2024, 6, 3), 5)[::2] + sess(1, date(2024, 7, 1), 150)
    sampled = infer(keys)
    assert (sampled.status, sampled.timeframe) == ("consistent", "1m"), _report(sampled)
    det, unc = _checks(_load(src, run, keys, "every_other_1m"))
    assert det.passed, det.detail
    assert not unc.passed and unc.severity == "warning" and "steps of 2 minute(s)" in unc.detail
    assert "cannot show whether" in unc.detail and "bars present only every 2 intervals" in unc.detail


def test_sampling_still_labels_a_sampled_regular_multiple_grid_mixed():
    """Recorded, unchanged (approved sampling rule, DQ-7): when a block lands in a regular 2-minute section (20 days),
    the block has no 1-minute step (< 10 %), does not agree, and the file is registered MIXED. The full-file check is
    then not run (it only runs for a single intraday timeframe). This difference is proposal DQ-14's subject."""
    keys = sess(1, date(2024, 1, 1), 150) + sess(1, date(2024, 6, 3), 20)[::2] + sess(1, date(2024, 7, 1), 150)
    sampled = infer(keys)
    assert (sampled.status, sampled.timeframe) == ("mixed", "MIXED"), _report(sampled)
    assert [(b.interval, b.agrees) for b in sampled.blocks if b.interval != "1m"] == [("2m", False)], _report(sampled)
    assert sampled.rows_examined == 620 and len(sampled.blocks) == 20


# ---- 2. 5-minute data with occasional 10-minute gaps ---------------------------------------------------------------
@pytest.mark.parametrize("drop", [0.03, 0.10, 0.25])
def test_5m_with_occasional_10m_gaps_is_not_reported(src, run, drop):
    rnd = random.Random(int(drop * 100))
    keys = [k for k in sess(5, date(2024, 1, 1), 200) if rnd.random() > drop]
    sampled = infer(keys)
    assert (sampled.status, sampled.timeframe) == ("consistent", "5m"), _report(sampled)
    det, unc = _checks(_load(src, run, keys, f"gaps_5m_{int(drop * 100)}"))
    assert det.passed and unc.passed, (det.detail, unc.detail)


# ---- 3. a genuinely different interval inside an otherwise consistent file ----------------------------------------
@pytest.mark.parametrize("other", [3, 7, 1])
def test_a_non_multiple_interval_section_is_detected(src, run, other):
    """3 or 7 minutes in 5-minute data (not whole multiples) and 1 minute (finer) cannot come from missing bars."""
    base = sess(5, date(2024, 1, 1), 200)
    mid = len(base) // 2
    section = sess(other, date(2025, 1, 1), 10)[:200]  # 200 rows: short enough to fall between the sampled blocks
    keys = sorted(base[:mid] + section + [k + timedelta(days=400) for k in base[mid:]])
    sampled = infer(keys)
    assert (sampled.status, sampled.timeframe) == ("consistent", "5m"), _report(sampled)  # the known sampling limit
    det, unc = _checks(_load(src, run, keys, f"genuine_{other}m"))
    assert not det.passed and det.severity == "warning", det.detail
    assert f"steps of {other} minute(s)" in det.detail and "source rows" in det.detail
    assert unc.passed, unc.detail


def test_a_genuine_section_with_its_own_missing_bars_is_still_detected(src, run):
    """A 3-minute section with a few of its own bars missing still contains runs of >= 30 identical 3-minute steps."""
    rnd = random.Random(3)
    base = sess(5, date(2024, 1, 1), 200)
    mid = len(base) // 2
    section = [k for k in sess(3, date(2025, 1, 1), 10)[:300] if rnd.random() >= 0.01]
    keys = sorted(base[:mid] + section + [k + timedelta(days=400) for k in base[mid:]])
    sampled = infer(keys)
    assert (sampled.status, sampled.timeframe) == ("consistent", "5m"), _report(sampled)
    det, _unc = _checks(_load(src, run, keys, "genuine_3m_gaps"))
    assert not det.passed and "steps of 3 minute(s)" in det.detail


# ---- 4. a sparse intraday instrument with dates that have one observation ------------------------------------------
def test_a_sparse_instrument_with_one_bar_dates_is_not_another_interval(src, run):
    """5-minute data; 40 consecutive weekdays with ONE observation each at varying times of day (seed 5) plus
    scattered one-bar dates. These are missing observations of a sparse instrument, not daily data."""
    rnd = random.Random(5)
    full = sess(5, date(2024, 1, 1), 120)
    sparse_days = weekdays(date(2024, 6, 3), 40)
    sparse = [at(d, 9 + rnd.randrange(6), 15 + 5 * rnd.randrange(9)) for d in sparse_days]
    later = sess(5, date(2024, 8, 5), 120)
    scattered = {k.astimezone(IST).date() for k in later[::400]}
    later = [k for k in later if k.astimezone(IST).date() not in scattered
             or k.astimezone(IST).time() == datetime(2025, 1, 1, 11, 0).time()]
    keys = full + sparse + later
    res = _load(src, run, keys, "sparse_5m")
    det, unc = _checks(res)
    assert det.passed and unc.passed, (det.detail, unc.detail)
    assert not next(c for c in res.checks if c.name == "partial_session").passed  # the sparse dates stay reported
    # sampling rule: a block inside the one-bar dates is measured in days (one bar per date) and never agrees with a
    # minute interval, so sampling calls such a file MIXED when a block lands there. Recorded (see DQ-14 proposal).
    sampled = infer(keys)
    day_blocks = [b for b in sampled.blocks if not T._is_minutes(b.interval)]
    assert sampled.status == ("mixed" if day_blocks else "consistent"), _report(sampled)


# ---- 5. a daily-like section inside intraday data ------------------------------------------------------------------
@pytest.mark.parametrize("stamp, expect", [((0, 0), "detected"), ((15, 30), "detected"), ((9, 15), "uncertain")])
def test_a_daily_like_section_is_detected_or_uncertain_by_its_time_of_day(src, run, stamp, expect):
    """60 one-bar dates at one time of day. Midnight (or 15:30, after the last 15:25 bar) is outside the times the
    1-minute bars use, so the bars cannot be surviving intraday bars: detected. 09:15 is also an intraday bar time:
    daily data, or only the first bar of each date - uncertain."""
    base = sess(1, date(2024, 1, 1), 150)
    keys = base + [at(d, *stamp) for d in weekdays(date(2024, 8, 1), 60)]
    sampled = infer(keys)
    assert (sampled.status, sampled.timeframe) == ("consistent", "1m"), _report(sampled)  # missed by sampling
    det, unc = _checks(_load(src, run, keys, f"daily_{stamp[0]}{stamp[1]}"))
    hit, other = (det, unc) if expect == "detected" else (unc, det)
    assert not hit.passed and "one bar each" in hit.detail and f"{stamp[0]:02d}:{stamp[1]:02d}" in hit.detail
    assert other.passed, other.detail


# ---- reproducibility and the bound behind the classification -------------------------------------------------------
def test_sampling_report_is_unchanged_and_reproducible():
    keys = sess(1, date(2025, 1, 1), 300)
    a, b = infer(keys), infer(list(keys))
    assert _report(a) == _report(b) and a.rows_examined == 620 and len(a.blocks) == 20


def test_random_gaps_cannot_produce_a_run_of_identical_multiples():
    """Independent missing bars give a step of k intervals with probability q(1-q)^(k-1) <= 0.25 (k = 2, q = 0.5);
    CHANGE_RUN identical steps in a row: <= 0.25^30, about 8.7e-19 per position."""
    assert max(q / 100 * (1 - q / 100) ** (k - 1) for q in range(1, 100) for k in range(2, 20)) <= 0.25
    assert 0.25 ** V.CHANGE_RUN < 1e-18
    assert V._classify_step_run(2, 1) == "uncertain" and V._classify_step_run(10, 5) == "uncertain"
    assert V._classify_step_run(3, 5) == "definite" and V._classify_step_run(1, 5) == "definite"
    assert V._classify_step_run(7, 5) == "definite" and V._classify_step_run(7.5, 5) == "definite"


def test_a_daily_section_with_more_dates_than_the_intraday_part_is_still_checked(src, run):
    """Third review: 30 intraday dates and 35 one-bar dates at 00:00. The most common bars-per-date is 1, which
    used to skip the daily-section check entirely; any multi-bar date now enables it."""
    keys = sess(5, date(2024, 1, 1), 42) + [at(d, 0, 0) for d in weekdays(date(2024, 3, 4), 35)]
    sampled = infer(keys)
    assert (sampled.status, sampled.timeframe) == ("consistent", "5m"), _report(sampled)
    det, unc = _checks(_load(src, run, keys, "daily_majority"))
    assert not det.passed and "35 consecutive trading dates with one bar each" in det.detail and "00:00" in det.detail
    assert unc.passed
