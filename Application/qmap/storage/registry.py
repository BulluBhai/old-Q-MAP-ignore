"""Raw-file registration with a receipt record for every file received.

Design rules (Stage 2):
* Raw files are content-addressed: Raw_Data/<sha256[:2]>/<sha256>.<ext>. Identical content is
  stored once, whatever its filename or extension.
* Every receipt gets its own row in `ingest_events` (original path, filename, time, source),
  including receipts of content that is already registered.
* The intent is committed (`started` event) before any file is moved, so recovery can finish
  or discard an interrupted registration after a restart.
* A registered raw file is never overwritten, modified or automatically deleted.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..core.runs import Run
from ..data_engine.format_detect import STORED_EXTENSION, DetectedFormat, detect_format
from .db import Database, utc_now_iso
from .faults import maybe_fail
from .files import copy_durably, make_read_only, safe_remove, sha256_file


@dataclass
class Receipt:
    event_id: int
    status: str  # registered_new | reused_existing | unsupported | failed
    raw_dataset_id: int | None = None
    sha256: str | None = None
    detected: DetectedFormat | None = None
    relative_path: str | None = None
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in ("registered_new", "reused_existing")


def raw_relative_path(sha256: str, detected_kind: str) -> str:
    return f"Raw_Data/{sha256[:2]}/{sha256}.{STORED_EXTENSION[detected_kind]}"


def find_raw_by_sha(db: Database, sha256: str):
    return db.one("SELECT * FROM datasets WHERE layer = 'raw' AND sha256 = ?", (sha256,))


def _insert_event(db: Database, run: Run, *, original_path: str, original_filename: str, original_extension: str,
                  file_size, file_mtime, source_label, note, sha256=None, detected_format=None,
                  intended_relative_path=None, status: str, raw_dataset_id=None, detail=None) -> int:
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO ingest_events(run_id, received_at, original_path, original_filename, original_extension, "
            "file_size, file_mtime, source_label, note, sha256, detected_format, intended_relative_path, status, "
            "raw_dataset_id, detail) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run.run_id, utc_now_iso(), original_path, original_filename, original_extension, file_size, file_mtime,
             source_label, note, sha256, detected_format, intended_relative_path, status, raw_dataset_id, detail))
        return int(cur.lastrowid)


def _finish_event(conn: sqlite3.Connection, event_id: int, status: str, raw_dataset_id: int | None, detail: str | None):
    conn.execute("UPDATE ingest_events SET status = ?, raw_dataset_id = ?, detail = ? WHERE event_id = ?",
                 (status, raw_dataset_id, detail, event_id))


def _fail_event(db: Database, event_id: int, detail: str) -> None:
    with db.transaction() as conn:
        _finish_event(conn, event_id, "failed", None, detail)


def receive_file(run: Run, src: str | Path, *, source_label: str | None = None, note: str | None = None) -> Receipt:
    """Register a file as raw data (or recognise it as already registered) and log the receipt."""
    settings, db, log = run.settings, run.db, run.logger
    src = Path(src)
    try:
        resolved = str(src.resolve())
    except OSError:
        resolved = str(src)
    base = dict(original_path=resolved, original_filename=src.name, original_extension=src.suffix.lower(),
                source_label=source_label, note=note)

    # 1. Hash the source. The source is only ever read.
    try:
        st = src.stat()
        mtime = datetime.fromtimestamp(st.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        base.update(file_size=st.st_size, file_mtime=mtime)
        sha = sha256_file(src)
    except OSError as exc:
        base.setdefault("file_size", None)
        base.setdefault("file_mtime", None)
        detail = f"Could not read the file: {exc}"
        eid = _insert_event(db, run, status="failed", detail=detail, **base)
        log.error("Receipt %s failed: %s (%s)", eid, detail, src)
        return Receipt(event_id=eid, status="failed", detail=detail)
    maybe_fail("after_hash")

    # 2. Detect the format from content.
    detected = detect_format(src, max_size_bytes=settings.max_file_size_mb * 1024 * 1024)
    if not detected.supported:
        eid = _insert_event(db, run, status="unsupported", sha256=sha, detail=detected.reason, **base)
        log.error("Receipt %s unsupported: %s (%s)", eid, detected.reason, src.name)
        return Receipt(event_id=eid, status="unsupported", sha256=sha, detected=detected, detail=detected.reason)

    # 3. Already registered? Then just record the receipt.
    existing = find_raw_by_sha(db, sha)
    repair = False
    if existing is not None:
        stored = settings.data_path(existing["relative_path"])
        if stored.is_file() and stored.stat().st_size == st.st_size:
            eid = _insert_event(db, run, status="reused_existing", sha256=sha, detected_format=detected.kind,
                                intended_relative_path=existing["relative_path"],
                                raw_dataset_id=existing["dataset_id"],
                                detail="identical content already registered", **base)
            log.info("Receipt %s: %s already registered as dataset %s (no new copy)", eid, src.name,
                     existing["dataset_id"])
            return Receipt(event_id=eid, status="reused_existing", raw_dataset_id=existing["dataset_id"], sha256=sha,
                           detected=detected, relative_path=existing["relative_path"],
                           detail="identical content already registered")
        repair = True  # record exists but the stored file is missing: restore it
        rel = existing["relative_path"]
    else:
        rel = raw_relative_path(sha, detected.kind)

    # 4. Commit the intent BEFORE touching the raw store.
    eid = _insert_event(db, run, status="started", sha256=sha, detected_format=detected.kind,
                        intended_relative_path=rel, **base)
    maybe_fail("after_event_started")

    # 5. Durable copy to a temporary file on the same volume, then verify the copy.
    tmp = settings.raw_incoming_dir / f"{eid}.tmp"
    copy_durably(src, tmp)
    if sha256_file(tmp) != sha:
        safe_remove(tmp)
        detail = "The source file changed while it was being copied. Nothing was registered; try again."
        _fail_event(db, eid, detail)
        log.error("Receipt %s failed: %s", eid, detail)
        return Receipt(event_id=eid, status="failed", sha256=sha, detected=detected, detail=detail)
    maybe_fail("after_temp_copy")

    # 6. Atomic rename into the content-addressed location. Never overwrite a stored file.
    final = settings.data_path(rel)
    final.parent.mkdir(parents=True, exist_ok=True)
    if final.exists():
        if sha256_file(final) == sha:
            safe_remove(tmp)  # identical content already there (also the Windows read-only case)
        else:
            safe_remove(tmp)
            detail = (f"A different file already occupies {rel}. It was NOT overwritten. "
                      "Run the registry verification and investigate.")
            _fail_event(db, eid, detail)
            log.error("Receipt %s failed: %s", eid, detail)
            return Receipt(event_id=eid, status="failed", sha256=sha, detected=detected, detail=detail)
    else:
        os.replace(tmp, final)
    maybe_fail("after_rename")
    make_read_only(final)

    # 7. One transaction: dataset row + event outcome.
    status, ds_id, detail = _commit_registration(db, eid, sha, detected, rel, existing if repair else None)
    maybe_fail("after_db_commit")
    log.info("Receipt %s: %s -> %s (dataset %s)%s", eid, src.name, status, ds_id, " [restored missing file]" if repair else "")
    return Receipt(event_id=eid, status=status, raw_dataset_id=ds_id, sha256=sha, detected=detected,
                   relative_path=rel, detail=detail)


def _commit_registration(db: Database, event_id: int, sha: str, detected: DetectedFormat, rel: str, existing):
    """Insert the raw dataset (unless it exists) and mark the event. Shared with crash recovery."""
    with db.transaction() as conn:
        maybe_fail("before_db_commit")
        if existing is not None:
            ds_id, status, detail = existing["dataset_id"], "reused_existing", "stored file was missing and has been restored"
        else:
            try:
                cur = conn.execute(
                    "INSERT INTO datasets(layer, file_format, relative_path, sha256, created_at) "
                    "VALUES ('raw', ?, ?, ?, ?)", (detected.kind, rel, sha, utc_now_iso()))
                ds_id, status, detail = int(cur.lastrowid), "registered_new", None
            except sqlite3.IntegrityError as exc:
                if "sha256" not in str(exc) and "relative_path" not in str(exc):
                    raise
                row = conn.execute("SELECT dataset_id FROM datasets WHERE layer = 'raw' AND sha256 = ?",
                                   (sha,)).fetchone()
                if row is None:
                    raise
                ds_id, status = int(row["dataset_id"]), "reused_existing"
                detail = "identical content was registered concurrently by another ingest"
        _finish_event(conn, event_id, status, ds_id, detail)
    return status, ds_id, detail
