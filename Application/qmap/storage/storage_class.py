"""Permanent / Temporary classification of managed (standardised or derived) datasets.

Rules (Database Manager, 01-Nov-26):

* Only managed datasets (layers `cleaned` and `timeframe`) have a storage class. Raw files - the preserved originals -
  are always permanent and are never moved or deleted (database trigger `trg_datasets_storage`).
* A TEMPORARY dataset lives under `Q-MAP_DATA/Temporary/<its permanent relative path>` (Blueprint v1.2, OD-8), so
  the mapping is reversible and the file name (which carries its lineage) never changes. Temporary data never expires
  on its own. Datasets moved to Temporary before OD-8 stay under `Temporary_Data/` until the user relocates them
  (Make Permanent, then Move to Temporary); nothing is moved automatically.
* Moving never modifies the data: the file is copied, the copy's SHA-256 is checked against the registered checksum,
  the registry is switched to the new path in one transaction, and only then is the old copy removed.
* Only a TEMPORARY dataset's file can be deleted, and only by the user. The registry record, its provenance and its
  audit trail are kept for ever (datasets are never deleted); the record is marked `file_deleted_at`.
* Every action is recorded in `storage_actions` BEFORE any file is touched, so recovery can finish or undo an
  interrupted action and never mistakes a half-moved file for an abandoned one.

Every function returns plain-English blockers instead of raising for a refused action; nothing is done until the
assessment has no blockers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..core.config import LEGACY_TEMPORARY_FOLDER, TEMPORARY_FOLDER, Settings
from ..core.runs import Run
from .db import Database, utc_now_iso
from .files import copy_durably, place_without_overwrite, safe_remove, sha256_file, unique_tmp_name

PERMANENT, TEMPORARY = "permanent", "temporary"
STORAGE_CLASSES = (PERMANENT, TEMPORARY)
MANAGED_LAYERS = ("cleaned", "timeframe")
LABELS = {PERMANENT: "Permanent", TEMPORARY: "Temporary"}


def temporary_path_for(permanent_rel: str) -> str:
    return f"{TEMPORARY_FOLDER}/{permanent_rel}"


TEMPORARY_PREFIXES = (f"{TEMPORARY_FOLDER}/", f"{LEGACY_TEMPORARY_FOLDER}/")


def is_legacy_temporary_path(rel: str) -> bool:
    return rel.startswith(f"{LEGACY_TEMPORARY_FOLDER}/")


def permanent_path_for(temporary_rel: str) -> str:
    """Inverse of temporary_path_for; also accepts the pre-OD-8 `Temporary_Data/` location."""
    for prefix in TEMPORARY_PREFIXES:
        if temporary_rel.startswith(prefix):
            return temporary_rel[len(prefix):]
    raise ValueError(f"not a temporary-area path: {temporary_rel!r}")


def incoming_dir_for(settings: Settings, rel: str) -> Path:
    """Temp files for a destination go to `<its top-level data folder>/_incoming`, which recovery watches."""
    return settings.data_root / rel.split("/", 1)[0] / "_incoming"


@dataclass
class StorageAssessment:
    """What an action would affect, and whether it may proceed."""

    dataset_id: int
    action: str  # move | delete_file
    layer: str = ""
    label: str = ""  # e.g. "NSE:NIFTY 1D (dataset 7)"
    storage_class: str = ""
    to_class: str | None = None
    from_path: str = ""
    to_path: str | None = None
    dependents: list[str] = field(default_factory=list)  # derived datasets built from this one
    run_uses: list[str] = field(default_factory=list)  # Run IDs that used it as an input
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return not self.blockers


@dataclass
class StorageResult:
    ok: bool
    message: str
    action_id: int | None = None
    assessment: StorageAssessment | None = None


def _dataset_row(db: Database, dataset_id: int):
    return db.one(
        "SELECT d.*, i.exchange, i.symbol FROM datasets d LEFT JOIN instruments i USING (instrument_id) "
        "WHERE d.dataset_id = ?", (dataset_id,))


def _label(row) -> str:
    who = f"{row['exchange']}:{row['symbol']}" if row["exchange"] else "raw file"
    return f"{who} {row['timeframe'] or ''} (dataset {row['dataset_id']})".replace("  ", " ")


def _common(settings: Settings, db: Database, dataset_id: int, action: str) -> tuple[StorageAssessment, object]:
    a = StorageAssessment(dataset_id=dataset_id, action=action)
    row = _dataset_row(db, dataset_id)
    if row is None:
        a.blockers.append(f"Dataset {dataset_id} is not registered.")
        return a, None
    a.layer, a.label, a.storage_class, a.from_path = row["layer"], _label(row), row["storage_class"], row["relative_path"]
    if row["layer"] not in MANAGED_LAYERS:
        a.blockers.append("This is an original source file (raw data). Original files are always kept permanently and "
                          "are never moved or deleted by Q-MAP.")
    if row["file_deleted_at"]:
        a.blockers.append(f"The file of this dataset was already deleted on {row['file_deleted_at'][:10]}.")
    open_action = db.one("SELECT action_id, run_id FROM storage_actions WHERE dataset_id = ? AND status = 'started'",
                         (dataset_id,))
    if open_action is not None:
        a.blockers.append(f"Another storage action on this dataset has not finished (action {open_action['action_id']}, "
                          f"run {open_action['run_id']}). Wait for it, or run recovery if Q-MAP was closed during it.")
    a.dependents = [_label(r) for r in db.query(
        "SELECT d.*, i.exchange, i.symbol FROM datasets d LEFT JOIN instruments i USING (instrument_id) "
        "WHERE d.parent_dataset_id = ? AND d.file_deleted_at IS NULL ORDER BY d.dataset_id", (dataset_id,))]
    a.run_uses = [r["run_id"] for r in db.query(
        "SELECT run_id FROM run_inputs WHERE dataset_id = ? ORDER BY run_id", (dataset_id,))]
    if not a.blockers:
        path = settings.data_path(row["relative_path"])
        if not path.is_file():
            a.blockers.append(f"The registered file is missing ({row['relative_path']}). Run 'verify' and investigate "
                              "before changing this dataset.")
    return a, row


def assess_move(settings: Settings, db: Database, dataset_id: int, to_class: str) -> StorageAssessment:
    a, row = _common(settings, db, dataset_id, "move")
    a.to_class = to_class
    if to_class not in STORAGE_CLASSES:
        a.blockers.append(f"Unknown storage class {to_class!r}; use 'permanent' or 'temporary'.")
        return a
    if row is None or a.blockers:
        return a
    if row["storage_class"] == to_class:
        a.blockers.append(f"This dataset is already {LABELS[to_class]}.")
        return a
    a.to_path = temporary_path_for(row["relative_path"]) if to_class == TEMPORARY else permanent_path_for(row["relative_path"])
    if settings.data_path(a.to_path).exists():
        a.blockers.append(f"A file already exists at the destination ({a.to_path}); it is never overwritten. Run "
                          "'verify' and investigate.")
    if db.one("SELECT 1 FROM datasets WHERE relative_path = ?", (a.to_path,)) is not None:
        a.blockers.append(f"The destination path is already registered to another dataset ({a.to_path}).")
    if a.run_uses:
        a.warnings.append(f"Used as an input by {len(a.run_uses)} research run(s). Their records keep pointing to this "
                          "dataset; the registry is updated, so the data stay reachable.")
    if to_class == TEMPORARY:
        a.warnings.append("Temporary data never expire on their own; only you can delete them.")
    return a


def assess_delete(settings: Settings, db: Database, dataset_id: int) -> StorageAssessment:
    a, row = _common(settings, db, dataset_id, "delete_file")
    if row is None or a.blockers:
        return a
    if row["storage_class"] != TEMPORARY:
        a.blockers.append("Only Temporary datasets can be deleted. Move it to Temporary first if you really no longer "
                          "need it.")
    if a.dependents:
        a.blockers.append("Other datasets were built from this one: " + ", ".join(a.dependents)
                          + ". Delete those first (they would lose their source).")
    if a.run_uses:
        a.warnings.append(f"Used as an input by research run(s) {', '.join(a.run_uses)}. Their results stay, but could "
                          "no longer be reproduced from this dataset. Deleting needs your explicit confirmation.")
    if row["layer"] == "cleaned":
        a.warnings.append("The original source file stays preserved; only this standardised copy is deleted. Loading "
                          "the same file again unchanged does NOT re-create it (see the user guide).")
    a.warnings.append("The registry record, its provenance and the audit trail are kept; only the data file is removed.")
    return a


def _start_action(db: Database, run: Run, a: StorageAssessment, reason: str | None) -> int:
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO storage_actions(run_id, dataset_id, action, from_class, to_class, from_path, to_path, reason, "
            "status, started_at) VALUES (?,?,?,?,?,?,?,?, 'started', ?)",
            (run.run_id, a.dataset_id, a.action, a.storage_class, a.to_class, a.from_path, a.to_path,
             reason.strip() if reason and reason.strip() else None, utc_now_iso()))
        return int(cur.lastrowid)


def _finish_action(conn, action_id: int, status: str, detail: str | None = None) -> None:
    conn.execute("UPDATE storage_actions SET status = ?, finished_at = ?, detail = ? WHERE action_id = ? "
                 "AND status = 'started'", (status, utc_now_iso(), detail, action_id))


def move_dataset(run: Run, dataset_id: int, to_class: str, *, reason: str | None = None) -> StorageResult:
    """Move a managed dataset between Permanent and Temporary storage (see the module notes for the steps)."""
    settings, db, log = run.settings, run.db, run.logger
    a = assess_move(settings, db, dataset_id, to_class)
    if not a.allowed:
        return StorageResult(False, " ".join(a.blockers), assessment=a)
    row = _dataset_row(db, dataset_id)
    src, dest = settings.data_path(a.from_path), settings.data_path(a.to_path)
    action_id = _start_action(db, run, a, reason)  # (1) intent first: recovery now knows about the destination
    tmp = incoming_dir_for(settings, a.to_path) / f"{run.run_id}.{unique_tmp_name()}"
    placed = False
    try:
        if sha256_file(src) != row["sha256"]:  # (2) never move a damaged file
            raise RuntimeError("the stored file does not match its registered checksum; run 'verify' and investigate")
        copy_durably(src, tmp)  # (3) copy, check, place without overwriting
        if sha256_file(tmp) != row["sha256"]:
            raise RuntimeError("the copy does not match the registered checksum")
        dest.parent.mkdir(parents=True, exist_ok=True)
        place_without_overwrite(tmp, dest)
        placed = True
        with db.transaction() as conn:  # (4) switch the registry, only if nothing changed meanwhile
            cur = conn.execute(
                "UPDATE datasets SET storage_class = ?, relative_path = ? WHERE dataset_id = ? AND relative_path = ? "
                "AND storage_class = ? AND file_deleted_at IS NULL",
                (to_class, a.to_path, dataset_id, a.from_path, a.storage_class))
            if cur.rowcount != 1:
                raise RuntimeError("the dataset changed while it was being moved")
            _finish_action(conn, action_id, "completed")
    except Exception as exc:
        safe_remove(tmp)
        if placed:
            safe_remove(dest)  # our own unregistered copy; the registered file is untouched
        with db.transaction() as conn:
            _finish_action(conn, action_id, "failed", f"{type(exc).__name__}: {exc}")
        log.error("Storage move of dataset %s failed: %s", dataset_id, exc)
        return StorageResult(False, f"The move did not happen ({exc}). The dataset is unchanged.", action_id, a)
    removed = safe_remove(src)  # (5) the old copy is now an unregistered duplicate
    if not removed and src.exists():
        log.warning("Moved dataset %s, but the old copy %s could not be removed yet; recovery will remove it.",
                    dataset_id, a.from_path)
    log.info("Dataset %s moved from %s to %s (%s -> %s)", dataset_id, a.from_path, a.to_path, a.storage_class, to_class)
    return StorageResult(True, f"{a.label} is now {LABELS[to_class]}. Stored at {a.to_path}.", action_id, a)


def delete_temporary_file(run: Run, dataset_id: int, *, reason: str | None = None,
                          confirm_run_inputs: bool = False) -> StorageResult:
    """Delete the data file of a TEMPORARY dataset, on the user's explicit request. The record is kept."""
    settings, db, log = run.settings, run.db, run.logger
    a = assess_delete(settings, db, dataset_id)
    if a.allowed and a.run_uses and not confirm_run_inputs:
        a.blockers.append("This dataset was used by research runs; confirm explicitly to delete it.")
    if not a.allowed:
        return StorageResult(False, " ".join(a.blockers), assessment=a)
    action_id = _start_action(db, run, a, reason)
    with db.transaction() as conn:  # commit first: a crash after this is finished by recovery
        cur = conn.execute("UPDATE datasets SET file_deleted_at = ? WHERE dataset_id = ? AND relative_path = ? AND "
                           "storage_class = 'temporary' AND file_deleted_at IS NULL",
                           (utc_now_iso(), dataset_id, a.from_path))
        if cur.rowcount != 1:
            _finish_action(conn, action_id, "failed", "the dataset changed before it could be deleted")
            return StorageResult(False, "The dataset changed before it could be deleted; nothing was deleted.", action_id, a)
        _finish_action(conn, action_id, "completed",
                       json.dumps({"run_inputs_confirmed": bool(a.run_uses and confirm_run_inputs)}))
    path = settings.data_path(a.from_path)
    if not safe_remove(path) and path.exists():
        log.warning("Dataset %s is marked deleted but its file could not be removed yet; recovery will remove it.",
                    dataset_id)
    log.warning("Temporary dataset %s deleted by the user (%s). Record and provenance kept.", dataset_id, a.from_path)
    return StorageResult(True, f"The file of {a.label} was deleted. Its registry record and history are kept.",
                         action_id, a)


