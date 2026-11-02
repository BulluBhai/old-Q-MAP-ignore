"""Automatic interpretation of a market-data file (Blueprint v1.3 §8.5.1, §8.5.4).

Q-MAP works out a file's layout from evidence in the file itself and turns it into an ordinary source profile, so
the existing engine still does all reading, parsing, validation, storage and registration. Nothing here writes to
the file or to the registry.

Decisions are made only when the evidence is unambiguous. Otherwise the result is a QUESTION for the user (the answer
is recorded and reused only for a file with the same structure) or a REJECTION with a plain reason. The rules are
numbered A-1 ... A-9 and documented in docs/architecture/Blueprint_v1.3_Implementation_Audit.md, section 6:

  A-1 format from the bytes          A-4 column names (fixed alias lists)      A-7 time zone (folder's market zone)
  A-2 delimiter (text)               A-5 headerless positional rule            A-8 instrument identity
  A-3 header row                     A-6 date/time format                      A-9 timeframe from the data

The generated profile's ID is the hash of its own text ("auto_<12 hex>"): the same layout and answers always give the
same profile, so re-scanning an unchanged file reuses the earlier result (processing identity D2-32).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..core.config import Settings
from ..core.errors import IngestError
from .datetime_parse import parse_times
from .format_detect import PARQUET, TEXT, XLS, XLSX, detect_format
from .instruments import normalise_exchange, normalise_symbol
from .mapping import SourceTable
from .numeric import OK, parse_number
from .profiles import ALLOWED_TIMEFRAMES, DatetimeSpec, FileSpec, SourceProfile, parse_profile
from .readers import read_source
from .results import Collector

RULES_VERSION = 3  # bump when any rule below changes how the same file would be interpreted
# 2 (02-Nov-26, owner decision DQ-2): an exchange column is always used, and a file name that contradicts an exchange
#   or symbol column is rejected (v1 let a file-name exchange replace an exchange column when there was no symbol column)
# 3 (02-Nov-26, PR #9 acceptance findings F-01..F-03): "min" timeframe tokens in file names; market prefix CRYPTO_
#   (symbol from the name, exchange/venue never defaulted); plain-name symbol only when the rest of the name is a
#   timeframe token, otherwise suggested; headerless date + time columns; a timeframe answer that contradicts a
#   clearly measured intraday bar interval is not used (asked again, or rejected when no timeframe fits).
#   180-minute bars = 3h: a new timeframe value, pending the owner's approval (DQ-7); separate commit.
# The rules version decides whether an unchanged file is interpreted again (scan fingerprint). The generated profile
# and the structure signature use the PINNED values below, so a file whose interpretation is unchanged keeps the same
# profile (its datasets are reused, not re-created) and its recorded answers stay valid (decision D5-16).
PROFILE_RULES_SEED = 2
SIGNATURE_RULES = 2

READY, NEEDS_ANSWER, REJECTED = "ready", "needs_answer", "rejected"

# A-2 ------------------------------------------------------------------------------------------------------------
DELIMITERS = (",", ";", "\t", "|")
MIN_COLUMNS = 5  # date + open, high, low, close

# A-4: exact names after normalisation (lower case, spaces/underscores/hyphens/dots collapsed to one space).
# Tier 1 wins over tier 2; two matches in the same tier are ambiguous.
ALIASES = {
    "date": (("date", "time", "datetime", "date time", "timestamp"), ("trade date", "tradedate", "day", "dt")),
    "open": (("open",), ("o", "open price")),
    "high": (("high",), ("h", "high price")),
    "low": (("low",), ("l", "low price")),
    "close": (("close",), ("c", "close price", "last", "ltp", "last price")),
    "volume": (("volume", "vol"), ("qty", "quantity", "traded quantity", "total traded quantity")),
    "symbol": (("symbol", "ticker"), ("tradingsymbol", "trading symbol", "scrip")),
    "exchange": (("exchange",), ("exch",)),
}
# A-8: exchange codes recognised at the start of a file name ("NSE_NIFTY, 1D.csv").
KNOWN_EXCHANGES = ("NSE", "BSE", "MCX", "NFO", "BFO", "CDS", "NCDEX", "NYSE", "NASDAQ", "AMEX", "LSE")
# Market prefixes ("CRYPTO_RIVERUSD, 180.csv"): the name gives the symbol, but NOT the exchange or venue, and the
# folder's default exchange (an equity exchange such as NSE) is never applied to them: the venue is always asked.
MARKET_PREFIXES = ("CRYPTO",)
_NAME_ID = re.compile(r"^(?P<exchange>[A-Za-z]+)_(?P<symbol>[A-Za-z0-9&-]+)(?=$|[,_ .(])")
_PLAIN_SYMBOL = re.compile(r"^[A-Za-z0-9&-]+$")
# A-9: timeframe token in a file name: ", 1D", ", 5", "_5m", "_1h" ... (evidence only, never decisive).
_NAME_TF = re.compile(r"(?:, ?|_)(\d{1,3})(min|[mhHdDwWM]?)(?=$|[ _(.\-])")
_TIME_OF_DAY = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")

# A-6: candidate date/time layouts. Each is tested with the SAME parser the engine uses (datetime_parse).
TWO_DIGIT_YEAR_PIVOT = 69  # Q-MAP's existing fixed rule: 00-68 -> 2000-2068, 69-99 -> 1969-1999
_DATE_FORMATS = ("%d-%m-%Y", "%d-%m-%y", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%y-%m-%d",
                 "%d.%m.%Y", "%Y/%m/%d", "%Y%m%d", "%d-%b-%Y", "%d-%b-%y", "%d %b %Y")
_TIME_SUFFIXES = ("", " %H:%M", " %H:%M:%S")
_TIME_FORMATS = ("%H:%M", "%H:%M:%S")
INTRADAY_STEPS = {1: "1m", 5: "5m", 15: "15m", 30: "30m", 60: "1h", 180: "3h", 240: "4h"}
MIN_BARS_FOR_TIMEFRAME = 3
MIN_STEP_SHARE = 0.6


@dataclass
class Question:
    key: str  # date_format | market_timezone | identity | timeframe
    text: str
    options: tuple = ()

    def as_dict(self) -> dict:
        return {"key": self.key, "text": self.text, "options": list(self.options)}


@dataclass
class Interpretation:
    status: str  # ready | needs_answer | rejected
    message: str = ""
    profile: SourceProfile | None = None
    overrides: dict = field(default_factory=dict)  # exchange / symbol / timeframe passed to ingest_file
    evidence: list = field(default_factory=list)  # plain-English decisions, in order
    questions: list = field(default_factory=list)
    signature: str = ""  # structure signature: answers are reused only for the same signature
    decisions: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"status": self.status, "message": self.message, "rules_version": RULES_VERSION,
                "profile_id": self.profile.profile_id if self.profile else None, "overrides": self.overrides,
                "evidence": self.evidence, "questions": [q.as_dict() for q in self.questions],
                "signature": self.signature, "decisions": self.decisions}


class _Reject(Exception):
    pass


def _norm(name) -> str:
    return re.sub(r"[\s_.\-]+", " ", str(name).strip().strip('"').casefold()).strip()


def _is_number(v) -> bool:
    if isinstance(v, bool):
        return False
    return parse_number(v)[1] == OK


def _is_blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


# ---------------------------------------------------------------------------------------------------------------
# A-1 ... A-3: read the table
# ---------------------------------------------------------------------------------------------------------------

def _read_text(path: Path, evidence: list) -> tuple[SourceTable, str]:
    fits = []
    for d in DELIMITERS:
        try:
            t = read_source(path, TEXT, FileSpec(header=False, delimiter=d))
        except IngestError as exc:
            if exc.code == "E_ENCODING":
                raise _Reject("The file is not readable as UTF-8 or UTF-16 text. Save it as UTF-8 and scan again.")
            continue
        if t.n_cols >= MIN_COLUMNS:
            fits.append((d, t))
    if not fits:
        raise _Reject("Q-MAP cannot tell how the columns are separated: no separator (comma, semicolon, tab or '|') "
                      f"splits every line into the same number of fields (at least {MIN_COLUMNS}: date, open, high, "
                      "low, close).")
    if len(fits) > 1:
        names = " and ".join(repr(d) for d, _ in fits)
        raise _Reject(f"The column separator is ambiguous: both {names} split every line consistently.")
    d, t = fits[0]
    evidence.append(f"A-2 separator {d!r}: every line has {t.n_cols} fields.")
    return t, d


def _looks_like_header(row: list) -> bool:
    cells = [c for c in row if not _is_blank(c)]
    return bool(cells) and all(isinstance(c, str) and re.search(r"[A-Za-z]", c) and not _is_number(c) for c in cells) \
        and not _ISO_LIKE.match(str(cells[0]).strip())


_ISO_LIKE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _split_header(t: SourceTable) -> tuple[list, list, bool]:
    """(names, columns, header) from a table read WITHOUT a header."""
    if t.n_rows == 0:
        raise _Reject("The file contains no rows.")
    first = [col[0] for col in t.columns]
    if _looks_like_header(first):
        return [None if _is_blank(c) else str(c).strip() for c in first], [col[1:] for col in t.columns], True
    return [None] * t.n_cols, t.columns, False


# ---------------------------------------------------------------------------------------------------------------
# A-4 / A-5: columns
# ---------------------------------------------------------------------------------------------------------------

def _find(names: list, field_: str) -> int | None:
    normed = [None if n is None else _norm(n) for n in names]
    for tier in ALIASES[field_]:
        hits = [i for i, n in enumerate(normed) if n in tier]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise _Reject(f"Two columns could be the {field_} column ({', '.join(repr(names[i]) for i in hits)}); "
                          "Q-MAP does not choose between them.")
    return None


def _map_named(names: list, evidence: list) -> dict:
    mapping = {}
    date_idx = None
    normed = [None if n is None else _norm(n) for n in names]
    # a "date" column plus a separate "time" column
    if "date" in normed and "time" in normed and normed.count("date") == 1 and normed.count("time") == 1:
        date_idx, mapping["time"] = normed.index("date"), normed.index("time")
    else:
        date_idx = _find(names, "date")
    if date_idx is None:
        raise _Reject(f"No date column was recognised. Columns found: {[n for n in names if n]}. Expected a name such "
                      "as 'date', 'time', 'datetime' or 'timestamp'.")
    mapping["date"] = date_idx
    for f in ("open", "high", "low", "close"):
        i = _find(names, f)
        if i is None:
            raise _Reject(f"No {f} column was recognised. Columns found: {[n for n in names if n]}.")
        mapping[f] = i
    if len(set(mapping.values())) != len(mapping):
        raise _Reject("The same column was recognised for two different fields.")
    for f in ("volume", "symbol", "exchange"):
        i = _find(names, f)
        if i is not None and i not in mapping.values():
            mapping[f] = i
    shown = ", ".join(f"{k} = {names[v]!r}" for k, v in mapping.items())
    evidence.append(f"A-4 columns by name: {shown}.")
    others = [names[i] or f"column {i + 1}" for i in range(len(names)) if i not in mapping.values()]
    if others:
        evidence.append(f"Kept unchanged as additional fields (not used in calculations): {others}.")
    return mapping


def _is_time_of_day(v) -> bool:
    return isinstance(v, time) or (isinstance(v, str) and bool(_TIME_OF_DAY.match(v.strip())))


def _map_positional(columns: list, evidence: list) -> dict:
    n_rows = len(columns[0])
    # Date and time in two columns ("2024-01-20,12:10:00,589.9,..."): column 2 is a time of day on EVERY row and
    # column 1 never carries one. Then columns 3-6 are open, high, low, close and the same checks apply, one column on.
    split_time = (len(columns) >= MIN_COLUMNS + 1 and all(_is_time_of_day(v) for v in columns[1])
                  and not any(_is_time_of_day(v) or (isinstance(v, str) and ":" in v) for v in columns[0]))
    first = 2 if split_time else 1
    nums = []
    for j in range(first, first + 4):
        vals = [parse_number(v) for v in columns[j]]
        if any(st != OK or not math.isfinite(x) for x, st in vals):
            order = "date, time, open, high, low, close" if split_time else "date, open, high, low, close"
            raise _Reject(f"The file has no header row, and column {j + 1} is not a number on every row, so the "
                          f"column order ({order}) cannot be confirmed.")
        nums.append([x for x, _ in vals])
    o, h, l, c = nums
    bad = [i + 1 for i in range(n_rows) if not (h[i] >= max(o[i], c[i], l[i]) and l[i] <= min(o[i], c[i], h[i]))]
    c1, c4 = first + 1, first + 4  # 1-based numbers of the open and close columns
    if bad:
        raise _Reject(f"The file has no header row, and on {len(bad)} row(s) (e.g. row {bad[0]}) columns {c1}-{c4} do "
                      "not behave like open, high, low, close, so their order cannot be confirmed. Add a header row.")
    mapping = {"date": 0, "open": first, "high": first + 1, "low": first + 2, "close": first + 3}
    if split_time:
        mapping["time"] = 1
    note = f"columns {c1}-{c4} = open, high, low, close (high and low bound open and close on every row)"
    vol = first + 4  # 0-based position of the column after close
    if len(columns) > vol:
        vals = [parse_number(v) for v in columns[vol]]
        if all(st == OK and math.isfinite(x) and x >= 0 and x == int(x) for x, st in vals):
            mapping["volume"] = vol
            note += f"; column {vol + 1} = volume (whole numbers, never negative)"
        else:
            note += f"; column {vol + 1} is not used as volume (it has negative or fractional values) and is kept as is"
    if len(columns) > vol + 1:
        extra = f"column {vol + 2}" if len(columns) == vol + 2 else f"columns {vol + 2}-{len(columns)}"
        note += f"; {extra} kept unchanged, never used as volume"
    head = "column 1 = date, column 2 = time of day (every row)" if split_time else "column 1 = date"
    evidence.append(f"A-5 no header row; positional rule: {head}; {note}.")
    return mapping


# ---------------------------------------------------------------------------------------------------------------
# A-6: dates
# ---------------------------------------------------------------------------------------------------------------

@dataclass
class _Cand:
    cid: str
    spec: dict  # [datetime] table entries (without the time zones)
    label: str


def _candidates(values: list, time_values: list | None, kind: str) -> list[_Cand]:
    sample = [v for v in values if not _is_blank(v)]
    if not sample:
        return []
    out: list[_Cand] = []
    if time_values is not None:
        for d in ("iso",) + _DATE_FORMATS:
            for tf in _TIME_FORMATS:
                if d == "iso":
                    out.append(_Cand(f"iso+{tf}", {"kind": "iso", "time_format": tf}, f"ISO date and time {tf}"))
                else:
                    out.append(_Cand(f"{d}+{tf}", {"kind": "format", "format": d, "time_format": tf}, f"{d} and time {tf}"))
        if all(isinstance(v, (date, datetime)) for v in sample):
            for tf in _TIME_FORMATS:
                out.append(_Cand(f"native+{tf}", {"kind": "native", "precision": "date", "time_format": tf},
                                 f"spreadsheet date cells and time {tf}"))
        return out
    if all(isinstance(v, (date, datetime)) for v in sample):
        midnight = all(not isinstance(v, datetime) or (v.tzinfo is None and v.time() == time(0)) for v in sample)
        prec = "date" if midnight else "datetime"
        return [_Cand(f"native:{prec}", {"kind": "native", "precision": prec}, f"spreadsheet/Parquet {prec} values")]
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in sample) and kind in (XLSX, XLS) and \
            all(10000 < float(v) < 100000 for v in sample):
        out.append(_Cand("excel_serial", {"kind": "excel_serial"}, "Excel serial day numbers"))
    digits = {len(str(v).strip()) for v in sample} if all(re.fullmatch(r"\d+", str(v).strip()) for v in sample) else set()
    if digits == {10}:
        out.append(_Cand("unix_s", {"kind": "unix_s"}, "Unix time in seconds"))
    if digits == {13}:
        out.append(_Cand("unix_ms", {"kind": "unix_ms"}, "Unix time in milliseconds"))
    out.append(_Cand("iso", {"kind": "iso"}, "ISO 8601 (YYYY-MM-DD[THH:MM[:SS]][offset])"))
    for d in _DATE_FORMATS:
        for t in _TIME_SUFFIXES:
            out.append(_Cand(f"format:{d}{t}", {"kind": "format", "format": d + t}, f"{d}{t}"))
    return out


def _dt_spec(c: _Cand, zone: str) -> DatetimeSpec:
    s = c.spec
    fmt = s.get("format")
    pivot = TWO_DIGIT_YEAR_PIVOT if fmt and "%y" in fmt else None
    return DatetimeSpec(kind=s["kind"], format=fmt, two_digit_year_pivot=pivot, precision=s.get("precision"),
                        timezone=zone, exchange_timezone=zone, time_format=s.get("time_format"))


def _try(c: _Cand, values, time_values, settings, zone, limit=None):
    vals = values if limit is None else values[:limit]
    tvals = None if time_values is None else (time_values if limit is None else time_values[:limit])
    col = Collector()
    try:
        parsed = parse_times(vals, _dt_spec(c, zone), timeframe="1D", settings=settings, collector=col,
                             time_values=tvals)
    except IngestError:
        return None
    if col.count("datetime_parseable") and any(i.severity == "error" for i in col.issues if i.check == "datetime_parseable"):
        return None
    return parsed


def _keys(parsed) -> list:
    return [t for t in (parsed.ts_utc if parsed.is_instant else parsed.session_dates) if t is not None]


def _monotonic(keys: list) -> bool:
    return all(a <= b for a, b in zip(keys, keys[1:])) or all(a >= b for a, b in zip(keys, keys[1:]))


# ---------------------------------------------------------------------------------------------------------------
# A-9: timeframe
# ---------------------------------------------------------------------------------------------------------------

def _measured_step(parsed, zone_for_days: str) -> tuple[int, float] | None:
    """(minutes, share) when the data CLEARLY have one intraday bar interval: several bars on a trading date, enough
    same-day steps, and the most common step covers >= MIN_STEP_SHARE of them. Whether that interval is a supported
    timeframe is decided by the caller. None for date-only data, one bar per date, or irregular steps."""
    if not parsed.is_instant:
        return None
    z = ZoneInfo(zone_for_days)
    ts = sorted(t for t in parsed.ts_utc if t is not None)
    per_day = Counter(t.astimezone(z).date() for t in ts)
    if not per_day or max(per_day.values()) <= 1:
        return None
    steps = [int(round((b - a).total_seconds() / 60)) for a, b in zip(ts, ts[1:])
             if a.astimezone(z).date() == b.astimezone(z).date()]
    if len(steps) < MIN_BARS_FOR_TIMEFRAME - 1:
        return None
    step, n = Counter(steps).most_common(1)[0]
    share = n / len(steps)
    return (step, share) if share >= MIN_STEP_SHARE else None


def _infer_timeframe(parsed, zone_for_days: str) -> tuple[str | None, str]:
    if parsed.is_instant:
        z = ZoneInfo(zone_for_days)
        ts = sorted(t for t in parsed.ts_utc if t is not None)
        per_day = Counter(t.astimezone(z).date() for t in ts)
        if per_day and max(per_day.values()) > 1:
            steps = [int(round((b - a).total_seconds() / 60)) for a, b in zip(ts, ts[1:])
                     if a.astimezone(z).date() == b.astimezone(z).date()]
            if len(steps) < MIN_BARS_FOR_TIMEFRAME - 1:
                return None, "too few bars within a day to measure the bar interval"
            step, n = Counter(steps).most_common(1)[0]
            share = n / len(steps)
            if step in INTRADAY_STEPS and share >= MIN_STEP_SHARE:
                return INTRADAY_STEPS[step], f"{share:.0%} of steps within a day are {step} minute(s)"
            return None, f"the most common step within a day is {step} minute(s) ({share:.0%} of steps), which is not a supported bar size"
        days = sorted(per_day)
        basis = "one bar per trading date"
    else:
        days = sorted({d for d in parsed.session_dates if d is not None})
        basis = "date-only values"
    if len(days) < MIN_BARS_FOR_TIMEFRAME:
        return None, f"only {len(days)} distinct date(s), too few to measure the bar interval"
    gap = median((b - a).days for a, b in zip(days, days[1:]))
    if 1 <= gap <= 4:
        return "1D", f"{basis}, typical gap {gap:g} day(s)"
    if 5 <= gap <= 9:
        return "1W", f"{basis}, typical gap {gap:g} days"
    if 27 <= gap <= 33:
        return "1M", f"{basis}, typical gap {gap:g} days"
    return None, f"{basis}, typical gap {gap:g} days, which is not a supported bar size"


def timeframe_from_name(stem: str) -> str | None:
    found = list(_NAME_TF.finditer(stem))
    if not found:
        return None
    num, unit = int(found[-1].group(1)), found[-1].group(2)
    if unit in ("", "m", "min"):
        return INTRADAY_STEPS.get(num)
    if unit in ("h", "H"):
        return {1: "1h", 3: "3h", 4: "4h"}.get(num)
    if unit in ("d", "D") and num == 1:
        return "1D"
    if unit in ("w", "W") and num == 1:
        return "1W"
    if unit == "M" and num == 1:
        return "1M"
    return None


# ---------------------------------------------------------------------------------------------------------------
# A-8: identity
# ---------------------------------------------------------------------------------------------------------------

def identity_from_name(stem: str) -> tuple[str, str] | None:
    m = _NAME_ID.match(stem)
    if not m or m.group("exchange").upper() not in KNOWN_EXCHANGES:
        return None
    return m.group("exchange").upper(), m.group("symbol").upper()


def market_prefix_from_name(stem: str) -> tuple[str, str] | None:
    """('CRYPTO', 'RIVERUSD') for 'CRYPTO_RIVERUSD, 180'. The prefix names a market, not an exchange or venue."""
    m = _NAME_ID.match(stem)
    if not m or m.group("exchange").upper() not in MARKET_PREFIXES:
        return None
    return m.group("exchange").upper(), m.group("symbol").upper()


def _plain_symbol(stem: str) -> str | None:
    """The whole name as a symbol: 'ICICIBANK', '5PAISA_30min', 'VERANDA_1min', 'NIFTY, 1D'. Only when what follows
    the first word is nothing but a timeframe token, so 'CRYPTO_RIVERUSD, 180' or 'csv headers std' give no symbol."""
    parts = re.split(r"(?=[, _(])", stem, maxsplit=1)
    head, rest = parts[0], (parts[1] if len(parts) > 1 else "")
    if not head or not _PLAIN_SYMBOL.match(head) or head.isdigit():
        return None
    if rest and not re.fullmatch(r"(?:, ?|_| )\d{1,3}(?:min|[mhHdDwWM])?(?: ?\(\d+\))?", rest):
        return None
    return head.upper()


# ---------------------------------------------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------------------------------------------

def _valid_zone(name: str | None) -> bool:
    if not name:
        return False
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def interpret_file(path: str | Path, settings: Settings, *, market_timezone: str | None = None,
                   default_exchange: str | None = None, symbol_from_filename: bool = False,
                   answers: dict | None = None) -> Interpretation:
    """Work out how to read `path`. Returns READY with a generated profile, NEEDS_ANSWER with questions, or
    REJECTED with a reason. `answers` holds the user's earlier answers for this file (keys as Question.key, plus
    'exchange', 'symbol', 'timeframe', 'date_format', 'market_timezone')."""
    path = Path(path)
    answers = {k: v for k, v in (answers or {}).items() if v not in (None, "")}
    evidence: list[str] = []
    res = Interpretation(status=REJECTED, evidence=evidence)
    try:
        return _interpret(path, settings, market_timezone, default_exchange, symbol_from_filename, answers, res)
    except _Reject as exc:
        res.status, res.message = REJECTED, str(exc)
        return res


def _interpret(path, settings, market_tz, default_exchange, symbol_from_filename, answers, res):
    evidence = res.evidence
    detected = detect_format(path, max_size_bytes=settings.max_file_size_mb * 1024 * 1024)
    if not detected.supported:
        raise _Reject(detected.reason or "Unsupported file type.")
    kind = detected.kind
    evidence.append(f"A-1 format: {kind} (from the file's content).")
    delimiter = None
    try:
        if kind == TEXT:
            raw, delimiter = _read_text(path, evidence)
            names, columns, header = _split_header(raw)
        elif kind == PARQUET:
            t = read_source(path, kind, FileSpec(header=True))
            names, columns, header = list(t.names), t.columns, True
        else:
            t = read_source(path, kind, FileSpec(header=False))
            names, columns, header = _split_header(t)
            if len(columns) < MIN_COLUMNS:
                raise _Reject(f"The sheet has {len(columns)} column(s); at least {MIN_COLUMNS} are needed.")
    except IngestError as exc:
        raise _Reject(f"{exc.message} {exc.action or ''}".strip()) from None
    if not columns or not columns[0]:
        raise _Reject("The file has no data rows.")
    evidence.append(f"A-3 {'header row found' if header else 'no header row (first row is data)'}; "
                    f"{len(columns[0])} data row(s), {len(columns)} column(s).")
    mapping = _map_named(names, evidence) if header else _map_positional(columns, evidence)

    # ---- A-6 dates ----------------------------------------------------------------------------------------
    values = columns[mapping["date"]]
    tvalues = columns[mapping["time"]] if "time" in mapping else None
    zone = market_tz if _valid_zone(market_tz) else "UTC"
    cands = _candidates(values, tvalues, kind)
    fitting = [c for c in cands if _try(c, values, tvalues, settings, zone, limit=50) is not None]
    full = [(c, p) for c in fitting for p in [_try(c, values, tvalues, settings, zone)] if p is not None]
    if not full:
        sample = [str(v) for v in values[:3]]
        raise _Reject(f"The dates could not be read with any supported layout (first values: {sample}). Supported: "
                      "ISO (2026-02-25 or 2026-02-25T09:15:00+05:30), 25-02-26, 25/02/2026, 25-Feb-26, 20260225, "
                      "Unix seconds or milliseconds, and spreadsheet date cells.")
    chosen = None
    pool = full
    answered = answers.get("date_format")
    if answered:
        chosen = next(((c, p) for c, p in full if c.cid == answered), None)
        if chosen:
            evidence.append(f"A-6 date layout {chosen[0].label}: chosen by the user (recorded answer).")
    if chosen is None:
        ordered = [(c, p) for c, p in full if _monotonic(_keys(p))] if len(full) > 1 else full
        pool = ordered or full
        distinct = {tuple(_keys(p)) for _, p in pool}
        if len(pool) == 1 or len(distinct) == 1:
            chosen = pool[0]
            why = "the only supported layout that fits every value"
            if len(full) > 1 and len(pool) == 1:
                why = (f"{len(full)} layouts fit every value, and only this one puts the dates in file order")
            elif len(pool) > 1:
                why = f"{len(pool)} layouts fit and give identical dates"
            evidence.append(f"A-6 date layout {chosen[0].label}: {why}.")
        else:
            res.questions.append(Question(
                "date_format",
                "The dates can be read in more than one way (for example day-first or month-first), and the data "
                "do not show which is right. Which layout do the dates use?",
                tuple(c.cid for c, _ in pool)))
    cand, parsed = chosen if chosen else (None, None)
    if cand is not None and "%y" in (cand.spec.get("format") or ""):
        evidence.append("Two-digit years use Q-MAP's fixed rule: 00-68 = 2000-2068, 69-99 = 1969-1999.")
    # While the date layout is still a question, the remaining questions are worked out from the candidate
    # layouts too (when they all agree), so the user is asked everything at once.
    probes = [p for _, p in pool] if parsed is None else [parsed]

    # ---- A-7 time zone --------------------------------------------------------------------------------------
    tz = answers.get("market_timezone") or market_tz
    needs_zone = any(p.is_instant for p in probes)
    if needs_zone and not _valid_zone(tz):
        res.questions.append(Question(
            "market_timezone",
            "These are date-times. Which market time zone should be used to work out each bar's trading date (and "
            "for times written without an offset)? For Indian exchanges: Asia/Kolkata.", ("Asia/Kolkata",)))
    elif needs_zone:
        naive = any(p.provenance.get("timezone_applied") is not None for p in probes)
        evidence.append(f"A-7 market time zone {tz} ("
                        + ("given by the user" if answers.get("market_timezone") else "confirmed for this source")
                        + "); " + ("times without an offset are read in this zone." if naive
                                   else "the values carry their own offset or are Unix (UTC) times."))
        if tz != zone:  # re-parse with the real zone so trading dates are right for the timeframe check
            if parsed is not None:
                parsed = _try(cand, values, tvalues, settings, tz)
                probes = [parsed]
            else:
                probes = [p for p in (_try(c, values, tvalues, settings, tz) for c, _ in pool) if p is not None]

    # ---- A-9 timeframe ---------------------------------------------------------------------------------------
    stem = path.stem
    name_tf = timeframe_from_name(stem)
    timeframe = answers.get("timeframe")
    if timeframe and timeframe not in ALLOWED_TIMEFRAMES:
        timeframe = None
    inferred, why = None, ""
    day_zone = tz if _valid_zone(tz) else "UTC"
    if probes:
        results = {_infer_timeframe(p, day_zone) for p in probes}
        inferred, why = (next(iter(results)) if len({r[0] for r in results}) == 1
                         else (None, "the candidate date layouts give different bar intervals"))
    measured = {_measured_step(p, day_zone) for p in probes}
    measured = next(iter(measured)) if len(measured) == 1 else None
    if measured is not None and (timeframe or not inferred):
        step, share = measured
        fits = INTRADAY_STEPS.get(step)  # the timeframe whose bar interval IS the measured one, if Q-MAP has it
        if fits is None:
            # A clear interval with no matching timeframe: every possible answer would relabel the bars (e.g.
            # 180-minute bars registered as 4h), so there is no valid answer to ask for.
            raise _Reject(f"The bars are {step} minutes apart ({share:.0%} of steps within a day), and {step}-minute "
                          "bars are not a supported timeframe"
                          + (f"; your recorded answer ({timeframe}) would relabel them" if timeframe else "")
                          + ". Q-MAP does not relabel, resample or aggregate bars.")
        if timeframe and timeframe != fits:
            # The interval is MEASURED (same-day steps). A different answer would relabel the data, so the recorded
            # answer is not used and the question is asked again with the only consistent choice.
            res.questions.append(Question(
                "timeframe", f"Your recorded answer says {timeframe} bars, but the data are {fits} bars ({share:.0%} of "
                             f"steps within a day are {step} minutes). Q-MAP does not relabel bars. Choose {fits}, or "
                             "correct the file.", (fits,)))
            timeframe = None
    asked = any(q.key == "timeframe" for q in res.questions)
    if timeframe and not asked:
        evidence.append(f"A-9 timeframe {timeframe}: given by the user (recorded answer).")
    elif probes and not asked:
        if inferred and name_tf and name_tf != inferred:
            res.questions.append(Question(
                "timeframe", f"The data look like {inferred} bars ({why}), but the file name says {name_tf}. "
                             "Which is right?", (inferred, name_tf)))
        elif inferred:
            timeframe = inferred
            evidence.append(f"A-9 timeframe {inferred}: {why}" + (f"; the file name agrees ({name_tf})." if name_tf else "."))
        else:
            res.questions.append(Question("timeframe", f"The bar interval could not be worked out ({why}). "
                                                       "What is the timeframe?", ALLOWED_TIMEFRAMES))

    # ---- A-8 identity ----------------------------------------------------------------------------------------
    # Precedence (owner decision DQ-2, 02-Nov-26): explicit columns in the file > the user's recorded answer > the
    # file name pattern EXCHANGE_SYMBOL > the source's settings. A file name that CONTRADICTS a column is never used
    # silently: the file is rejected with the reason.
    overrides: dict = {}
    instrument: dict = {}
    name_id = identity_from_name(stem)
    prefix_id = None if name_id else market_prefix_from_name(stem)
    exch_ans, sym_ans = answers.get("exchange"), answers.get("symbol")
    col_values = {}
    for f in ("exchange", "symbol"):
        if f in mapping:
            norm = normalise_exchange if f == "exchange" else normalise_symbol
            col_values[f] = {norm(v) for v in columns[mapping[f]] if not _is_blank(v)}
    if name_id:
        for f, from_name in (("exchange", name_id[0]), ("symbol", name_id[1])):
            if f in col_values and from_name not in col_values[f]:
                found = ", ".join(sorted(col_values[f])[:5])
                raise _Reject(f"The file name says {f} {from_name}, but the file's {f} column says {found}. File "
                              "contents are never overridden by a file name; rename the file or correct the data.")
    # exchange
    if "exchange" in mapping:
        instrument.update(exchange_from="column", exchange_column=mapping["exchange"])
        evidence.append(f"A-8 exchange from the column {names[mapping['exchange']]!r}.")
    else:
        # a market prefix (CRYPTO_) says the folder's default exchange does not apply: the venue must be given
        exch = exch_ans or (name_id[0] if name_id else None) or (None if prefix_id else default_exchange)
        if prefix_id and not exch_ans and default_exchange:
            evidence.append(f"A-8 the file name starts with the market prefix {prefix_id[0]}_, which names no exchange "
                            f"or venue, so the folder's default exchange ({normalise_exchange(default_exchange)}) "
                            "is not applied.")
        if exch:
            instrument["exchange_from"] = "ingest"
            overrides["exchange"] = normalise_exchange(exch)
            evidence.append(f"A-8 exchange {overrides['exchange']}: " + (
                "given by the user." if exch_ans else "from the file name." if name_id
                else "the source's default exchange."))
    # symbol
    if "symbol" in mapping:
        instrument.update(symbol_from="column", symbol_column=mapping["symbol"])
        evidence.append(f"A-8 symbol from the column {names[mapping['symbol']]!r}"
                        + (" (the file name is consistent with it but is not used)." if name_id else "."))
    else:
        instrument["symbol_from"] = "ingest"
        sym = None
        if sym_ans:
            sym, why = sym_ans, "given by the user"
        elif name_id:
            sym, why = name_id[1], "from the file name pattern EXCHANGE_SYMBOL"
        elif prefix_id:
            sym, why = prefix_id[1], f"from the file name pattern {prefix_id[0]}_SYMBOL"
        elif symbol_from_filename and _plain_symbol(stem) and (overrides.get("exchange") or "exchange" in mapping):
            sym, why = _plain_symbol(stem), "the file name (enabled for this source)"
        if sym:
            overrides["symbol"] = normalise_symbol(sym)
            evidence.append(f"A-8 symbol {overrides['symbol']}: {why}.")
    need_exch = "exchange_from" not in instrument
    need_sym = instrument.get("symbol_from") == "ingest" and "symbol" not in overrides
    # A plain file name ("ICICIBANK.txt") is only a SUGGESTION unless the folder's option "symbol from the file name"
    # is on (decision D5-06): the Sources screen fills it in, and the user confirms it with Save answer.
    suggest = (_plain_symbol(stem),) if need_sym and _plain_symbol(stem) else ()
    hint = (f" The file name suggests {suggest[0]} (confirm it, or switch on 'symbol from the file name' for this "
            "folder)." if suggest else "")
    if need_exch and need_sym:
        res.questions.append(Question("identity", "Which instrument is this (exchange and symbol)? Q-MAP could not "
                                                  "read it from the file or its name." + hint, suggest))
    elif need_exch:
        res.questions.append(Question("exchange", (
            f"Which exchange or venue is {overrides.get('symbol', 'this')} traded on? The file does not say, and the "
            f"{prefix_id[0]}_ prefix in its name is a market, not a venue." if prefix_id
            else "Which exchange is this traded on? The file does not say.")))
    elif need_sym:
        res.questions.append(Question("identity", "Which symbol is this? Q-MAP could not read it from the file or "
                                                  "its name." + hint, suggest))

    # ---- structure signature (for reusing answers) ------------------------------------------------------------
    sig = {"rules": SIGNATURE_RULES, "format": kind, "delimiter": delimiter, "header": header,
           "names": [_norm(n) if n else None for n in names] if header else len(columns),
           "date_layouts": sorted(c.cid for c, _ in full)}
    res.signature = hashlib.sha256(json.dumps(sig, sort_keys=True).encode()).hexdigest()[:16]
    res.decisions = {"format": kind, "delimiter": delimiter, "header": header,
                     "mapping": {k: {"position": v, "name": names[v]} for k, v in mapping.items()},
                     "date_layout": cand.cid if cand else None, "timeframe": timeframe,
                     "market_timezone": tz if needs_zone else None, "identity": overrides or None}

    if res.questions:
        res.status = NEEDS_ANSWER
        res.message = " ".join(q.text for q in res.questions)
        return res

    # ---- generate the profile ---------------------------------------------------------------------------------
    overrides["timeframe"] = timeframe
    res.profile = _build_profile(kind, delimiter, header, mapping, cand, tz if needs_zone else None, instrument)
    res.overrides = overrides
    res.status = READY
    res.message = f"Read automatically as {res.profile.profile_id}."
    return res


def _toml(v) -> str:
    return json.dumps(v, ensure_ascii=False)  # a JSON string/number is valid TOML for these values


def _build_profile(kind, delimiter, header, mapping, cand: _Cand, zone, instrument: dict) -> SourceProfile:
    lines = ["[file]", f"expected_format = {_toml(kind)}", f"header = {'true' if header else 'false'}"]
    if delimiter is not None:
        lines.append(f"delimiter = {_toml(delimiter)}")
    lines += ["[instrument]", f"exchange_from = {_toml(instrument['exchange_from'])}",
              f"symbol_from = {_toml(instrument['symbol_from'])}", 'timeframe = "ingest"']
    for k in ("exchange_column", "symbol_column"):
        if k in instrument:
            lines.append(f"{k} = {{ position = {instrument[k]} }}")
    lines.append("[columns]")
    for k in ("date", "time", "open", "high", "low", "close"):
        if k in mapping:
            lines.append(f"{k} = {{ position = {mapping[k]} }}")
    s = cand.spec
    lines += ["[datetime]", f"kind = {_toml(s['kind'])}"]
    if s.get("format"):
        lines.append(f"format = {_toml(s['format'])}")
        if "%y" in s["format"]:
            lines.append(f"two_digit_year_pivot = {TWO_DIGIT_YEAR_PIVOT}")
    if s.get("precision"):
        lines.append(f"precision = {_toml(s['precision'])}")
    if s.get("time_format"):
        lines.append(f"time_format = {_toml(s['time_format'])}")
    if zone:
        lines += [f"timezone = {_toml(zone)}", f"exchange_timezone = {_toml(zone)}"]
    lines.append("[volume]")
    if "volume" in mapping:
        lines += ['rule = "use_column"', f"column = {{ position = {mapping['volume']} }}"]
    else:
        lines.append('rule = "none"')
    lines.append('requirement_set = "price_only"')
    body = "\n".join(lines) + "\n"
    digest = hashlib.sha256(f"auto-rules-{PROFILE_RULES_SEED}\n{body}".encode("utf-8")).hexdigest()[:12]
    pid = f"auto_{digest}"
    head = (f'profile_id = "{pid}"\nprofile_version = 1\nstatus = "auto"\n'
            f'display_name = "Automatic interpretation {pid}"\n'
            f'source_label = "Automatic interpretation (rules v{PROFILE_RULES_SEED})"\n'
            f'description = "Generated by Q-MAP automatic interpretation rules A-1 to A-9, version {PROFILE_RULES_SEED}. '
            'Exchange, symbol and timeframe are supplied with each file (from its content, its name, the source '
            'settings or the user\'s recorded answer)."\n')
    return parse_profile(head + body)
