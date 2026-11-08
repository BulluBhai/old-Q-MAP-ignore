"""Run lifecycle: unique Run IDs, output folders and manifests.

Run ID format: <MODULE>_<YYYYMMDD>_<HHMMSS> in UTC. Two runs started in the same second
get a numeric suffix (_02, _03 ...). Reservation is safe against simultaneous runs:
the run folder is created with an atomic mkdir, and the Run ID is then claimed through
the primary key of the `runs` table.

Liveness: while a run is open its process holds an operating-system lock on
Q-MAP_DATA/Metadata/run_locks/<Run ID>.lock. The operating system releases that lock the moment
the process ends, however it ends (crash, power loss, closed window). Recovery therefore never
treats a run as interrupted while its lock is held, however long the run has been going; an age
threshold alone cannot prove that a writer has stopped.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import CLEANING_CODE_VERSION, __version__
from ..storage.db import Database, utc_now_iso
from ..storage.files import atomic_write_bytes, sha256_file
from .config import Settings
from .logging_setup import attach_run_log, detach_run_log, get_logger

MANIFEST_NAME = "run_manifest.json"
MAX_SUFFIX = 1000

_KIND_BY_EXT = {
    ".csv": "csv", ".txt": "text", ".log": "log", ".json": "json", ".parquet": "parquet",
    ".xlsx": "excel", ".xls": "excel", ".png": "chart", ".pdf": "pdf",
}


@dataclass
class Run:
    run_id: str
    module_code: str
    area: str
    dir: Path
    settings: Settings
    db: Database
    started_at: str
    params: dict = field(default_factory=dict)
    logger: logging.Logger = field(default_factory=get_logger)
    _log_handler: logging.Handler | None = None
    _lock_fd: int | None = None
    finished: bool = False

    def _release_lock(self) -> None:
        """Release the liveness lock (done by finish_run; the OS does it automatically if the process dies)."""
        if self._lock_fd is not None:
            _unlock(self._lock_fd)
            self._lock_fd = None

    @property
    def relative_dir(self) -> str:
        return self.dir.resolve().relative_to(self.settings.output_root).as_posix()

    def output_path(self, name: str) -> Path:
        """Path for a new output file inside this run's folder."""
        return self.dir / name


# ---- liveness locks ----------------------------------------------------------------------------------------
def _lock_path(settings: Settings, run_id: str) -> Path:
    return settings.data_root / "Metadata" / "run_locks" / f"{run_id}.lock"


def _try_lock_fd(fd: int) -> bool:
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(fd: int) -> None:
    with contextlib.suppress(OSError):
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
    with contextlib.suppress(OSError):
        os.close(fd)


def _acquire_run_lock(settings: Settings, run_id: str) -> int | None:
    """Take the liveness lock for a new run. None if another live process already holds it."""
    path = _lock_path(settings, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)  # not inherited by child processes
    if _try_lock_fd(fd):
        return fd
    os.close(fd)
    return None


def run_is_alive(settings: Settings, run_id: str) -> bool | None:
    """True: the run's process is alive. False: it is not. None: cannot tell (no lock file)."""
    path = _lock_path(settings, run_id)
    try:
        fd = os.open(path, os.O_RDWR)  # never create: a missing file means "unknown"
    except FileNotFoundError:
        return None
    except OSError:
        return True  # cannot even open it (for example locked or access denied): assume alive, be safe
    try:
        if _try_lock_fd(fd):
            _unlock(fd)
            return False
        return True
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)


def _remove_lock_file(settings: Settings, run_id: str) -> None:
    with contextlib.suppress(OSError):
        _lock_path(settings, run_id).unlink()


def ensure_module(db: Database, code: str, name: str, version: str = __version__) -> None:
    with db.transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO modules(module_code, name, version) VALUES (?, ?, ?)",
                     (code, name, version))
        conn.execute("UPDATE modules SET version = ? WHERE module_code = ? AND version <> ?",
                     (version, code, version))


