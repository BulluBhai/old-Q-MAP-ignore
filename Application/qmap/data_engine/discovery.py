"""Folder sources and scanning (Blueprint v1.3 §8.5.2, §8.5.3, §8.5.6).

A folder source is a folder the user chose (anywhere, including a locally synchronised OneDrive or Google Drive
folder). A scan:

  1. lists the supported files inside the folder (sub-folders only if chosen; hidden files, Office lock files,
     links and Q-MAP's own data and output folders are never touched; exclusion patterns are respected). A folder
     that cannot be read makes the scan INCOMPLETE: it is reported, the scan is recorded as failed, and files last
     seen inside it are recorded as unreadable, never as missing;
  2. skips files whose contents have not changed since they were last handled (same SHA-256 checksum, computed on
     every scan, and the same interpretation inputs), so repeated scans are idempotent and a changed file is never
     missed, even when its size and modification time are unchanged;
  3. interprets new and changed files automatically (auto_interpret), and either loads them through the normal
     ingestion pipeline, or records a QUESTION for the user, or records why the file was rejected;
  4. compares each newly registered dataset with existing datasets of the same instrument and timeframe and reports
     overlaps and conflicts (overlap.py; nothing is merged or overwritten);
  5. records every file it saw, and what happened, in source_file_observations (append-only), and writes a CSV
     report into the scan's run folder.

Source files are only ever read. Nothing in a source folder is created, changed, moved or deleted.
"""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import os
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..core.config import Settings
from ..core.errors import QmapError
from ..core.runs import Run
from ..storage.db import Database, utc_now_iso
from ..storage.files import sha256_file
from . import auto_interpret as A
from .format_detect import EXTENSION_KIND
from .ingest import _date_limit_retry, ingest_file
from .instruments import normalise_exchange, normalise_symbol, record_display_name
from .profiles import MIXED, canonical_timeframe
from .instrument_names import ensure_registry_template, load_registry, registry_path
from .overlap import check_new_datasets, write_overlap_report

MODULE_CODE = "SCAN"
MODULE_NAME = "Folder scan (Database Manager)"
AREA = "Data_Management"
SUPPORTED_EXTENSIONS = tuple(sorted(EXTENSION_KIND))  # .csv .dat .parquet .pq .tsv .txt .xls .xlsx

# outcomes after which an unchanged file is not processed again (the same inputs would give the same result)
FINAL_OUTCOMES = ("imported", "reused", "needs_answer", "rejected", "blocked", "unsupported", "ignored")
OUTCOME_LABELS = {"imported": "Imported", "reused": "Already loaded", "needs_answer": "Needs your answer",
                  "rejected": "Rejected", "blocked": "Rejected earlier (unchanged)", "unsupported": "Not supported",
                  "ignored": "Ignored (not a data file type)", "failed": "Failed", "missing": "No longer in the folder"}


class SourceError(QmapError):
    pass


@dataclass
class FolderSource:
    source_id: int
    location: str
    label: str
    include_subfolders: bool
    exclude_patterns: tuple
    market_timezone: str | None
    default_exchange: str | None
    symbol_from_filename: bool
    status: str
    created_at: str

    def settings_snapshot(self) -> dict:
        return {"location": self.location, "include_subfolders": self.include_subfolders,
                "exclude_patterns": list(self.exclude_patterns), "market_timezone": self.market_timezone,
                "default_exchange": self.default_exchange, "symbol_from_filename": self.symbol_from_filename}


@dataclass
class FileState:
    """The current state of one file of a source = its latest observation."""
    relative_path: str
    outcome: str
    change: str
    action: str
    detail: str
    observed_at: str
    dataset_ids: list
    questions: list
    interpretation: dict
    scan_id: int

    @property
    def outcome_label(self) -> str:
        return OUTCOME_LABELS.get(self.outcome, self.outcome)


