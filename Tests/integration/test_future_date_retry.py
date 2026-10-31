"""Future-date rejection and retry (follow-up review, finding F-01; decision log D2-33).

The run date is deliberately not part of the processing identity (D2-32). A file rejected ONLY because some of
its dates lie beyond the "not in the future" limit must therefore be retried automatically once the run date has
moved far enough for those dates to be valid, while an unchanged retry that cannot succeed stays blocked.
All dates are controlled explicitly; nothing depends on the day CI runs.
"""

import dataclasses
import json
from datetime import date

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest
from qmap.core.runs import finish_run, start_run
from qmap.storage.faults import InjectedFault, inject
from qmap.storage.files import sha256_file
from qmap.storage.recovery import recover_incomplete, verify_registry

ROWS = daily_rows(8)  # weekdays 05-Jan-26 .. 14-Jan-26
LAST = date(2026, 1, 14)
EARLY = date(2026, 1, 10)  # limit = today + 1 day = 11-Jan-26: rows of 12, 13 and 14-Jan-26 are "in the future"


@pytest.fixture
def good(src):
    return write_delimited(src / "good.csv", HEADER, ROWS)


def ingest_on(settings, db, path, today, **kw):
    run = start_run(settings, db, "FOUND", area="Ingestion")
    try:
        return do_ingest(run, path, today=today, **kw)
    finally:
        finish_run(run)


def attempts(db):
    return db.query("SELECT * FROM ingest_attempts ORDER BY attempt_id")


def cleaned(db):
    return db.query("SELECT * FROM datasets WHERE layer='cleaned' ORDER BY dataset_id")


def failed_checks(db, attempt_id):
    return {r["check_name"] for r in db.query(
        "SELECT check_name FROM quality_checks WHERE attempt_id=? AND severity='error' AND passed=0", (attempt_id,))}


# ---- Scenario A: rejected because of future dates, later valid ------------------------------------------------
def test_a_future_dated_file_is_retried_automatically_once_its_dates_are_valid(settings, db, good):
    raw_sha = sha256_file(good)
    first = ingest_on(settings, db, good, EARLY)
    assert first.outcome == "rejected" and failed_checks(db, first.attempt_id) == {"date_in_range"}
    rec = json.loads(attempts(db)[0]["datetime_rules_json"])["applied"]["plausible_range"]
    assert rec == {"min": "1990-01-01", "max": "2026-01-11", "rows_before_min": 0, "rows_after_max": 3,
                   "latest_date_after_max": "2026-01-14"}

    later = ingest_on(settings, db, good, LAST)  # 14-Jan-26: every date is now within the limit
    assert later.outcome == "accepted", later.message
    a = attempts(db)
    assert [x["outcome"] for x in a] == ["rejected", "accepted"]
    assert a[1]["revalidation_of_attempt_id"] == a[0]["attempt_id"] and a[1]["force_reason"] is None
    assert a[0]["config_fingerprint"] == a[1]["config_fingerprint"]  # same identity, the run date moved
    retry_note = db.one("SELECT * FROM quality_checks WHERE attempt_id=? AND check_name='retry_after_date_limit'",
                        (later.attempt_id,))
    assert retry_note["severity"] == "info" and str(first.attempt_id) in retry_note["detail"]
    # the original rejection and its diagnostics are untouched
    assert failed_checks(db, first.attempt_id) == {"date_in_range"} and first.issues_report.exists()
    assert len(cleaned(db)) == 1 and cleaned(db)[0]["created_by_attempt_id"] == later.attempt_id
    assert sha256_file(good) == raw_sha and not verify_registry(settings, db).needs_attention


def test_a_retry_before_the_dates_are_valid_stays_blocked_and_says_when_it_will_be_allowed(settings, db, good):
    ingest_on(settings, db, good, EARLY)
    too_soon = ingest_on(settings, db, good, date(2026, 1, 12))  # limit 13-Jan-26 < 14-Jan-26
    assert too_soon.outcome == "blocked"
    assert "2026-01-13" in too_soon.message or "13-Jan-26" in too_soon.message  # earliest run date that works
    assert len(attempts(db)) == 1


