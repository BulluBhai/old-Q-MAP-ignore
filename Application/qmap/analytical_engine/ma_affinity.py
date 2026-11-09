"""MA Affinity (analysis `ma_affinity`, version 1): QLOPB's MA Affinity Scanner V2 run on a registered Q-MAP dataset.

The calculation is QLOPB's, unchanged (`qlopb.core.research_engine.run_ma_affinity`; Application/qlopb). This module only:
  1. turns the Workbench's typed parameters into QLOPB settings with QLOPB's own parser and checks
     (`qlopb.gui.research_controls.parse_settings`, which also applies safeguard S-2 on the weights);
  2. adds the readiness items agreed by the Project Owner on 03-Nov-26 (decision 4) on top of Q-MAP's shared checks;
  3. reads the registered dataset (never a source file) and passes its bars to the engine with timeframe "as_loaded",
     so the engine never aggregates: weekly/monthly research uses Q-MAP's registered derived datasets (decision 3);
  4. writes QLOPB's Excel, PDF and PNG reports plus two CSV tables into the run folder.

Timeframes: daily, weekly and monthly registered datasets. Q-MAP's weekly/monthly bars were shown to equal QLOPB's
own aggregation, and to give identical MA Affinity results (Tests/integration/test_ma_affinity_timeframe_equivalence.py).
Intraday and quarterly datasets are not offered in v0.1 (not part of the approved scope).

Eligibility (decision 4; existing DQ classifications are only READ, never changed):
  FAIL  rows flagged `conflicting_observation` in the chosen period (DQ-10: same time, different values, unresolved),
        including weekly/monthly bars built from such days - MA Affinity needs exactly one bar per time;
  FAIL  MIXED timeframe (shared readiness rule);
  FAIL  data too short for the chosen settings, or non-finite prices (QLOPB's own checks, safeguard S-1);
  WARN  overlap/conflict with ANOTHER dataset, uncertain interval findings, gaps, edge periods (shared checks);
  PASS  exact duplicates removed at load (DQ-10): they are not in the dataset.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, replace
from xml.sax.saxutils import escape
from pathlib import Path

import numpy as np

import qlopb
from qlopb.config import settings as qcfg

from ..catalog import DataRequirement, FAIL, PASS, WARN, fmt_date, get_dataset, provenance, read_dataset
from ..core.build import build_label, current_build
from ..data_engine import canonical as C
from .base import AnalysisSpec, Parameter, RunContext

TIMEFRAMES = ("1D", "1W", "1M")
_D = qcfg.MAResearchSettings()
METHOD_SOURCE = (f"{qlopb.METHOD_NAME}, {qlopb.SOURCE_REPOSITORY} commit {qlopb.SOURCE_COMMIT[:7]} "
                 "(safeguards S-1..S-3); calculations unchanged")

# (key used by QLOPB's parser, label, default text, help)
_FIELDS = (
    ("ma_types", "MA types", ",".join(_D.ma_types), "One or more of " + ", ".join(qcfg.ALL_MA_TYPES) + ", separated by commas."),
    ("ma_start", "MA start", str(_D.ma_start), "Shortest MA period tested."),
    ("ma_end", "MA end", str(_D.ma_end), "Longest MA period tested."),
    ("proximity_pct", "Proximity %", str(_D.proximity_pct), "A bar is in the zone when it comes within this % of the MA."),
    ("cooldown_bars", "Cooldown bars", str(_D.cooldown_bars), "Minimum bars between two recorded interactions."),
    ("fwd_windows", "Forward windows", ",".join(map(str, _D.fwd_windows)), "Bars ahead, comma separated; the FIRST is the primary window."),
    ("min_interactions", "Min interactions", str(_D.min_interactions), "In-sample interactions needed before a candidate is ranked."),
    ("is_pct", "IS split %", str(_D.is_pct), "Share of bars used in-sample (ranking); the rest is out-of-sample."),
    ("regime_ma", "Regime MA", str(_D.regime_ma), "SMA period used to label the market regime of each interaction."),
    ("top_n", "Top-N", str(_D.top_n), "Number of in-sample leaders frozen before out-of-sample evaluation."),
    ("w_interaction", "Wt: strength", str(_D.weight_interaction_strength), "Affinity weight: interaction strength (weights are divided by their sum)."),
    ("w_success", "Wt: success", str(_D.weight_success_rate), "Affinity weight: success rate."),
    ("w_forward", "Wt: fwd return", str(_D.weight_forward_return), "Affinity weight: forward return (Directed IR, pending owner review)."),
    ("w_stability", "Wt: stability", str(_D.weight_stability), "Affinity weight: stability."),
    ("oos_scope", "OOS scope", _D.oos_scope, "top_n = out-of-sample for the frozen Top-N only (default); all = every candidate (information only)."),
    ("min_oos", "Min OOS outcomes", str(_D.min_oos_outcomes_for_consistency), "Out-of-sample outcomes needed before IS/OOS consistency is shown."),
)
PARAMETERS = (
    Parameter("date_from", "Start date", "date", help="Optional. Empty = from the first bar. Rows before it are not used."),
    Parameter("date_to", "End date", "date", help="Optional. Empty = to the last bar."),
) + tuple(Parameter(k, label, "text", default=default, help=help_) for k, label, default, help_ in _FIELDS)


def check_params(params: dict) -> tuple[dict, list[str]]:
    """QLOPB's own parser and range checks (unchanged); returns the cleaned parameters recorded in Run_Metadata."""
    from qlopb.gui.research_controls import parse_settings

    raw = {k: params.get(k) for k, *_ in _FIELDS}
    names = [t.strip().upper() for t in str(raw["ma_types"] or "").replace(";", ",").split(",") if t.strip()]
    problems = [f"MA types: '{n}' is not one of {', '.join(qcfg.ALL_MA_TYPES)}." for n in names
                if n not in qcfg.ALL_MA_TYPES]
    raw["ma_types"] = tuple(names)
    raw["oos_scope"] = str(raw["oos_scope"] or "").strip().lower()
    cleaned = {"date_from": params.get("date_from"), "date_to": params.get("date_to")}
    try:
        s = parse_settings(raw)  # timeframe is not given, so it stays "as_loaded": the engine never aggregates
    except qcfg.SettingsError as exc:
        problems += [line.lstrip("- ").strip() for line in str(exc).splitlines()[1:] if line.strip()] or [str(exc)]
        return {**cleaned, **{k: params.get(k) for k, *_ in _FIELDS}}, problems
    if problems:
        return {**cleaned, **{k: params.get(k) for k, *_ in _FIELDS}}, problems
    return {**cleaned, "qlopb_settings": asdict(s)}, []


