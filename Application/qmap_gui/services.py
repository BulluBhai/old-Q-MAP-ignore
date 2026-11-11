"""GUI-facing services: a thin, tkinter-free adapter over the Foundation.

Everything the screens need (locations, profiles, preview, check, open-a-folder) goes through here, and
all processing is done by the Foundation (`qmap`). Nothing in this module re-implements validation,
parsing, storage or registry logic.
"""

from __future__ import annotations

import dataclasses
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from qmap.core.config import (Settings, load_settings, location_rule_violation, overlap_violation)
from qmap.core.errors import ConfigError, IngestError, ProfileError, QmapError
from qmap.data_engine.format_detect import detect_format
from qmap.data_engine.preview import preview_file
from qmap.data_engine.instruments import normalise_exchange, normalise_symbol
from qmap.data_engine.process import filename_identity_problem, process_table
from qmap.data_engine.profiles import (STATUS_LABELS, SourceProfile, check_profile_against_settings, load_profile,
                                       parse_profile)
from qmap.data_engine.readers import read_source
from qmap.data_engine.results import ERROR, CheckResult
from qmap.storage.db import open_database

from .common import open_in_file_manager  # noqa: F401 - part of this module's interface
from .messages import Finding, findings_from_checks


class GuiError(Exception):
    """A problem explained in plain English; safe to show to the user as is."""


def plain(exc: Exception) -> str:
    """Foundation errors carry a message and an action; show them without the technical code."""
    if isinstance(exc, QmapError):
        return f"{exc.message} {exc.action}".strip() if exc.action else exc.message
    return str(exc)


# ---------------------------------------------------------------------------------------------------
# Folders (Q-MAP_DATA and Q-MAP_OUTPUT)
# ---------------------------------------------------------------------------------------------------
@dataclass
class LocationStatus:
    ok: bool
    message: str
    can_create: bool = False


@dataclass
class LocationsState:
    data: LocationStatus
    output: LocationStatus
    overall_ok: bool
    summary: str


def _one(label: str, text: str, code_root: Path) -> LocationStatus:
    text = (text or "").strip()
    if not text:
        return LocationStatus(False, "Not chosen yet.")
    path = Path(text).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        return LocationStatus(False, f"That location cannot be used: {exc}")
    problem = location_rule_violation(label, path, code_root)
    if problem:
        return LocationStatus(False, f"{problem[0]} {problem[1]}")
    if not path.exists():
        return LocationStatus(False, "This folder does not exist yet. Press 'Create folder' to make it.", can_create=True)
    if not path.is_dir():
        return LocationStatus(False, "That is a file, not a folder.")
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".qmap_write_test_", delete=True):
            pass
    except OSError as exc:
        return LocationStatus(False, f"Q-MAP cannot write to this folder ({exc}). Choose another folder.")
    return LocationStatus(True, "OK")


def check_locations(data_root: str, output_root: str, code_root: str | Path) -> LocationsState:
    code = Path(code_root).resolve()
    d, o = _one("Q-MAP_DATA", data_root, code), _one("Q-MAP_OUTPUT", output_root, code)
    summary = "Both folders are ready."
    ok = d.ok and o.ok
    if ok:
        overlap = overlap_violation(Path(data_root).expanduser().resolve(), Path(output_root).expanduser().resolve())
        if overlap:
            ok = False
            o = LocationStatus(False, f"{overlap[0]} {overlap[1]}")
    if not ok:
        summary = "Choose a data folder and an output folder (two separate folders outside the Q-MAP code folder)."
    return LocationsState(d, o, ok, summary)


def create_folder(text: str, label: str, code_root: str | Path, other: str = "") -> Path:
    """Create a folder after the same separation checks the Foundation applies."""
    if not (text or "").strip():
        raise GuiError("Type or choose a folder first.")
    code = Path(code_root).resolve()
    path = Path(text).expanduser().resolve()
    problem = location_rule_violation(label, path, code)
    if problem:
        raise GuiError(f"{problem[0]} {problem[1]}")
    if (other or "").strip():
        overlap = overlap_violation(path, Path(other).expanduser().resolve())
        if overlap:
            raise GuiError(f"{overlap[0]} {overlap[1]}")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GuiError(f"The folder could not be created: {exc}") from exc
    return path


