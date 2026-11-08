"""Plain-English wording for the Foundation's automatic future-date retry (Foundation decision D2-33).

The Foundation records an info check `retry_after_date_limit` on an attempt that is an automatic retry of a file
that was rejected only because some dates were beyond the future-date limit. The GUI must show it in plain English.
"""

import re
from datetime import date
from pathlib import Path

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from qmap.data_engine import ingest as ingest_mod
from qmap.data_engine.results import INFO, CheckResult
from qmap_gui import messages

PACKAGE = Path(__file__).resolve().parents[2] / "Application" / "qmap"


def test_retry_check_has_plain_wording():
    title, meaning, todo = messages.explain("retry_after_date_limit")
    assert "Retried automatically" in title and "rejected" in meaning and todo == "Nothing to do."
    for text in (title, meaning, todo):
        assert "retry_after_date_limit" not in text and "_" not in text  # no technical names in what the user reads


def test_retry_check_is_shown_as_an_information_finding_with_its_details():
    check = CheckResult("retry_after_date_limit", INFO, True, 0,
                        "Automatic retry: attempt 3 was rejected only because some dates were later than the limit.")
    (finding,) = messages.findings_from_checks([check])
    assert finding.severity == "info" and finding.title.startswith("Retried automatically")
    assert "attempt 3" in finding.detail
    assert "[INFO] Retried automatically" in finding.text()


def test_every_check_name_the_foundation_creates_directly_has_plain_wording():
    """Guards the gap that existed for `retry_after_date_limit`: a check that only appears in a rarely-met situation."""
    names = set()
    for path in PACKAGE.rglob("*.py"):
        names |= set(re.findall(r'CheckResult\(\s*"([a-z_]+)"', path.read_text(encoding="utf-8")))
    missing = sorted(n for n in names if n not in messages.CHECKS)
    assert not missing, f"checks without plain-English wording: {missing}"


# ---- end to end with the real Foundation: only meaningful once the Foundation has the retry rule -------------
needs_retry_rule = pytest.mark.skipif(not hasattr(ingest_mod, "_date_limit_retry"),
                                      reason="this Foundation version has no automatic future-date retry")


@needs_retry_rule
def test_real_automatic_retry_is_explained_in_plain_english(settings, db, src):
    from fixtures.profiles import do_ingest
    from qmap.core.runs import finish_run, start_run

    path = write_delimited(src / "future.csv", HEADER, daily_rows(8))  # last bar 14-Jan-26

    def ingest_on(today):
        run = start_run(settings, db, "FOUND", area="Ingestion")
        try:
            return do_ingest(run, path, today=today)
        finally:
            finish_run(run)

    first = ingest_on(date(2026, 1, 10))  # dates up to 14-Jan are beyond the limit of 11-Jan
    blocked = ingest_on(date(2026, 1, 12))
    retried = ingest_on(date(2026, 1, 14))
    assert (first.outcome, blocked.outcome, retried.outcome) == ("rejected", "blocked", "accepted")
    findings = messages.findings_from_checks(retried.checks)
    retry = [f for f in findings if f.check == "retry_after_date_limit"]
    assert len(retry) == 1 and retry[0].severity == "info" and retry[0].title.startswith("Retried automatically")
    shown = retry[0].text() + messages.readable(blocked.message)
    assert "retry_after_date_limit" not in retry[0].text() and "E_" not in shown
    assert messages.OUTCOMES["blocked"] and messages.OUTCOMES["accepted"]