def _settings(params: dict):
    s = qcfg.MAResearchSettings(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in params["qlopb_settings"].items()})
    if s.timeframe != "as_loaded":  # decision 3: never aggregate or substitute a timeframe inside the analysis
        raise ValueError("MA Affinity in Q-MAP always runs on the registered dataset's own timeframe.")
    return s.check()


def _frame(settings, db, dataset_id: int, params: dict):
    import pandas as pd

    t = read_dataset(settings, db, dataset_id, date_from=params.get("date_from"), date_to=params.get("date_to"))
    cols = {k: np.asarray(t.column(k).to_numpy(zero_copy_only=False), dtype=float) for k in ("open", "high", "low", "close")}
    vol = t.column("volume")
    cols["volume"] = np.where(np.asarray(vol.is_valid().to_numpy(zero_copy_only=False), dtype=bool),
                              np.asarray(vol.fill_null(0).to_numpy(zero_copy_only=False), dtype=float), np.nan)
    index = pd.DatetimeIndex(pd.to_datetime(t.column("session_date").to_pylist()), name="datetime")
    return pd.DataFrame(cols, index=index), t


def dataset_checks(settings, db, dataset_id: int, params: dict, report) -> None:
    """Decision 4 items, then QLOPB's own data checks for the chosen settings."""
    info = get_dataset(db, dataset_id)
    frame, table = _frame(settings, db, dataset_id, params)
    flags = np.asarray(table.column("quality_flags").to_numpy(zero_copy_only=False), dtype=np.int64)
    conflicted = (flags & C.FLAG_CONFLICTING_OBSERVATION) != 0
    keys = table.column("timestamp_utc").to_pylist() if "timestamp_utc" in table.column_names else []
    dates = table.column("session_date").to_pylist()
    keys = [k if k is not None else d for k, d in zip(keys or dates, dates)]
    if conflicted.any():
        times = sorted({keys[i] for i in np.flatnonzero(conflicted)}, key=str)
        days = sorted({dates[i] for i in np.flatnonzero(conflicted)})
        shown = ", ".join(fmt_date(d) for d in days[:5]) + (" ..." if len(days) > 5 else "")
        if info.layer == "timeframe":
            what = (f"{len(times)} {info.timeframe_label.lower()} bar(s) in the chosen period were built from daily "
                    f"data with conflicting observations ({shown})")
        else:
            what = (f"{len(times)} timestamp(s) in the chosen period hold conflicting observations - the same time "
                    f"with different values, which Q-MAP has not resolved ({shown})")
        report.add("ma_affinity_conflicts", FAIL,
                   f"{what}. MA Affinity needs exactly one bar per time, so it cannot use this dataset safely. Load a "
                   "corrected source file in Database Manager, or choose a period that leaves these dates out.")
        return  # the one reason is enough; QLOPB's own checks would only repeat it
    if len(set(keys)) != len(keys):
        report.add("ma_affinity_conflicts", FAIL, "Some times hold more than one bar. MA Affinity needs exactly one "
                                                  "bar per time, so it cannot use this dataset.")
        return
    else:
        report.add("ma_affinity_conflicts", PASS,
                   "No conflicting observations inside this dataset in the chosen period (exact duplicates were already "
                   "removed when it was loaded). Overlap warnings about OTHER datasets do not stop this analysis.")
    if "qlopb_settings" not in params or len(frame) == 0:
        return
    from qlopb.core.validation import check_data_for_settings, validate_ohlc_frame

    problems = validate_ohlc_frame(frame)  # includes safeguard S-1 (infinite prices)
    if problems:
        report.add("ma_affinity_prices", FAIL, "The price table is not usable: " + " ".join(problems))
        return
    errors, warnings = check_data_for_settings(frame, _settings(params))
    for e in errors:
        report.add("ma_affinity_history", FAIL, f"{e} ({len(frame)} bars in the chosen period.)")
    for w in warnings:
        report.add("ma_affinity_history", WARN, w)
    if not errors:
        report.add("ma_affinity_history", PASS, f"{len(frame)} bars are enough for the chosen MA range and windows.")


