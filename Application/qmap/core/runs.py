"""Run lifecycle: unique Run IDs, output folders and manifests.

Run ID format: <MODULE>_<YYYYMMDD>_<HHMMSS> in UTC. Two runs started in the same second
get a numeric suffix (_02, _03 ...). Reservation is safe against simultaneous runs:
the run folder is created with an atomic mkdir, and the Run ID is then claimed through
the primary key of the `runs` table.
"""

from __future__ import annotations

import contextlib
import json
import logging
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
    finished: bool = False

    @property
    def relative_dir(self) -> str:
        return self.dir.resolve().relative_to(self.settings.output_root).as_posix()

    def output_path(self, name: str) -> Path:
        """Path for a new output file inside this run's folder."""
        return self.dir / name


def ensure_module(db: Database, code: str, name: str, version: str = __version__) -> None:
    with db.transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO modules(module_code, name, version) VALUES (?, ?, ?)",
                     (code, name, version))
        conn.execute("UPDATE modules SET version = ? WHERE module_code = ? AND version <> ?",
                     (version, code, version))


def _reserve_run(settings: Settings, db: Database, module_code: str, area: str, now: datetime,
                 params: dict) -> tuple[str, Path]:
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
            if "runs.run_id" not in str(exc):
                run_dir.rmdir()
                raise
            # The id is already used (for example in another output area): release our empty folder.
            with contextlib.suppress(OSError):
                run_dir.rmdir()
            continue
        return run_id, run_dir
    raise RuntimeError(f"Could not reserve a Run ID based on {base} after {MAX_SUFFIX} attempts.")


def start_run(settings: Settings, db: Database, module_code: str, *, area: str, module_name: str | None = None,
              params: dict | None = None, now: datetime | None = None, recover: bool = True) -> Run:
    params = params or {}
    ensure_module(db, module_code, module_name or module_code)
    if recover:
        from ..storage.recovery import recover_incomplete  # local import avoids a cycle

        recover_incomplete(settings, db)
    now = now or datetime.now(timezone.utc)
    run_id, run_dir = _reserve_run(settings, db, module_code, area, now, params)
    run = Run(run_id=run_id, module_code=module_code, area=area, dir=run_dir, settings=settings, db=db,
              started_at=utc_now_iso(), params=params)
    run._log_handler = attach_run_log(run_dir, run_id, settings.log_level)
    run.logger.info("Run %s started (module %s, area %s)", run_id, module_code, area)
    return run


def _kind(path: Path) -> str:
    return _KIND_BY_EXT.get(path.suffix.lower(), "other")


def finish_run(run: Run, status: str = "completed", error: str | None = None) -> Path:
    """Close the run: stop logging, hash outputs, write the manifest last, then update the database."""
    if run.finished:
        return run.dir / MANIFEST_NAME
    if status not in ("completed", "failed", "cancelled"):
        raise ValueError(f"invalid final run status {status!r}")
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


def mark_interrupted_runs(db: Database, stale_minutes: int, now: datetime | None = None) -> list[str]:
    """Runs left in 'running' for longer than the stale threshold are marked failed (interrupted)."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=stale_minutes)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT run_id FROM runs WHERE status IN ('created', 'running') AND started_at <= ?", (cutoff,)
        ).fetchall()
        ids = [r["run_id"] for r in rows]
        for run_id in ids:
            conn.execute("UPDATE runs SET status = 'failed', finished_at = ?, error_message = 'interrupted' "
                         "WHERE run_id = ?", (utc_now_iso(), run_id))
    return ids