STANDARD_FOLDER_NAMES = ("Q-MAP_DATA", "Q-MAP_OUTPUT")


@dataclass
class StandardFolders:
    """The standard Q-MAP_DATA and Q-MAP_OUTPUT folders next to the program folder, and what preparing them did."""

    data: Path
    output: Path
    created: list[str] = field(default_factory=list)  # names of the folders made just now (they were missing)
    existing: list[str] = field(default_factory=list)  # names of the folders that were already there (used as is)
    problem: str = ""  # plain-English explanation when preparation cannot be completed

    @property
    def ok(self) -> bool:
        return not self.problem

    def describe(self) -> str:
        parts = []
        if self.created:
            parts.append("created " + " and ".join(self.created))
        if self.existing:
            parts.append("found " + " and ".join(self.existing) + " already there (used as they are; nothing in them "
                         "was changed)")
        return "; ".join(parts)


def standard_folders(parent: str | Path) -> tuple[Path, Path]:
    """Where the standard folders belong: side by side in the folder that holds the Q-MAP program folder."""
    base = Path(parent).expanduser().resolve()
    return base / STANDARD_FOLDER_NAMES[0], base / STANDARD_FOLDER_NAMES[1]


def prepare_standard_folders(parent: str | Path, code_root: str | Path) -> StandardFolders:
    """Prepare the two standard folders without changing any pre-existing folder or user data.

    If a later creation fails, only a newly created empty folder from this attempt may be rolled back.
    """
    data, output = standard_folders(parent)
    result = StandardFolders(data, output)
    code = Path(code_root).resolve()
    for label, path in zip(STANDARD_FOLDER_NAMES, (data, output)):
        problem = location_rule_violation(label, path, code)
        if problem:
            result.problem = f"{problem[0]} {problem[1]}"
            return result
        if path.exists() and not path.is_dir():
            result.problem = (f"{path} is a file, not a folder, so Q-MAP cannot use it as {label}. Nothing was "
                              "changed. Choose your folders with Browse... below.")
            return result
    created_identity = {}
    for label, path in zip(STANDARD_FOLDER_NAMES, (data, output)):
        if path.is_dir():
            result.existing.append(label)
            continue
        try:
            path.mkdir()  # the parent folder must exist already: the program folder is in it
        except OSError as exc:
            # Roll back only folders this call created, and only with rmdir(): it succeeds for an empty folder and
            # cannot remove user files. If anything has appeared inside, leave it in place and report the partial result.
            retained = []
            for created_label in reversed(result.created[:]):
                created_path = data if created_label == "Q-MAP_DATA" else output
                try:
                    stat = created_path.lstat()
                    if created_identity.get(created_label) != (stat.st_dev, stat.st_ino):
                        retained.append(created_label)
                        continue
                    created_path.rmdir()
                except OSError:
                    retained.append(created_label)
                else:
                    result.created.remove(created_label)
            if retained:
                result.problem = (f"Q-MAP could not create the folder {path} ({exc}). The newly created folder(s) "
                                  f"{', '.join(reversed(retained))} could not be safely removed and have been left "
                                  "in place. No pre-existing folders or data were touched. You can choose or create "
                                  "your folders with Browse... or Create folder below.")
            else:
                result.problem = (f"Q-MAP could not create the folder {path} ({exc}). Newly created empty folder(s) "
                                  "were safely removed. No pre-existing folders or data were touched. You can choose "
                                  "or create your folders with Browse... or Create folder below.")
            return result
        result.created.append(label)
        try:
            stat = path.lstat()
            created_identity[label] = (stat.st_dev, stat.st_ino)
        except OSError:
            # Without a reliable identity, do not risk removing this path during rollback.
            created_identity[label] = None
    return result


