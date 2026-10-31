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
from qmap.data_engine.process import process_table
from qmap.data_engine.profiles import (SourceProfile, check_profile_against_settings, load_profile,
                                       parse_profile)
from qmap.data_engine.readers import read_source
from qmap.data_engine.results import ERROR, CheckResult
from qmap.storage.db import open_database

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
    where: str  # "example" | "mine" | "file"
    profile: SourceProfile | None
    problem: str | None

    @property
    def label(self) -> str:
        if self.profile is None:
            return f"{self.path.stem}  [{self.where}]  (has a problem)"
        p = self.profile
        return f"{p.profile_id}  v{p.profile_version}  [{self.where}]  {p.source_label}"


def list_profiles(settings: Settings) -> list[ProfileInfo]:
    found: list[ProfileInfo] = []
    for i, folder in enumerate(settings.profile_dirs):
        if not Path(folder).is_dir():
            continue
        for path in sorted(Path(folder).glob("*.toml")):
            where = "example" if i == 0 else "mine"
            try:
                profile = load_profile(path)
                check_profile_against_settings(profile, settings)
                found.append(ProfileInfo(path, where, profile, None))
            except (ProfileError, QmapError) as exc:
                found.append(ProfileInfo(path, where, None, plain(exc)))
    return found


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


def describe_profile(profile: SourceProfile) -> list[tuple[str, str]]:
    f, d, v, ins = profile.file, profile.datetime, profile.volume, profile.instrument
    where = {"fixed": "fixed in the profile", "column": "read from a column in the file",
             "filename_pattern": "read from the file name", "ingest": "you type it below"}
    rows = [
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
    needs, out = profile_needs(profile), []
    if needs.exchange and not exchange.strip():
        out.append("Type the exchange (for example NSE). This profile cannot read it from the file.")
    if needs.symbol and not symbol.strip():
        out.append("Type the symbol (for example NIFTY). This profile cannot read it from the file.")
    if needs.timeframe and not timeframe.strip():
        out.append("Choose the timeframe (for example 1D or 5m). Q-MAP never guesses it.")
    return out


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


def copy_example_as(example: Path, new_id: str, directory: str | Path) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", new_id or ""):
        raise GuiError("A profile name may only use letters, digits, '_', '.' and '-' (no spaces).")
    text = Path(example).read_text(encoding="utf-8")
    text, n = re.subn(r'(?m)^profile_id\s*=\s*"[^"]*"', f'profile_id      = "{new_id}"', text, count=1)
    text = re.sub(r'(?m)^profile_version\s*=\s*\d+', "profile_version = 1", text, count=1)
    if n != 1:
        raise GuiError("That example does not look like a profile (no profile_id line).")
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
def open_in_file_manager(path: str | Path) -> tuple[bool, str]:
    p = Path(path)
    if not p.exists():
        return False, f"{p} does not exist."
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except OSError as exc:
        return False, f"Could not open {p}: {exc}"
    return True, "Opened."
