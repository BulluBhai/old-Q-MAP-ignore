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

from qmap.catalog import fmt_date, get_dataset, timeframe_label
from qmap.data_engine import user_decisions as UD
from qmap.data_engine.instrument_names import add_aliases, registry_path
from qmap.core.config import Settings
from qmap.core.errors import QmapError
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap.data_engine.profiles import ALLOWED_TIMEFRAMES
from qmap.storage.db import open_database

from .common import EmitHandler as _EmitHandler
from .services import plain  # also used by the Sources screen (errors without their technical code)

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


def _inference(s: D.FileState) -> dict:
    return (s.interpretation.get("decisions") or {}).get("timeframe_inference") or {}


def detected_timeframe(s: D.FileState) -> str:
    inf = _inference(s)
    tf = inf.get("timeframe") or (s.interpretation.get("decisions") or {}).get("timeframe")
    return timeframe_label(tf) if tf else "-"


def identity_text(s: D.FileState) -> str:
    """The identity Q-MAP used for the file, and how ("NSE:RELIANCE (alias)")."""
    ident = (s.interpretation.get("decisions") or {}).get("identification") or {}
    ov = s.interpretation.get("overrides") or {}
    match = ident.get("match") or {}
    sym = ov.get("symbol") or match.get("symbol") or ""
    exch = ov.get("exchange") or ""
    if not sym and not exch:
        return "-"
    how = {"canonical": "registry", "alias": "alias", "pattern": "file name", "provisional": "provisional",
           "ambiguous": "ambiguous"}.get(match.get("status"), "")
    return f"{exch}:{sym}" + (f" ({how})" if how else "")


def file_row(s: D.FileState, decisions: dict | None = None) -> tuple:
    ds = ", ".join(str(i) for i in s.dataset_ids) or "-"
    result = s.outcome_label
    if decisions and s.dataset_ids and all(decisions.get(i) == "rejected" for i in s.dataset_ids):
        result = "Rejected by you"
    return (s.relative_path, result, detected_timeframe(s), identity_text(s), s.change, ds,
            (s.detail or "")[:160])


def file_details(s: D.FileState, decisions: dict | None = None) -> list[tuple[str, str | None]]:
    """Plain-English description of one file's current state, as (text, tag) parts."""
    tag = {"imported": "ok", "reused": "ok", "needs_answer": "warning", "missing": "warning"}.get(s.outcome, "error")
    if s.outcome == "ignored":
        tag = "muted"
    parts = [(f"{s.relative_path}\n", "bold"), (f"{s.outcome_label}", tag),
             (f"   (last looked at {fmt_date(s.observed_at[:10])}; {s.change})\n", "muted")]
    inf = _inference(s)
    if inf:  # DQ-7 section 3.6: detected timeframe, sampled blocks, validation, discrepancy, acceptance status
        rejected = bool(decisions and s.dataset_ids and all(decisions.get(i) == "rejected" for i in s.dataset_ids))
        status = ("Rejected by you (reversible: Restore)" if rejected else
                  "Accepted by default" if s.outcome in ("imported", "reused") else s.outcome_label)
        parts.append((f"Detected timeframe: {detected_timeframe(s)}\n", "bold"))
        parts.append((f"Validation: {inf.get('summary')} ({inf.get('rows_examined')} of {inf.get('rows_total')} rows "
                      f"examined)\n", "warning" if inf.get("status") != "consistent" else None))
        name_tf = [w for w in s.interpretation.get("warnings", []) if "file name says" in w]
        if name_tf:
            parts.append((f"File name: {name_tf[0]}\n", "warning"))
        parts.append((f"Status: {status}\n", "error" if rejected else "ok" if status.startswith("Accepted") else None))
    if identity_text(s) != "-":
        parts.append((f"Instrument: {identity_text(s)}\n", None))
    for w in s.interpretation.get("warnings", []):
        if "file name says" not in w:
            parts.append((f"WARNING: {w}\n", "warning"))
    if s.detail:
        parts.append((f"{s.detail}\n", None))
    if s.dataset_ids:
        parts.append((f"Dataset(s): {', '.join(map(str, s.dataset_ids))} - see Datasets and Storage.\n", None))
    for q in s.questions:
        parts.append((f"QUESTION: {q['text']}\n", "warning"))
        if q.get("options") and q["key"] not in ("timeframe", "identity"):  # these are filled into the boxes
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