# ---- Scenario B: unchanged retry on the same date ----------------------------------------------------------
def test_b_unchanged_retry_on_the_same_date_is_blocked_deterministically(settings, db, good):
    first = ingest_on(settings, db, good, EARLY)
    second = ingest_on(settings, db, good, EARLY)
    third = ingest_on(settings, db, good, EARLY)
    assert first.outcome == "rejected" and (second.outcome, third.outcome) == ("blocked", "blocked")
    assert second.message == third.message and len(attempts(db)) == 1 and not cleaned(db)


def test_b_a_rejection_that_time_cannot_cure_stays_blocked_on_later_dates(settings, db, src):
    rows = [list(r) for r in ROWS]
    rows[2][3] = 500  # Low far above everything: an OHLC error
    bad = write_delimited(src / "bad.csv", HEADER, rows)
    first = ingest_on(settings, db, bad, EARLY)  # OHLC error AND future dates
    assert failed_checks(db, first.attempt_id) == {"date_in_range", "low_le_open_close", "low_le_high"}
    assert ingest_on(settings, db, bad, LAST).outcome == "blocked"


def test_b_dates_before_the_minimum_are_never_cured_by_time(settings, db, src):
    rows = [list(r) for r in ROWS]
    rows[0][0] = "1985-01-02"
    old = write_delimited(src / "old.csv", HEADER, rows)
    assert ingest_on(settings, db, old, EARLY).outcome == "rejected"
    assert ingest_on(settings, db, old, date(2030, 1, 1)).outcome == "blocked"


# ---- Scenario C: configuration changes -------------------------------------------------------------------------
def test_c_more_days_ahead_is_a_new_identity_and_processes_immediately(settings, db, good):
    first = ingest_on(settings, db, good, EARLY)
    wider = dataclasses.replace(settings, plausible_max_days_ahead=10)
    second = ingest_on(wider, db, good, EARLY)
    assert (first.outcome, second.outcome) == ("rejected", "accepted")
    a = attempts(db)
    assert a[0]["config_fingerprint"] != a[1]["config_fingerprint"]
    third = ingest_on(settings, db, good, LAST)  # back to the original settings, now valid: retried, not mixed up
    assert third.outcome == "accepted" and len(cleaned(db)) == 2
    assert cleaned(db)[0]["status"] == "superseded" and cleaned(db)[1]["config_fingerprint"] == a[0]["config_fingerprint"]


def test_c_an_accepted_result_is_reused_on_later_dates_without_reprocessing(settings, db, good):
    first = ingest_on(settings, db, good, LAST)
    later = ingest_on(settings, db, good, date(2026, 6, 30))
    assert (first.outcome, later.outcome) == ("accepted", "reused") and len(attempts(db)) == 2


# ---- Scenario D: explicit forced retry ---------------------------------------------------------------------
def test_d_force_reason_does_not_bypass_validation_and_keeps_the_audit_trail(settings, db, good):
    first = ingest_on(settings, db, good, EARLY)
    forced = ingest_on(settings, db, good, EARLY, force_reason="checking the provider's corrected file")
    assert forced.outcome == "rejected"  # still invalid on this date: validation is never bypassed
    a = attempts(db)
    assert [x["outcome"] for x in a] == ["rejected", "rejected"]
    assert a[1]["force_reason"] == "checking the provider's corrected file"
    assert a[1]["revalidation_of_attempt_id"] == first.attempt_id
    assert forced.issues_report != first.issues_report and first.issues_report.exists()
    assert len(db.query("SELECT * FROM datasets WHERE layer='raw'")) == 1 and not verify_registry(settings, db).needs_attention


# ---- Scenario E: interruption during the automatic retry ---------------------------------------------------
def test_e_crash_during_the_automatic_retry_is_recovered_and_the_retry_completes_once(settings, db, good):
    ingest_on(settings, db, good, EARLY)
    run = start_run(settings, db, "FOUND", area="Ingestion")
    with pytest.raises(InjectedFault):
        with inject("before_result_commit"):
            do_ingest(run, good, today=LAST)
    run._release_lock()  # the process died
    report = recover_incomplete(settings, db, stale_minutes=0)
    assert report.deleted_cleaned_orphans and not report.failed_events  # the raw receipt itself was complete
    assert [x["outcome"] for x in attempts(db)] == ["rejected"]  # nothing half-recorded
    again = ingest_on(settings, db, good, LAST)
    assert again.outcome == "accepted" and len(cleaned(db)) == 1
    assert [x["outcome"] for x in attempts(db)] == ["rejected", "accepted"]
    assert not verify_registry(settings, db).needs_attention
