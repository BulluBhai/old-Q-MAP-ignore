"""Database Manager logic for the Sources screen (no tkinter): folder sources, scanning, results and answers.

Everything is done by the Foundation (`qmap.data_engine.discovery`), inside a normal Q-MAP run, so a scan gets a Run
ID, a log, a manifest and crash recovery like any load. This module only turns results into plain words and rows.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from qmap.catalog import fmt_date
from qmap.core.config import Settings
from qmap.core.errors import QmapError
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap.data_engine.profiles import ALLOWED_TIMEFRAMES
from qmap.storage.db import open_database

from .common import EmitHandler as _EmitHandler
from .services import plain

ATTENTION = ("needs_answer", "rejected", "blocked", "unsupported", "failed", "missing")
COMMON_ZONES = ("Asia/Kolkata", "UTC", "America/New_York", "Europe/London", "Asia/Singapore")
TIMEFRAMES = ALLOWED_TIMEFRAMES
SourceError = D.SourceError


def _with_db(settings: Settings, fn):
    db = open_database(settings.db_path)
    try:
        return fn(db)
    finally:
        db.close()


# ---- sources ---------------------------------------------------------------------------------------------------
def sources(settings: Settings) -> list[D.FolderSource]:
    return _with_db(settings, D.list_sources)


def source_row(s: D.FolderSource) -> tuple:
    return (s.label, s.location, s.market_timezone or "(ask)", s.default_exchange or "-",
            "yes" if s.symbol_from_filename else "no", "yes" if s.include_subfolders else "no")


def add_source(settings: Settings, folder: str, **options) -> D.FolderSource:
    return _with_db(settings, lambda db: D.add_folder_source(settings, db, folder, **options))


def update_source(settings: Settings, source_id: int, **changes) -> D.FolderSource:
    return _with_db(settings, lambda db: D.update_folder_source(db, source_id, **changes))


def remove_source(settings: Settings, source_id: int) -> None:
    _with_db(settings, lambda db: D.remove_folder_source(db, source_id))


def parse_patterns(text: str) -> list[str]:
    return [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]


# ---- files ----------------------------------------------------------------------------------------------------------
def files(settings: Settings, source_id: int, *, attention_only: bool = False) -> list[D.FileState]:
    states = _with_db(settings, lambda db: D.file_states(db, source_id))
    return [s for s in states if not attention_only or s.outcome in ATTENTION]


def file_row(s: D.FileState) -> tuple:
    ds = ", ".join(str(i) for i in s.dataset_ids) or "-"
    return (s.relative_path, s.outcome_label, s.change, ds, fmt_date(s.observed_at[:10]), (s.detail or "")[:160])


def file_details(s: D.FileState) -> list[tuple[str, str | None]]:
    """Plain-English description of one file's current state, as (text, tag) parts."""
    tag = {"imported": "ok", "reused": "ok", "needs_answer": "warning", "missing": "warning"}.get(s.outcome, "error")
    if s.outcome == "ignored":
        tag = "muted"
    parts = [(f"{s.relative_path}\n", "bold"), (f"{s.outcome_label}", tag),
             (f"   (last looked at {fmt_date(s.observed_at[:10])}; {s.change})\n", "muted")]
    if s.detail:
        parts.append((f"{s.detail}\n", None))
    if s.dataset_ids:
        parts.append((f"Dataset(s): {', '.join(map(str, s.dataset_ids))} - see Datasets and Storage.\n", None))
    for q in s.questions:
        parts.append((f"QUESTION: {q['text']}\n", "warning"))
        if q.get("options") and q["key"] != "timeframe":
            parts.append(("  Choices: " + ", ".join(describe_option(o) for o in q["options"]) + "\n", "muted"))
    ev = s.interpretation.get("evidence") or []
    if ev:
        parts.append(("How Q-MAP read the file:\n", "bold"))
        parts += [(f"  {line}\n", "muted") for line in ev]
    return parts


