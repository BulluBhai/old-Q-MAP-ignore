"""Background ingest job. Runs in a worker thread and talks to the screen ONLY through `emit` (a queue put).

The job never touches a widget. It calls the Foundation (`run_context`, `ingest_file`) and reports what happened.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from qmap.core.config import Settings
from qmap.core.errors import QmapError
from qmap.core.runs import run_context
from qmap.data_engine.ingest import IngestResult, ingest_file
from qmap.data_engine.overlap import check_new_datasets, write_overlap_report
from qmap.data_engine.profiles import SourceProfile
from qmap.storage.db import open_database

from .common import EmitHandler
from .messages import OUTCOMES, Finding, findings_from_checks
from .services import plain


@dataclass
class FileOutcome:
    path: Path
    outcome: str
    label: str
    message: str
    rows_read: int | None = None
    rows_flagged: int | None = None
    datasets: list = field(default_factory=list)
    issues_report: Path | None = None
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.outcome in ("accepted", "reused")


@dataclass
class RunSummary:
    run_id: str | None = None
    run_dir: Path | None = None
    outcomes: list[FileOutcome] = field(default_factory=list)
    cancelled: bool = False
    error: str | None = None
    overlaps: list = field(default_factory=list)  # OverlapFinding (report only, DQ-9)
    overlap_report: Path | None = None

    def counts(self) -> dict:
        c: dict[str, int] = {}
        for o in self.outcomes:
            c[o.outcome] = c.get(o.outcome, 0) + 1
        return c

    @property
    def rows_total(self) -> int:
        return sum(o.rows_read or 0 for o in self.outcomes)


_EmitHandler = EmitHandler  # moved to .common (shared with the Analytical Workbench)


def outcome_from_result(res: IngestResult, path: Path, db) -> FileOutcome:
    rows_read = rows_flagged = None
    if res.attempt_id:
        row = db.one("SELECT rows_read, rows_flagged FROM ingest_attempts WHERE attempt_id = ?", (res.attempt_id,))
        if row:
            rows_read, rows_flagged = row["rows_read"], row["rows_flagged"]
    findings = findings_from_checks(res.checks)
    message = res.message
    outcome = res.outcome
    if res.outcome == "rejected" and findings:
        errs = [f.title for f in findings if f.severity == "error"]
        message = "Not loaded. Problems: " + "; ".join(errs[:4]) + (" ..." if len(errs) > 4 else "")
    elif res.outcome == "blocked" and res.retry_on is not None:  # rejected only for future dates (D2-33): waiting
        outcome = "waiting"
        message = (f"Not loaded yet: it was rejected only because some dates were in the future. Load it again on or "
                   f"after {res.retry_on.strftime('%d-%b-%y')} and Q-MAP will process it automatically. "
                   "Nothing needs to change.")
    return FileOutcome(path, outcome, OUTCOMES.get(outcome, outcome), message, rows_read, rows_flagged,
                       list(res.dataset_ids), res.issues_report, findings)


class IngestJob:
    def __init__(self, settings: Settings, files: list, profile: SourceProfile, *, exchange: str = "", symbol: str = "",
                 timeframe: str = "", source_label: str = "", note: str = "", force_reason: str = "",
                 emit: Callable[[dict], None] = lambda event: None):
        self.settings, self.files, self.profile, self.emit = settings, [Path(f) for f in files], profile, emit
        self.request = dict(exchange=exchange.strip() or None, symbol=symbol.strip() or None,
                            timeframe=timeframe.strip() or None, source_label=source_label.strip() or None,
                            note=note.strip() or None, force_reason=force_reason.strip() or None)
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Stop after the file currently being processed."""
        self._cancel.set()

    def run(self) -> RunSummary:
        summary = RunSummary()
        handler = _EmitHandler(self.emit)
        logger = logging.getLogger("qmap")
        logger.addHandler(handler)
        db = None
        try:
            self.emit({"type": "stage", "text": "Opening the Q-MAP registry and starting a run"})
            db = open_database(self.settings.db_path)
            params = {"command": "gui-ingest", "profile": self.profile.profile_id,
                      "files": [str(f) for f in self.files]}
            with run_context(self.settings, db, "FOUND", area="Ingestion", module_name="Foundation", params=params) as run:
                summary.run_id, summary.run_dir = run.run_id, run.dir
                self.emit({"type": "run_started", "run_id": run.run_id, "run_dir": str(run.dir),
                           "started": datetime.now(timezone.utc).astimezone().isoformat()})
                for i, path in enumerate(self.files, start=1):
                    if self._cancel.is_set():
                        summary.cancelled = True
                        self.emit({"type": "log", "text": "Cancelled by you: the remaining files were not processed."})
                        break
                    self.emit({"type": "file_start", "index": i, "total": len(self.files), "path": str(path)})
                    self.emit({"type": "stage", "text": f"Loading file {i} of {len(self.files)}"})
                    try:
                        res = ingest_file(run, path, self.profile, source_label=self.request["source_label"],
                                          note=self.request["note"], force_reason=self.request["force_reason"],
                                          exchange=self.request["exchange"], symbol=self.request["symbol"],
                                          timeframe=self.request["timeframe"])
                        outcome = outcome_from_result(res, path, db)
                        if res.outcome == "accepted":  # report-only overlap check (DQ-9), as in a folder scan
                            found = check_new_datasets(run, res.dataset_ids)
                            summary.overlaps.extend(found)
                            if found:
                                outcome.message += " Overlap with existing data: " + "; ".join(f.note() for f in found) + "."
                    except QmapError as exc:
                        outcome = FileOutcome(path, "failed", OUTCOMES["failed"], plain(exc))
                    except Exception as exc:  # keep going with the other files, and say what happened
                        logger.exception("Unexpected problem with %s", path)
                        outcome = FileOutcome(path, "failed", OUTCOMES["failed"],
                                              f"Unexpected problem ({type(exc).__name__}): {exc}")
                    summary.outcomes.append(outcome)
                    self.emit({"type": "file_done", "index": i, "total": len(self.files), "outcome": outcome})
                summary.overlap_report = write_overlap_report(run, summary.overlaps)
                if summary.overlap_report:
                    self.emit({"type": "log", "text": f"Overlap report: {summary.overlap_report}"})
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