# ---- recovery (called by storage.recovery.recover_incomplete) ------------------------------------------------------
def open_destinations(db: Database) -> set[str]:
    """Destinations of storage actions that have not finished: recovery must never delete these files."""
    return {r["to_path"] for r in db.query("SELECT to_path FROM storage_actions WHERE status = 'started' "
                                           "AND to_path IS NOT NULL")}


def is_open_destination(db: Database, rel: str) -> bool:
    return db.one("SELECT 1 FROM storage_actions WHERE status = 'started' AND to_path = ?", (rel,)) is not None


def recover_storage_actions(settings: Settings, db: Database, is_live, report) -> None:
    """Finish or undo storage actions whose run has ended, and remove copies that are provably redundant.

    `is_live(run_id)` is recovery's liveness test (True = do not touch). Findings go into `report`.
    """
    for act in db.query("SELECT * FROM storage_actions WHERE status = 'started' ORDER BY action_id"):
        if is_live(act["run_id"]) is not False:
            continue
        row = db.one("SELECT relative_path, file_deleted_at FROM datasets WHERE dataset_id = ?", (act["dataset_id"],))
        if act["action"] == "move":
            done = row is not None and row["relative_path"] == act["to_path"]
            if not done and act["to_path"] and act["to_path"] != (row["relative_path"] if row else None):
                if safe_remove(settings.data_path(act["to_path"])):
                    report.deleted_temp_files.append(act["to_path"])
        else:
            done = row is not None and row["file_deleted_at"] is not None
        with db.transaction() as conn:
            _finish_action(conn, act["action_id"], "completed" if done else "failed",
                           None if done else "interrupted (cleaned up by recovery; the dataset is unchanged)")
        report.storage_actions_closed.append(act["action_id"])

    # Old copy left behind by a completed move: removed only if no dataset uses that path and it is an exact copy.
    for act in db.query("SELECT a.from_path, d.sha256 FROM storage_actions a JOIN datasets d USING (dataset_id) "
                        "WHERE a.action = 'move' AND a.status = 'completed'"):
        old = settings.data_path(act["from_path"])
        if not old.is_file() or db.one("SELECT 1 FROM datasets WHERE relative_path = ?", (act["from_path"],)):
            continue
        try:
            same = sha256_file(old) == act["sha256"]
        except OSError as exc:
            report.problems.append(f"could not check the old copy {act['from_path']}: {exc}")
            continue
        if same and safe_remove(old):
            report.deleted_temp_files.append(act["from_path"])
        elif not same:
            report.problems.append(f"{act['from_path']} is not a copy of the moved dataset; left untouched")

    # A deletion was committed but its file is still there (crash, or the file was locked at the time).
    for row in db.query("SELECT relative_path FROM datasets WHERE file_deleted_at IS NOT NULL"):
        path = settings.data_path(row["relative_path"])
        if path.is_file() and safe_remove(path):
            report.deleted_temp_files.append(row["relative_path"])
