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


# ---- review findings (PR #4) ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("params", [{"date_from": "01/01/0000"}, {"date_to": "0000-12-31"},
                                    {"date_from": "29-Feb-0000", "date_to": "16-01-26"}])
def test_year_0000_is_invalid_input_in_check_and_run_and_nothing_is_created(settings, db, daily, params):
    before = db.one("SELECT COUNT(*) FROM runs WHERE module_code = 'DSUM'")[0]
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], params)  # used to raise ValueError here
    assert r.state == INVALID_INPUT and "there is no year 0000" in " ".join(r.input_problems) and r.reports == []
    res = run_analysis(settings, db, DATASET_SUMMARY, [daily], params)
    assert res.outcome == "blocked" and res.run_id is None and res.run_dir is None
    assert res.message.startswith("The dates entered are not valid")
    _nothing_was_run(settings, db, before)


def test_the_widest_valid_years_simply_cover_all_the_data(settings, db, daily):
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": "01/01/0001", "date_to": "31/12/9999"})
    assert r.state == READY and r.reports[0].rows_in_window == 30


@pytest.fixture
def later(run, src):
    """A second instrument whose 10 weekday bars start on Monday 02-Mar-26 (after `daily` ends on 13-Feb-26)."""
    from datetime import date as _date

    from fixtures.profiles import make_profile

    prof = make_profile(profile_id="later_instrument", profile_version=1,
                        instrument={"exchange_from": "ingest", "symbol_from": "ingest", "exchange": None, "symbol": None})
    res = do_ingest(run, write_delimited(src / "later.csv", HEADER, daily_rows(10, start=_date(2026, 3, 2))), prof,
                    exchange="NSE", symbol="LATER")
    assert res.outcome == "accepted", res.message
    return res.dataset_ids[0]


JANUARY = {"date_from": "12-Jan-26", "date_to": "16-Jan-26"}  # 5 bars in `daily`, none in `later`
APRIL = {"date_from": "01-Apr-26", "date_to": "30-Apr-26"}  # no bars in either


def _refused_cleanly(settings, db, ids, params):
    before = db.one("SELECT COUNT(*) FROM runs WHERE module_code = 'DSUM'")[0]
    res = run_analysis(settings, db, DATASET_SUMMARY, ids, params)
    assert res.outcome == "blocked" and res.run_id is None and res.run_dir is None and res.outputs == []
    _nothing_was_run(settings, db, before)
    return res


def test_case1_one_dataset_with_eligible_bars_is_ready(settings, db, daily, later):
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], JANUARY)
    assert r.state == READY and r.datasets_without_bars == [] and r.partial_period_note == ""


def test_case2_one_dataset_without_bars_in_the_period_is_no_eligible_data(settings, db, daily, later):
    r = check_analysis(settings, db, DATASET_SUMMARY, [later], JANUARY)
    assert r.state == NO_ELIGIBLE_DATA and r.partial_period_note == ""
    assert "no bars in that period" in _refused_cleanly(settings, db, [later], JANUARY).message


def test_case3_several_datasets_all_without_bars_is_no_eligible_data(settings, db, daily, later):
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily, later], APRIL)
    assert r.state == NO_ELIGIBLE_DATA and len(r.datasets_without_bars) == 2 and r.partial_period_note == ""
    assert "no bars in that period" in _refused_cleanly(settings, db, [daily, later], APRIL).message


@pytest.mark.parametrize("order", ["with_bars_first", "without_bars_first"])
def test_case4_one_dataset_with_bars_and_one_without_is_not_ready_not_no_data(settings, db, daily, later, order):
    """The review finding: this used to be labelled NO DATA IN THIS PERIOD although `daily` has 5 bars."""
    ids = [daily, later] if order == "with_bars_first" else [later, daily]
    r = check_analysis(settings, db, DATASET_SUMMARY, ids, JANUARY)
    assert r.state == NOT_READY and not r.ready
    by_id = {x.dataset_id: x for x in r.reports}
    assert by_id[daily].ready and by_id[daily].rows_in_window == 5  # the underlying per-dataset facts are unchanged
    assert by_id[later].no_eligible_bars and [f.name for f in by_id[later].failures] == ["history"]
    assert [x.dataset_id for x in r.datasets_without_bars] == [later]
    assert "1 of the 2 selected datasets have no bars in this period" in r.partial_period_note
    assert "NSE:LATER" in r.partial_period_note
    res = _refused_cleanly(settings, db, ids, JANUARY)
    assert res.message.startswith("The analysis cannot run reliably:") and "no bars in that period" not in res.message
    assert r.partial_period_note in res.message and "The dates are valid, but this dataset has no bars" in res.message


