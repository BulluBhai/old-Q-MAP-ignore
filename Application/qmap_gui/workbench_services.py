"""Analytical Workbench logic (no tkinter). It only READS prepared, registered data.

This module must never import ingestion, profile, registration or storage-changing code: the Workbench does not
prepare data. When data are missing it tells the user what to prepare in Database Manager (a test enforces this).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from qmap.analytical_engine import ANALYSES, OUTPUT_AREA, AnalysisReadiness, AnalysisRunResult, check_analysis, run_analysis
from qmap.catalog import FAIL, PASS, WARN, DatasetInfo, fmt_date, list_datasets
from qmap.core.config import Settings
from qmap.storage.db import open_database

from .common import EmitHandler as _EmitHandler

PREPARE_HINT = ("Prepare the data in Database Manager (open database_manager.py): load the files, check the "
                "results, and derive weekly or monthly data there if needed.")


@dataclass
class AnalysisChoice:
    analysis_id: str
    name: str
    description: str
    kind_note: str
    timeframes: tuple
    parameters: tuple


def analyses() -> list[AnalysisChoice]:
    return [AnalysisChoice(s.analysis_id, s.name, s.description, s.kind_note, s.requirement.timeframes, s.parameters)
            for s in ANALYSES.values()]


def output_folder(settings: Settings) -> Path:
    return settings.output_root / OUTPUT_AREA


def ready_datasets(settings: Settings, *, include_superseded: bool = False, timeframe: str = "") -> list[DatasetInfo]:
    """Datasets whose file exists (deleted ones are never offered)."""
    db = open_database(settings.db_path)
    try:
        return list_datasets(db, include_superseded=include_superseded, include_deleted=False,
                             timeframes=(timeframe,) if timeframe else None)
    finally:
        db.close()


def row_values(d: DatasetInfo) -> tuple:
    return (d.dataset_id, d.instrument, d.timeframe_label, d.row_count or 0, fmt_date(d.date_from), fmt_date(d.date_to),
            "Passed with warnings" if d.warnings else "Passed", d.storage_label, d.state_label)


def check(settings: Settings, analysis_id: str, dataset_ids: list[int], params: dict) -> AnalysisReadiness:
    db = open_database(settings.db_path)
    try:
        return check_analysis(settings, db, ANALYSES[analysis_id], dataset_ids, params)
    finally:
        db.close()


def readiness_parts(res: AnalysisReadiness) -> list[tuple[str, str | None]]:
    """The readiness result as (text, tag) parts: green pass, orange warning, red failure."""
    tag = {PASS: "ok", WARN: "warning", FAIL: "error"}
    parts: list[tuple[str, str | None]] = []
    if res.ready:
        parts.append(("READY - every requirement is met." + (" Read the warnings below." if res.warnings else "")
                      + "\n", "ok"))
    else:
        parts.append(("NOT READY - the analysis cannot run reliably yet:\n", "error"))
        parts += [(f"  - {p}\n", "error") for p in res.problems]
        if any(not r.ready for r in res.reports):
            parts.append((f"  {PREPARE_HINT}\n", "muted"))
    for r in res.reports:
        parts.append((f"\n{r.label}: {'ready' if r.ready else 'not ready'}\n", "bold"))
        for item in r.items:
            mark = {PASS: "OK  ", WARN: "NOTE", FAIL: "FAIL"}[item.status]
            parts.append((f"  {mark} {item.detail}\n", tag[item.status] if item.status != PASS else None))
    return parts


@dataclass
class AnalysisJob:
    settings: Settings
    analysis_id: str
    dataset_ids: list[int]
    params: dict
    emit: Callable[[dict], None] = field(default=lambda event: None)

    def run(self) -> AnalysisRunResult:
        handler = _EmitHandler(self.emit)
        logger = logging.getLogger("qmap")
        logger.addHandler(handler)
        db = None
        try:
            self.emit({"type": "stage", "text": "Checking readiness and starting the run"})
            db = open_database(self.settings.db_path)
            result = run_analysis(self.settings, db, ANALYSES[self.analysis_id], self.dataset_ids, self.params,
                                  log=lambda m: self.emit({"type": "progress", "text": m}))
        except Exception as exc:
            result = AnalysisRunResult("failed", f"Unexpected problem ({type(exc).__name__}): {exc}")
        finally:
            logger.removeHandler(handler)
            if db is not None:
                db.close()
        self.emit({"type": "done", "result": result})
        return result