def suggested_answers(s: D.FileState) -> tuple[str, str, str]:
    """(exchange, symbol, timeframe) to fill into the answer boxes: the exchange Q-MAP already has (the folder's default
    exchange or the file name), the file name's symbol suggestion, and the timeframe when the question offers exactly
    one choice. Nothing is saved until the user presses Save answer."""
    exch = sym = tf = ""
    known = (s.interpretation.get("decisions") or {}).get("identity") or {}
    for q in s.questions:
        opts = q.get("options") or []
        if q["key"] == "identity":
            exch = str(known.get("exchange") or "")
            if len(opts) == 1:
                sym = str(opts[0])
        if q["key"] == "timeframe" and len(opts) == 1 and opts[0] in TIMEFRAMES:
            tf = str(opts[0])
    return exch, sym, tf


def date_options(s: D.FileState) -> list[tuple[str, str]]:
    """[(label, option id)] for the date-layout question, or, for a file read without a question, the other layouts
    that also fit its dates (so an assumed day-first reading can be corrected)."""
    q = next((q for q in s.questions if q["key"] == "date_format"), None)
    options = q["options"] if q else (s.interpretation.get("decisions") or {}).get("date_layouts") or []
    return [(describe_option(o), o) for o in options]


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
    stopped: bool = False
    not_processed: list = field(default_factory=list)
    overlap_report: Path | None = None
    identification_report: Path | None = None


