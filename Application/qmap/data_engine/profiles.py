"""Source profiles: explicit, versioned descriptions of one source layout.

One generic ingestion engine is driven by these small TOML files, so supporting a new
provider means adding a profile (and tests), not new code. A profile must state every
setting that could otherwise be guessed: header presence, date rule and unit, time zone,
volume mapping and timeframe.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ..core.config import Settings
from ..core.errors import IngestError, ProfileError
from ..storage.db import Database, utc_now_iso

ALLOWED_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h", "1D", "1W", "1M")
INTRADAY_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240}
DATETIME_KINDS = ("iso", "format", "unix_s", "unix_ms", "excel_serial", "native")
VOLUME_RULES = ("none", "use_column", "sum_columns")
FROM_KINDS = ("fixed", "column", "filename_pattern", "ingest")
EXPECTED_FORMATS = ("delimited_text", "xlsx", "xls", "parquet")
_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
# What a profile is for (docs/standards/Q-MAP_Naming_and_Reference_Conventions.md, section C). Descriptive only:
# the status never changes how a file is read. A profile without a status (e.g. your own) is "custom".
PROFILE_STATUSES = ("standard", "example", "template", "legacy", "custom")
STATUS_LABELS = {"standard": "Standard", "example": "Example", "template": "Template", "legacy": "Legacy",
                 "custom": "My profile"}
_TIME_DIRECTIVES = ("%H", "%I", "%M", "%S", "%f")


@dataclass(frozen=True)
class ColumnRef:
    name: str | None = None
    position: int | None = None
    aliases: tuple[str, ...] = ()

    def describe(self) -> str:
        return f"position {self.position}" if self.position is not None else f"'{self.name}'"


@dataclass(frozen=True)
class FileSpec:
    expected_format: str | None = None
    encoding: str = "utf-8"
    delimiter: str = ","
    quotechar: str = '"'
    header: bool = True
    skip_rows: int = 0
    sheet: str | int | None = None
    decimal: str = "."
    thousands: str = ""


@dataclass(frozen=True)
class InstrumentSpec:
    exchange_from: str
    symbol_from: str
    exchange: str | None = None
    symbol: str | None = None
    exchange_column: ColumnRef | None = None
    symbol_column: ColumnRef | None = None
    filename_pattern: str | None = None
    timeframe: str = "1D"  # a code, "ingest" or "filename_pattern"
    timeframe_map: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DatetimeSpec:
    kind: str
    format: str | None = None
    two_digit_year_pivot: int | None = None
    zero_pad_width: int | None = None
    precision: str | None = None  # "date" | "datetime" (kind = native)
    timezone: str | None = None  # for timestamps without an offset
    exchange_timezone: str | None = None  # to derive session_date from an instant
    time_format: str | None = None  # when date and time are in separate columns
    time_zero_pad_width: int | None = None


@dataclass(frozen=True)
class VolumeSpec:
    rule: str
    column: ColumnRef | None = None
    columns: tuple[ColumnRef, ...] = ()
    justification: str | None = None
    verify_identical: tuple[ColumnRef, ...] = ()
    preserved_not_volume: tuple[ColumnRef, ...] = ()


@dataclass(frozen=True)
class SourceProfile:
    profile_id: str
    profile_version: int
    source_label: str
    description: str
    file: FileSpec
    instrument: InstrumentSpec
    columns: dict
    datetime: DatetimeSpec
    volume: VolumeSpec
    requirement_set: str
    on_unsorted: str
    keep_unmapped: bool
    content_sha256: str
    content_text: str = field(repr=False, default="")
    path: str | None = None
    display_name: str = ""  # what people see; falls back to the description / source label
    status: str = "custom"
    legacy_ids: tuple[str, ...] = ()  # earlier profile_ids of this same layout (compatibility aliases)

    @property
    def title(self) -> str:
        return self.display_name or self.description or self.source_label or self.profile_id


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def _ref(value, where: str, allow_aliases: bool = False) -> ColumnRef:
    if isinstance(value, ColumnRef):
        return value
    if isinstance(value, bool):
        raise ProfileError(f"{where}: a column must be a name, a position or a table, got {value!r}.")
    if isinstance(value, int):
        if value < 0:
            raise ProfileError(f"{where}: column position must be 0 or more.")
        return ColumnRef(position=value)
    if isinstance(value, str):
        if not value.strip():
            raise ProfileError(f"{where}: column name is empty.")
        return ColumnRef(name=value.strip())
    if isinstance(value, dict):
        name, pos = value.get("name"), value.get("position")
        if (name is None) == (pos is None):
            raise ProfileError(f"{where}: give exactly one of 'name' or 'position'.")
        aliases = tuple(str(a).strip() for a in value.get("aliases", ())) if allow_aliases else ()
        if pos is not None:
            if isinstance(pos, bool) or not isinstance(pos, int) or pos < 0:
                raise ProfileError(f"{where}: position must be a whole number 0 or more.")
            return ColumnRef(position=pos)
        return ColumnRef(name=str(name).strip(), aliases=aliases)
    raise ProfileError(f"{where}: a column must be a name, a position or a table, got {value!r}.")


def _require(table: dict, key: str, where: str):
    if key not in table:
        raise ProfileError(f"{where}: required setting '{key}' is missing.",
                           action="Add it to the profile. Q-MAP never guesses this value.")
    return table[key]


def _check_zone(name: str | None, where: str) -> None:
    if name is None:
        return
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise ProfileError(f"{where}: '{name}' is not a known IANA time zone (for example 'Asia/Kolkata').") from exc


def parse_profile(text: str, path: str | None = None) -> SourceProfile:
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"Profile is not valid TOML: {exc}.") from exc
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

    profile_id = _require(raw, "profile_id", "profile")
    if not isinstance(profile_id, str) or not _ID.match(profile_id):
        raise ProfileError("profile_id may only contain letters, digits, '_', '.' and '-' (no '@' or '+').")
    version = _require(raw, "profile_version", "profile")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ProfileError("profile_version must be a whole number, 1 or more.")

    f = raw.get("file", {})
    header = _require(f, "header", "[file]")
    if not isinstance(header, bool):
        raise ProfileError("[file] header must be true or false.")
    expected = f.get("expected_format")
    if expected is not None and expected not in EXPECTED_FORMATS:
        raise ProfileError(f"[file] expected_format must be one of {EXPECTED_FORMATS}.")
    delimiter = str(f.get("delimiter", ","))
    if len(delimiter) != 1:
        raise ProfileError("[file] delimiter must be a single character (use \"\\t\" for tab).")
    decimal, thousands = str(f.get("decimal", ".")), str(f.get("thousands", ""))
    if decimal not in (".", ",") or thousands not in ("", ",", ".", " ", "_") or decimal == thousands:
        raise ProfileError("[file] decimal must be '.' or ',', and 'thousands' must differ from it.")
    sheet = f.get("sheet")
    file_spec = FileSpec(expected_format=expected, encoding=str(f.get("encoding", "utf-8")), delimiter=delimiter,
                         quotechar=str(f.get("quotechar", '"')), header=header, skip_rows=int(f.get("skip_rows", 0)),
                         sheet=sheet, decimal=decimal, thousands=thousands)

    # instrument ------------------------------------------------------------
    ins = raw.get("instrument", {})
    exch_from, sym_from = _require(ins, "exchange_from", "[instrument]"), _require(ins, "symbol_from", "[instrument]")
    for k, v in (("exchange_from", exch_from), ("symbol_from", sym_from)):
        if v not in FROM_KINDS:
            raise ProfileError(f"[instrument] {k} must be one of {FROM_KINDS}.")
    pattern = ins.get("filename_pattern")
    if pattern is not None:
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise ProfileError(f"[instrument] filename_pattern is not a valid regular expression: {exc}.") from exc
    else:
        compiled = None
    for kind, label, group in ((exch_from, "exchange", "exchange"), (sym_from, "symbol", "symbol")):
        if kind == "fixed" and not str(ins.get(label, "")).strip():
            raise ProfileError(f"[instrument] {label}_from = 'fixed' needs a '{label}' value.")
        if kind == "column" and f"{label}_column" not in ins:
            raise ProfileError(f"[instrument] {label}_from = 'column' needs '{label}_column'.")
        if kind == "filename_pattern":
            if compiled is None or group not in compiled.groupindex:
                raise ProfileError(f"[instrument] {label}_from = 'filename_pattern' needs a filename_pattern with a "
                                   f"named group (?P<{group}>...).")
    timeframe = str(_require(ins, "timeframe", "[instrument]"))
    tf_map = tuple(sorted((str(k), str(v)) for k, v in ins.get("timeframe_map", {}).items()))
    if timeframe == "filename_pattern":
        if compiled is None or "timeframe" not in compiled.groupindex:
            raise ProfileError("[instrument] timeframe = 'filename_pattern' needs a named group (?P<timeframe>...).")
    elif timeframe != "ingest" and timeframe not in ALLOWED_TIMEFRAMES:
        raise ProfileError(f"[instrument] timeframe must be one of {ALLOWED_TIMEFRAMES}, 'ingest' or 'filename_pattern'. "
                           "It is declared, never inferred.")
    for _, v in tf_map:
        if v not in ALLOWED_TIMEFRAMES:
            raise ProfileError(f"[instrument] timeframe_map value {v!r} is not one of {ALLOWED_TIMEFRAMES}.")
    instrument = InstrumentSpec(
        exchange_from=exch_from, symbol_from=sym_from, exchange=ins.get("exchange"), symbol=ins.get("symbol"),
        exchange_column=_ref(ins["exchange_column"], "[instrument] exchange_column") if "exchange_column" in ins else None,
        symbol_column=_ref(ins["symbol_column"], "[instrument] symbol_column") if "symbol_column" in ins else None,
        filename_pattern=pattern, timeframe=timeframe, timeframe_map=tf_map)

    # columns ---------------------------------------------------------------
    cols_raw = raw.get("columns", {})
    columns = {}
    for key in ("date", "open", "high", "low", "close"):
        columns[key] = _ref(_require(cols_raw, key, "[columns]"), f"[columns] {key}", allow_aliases=True)
    if "time" in cols_raw:
        columns["time"] = _ref(cols_raw["time"], "[columns] time", allow_aliases=True)
    unknown = set(cols_raw) - set(columns)
    if unknown:
        raise ProfileError(f"[columns] unknown canonical field(s): {sorted(unknown)}. "
                           "Volume is configured in [volume], not in [columns].")

    # datetime --------------------------------------------------------------
    dt = raw.get("datetime", {})
    kind = _require(dt, "kind", "[datetime]")
    if kind not in DATETIME_KINDS:
        raise ProfileError(f"[datetime] kind must be one of {DATETIME_KINDS}.")
    fmt = dt.get("format")
    pivot = dt.get("two_digit_year_pivot")
    time_format = dt.get("time_format")
    if kind == "format":
        if not fmt:
            raise ProfileError("[datetime] kind = 'format' needs a 'format' such as \"%d-%m-%y\".")
    elif fmt:
        raise ProfileError(f"[datetime] 'format' is only used with kind = 'format' (not '{kind}').")
    if (fmt and "%y" in fmt or time_format and "%y" in time_format) and pivot is None:
        raise ProfileError("[datetime] the format has a two-digit year (%y): set 'two_digit_year_pivot' "
                           "(e.g. 69 means 69-99 = 1969-1999 and 00-68 = 2000-2068). Q-MAP never guesses the century.")
    if pivot is not None and (isinstance(pivot, bool) or not isinstance(pivot, int) or not 0 <= pivot <= 99):
        raise ProfileError("[datetime] two_digit_year_pivot must be a whole number from 0 to 99.")
    precision = dt.get("precision")
    if kind == "native" and precision not in ("date", "datetime"):
        raise ProfileError("[datetime] kind = 'native' needs precision = \"date\" or \"datetime\".")
    if precision is not None and precision not in ("date", "datetime"):
        raise ProfileError("[datetime] precision must be \"date\" or \"datetime\".")
    if "time" in columns:
        if kind not in ("format", "iso", "native"):
            raise ProfileError("[datetime] a separate time column can only be combined with kind format, iso or native.")
        if not time_format:
            raise ProfileError("[datetime] a [columns] time column needs 'time_format' such as \"%H:%M:%S\".")
    elif time_format:
        raise ProfileError("[datetime] 'time_format' is set but there is no [columns] time column.")
    for k in ("timezone", "exchange_timezone"):
        _check_zone(dt.get(k), f"[datetime] {k}")
    datetime_spec = DatetimeSpec(kind=kind, format=fmt, two_digit_year_pivot=pivot,
                                 zero_pad_width=dt.get("zero_pad_width"), precision=precision,
                                 timezone=dt.get("timezone"), exchange_timezone=dt.get("exchange_timezone"),
                                 time_format=time_format, time_zero_pad_width=dt.get("time_zero_pad_width"))

    # volume ----------------------------------------------------------------
    vol = raw.get("volume", {})
    rule = _require(vol, "rule", "[volume]")
    if rule not in VOLUME_RULES:
        raise ProfileError(f"[volume] rule must be one of {VOLUME_RULES}.")
    column = _ref(vol["column"], "[volume] column", True) if "column" in vol else None
    cols = tuple(_ref(c, "[volume] columns", True) for c in vol.get("columns", ()))
    justification = vol.get("justification")
    if rule == "use_column" and column is None:
        raise ProfileError("[volume] rule = 'use_column' needs 'column'.")
    if rule == "sum_columns":
        if len(cols) < 2:
            raise ProfileError("[volume] rule = 'sum_columns' needs 'columns' with at least two columns.")
        if not justification or not str(justification).strip():
            raise ProfileError("[volume] rule = 'sum_columns' needs a written 'justification' (for example a statement "
                               "from the provider's documentation). Volume fields are never combined without a reason.")
    if rule != "use_column" and vol.get("verify_identical"):
        raise ProfileError("[volume] 'verify_identical' is only used with rule = 'use_column'.")
    volume = VolumeSpec(rule=rule, column=column, columns=cols, justification=justification,
                        verify_identical=tuple(_ref(c, "[volume] verify_identical", True) for c in vol.get("verify_identical", ())),
                        preserved_not_volume=tuple(_ref(c, "[volume] preserved_not_volume", True)
                                                   for c in vol.get("preserved_not_volume", ())))
    requirement_set = str(_require(vol, "requirement_set", "[volume]"))

    # descriptive metadata (never affects parsing) -----------------------------
    display_name = str(raw.get("display_name", "")).strip()
    status = str(raw.get("status", "custom")).strip()
    if status not in PROFILE_STATUSES:
        raise ProfileError(f"status must be one of {PROFILE_STATUSES}, got {status!r}.")
    legacy_raw = raw.get("legacy_ids", [])
    if not isinstance(legacy_raw, list) or not all(isinstance(x, str) and _ID.match(x) for x in legacy_raw):
        raise ProfileError("legacy_ids must be a list of earlier profile names (letters, digits, '_', '.', '-').")
    legacy_ids = tuple(legacy_raw)
    if profile_id in legacy_ids:
        raise ProfileError("legacy_ids must not contain the profile's own profile_id.")

    order = raw.get("order", {})
    on_unsorted = order.get("on_unsorted", "sort_and_warn")
    if on_unsorted not in ("sort_and_warn", "error"):
        raise ProfileError("[order] on_unsorted must be 'sort_and_warn' or 'error'.")

    return SourceProfile(
        display_name=display_name, status=status, legacy_ids=legacy_ids,
        profile_id=profile_id, profile_version=version, source_label=str(raw.get("source_label", profile_id)),
        description=str(raw.get("description", "")), file=file_spec, instrument=instrument, columns=columns,
        datetime=datetime_spec, volume=volume, requirement_set=requirement_set, on_unsorted=on_unsorted,
        keep_unmapped=bool(raw.get("keep_unmapped", True)), content_sha256=digest, content_text=text, path=path)


def load_profile(path: str | Path) -> SourceProfile:
    p = Path(path)
    if not p.is_file():
        raise ProfileError(f"Profile file not found: {p}.")
    return parse_profile(p.read_text(encoding="utf-8"), str(p))


def find_profile(settings: Settings, id_or_path: str) -> SourceProfile:
    """A profile by file path, by its name (profile_id = file name), or by an EARLIER name listed in a profile's
    legacy_ids (profiles renamed under the naming standard keep working when asked for by their old name)."""
    candidate = Path(id_or_path)
    if candidate.suffix == ".toml" and candidate.is_file():
        return load_profile(candidate)
    for folder in settings.profile_dirs:
        p = folder / f"{id_or_path}.toml"
        if p.is_file():
            return load_profile(p)
    renamed = resolve_legacy_id(settings, id_or_path)
    if renamed is not None:
        return renamed
    raise ProfileError(f"Profile '{id_or_path}' was not found.",
                       action="Check the name, or give the full path of a .toml profile.")


def resolve_legacy_id(settings: Settings, old_id: str) -> SourceProfile | None:
    """The current profile that lists `old_id` among its legacy_ids, or None. Unreadable files are skipped."""
    for folder in settings.profile_dirs:
        if not Path(folder).is_dir():
            continue
        for p in sorted(Path(folder).glob("*.toml")):
            try:
                prof = load_profile(p)
            except ProfileError:
                continue
            if old_id in prof.legacy_ids:
                return prof
    return None


def check_profile_against_settings(profile: SourceProfile, settings: Settings) -> None:
    if profile.requirement_set not in settings.requirement_sets:
        raise ProfileError(f"requirement_set '{profile.requirement_set}' is not defined "
                           f"(known: {sorted(settings.requirement_sets)}).",
                           action="Define it under [requirement_sets] in your configuration or fix the profile.")


def processing_version(profile: SourceProfile, cleaning_code_version: str) -> str:
    return f"{profile.profile_id}@{profile.profile_version}+{cleaning_code_version}"


def register_profile_snapshot(db: Database, profile: SourceProfile) -> None:
    """Store the exact profile text used. The same version must always have the same content."""
    with db.transaction() as conn:
        row = conn.execute("SELECT content_sha256 FROM source_profiles WHERE profile_id = ? AND profile_version = ?",
                           (profile.profile_id, profile.profile_version)).fetchone()
        if row is None:
            conn.execute("INSERT INTO source_profiles(profile_id, profile_version, content_sha256, content_text, "
                         "first_used_at) VALUES (?, ?, ?, ?, ?)",
                         (profile.profile_id, profile.profile_version, profile.content_sha256, profile.content_text,
                          utc_now_iso()))
        elif row["content_sha256"] != profile.content_sha256:
            raise IngestError(
                f"Profile '{profile.profile_id}' version {profile.profile_version} was already used with different "
                "content. A changed profile must have a new profile_version so past results stay traceable.",
                code="E_PROFILE_CHANGED", check="profile_version",
                action="Increase profile_version in the profile file.")
