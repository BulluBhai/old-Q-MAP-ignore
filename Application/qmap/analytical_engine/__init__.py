"""Analytical engine: analyses that READ prepared, registered datasets. It never imports source files.

`ANALYSES` lists only analyses that genuinely run. Planned research modules (MIQP Market Intelligence, QLOPB MA
Research, CPR/pivots, Ichimoku, Stage Analysis ...) are listed by the Analytical Workbench as planned and are added
here only once their rules, parameters, outputs and validation criteria are approved.
"""

from .base import (AVAILABLE, INVALID_INPUT, NO_ELIGIBLE_DATA, NOT_READY, OUTPUT_AREA, PLANNED, READY,
                   AnalysisReadiness, AnalysisRunResult, AnalysisSpec, Parameter, check_analysis, run_analysis)
from .dataset_summary import SPEC as DATASET_SUMMARY

ANALYSES = {spec.analysis_id: spec for spec in (DATASET_SUMMARY,)}


def latest_completed_run(settings, db):
    """The ONE definition of "the latest completed analysis run": the most recently finished run of any analysis in
    ANALYSES whose status is 'completed'. Returns (run_id, folder) using the folder RECORDED for that run (relative to
    Q-MAP_OUTPUT), or None. Failed and refused requests never count (a refused request creates no run at all)."""
    prefixes = sorted({spec.run_prefix for spec in ANALYSES.values()})
    row = db.one(f"SELECT run_id, output_path FROM runs WHERE status = 'completed' AND module_code IN "
                 f"({', '.join('?' * len(prefixes))}) AND output_path IS NOT NULL "
                 "ORDER BY finished_at DESC, run_id DESC LIMIT 1", prefixes)
    if row is None:
        return None
    return row["run_id"], settings.output_root.joinpath(*row["output_path"].split("/"))


__all__ = ["ANALYSES", "AVAILABLE", "DATASET_SUMMARY", "INVALID_INPUT", "NO_ELIGIBLE_DATA", "NOT_READY", "OUTPUT_AREA",
           "PLANNED", "READY", "AnalysisReadiness", "AnalysisRunResult", "AnalysisSpec", "Parameter", "check_analysis",
           "latest_completed_run", "run_analysis"]
