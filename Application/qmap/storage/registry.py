"""Raw-file registration with a receipt record for every file received.

Design rules (Stage 2):
* Raw files are content-addressed: Raw_Data/<sha256[:2]>/<sha256>.<ext>. Identical content is
  stored once, whatever its filename or extension.
* Every receipt gets its own row in `ingest_events` (original path, filename, time, source),
  including receipts of content that is already registered.
* The intent is committed (`started` event) before any file is moved, so recovery can finish
  or discard an interrupted registration after a restart.
* A registered raw file is never overwritten, modified or automatically deleted, and its SHA-256 is verified
  against the registered checksum before it is reused (size is never trusted). A mismatch fails the receipt;
  `restore_raw_file` is the explicit, audited way to put the original back (the corrupt copy is quarantined).
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..core.errors import IngestError
from ..core.runs import Run
from ..data_engine.format_detect import STORED_EXTENSION, DetectedFormat, detect_format
from .db import Database, utc_now_iso
from .faults import maybe_fail
from .files import copy_durably, make_read_only, place_without_overwrite, safe_remove, sha256_file


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


class EventAlreadyFinished(RuntimeError):
    """A receipt that is no longer 'started' was about to be finalised a second time."""


def _finish_event(conn: sqlite3.Connection, event_id: int, status: str, raw_dataset_id: int | None, detail: str | None):
    """Move a receipt from 'started' to its final status. A final status is never rewritten."""
    cur = conn.execute("UPDATE ingest_events SET status = ?, raw_dataset_id = ?, detail = ? "
                       "WHERE event_id = ? AND status = 'started'", (status, raw_dataset_id, detail, event_id))
    if cur.rowcount != 1:
        raise EventAlreadyFinished(f"receipt {event_id} is not in progress (already finalised by another process?)")


def _fail_event(db: Database, event_id: int, detail: str) -> None:
    with db.transaction() as conn:
        _finish_event(conn, event_id, "failed", None, detail)


CHANGED_SINCE_EXAMINED = "E_CHANGED_SINCE_EXAMINED"


def receive_file(run: Run, src: str | Path, *, source_label: str | None = None, note: str | None = None,
                 expected_sha256: str | None = None) -> Receipt:
    """Register a file as raw data (or recognise it as already registered) and log the receipt.

    `expected_sha256` (folder scans): the checksum of the content the caller examined. If the file now has another
    checksum it changed in between, and NOTHING is registered (the receipt is recorded as failed), so content can
    never be registered with an interpretation made from earlier content."""
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
    if expected_sha256 is not None and sha != expected_sha256:
        detail = (f"{CHANGED_SINCE_EXAMINED}: the file changed after it was examined (checksum {expected_sha256[:12]}... when examined, "
                  f"{sha[:12]}... now). Nothing was registered. Scan again when the file is no longer being written.")
        eid = _insert_event(db, run, status="failed", sha256=sha, detail=detail, **base)
        log.warning("Receipt %s: %s (%s)", eid, detail, src.name)
        return Receipt(event_id=eid, status="failed", sha256=sha, detail=detail)

    # 2. Detect the format from content.
    detected = detect_format(src, max_size_bytes=settings.max_file_size_mb * 1024 * 1024)
    if not detected.supported:
        eid = _insert_event(db, run, status="unsupported", sha256=sha, detail=detected.reason, **base)
        log.error("Receipt %s unsupported: %s (%s)", eid, detected.reason, src.name)
        return Receipt(event_id=eid, status="unsupported", sha256=sha, detected=detected, detail=detected.reason)

    # 3. Already registered? Verify the stored copy against the REGISTERED checksum before reusing it.
    #    File size is not proof of integrity: a same-size corruption must not be reused or processed.
    existing = find_raw_by_sha(db, sha)
    repair = False
    if existing is not None:
        stored = settings.data_path(existing["relative_path"])
        rel = existing["relative_path"]
        if stored.is_file():
            try:
                actual = sha256_file(stored)
            except OSError as exc:
                actual = f"unreadable ({exc})"
            if actual == existing["sha256"]:
                eid = _insert_event(db, run, status="reused_existing", sha256=sha, detected_format=detected.kind,
                                    intended_relative_path=rel, raw_dataset_id=existing["dataset_id"],
                                    detail="identical content already registered; stored copy verified", **base)
                log.info("Receipt %s: %s already registered as dataset %s (stored copy verified, no new copy)", eid,
                         src.name, existing["dataset_id"])
                return Receipt(event_id=eid, status="reused_existing", raw_dataset_id=existing["dataset_id"],
                               sha256=sha, detected=detected, relative_path=rel,
                               detail="identical content already registered; stored copy verified")
            detail = (f"E_RAW_CORRUPT: the stored raw file {rel} (dataset {existing['dataset_id']}) no longer matches its "
                      f"registered SHA-256 (registered {existing['sha256'][:12]}..., found {actual[:12]}...). It was NOT "
                      f"used, overwritten or deleted, and nothing was processed. The file you supplied DOES match the "
                      f"registered checksum, so you can restore the stored copy explicitly (the corrupt copy is "
                      f"preserved in Raw_Data/_quarantine): python -m qmap restore-raw --dataset-id "
                      f"{existing['dataset_id']} --from \"{resolved}\" --reason \"<why>\"")
            eid = _insert_event(db, run, status="failed", sha256=sha, detected_format=detected.kind,
                                intended_relative_path=rel, raw_dataset_id=existing["dataset_id"], detail=detail, **base)
            log.error("Receipt %s: %s", eid, detail)
            return Receipt(event_id=eid, status="failed", raw_dataset_id=existing["dataset_id"], sha256=sha,
                           detected=detected, relative_path=rel, detail=detail)
        repair = True  # the stored file is MISSING (nothing to overwrite): restore it from this verified source
    else:
        rel = raw_relative_path(sha, detected.kind)

    # 4. Commit the intent BEFORE touching the raw store.
    eid = _insert_event(db, run, status="started", sha256=sha, detected_format=detected.kind,
                        intended_relative_path=rel, **base)
    maybe_fail("after_event_started")

    # 5. Durable copy to a temporary file on the same volume, then verify the copy.
    tmp = settings.raw_incoming_dir / f"{eid}.tmp"
    final = settings.data_path(rel)
    try:
        copy_durably(src, tmp)
        copy_ok = sha256_file(tmp) == sha
    except OSError as exc:
        return _abandon(run, eid, tmp, sha, detected, f"Could not copy the file into the raw store: {exc}. "
                                                      "Nothing was registered; fix the cause and try again.")
    if not copy_ok:
        return _abandon(run, eid, tmp, sha, detected,
                        "The source file changed while it was being copied. Nothing was registered; try again.")
    maybe_fail("after_temp_copy")

    # 6. Atomic placement that can NEVER replace an existing file (no check-then-replace window).
    try:
        final.parent.mkdir(parents=True, exist_ok=True)
        place_without_overwrite(tmp, final)
    except FileExistsError:
        # Someone else (a concurrent ingest, or an interrupted earlier one) already put a file there.
        try:
            same = sha256_file(final) == sha
        except OSError:
            same = False
        if not same:
            return _abandon(run, eid, tmp, sha, detected,
                            f"A different file already occupies {rel}. It was NOT overwritten. "
                            "Run the registry verification and investigate.")
        safe_remove(tmp)  # identical content is already in place: adopt it, never touch it
    except OSError as exc:
        return _abandon(run, eid, tmp, sha, detected, f"Could not place the file in the raw store: {exc}. "
                                                      "Nothing was registered; fix the cause and try again.")
    maybe_fail("after_rename")
    try:
        make_read_only(final)
    except OSError as exc:  # not fatal: the content is verified and the registration is still correct
        log.warning("Receipt %s: could not set the read-only flag on %s (%s)", eid, rel, exc)

    # 7. One transaction: dataset row + event outcome.
    status, ds_id, detail = _commit_registration(db, eid, sha, detected, rel, existing if repair else None)
    maybe_fail("after_db_commit")
    log.info("Receipt %s: %s -> %s (dataset %s)%s", eid, src.name, status, ds_id, " [restored missing file]" if repair else "")
    return Receipt(event_id=eid, status=status, raw_dataset_id=ds_id, sha256=sha, detected=detected,
                   relative_path=rel, detail=detail)


def _abandon(run: Run, event_id: int, tmp: Path, sha: str, detected: DetectedFormat, detail: str) -> Receipt:
    """Give up a started registration: remove our temporary file, mark the receipt failed, report it."""
    safe_remove(tmp)
    _fail_event(run.db, event_id, detail)
    run.logger.error("Receipt %s failed: %s", event_id, detail)
    return Receipt(event_id=event_id, status="failed", sha256=sha, detected=detected, detail=detail)


def _commit_registration(db: Database, event_id: int, sha: str, detected: DetectedFormat, rel: str, existing,
                         detail_override: str | None = None):
    """Insert the raw dataset (unless it exists) and mark the event. Shared with crash recovery."""
    with db.transaction() as conn:
        maybe_fail("before_db_commit")
        if existing is not None:
            ds_id, status = existing["dataset_id"], "reused_existing"
            detail = detail_override or "stored file was missing and has been restored"
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


def restore_raw_file(run: Run, dataset_id: int, source: str | Path, *, reason: str) -> Receipt:
    """Explicitly restore a registered raw file whose stored copy is corrupt (or missing).

    Safe by construction:
    * a written reason is required and recorded;
    * `source` must match the REGISTERED SHA-256 (a wrong file changes nothing);
    * an intact stored file is never replaced;
    * the corrupt copy is MOVED to Raw_Data/_quarantine (evidence kept, never deleted);
    * the intent is committed first and the registration machinery is reused, so a crash at any step
      is completed or cleaned up by recovery, and the earlier failed receipt stays in the audit trail.
    """
    settings, db, log = run.settings, run.db, run.logger
    if not reason or not reason.strip():
        raise IngestError("A written reason is required to restore a raw file.", code="E_REASON_REQUIRED",
                          check="raw_integrity", action='Add --reason "why this restore is correct".')
    row = db.one("SELECT * FROM datasets WHERE dataset_id = ? AND layer = 'raw'", (dataset_id,))
    if row is None:
        raise IngestError(f"There is no registered raw dataset {dataset_id}.", code="E_DATASET_NOT_FOUND", check="raw_integrity")
    src = Path(source)
    try:
        st = src.stat()
        src_sha = sha256_file(src)
    except OSError as exc:
        raise IngestError(f"The restore source could not be read: {exc}.", code="E_RESTORE_SOURCE", check="raw_integrity") from exc
    if src_sha != row["sha256"]:
        raise IngestError(
            f"The file you supplied does not match dataset {dataset_id}'s registered SHA-256 "
            f"(registered {row['sha256'][:12]}..., supplied {src_sha[:12]}...). Nothing was changed.",
            code="E_RESTORE_MISMATCH", check="raw_integrity", action="Supply the original, unmodified file.")
    rel = row["relative_path"]
    final = settings.data_path(rel)
    if final.is_file():
        try:
            intact = sha256_file(final) == row["sha256"]
        except OSError:
            intact = False
        if intact:
            raise IngestError(f"The stored file for dataset {dataset_id} is intact. Nothing to restore.",
                              code="E_RAW_INTACT", check="raw_integrity")

    try:
        resolved = str(src.resolve())
    except OSError:
        resolved = str(src)
    base = dict(original_path=resolved, original_filename=src.name, original_extension=src.suffix.lower(),
                file_size=st.st_size, file_mtime=datetime.fromtimestamp(st.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                source_label="restore-raw", note=f"restore reason: {reason.strip()}")
    eid = _insert_event(db, run, status="started", sha256=src_sha, detected_format=row["file_format"],
                        intended_relative_path=rel, raw_dataset_id=row["dataset_id"], **base)
    tmp = settings.raw_incoming_dir / f"{eid}.tmp"
    copy_durably(src, tmp)
    if sha256_file(tmp) != src_sha:
        safe_remove(tmp)
        detail = "The restore source changed while it was being copied. Nothing was changed; try again."
        _fail_event(db, eid, detail)
        raise IngestError(detail, code="E_RESTORE_SOURCE", check="raw_integrity")

    quarantined = None
    if final.is_file():
        qdir = settings.raw_quarantine_dir
        qdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target = qdir / f"{row['sha256']}.{stamp}_{uuid.uuid4().hex[:6]}.corrupt"
        os.replace(final, target)  # move, never delete: the corrupt copy stays available as evidence
        quarantined = settings.to_relative(target)
    maybe_fail("restore_after_quarantine")
    try:
        place_without_overwrite(tmp, final)
    except FileExistsError:
        # Another process put a file there after the corrupt copy was moved aside: never replace it.
        try:
            same = sha256_file(final) == src_sha
        except OSError:
            same = False
        safe_remove(tmp)
        if not same:
            detail = (f"A different file appeared at {rel} during the restore. It was NOT overwritten"
                      + (f"; the corrupt copy is preserved at {quarantined}" if quarantined else "") + ".")
            _fail_event(db, eid, detail)
            raise IngestError(detail, code="E_RESTORE_CONFLICT", check="raw_integrity",
                              action="Run verify and investigate before trying again.")
    maybe_fail("restore_after_replace")
    make_read_only(final)
    detail = (f"RESTORED from {resolved}; reason: {reason.strip()}; "
              + (f"the corrupt copy was preserved at {quarantined}" if quarantined else "the stored file had been missing"))
    status, ds_id, detail = _commit_registration(db, eid, src_sha, DetectedFormat(kind=row["file_format"]), rel, row,
                                                 detail_override=detail)
    log.warning("Restored raw dataset %s: %s", dataset_id, detail)
    return Receipt(event_id=eid, status=status, raw_dataset_id=ds_id, sha256=src_sha,
                   detected=DetectedFormat(kind=row["file_format"]), relative_path=rel, detail=detail)