def _reserve_run(settings: Settings, db: Database, module_code: str, area: str, now: datetime,
                 params: dict) -> tuple[str, Path, int]:
    base = f"{module_code}_{now:%Y%m%d_%H%M%S}"
    area_dir = settings.output_root / area
    area_dir.mkdir(parents=True, exist_ok=True)
    for n in range(1, MAX_SUFFIX + 1):
        run_id = base if n == 1 else f"{base}_{n:02d}"
        run_dir = area_dir / run_id
        try:
            run_dir.mkdir()  # atomic: only one process can create a given folder
        except FileExistsError:
            continue
        lock_fd = _acquire_run_lock(settings, run_id)
        if lock_fd is None:  # the same Run ID is live in another output area
            with contextlib.suppress(OSError):
                run_dir.rmdir()
            continue
        try:
            with db.transaction() as conn:
                conn.execute(
                    "INSERT INTO runs(run_id, module_code, status, started_at, params_json, code_version, output_path) "
                    "VALUES (?, ?, 'running', ?, ?, ?, ?)",
                    (run_id, module_code, utc_now_iso(), json.dumps(params, default=str, sort_keys=True),
                     f"qmap {__version__} / {CLEANING_CODE_VERSION}",
                     run_dir.resolve().relative_to(settings.output_root).as_posix()),
                )
        except sqlite3.IntegrityError as exc:
            _unlock(lock_fd)
            if "runs.run_id" not in str(exc):
                run_dir.rmdir()
                raise
            # The id is already used (for example in another output area): release our empty folder.
            with contextlib.suppress(OSError):
                run_dir.rmdir()
            continue
        except BaseException:
            _unlock(lock_fd)
            raise
        return run_id, run_dir, lock_fd
    raise RuntimeError(f"Could not reserve a Run ID based on {base} after {MAX_SUFFIX} attempts.")


def start_run(settings: Settings, db: Database, module_code: str, *, area: str, module_name: str | None = None,
              params: dict | None = None, now: datetime | None = None, recover: bool = True) -> Run:
    params = params or {}
    ensure_module(db, module_code, module_name or module_code)
    report = None
    if recover:
        from ..storage.recovery import recover_incomplete  # local import avoids a cycle

        report = recover_incomplete(settings, db)
    now = now or datetime.now(timezone.utc)
    run_id, run_dir, lock_fd = _reserve_run(settings, db, module_code, area, now, params)
    run = Run(run_id=run_id, module_code=module_code, area=area, dir=run_dir, settings=settings, db=db,
              started_at=utc_now_iso(), params=params, _lock_fd=lock_fd)
    run._log_handler = attach_run_log(run_dir, run_id, settings.log_level)
    run.logger.info("Run %s started (module %s, area %s)", run_id, module_code, area)
    if report is not None and report.has_actions:
        # Make the recovery done just before this run visible in this run's own folder and log.
        atomic_write_bytes(run_dir / "recovery_report.json",
                           json.dumps(report.as_dict(), indent=2, sort_keys=True).encode("utf-8"))
        log = run.logger.warning if report.needs_attention else run.logger.info
        log("Recovery before this run: %s (details in recovery_report.json)", report.summary())
    return run


def _kind(path: Path) -> str:
    return _KIND_BY_EXT.get(path.suffix.lower(), "other")


def finish_run(run: Run, status: str = "completed", error: str | None = None) -> Path:
    """Close the run: stop logging, hash outputs, write the manifest last, then update the database."""
    if run.finished:
        return run.dir / MANIFEST_NAME
    if status not in ("completed", "failed", "cancelled"):
        raise ValueError(f"invalid final run status {status!r}")
    try:
        manifest_path = _finish(run, status, error)
    finally:
        # Always give up liveness, even if finishing failed: recovery can then deal with the run.
        run._release_lock()
    _remove_lock_file(run.settings, run.run_id)
    return manifest_path


