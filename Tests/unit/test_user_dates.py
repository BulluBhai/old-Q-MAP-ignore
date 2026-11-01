"""Dates typed in the Analytical Workbench (requirement 2.2-2.4): formats, the two-digit-year rule, refusals."""

from __future__ import annotations

import locale
from datetime import date

import pytest

from qmap.core.dates import (TWO_DIGIT_YEAR_PIVOT, DateInputError, expand_two_digit_year, format_for_entry, format_long,
                             parse_user_date)


@pytest.mark.parametrize("text", ["25/02/26", "25-02-26", "25-Feb-26", "250226"])
def test_the_four_required_formats_all_mean_25_february_2026(text):
    assert parse_user_date(text) == date(2026, 2, 25)


def test_six_digits_are_always_ddmmyy_never_a_number_or_timestamp():
    assert parse_user_date("010203") == date(2003, 2, 1)  # 01-02-03: day 1, February, 2003
    assert parse_user_date("311299") == date(1999, 12, 31)
    with pytest.raises(DateInputError, match="exactly six digits"):
        parse_user_date("1793262840")  # a Unix timestamp is refused, not converted
    for digits in ("2502", "25026", "2502260", "25022026"):  # any other length of digits is refused
        with pytest.raises(DateInputError, match="exactly six digits"):
            parse_user_date(digits)


@pytest.mark.parametrize("yy, year", [("00", 2000), ("26", 2026), ("68", 2068), ("69", 1969), ("95", 1995), ("99", 1999)])
def test_two_digit_year_rule_is_the_same_for_every_format(yy, year):
    assert TWO_DIGIT_YEAR_PIVOT == 69 and expand_two_digit_year(int(yy)) == year
    for text in (f"15/06/{yy}", f"15-06-{yy}", f"15-Jun-{yy}", f"1506{yy}"):
        assert parse_user_date(text) == date(year, 6, 15), text


def test_the_rule_matches_the_ingestion_profiles_pivot():
    """Workbench dates and profile dates must agree (profiles use two_digit_year_pivot = 69)."""
    from pathlib import Path

    from qmap.data_engine.profiles import load_profile

    repo = Path(__file__).resolve().parents[2]
    profile = load_profile(repo / "Configuration/source_profiles/csv_hdr_ddmmyy.toml")
    assert profile.datetime.two_digit_year_pivot == TWO_DIGIT_YEAR_PIVOT


@pytest.mark.parametrize("text", ["25-feb-26", "25-FEB-26", "25 Feb 26", "  25-Feb-26  ", "25/02/2026", "25-02-2026",
                                  "25-Feb-2026", "2026-02-25", "5/2/26", "5-Feb-26"])
def test_other_accepted_spellings(text):
    assert parse_user_date(text) in (date(2026, 2, 25), date(2026, 2, 5))


def test_month_names_do_not_depend_on_the_computers_language(monkeypatch):
    monkeypatch.setattr(locale, "getlocale", lambda *a: ("de_DE", "UTF-8"))
    assert parse_user_date("25-Mar-26") == date(2026, 3, 25)


def test_blank_means_not_given():
    assert parse_user_date("") is None and parse_user_date("   ") is None and parse_user_date(None) is None


@pytest.mark.parametrize("text, message", [
    ("31/02/26", "February 2026 has 28 days"),
    ("29-02-25", "February 2025 has 28 days"),
    ("32-01-26", "January 2026 has 31 days"),
    ("15-13-26", "no month 13"),
    ("310426", "April 2026 has 30 days"),
    ("00-01-26", "January 2026 has 31 days"),
])
def test_impossible_calendar_dates_are_refused_as_such(text, message):
    with pytest.raises(DateInputError, match="not a real calendar date") as exc:
        parse_user_date(text)
    assert message in str(exc.value)


def test_29_february_in_a_leap_year_is_valid():
    assert parse_user_date("29/02/28") == date(2028, 2, 29)


@pytest.mark.parametrize("text", ["25.02.26", "2026/02/25", "Feb 25 2026", "25-Fbr-26", "25-02", "tomorrow", "25-02/26"])
def test_unsupported_formats_are_refused_with_examples(text):
    with pytest.raises(DateInputError) as exc:
        parse_user_date(text)
    assert "25/02/26, 25-02-26, 25-Feb-26 or 250226" in str(exc.value)


def test_what_the_window_writes_reads_back_the_same():
    for d in (date(2026, 2, 25), date(1999, 12, 31), date(2000, 1, 1), date(2068, 7, 4)):
        assert parse_user_date(format_for_entry(d)) == d
    assert format_for_entry(date(2026, 2, 25)) == "25-Feb-26" and format_long(date(2026, 2, 25)) == "25-Feb-2026"