def build_core_settings(data_root: str, output_root: str, code_root: str | Path,
                        user_profiles_dir: str | Path | None = None) -> Settings:
    """The Foundation's own Settings, built with the Foundation's own safeguards."""
    try:
        settings = load_settings(None, env={"QMAP_DATA_ROOT": str(data_root), "QMAP_OUTPUT_ROOT": str(output_root)},
                                 code_root=code_root)
    except ConfigError as exc:
        raise GuiError(plain(exc)) from exc
    if user_profiles_dir:
        mine = Path(user_profiles_dir)
        settings = dataclasses.replace(settings, profile_dirs=tuple(settings.profile_dirs) + (mine,))
    return settings


# ---------------------------------------------------------------------------------------------------
# Source profiles
# ---------------------------------------------------------------------------------------------------
@dataclass
class ProfileInfo:
    path: Path
    where: str  # "example" = shipped with Q-MAP (read-only library) | "mine" | "file"
    profile: SourceProfile | None
    problem: str | None

    @property
    def status_label(self) -> str:
        if self.profile is None:
            return "has a problem"
        if self.where == "example":
            return STATUS_LABELS.get(self.profile.status, self.profile.status)
        return "My profile" if self.where == "mine" else "Profile file"

    @property
    def label(self) -> str:
        """Drop-down text: the clear display name first, then what kind of profile it is, then its ID."""
        if self.profile is None:
            return f"{self.path.stem}  [has a problem]"
        p = self.profile
        return f"{p.title}   [{self.status_label}]   ({p.profile_id} v{p.profile_version})"


_STATUS_ORDER = {"standard": 0, "example": 1, "template": 2, "legacy": 3, "custom": 4}


def list_profiles(settings: Settings) -> list[ProfileInfo]:
    """Q-MAP's own library (Standard, then Examples, then Templates), then your own profiles."""
    found: list[ProfileInfo] = []
    for i, folder in enumerate(settings.profile_dirs):
        if not Path(folder).is_dir():
            continue
        group: list[ProfileInfo] = []
        for path in sorted(Path(folder).glob("*.toml")):
            where = "example" if i == 0 else "mine"
            try:
                profile = load_profile(path)
                check_profile_against_settings(profile, settings)
                group.append(ProfileInfo(path, where, profile, None))
            except (ProfileError, QmapError) as exc:
                group.append(ProfileInfo(path, where, None, plain(exc)))
        if i == 0:
            group.sort(key=lambda info: (_STATUS_ORDER.get(info.profile.status, 9) if info.profile else 9, info.path.name))
        found += group
    return found


def library_and_legacy_ids(settings: Settings) -> set[str]:
    """Names reserved by Q-MAP's own library: current profile IDs and their earlier (legacy) names."""
    ids: set[str] = set()
    for info in list_profiles(settings):
        if info.where == "example" and info.profile:
            ids.add(info.profile.profile_id)
            ids.update(info.profile.legacy_ids)
    return ids


def load_profile_file(path: str | Path, settings: Settings) -> ProfileInfo:
    path = Path(path)
    try:
        profile = load_profile(path)
        check_profile_against_settings(profile, settings)
        return ProfileInfo(path, "file", profile, None)
    except QmapError as exc:
        return ProfileInfo(path, "file", None, plain(exc))


@dataclass
class ProfileNeeds:
    exchange: bool
    symbol: bool
    timeframe: bool


def profile_needs(profile: SourceProfile) -> ProfileNeeds:
    ins = profile.instrument
    return ProfileNeeds(ins.exchange_from == "ingest", ins.symbol_from == "ingest", ins.timeframe == "ingest")


STATUS_MEANING = {"standard": "Standard - recommended for routine use",
                  "example": "Example - for learning and testing, not for routine use",
                  "template": "Template - copy it and adapt it before use",
                  "legacy": "Legacy - kept for compatibility only",
                  "custom": "Your own profile"}