class QmapDataNote:
    """What QLOPB's reports call the data-quality report, filled with the Q-MAP facts about the registered dataset.

    QLOPB's engine accepts such an object (`quality=`): it shows `inferred_frequency` as the bar size and writes
    `to_text()` to the Excel sheet Data_Quality. Nothing in the calculation reads it.
    """

    def __init__(self, ctx: RunContext, info, frame) -> None:
        self.inferred_frequency = f"{info.timeframe_label} (Q-MAP registered dataset; not re-aggregated)"
        b = current_build()
        period = (f"{fmt_date(ctx.params.get('date_from')) if ctx.params.get('date_from') else 'first bar'} to "
                  f"{fmt_date(ctx.params.get('date_to')) if ctx.params.get('date_to') else 'last bar'}")
        self.lines = [
            "Q-MAP run and data record",
            f"Run ID: {ctx.run_id}",
            f"Code build: {build_label(b)}",
            f"Source fingerprint: {b['source_fingerprint']}",
            f"Method: {METHOD_SOURCE}",
            f"Dataset: {dataset_label(info)}",
            f"Dataset checksum (SHA-256): {info.sha256}",
            f"Validation status: {info.validation_status}",
            f"Requested period: {period}; bars used: {len(frame)} "
            f"({fmt_date(frame.index[0].date())} to {fmt_date(frame.index[-1].date())})",
            "Source file(s): " + (", ".join(info.source_files) or "-"),
            "Lineage:",
            *[f"  {line}" for line in provenance(ctx.db, info.dataset_id)],
            "Dataset validation warnings:",
            *([f"  {w}" for w in info.warnings] or ["  none"]),
            "Readiness notes shown before the run:",
            *([f"  {w}" for w in ctx.readiness_warnings] or ["  none"]),
        ]

    def to_text(self) -> str:
        return "\n".join(self.lines)


