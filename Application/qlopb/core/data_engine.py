"""
QLOPB data engine: loads a price file and turns it into ONE standard table.

Standard table
    index   : DatetimeIndex named "datetime", ascending, unique, timezone-naive
    columns : open, high, low, close, volume   (volume is NaN if the file has none)

Design rules (owner requirements)
  * Nothing is guessed silently. If the structure cannot be proven from the file
    itself, the loader stops with a plain-English message instead of guessing.
  * No default date filter is applied. Every row of the file is used.
  * Every rejected row is kept (with its reason) so nothing disappears quietly.
  * The original file is never modified (a SHA-256 fingerprint proves it).
  * Quality flags (outliers, weekend bars, low volume, gaps ...) are REPORTED,
    never auto-corrected.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from qlopb.config import settings as cfg
from qlopb.core.validation import ohlc_inconsistent_mask

STD_COLS = ("open", "high", "low", "close", "volume")


# ── Errors ────────────────────────────────────────────────────────────────
class DataLoadError(Exception):
    """The file cannot be used. The message says why in plain English."""


class ColumnMappingError(DataLoadError):
    """Columns could not be identified safely."""


class AmbiguousDateError(DataLoadError):
    """Dates could be read in more than one way (for example 03/04/2025)."""


# ── Options and result containers ─────────────────────────────────────────
@dataclass
class LoadOptions:
    delimiter: str | None = None          # None = detect
    has_header: bool | None = None        # None = detect
    column_map: dict | None = None        # {"datetime": "time", "close": "Last", ...}
    dayfirst: bool | None = None          # needed only for ambiguous dd/mm dates
    target_tz: str | None = None          # e.g. "Asia/Kolkata"; only for mixed offsets
    duplicate_policy: str = "first"       # first | last | error
    adjustment_status: str = "unknown"    # adjusted | unadjusted | unknown


@dataclass
class DataQualityReport:
    source_name: str = ""
    sha256: str = ""
    file_bytes: int = 0
    encoding: str = "utf-8"
    delimiter: str = ","
    header_detected: bool = True
    column_map: dict = field(default_factory=dict)       # standard -> source name
    unmapped_columns: list = field(default_factory=list)
    structure_notes: list = field(default_factory=list)
    rows_in_file: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    reject_counts: dict = field(default_factory=dict)
    out_of_order_rows: int = 0
    duplicates_found: int = 0
    timezone_note: str = ""
    first_ts: object = None
    last_ts: object = None
    inferred_frequency: str = ""
    bar_minutes: float = float("nan")
    volume_available: bool = False
    adjustment_status: str = "unknown"
    flags: dict = field(default_factory=dict)            # name -> {"count", "examples"}
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["first_ts"] = _fmt(self.first_ts)
        d["last_ts"] = _fmt(self.last_ts)
        return d

    def to_text(self) -> str:
        L = [f"Source file      : {self.source_name}",
             f"SHA-256          : {self.sha256}",
             f"Delimiter        : {'TAB' if self.delimiter == chr(9) else self.delimiter}   "
             f"Header row: {'yes' if self.header_detected else 'no'}   Encoding: {self.encoding}",
             "Columns used     : " + ", ".join(f"{k}<-{v}" for k, v in self.column_map.items())]
        if self.unmapped_columns:
            L.append("Columns ignored  : " + ", ".join(map(str, self.unmapped_columns)))
        for n in self.structure_notes:
            L.append("Structure        : " + n)
        L.append(f"Rows             : {self.rows_in_file} in file, {self.rows_accepted} accepted, "
                 f"{self.rows_rejected} rejected")
        for k, v in self.reject_counts.items():
            L.append(f"  rejected [{k}]: {v}")
        L.append(f"Period           : {_fmt(self.first_ts)} to {_fmt(self.last_ts)}   "
                 f"Frequency: {self.inferred_frequency}")
        if self.timezone_note:
            L.append("Timezone         : " + self.timezone_note)
        L.append(f"Volume           : {'available' if self.volume_available else 'NOT in file'}")
        L.append(f"Price adjustment : {self.adjustment_status}")
        if self.out_of_order_rows:
            L.append(f"Order            : {self.out_of_order_rows} rows were out of order and were sorted")
        for name, info in self.flags.items():
            if info["count"]:
                ex = ", ".join(info["examples"])
                L.append(f"Flag [{name}]: {info['count']}  e.g. {ex}")
        for w in self.warnings:
            L.append("WARNING          : " + w)
        return "\n".join(L)


@dataclass
class LoadResult:
    df: pd.DataFrame
    report: DataQualityReport
    rejected: pd.DataFrame


# ── Small helpers ─────────────────────────────────────────────────────────
def _fmt(ts) -> str:
    if ts is None or (not isinstance(ts, str) and pd.isna(ts)):
        return ""
    t = pd.Timestamp(ts)
    if t.hour == 0 and t.minute == 0 and t.second == 0:
        return t.strftime(cfg.DATE_FMT)
    return t.strftime(cfg.DATETIME_FMT)


def sha256_of_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _norm_name(name) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


# Aliases are compared after removing spaces/punctuation and lower-casing.
# "adjclose", "turnover" and "price" are deliberately NOT aliases because they
# could mean something different from the plain Close / Volume.
_ALIASES = {
    "datetime": {"time", "date", "datetime", "timestamp", "dt", "datetimestamp",
                 "tradedate", "tradingdate", "day"},
    "open": {"open", "o", "openprice"},
    "high": {"high", "h", "highprice"},
    "low": {"low", "l", "lowprice"},
    "close": {"close", "c", "closeprice", "closing"},
    "volume": {"volume", "vol", "v", "qty", "quantity", "shares"},
}


def _is_number(text) -> bool:
    try:
        float(str(text).strip().replace(",", ""))
        return True
    except ValueError:
        return False


def detect_delimiter(lines: list) -> str:
    sample = [ln for ln in lines if ln.strip()][:20]
    if not sample:
        raise DataLoadError("The file is empty.")
    good = []
    for d in (",", ";", "\t", "|"):
        counts = [ln.count(d) for ln in sample]
        if min(counts) >= 3 and len(set(counts)) == 1:
            good.append((counts[0], d))
    if not good:
        raise DataLoadError(
            "Could not work out the column separator (comma, semicolon, tab or |). "
            "Every line should have the same number of separators and at least 4 columns. "
            "Please choose the delimiter manually.")
    good.sort(reverse=True)
    if len(good) > 1 and good[0][0] == good[1][0]:
        raise DataLoadError(
            f"Both '{good[0][1]}' and '{good[1][1]}' look like separators. "
            "Please choose the delimiter manually.")
    return good[0][1]


# ── Timestamp parsing ─────────────────────────────────────────────────────
_OFFSET_RE = re.compile(r"\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?\s*(Z|[+-]\d{2}:?\d{2})\s*$")
_OFFSET_TAIL = re.compile(r"(Z|[+-]\d{2}:?\d{2})\s*$")
_SLASH_DATE = re.compile(r"^\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})")


def parse_timestamps(values: pd.Series, options: LoadOptions) -> tuple:
    """Return (naive_timestamps, timezone_note). Unparseable values become NaT."""
    s = values.astype(str).str.strip()
    nonblank = s[s != ""]
    note = ""

    # 1) timezone offsets (only looked for when a time-of-day is present)
    has_offset = nonblank.map(lambda x: bool(_OFFSET_RE.search(x)))
    if has_offset.any():
        offsets = set()
        for x in nonblank[has_offset]:
            m = _OFFSET_TAIL.search(x)
            offsets.add(m.group(1))
        norm_offsets = {("+00:00" if o == "Z" else (o if ":" in o else o[:3] + ":" + o[3:]))
                        for o in offsets}
        if len(norm_offsets) > 1 and not options.target_tz:
            raise DataLoadError(
                "Timestamps carry different timezone offsets (" + ", ".join(sorted(norm_offsets))
                + "). Choose a target timezone, e.g. Asia/Kolkata.")
        if options.target_tz:
            utc = pd.to_datetime(s, utc=True, errors="coerce", format="ISO8601")
            naive = utc.dt.tz_convert(options.target_tz).dt.tz_localize(None)
            note = (f"Offsets found ({', '.join(sorted(norm_offsets))}); converted to "
                    f"{options.target_tz} and stored as plain local times.")
            return naive, note
        off = next(iter(norm_offsets))
        stripped = s.str.replace(_OFFSET_TAIL, "", regex=True).str.strip()
        naive = pd.to_datetime(stripped, errors="coerce", format="ISO8601")
        note = (f"Every timestamp carried the same offset {off}. The offset was removed and the "
                f"wall-clock times were kept unchanged (treated as exchange-local time).")
        return naive, note

    # 2) day/month/year style dates: refuse to guess when ambiguous
    m = nonblank.map(lambda x: _SLASH_DATE.match(x))
    if m.notna().all() and len(m) > 0:
        firsts = np.array([int(x.group(1)) for x in m])
        seconds = np.array([int(x.group(2)) for x in m])
        dayfirst = options.dayfirst
        if dayfirst is None:
            if (firsts > 12).any() and not (seconds > 12).any():
                dayfirst = True
            elif (seconds > 12).any() and not (firsts > 12).any():
                dayfirst = False
            elif (firsts > 12).any() and (seconds > 12).any():
                raise AmbiguousDateError("Dates mix day-first and month-first styles.")
            else:
                raise AmbiguousDateError(
                    "Dates like 03/04/2025 could be 3 April or 4 March - every value has both "
                    "numbers at 12 or below. Please state whether the day comes first.")
        naive = pd.to_datetime(s, errors="coerce", dayfirst=dayfirst, format="mixed")
        return naive, ("Dates read as day-first." if dayfirst else "Dates read as month-first.")

    # 3) ISO-style, then anything else pandas can read unambiguously
    naive = pd.to_datetime(s, errors="coerce", format="ISO8601")
    if naive.isna().sum() > (s == "").sum():
        alt = pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=False)
        naive = naive.where(naive.notna(), alt)
    return naive, note


# ── Reading the file into a raw text table ────────────────────────────────
def _read_text(path: Path) -> tuple:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc), ("utf-8" if enc == "utf-8-sig" else "latin-1 (fallback)")
        except UnicodeDecodeError:
            continue
    raise DataLoadError("Cannot decode the file as text.")


def _raw_table(path, options: LoadOptions, report: DataQualityReport) -> tuple:
    """Return (header_names or None, rows(list of lists), source_line_numbers)."""
    text, enc = _read_text(path)
    report.encoding = enc
    lines = text.splitlines()
    delim = options.delimiter or detect_delimiter(lines)
    report.delimiter = delim
    parsed = [(i + 1, r) for i, r in enumerate(csv.reader(io.StringIO(text), delimiter=delim))
              if any(c.strip() for c in r)]
    if not parsed:
        raise DataLoadError("The file is empty.")
    first = [c.strip() for c in parsed[0][1]]
    if options.has_header is None:
        # Headerless when the cells that should be prices are all numbers.
        has_header = not all(_is_number(c) for c in first[1:5])
    else:
        has_header = options.has_header
    report.header_detected = has_header
    if has_header:
        return first, parsed[1:], None
    return None, parsed, None


# ── Main entry point ──────────────────────────────────────────────────────
def load_file(path, options: LoadOptions | None = None) -> LoadResult:
    options = options or LoadOptions()
    path = Path(path)
    if not path.is_file():
        raise DataLoadError(f"File not found: {path}")
    if path.suffix.lower() in (".parquet", ".pq"):
        return _load_parquet(path, options)

    report = DataQualityReport(source_name=path.name, sha256=sha256_of_file(path),
                               file_bytes=path.stat().st_size,
                               adjustment_status=options.adjustment_status)
    header, rows, _ = _raw_table(path, options, report)
    ncols_expected = len(header) if header else max(len(r) for _, r in rows[:200])

    # ---- identify columns ------------------------------------------------
    if header:
        col_index = _map_header(header, options, report)
    else:
        col_index = _map_headerless(rows, ncols_expected, report)
        header = [f"column {i + 1}" for i in range(ncols_expected)]
    used = set(col_index.values())
    report.unmapped_columns = [header[i] for i in range(len(header)) if i not in used]
    report.column_map = {k: header[v] for k, v in col_index.items()}
    report.volume_available = "volume" in col_index

    # ---- build raw string table -----------------------------------------
    report.rows_in_file = len(rows)
    short = []
    data = {k: [] for k in col_index}
    line_nos, raw_text = [], []
    for line_no, r in rows:
        if len(r) != ncols_expected:      # too few OR too many values
            short.append((line_no, r))
            continue
        line_nos.append(line_no)
        raw_text.append(options.delimiter or report.delimiter)  # placeholder, replaced below
        raw_text[-1] = report.delimiter.join(r)
        for k, idx in col_index.items():
            data[k].append(r[idx].strip())
    tbl = pd.DataFrame(data)
    tbl["_line"] = line_nos
    tbl["_raw"] = raw_text

    # ---- parse values ---------------------------------------------------
    ts, tz_note = parse_timestamps(tbl["datetime"], options)
    report.timezone_note = tz_note
    thousands = report.delimiter != ","
    nums = {}
    for c in STD_COLS:
        if c in tbl.columns:
            col = tbl[c].astype(str)
            if thousands:
                col = col.str.replace(",", "", regex=False)
            nums[c] = pd.to_numeric(col.replace("", np.nan), errors="coerce")
        else:
            nums[c] = pd.Series(np.nan, index=tbl.index)
    std = pd.DataFrame({"datetime": ts, **nums})

    reasons = pd.Series("", index=std.index, dtype=object)

    def mark(mask, why):
        reasons[(mask) & (reasons == "")] = why

    mark(std["datetime"].isna(), "unparseable_date")
    price = std[["open", "high", "low", "close"]]
    mark(price.isna().any(axis=1), "missing_or_non_numeric_price")
    mark(np.isinf(price).any(axis=1), "infinite_price")
    mark((price <= 0).any(axis=1), "non_positive_price")
    bad_ohlc = pd.Series(ohlc_inconsistent_mask(std["open"], std["high"], std["low"], std["close"]),
                         index=std.index)
    ohlc_inconsistent_n = int((bad_ohlc & (reasons == "")).sum())
    mark(bad_ohlc, "ohlc_inconsistent")
    mark(std["volume"] < 0, "negative_volume")

    # file-level sanity checks BEFORE anything is dropped
    total = len(rows)
    if total < cfg.MIN_ROWS_REQUIRED:
        raise DataLoadError(f"Only {total} data rows found; at least {cfg.MIN_ROWS_REQUIRED} are needed.")
    if total and ohlc_inconsistent_n / total > cfg.MAX_OHLC_INCONSISTENT_FRACTION:
        raise ColumnMappingError(
            f"{ohlc_inconsistent_n} of {total} rows ({ohlc_inconsistent_n / total:.1%}) break the "
            "High/Low rule. The columns are probably mapped wrongly or the file is corrupt.")

    # duplicates among otherwise valid rows
    valid = reasons == ""
    dup_mask = std["datetime"].duplicated(keep=False) & valid
    n_dup_rows = int(std.loc[dup_mask, "datetime"].duplicated(keep="first").sum())
    report.duplicates_found = n_dup_rows
    if n_dup_rows and options.duplicate_policy == "error":
        raise DataLoadError(f"{n_dup_rows} duplicate timestamps found (duplicate policy = error).")
    keep = "last" if options.duplicate_policy == "last" else "first"
    dup_drop = std["datetime"].duplicated(keep=keep) & valid
    mark(dup_drop, "duplicate_timestamp")

    # build rejected table
    rej_idx = reasons != ""
    rejected = pd.DataFrame({
        "source_line": tbl.loc[rej_idx, "_line"].to_numpy(),
        "reason": reasons[rej_idx].to_numpy(),
        "raw_row": tbl.loc[rej_idx, "_raw"].to_numpy()})
    if short:
        extra = pd.DataFrame({"source_line": [s[0] for s in short],
                              "reason": "wrong_column_count",
                              "raw_row": [report.delimiter.join(s[1]) for s in short]})
        rejected = pd.concat([rejected, extra], ignore_index=True).sort_values("source_line")
    report.rows_rejected = len(rejected)
    report.reject_counts = rejected["reason"].value_counts().to_dict()
    if total and report.rows_rejected / total > cfg.MAX_REJECTED_FRACTION:
        raise DataLoadError(
            f"{report.rows_rejected} of {total} rows ({report.rows_rejected / total:.1%}) were "
            f"rejected ({report.reject_counts}). That is above the "
            f"{cfg.MAX_REJECTED_FRACTION:.0%} limit, so the file structure is probably misread.")

    good = std.loc[reasons == "", ["datetime", *STD_COLS]].copy()
    if len(good) < cfg.MIN_ROWS_REQUIRED:
        raise DataLoadError(f"Only {len(good)} usable rows remain; at least "
                            f"{cfg.MIN_ROWS_REQUIRED} are needed.")
    report.out_of_order_rows = int((good["datetime"].diff() < pd.Timedelta(0)).sum())
    good = good.sort_values("datetime", kind="stable").set_index("datetime")
    good.index.name = "datetime"
    report.rows_accepted = len(good)
    _describe_and_flag(good, report)
    return LoadResult(df=good, report=report, rejected=rejected.reset_index(drop=True))


def _map_header(header: list, options: LoadOptions, report: DataQualityReport) -> dict:
    index = {}
    if options.column_map:
        for std, src in options.column_map.items():
            if src not in header:
                raise ColumnMappingError(f"Mapped column '{src}' is not in the file. "
                                         f"Columns found: {', '.join(header)}")
            index[std] = header.index(src)
    else:
        for std, names in _ALIASES.items():
            hits = [i for i, h in enumerate(header) if _norm_name(h) in names]
            if len(hits) > 1:
                raise ColumnMappingError(
                    f"More than one column could be '{std}': "
                    + ", ".join(header[i] for i in hits) + ". Please choose one.")
            if hits:
                index[std] = hits[0]
    missing = [c for c in ("datetime", "open", "high", "low", "close") if c not in index]
    if missing:
        raise ColumnMappingError(f"Could not identify column(s): {', '.join(missing)}. "
                                 f"Columns found: {', '.join(header)}")
    if len(set(index.values())) != len(index):
        raise ColumnMappingError("The same file column was assigned to two different fields.")
    return index


def _map_headerless(rows: list, ncols: int, report: DataQualityReport) -> dict:
    """Headerless files: position is date, open, high, low, close[, volume].
    The order is VERIFIED from the numbers; if it cannot be proven we stop."""
    if ncols < 5:
        raise ColumnMappingError(
            f"The file has no header and only {ncols} columns; at least 5 are needed "
            "(date, open, high, low, close).")
    col_index = {"datetime": 0, "open": 1, "high": 2, "low": 3, "close": 4}
    if ncols >= 6:
        vol_ok = sum(_is_number(r[5]) for _, r in rows if len(r) > 5)
        if vol_ok >= 0.99 * len(rows):
            col_index["volume"] = 5
    o, h, l, c = [], [], [], []
    for _, r in rows:
        if len(r) < 5 or not all(_is_number(x) for x in r[1:5]):
            continue
        o.append(float(r[1].replace(",", "")))
        h.append(float(r[2].replace(",", "")))
        l.append(float(r[3].replace(",", "")))
        c.append(float(r[4].replace(",", "")))
    if len(o) < cfg.MIN_ROWS_REQUIRED:
        raise ColumnMappingError("Too few numeric rows to verify the column order.")
    ok = ~ohlc_inconsistent_mask(o, h, l, c)
    share = float(ok.mean())
    if share < cfg.POSITIONAL_OHLC_MIN_CONSISTENT:
        raise ColumnMappingError(
            f"The file has no header and the numbers do not fit the order "
            f"Open, High, Low, Close ({share:.1%} of rows fit; {cfg.POSITIONAL_OHLC_MIN_CONSISTENT:.0%} "
            "needed). Please give the column order explicitly.")
    report.structure_notes.append(
        f"No header row. Column order Date, Open, High, Low, Close"
        f"{', Volume' if 'volume' in col_index else ''} was assumed by position and CONFIRMED from "
        f"the data ({share:.1%} of rows satisfy High >= Open/Close >= Low).")
    return col_index


def _load_parquet(path: Path, options: LoadOptions) -> LoadResult:
    try:
        raw = pd.read_parquet(path)
    except ImportError as e:
        raise DataLoadError("Parquet needs the 'pyarrow' package (pip install pyarrow).") from e
    if isinstance(raw.index, pd.DatetimeIndex):
        raw = raw.reset_index()
    report = DataQualityReport(source_name=path.name, sha256=sha256_of_file(path),
                               file_bytes=path.stat().st_size, delimiter="(parquet)",
                               adjustment_status=options.adjustment_status)
    header = [str(c) for c in raw.columns]
    raw.columns = header
    index = _map_header(header, options, report)
    report.column_map = {k: header[v] for k, v in index.items()}
    report.unmapped_columns = [h for i, h in enumerate(header) if i not in index.values()]
    report.volume_available = "volume" in index
    std = pd.DataFrame({k: raw[header[v]] for k, v in index.items()})
    ts = pd.to_datetime(std["datetime"], errors="coerce")
    if getattr(ts.dt, "tz", None) is not None:
        report.timezone_note = f"Parquet timestamps had timezone {ts.dt.tz}; stored as local wall-clock."
        ts = ts.dt.tz_localize(None)
    std["datetime"] = ts
    for c in STD_COLS:
        std[c] = pd.to_numeric(std[c], errors="coerce") if c in std else np.nan
    reasons = pd.Series("", index=std.index, dtype=object)
    reasons[std["datetime"].isna()] = "unparseable_date"
    reasons[(reasons == "") & std[["open", "high", "low", "close"]].isna().any(axis=1)] = "missing_or_non_numeric_price"
    reasons[(reasons == "") & np.isinf(std[["open", "high", "low", "close"]]).any(axis=1)] = "infinite_price"
    reasons[(reasons == "") & (std[["open", "high", "low", "close"]] <= 0).any(axis=1)] = "non_positive_price"
    bad = pd.Series(ohlc_inconsistent_mask(std["open"], std["high"], std["low"], std["close"]), index=std.index)
    reasons[(reasons == "") & bad] = "ohlc_inconsistent"
    reasons[(reasons == "") & std["datetime"].duplicated(keep="first")] = "duplicate_timestamp"
    report.rows_in_file = len(std)
    rej = reasons != ""
    rejected = pd.DataFrame({"source_line": np.where(rej)[0] + 1, "reason": reasons[rej].to_numpy(),
                             "raw_row": ""})
    report.rows_rejected = len(rejected)
    report.reject_counts = rejected["reason"].value_counts().to_dict()
    if len(std) < cfg.MIN_ROWS_REQUIRED or report.rows_rejected / max(len(std), 1) > cfg.MAX_REJECTED_FRACTION:
        raise DataLoadError("Parquet file has too few usable rows or too many rejected rows.")
    good = std.loc[~rej, ["datetime", *STD_COLS]].sort_values("datetime").set_index("datetime")
    report.rows_accepted = len(good)
    _describe_and_flag(good, report)
    return LoadResult(df=good, report=report, rejected=rejected)


# ── Description and flags ─────────────────────────────────────────────────
def _examples(index_values) -> list:
    out = [_fmt(t) for t in list(index_values)[: cfg.MAX_EXAMPLES_IN_REPORT]]
    return out


def infer_frequency(index: pd.DatetimeIndex) -> tuple:
    """Return (label, bar_minutes) using the typical (median) gap between bars."""
    if len(index) < 3:
        return "unknown", float("nan")
    gaps = pd.Series(index[1:] - index[:-1]).dt.total_seconds() / 60.0
    typical = float(gaps[gaps > 0].median())
    if typical < 20 * 60:
        return f"intraday (~{typical:.0f} min bars)", typical
    if typical < 4 * 1440:
        return "daily", 1440.0
    if typical < 10 * 1440:
        return "weekly", 7 * 1440.0
    return "monthly or longer", typical


def _describe_and_flag(df: pd.DataFrame, report: DataQualityReport) -> None:
    report.first_ts, report.last_ts = df.index[0], df.index[-1]
    report.inferred_frequency, report.bar_minutes = infer_frequency(df.index)
    if df["volume"].notna().sum() == 0:
        report.volume_available = False
    flags = {}

    ret = df["close"].pct_change().abs() * 100
    big = ret[ret > cfg.OUTLIER_RETURN_PCT]
    flags["close-to-close move above %.0f%%" % cfg.OUTLIER_RETURN_PCT] = {
        "count": len(big), "examples": _examples(big.index)}

    if report.volume_available:
        low = df.index[(df["volume"] <= cfg.LOW_VOLUME_FLAG).to_numpy()]
        flags["volume at or below %d" % cfg.LOW_VOLUME_FLAG] = {"count": len(low), "examples": _examples(low)}

    wk = df.index[df.index.dayofweek >= 5]
    flags["bar on a Saturday/Sunday"] = {"count": len(wk), "examples": _examples(wk)}

    days = pd.Series(df.index.normalize().unique())
    gap = days.diff().dt.days
    gi = gap[gap > cfg.CALENDAR_GAP_DAYS].index
    flags["calendar gap over %d days" % cfg.CALENDAR_GAP_DAYS] = {
        "count": len(gi),
        "examples": [f"{_fmt(days[i - 1])}->{_fmt(days[i])}" for i in gi[: cfg.MAX_EXAMPLES_IN_REPORT]]}

    if report.bar_minutes < 20 * 60:
        per_day = pd.Series(1, index=df.index).groupby(df.index.normalize()).sum()
        mode = int(per_day.mode().iloc[0])
        short_days = per_day[per_day < mode]
        flags["intraday day with fewer bars than usual (%d)" % mode] = {
            "count": len(short_days), "examples": _examples(short_days.index)}
        if len(short_days):
            report.warnings.append(
                f"{len(short_days)} trading day(s) have fewer than the usual {mode} bars "
                "(partial first/last day, holidays or missing bars). Not corrected.")
    report.flags = flags
    if flags.get("bar on a Saturday/Sunday", {}).get("count"):
        report.warnings.append("Weekend-dated bars exist. They were kept; check the source.")
    if report.adjustment_status == "unknown":
        report.warnings.append("Whether prices are adjusted for splits/dividends is unknown. "
                               "Unadjusted splits would appear as artificial price jumps.")
    if not report.volume_available:
        report.warnings.append("No volume in the file. MA research does not use volume.")


def save_processed(result: LoadResult, out_dir, stamp: str) -> dict:
    """Write the standardised table and the rejected-rows table. Returns the paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    from qlopb.storage.file_provider import safe_name   # local import keeps layers simple
    stem = safe_name(Path(result.report.source_name).stem, 60)
    clean = out_dir / f"{stem}_clean_{stamp}.csv"
    df = result.df.copy()
    df.index = df.index.strftime("%Y-%m-%d %H:%M:%S")
    df.to_csv(clean)
    paths = {"clean": clean}
    if len(result.rejected):
        rej = out_dir / f"{stem}_rejected_rows_{stamp}.csv"
        result.rejected.to_csv(rej, index=False)
        paths["rejected"] = rej
    return paths