@dataclass
class ScanResult:
    scan_id: int
    run_id: str
    source_id: int
    counts: dict = field(default_factory=dict)
    files: list = field(default_factory=list)  # (relative_path, change, action, outcome, detail)
    excluded: int = 0
    report_path: Path | None = None
    overlaps: list = field(default_factory=list)  # OverlapFinding for every dataset registered by this scan
    overlap_report_path: Path | None = None
    identification_report_path: Path | None = None
    stopped: bool = False
    not_processed: list = field(default_factory=list)  # files not reached because the user stopped the scan
    registry_problems: list = field(default_factory=list)  # alias-registry problems (conflicting aliases ...)
    unreadable_folders: list = field(default_factory=list)  # (relative folder, reason): the scan is INCOMPLETE
    links_skipped: list = field(default_factory=list)  # relative paths of links and junctions, never followed
    # sub-folders of the selected folder left out because Include sub-folders is off (owner acceptance W08, 09-Nov-26):
    # counted so a scan that finds nothing can say why, never inspected
    subfolders_not_scanned: int = 0
    include_subfolders: bool = False

    @property
    def complete(self) -> bool:
        """False when a folder inside the scan could not be read (PR #9). A scan the user STOPPED is reported
        separately (`stopped`, PR #10)."""
        return not self.unreadable_folders

    def incomplete_text(self) -> str | None:
        if self.complete:
            return None
        shown = "; ".join(f"{'(the folder itself)' if d == '.' else d}: {why}" for d, why in self.unreadable_folders[:3])
        more = f" and {len(self.unreadable_folders) - 3} more" if len(self.unreadable_folders) > 3 else ""
        return (f"{len(self.unreadable_folders)} folder(s) could not be read, so their files were not checked "
                f"({shown}{more}).")

    def summary(self) -> str:
        parts = [f"{n} {OUTCOME_LABELS.get(k, k).lower()}" for k, n in sorted(self.counts.items()) if n]
        if self.stopped:
            parts.append(f"STOPPED by you: {len(self.not_processed)} file(s) not processed")
        text = ", ".join(parts) or "no supported files found"
        if self.subfolders_not_scanned and not self.include_subfolders:
            text += (f" ({self.subfolders_not_scanned} sub-folder(s) not scanned: Include sub-folders is off for this "
                     "folder)")
        return text if self.complete else f"INCOMPLETE SCAN: {text}"


# ---------------------------------------------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------------------------------------------

def _row_to_source(r) -> FolderSource:
    return FolderSource(r["source_id"], r["location"], r["label"], bool(r["include_subfolders"]),
                        tuple(json.loads(r["exclude_patterns_json"] or "[]")), r["market_timezone"],
                        r["default_exchange"], bool(r["symbol_from_filename"]), r["status"], r["created_at"])


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _check_settings(market_timezone, default_exchange, exclude_patterns) -> tuple:
    tz = (market_timezone or "").strip() or None
    if tz:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise SourceError(f"'{tz}' is not a known time zone.", action="Use a name such as Asia/Kolkata.") from None
    exch = normalise_exchange(default_exchange) if default_exchange and str(default_exchange).strip() else None
    pats = tuple(p.strip() for p in (exclude_patterns or ()) if p and p.strip())
    return tz, exch, pats


def add_folder_source(settings: Settings, db: Database, location: str | os.PathLike, *, label: str | None = None,
                      include_subfolders: bool = False, exclude_patterns=(), market_timezone: str | None = None,
                      default_exchange: str | None = None, symbol_from_filename: bool = True) -> FolderSource:
    folder = Path(location).expanduser()
    if not folder.is_dir():
        raise SourceError(f"The folder {folder} does not exist or is not a folder.")
    folder = folder.resolve()
    for root, what in ((settings.data_root, "Q-MAP data"), (settings.output_root, "Q-MAP output")):
        root = Path(root).resolve()
        if _is_inside(folder, root):
            raise SourceError(f"This folder is inside the {what} folder, which Q-MAP manages itself.",
                              action="Choose the folder where your source files are kept.")
    if _is_inside(folder, Path(settings.code_root).resolve()):
        raise SourceError("This folder is inside the Q-MAP application folder.",
                          action="Keep source files outside the application folder.")
    tz, exch, pats = _check_settings(market_timezone, default_exchange, exclude_patterns)
    # (DQ-8: file-name identification no longer needs a folder exchange; NSE is used when none is given)
    existing = db.one("SELECT * FROM data_sources WHERE location = ?", (str(folder),))
    if existing is not None and existing["status"] == "active":
        raise SourceError(f"This folder is already a source ('{existing['label']}').")
    now = utc_now_iso()
    with db.transaction() as conn:
        if existing is not None:  # re-adding a removed folder keeps its history
            conn.execute("UPDATE data_sources SET status = 'active', label = ?, include_subfolders = ?, "
                         "exclude_patterns_json = ?, market_timezone = ?, default_exchange = ?, symbol_from_filename = ?, "
                         "updated_at = ? WHERE source_id = ?",
                         (label or existing["label"], int(include_subfolders), json.dumps(list(pats)), tz, exch,
                          int(symbol_from_filename), now, existing["source_id"]))
            sid = existing["source_id"]
        else:
            sid = conn.execute(
                "INSERT INTO data_sources(kind, location, label, include_subfolders, exclude_patterns_json, "
                "market_timezone, default_exchange, symbol_from_filename, created_at, updated_at) "
                "VALUES ('folder', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(folder), (label or folder.name or str(folder)).strip(), int(include_subfolders),
                 json.dumps(list(pats)), tz, exch, int(symbol_from_filename), now, now)).lastrowid
    return get_source(db, sid)


