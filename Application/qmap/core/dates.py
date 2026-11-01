"""Dates typed by a person (Analytical Workbench start/end dates). One authoritative, deterministic parser.

Accepted (day always first, then month, then year):

  25/02/26     day/month/two-digit year
  25-02-26     day-month-two-digit year
  25-Feb-26    day-month abbreviation-two-digit year (English, any letter case: feb, FEB, Feb)
  250226       exactly six digits = DDMMYY (never read as a Unix timestamp or any other number)

Also accepted, as before: the same forms with a four-digit year (25/02/2026, 25-02-2026, 25-Feb-2026),
spaces instead of hyphens around a month abbreviation (25 Feb 26), and ISO dates (2026-02-25).

Two-digit years (the same rule as Q-MAP's ingestion profiles, `two_digit_year_pivot = 69`):
  00-68 -> 2000-2068      69-99 -> 1969-1999
It is applied in this module itself, never by an operating-system or library default.

Anything else is refused with a message that shows the supported formats; an impossible date such as 31/02/26 is
refused as "not a real calendar date". Nothing here depends on the computer's language or regional settings.
"""

from __future__ import annotations

import calendar
import re
from datetime import date

TWO_DIGIT_YEAR_PIVOT = 69  # same rule as datetime_parse / the example profiles
FORMAT_EXAMPLES = "25/02/26, 25-02-26, 25-Feb-26 or 250226"
FORMAT_HELP = f"Use day, month, year, for example {FORMAT_EXAMPLES}."
MONTHS = {m.lower(): n for n, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                              "Nov", "Dec"), start=1)}
MONTH_ABBR = {n: m.capitalize() for m, n in MONTHS.items()}

_NUMERIC = re.compile(r"^(\d{1,2})([/-])(\d{1,2})\2(\d{2}|\d{4})$")
_NAMED = re.compile(r"^(\d{1,2})(?:-| +)([A-Za-z]{3})(?:-| +)(\d{2}|\d{4})$")
_COMPACT = re.compile(r"^(\d{2})(\d{2})(\d{2})$")
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


class DateInputError(ValueError):
    """The text is not a usable date; the message is written for the person who typed it."""


def expand_two_digit_year(yy: int) -> int:
    if not 0 <= yy <= 99:
        raise ValueError(yy)
    return (1900 if yy >= TWO_DIGIT_YEAR_PIVOT else 2000) + yy


def _year(text: str) -> int:
    return expand_two_digit_year(int(text)) if len(text) == 2 else int(text)


def _build(raw: str, day: int, month: int, year: int) -> date:
    if not 1 <= month <= 12:
        raise DateInputError(f"'{raw}' is not a real calendar date: there is no month {month}. {FORMAT_HELP}")
    last = calendar.monthrange(year, month)[1]
    if not 1 <= day <= last:
        raise DateInputError(f"'{raw}' is not a real calendar date: {calendar.month_name[month]} {year} has {last} days.")
    return date(year, month, day)


def parse_user_date(text: str | date | None) -> date | None:
    """A typed date as a `date`; None for a blank field. Raises DateInputError with a plain-English message."""
    if text is None or isinstance(text, date):
        return text
    raw = str(text).strip()
    if raw == "":
        return None
    m = _NUMERIC.match(raw)
    if m:
        return _build(raw, int(m.group(1)), int(m.group(3)), _year(m.group(4)))
    m = _NAMED.match(raw)
    if m:
        month = MONTHS.get(m.group(2).lower())
        if month is None:
            raise DateInputError(f"'{raw}': '{m.group(2)}' is not a month abbreviation (Jan, Feb ... Dec). {FORMAT_HELP}")
        return _build(raw, int(m.group(1)), month, _year(m.group(3)))
    m = _COMPACT.match(raw)
    if m:
        return _build(raw, int(m.group(1)), int(m.group(2)), _year(m.group(3)))
    m = _ISO.match(raw)
    if m:
        return _build(raw, int(m.group(3)), int(m.group(2)), int(m.group(1)))
    if raw.isdigit():
        raise DateInputError(f"'{raw}' is not a supported date: a date written only in digits must have exactly six "
                             f"digits, day-month-year (250226 = 25-Feb-26). {FORMAT_HELP}")
    raise DateInputError(f"'{raw}' is not a date Q-MAP understands. {FORMAT_HELP}")


def format_for_entry(d: date) -> str:
    """How Q-MAP writes a date into a date box: dd-Mmm-yy (e.g. 25-Feb-26), which parse_user_date reads back."""
    return f"{d.day:02d}-{MONTH_ABBR[d.month]}-{d.year % 100:02d}"


def format_long(d: date) -> str:
    """Unambiguous confirmation shown next to a date box (four-digit year): 25-Feb-2026."""
    return f"{d.day:02d}-{MONTH_ABBR[d.month]}-{d.year}"
