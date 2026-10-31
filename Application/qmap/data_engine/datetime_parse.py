"""Explicit, auditable date/time parsing.

Every date/time field is parsed with ONE rule declared in the source profile. There is no
fallback format, no unit detection and no time-zone assumption. Values that cannot be
parsed by the declared rule are reported (never repaired, never dropped).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ..core.config import Settings
from ..core.errors import IngestError
from .numeric import parse_number
from .profiles import INTRADAY_MINUTES, DatetimeSpec
from .results import ERROR, Collector

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
EXCEL_EPOCH = datetime(1899, 12, 30)
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}([T ].+)?$")
_TIME_DIRECTIVES = ("%H", "%I", "%M", "%S", "%f")


class _Bad(Exception):
    """A single value that the declared rule cannot parse."""


@dataclass
class ParsedTimes:
    ts_utc: list  # datetime in UTC per row (None where unparseable); empty when the data is date-only
    session_dates: list  # date per row (None where unparseable)
    is_instant: bool
    ambiguous_rows: set = field(default_factory=set)  # 0-based rows flagged: day/month order unverified
    date_order_unverified: bool = False
    provenance: dict = field(default_factory=dict)


def _missing(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _digits_text(v, pad: int | None, counter: list) -> str:
    """Numeric cells (Excel/Parquet) become text; leading zeros lost by the source are restored only if declared."""
    if isinstance(v, bool):
        raise _Bad("is a true/false value, not a date")
    if isinstance(v, int):
        s = str(v)
    elif isinstance(v, float):
        if not math.isfinite(v) or v != int(v):
            raise _Bad("is not a whole number, so it cannot be a date written as digits")
        s = str(int(v))
    else:
        return v
    if pad and len(s) < pad:
        s = s.zfill(pad)
        counter.append(1)
    return s


def _strptime_strict(s: str, fmt: str, pivot: int | None) -> datetime:
    s = s.strip()
    try:
        parsed = datetime.strptime(s, fmt)
    except ValueError:
        raise _Bad(f"does not match the declared format {fmt}") from None
    if "%y" in fmt and pivot is not None:
        yy = parsed.year % 100
        try:
            parsed = parsed.replace(year=(1900 if yy >= pivot else 2000) + yy)
        except ValueError:
            raise _Bad("is not a valid date once the two-digit year rule is applied") from None
    if parsed.strftime(fmt) != s:
        raise _Bad(f"is not written exactly as the declared format {fmt} (check zero-padding and spacing)")
    return parsed


def _parse_iso(v) -> tuple[str, object]:
    if not isinstance(v, str):
        raise _Bad("is not text, so it cannot be an ISO timestamp (declare kind = 'native' or a unix unit)")
    s = v.strip()
    if not _ISO.match(s):
        raise _Bad("is not an ISO 8601 date or timestamp (expected YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS[+HH:MM])")
    if len(s) == 10:
        try:
            return "date", date.fromisoformat(s)
        except ValueError:
            raise _Bad("is not a valid calendar date") from None
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        raise _Bad("is not a valid ISO 8601 timestamp") from None
    return ("aware" if d.tzinfo is not None else "naive"), d


def _unix_hint(unit: str, number: float) -> str:
    if unit == "s" and abs(number) >= 1e11:
        return " The value looks like MILLISECONDS but the profile declares seconds (unix_s)."
    if unit == "ms" and abs(number) < 1e11:
        return " The value looks like SECONDS but the profile declares milliseconds (unix_ms)."
    return ""


def _parse_unix(v, unit: str) -> tuple[str, object, float]:
    number, status = parse_number(v)
    if status != "ok" or not math.isfinite(number):
        raise _Bad("is not a number, so it cannot be a Unix timestamp")
    seconds = number if unit == "s" else number / 1000.0
    try:
        return "aware", EPOCH + timedelta(seconds=seconds), number
    except OverflowError:
        raise _Bad("is far outside any plausible date." + _unix_hint(unit, number)) from None


def _parse_native(v, spec: DatetimeSpec) -> tuple[str, object]:
    if isinstance(v, datetime):
        if spec.precision == "date":
            if v.tzinfo is not None or (v.hour, v.minute, v.second, v.microsecond) != (0, 0, 0, 0):
                raise _Bad("has a time or time zone but the profile declares precision = 'date'")
            return "date", v.date()
        return ("aware" if v.tzinfo is not None else "naive"), v
    if isinstance(v, date):
        if spec.precision == "datetime":
            raise _Bad("is a date without a time but the profile declares precision = 'datetime'")
        return "date", v
    raise _Bad(f"is {type(v).__name__} (text/number), but the profile declares native date values")


def _parse_time_value(v, fmt: str, pad: int | None, counter: list) -> time:
    if isinstance(v, time) and not isinstance(v, datetime):
        return v
    s = _digits_text(v, pad, counter)
    if not isinstance(s, str):
        raise _Bad("is not a time")
    return _strptime_strict(s, fmt, None).time()


def parse_times(values: list, spec: DatetimeSpec, *, timeframe: str, settings: Settings, collector: Collector,
                time_values: list | None = None, today: date | None = None) -> ParsedTimes:
    n = len(values)
    today = today or datetime.now(timezone.utc).date()
    pad_counter: list = []
    parsed: list = [None] * n  # (kind, value)
    unix_numbers: list = [None] * n
    prov: dict = {"kind": spec.kind}

    fmt = spec.format
    has_time_in_format = bool(fmt) and any(d in fmt for d in _TIME_DIRECTIVES)
    excel_numbers: list = [None] * n

    for i, v in enumerate(values):
        try:
            if _missing(v):
                raise _Bad("is missing")
            if spec.kind == "iso":
                parsed[i] = _parse_iso(v)
            elif spec.kind == "format":
                text = _digits_text(v, spec.zero_pad_width, pad_counter)
                if not isinstance(text, str):
                    raise _Bad("is not text")
                d = _strptime_strict(text, fmt, spec.two_digit_year_pivot)
                if has_time_in_format:
                    parsed[i] = ("aware" if d.tzinfo is not None else "naive", d)
                else:
                    parsed[i] = ("date", d.date())
            elif spec.kind in ("unix_s", "unix_ms"):
                kind, d, num = _parse_unix(v, "s" if spec.kind == "unix_s" else "ms")
                parsed[i], unix_numbers[i] = (kind, d), num
            elif spec.kind == "excel_serial":
                num, st = parse_number(v)
                if st != "ok" or not math.isfinite(num):
                    raise _Bad("is not a number, so it cannot be an Excel serial date")
                excel_numbers[i] = num
            elif spec.kind == "native":
                parsed[i] = _parse_native(v, spec)
        except _Bad as exc:
            collector.add("datetime_parseable", ERROR, i + 1, "date", v, f"Value {v!r} {exc}.")

    if spec.kind == "excel_serial":
        has_fraction = any(x is not None and abs(x - round(x)) > 1e-9 for x in excel_numbers)
        prov["excel_serial_has_time_of_day"] = has_fraction
        for i, num in enumerate(excel_numbers):
            if num is None:
                continue
            try:
                d = EXCEL_EPOCH + timedelta(days=num)
            except OverflowError:
                collector.add("datetime_parseable", ERROR, i + 1, "date", values[i],
                              f"Value {values[i]!r} is far outside any plausible date.")
                continue
            if has_fraction:
                # Excel stores times as day fractions with tiny floating-point error: round to the second.
                d = (d + timedelta(microseconds=500_000)).replace(microsecond=0)
                parsed[i] = ("naive", d)
            else:
                parsed[i] = ("date", d.date())

    # separate time column -------------------------------------------------------
    if time_values is not None:
        combined = [None] * n
        for i in range(n):
            if parsed[i] is None:
                continue
            try:
                if _missing(time_values[i]):
                    raise _Bad("is missing")
                kind, dval = parsed[i]
                if kind != "date":
                    raise _Bad("cannot be combined because the date column already contains a time")
                t = _parse_time_value(time_values[i], spec.time_format, spec.time_zero_pad_width, pad_counter)
                combined[i] = ("naive", datetime.combine(dval, t))
            except _Bad as exc:
                collector.add("datetime_parseable", ERROR, i + 1, "time", time_values[i],
                              f"Time value {time_values[i]!r} {exc}.")
        parsed = combined
        prov["date_and_time_columns_combined"] = True
    if pad_counter:
        prov["zero_padded_values"] = len(pad_counter)

    ok = [p for p in parsed if p is not None]
    kinds = {k for k, _ in ok}
    ambiguous_rows: set[int] = set()
    unverified = False

    if not ok:
        return ParsedTimes([], [None] * n, False, provenance=prov)

    if "date" in kinds and kinds != {"date"}:
        raise IngestError("The date column mixes date-only values and values with a time of day.",
                          code="E_MIXED_DATETIME", check="datetime_parseable",
                          action="Use one consistent layout per column, or split the file.")
    if {"naive", "aware"} <= kinds:
        raise IngestError("The timestamp column mixes values with and without a UTC offset.",
                          code="E_MIXED_TIMEZONE", check="timezone_declared",
                          action="Use one consistent layout per column, or split the file.")

    is_instant = kinds != {"date"}
    session_dates: list = [None] * n
    ts_utc: list = [None] * n

    if not is_instant:
        if timeframe in INTRADAY_MINUTES:
            raise IngestError(f"The dates carry no time of day but the timeframe is intraday ({timeframe}).",
                              code="E_TIMEFRAME_MISMATCH", check="datetime_parseable",
                              action="Check the timeframe in the profile, or use a source with timestamps.")
        for i, p in enumerate(parsed):
            if p is not None:
                session_dates[i] = p[1]
        prov["result"] = "date"
        if spec.kind == "format" and fmt and "%d" in fmt and "%m" in fmt and not fmt.lstrip().startswith("%Y"):
            evidence = 0
            candidate_rows = []
            for i, p in enumerate(parsed):
                if p is None:
                    continue
                d = p[1]
                if d.day > 12:
                    evidence += 1
                elif d.day != d.month:
                    candidate_rows.append(i)
            unverified = evidence == 0
            prov["order_audit"] = {"rows_proving_declared_order": evidence,
                                   "rows_that_fit_both_orders": len(candidate_rows),
                                   "verified": not unverified}
            if unverified:
                ambiguous_rows = set(candidate_rows)
                collector.add("date_order_unverified", "warning", None, "date", None,
                              f"Every date has a day of 12 or less, so day-first and month-first cannot be told apart "
                              f"from the data. The profile declares {fmt}; please confirm it is correct.")
    else:
        zone_name = spec.timezone
        zone = None
        if "naive" in kinds:
            if not zone_name:
                raise IngestError("The timestamps have no UTC offset and the profile declares no time zone.",
                                  code="E_TZ_REQUIRED", check="timezone_declared",
                                  action="Set [datetime] timezone (for example \"Asia/Kolkata\"). Q-MAP never assumes it.")
            zone = ZoneInfo(zone_name)
            prov["timezone_applied"] = zone_name
        if not spec.exchange_timezone:
            raise IngestError("The profile declares no exchange_timezone, which is needed to work out each bar's trading date.",
                              code="E_TZ_REQUIRED", check="timezone_declared",
                              action="Set [datetime] exchange_timezone (for example \"Asia/Kolkata\").")
        exch = ZoneInfo(spec.exchange_timezone)
        offsets = set()
        for i, p in enumerate(parsed):
            if p is None:
                continue
            kind, d = p
            if kind == "naive":
                a, b = d.replace(tzinfo=zone, fold=0), d.replace(tzinfo=zone, fold=1)
                if a.utcoffset() != b.utcoffset():
                    collector.add("datetime_parseable", ERROR, i + 1, "date", d.isoformat(),
                                  f"The local time {d.isoformat()} is ambiguous in {zone_name} (clocks go back); "
                                  "it is not guessed.")
                    continue
                aware = a
                if aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != d:
                    collector.add("datetime_parseable", ERROR, i + 1, "date", d.isoformat(),
                                  f"The local time {d.isoformat()} does not exist in {zone_name} (clocks go forward).")
                    continue
            else:
                aware = d
                if spec.kind != "unix_s" and spec.kind != "unix_ms":
                    offsets.add(str(d.utcoffset()))
            utc = aware.astimezone(timezone.utc)
            ts_utc[i] = utc
            session_dates[i] = utc.astimezone(exch).date()
        if offsets:
            prov["source_utc_offsets"] = sorted(offsets)
        prov.update({"result": "instant", "exchange_timezone": spec.exchange_timezone, "session_date_derived": True})

    # plausible range -------------------------------------------------------------
    lo, hi = settings.plausible_min_date, today + timedelta(days=settings.plausible_max_days_ahead)
    for i in range(n):
        d = session_dates[i] if session_dates[i] is not None else None
        if d is None:
            continue
        if d < lo or d > hi:
            hint = _unix_hint("s" if spec.kind == "unix_s" else "ms", unix_numbers[i]) if unix_numbers[i] is not None else ""
            collector.add("date_in_range", ERROR, i + 1, "date", values[i],
                          f"Date {d.isoformat()} is outside the plausible range {lo.isoformat()} to {hi.isoformat()}.{hint}")
            session_dates[i] = None
            ts_utc[i] = None
    if spec.kind in ("unix_s", "unix_ms"):
        numbers = [parse_number(v)[0] for v in values if not _missing(v)]
        lengths = {len(str(int(abs(x)))) for x in numbers if math.isfinite(x)}
        if len(lengths) > 1 and (max(lengths) - min(lengths)) >= 3:
            collector.add("datetime_parseable", "warning", None, "date", None,
                          f"The Unix timestamps have mixed digit lengths {sorted(lengths)}, which can mean seconds and "
                          "milliseconds are mixed in one column.")
    return ParsedTimes(ts_utc=ts_utc if is_instant else [], session_dates=session_dates, is_instant=is_instant,
                       ambiguous_rows=ambiguous_rows, date_order_unverified=unverified, provenance=prov)