def describe_option(cid: str) -> str:
    """'format:%d-%m-%y %H:%M' -> 'DD-MM-YY HH:MM'."""
    if cid.startswith("format:"):
        text = cid[7:]
        for a, b in (("%d", "DD"), ("%m", "MM"), ("%Y", "YYYY"), ("%y", "YY"), ("%b", "Mon"), ("%H", "HH"), ("%M", "MM"),
                     ("%S", "SS")):
            text = text.replace(a, b)
        return text
    return {"iso": "ISO (YYYY-MM-DD...)", "unix_s": "Unix seconds", "unix_ms": "Unix milliseconds",
            "excel_serial": "Excel day numbers"}.get(cid, cid)


def question_keys(s: D.FileState) -> set[str]:
    return {q["key"] for q in s.questions}


def date_options(s: D.FileState) -> list[tuple[str, str]]:
    """[(label, option id)] for the date-layout question, if any."""
    q = next((q for q in s.questions if q["key"] == "date_format"), None)
    return [(describe_option(o), o) for o in (q["options"] if q else [])]


def save_answer(settings: Settings, source_id: int, relative_path: str, answers: dict) -> None:
    _with_db(settings, lambda db: D.record_answer(db, source_id, relative_path, answers))


def counts_text(states: list[D.FileState]) -> str:
    c: dict = {}
    for s in states:
        c[s.outcome_label] = c.get(s.outcome_label, 0) + 1
    return ", ".join(f"{n} {k.lower()}" for k, n in sorted(c.items())) or "no files scanned yet"


# ---- scanning (worker thread; events only) ------------------------------------------------------------------------
@dataclass
class ScanSummary:
    run_id: str | None = None
    run_dir: Path | None = None
    report_path: Path | None = None
    summary: str = ""
    counts: dict = field(default_factory=dict)
    error: str | None = None


class ScanJob:
    """Scans one folder source inside ONE Q-MAP run and reports progress as events. No widgets here."""

    def __init__(self, settings: Settings, source_id: int, emit: Callable[[dict], None] = lambda event: None):
        self.settings, self.source_id, self.emit = settings, source_id, emit
        self._cancel = threading.Event()

    def cancel(self) -> None:  # a scan finishes the file it is on; it is short, so it is not interrupted mid-way
        self._cancel.set()

    def run(self) -> ScanSummary:
        out = ScanSummary()
        handler = _EmitHandler(self.emit)
        logger = logging.getLogger("qmap")
        logger.addHandler(handler)
        db = None
        try:
            self.emit({"type": "stage", "text": "Opening the Q-MAP registry and starting a run"})
            db = open_database(self.settings.db_path)
            with run_context(self.settings, db, D.MODULE_CODE, area=D.AREA, module_name=D.MODULE_NAME,
                             params={"command": "scan", "source_id": self.source_id}) as run:
                out.run_id, out.run_dir = run.run_id, run.dir
                self.emit({"type": "run_started", "run_id": run.run_id, "run_dir": str(run.dir),
                           "started": datetime.now(timezone.utc).astimezone().isoformat()})
                self.emit({"type": "stage", "text": "Scanning the folder"})

                def progress(done, total, rel):
                    self.emit({"type": "progress", "done": done, "total": total, "label": rel})

                res = D.scan_source(run, self.source_id, progress=progress)
                out.report_path, out.summary, out.counts = res.report_path, res.summary(), dict(res.counts)
                for rel, change, action, outcome, detail in res.files:
                    self.emit({"type": "file", "label": rel, "outcome": outcome,
                               "text": f"{D.OUTCOME_LABELS.get(outcome, outcome):<28} {rel}: {detail[:200]}"})
        except QmapError as exc:
            out.error = plain(exc)
        except Exception as exc:
            logger.exception("Scan failed")
            out.error = f"Unexpected problem ({type(exc).__name__}): {exc}"
        finally:
            logger.removeHandler(handler)
            if db is not None:
                db.close()
            self.emit({"type": "done", "summary": out})
        return out