def _pdf_view(ctx: RunContext, info, res):
    """The result as QLOPB's PDF writer should see it (closure review 04-Nov-26): the PDF has no Data_Quality sheet, so
    its heading line (`label`) carries the provenance - Run ID, Q-MAP build, full source fingerprint, dataset checksum.
    Text is XML-escaped because the PDF writer reads it as markup (`&`, `<` in names or warnings). A copy only: the
    calculation result, the Excel workbook and the CSV tables are unaffected."""
    b = current_build()
    label = (f"{dataset_label(info)}, Run {ctx.run_id} | Q-MAP build: {build_label(b)} | Source fingerprint (SHA-256): "
             f"{b['source_fingerprint']} | Dataset checksum (SHA-256): {info.sha256}")
    return replace(res, label=escape(label), warnings=[escape(w) for w in res.warnings])


def dataset_label(info) -> str:
    return f"{info.instrument} {info.timeframe_label} (dataset {info.dataset_id})"


def _csv(path: Path, rows: list[dict]) -> Path:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return path


def execute(ctx: RunContext) -> list[Path]:
    from qlopb.core.research_engine import run_ma_affinity
    from qlopb.reports.chart_report import make_charts
    from qlopb.reports.excel_report import write_excel
    from qlopb.reports.pdf_report import write_pdf

    (dataset_id,) = ctx.dataset_ids
    info = get_dataset(ctx.db, dataset_id)
    s = _settings(ctx.params)
    frame, _ = _frame(ctx.settings, ctx.db, dataset_id, ctx.params)
    label = f"{dataset_label(info)}, Run {ctx.run_id}"
    ctx.log(f"MA Affinity on {label}: {len(frame)} bars, {fmt_date(frame.index[0].date())} to "
            f"{fmt_date(frame.index[-1].date())}. Method: {METHOD_SOURCE}.")
    res = run_ma_affinity(frame, s, label=label, log=ctx.log, quality=QmapDataNote(ctx, info, frame))
    for w in res.warnings:
        ctx.log(f"WARNING: {w}")
    # The reports print res.warnings; the Q-MAP data notes shown before the run are added so that the Excel and PDF
    # carry them too (Blueprint v1.35 8.5.5 / 8.5.11 E). Nothing in the calculation reads this list.
    res.warnings.extend(f"Q-MAP data: {w}" for w in ctx.readiness_warnings)
    res.warnings.extend(f"Q-MAP dataset validation warning: {w}" for w in info.warnings)
    charts = make_charts(res, ctx.run_dir, ctx.stamp)
    outputs = [write_excel(res, ctx.run_dir, ctx.stamp, charts), write_pdf(_pdf_view(ctx, info, res), ctx.run_dir, ctx.stamp, charts)]
    outputs += list(charts.values())
    outputs.append(_csv(ctx.output(f"MA_Affinity_Candidates_{ctx.stamp}.csv"), res.results))
    outputs.append(_csv(ctx.output(f"MA_Affinity_Interactions_{ctx.stamp}.csv"), res.interactions.to_dict("records")))
    ctx.log(f"Frozen Top-{len(res.frozen_top)}: " + (", ".join(f"{t}-{p}" for t, p in res.frozen_top) or "none")
            + f". Status counts: {res.counts()}.")
    return [Path(p) for p in outputs]


SPEC = AnalysisSpec(
    analysis_id="ma_affinity", name="MA Affinity (QLOPB)", version=1,
    description="How price behaved around moving averages: interactions, forward returns and an affinity score per MA "
                "period, ranked in-sample, then checked out-of-sample (QLOPB MA Affinity Scanner V2). Daily, weekly or "
                "monthly registered datasets; one dataset per run.",
    run_prefix="MAAF",
    requirement=DataRequirement(timeframes=TIMEFRAMES, min_rows=qcfg.MIN_ROWS_REQUIRED, allow_mixed=False),
    execute=execute, parameters=PARAMETERS, min_datasets=1, max_datasets=1,
    kind_note="exploratory historical research - not a trading signal; Directed IR and the weight scheme are pending "
              "owner review; p-values are not corrected for the many candidates tested",
    check_params=check_params, dataset_checks=dataset_checks, method_source=METHOD_SOURCE,
)
