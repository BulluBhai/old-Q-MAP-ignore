"""Workbench date validation, readiness states and run safety (requirements 2.4, 2.5) and the latest completed run (3).

The synthetic daily dataset has 30 weekday bars from Monday 05-Jan-26 to Friday 13-Feb-26.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest
from qmap.analytical_engine import (DATASET_SUMMARY, INVALID_INPUT, NO_ELIGIBLE_DATA, NOT_READY, READY, check_analysis,
                                    latest_completed_run, run_analysis)


@pytest.fixture
def daily(run, src):
    return do_ingest(run, write_delimited(src / "d.csv", HEADER, daily_rows(30))).dataset_ids[0]


def _nothing_was_run(settings, db, before: int):
    assert db.one("SELECT COUNT(*) FROM runs WHERE module_code = 'DSUM'")[0] == before
    folder = settings.output_root / "Research_Reports"
    assert not folder.exists() or not any(folder.iterdir())


# ---- 2.2: every required format gives the same, correct period ----------------------------------------------------
@pytest.mark.parametrize("start, end", [("12/01/26", "16/01/26"), ("12-01-26", "16-01-26"), ("12-Jan-26", "16-Jan-26"),
                                        ("120126", "160126")])
def test_each_format_selects_the_same_bars(settings, db, daily, start, end):
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": start, "date_to": end})
    assert r.state == READY and r.params == {"date_from": date(2026, 1, 12), "date_to": date(2026, 1, 16)}
    assert r.reports[0].rows_in_window == 5


# ---- 2.4: three different situations are kept apart ---------------------------------------------------------------
@pytest.mark.parametrize("params, expected", [
    ({"date_from": "25.01.26"}, "not a date Q-MAP understands"),
    ({"date_to": "31/02/26"}, "not a real calendar date"),
    ({"date_from": "1793262840"}, "exactly six digits"),
    ({"date_from": "20-Jan-26", "date_to": "10-Jan-26"}, "is after the end date"),
])
def test_invalid_input_is_reported_as_invalid_input_and_nothing_runs(settings, db, daily, params, expected):
    before = db.one("SELECT COUNT(*) FROM runs WHERE module_code = 'DSUM'")[0]
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], params)
    assert r.state == INVALID_INPUT and not r.ready and expected in " ".join(r.input_problems)
    assert r.reports == []  # no dataset is judged against a period that is not understood
    res = run_analysis(settings, db, DATASET_SUMMARY, [daily], params)
    assert res.outcome == "blocked" and res.run_id is None and res.message.startswith("The dates entered are not valid")
    _nothing_was_run(settings, db, before)


@pytest.mark.parametrize("params, what", [
    ({"date_from": "01-Jan-30"}, "after the data"),
    ({"date_from": "01/01/25", "date_to": "31/12/25"}, "before the data"),
    ({"date_from": "10-Jan-26", "date_to": "11-Jan-26"}, "a weekend inside the coverage"),
])
def test_a_valid_period_without_bars_is_not_a_date_error(settings, db, daily, params, what):
    before = db.one("SELECT COUNT(*) FROM runs WHERE module_code = 'DSUM'")[0]
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], params)
    assert r.state == NO_ELIGIBLE_DATA, what
    assert r.input_problems == [] and r.reports[0].no_eligible_bars
    detail = r.reports[0].failures[0].detail
    assert "The dates are valid" in detail and "05-Jan-26 to 13-Feb-26" in detail  # shows the actual coverage
    res = run_analysis(settings, db, DATASET_SUMMARY, [daily], params)
    assert res.outcome == "blocked" and res.run_id is None and "no bars in that period" in res.message
    _nothing_was_run(settings, db, before)


def test_a_period_wider_than_the_data_is_ready_with_coverage_notes(settings, db, daily):
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": "01-Jan-26", "date_to": "31-Mar-26"})
    assert r.state == READY and r.reports[0].rows_in_window == 30
    names = {w.name for w in r.reports[0].warnings}
    assert {"coverage_start", "coverage_end"} <= names


def test_too_few_bars_is_not_ready_rather_than_no_data(settings, db, daily):
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": "05-01-26", "date_to": "05-01-26"})
    assert r.state == NOT_READY and r.reports[0].rows_in_window == 1 and "at least 2" in r.reports[0].failures[0].detail


def test_blank_dates_keep_using_all_the_data(settings, db, daily):
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": "", "date_to": "  "})
    assert r.state == READY and r.params == {"date_from": None, "date_to": None} and r.reports[0].rows_in_window == 30


def test_a_valid_request_runs_and_records_the_dates_it_used(settings, db, daily):
    res = run_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": "120126", "date_to": "16/01/26"})
    assert res.ok
    import json

    meta = json.loads(res.metadata_path.read_text())
    assert meta["parameters"] == {"date_from": "2026-01-12", "date_to": "2026-01-16"}
    assert meta["input_datasets"][0]["rows_in_window"] == 5


# ---- 3: the latest COMPLETED run ---------------------------------------------------------------------------------
def test_latest_completed_run_uses_the_recorded_folder_and_ignores_failures(settings, db, daily):
    assert latest_completed_run(settings, db) is None
    first = run_analysis(settings, db, DATASET_SUMMARY, [daily], {})
    assert latest_completed_run(settings, db) == (first.run_id, first.run_dir)

    def boom(_ctx):
        raise RuntimeError("calculation error")

    failed = run_analysis(settings, db, replace(DATASET_SUMMARY, execute=boom), [daily], {})
    assert failed.outcome == "failed" and failed.run_dir is not None
    refused = run_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": "nonsense"})
    assert refused.outcome == "blocked"
    assert latest_completed_run(settings, db) == (first.run_id, first.run_dir)  # neither counts
    second = run_analysis(settings, db, DATASET_SUMMARY, [daily], {})
    assert latest_completed_run(settings, db) == (second.run_id, second.run_dir)


def test_data_management_runs_are_never_the_latest_analysis_run(settings, db, run, daily):
    from qmap.data_engine.derive import derive_timeframe

    assert derive_timeframe(run, daily, "1W").ok  # a FOUND/DBM run, not an analysis
    assert latest_completed_run(settings, db) is None