def describe_profile(profile: SourceProfile) -> list[tuple[str, str]]:
    f, d, v, ins = profile.file, profile.datetime, profile.volume, profile.instrument
    where = {"fixed": "fixed in the profile", "column": "read from a column in the file",
             "filename_pattern": "read from the file name", "ingest": "you type it below"}
    rows = [("Kind of profile", STATUS_MEANING.get(profile.status, profile.status)),
            ("Profile ID", f"{profile.profile_id} (version {profile.profile_version})")]
    if profile.legacy_ids:
        rows.append(("Earlier names (still recognised)", ", ".join(profile.legacy_ids)))
    rows += [
        ("File type", {"delimited_text": "CSV / text", "xlsx": "Excel (.xlsx)", "xls": "Excel (.xls)",
                       "parquet": "Parquet", None: "any supported type"}[f.expected_format]),
        ("First row is a header", "Yes" if f.header else "No (columns are taken by position)"),
    ]
    rule = {"iso": "ISO dates/times (e.g. 2026-01-05 or 2026-01-05T09:15:00+05:30)", "format": f"text matching {d.format}",
            "unix_s": "Unix timestamps in SECONDS", "unix_ms": "Unix timestamps in MILLISECONDS",
            "excel_serial": "Excel serial date numbers", "native": "real dates already stored in the file"}[d.kind]
    rows.append(("Date / time", rule))
    if d.timezone:
        rows.append(("Time zone of the times", d.timezone))
    if d.exchange_timezone:
        rows.append(("Exchange time zone (trading date)", d.exchange_timezone))
    if d.two_digit_year_pivot is not None:
        rows.append(("Two-digit years", f"{d.two_digit_year_pivot}-99 mean 19xx, 00-{d.two_digit_year_pivot - 1:02d} mean 20xx"))
    rows.append(("Timeframe", ins.timeframe if ins.timeframe not in ("ingest", "filename_pattern")
                 else ("you type it below" if ins.timeframe == "ingest" else "read from the file name")))
    rows.append(("Exchange", where[ins.exchange_from] + (f": {ins.exchange}" if ins.exchange_from == "fixed" else "")))
    rows.append(("Symbol", where[ins.symbol_from] + (f": {ins.symbol}" if ins.symbol_from == "fixed" else "")))
    vol = {"none": "The file has no volume (that is fine)", "use_column": f"Volume is the column {v.column.describe() if v.column else ''}",
           "sum_columns": "Volume is the sum of several columns (reason recorded in the profile)"}[v.rule]
    rows.append(("Volume", vol))
    if v.preserved_not_volume:
        rows.append(("Kept but not used as volume", ", ".join(c.describe() for c in v.preserved_not_volume)))
    rows.append(("Purpose", profile.requirement_set))
    rows.append(("Rows out of date order", "sorted and noted" if profile.on_unsorted == "sort_and_warn" else "rejected"))
    return rows


def request_problems(profile: SourceProfile, exchange: str, symbol: str, timeframe: str) -> list[str]:
    """What must still be fixed before checking or loading, in plain words. Uses the Foundation's own rules."""
    needs, out = profile_needs(profile), []
    if needs.exchange and not exchange.strip():
        out.append("Type the exchange (for example NSE). This profile cannot read it from the file.")
    if needs.symbol and not symbol.strip():
        out.append("Type the symbol (for example NIFTY). This profile cannot read it from the file.")
    if needs.timeframe and not timeframe.strip():
        out.append("Choose the timeframe (for example 1D or 5m). Q-MAP never guesses it.")
    for wanted, typed, normalise in ((needs.exchange, exchange, normalise_exchange), (needs.symbol, symbol, normalise_symbol)):
        if wanted and typed.strip():
            try:
                normalise(typed)
            except IngestError as exc:
                out.append(plain(exc))
    return out