def test_case5_another_problem_takes_precedence_over_no_data(settings, db, daily, later):
    from dataclasses import replace as _replace

    from qmap.catalog import DataRequirement

    # a selection problem: too many datasets, although every selected dataset is empty in April
    one_only = _replace(DATASET_SUMMARY, max_datasets=1)
    r = check_analysis(settings, db, one_only, [daily, later], APRIL)
    assert r.state == NOT_READY and r.selection_problems and r.partial_period_note == ""
    # a readiness problem: the timeframe is wrong for both, and both are also empty in April
    weekly_only = _replace(DATASET_SUMMARY, requirement=DataRequirement(timeframes=("1W",), min_rows=2))
    r = check_analysis(settings, db, weekly_only, [daily, later], APRIL)
    assert r.state == NOT_READY and all("timeframe" in {f.name for f in x.failures} for x in r.reports)
    _refused_cleanly(settings, db, [daily, later], {**APRIL, "date_from": "31/02/26"})
    # an invalid date wins over everything, even with a dataset that has bars
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily, later], {"date_from": "01/01/0000"})
    assert r.state == INVALID_INPUT and r.reports == []


def test_case6_empty_dates_keep_their_meaning_for_several_datasets(settings, db, daily, later):
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily, later], {"date_from": "", "date_to": ""})
    assert r.state == READY and r.params == {"date_from": None, "date_to": None}
    assert sorted(x.rows_in_window for x in r.reports) == [10, 30] and r.datasets_without_bars == []
    # one end empty: from 02-Mar-26 to the last bar -> `later` has bars, `daily` has none -> NOT READY, explained
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily, later], {"date_from": "02/03/26", "date_to": ""})
    assert r.state == NOT_READY and [x.dataset_id for x in r.datasets_without_bars] == [daily]


def test_the_workbench_text_explains_the_mixed_case_and_keeps_the_others(settings, db, daily, later):
    from qmap_gui.workbench_services import PREPARE_HINT, readiness_parts

    def text(ids, params, spec=DATASET_SUMMARY):
        return "".join(t for t, _tag in readiness_parts(check_analysis(settings, db, spec, ids, params)))

    mixed = text([daily, later], JANUARY)
    assert mixed.startswith("NOT READY") and "NO DATA IN THIS PERIOD" not in mixed
    assert "1 of the 2 selected datasets have no bars in this period" in mixed
    assert PREPARE_HINT not in mixed  # another period is needed, not Database Manager
    assert text([daily, later], APRIL).startswith("NO DATA IN THIS PERIOD")
    assert text([daily], {"date_from": "01/01/0000"}).startswith("INVALID DATE INPUT")
    assert text([daily], JANUARY).startswith("READY")
    too_few = text([daily], {"date_from": "05-01-26", "date_to": "05-01-26"})
    assert too_few.startswith("NOT READY") and PREPARE_HINT in too_few  # unchanged for other refusals


def test_readiness_never_formats_a_typed_date_with_strftime(settings, db, daily, monkeypatch):
    """Windows CI on 9b2d063: date.strftime('%y') refuses years before 1900 there (not on Linux). Readiness messages
    must work for every year the parser accepts, so a strftime anywhere on this path fails here on every platform."""
    import datetime as _dt

    import qmap.catalog as catalog

    class NoStrftime(_dt.date):
        def strftime(self, fmt):
            raise AssertionError("strftime used on a user date")

    monkeypatch.setattr(catalog, "date", NoStrftime)  # covers dates built from the registry's ISO text
    assert catalog.fmt_date("2026-01-05") == "05-Jan-26" and catalog.fmt_date(_dt.date(1, 1, 1)) == "01-Jan-0001"
    assert catalog.fmt_date(NoStrftime(1899, 12, 31)) == "31-Dec-1899"
    r = check_analysis(settings, db, DATASET_SUMMARY, [daily], {"date_from": "01/01/0001", "date_to": "31/12/1899"})
    assert r.state == NO_ELIGIBLE_DATA and "01-Jan-0001 to 31-Dec-1899" in r.reports[0].failures[0].detail