def update_folder_source(db: Database, source_id: int, **changes) -> FolderSource:
    src = get_source(db, source_id)
    if src is None:
        raise SourceError(f"Source {source_id} does not exist.")
    merged = {"label": src.label, "include_subfolders": src.include_subfolders, "exclude_patterns": src.exclude_patterns,
              "market_timezone": src.market_timezone, "default_exchange": src.default_exchange,
              "symbol_from_filename": src.symbol_from_filename}
    unknown = set(changes) - set(merged)
    if unknown:
        raise ValueError(f"unknown source setting(s): {sorted(unknown)}")
    merged.update(changes)
    tz, exch, pats = _check_settings(merged["market_timezone"], merged["default_exchange"], merged["exclude_patterns"])
    with db.transaction() as conn:
        conn.execute("UPDATE data_sources SET label = ?, include_subfolders = ?, exclude_patterns_json = ?, "
                     "market_timezone = ?, default_exchange = ?, symbol_from_filename = ?, updated_at = ? "
                     "WHERE source_id = ?",
                     (str(merged["label"]).strip() or src.label, int(bool(merged["include_subfolders"])),
                      json.dumps(list(pats)), tz, exch, int(bool(merged["symbol_from_filename"])), utc_now_iso(),
                      source_id))
    return get_source(db, source_id)


def remove_folder_source(db: Database, source_id: int) -> None:
    """Stop scanning a folder. Its history, and every dataset loaded from it, stay exactly as they are."""
    with db.transaction() as conn:
        conn.execute("UPDATE data_sources SET status = 'removed', updated_at = ? WHERE source_id = ?",
                     (utc_now_iso(), source_id))


def get_source(db: Database, source_id: int) -> FolderSource | None:
    r = db.one("SELECT * FROM data_sources WHERE source_id = ?", (source_id,))
    return _row_to_source(r) if r else None


def list_sources(db: Database, *, include_removed: bool = False) -> list[FolderSource]:
    sql = "SELECT * FROM data_sources" + ("" if include_removed else " WHERE status = 'active'") + " ORDER BY label, source_id"
    return [_row_to_source(r) for r in db.query(sql)]


# ---------------------------------------------------------------------------------------------------------------
# file state and answers
# ---------------------------------------------------------------------------------------------------------------

def _latest_rows(db: Database, source_id: int) -> dict:
    rows = db.query(
        "SELECT o.* FROM source_file_observations o JOIN (SELECT relative_path, MAX(observation_id) AS m "
        "FROM source_file_observations WHERE source_id = ? GROUP BY relative_path) x "
        "ON o.observation_id = x.m ORDER BY o.relative_path", (source_id,))
    return {r["relative_path"]: r for r in rows}


def file_states(db: Database, source_id: int, *, include_missing: bool = True) -> list[FileState]:
    out = []
    for r in _latest_rows(db, source_id).values():
        if r["outcome"] == "missing" and not include_missing:
            continue
        out.append(FileState(r["relative_path"], r["outcome"], r["change"], r["action"], r["detail"] or "",
                             r["observed_at"], json.loads(r["dataset_ids_json"] or "[]"),
                             json.loads(r["questions_json"] or "[]"), json.loads(r["interpretation_json"] or "{}"),
                             r["scan_id"]))
    return out


def file_history(db: Database, source_id: int, relative_path: str) -> list:
    return db.query("SELECT * FROM source_file_observations WHERE source_id = ? AND relative_path = ? "
                    "ORDER BY observation_id", (source_id, relative_path))


def latest_answer(db: Database, source_id: int, relative_path: str):
    return db.one("SELECT * FROM source_answers WHERE source_id = ? AND relative_path = ? ORDER BY answer_id DESC "
                  "LIMIT 1", (source_id, relative_path))


ANSWER_KEYS = ("date_format", "market_timezone", "exchange", "symbol", "timeframe")


def record_answer(db: Database, source_id: int, relative_path: str, answers: dict) -> int:
    """Record the user's answers for one file. They apply to the next scan, and only while the file keeps the
    structure it had when the question was asked (the signature of its latest interpretation)."""
    state = next((s for s in file_states(db, source_id) if s.relative_path == relative_path), None)
    # DQ-8 (03-Nov-26): a correction can be recorded for any file Q-MAP has read (bulk corrections of imported files
    # included); it applies from the next scan, which registers the corrected data as a new dataset (nothing is
    # changed or deleted in place).
    if state is None or state.outcome in ("missing", "ignored", "unsupported"):
        raise SourceError("This file is not in the folder any more, or is not a data file.")
    clean = {k: str(v).strip() for k, v in answers.items() if k in ANSWER_KEYS and v is not None and str(v).strip()}
    unknown = set(answers) - set(ANSWER_KEYS)
    if unknown:
        raise ValueError(f"unknown answer key(s): {sorted(unknown)}")
    if not clean:
        raise SourceError("No answer was given.")
    if "market_timezone" in clean:
        _check_settings(clean["market_timezone"], None, ())
    try:  # the same rules the registry applies, so a bad value is refused now rather than at the next scan
        if "exchange" in clean:
            clean["exchange"] = normalise_exchange(clean["exchange"])
        if "symbol" in clean:
            clean["symbol"] = normalise_symbol(clean["symbol"])
    except QmapError as exc:
        raise SourceError(exc.message, action=exc.action) from None
    if "timeframe" in clean:
        canon = canonical_timeframe(clean["timeframe"])
        if canon is None or canon == MIXED:
            raise SourceError(f"Timeframe {clean['timeframe']!r} is not a timeframe (examples: 1m, 5m, 75m, 1h, 2h, "
                              "1D, 1W, 1M).")
        clean["timeframe"] = canon
    earlier = latest_answer(db, source_id, relative_path)
    sig = state.interpretation.get("signature", "")
    merged = dict(json.loads(earlier["answers_json"])) if earlier and earlier["structure_signature"] == sig else {}
    merged.update(clean)
    with db.transaction() as conn:
        return int(conn.execute("INSERT INTO source_answers(source_id, relative_path, structure_signature, answers_json, "
                                "answered_at) VALUES (?, ?, ?, ?, ?)",
                                (source_id, relative_path, sig, json.dumps(merged, sort_keys=True), utc_now_iso())).lastrowid)