def file_name_notes(profile: SourceProfile, files) -> list[str]:
    """Advice, not a block: files whose NAME cannot give this profile its exchange/symbol/timeframe. Each such file
    would be rejected on its own when checked or loaded (unless its content was already loaded), so the other files
    in the list can still go ahead."""
    out = []
    for f in files:
        reason = filename_identity_problem(profile, Path(f).name)
        if reason:
            out.append(f"{reason} (In this window: 'Copy so it asks me for exchange and symbol...' makes such a profile.)")
    return out


def identity_note(profile: SourceProfile) -> str:
    """Where this profile takes the instrument and timeframe from, and so why the boxes are on or off."""
    ins = profile.instrument
    where = {"fixed": "fixed in the profile", "column": "read from a column of the file",
             "filename_pattern": f"read from the file name (pattern {ins.filename_pattern})", "ingest": "typed by you below"}
    parts = [f"Exchange: {where[ins.exchange_from]}" + (f" ({ins.exchange})" if ins.exchange_from == "fixed" else ""),
             f"Symbol: {where[ins.symbol_from]}" + (f" ({ins.symbol})" if ins.symbol_from == "fixed" else ""),
             "Timeframe: " + ("typed by you below" if ins.timeframe == "ingest" else
                              where["filename_pattern"] if ins.timeframe == "filename_pattern" else f"fixed in the profile ({ins.timeframe})")]
    note = "This profile: " + "; ".join(parts) + ". A box is switched off when the profile does not use what you type."
    if "filename_pattern" in (ins.exchange_from, ins.symbol_from):
        note += (" If your file names do not fit the pattern, rename the files, or use 'Copy so it asks me for exchange "
                 "and symbol...'.")
    return note


def reads_identity_from_filename(profile: SourceProfile) -> bool:
    return "filename_pattern" in (profile.instrument.exchange_from, profile.instrument.symbol_from)


def copy_profile_asking_for_identity(source: Path, new_id: str, directory: str | Path) -> Path:
    """A copy of a profile that reads exchange and symbol from the file name, changed so that you type them instead.
    Everything else is unchanged. The copy is a new profile (new name, version 1) in your own profiles folder; the
    original is never edited. Q-MAP still never guesses the instrument: you must type it for every load."""
    text = Path(source).read_text(encoding="utf-8")
    for key in ("exchange_from", "symbol_from"):
        text = re.sub(rf'(?m)^(\s*{key}\s*=\s*)"filename_pattern"', r'\1"ingest"', text, count=1)
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f".{new_id}.converting"
    try:
        tmp.write_text(text, encoding="utf-8")
        path = copy_example_as(tmp, new_id, folder)
    finally:
        tmp.unlink(missing_ok=True)
    converted = load_profile(path)
    if reads_identity_from_filename(converted):  # pragma: no cover - only for an unusual profile layout
        path.unlink()
        raise GuiError("This profile could not be converted automatically. Edit 'exchange_from' and 'symbol_from' "
                       "to \"ingest\" in a copy instead.")
    return path


def validate_profile_text(text: str, settings: Settings) -> tuple[SourceProfile | None, str]:
    """(profile, message). profile is None when the text is not a valid profile."""
    try:
        profile = parse_profile(text)
        check_profile_against_settings(profile, settings)
    except QmapError as exc:
        return None, plain(exc)
    return profile, "This profile is valid."


def profile_version_conflict(settings: Settings, profile: SourceProfile) -> str | None:
    """A message if this profile id+version was already used with different content."""
    if not settings.db_path.is_file():
        return None
    db = open_database(settings.db_path, migrate=False)
    try:
        row = db.one("SELECT content_sha256 FROM source_profiles WHERE profile_id = ? AND profile_version = ?",
                     (profile.profile_id, profile.profile_version))
    except Exception:
        return None
    finally:
        db.close()
    if row is not None and row["content_sha256"] != profile.content_sha256:
        return (f"Version {profile.profile_version} of '{profile.profile_id}' was already used with different "
                "settings. Increase profile_version before saving, so past results stay traceable.")
    return None