def _finish(run: Run, status: str, error: str | None) -> Path:
    run.logger.info("Run %s finished with status %s%s", run.run_id, status, f" ({error})" if error else "")
    if run._log_handler is not None:
        detach_run_log(run._log_handler)
        run._log_handler = None
    finished_at = utc_now_iso()

    outputs = []
    for path in sorted(p for p in run.dir.rglob("*") if p.is_file() and p.name != MANIFEST_NAME
                       and not p.name.endswith(".tmp")):
        outputs.append({
            "relative_path": path.relative_to(run.dir).as_posix(),
            "kind": _kind(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    inputs = [
        {"dataset_id": r["dataset_id"], "sha256": r["sha256"]}
        for r in run.db.query(
            "SELECT d.dataset_id, d.sha256 FROM run_inputs ri JOIN datasets d USING (dataset_id) "
            "WHERE ri.run_id = ? ORDER BY d.dataset_id", (run.run_id,))
    ]
    manifest = {
        "run_id": run.run_id,
        "module_code": run.module_code,
        "area": run.area,
        "status": status,
        "started_at": run.started_at,
        "finished_at": finished_at,
        "qmap_version": __version__,
        "cleaning_code_version": CLEANING_CODE_VERSION,
        "parameters": run.params,
        "error_message": error,
        "input_datasets": inputs,
        "outputs": outputs,
    }
    manifest_path = run.dir / MANIFEST_NAME
    atomic_write_bytes(manifest_path, json.dumps(manifest, indent=2, default=str, sort_keys=True).encode("utf-8"))

    with run.db.transaction() as conn:
        conn.execute("UPDATE runs SET status = ?, finished_at = ?, error_message = ? WHERE run_id = ?",
                     (status, finished_at, error, run.run_id))
        rows = [(run.run_id, f"{run.relative_dir}/{o['relative_path']}", o["kind"], o["sha256"], o["size_bytes"])
                for o in outputs]
        rows.append((run.run_id, f"{run.relative_dir}/{MANIFEST_NAME}", "json", sha256_file(manifest_path),
                     manifest_path.stat().st_size))
        conn.executemany(
            "INSERT OR REPLACE INTO run_outputs(run_id, relative_path, kind, sha256, size_bytes) VALUES (?, ?, ?, ?, ?)",
            rows)
    run.finished = True
    return manifest_path


@contextlib.contextmanager
def run_context(settings: Settings, db: Database, module_code: str, *, area: str, params: dict | None = None,
                module_name: str | None = None, now: datetime | None = None):
    run = start_run(settings, db, module_code, area=area, params=params, module_name=module_name, now=now)
    try:
        yield run
    except BaseException as exc:
        finish_run(run, "failed", f"{type(exc).__name__}: {exc}")
        raise
    else:
        finish_run(run, "completed")


def mark_interrupted_runs(db: Database, stale_minutes: int, now: datetime | None = None, *,
                          settings: Settings | None = None) -> list[str]:
    """Mark runs failed ('interrupted') when they are left 'running' beyond the stale threshold.

    With `settings`, a run whose process still holds its liveness lock is never marked, however old it is.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=stale_minutes)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    candidates = [r["run_id"] for r in db.query(
        "SELECT run_id FROM runs WHERE status IN ('created', 'running') AND started_at <= ?", (cutoff,))]
    if settings is not None:
        candidates = [r for r in candidates if run_is_alive(settings, r) is not True]
    ids = []
    with db.transaction() as conn:
        for run_id in candidates:
            cur = conn.execute("UPDATE runs SET status = 'failed', finished_at = ?, error_message = 'interrupted' "
                               "WHERE run_id = ? AND status IN ('created', 'running')", (utc_now_iso(), run_id))
            if cur.rowcount:
                ids.append(run_id)
    if settings is not None:
        for run_id in ids:
            _remove_lock_file(settings, run_id)
    return ids
