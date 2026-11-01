"""Analytical engine: analyses that READ prepared, registered datasets. It never imports source files.

`ANALYSES` lists only analyses that genuinely run. Planned research modules (MIQP Market Intelligence, QLOPB MA
Research, CPR/pivots, Ichimoku, Stage Analysis ...) are listed by the Analytical Workbench as planned and are added
here only once their rules, parameters, outputs and validation criteria are approved.
"""

from .base import (AVAILABLE, OUTPUT_AREA, PLANNED, AnalysisReadiness, AnalysisRunResult, AnalysisSpec, Parameter,
                   check_analysis, run_analysis)
from .dataset_summary import SPEC as DATASET_SUMMARY

ANALYSES = {spec.analysis_id: spec for spec in (DATASET_SUMMARY,)}

__all__ = ["ANALYSES", "AVAILABLE", "OUTPUT_AREA", "PLANNED", "AnalysisReadiness", "AnalysisRunResult", "AnalysisSpec",
           "Parameter", "check_analysis", "run_analysis", "DATASET_SUMMARY"]
