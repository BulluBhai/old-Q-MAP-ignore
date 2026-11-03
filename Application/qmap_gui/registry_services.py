"""Database Manager logic for the Datasets screen (no tkinter): list, explain, re-classify, delete and derive.

Every operation is done by the Foundation (`qmap.catalog`, `qmap.storage.storage_class`, `qmap.data_engine.derive`)
inside a normal Q-MAP run, so it gets a Run ID, a log, a manifest and crash recovery like any load.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from qmap.catalog import DatasetInfo, fmt_date, get_dataset, list_datasets, overview, provenance, timeframe_label
from qmap.core.config import Settings
from qmap.core.errors import QmapError
from qmap.core.runs import run_context
from qmap.data_engine.derive import DERIVED_TIMEFRAMES, assess_derivation, derive_timeframe
from qmap.storage.db import open_database
from qmap.storage.storage_class import (LABELS, is_legacy_temporary_path, PERMANENT, TEMPORARY, StorageAssessment, assess_delete, assess_move,
                                        delete_temporary_file, move_dataset)

from .common import EmitHandler as _EmitHandler
from .services import plain

MODULE_CODE, MODULE_NAME, AREA = "DBM", "Database Manager", "Data_Management"
DERIVABLE = tuple(DERIVED_TIMEFRAMES)  # 1W 1M 1Q 1Y


def _with_db(settings: Settings, fn):
    db = open_database(settings.db_path)
    try:
        return fn(db)
    finally:
        db.close()


def datasets(settings: Settings, *, include_superseded: bool = True, include_deleted: bool = False,
             timeframe: str = "") -> list[DatasetInfo]:
    return _with_db(settings, lambda db: list_datasets(
        db, include_superseded=include_superseded, include_deleted=include_deleted,
        timeframes=(timeframe,) if timeframe else None))


def overview_text(settings: Settings) -> str:
    ov = _with_db(settings, overview)
    if not ov.raw_files:
        return "No data loaded yet. Use Data Management to load your first files."
    tfs = ", ".join(f"{timeframe_label(tf)} {n}" for tf, n in ov.by_timeframe.items()) or "none"
    return (f"{ov.instruments} instrument(s); {ov.datasets_active} active dataset(s) ({tfs}); "
            f"{ov.permanent} Permanent, {ov.temporary} Temporary; {ov.datasets_superseded} superseded; "
            f"{ov.datasets_deleted} deleted by you; {ov.raw_files} original file(s) preserved.")


def row_values(d: DatasetInfo) -> tuple:
    kind = {"cleaned": "Standardised", "timeframe": "Derived"}.get(d.layer, d.layer)
    validation = "Passed with warnings" if d.warnings else "Passed"
    return (d.dataset_id, d.instrument, d.timeframe_label, kind, d.row_count or 0, fmt_date(d.date_from),
            fmt_date(d.date_to), validation, d.storage_label, d.state_label)


def details(settings: Settings, dataset_id: int) -> list[tuple[str, str | None]]:
    """Plain-English description of one dataset, as (text, tag) parts for a text box."""
    def build(db):
        d = get_dataset(db, dataset_id)
        if d is None:
            return [(f"Dataset {dataset_id} is not registered.\n", "error")]
        parts = [(f"{d.instrument}  {d.timeframe_label}  (dataset {d.dataset_id})\n", "bold"),
                 (f"Bars: {d.row_count}   From {fmt_date(d.date_from)} to {fmt_date(d.date_to)}   "
                  f"Volume: {d.volume_status}\n", None),
                 (f"Storage: {d.storage_label}   State: {d.state_label}\n", "warning" if d.storage_class == TEMPORARY else None),
                 (f"Stored at: Q-MAP_DATA/{d.relative_path}\n", "muted"),
                 *([("This Temporary dataset is in the OLD folder Temporary_Data (before the Temporary/ decision). It is "
                     "valid and safe there. To move it to Q-MAP_DATA/Temporary, use Make Permanent, then Move to "
                     "Temporary.\n", "warning")] if d.available and is_legacy_temporary_path(d.relative_path) else []),
                 (f"Processing: {d.processing_version}   Settings fingerprint: {d.config_fingerprint}\n", "muted")]
        if d.source_files:
            parts.append((f"Original file(s): {', '.join(d.source_files)} (preserved unchanged)\n", None))
        parts.append(("Validation: " + ("passed with warnings:\n" if d.warnings else "passed.\n"),
                      "warning" if d.warnings else "ok"))
        parts += [(f"  - {w}\n", "warning") for w in d.warnings]
        parts.append(("Lineage (newest first):\n", "bold"))
        parts += [(f"  {line}\n", None) for line in provenance(db, dataset_id)]
        return parts
    return _with_db(settings, build)


def assess_storage(settings: Settings, ids: list[int], action: str) -> list[StorageAssessment]:
    """action: 'temporary' | 'permanent' (move) or 'delete'."""
    def build(db):
        if action == "delete":
            return [assess_delete(settings, db, i) for i in ids]
        return [assess_move(settings, db, i, action) for i in ids]
    return _with_db(settings, build)


def assess_derive(settings: Settings, ids: list[int], timeframes: list[str]):
    return _with_db(settings, lambda db: [assess_derivation(settings, db, i, tf) for i in ids for tf in timeframes])


def confirmation_text(assessments, verb: str) -> tuple[str, bool]:
    """(text for a confirmation dialog, whether anything can be done)."""
    ok = [a for a in assessments if a.allowed]
    lines = []
    for a in assessments:
        label = getattr(a, "label", "") or f"dataset {getattr(a, 'dataset_id', '')}"
        if a.allowed:
            lines.append(f"WILL {verb}: {label}")
            lines += [f"    note: {w}" for w in a.warnings]
        else:
            lines.append(f"CANNOT {verb}: {label}")
            lines += [f"    reason: {b}" for b in a.blockers]
    return "\n".join(lines), bool(ok)


@dataclass
class OperationSummary:
    run_id: str | None = None
    run_dir: Path | None = None
    done: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    error: str | None = None
    cancelled: bool = False


class OperationJob:
    """Runs a list of (label, callable(run) -> (ok, message)) inside ONE Database Manager run. No widgets here."""

    def __init__(self, settings: Settings, title: str, items: list[tuple[str, Callable]], params: dict,
                 emit: Callable[[dict], None] = lambda event: None):
        self.settings, self.title, self.items, self.params, self.emit = settings, title, items, params, emit
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> OperationSummary:
        summary = OperationSummary()
        handler = _EmitHandler(self.emit)
        logger = logging.getLogger("qmap")
        logger.addHandler(handler)
        db = None
        try:
            self.emit({"type": "stage", "text": "Opening the Q-MAP registry and starting a run"})
            db = open_database(self.settings.db_path)
            with run_context(self.settings, db, MODULE_CODE, area=AREA, module_name=MODULE_NAME,
                             params={"command": self.title, **self.params}) as run:
                summary.run_id, summary.run_dir = run.run_id, run.dir
                self.emit({"type": "run_started", "run_id": run.run_id, "run_dir": str(run.dir),
                           "started": datetime.now(timezone.utc).astimezone().isoformat()})
                for n, (label, op) in enumerate(self.items, start=1):
                    if self._cancel.is_set():
                        summary.cancelled = True
                        self.emit({"type": "log", "text": "Stopped by you: the remaining items were not processed."})
                        break
                    self.emit({"type": "item_start", "index": n, "total": len(self.items), "label": label})
                    try:
                        ok, message = op(run)
                    except QmapError as exc:
                        ok, message = False, plain(exc)
                    except Exception as exc:
                        logger.exception("Unexpected problem with %s", label)
                        ok, message = False, f"Unexpected problem ({type(exc).__name__}): {exc}"
                    (summary.done if ok else summary.failed).append(f"{label}: {message}")
                    self.emit({"type": "item_done", "index": n, "total": len(self.items), "label": label, "ok": ok,
                               "message": message})
        except QmapError as exc:
            summary.error = plain(exc)
        except Exception as exc:
            summary.error = f"Unexpected problem ({type(exc).__name__}): {exc}"
        finally:
            logger.removeHandler(handler)
            if db is not None:
                db.close()
            self.emit({"type": "done", "summary": summary})
        return summary


def storage_items(assessments: list[StorageAssessment], action: str, *, reason: str = "",
                  confirm_run_inputs: bool = False) -> list[tuple[str, Callable]]:
    items = []
    for a in assessments:
        if not a.allowed:
            continue
        if action == "delete":
            op = (lambda run, i=a.dataset_id: (lambda r: (r.ok, r.message))(
                delete_temporary_file(run, i, reason=reason, confirm_run_inputs=confirm_run_inputs)))
        else:
            op = (lambda run, i=a.dataset_id: (lambda r: (r.ok, r.message))(move_dataset(run, i, action, reason=reason)))
        items.append((a.label, op))
    return items


def derive_items(assessments) -> list[tuple[str, Callable]]:
    return [(a.label, (lambda run, i=a.source_dataset_id, tf=a.timeframe: (lambda r: (r.ok, r.message))(
        derive_timeframe(run, i, tf)))) for a in assessments if a.allowed]


__all__ = ["DERIVABLE", "LABELS", "PERMANENT", "TEMPORARY", "OperationJob", "OperationSummary", "assess_derive",
           "assess_storage", "confirmation_text", "datasets", "derive_items", "details", "overview_text",
           "row_values", "storage_items", "timeframe_label"]


def record_decision(settings: Settings, ids: list[int], action: str, reason: str = ""):
    """Reject (reversible) or restore datasets; recorded in dataset_user_decisions. Nothing is deleted or moved."""
    from qmap.data_engine import user_decisions as UD

    fn = UD.reject_datasets if action == "reject" else UD.restore_datasets
    return _with_db(settings, lambda db: fn(db, ids, reason=reason, origin="datasets"))
