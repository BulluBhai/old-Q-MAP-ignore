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
    problems: list[str] = field(default_factory=list)  # anything recovery could not do; nothing is hidden

    @property
    def needs_attention(self) -> bool:
        return bool(self.orphan_raw_files or self.missing_files or self.checksum_mismatches
                    or self.unreadable_files or self.problems)

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

    # --- stray temporary cleaned files ---------------------------------------
    if settings.cleaned_incoming_dir.exists():
        for tmp in list(settings.cleaned_incoming_dir.iterdir()):
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

    # --- orphan cleaned files (reproducible, so removed when provably abandoned) --------
    for path in _files_under(settings.cleaned_dir):
        rel = settings.to_relative(path)
        if rel in registered or not delete_cleaned_orphans:
            continue
        if not _cleaned_safe_to_delete(path, live, cutoff_epoch):
            continue
        # re-check at the moment of deletion: never delete a file that has just been registered
        if db.one("SELECT 1 FROM datasets WHERE relative_path = ?", (rel,)) is not None:
            continue
        if safe_remove(path):
            report.deleted_cleaned_orphans.append(rel)
            log.warning("Removed orphan cleaned file (unregistered, its run is not live; reproducible from raw): %s", rel)
        elif path.exists():
            report.problems.append(f"could not remove orphan cleaned file {rel}")

    # --- registered files that are missing ---------------------------------
    for row in db.query("SELECT relative_path FROM datasets"):
        if not settings.data_path(row["relative_path"]).is_file():
            report.missing_files.append(row["relative_path"])
            log.error("Registered file is missing: %s", row["relative_path"])
    return report


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
    for row in db.query("SELECT relative_path, sha256 FROM datasets"):
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
