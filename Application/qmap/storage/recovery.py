"""Crash recovery and registry verification.

Recovery is simple and testable. It runs at the start of every run and can be run on demand.
It never deletes a registered raw file and never deletes an unregistered raw file.

| Situation after a crash                                     | Action                                   |
|--------------------------------------------------------------|------------------------------------------|
| `started` event is stale, final raw file present + hash OK   | Complete the registration                |
| `started` event is stale, no valid final file                | Delete temp file, mark event failed      |
| Temp file with no live event                                 | Delete it                                |
| Raw file with no database record and no live event           | REPORT as orphan (never auto-deleted)    |
| Cleaned file with no database record, older than stale limit | Delete (it is reproducible from raw)     |
| Run left `running` beyond the stale limit                    | Mark failed (interrupted)                |
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core.config import Settings
from ..core.logging_setup import get_logger
from ..core.runs import mark_interrupted_runs
from ..data_engine.format_detect import DetectedFormat
from .db import Database
from .files import safe_remove, sha256_file
from .registry import _commit_registration, _finish_event

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
    interrupted_runs: list[str] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return bool(self.orphan_raw_files or self.missing_files or self.checksum_mismatches)

    def summary(self) -> str:
        parts = [f"{k}={len(v)}" for k, v in self.__dict__.items() if v]
        return ", ".join(parts) if parts else "nothing to recover"


def _files_under(root: Path, skip_dir_name: str = "_incoming"):
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file() and skip_dir_name not in path.relative_to(root).parts:
            yield path


def recover_incomplete(settings: Settings, db: Database, *, stale_minutes: int | None = None,
                       delete_cleaned_orphans: bool = True) -> RecoveryReport:
    stale = settings.stale_minutes if stale_minutes is None else stale_minutes
    now = datetime.now(timezone.utc)
    cutoff_iso = (now - timedelta(minutes=stale)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    cutoff_epoch = time.time() - stale * 60
    report = RecoveryReport()

    report.interrupted_runs = mark_interrupted_runs(db, stale, now)

    # --- interrupted raw registrations -------------------------------------
    started = db.query(
        "SELECT e.*, r.status AS run_status FROM ingest_events e JOIN runs r USING (run_id) WHERE e.status = 'started'")
    live_event_ids: set[int] = set()
    for ev in started:
        is_stale = ev["run_status"] != "running" or ev["received_at"] <= cutoff_iso
        if not is_stale:
            live_event_ids.add(ev["event_id"])
            continue
        eid, rel, sha = ev["event_id"], ev["intended_relative_path"], ev["sha256"]
        final = settings.data_path(rel) if rel else None
        tmp = settings.raw_incoming_dir / f"{eid}.tmp"
        if final is not None and final.is_file() and sha256_file(final) == sha:
            existing = db.one("SELECT * FROM datasets WHERE layer = 'raw' AND sha256 = ?", (sha,))
            detected = DetectedFormat(kind=ev["detected_format"])
            _commit_registration(db, eid, sha, detected, rel, existing)
            from .files import make_read_only

            make_read_only(final)
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

    # --- stray temporary files ---------------------------------------------
    if settings.raw_incoming_dir.exists():
        for tmp in settings.raw_incoming_dir.iterdir():
            if not tmp.is_file():
                continue
            try:
                eid = int(tmp.stem)
            except ValueError:
                eid = None
            if eid is not None and eid in live_event_ids:
                continue
            if eid is None and tmp.stat().st_mtime > cutoff_epoch:
                continue
            if safe_remove(tmp):
                report.deleted_temp_files.append(tmp.name)
    if settings.cleaned_incoming_dir.exists():
        for tmp in settings.cleaned_incoming_dir.iterdir():
            if tmp.is_file() and tmp.stat().st_mtime <= cutoff_epoch and safe_remove(tmp):
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

    # --- orphan cleaned files (reproducible, so removed once stale) --------
    for path in _files_under(settings.cleaned_dir):
        rel = settings.to_relative(path)
        if rel not in registered and path.stat().st_mtime <= cutoff_epoch:
            if delete_cleaned_orphans and safe_remove(path):
                report.deleted_cleaned_orphans.append(rel)
                log.warning("Removed orphan cleaned file (reproducible from raw): %s", rel)

    # --- registered files that are missing ---------------------------------
    for row in db.query("SELECT relative_path FROM datasets"):
        if not settings.data_path(row["relative_path"]).is_file():
            report.missing_files.append(row["relative_path"])
            log.error("Registered file is missing: %s", row["relative_path"])
    return report


def verify_registry(settings: Settings, db: Database) -> RecoveryReport:
    """Full integrity check: re-hash every registered file. Reports problems; never repairs silently."""
    report = recover_incomplete(settings, db, delete_cleaned_orphans=False)
    for row in db.query("SELECT relative_path, sha256 FROM datasets"):
        path = settings.data_path(row["relative_path"])
        if path.is_file() and sha256_file(path) != row["sha256"]:
            report.checksum_mismatches.append(row["relative_path"])
            log.error("Checksum mismatch for registered file: %s", row["relative_path"])
    return report