def save_user_profile(text: str, directory: str | Path) -> Path:
    profile = parse_profile(text)
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{profile.profile_id}.toml"
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".profile_", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, target)
    return target


def as_user_copy_text(text: str) -> str:
    """A library profile's text turned into YOUR copy: status "custom" (never labelled Standard or Example), no claim
    to the library's earlier names, display name marked as a copy. The reading rules are not touched."""
    text = re.sub(r'(?m)^status\s*=\s*"[^"]*"', 'status          = "custom"', text, count=1)
    text = re.sub(r'(?m)^legacy_ids\s*=.*\n', "", text, count=1)
    return re.sub(r'(?m)^display_name\s*=\s*"(?:Example - )?([^"]*)"',
                  lambda m: f'display_name    = "My copy: {m.group(1)}"', text, count=1)


def copy_example_as(example: Path, new_id: str, directory: str | Path) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", new_id or ""):
        raise GuiError("A profile name may only use letters, digits, '_', '.' and '-' (no spaces).")
    text = Path(example).read_text(encoding="utf-8")
    text, n = re.subn(r'(?m)^profile_id\s*=\s*"[^"]*"', f'profile_id      = "{new_id}"', text, count=1)
    text = re.sub(r'(?m)^profile_version\s*=\s*\d+', "profile_version = 1", text, count=1)
    if n != 1:
        raise GuiError("That example does not look like a profile (no profile_id line).")
    text = as_user_copy_text(text)
    target = Path(directory) / f"{new_id}.toml"
    if target.exists():
        raise GuiError(f"You already have a profile called '{new_id}'. Choose another name.")
    return save_user_profile(text, directory)


# ---------------------------------------------------------------------------------------------------
# Preview and check (no changes are made to Q-MAP_DATA)
# ---------------------------------------------------------------------------------------------------
@dataclass
class CheckReport:
    file: Path
    outcome: str  # would_be_accepted | would_be_rejected | unsupported | unreadable
    rows_read: int = 0
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]


def make_preview(path: str | Path, profile: SourceProfile | None, settings: Settings | None,
                 overrides: dict | None = None) -> str:
    ov = overrides or {}
    return preview_file(Path(path), profile, settings, exchange=ov.get("exchange") or None,
                        symbol=ov.get("symbol") or None, timeframe=ov.get("timeframe") or None)


def check_file(path: str | Path, profile: SourceProfile, settings: Settings, overrides: dict | None = None) -> CheckReport:
    """Validate one file with the Foundation's own reader and processing, without registering anything."""
    path, ov = Path(path), overrides or {}
    det = detect_format(path, max_size_bytes=settings.max_file_size_mb * 1024 * 1024)
    if not det.supported:
        return CheckReport(path, "unsupported", 0, findings_from_checks(
            [CheckResult("format_supported", ERROR, False, 0, det.reason)]))
    checks = [CheckResult("format_supported", ERROR, True, 0, "")]
    if not det.extension_matches:
        checks.append(CheckResult("extension_matches_content", "warning", False, 0,
                                  f"The ending {det.extension or '(none)'} does not match the contents ({det.kind})."))
    try:
        table = read_source(path, det.kind, profile.file)
    except IngestError as exc:
        checks.append(CheckResult(exc.check, ERROR, False, 0, plain(exc)))
        return CheckReport(path, "unreadable", 0, findings_from_checks(checks))
    res = process_table(table, profile, settings, filename=path.name,
                        overrides={"exchange": ov.get("exchange") or None, "symbol": ov.get("symbol") or None,
                                   "timeframe": ov.get("timeframe") or None})
    checks += res.checks
    outcome = "would_be_accepted" if res.accepted and not any(c.is_error for c in checks) else "would_be_rejected"
    return CheckReport(path, outcome, res.rows_read, findings_from_checks(checks))


# ---------------------------------------------------------------------------------------------------
# Opening folders and reports
# ---------------------------------------------------------------------------------------------------
# open_in_file_manager lives in .common (shared with the Analytical Workbench); imported above.
