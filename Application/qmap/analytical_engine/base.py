"""How every analysis is described, checked and run, so that each run is reproducible.

An analysis declares what it is (`AnalysisSpec`): identifier, version, the data it needs (`DataRequirement`), its
parameters and how many datasets it takes. `run_analysis` then always does the same things in the same order:

1. check the parameters and the readiness of every selected dataset - nothing starts if anything is missing;
2. reserve a unique Run ID and a run folder in Q-MAP_OUTPUT/Research_Reports (never overwriting an earlier run);
3. record the input datasets in the registry (`run_inputs`);
4. execute the analysis, which writes its outputs only inside the run folder;
5. write `Run_Metadata_<dd_mmm_yy_hhmmss>.json` (analysis and code versions, parameters, every input dataset with
   its checksum, processing version, settings fingerprint and lineage, readiness warnings, outputs) and close the run
   with its manifest.

The analytical engine only READS prepared, registered data. It never imports, standardises or registers source files;
when data are missing it says what to prepare in Database Manager.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from .. import CLEANING_CODE_VERSION, __version__
from ..catalog import DataRequirement, ReadinessReport, check_readiness, get_dataset, provenance
from ..core.build import current_build
from ..core.config import Settings
from ..core.dates import DateInputError, format_long, parse_user_date
from ..core.errors import RunCancelled
from ..core.runs import run_context
from ..storage.db import Database
from ..storage.files import atomic_write_bytes

OUTPUT_AREA = "Research_Reports"
AVAILABLE, PLANNED = "available", "planned"


def file_stamp(moment: datetime | None = None) -> str:
    """dd_mmm_yy_hhmmss suffix for output file names (local time of the person running it)."""
    return (moment or datetime.now()).strftime("%d_%b_%y_%H%M%S")


@dataclass(frozen=True)
class Parameter:
    key: str
    label: str
    kind: str  # date | int
    required: bool = False
    default: object = None
    help: str = ""
    minimum: int | None = None


@dataclass
class RunContext:
    """What an executing analysis may use."""

    settings: Settings
    db: Database
    run_id: str
    run_dir: Path
    dataset_ids: list[int]
    params: dict
    stamp: str
    log: Callable[[str], None]
    readiness_warnings: list[str] = field(default_factory=list)  # shown to the user before the run (NOTE lines)
    # what the analysis actually used (for example the bars and the in-sample/out-of-sample split); recorded in
    # Run_Metadata under "analysis_details" (beta provenance, 09-Nov-26)
    details: dict = field(default_factory=dict)
    # progress(done, total, text): how far the calculation is (for the Workbench's counter and ETA); optional
    progress: Callable[[int, int, str], None] = field(default=lambda done, total, text: None)
    # cancel_requested() -> True when the person pressed Cancel or closed the window; long analyses check it
    cancel_requested: Callable[[], bool] = field(default=lambda: False)

    def output(self, name: str) -> Path:
        return self.run_dir / name

    def stop_if_cancelled(self) -> None:
        if self.cancel_requested():
            raise RunCancelled("Cancelled by the user.")


@dataclass
class AnalysisSpec:
    analysis_id: str
    name: str
    version: int
    description: str
    run_prefix: str  # Run ID prefix, e.g. DSUM -> DSUM_20261101_101500
    requirement: DataRequirement
    execute: Callable[[RunContext], list[Path]]
    parameters: tuple[Parameter, ...] = ()
    min_datasets: int = 1
    max_datasets: int = 50
    kind_note: str = ""  # what kind of result this is, shown to the user (e.g. "descriptive statistics only")
    # Optional, analysis-specific: (parsed params) -> (cleaned params, problems). Runs after the per-parameter parsing.
    check_params: Callable[[dict], tuple[dict, list[str]]] | None = None
    # Optional, analysis-specific readiness items for ONE dataset that passed the shared checks:
    # (settings, db, dataset_id, cleaned params, report) -> None; adds items to the report with report.add(...).
    dataset_checks: Callable[[Settings, Database, int, dict, ReadinessReport], None] | None = None
    method_source: str = ""  # where the method comes from (recorded in Run_Metadata)
    # output-name prefixes of the RESULT TABLES: the files that must be identical when a run is reproduced (charts,
    # PDF and Excel carry the Run ID and the time, so they always differ)
    result_tables: tuple[str, ...] = ()


INVALID_INPUT, NO_ELIGIBLE_DATA, NOT_READY, READY = "invalid_input", "no_eligible_data", "not_ready", "ready"


@dataclass
class AnalysisReadiness:
    """Result of checking one request before anything runs.

    `state` keeps three different situations apart (Workbench requirement 2.4):
      invalid_input     - a date (or other parameter) cannot be understood, or the start is after the end;
      no_eligible_data  - every input and the selection are valid, but NONE of the selected datasets has a bar in the
                          chosen period, and that is the only thing wrong with any of them;
      not_ready         - anything else that stops the run (wrong timeframe, too little history, damaged file ...),
                          including a selection where some datasets have bars in the period and others have none;
      ready             - the analysis may run.
    """

    ready: bool
    problems: list[str] = field(default_factory=list)  # every input and selection problem (kept for callers)
    reports: list[ReadinessReport] = field(default_factory=list)
    params: dict = field(default_factory=dict)  # cleaned parameter values
    input_problems: list[str] = field(default_factory=list)  # dates / parameters
    selection_problems: list[str] = field(default_factory=list)  # number of datasets
    parameter_problems: list[str] = field(default_factory=list)  # analysis-specific (not date) parameters; also in input_problems

    @property
    def warnings(self) -> list[str]:
        return [f"{r.label}: {w.detail}" for r in self.reports for w in r.warnings]

    @property
    def state(self) -> str:
        if self.input_problems:
            return INVALID_INPUT
        if self.ready:
            return READY
        # "No data in this period" describes the whole selection: every selected dataset must be empty in the period
        # and that must be its only failure. One dataset with bars (ready or not) makes the request NOT READY.
        if not self.selection_problems and self.reports and all(
                r.no_eligible_bars and all(f.name == "history" for f in r.failures) for r in self.reports):
            return NO_ELIGIBLE_DATA
        return NOT_READY

    @property
    def datasets_without_bars(self) -> list[ReadinessReport]:
        """Selected datasets that have no bar at all in the chosen (valid) period."""
        return [r for r in self.reports if r.no_eligible_bars]

    @property
    def partial_period_note(self) -> str:
        """For a NOT READY request where only part of the selection is empty in the period: what that means."""
        empty = self.datasets_without_bars
        if self.state != NOT_READY or not empty or len(empty) == len(self.reports):
            return ""
        names = ", ".join(r.label for r in empty)
        return (f"{len(empty)} of the {len(self.reports)} selected datasets have no bars in this period ({names}); the "
                "others do. Choose a period that every selected dataset covers, or remove those datasets from the "
                "selection.")


@dataclass
class AnalysisRunResult:
    outcome: str  # completed | blocked | failed | cancelled
    message: str
    run_id: str | None = None
    run_dir: Path | None = None
    outputs: list[Path] = field(default_factory=list)
    metadata_path: Path | None = None
    readiness: AnalysisReadiness | None = None
    reproduction: dict | None = None  # set when this run repeated an earlier one (see reproduce.py)

    @property
    def ok(self) -> bool:
        return self.outcome == "completed"


def _parse_param(p: Parameter, raw) -> tuple[object, str | None]:
    text = "" if raw is None else str(raw).strip()
    if text == "":
        if p.required:
            return None, f"{p.label} is required."
        return p.default, None
    if p.kind == "date":
        try:
            return parse_user_date(raw), None
        except DateInputError as exc:
            return None, f"{p.label}: {exc}"
    if p.kind == "int":
        try:
            value = int(text)
        except ValueError:
            return None, f"{p.label}: '{text}' is not a whole number."
        if p.minimum is not None and value < p.minimum:
            return None, f"{p.label} must be at least {p.minimum}."
        return value, None
    return text, None


def check_analysis(settings: Settings, db: Database, spec: AnalysisSpec, dataset_ids: list[int], raw_params: dict,
                   *, verify_checksum: bool = True) -> AnalysisReadiness:
    """Parameters + selection + readiness of every dataset. Nothing is written."""
    res = AnalysisReadiness(ready=False)
    for p in spec.parameters:
        value, problem = _parse_param(p, raw_params.get(p.key))
        res.params[p.key] = value
        if problem:
            res.input_problems.append(problem)
    start, end = res.params.get("date_from"), res.params.get("date_to")
    if start and end and start > end:
        res.input_problems.append(f"The start date ({format_long(start)}) is after the end date ({format_long(end)}).")
    if spec.check_params is not None and not res.input_problems:
        res.params, extra = spec.check_params(dict(res.params))
        res.input_problems.extend(extra)
        res.parameter_problems.extend(extra)
    ids = list(dict.fromkeys(int(i) for i in dataset_ids))
    if len(ids) < spec.min_datasets:
        res.selection_problems.append(f"Select at least {spec.min_datasets} dataset(s).")
    if len(ids) > spec.max_datasets:
        res.selection_problems.append(f"Select at most {spec.max_datasets} datasets.")
    res.problems = res.input_problems + res.selection_problems
    if res.input_problems:  # the period is unknown, so no dataset can be checked against it
        return res
    req = spec.requirement
    if start or end:
        req = DataRequirement(**{**asdict(req), "date_from": start, "date_to": end})
    for i in ids:
        report = check_readiness(settings, db, i, req, verify_checksum=verify_checksum)
        if spec.dataset_checks is not None and report.ready:
            spec.dataset_checks(settings, db, i, res.params, report)
        res.reports.append(report)
    res.ready = not res.problems and all(r.ready for r in res.reports) and bool(ids)
    return res


def _dataset_record(db: Database, dataset_id: int, report: ReadinessReport) -> dict:
    d = get_dataset(db, dataset_id)
    return {"dataset_id": dataset_id, "instrument": d.instrument, "timeframe": d.timeframe, "layer": d.layer,
            "sha256": d.sha256, "processing_version": d.processing_version, "config_fingerprint": d.config_fingerprint,
            "canonical_schema_version": d.canonical_schema_version, "storage_class": d.storage_class,
            "relative_path": d.relative_path, "date_from": d.date_from, "date_to": d.date_to, "row_count": d.row_count,
            "rows_in_window": report.rows_in_window, "validation_status": d.validation_status,
            "validation_warnings": d.warnings, "source_files": d.source_files, "lineage": provenance(db, dataset_id),
            # which DQ-7 comparison classified the timeframe: corrected / earlier (before 04-Nov-26) / not applicable
            "timeframe_classified_by": {"corrected": "DQ-7 corrected comparison (04-Nov-26)",
                                        "earlier_same": "DQ-7 comparison before the 04-Nov-26 correction; same result",
                                        "earlier_changed": "DQ-7 comparison before the 04-Nov-26 correction; the "
                                                           "corrected comparison would give MIXED"}.get(
                                            d.timeframe_logic, "not a DQ-7 sampling result or not affected")}


def run_analysis(settings: Settings, db: Database, spec: AnalysisSpec, dataset_ids: list[int], raw_params: dict, *,
                 log: Callable[[str], None] | None = None, now: datetime | None = None,
                 reproduce_of: dict | None = None, progress: Callable[[int, int, str], None] | None = None,
                 cancel: Callable[[], bool] | None = None) -> AnalysisRunResult:
    """`reproduce_of` (from qmap.analytical_engine.reproduce): the earlier run this run repeats. Its result tables are
    compared with the new ones and a Reproducibility_Report is written into the new run folder.
    `progress(done, total, text)` receives the analysis's progress; `cancel()` returning True stops a running analysis
    at its next check: the run is then closed as 'cancelled' and the result's outcome is 'cancelled'."""
    say = log or (lambda _m: None)
    say(f"Checking readiness of {len(dataset_ids)} dataset(s) for {spec.name}...")
    # A reproduction is tied to the exact historical dataset recorded by the earlier run. It may therefore
    # use a preserved superseded dataset, but only after reproduce.py has verified the original run's SHA-256.
    # Keep the ordinary AnalysisSpec unchanged: new research runs must continue to reject superseded datasets.
    readiness_spec = (replace(spec, requirement=replace(spec.requirement, allow_superseded=True))
                      if reproduce_of is not None else spec)
    readiness = check_analysis(settings, db, readiness_spec, dataset_ids, raw_params)
    if not readiness.ready:
        reasons = readiness.problems + [f"{r.label}: {f.detail}" for r in readiness.reports for f in r.failures]
        lead = {INVALID_INPUT: "The parameters entered are not valid, so nothing was run:" if readiness.parameter_problems
                else "The dates entered are not valid, so nothing was run:",
                NO_ELIGIBLE_DATA: "The dates are valid, but the selected data have no bars in that period, so nothing "
                                  "was run:"}.get(readiness.state, "The analysis cannot run reliably:")
        if readiness.partial_period_note:
            lead += " " + readiness.partial_period_note
        say("Not started: " + " | ".join(reasons))
        return AnalysisRunResult("blocked", lead + " " + " ".join(reasons), readiness=readiness)
    for w in readiness.warnings:
        say(f"Warning: {w}")
    ids = [r.dataset_id for r in readiness.reports]
    params = {"analysis_id": spec.analysis_id, "analysis_version": spec.version, "dataset_ids": ids,
              "parameters": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in readiness.params.items()}}
    stamp = file_stamp()
    run_id = run_dir = None
    try:
        with run_context(settings, db, spec.run_prefix, area=OUTPUT_AREA, module_name=spec.name, params=params,
                         now=now) as run:
            run_id, run_dir = run.run_id, run.dir
            say(f"Run {run.run_id} started; results go to {run.dir}")
            with db.transaction() as conn:
                conn.executemany("INSERT OR IGNORE INTO run_inputs(run_id, dataset_id) VALUES (?, ?)",
                                 [(run.run_id, i) for i in ids])
            ctx = RunContext(settings, db, run.run_id, run.dir, ids, readiness.params, stamp,
                             lambda m: (run.logger.info(m), say(m)), list(readiness.warnings))
            if progress is not None:
                # one extra final step (reports, run record): the count reaches its total only when the run is done
                reported = {"total": 0}

                def analysis_progress(done: int, total: int, text: str) -> None:
                    reported["total"] = total
                    progress(min(done, total), total + 1, text)
                ctx.progress = analysis_progress
            if cancel is not None:
                ctx.cancel_requested = cancel
            outputs = list(spec.execute(ctx))
            reproduction = None
            if reproduce_of is not None:
                from .reproduce import compare_and_report
                report_path, reproduction = compare_and_report(ctx, spec, reproduce_of, outputs)
                outputs.append(report_path)
            meta = {
                "run_id": run.run_id, "analysis_id": spec.analysis_id, "analysis_name": spec.name,
                "analysis_version": spec.version, "result_kind": spec.kind_note, "method_source": spec.method_source,
                "qmap_version": __version__, "cleaning_code_version": CLEANING_CODE_VERSION, "build": current_build(),
                "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "parameters": params["parameters"], "readiness_warnings": readiness.warnings,
                # exactly what was entered (None = left empty): what a later reproduction runs with again
                "raw_parameters": {p.key: (None if raw_params.get(p.key) is None else str(raw_params.get(p.key)))
                                   for p in spec.parameters},
                "analysis_details": ctx.details,
                "input_datasets": [_dataset_record(db, r.dataset_id, r) for r in readiness.reports],
                "outputs": [p.name for p in outputs],
            }
            if reproduction is not None:
                meta["reproduction"] = reproduction
            meta_path = run.dir / f"Run_Metadata_{stamp}.json"
            atomic_write_bytes(meta_path, json.dumps(meta, indent=2, default=str, sort_keys=True).encode("utf-8"))
            if progress is not None:
                final = reported["total"] + 1
                progress(final, final, "Reports and run record written")
    except RunCancelled:
        say(f"Run {run_id} cancelled by the user; it is recorded as cancelled.")
        return AnalysisRunResult("cancelled", f"Cancelled. Run {run_id} stopped before it finished and is recorded as "
                                 "cancelled; its folder holds only the run log, no results.", run_id, run_dir,
                                 readiness=readiness)
    except Exception as exc:
        say(f"FAILED: {type(exc).__name__}: {exc}")
        return AnalysisRunResult("failed", f"The analysis failed ({type(exc).__name__}: {exc}). The run is recorded as "
                                 "failed; see its log.", run_id, run_dir, readiness=readiness)
    say(f"Run {run_id} completed: {len(outputs)} output file(s).")
    return AnalysisRunResult("completed", f"Completed. Results are in {run_dir}", run_id, run_dir, outputs, meta_path,
                             readiness, reproduction)