class ScanJob:
    """Scans one folder source inside ONE Q-MAP run and reports progress as events. No widgets here."""

    def __init__(self, settings: Settings, source_id: int, emit: Callable[[dict], None] = lambda event: None):
        self.settings, self.source_id, self.emit = settings, source_id, emit
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Stop: the file being processed is finished (never left half-written), then the scan stops."""
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

                res = D.scan_source(run, self.source_id, progress=progress, should_stop=self._cancel.is_set)
                out.stopped, out.not_processed = res.stopped, list(res.not_processed)
                out.overlap_report, out.identification_report = res.overlap_report_path, res.identification_report_path
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


# ---- consolidated exceptions and bulk actions (DQ-7..DQ-10 section 7) ---------------------------------------------
EXCEPTION_ORDER = ("needs_answer", "rejected_data", "mixed_intervals", "interval_change", "interval_uncertain", "timeframe_name", "conflicts_within",
                   "conflicts_between", "provisional", "ambiguous", "name_column_disagreement", "crypto_venue_unknown",
                   "date_layout_assumed", "timezone_assumed", "rejected_by_you")
EXCEPTION_LABELS = {
    "needs_answer": "Needs your answer", "rejected_data": "Not loaded: data errors",
    "mixed_intervals": "Mixed bar intervals (kept as MIXED)",
    "interval_change": "A section of the file has another bar interval (found by the full-file check)",
    "interval_uncertain": "A section may have another bar interval or regularly missing bars (full-file check)", "timeframe_name": "File name timeframe differs from the data",
    "conflicts_within": "Conflicting observations inside the file (kept, not resolved)",
    "conflicts_between": "Bars differ from another dataset (both kept)",
    "provisional": "Instrument not in the alias registry (provisional)", "ambiguous": "Ambiguous instrument name",
    "name_column_disagreement": "File name and file columns disagree (column used)",
    "crypto_venue_unknown": "Cryptocurrency: trading venue unknown",
    "date_layout_assumed": "Day/month order assumed day-first", "timezone_assumed": "Time zone assumed Asia/Kolkata",
    "rejected_by_you": "Rejected by you"}


def exception_groups(settings: Settings, source_id: int) -> list[dict]:
    """Every material exception of the folder's current files, GROUPED (one line per kind, with the files), so a
    folder of hundreds of files is reviewed in one place instead of file by file."""
    def build(db):
        states = [s for s in D.file_states(db, source_id) if s.outcome not in ("missing", "ignored")]
        groups: dict = {}

        def add(kind, st, note=""):
            g = groups.setdefault(kind, {"kind": kind, "label": EXCEPTION_LABELS[kind], "files": [], "notes": []})
            g["files"].append(st.relative_path)
            if note and len(g["notes"]) < 3:
                g["notes"].append(note)

        for st in states:
            dec = st.interpretation.get("decisions") or {}
            ident = dec.get("identification") or {}
            if st.outcome == "needs_answer":
                add("needs_answer", st, (st.detail or "")[:120])
            if st.outcome in ("rejected", "blocked", "failed"):
                add("rejected_data", st, (st.detail or "")[:120])
            if (dec.get("timeframe_inference") or {}).get("status") == "mixed":
                add("mixed_intervals", st, dec["timeframe_inference"].get("summary", ""))
            if any("file name says" in w and "data are" in w for w in st.interpretation.get("warnings", [])):
                add("timeframe_name", st)
            if ident.get("exception"):
                add(ident["exception"], st, (ident.get("match") or {}).get("method", ""))
            for flag in ("date_layout_assumed", "timezone_assumed"):
                if dec.get(flag):
                    add(flag, st)
            for ds in st.dataset_ids:
                info = get_dataset(db, ds)
                if info is None:
                    continue
                if info.rejected_by_user:
                    add("rejected_by_you", st)
                if any(w.startswith("conflicting_observations") for w in info.warnings):
                    add("conflicts_within", st)
                if any(w.startswith("conflicts_with_existing_dataset") for w in info.warnings):
                    add("conflicts_between", st)
                if any(w.startswith("interval_change_detected") for w in info.warnings):
                    add("interval_change", st)
                if any(w.startswith("interval_change_uncertain") for w in info.warnings):
                    add("interval_uncertain", st)
        return [groups[k] for k in EXCEPTION_ORDER if k in groups]
    return _with_db(settings, build)


def exceptions_text(groups: list[dict]) -> list[tuple[str, str | None]]:
    if not groups:
        return [("No exceptions: every file was read and accepted without warnings.\n", "ok")]
    total = sum(len(g["files"]) for g in groups)
    parts = [(f"{len(groups)} kind(s) of exception, {total} file mention(s). Routine files are not listed.\n", "bold")]
    for g in groups:
        shown = ", ".join(g["files"][:6]) + (f" (+{len(g['files']) - 6} more)" if len(g["files"]) > 6 else "")
        parts.append((f"{g['label']}: {len(g['files'])} file(s)\n", "warning"))
        parts.append((f"    {shown}\n", "muted"))
    return parts


def dataset_decisions(settings: Settings, dataset_ids) -> dict:
    return _with_db(settings, lambda db: {i: UD.current_decision(db, i) for i in dataset_ids})


def reject_files(settings: Settings, states: list, reason: str = "") -> UD.DecisionResult:
    """Reject the datasets of the selected files (reversible; nothing is deleted)."""
    ids = [i for s in states for i in s.dataset_ids]
    return _with_db(settings, lambda db: UD.reject_datasets(db, ids, reason=reason, origin="sources"))


def restore_files(settings: Settings, states: list, reason: str = "") -> UD.DecisionResult:
    ids = [i for s in states for i in s.dataset_ids]
    return _with_db(settings, lambda db: UD.restore_datasets(db, ids, reason=reason, origin="sources"))


def correct_files(settings: Settings, source_id: int, states: list, answers: dict) -> int:
    """Bulk correction (exchange, symbol, date layout, time zone, timeframe when unmeasurable): recorded for every
    selected file and applied by the next scan (as new datasets; nothing is changed in place)."""
    def run(db):
        for st in states:
            D.record_answer(db, source_id, st.relative_path, answers)
        return len(states)
    return _with_db(settings, run)


def cleaned_names(states: list) -> list[str]:
    out = []
    for st in states:
        ident = (st.interpretation.get("decisions") or {}).get("identification") or {}
        name = (ident.get("cleaned") or {}).get("cleaned")
        if name and name not in out:
            out.append(name)
    return out


def add_to_alias_registry(settings: Settings, canonical: str, aliases: list[str]) -> Path:
    """Reusable correction: add the selected files' cleaned names as aliases of `canonical` (backup kept, change
    recorded in its own run). The next scan identifies those files, and future files with these names, again."""
    canonical = canonical.strip()
    if not canonical:
        raise ValueError("Type the canonical instrument name first.")
    db = open_database(settings.db_path)
    try:
        with run_context(settings, db, "ALIAS", area="Data_Management", module_name="Alias registry",
                         params={"canonical": canonical, "aliases": aliases}) as run:
            return add_aliases(run, [(canonical, a) for a in aliases] or [(canonical, "")])
    finally:
        db.close()


def alias_registry_file(settings: Settings) -> Path:
    return registry_path(settings)
