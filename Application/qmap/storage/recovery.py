"""Crash recovery and registry verification.

Recovery runs at the start of every run and can be run on demand (`python -m qmap recover`).
It never deletes a registered file and never deletes an unregistered raw file.

When is something "interrupted"? A run is LIVE while its process holds the run's liveness lock (see
core/runs.py), however long it has been going. Work is treated as interrupted only when its run is not
live AND (the run is no longer 'running' OR it started more than `stale_minutes` ago). The age rule is a
second, independent safeguard for the moment a run is being created and for file systems without locks.

| Situation (only for work of a run that is not live, see above) | Action                               |
|----------------------------------------------------------------|--------------------------------------|
| `started` receipt, final raw file present + hash OK            | Complete the registration            |
| `started` receipt, no valid final file                         | Delete its temp file, mark it failed |
| Raw temp file whose receipt is finished (or unknown and old)   | Delete it                            |
| Raw file with no database record                               | REPORT as orphan (never deleted)     |
| Cleaned file / cleaned temp file not registered                | Delete (reproducible from raw); the  |
|                                                                | registration is re-checked first     |
| Run left `running`                                             | Mark failed (interrupted)            |
| Registered file missing / unreadable / wrong checksum          | REPORT (verify re-hashes everything) |
| Storage action (move / delete) left `started`                  | Finish or undo it (storage_class.py) |
| Derived-timeframe file / temp file not registered              | Delete (reproducible from its source)|
| Unregistered file in Temporary_Data                            | REPORT (never deleted)               |

A dataset whose file the user deleted (Temporary data, `file_deleted_at`) is not reported as missing.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core.config import Settings
from ..core.logging_setup import get_logger
from ..core.runs import mark_interrupted_runs, run_is_alive
from ..data_engine.format_detect import DetectedFormat
from .db import Database
from .files import make_read_only, safe_remove, sha256_file
from .registry import EventAlreadyFinished, _commit_registration, _finish_event
from .storage_class import is_open_destination, open_destinations, recover_storage_actions

log = get_logger("recovery")


@dataclass
class RecoveryReport:
    completed_events: list[int] = field(default_factory=list)
    failed_events: list[int] = field(default_factory=list)
    deleted_temp_files: list[str] = field(default_factory=list)
    orphan_raw_files: list[str] = field(default_factory=list)
    deleted_cleaned_orphans: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    checksum_mismatches: list[str] = field(default_factory=list)
    unreadable_files: list[str] = field(default_factory=list)
    interrupted_runs: list[str] = field(default_factory=list)
    storage_actions_closed: list[int] = field(default_factory=list)
    unregistered_temporary_files: list[str] = field(default_factory=list)
    storage_inconsistencies: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # anything recovery could not do; nothing is hidden

    @property
    def needs_attention(self) -> bool:
        return bool(self.orphan_raw_files or self.missing_files or self.checksum_mismatches
                    or self.unreadable_files or self.unregistered_temporary_files or self.storage_inconsistencies
                    or self.problems)

    @property
    def has_actions(self) -> bool:
        return any(bool(v) for v in self.__dict__.values())

    def as_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        parts = [f"{k}={len(v)}" for k, v in self.__dict__.items() if v]
        return ", ".join(parts) if parts else "nothing to recover"


_SKIPPED_DIRS = {"_incoming", "_quarantine"}  # temp files and preserved corrupt copies are handled separately


def _files_under(root: Path):
    if not root.exists():
        return
    for path in root.rglob("*"):
        try:
            if path.is_file() and not (_SKIPPED_DIRS & set(path.relative_to(root).parts)):
                yield path
        except OSError:  # vanished or unreadable while scanning
            continue


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None  # vanished meanwhile (another process finished with it)


class _Liveness:
    """Decides, per run, whether its work may be treated as interrupted. Cached for one recovery pass."""

    def __init__(self, settings: Settings, db: Database, cutoff_iso: str):
        self.settings, self.db, self.cutoff_iso = settings, db, cutoff_iso
        self._cache: dict[str, bool] = {}

    def is_live(self, run_id: str | None) -> bool | None:
        """True = do not touch; False = interrupted; None = unknown run (caller falls back to file age)."""
        if run_id is None:
            return None
        if run_id in self._cache:
            return self._cache[run_id]
        row = self.db.one("SELECT status, started_at FROM runs WHERE run_id = ?", (run_id,))
        if row is None:
            return None
        alive = run_is_alive(self.settings, run_id)
        live = alive is True or (row["status"] in ("created", "running") and (row["started_at"] or "") > self.cutoff_iso)
        self._cache[run_id] = live
        return live


def _cleaned_run_id(path: Path) -> str | None:
    """Run ID embedded in a cleaned file name (<sha12>_<version hash>_<Run ID>.parquet) or temp name."""
    if path.suffix == ".parquet":
        parts = path.stem.split("_", 2)
        return parts[2] if len(parts) == 3 else None
    if path.suffix == ".tmp" and "." in path.stem:
        return path.stem.split(".", 1)[0]
    return None


def recover_incomplete(settings: Settings, db: Database, *, stale_minutes: int | None = None,
                       delete_cleaned_orphans: bool = True) -> RecoveryReport:
    stale = settings.stale_minutes if stale_minutes is None else stale_minutes
    now = datetime.now(timezone.utc)
    cutoff_iso = (now - timedelta(minutes=stale)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    cutoff_epoch = time.time() - stale * 60
    report = RecoveryReport()
    live = _Liveness(settings, db, cutoff_iso)

    report.interrupted_runs = mark_interrupted_runs(db, stale, now, settings=settings)

    # --- interrupted raw registrations -------------------------------------
    started = db.query(
        "SELECT e.*, r.status AS run_status FROM ingest_events e JOIN runs r USING (run_id) WHERE e.status = 'started'")
    for ev in started:
        if live.is_live(ev["run_id"]) is not False:
            continue  # its process is still working on it
        eid, rel, sha = ev["event_id"], ev["intended_relative_path"], ev["sha256"]
        tmp = settings.raw_incoming_dir / f"{eid}.tmp"
        try:
            final = settings.data_path(rel) if rel else None
            valid = final is not None and final.is_file() and sha256_file(final) == sha
        except (OSError, ValueError) as exc:
            report.problems.append(f"event {eid}: could not check {rel}: {exc}")
            log.error("Recovery could not check the stored file of event %s (%s): %s", eid, rel, exc)
            continue
        try:
            if valid:
                existing = db.one("SELECT * FROM datasets WHERE layer = 'raw' AND sha256 = ?", (sha,))
                _commit_registration(db, eid, sha, DetectedFormat(kind=ev["detected_format"]), rel, existing)
                try:
                    make_read_only(final)
                except OSError as exc:
                    log.warning("Recovery could not set %s read-only: %s", rel, exc)
                safe_remove(tmp)
                report.completed_events.append(eid)
                log.warning("Recovery completed interrupted registration (event %s, %s)", eid, rel)
            else:
                if safe_remove(tmp):
                    report.deleted_temp_files.append(tmp.name)
                with db.transaction() as conn:
                    _finish_event(conn, eid, "failed", None, "incomplete registration (cleaned up by recovery)")
                report.failed_events.append(eid)
                log.warning("Recovery marked event %s failed (no valid stored file)", eid)
        except EventAlreadyFinished:
            log.info("Event %s was finished by another process during recovery", eid)

    # --- stray temporary raw files -----------------------------------------
    # Each is re-checked against the database at the moment of deletion, so a receipt that began
    # after the query above is never touched.
    if settings.raw_incoming_dir.exists():
        for tmp in list(settings.raw_incoming_dir.iterdir()):
            if not tmp.is_file():
                continue
            try:
                eid = int(tmp.stem) if tmp.suffix == ".tmp" else None
            except ValueError:
                eid = None
            ev = db.one("SELECT status, run_id FROM ingest_events WHERE event_id = ?", (eid,)) if eid is not None else None
            if ev is not None:
                deletable = ev["status"] != "started" or live.is_live(ev["run_id"]) is False
            else:
                m = _mtime(tmp)
                deletable = m is not None and m <= cutoff_epoch
            if deletable and safe_remove(tmp):
                report.deleted_temp_files.append(tmp.name)

    # --- storage actions (Permanent/Temporary moves and deletions) left unfinished -------------
    recover_storage_actions(settings, db, live.is_live, report)

    # --- stray temporary managed files (names start with the Run ID of the run that owns them) ----------
    for incoming in (settings.cleaned_incoming_dir, settings.timeframe_incoming_dir, settings.temporary_dir / "_incoming"):
        if not incoming.exists():
            continue
        for tmp in list(incoming.iterdir()):
            if not tmp.is_file() or not _cleaned_safe_to_delete(tmp, live, cutoff_epoch):
                continue
            if safe_remove(tmp):
                report.deleted_temp_files.append(tmp.name)

    # --- orphan raw files (report only) ------------------------------------
    registered = {r["relative_path"] for r in db.query("SELECT relative_path FROM datasets")}
    live_paths = {r["intended_relative_path"] for r in db.query(
        "SELECT intended_relative_path FROM ingest_events WHERE status = 'started'")}
    for path in _files_under(settings.raw_dir):
        rel = settings.to_relative(path)
        if rel not in registered and rel not in live_paths:
            report.orphan_raw_files.append(rel)
            log.warning("Orphan raw file (no database record): %s. Not deleted; re-ingest the original to adopt it.", rel)

    # --- orphan cleaned / derived-timeframe files (reproducible, so removed when provably abandoned) --------
    moving_to = open_destinations(db)
    for path in [*_files_under(settings.cleaned_dir), *_files_under(settings.timeframe_dir)]:
        rel = settings.to_relative(path)
        if rel in registered or rel in moving_to or not delete_cleaned_orphans:
            continue
        if not _cleaned_safe_to_delete(path, live, cutoff_epoch):
            continue
        # re-check at the moment of deletion: never delete a file that has just been registered or is being moved here
        if db.one("SELECT 1 FROM datasets WHERE relative_path = ?", (rel,)) is not None or is_open_destination(db, rel):
            continue
        if safe_remove(path):
            report.deleted_cleaned_orphans.append(rel)
            log.warning("Removed orphan managed file (unregistered, its run is not live; reproducible from its source): %s",
                        rel)
        elif path.exists():
            report.problems.append(f"could not remove orphan managed file {rel}")

    # --- unregistered files in the Temporary area (report only: never deleted automatically) -------------
    for path in _files_under(settings.temporary_dir):
        rel = settings.to_relative(path)
        if rel not in registered and rel not in moving_to:
            report.unregistered_temporary_files.append(rel)
            log.warning("Unregistered file in Temporary_Data (not deleted): %s", rel)

    report.storage_inconsistencies = find_storage_inconsistencies(db)
    for item in report.storage_inconsistencies:
        log.error("Storage record inconsistent (reported, not changed): %s", item)

    # --- registered files that are missing (a file the user deleted on purpose is not missing) ----------
    for row in db.query("SELECT relative_path FROM datasets WHERE file_deleted_at IS NULL"):
        if not settings.data_path(row["relative_path"]).is_file():
            report.missing_files.append(row["relative_path"])
            log.error("Registered file is missing: %s", row["relative_path"])
    return report


def find_storage_inconsistencies(db: Database) -> list[str]:
    """Datasets whose storage class, path or deletion state is not explained by the storage-action audit trail.

    Since schema migration 6 the database refuses such changes; this finds rows changed directly BEFORE that
    migration was applied. Report only: nothing is repaired automatically.
    """
    out = []
    for r in db.query("SELECT dataset_id, storage_class, relative_path FROM datasets "
                      "WHERE (storage_class = 'temporary') <> (substr(relative_path, 1, 15) = 'Temporary_Data/')"):
        out.append(f"dataset {r['dataset_id']}: storage class {r['storage_class']} does not match its path "
                   f"{r['relative_path']}")
    for r in db.query("SELECT d.dataset_id FROM datasets d WHERE d.file_deleted_at IS NOT NULL AND NOT EXISTS ("
                      "SELECT 1 FROM storage_actions a WHERE a.dataset_id = d.dataset_id AND a.action = 'delete_file' "
                      "AND a.status = 'completed' AND a.from_path = d.relative_path)"):
        out.append(f"dataset {r['dataset_id']}: marked deleted without a recorded delete action")
    for r in db.query(
            "SELECT d.dataset_id, d.storage_class, d.relative_path, "
            "(SELECT a.to_path FROM storage_actions a WHERE a.dataset_id = d.dataset_id AND a.action = 'move' "
            " AND a.status = 'completed' ORDER BY a.action_id DESC LIMIT 1) AS last_move "
            "FROM datasets d WHERE d.layer <> 'raw'"):
        if r["last_move"] is None and r["storage_class"] == "temporary":
            out.append(f"dataset {r['dataset_id']}: Temporary without a recorded move")
        elif r["last_move"] is not None and r["last_move"] != r["relative_path"]:
            out.append(f"dataset {r['dataset_id']}: path {r['relative_path']} differs from its last recorded move "
                       f"({r['last_move']})")
    return out


def _cleaned_safe_to_delete(path: Path, live: _Liveness, cutoff_epoch: float) -> bool:
    """An unregistered cleaned (or cleaned temp) file may be removed only if no live run can still own it."""
    state = live.is_live(_cleaned_run_id(path))
    if state is not None:
        return state is False
    m = _mtime(path)  # owner unknown: fall back to age
    return m is not None and m <= cutoff_epoch


def verify_registry(settings: Settings, db: Database) -> RecoveryReport:
    """Full integrity check: recovery (without deleting cleaned files) plus a re-hash of every registered file.

    Reports problems; never repairs a registered file.
    """
    report = recover_incomplete(settings, db, delete_cleaned_orphans=False)
    for row in db.query("SELECT relative_path, sha256 FROM datasets WHERE file_deleted_at IS NULL"):
        path = settings.data_path(row["relative_path"])
        if not path.is_file():
            continue  # already listed as missing
        try:
            actual = sha256_file(path)
        except OSError as exc:
            report.unreadable_files.append(f"{row['relative_path']} ({exc})")
            log.error("Registered file could not be read: %s (%s)", row["relative_path"], exc)
            continue
        if actual != row["sha256"]:
            report.checksum_mismatches.append(row["relative_path"])
            log.error("Checksum mismatch for registered file: %s", row["relative_path"])
    return report
