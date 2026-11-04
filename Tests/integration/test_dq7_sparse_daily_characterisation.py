"""Sparse daily / weekly observations under DQ-7 (review of 04-Nov-26, item C5): CHARACTERISATION tests.

These tests record what the approved DQ-7 method does TODAY with synthetic files whose observations are regularly
spaced 2-4 days apart (no 1-day step anywhere) or 5-10 days apart. They do not change the method: the result is
reported to the owner (docs/release/Q-MAP_v0.1_Review_Corrections_04_Nov_26_*.md, section C5) with a
recommendation. If the owner approves a change, these expectations change with it, deliberately and visibly.

Finding: a daily-or-longer block is labelled by its most common step in calendar days (1-4 -> 1D, 5-10 -> 1W,
26-35 -> 1M ...) BEFORE the agreement rule runs, and the agreement rule's "the interval itself occurs in the block"
then compares labels, not steps. So the base interval itself (a 1-day or a 7-day step) need not occur at all.
"""

from __future__ import annotations

import itertools
from datetime import date, timedelta

import pytest

from fixtures.builders import HEADER, ohlcv, write_delimited
from fixtures.profiles import do_ingest, make_profile
from qmap.data_engine.timeframe_infer import CONSISTENT, MIXED_STATUS, infer_interval


def dates(steps, n=200, start=date(2022, 1, 3)):
    out, cycle = [start], itertools.cycle(steps)
    while len(out) < n:
        out.append(out[-1] + timedelta(days=next(cycle)))
    return out


# ---- controls: genuine daily and weekly data ------------------------------------------------------------------

@pytest.mark.parametrize("steps", [[1, 1, 1, 1, 3], [1, 1, 2, 1, 3, 1, 1, 1, 3]], ids=["weekdays", "daily_some_gaps"])
def test_genuine_daily_data_are_1d(steps):
    inf = infer_interval(dates(steps), zone=None)
    assert (inf.status, inf.timeframe) == (CONSISTENT, "1D")


def test_genuine_weekly_data_are_1w():
    inf = infer_interval(dates([7]), zone=None)
    assert (inf.status, inf.timeframe) == (CONSISTENT, "1W")


# ---- files with only two-to-four-day gaps (no 1-day step anywhere) --------------------------------------------

@pytest.mark.parametrize("steps", [[2], [2, 2, 3], [3], [4]], ids=["every_2_days", "mon_wed_fri", "every_3", "every_4"])
def test_current_behaviour_two_to_four_day_gaps_are_registered_as_1d(steps):
    inf = infer_interval(dates(steps), zone=None)
    assert (inf.status, inf.timeframe) == (CONSISTENT, "1D")
    # the base interval itself (a 1-day step) occurs in no block
    assert 1 not in steps


# ---- files with five-to-ten-day gaps ---------------------------------------------------------------------------

@pytest.mark.parametrize("steps", [[5], [6], [9], [10], [5, 10], [5, 6, 8, 9]],
                         ids=["every_5", "every_6", "every_9", "every_10", "5_and_10", "5_6_8_9"])
def test_current_behaviour_five_to_ten_day_gaps_are_registered_as_1w(steps):
    inf = infer_interval(dates(steps), zone=None)
    assert (inf.status, inf.timeframe) == (CONSISTENT, "1W")
    assert 7 not in steps  # a 7-day step occurs in no block


def test_current_behaviour_longer_regular_gaps_get_their_own_day_label():
    assert infer_interval(dates([11]), zone=None).timeframe == "11d"
    assert infer_interval(dates([14]), zone=None).timeframe == "14d"  # not 2W


def test_a_file_whose_sections_differ_in_kind_is_still_mixed():
    inf = infer_interval(dates([2, 9]), zone=None)  # alternating 2-day and 9-day steps: blocks disagree
    assert inf.status == MIXED_STATUS


def test_the_same_result_through_ingestion(src, run, db):
    """The ingest path registers the same label (the inference above is what process.py uses)."""
    days = dates([2, 2, 3], n=60, start=date(2025, 1, 6))
    p = write_delimited(src / "SPARSE.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, ohlcv(60))])
    res = do_ingest(run, p, make_profile(profile_id="sparse"))
    assert res.outcome == "accepted", res.message
    assert db.one("SELECT timeframe FROM datasets WHERE layer = 'cleaned'")[0] == "1D"