# ---------------------------------------------------------------------------------------------------------------
# scanning
# ---------------------------------------------------------------------------------------------------------------

def _hidden(name: str) -> bool:
    return name.startswith(".") or name.startswith("~$") or name.lower() in ("thumbs.db", "desktop.ini")


LINK, UNREADABLE = "link", "unreadable"


def _entry_kind(entry: Path, parent_real: Path, root_real: Path) -> tuple[str | None, str]:
    """(None, "") for an ordinary entry; (LINK, why) for a link of any kind (symbolic link, Windows junction or other
    reparse point: its real location is not simply `parent_real / name`) or anything outside the source folder;
    (UNREADABLE, why) if its real location cannot be determined. os.walk(followlinks=False) does not recognise
    Windows junctions as links, so this is checked separately (review of 08-Nov-26)."""
    try:
        if entry.is_symlink():
            return LINK, "symbolic link"
        real = entry.resolve()
    except (OSError, RuntimeError) as exc:
        return UNREADABLE, f"its location cannot be read ({getattr(exc, 'strerror', None) or exc})"
    if real != parent_real / entry.name:
        return LINK, "link or junction"
    if not _is_inside(real, root_real):
        return LINK, "outside the source folder"
    return None, ""


def scan_settings_text(src: FolderSource) -> str:
    """The folder settings a scan used, in words (run log and scan report; owner acceptance W08, 09-Nov-26)."""
    return (f"sub-folders {'included' if src.include_subfolders else 'not included'}; skip patterns: "
            f"{', '.join(src.exclude_patterns) or 'none'}; market time zone {src.market_timezone or '(ask)'}; "
            f"default exchange {src.default_exchange or '-'}; symbol from file name "
            f"{'yes' if src.symbol_from_filename else 'no'}")


def _rel(path, root: Path) -> str:
    try:
        rel = Path(path).relative_to(root).as_posix()
    except ValueError:
        return str(path)
    return rel or "."


def list_candidate_files(settings: Settings, src: FolderSource, *, unreadable: list | None = None,
                         links: list | None = None, skipped_subfolders: list | None = None) -> tuple[list[Path], int]:
    """(files to look at, number excluded by the source's patterns). Never follows links out of the folder:
    symbolic links, Windows junctions and anything whose real location is not inside the folder are skipped (and
    listed in `links`). Every folder or entry that cannot be read is listed in `unreadable` as (relative path, reason),
    so a caller can never mistake an incomplete listing for a complete one (os.walk ignores such errors by default).
    With Include sub-folders off, the names of the selected folder's visible sub-folders are put in
    `skipped_subfolders` (they are not opened or inspected)."""
    unreadable = [] if unreadable is None else unreadable
    links = [] if links is None else links
    root = Path(src.location)

    def walk_error(exc: OSError) -> None:
        unreadable.append((_rel(exc.filename or root, root), exc.strerror or str(exc)))

    try:
        root_real = root.resolve()
    except (OSError, RuntimeError) as exc:
        unreadable.append((".", getattr(exc, "strerror", None) or str(exc)))
        return [], 0
    managed = [Path(settings.data_root).resolve(), Path(settings.output_root).resolve(), Path(settings.code_root).resolve()]
    found, excluded = [], 0
    for dirpath, dirnames, filenames in os.walk(root, onerror=walk_error, followlinks=False):
        here = Path(dirpath)
        try:
            here_real = here.resolve()
        except (OSError, RuntimeError) as exc:
            unreadable.append((_rel(here, root), getattr(exc, "strerror", None) or str(exc)))
            dirnames[:] = []
            continue
        keep = []
        if not src.include_subfolders and skipped_subfolders is not None and here == root:
            skipped_subfolders.extend(d for d in sorted(dirnames) if not _hidden(d))
        # Sub-folders are outside the scan when the user did not include them: they are not inspected or classified
        # at all, so a problem inside one can never make the scan incomplete (re-review of b3b3379, 08-Nov-26).
        for d in sorted(dirnames) if src.include_subfolders else ():
            if _hidden(d):
                continue
            kind, why = _entry_kind(here / d, here_real, root_real)
            if kind == UNREADABLE:
                unreadable.append((_rel(here / d, root), why))
                continue
            if kind == LINK:
                links.append((_rel(here / d, root) + "/", why))
                continue
            if not any(_is_inside((here / d).resolve(), m) for m in managed):
                keep.append(d)
        dirnames[:] = keep
        for name in sorted(filenames):
            p = here / name
            if _hidden(name):
                continue
            kind, why = _entry_kind(p, here_real, root_real)
            if kind == UNREADABLE:
                unreadable.append((_rel(p, root), why))
                continue
            if kind == LINK:
                links.append((_rel(p, root), why))
                continue
            rel = p.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat) for pat in src.exclude_patterns):
                excluded += 1
                continue
            found.append(p)
    return found, excluded


def _inputs_fingerprint(src: FolderSource, answer_row, settings: Settings) -> str:
    """Everything outside the file that can change how it is interpreted or validated."""
    reg = registry_path(settings)
    aliases = hashlib.sha256(reg.read_bytes()).hexdigest()[:16] if reg.is_file() else None
    payload = {"rules": A.RULES_VERSION, "tz": src.market_timezone, "exch": src.default_exchange, "aliases": aliases,
               "sym_from_name": src.symbol_from_filename, "answer": answer_row["answer_id"] if answer_row else None,
               "validation": [str(settings.plausible_min_date), settings.plausible_max_days_ahead,
                              settings.max_daily_move_pct, settings.min_rows, settings.max_gap_days]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _start_scan(run: Run, src: FolderSource) -> int:
    with run.db.transaction() as conn:
        # a scan left 'running' by a run that has ended (crash) is closed as failed, never silently reused
        conn.execute("UPDATE source_scans SET status = 'failed', finished_at = ?, detail = 'interrupted' "
                     "WHERE source_id = ? AND status = 'running' AND run_id IN "
                     "(SELECT run_id FROM runs WHERE status <> 'running')", (utc_now_iso(), src.source_id))
        return int(conn.execute(
            "INSERT INTO source_scans(source_id, run_id, started_at, settings_json, status) VALUES (?, ?, ?, ?, 'running')",
            (src.source_id, run.run_id, utc_now_iso(), json.dumps(src.settings_snapshot(), sort_keys=True))).lastrowid)


def _observe(db: Database, scan_id: int, source_id: int, rel: str, **v) -> None:
    cols = {"scan_id": scan_id, "source_id": source_id, "relative_path": rel, "observed_at": utc_now_iso(), **v}
    for k in ("dataset_ids_json", "interpretation_json", "questions_json"):
        if k in cols and not isinstance(cols[k], (str, type(None))):
            cols[k] = json.dumps(cols[k], default=str, sort_keys=True)
    with db.transaction() as conn:
        conn.execute(f"INSERT INTO source_file_observations({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                     list(cols.values()))


_OUTCOME_OF_INGEST = {"accepted": "imported", "reused": "reused", "rejected": "rejected", "blocked": "blocked",
                      "unsupported": "unsupported", "failed": "failed"}


def scan_source(run: Run, source_id: int, *, today: date | None = None, progress=None,
                should_stop=None) -> ScanResult:
    """Scan one folder source inside `run`. `progress(done, total, relative_path)` is called per file (optional).
    `should_stop()` is asked before each file: when it returns True the scan STOPS safely there (the file being
    processed is always finished, so nothing is left half-written); files not reached keep their earlier state and
    are listed in the report as not processed."""
    db, settings, log = run.db, run.settings, run.logger
    src = get_source(db, source_id)
    if src is None or src.status != "active":
        raise SourceError(f"Source {source_id} is not an active source.")
    root = Path(src.location)
    if not root.is_dir():
        raise SourceError(f"The folder {src.location} is not available (moved, renamed, disconnected or not "
                          "synchronised).", action="Reconnect the drive or check the folder, then scan again.")
    scan_id = _start_scan(run, src)
    result = ScanResult(scan_id, run.run_id, source_id, include_subfolders=src.include_subfolders)
    log.info("Scan settings of '%s' (%s): %s", src.label, src.location, scan_settings_text(src))
    ensure_registry_template(settings)
    registry = load_registry(settings)  # once per scan: every file is matched against the same registry
    result.registry_problems = [p.text for p in registry.problems]
    for text in result.registry_problems:
        log.warning("Alias registry: %s", text)
    today = today or datetime.now(timezone.utc).date()
    try:
        skipped_dirs: list = []
        files, result.excluded = list_candidate_files(settings, src, unreadable=result.unreadable_folders,
                                                      links=result.links_skipped, skipped_subfolders=skipped_dirs)
        result.subfolders_not_scanned = len(skipped_dirs)
        if skipped_dirs:
            log.info("Include sub-folders is off: %d sub-folder(s) of '%s' not scanned (%s)", len(skipped_dirs),
                     src.label, ", ".join(skipped_dirs[:5]) + (" ..." if len(skipped_dirs) > 5 else ""))
        for d, why in result.unreadable_folders:
            log.warning("Scan of '%s' is incomplete: %s could not be read (%s)", src.label, d, why)
        latest = _latest_rows(db, source_id)
        seen = set()
        for n, path in enumerate(files, start=1):
            rel = path.relative_to(root).as_posix()
            if should_stop is not None and should_stop():
                result.stopped = True
                result.not_processed = [p.relative_to(root).as_posix() for p in files[n - 1:]]
                log.warning("Scan stopped by the user: %d file(s) not processed.", len(result.not_processed))
                break
            seen.add(rel)
            if progress:
                progress(n - 1, len(files), rel)
            try:
                outcome, change, action, detail = _scan_one(run, src, scan_id, path, rel, latest.get(rel), today,
                                                            result.overlaps, registry)
            except Exception as exc:  # one bad file never stops the scan; it is recorded as failed
                log.error("Scan of %s failed: %s\n%s", rel, exc, traceback.format_exc())
                detail = f"Unexpected problem: {type(exc).__name__}: {exc}"
                outcome, change, action = "failed", "unreadable", "none"
                _observe(db, scan_id, source_id, rel, change=change, action=action, outcome=outcome, detail=detail)
            result.counts[outcome] = result.counts.get(outcome, 0) + 1
            result.files.append((rel, change, action, outcome, detail))
        for rel, row in (latest.items() if not result.stopped else ()):  # unknown when stopped early
            if rel in seen or row["outcome"] == "missing":
                continue
            blocked = next((d for d, _ in result.unreadable_folders if d == "." or rel == d or rel.startswith(d + "/")),
                           None)
            if blocked is not None:
                # not seen because its folder could not be read: unknown, never reported as missing
                where = "the source folder" if blocked == "." else f"the folder {blocked}"
                detail = (f"Not checked: {where} could not be read. Data already loaded from this file are unchanged; "
                          "the next scan tries again.")
                _observe(db, scan_id, source_id, rel, change="unreadable", action="none", outcome="failed",
                         sha256=row["sha256"], dataset_ids_json=row["dataset_ids_json"], detail=detail)
                result.counts["failed"] = result.counts.get("failed", 0) + 1
                result.files.append((rel, "unreadable", "none", "failed", detail))
                continue
            detail = "No longer found in the folder (moved, renamed, deleted or now excluded). Data already " \
                     "loaded from it are unchanged."
            _observe(db, scan_id, source_id, rel, change="missing", action="none", outcome="missing",
                     sha256=row["sha256"], dataset_ids_json=row["dataset_ids_json"], detail=detail)
            result.counts["missing"] = result.counts.get("missing", 0) + 1
            result.files.append((rel, "missing", "none", "missing", detail))
        if progress:
            progress(len(files), len(files), "")
        result.report_path = _write_report(run, src, result)
        result.overlap_report_path = write_overlap_report(run, result.overlaps)
        result.identification_report_path = _write_identification_report(run, db, source_id, result)
        # an incomplete listing is never recorded as a completed scan
        status, err = ("completed", None) if result.complete else ("failed", "Incomplete: " + result.incomplete_text())
    except BaseException as exc:
        status, err = "failed", f"{type(exc).__name__}: {exc}"
        raise
    finally:
        with db.transaction() as conn:
            conn.execute("UPDATE source_scans SET status = ?, finished_at = ?, summary_json = ?, detail = ? "
                         "WHERE scan_id = ?", (status, utc_now_iso(),
                                               json.dumps({"counts": result.counts, "excluded": result.excluded,
                                                           "stopped": result.stopped,
                                                           "not_processed": result.not_processed,
                                                           "complete": result.complete,
                                                           "unreadable_folders": result.unreadable_folders,
                                                           "links_skipped": result.links_skipped,
                                                           "subfolders_not_scanned": result.subfolders_not_scanned},
                                                          sort_keys=True), err, scan_id))
    log.info("Scan %s of '%s': %s", scan_id, src.label, result.summary())
    return result


def _scan_one(run: Run, src: FolderSource, scan_id: int, path: Path, rel: str, last, today: date,
              overlaps: list | None = None, registry=None):
    db, settings = run.db, run.settings
    sid = src.source_id
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        if last is not None and last["outcome"] == "ignored":
            change = "unchanged"
        else:
            change = "new" if last is None or last["outcome"] == "missing" else "changed"
        detail = f"Not a market-data file type (supported: {', '.join(SUPPORTED_EXTENSIONS)})."
        _observe(db, scan_id, sid, rel, change=change, action="none", outcome="ignored", detail=detail)
        return "ignored", change, "none", detail
    try:
        st = path.stat()
    except OSError as exc:
        detail = f"The file cannot be read ({exc.strerror or exc}). If it is in a cloud folder, make it available offline."
        _observe(db, scan_id, sid, rel, change="unreadable", action="none", outcome="failed", detail=detail)
        return "failed", "unreadable", "none", detail
    answer = latest_answer(db, sid, rel)
    fp = _inputs_fingerprint(src, answer, settings)
    retry_due = bool(last is not None and last["retry_on"] and date.fromisoformat(last["retry_on"]) <= today)

    def unchanged_skip(sha):
        detail = f"Unchanged since {last['observed_at'][:10]}: {OUTCOME_LABELS.get(last['outcome'], last['outcome'])}."
        if last["detail"]:
            detail += f" {last['detail']}"
        _observe(db, scan_id, sid, rel, file_size=st.st_size, file_mtime_ns=st.st_mtime_ns, sha256=sha,
                 change="unchanged", action="skipped", outcome=last["outcome"], inputs_fingerprint=fp,
                 event_id=last["event_id"], attempt_id=last["attempt_id"], dataset_ids_json=last["dataset_ids_json"],
                 interpretation_json=last["interpretation_json"], questions_json=last["questions_json"],
                 retry_on=last["retry_on"], detail=last["detail"])
        return last["outcome"], "unchanged", "skipped", detail

    can_skip = (last is not None and last["outcome"] in FINAL_OUTCOMES and last["inputs_fingerprint"] == fp
                and not retry_due and last["sha256"])
    # The checksum is computed on EVERY scan (review of 08-Nov-26): an edited file can keep its size and modification
    # time (copy tools, restored timestamps), so those are recorded but never used to decide that a file is unchanged.
    try:
        sha = sha256_file(path)
    except OSError as exc:
        detail = f"The file cannot be read ({exc.strerror or exc}). If it is in a cloud folder, make it available offline."
        _observe(db, scan_id, sid, rel, change="unreadable", action="none", outcome="failed", detail=detail)
        return "failed", "unreadable", "none", detail
    if can_skip and sha == last["sha256"]:
        return unchanged_skip(sha)
    if last is None or last["outcome"] == "missing" or not last["sha256"]:
        change = "new"
    else:
        change = "unchanged" if sha == last["sha256"] else "changed"

    # ---- interpret (answers apply only to the structure they were given for) ------------------------------------
    answers = json.loads(answer["answers_json"]) if answer else {}
    kwargs = dict(market_timezone=src.market_timezone, default_exchange=src.default_exchange,
                  symbol_from_filename=src.symbol_from_filename, registry=registry)
    interp = A.interpret_file(path, settings, answers=answers, **kwargs)
    note = ""
    if answer and interp.signature and interp.signature != answer["structure_signature"]:
        interp = A.interpret_file(path, settings, **kwargs)
        note = "Your earlier answer was not reused because the file's structure has changed. "
    base = dict(file_size=st.st_size, file_mtime_ns=st.st_mtime_ns, sha256=sha, change=change, inputs_fingerprint=fp,
                interpretation_json=interp.as_dict())
    if interp.status == A.NEEDS_ANSWER:
        detail = note + interp.message
        _observe(db, scan_id, sid, rel, action="processed", outcome="needs_answer",
                 questions_json=[q.as_dict() for q in interp.questions], detail=detail, **base)
        return "needs_answer", change, "processed", detail
    if interp.status == A.REJECTED:
        detail = note + interp.message
        _observe(db, scan_id, sid, rel, action="processed", outcome="rejected", detail=detail, **base)
        return "rejected", change, "processed", detail

    # ---- load through the normal pipeline -------------------------------------------------------------------------
    o = interp.overrides
    res = ingest_file(run, path, interp.profile, source_label=f"Folder source: {src.label}",
                      note=f"scan {scan_id}: {rel}", exchange=o.get("exchange"), symbol=o.get("symbol"),
                      timeframe=o.get("timeframe"), today=today)
    raw = db.one("SELECT sha256 FROM datasets WHERE dataset_id = ?", (res.raw_dataset_id,)) if res.raw_dataset_id else None
    if raw is not None and raw["sha256"] != sha:
        detail = ("The file changed while it was being scanned; the version that was loaded is recorded under its own "
                  "checksum. Scan again when the file is no longer being written.")
        _observe(db, scan_id, sid, rel, action="processed", outcome="failed", event_id=res.event_id,
                 attempt_id=res.attempt_id, detail=detail, **base)
        return "failed", change, "processed", detail
    outcome = _OUTCOME_OF_INGEST.get(res.outcome, "failed")
    detail = note + (res.message or "")
    retry_on = res.retry_on
    if outcome == "rejected" and res.attempt_id:
        # rejected ONLY because some dates are after today + plausible_max_days_ahead (rule D2-33): the unchanged file
        # is processed again by the first scan on or after the date that cures it
        attempt = db.one("SELECT * FROM ingest_attempts WHERE attempt_id = ?", (res.attempt_id,))
        retry_on = _date_limit_retry(db, attempt, today, settings)[1]
        if retry_on:
            detail += f" It will be loaded again automatically by a scan on or after {retry_on.isoformat()}."
    if outcome in ("imported", "reused"):
        _record_display_names(db, res.dataset_ids, interp)
    if outcome == "imported":
        found = check_new_datasets(run, res.dataset_ids)
        if overlaps is not None:
            overlaps.extend(found)
        if found:
            detail += " Overlap with existing data: " + "; ".join(f.note() for f in found) + "."
    _observe(db, scan_id, sid, rel, action="processed", outcome=outcome, event_id=res.event_id,
             attempt_id=res.attempt_id, dataset_ids_json=list(res.dataset_ids),
             retry_on=retry_on.isoformat() if retry_on else None, detail=detail.strip(), **base)
    return outcome, change, "processed", detail.strip()


def _record_display_names(db: Database, dataset_ids, interp) -> None:
    """DQ-8 review (03-Nov-26): a registry match keeps its canonical display name ("NIFTY 50") with the instrument."""
    match = ((interp.decisions or {}).get("identification") or {}).get("match") or {}
    if match.get("status") not in ("canonical", "alias") or not match.get("canonical"):
        return
    for ds in dataset_ids:
        row = db.one("SELECT instrument_id FROM datasets WHERE dataset_id = ?", (ds,))
        if row is not None and row["instrument_id"] is not None:
            record_display_name(db, row["instrument_id"], match["canonical"])


REPORT_COLUMNS = ("File", "Change", "Action", "Result", "Detail")
IDENT_COLUMNS = ("Exception", "Cleaned name", "Identity used", "Possible matches", "Files", "File names", "Explanation")
IDENT_LABELS = {"provisional": "Not in the alias registry (provisional identity)",
                "ambiguous": "Ambiguous: alias of more than one instrument",
                "name_column_disagreement": "File name and file columns disagree (column used)",
                "crypto_venue_unknown": "Cryptocurrency, trading venue unknown"}


def identification_exceptions(states: list) -> list[dict]:
    """Identification exceptions of the files' CURRENT state, grouped by kind and cleaned name (so "RELIANCE.csv",
    "RELIANCE (1).csv" and "RELIANCE - Copy.csv" are one line). Used by the scan report and the Sources screen."""
    groups: dict = {}
    for st in states:
        ident = (st.interpretation.get("decisions") or {}).get("identification") or {}
        kind = ident.get("exception")
        if not kind or st.outcome in ("missing", "ignored", "unsupported"):
            continue
        cleaned = (ident.get("cleaned") or {}).get("cleaned", "")
        match = ident.get("match") or {}
        key = (kind, cleaned)
        g = groups.setdefault(key, {"kind": kind, "label": IDENT_LABELS.get(kind, kind), "cleaned": cleaned,
                                    "identity": match.get("symbol") or "", "candidates": match.get("candidates") or [],
                                    "files": [], "explanation": match.get("method") or ""})
        g["files"].append(st.relative_path)
        if kind == "name_column_disagreement":
            g["explanation"] = next((w for w in st.interpretation.get("warnings", []) if "column" in w), g["explanation"])
    return sorted(groups.values(), key=lambda g: (g["kind"], g["cleaned"]))


def _write_identification_report(run: Run, db: Database, source_id: int, result: ScanResult) -> Path | None:
    groups = identification_exceptions(file_states(db, source_id, include_missing=False))
    if not groups and not result.registry_problems:
        return None
    stamp = datetime.now().strftime("%d_%b_%y_%H%M%S")
    path = run.output_path(f"Identification_Exceptions_{stamp}.csv")
    with open(path, "x", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(IDENT_COLUMNS)
        for g in groups:
            w.writerow((g["label"], g["cleaned"], g["identity"], "; ".join(g["candidates"]), len(g["files"]),
                        "; ".join(g["files"]), g["explanation"]))
        for text in result.registry_problems:
            w.writerow(("Alias registry problem", "", "", "", 0, str(registry_path(run.settings)), text))
    return path


def _write_report(run: Run, src: FolderSource, result: ScanResult) -> Path:
    stamp = datetime.now().strftime("%d_%b_%y_%H%M%S")
    path = run.output_path(f"Scan_Report_{stamp}.csv")
    with open(path, "x", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("Source", src.label, "Folder", src.location, "Scan",
                    "complete" if result.complete else "INCOMPLETE: " + result.incomplete_text(),
                    "Sub-folders", "included" if src.include_subfolders else
                    f"not included ({result.subfolders_not_scanned} not scanned)",
                    "Skip patterns", "; ".join(src.exclude_patterns) or "none"))
        w.writerow(REPORT_COLUMNS)
        for rel, change, action, outcome, detail in result.files:
            w.writerow((rel, change, action, OUTCOME_LABELS.get(outcome, outcome), detail))
        for rel in result.not_processed:
            w.writerow((rel, "", "none", "Not processed (scan stopped by you)",
                        "Its earlier state, if any, is unchanged. Scan again to process it."))
        for rel, why in result.unreadable_folders:
            w.writerow((rel, "unreadable", "none", "Could not be read",
                        f"{why}. Files inside were not checked, so this scan is incomplete."))
        for rel, why in result.links_skipped:
            w.writerow((rel, "skipped", "none", "Link not followed",
                        f"{why}: Q-MAP never reads through links, so files behind it are not scanned."))
    return path
