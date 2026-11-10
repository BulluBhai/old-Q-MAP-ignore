"""MA Affinity V2 (analysis `ma_affinity_v2`, version 1): V1 plus a chance test and a drift baseline (owner direction
10-Nov-26). The calculation is in ma_affinity_v2_method.py; this module connects it to the Workbench.

V1 (`ma_affinity`) is unchanged and stays available, so every V1 run can still be reproduced. V2 is a separate analysis
with its own Run ID prefix (MAA2) rather than "version 2" of V1, because the registry keeps one version per analysis
and reproducing an old run requires the analysis version it was made with.

Everything V1 checks before a run is checked here too, with V1's own code (qmap.analytical_engine.ma_affinity):
the parameters (QLOPB's parser and range checks), conflicting observations, mixed timeframes, data length and prices.
V2 adds its own parameters (chance test) and one readiness item: the in-sample part must hold enough blocks to shuffle.
"""

from __future__ import annotations

import datetime as dt
import textwrap
from dataclasses import asdict, fields, replace
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

from qlopb.config import settings as qcfg

from ..catalog import DataRequirement, FAIL, PASS, WARN, fmt_date, get_dataset
from ..core.build import build_label, current_build
from . import ma_affinity as v1
from .base import AnalysisSpec, Parameter, RunContext
from .ma_affinity_v2_method import (LIMITATIONS_V2, METHOD_NAME, NOT_DISTINGUISHABLE, NOT_RUN, STANDS_OUT,
                                    MAAffinityV2Settings,
                                    run_ma_affinity_v2)

TIMEFRAMES = v1.TIMEFRAMES
RESEARCH_QUESTION = v1.RESEARCH_QUESTION + (" And is the best result stronger than the best result that chance alone "
                                            "produces on the same prices?")
_D = MAAffinityV2Settings()
METHOD_SOURCE = (f"{METHOD_NAME} (Q-MAP beta, provisional defaults, 10-Nov-26): QLOPB MA Affinity Scanner V2 calculations, "
                 f"unchanged ({v1.METHOD_SOURCE}), plus a block-shuffle chance test and a drift baseline")

# (key, label, default text, help) - the V2 additions; the V1 fields keep their V1 keys, labels and defaults
_V2_FIELDS = (
    ("chance_shuffles", "Chance shuffles", str(_D.chance_shuffles),
     "Shuffled copies of the in-sample prices tested for the chance comparison (0 = not run)."),
    ("chance_block", "Chance block bars", str(_D.chance_block_bars),
     "Bars per block when shuffling (blocks keep short trends intact)."),
    ("chance_seed", "Chance seed", str(_D.chance_seed),
     "Fixes the random order of the shuffles, so the same run gives the same result."),
    ("strength_rule", "Strength rule", _D.strength_rule,
     "relative = interactions compared with nearby periods (V2); v1 = fixed V1 reference, for comparison."),
    ("group_pct", "Group %", f"{_D.group_pct:g}",
     "Periods of one MA type within this % of a leader form one finding in the Top-N (0 = no grouping)."),
    ("zone_mode", "Zone mode", _D.zone_mode, "percent = Proximity % of the MA (V1); atr = ATR multiple x ATR."),
    ("atr_period", "ATR period", str(_D.atr_period), "Bars in the average true range (zone mode atr only)."),
    ("atr_multiple", "ATR multiple", f"{_D.atr_multiple:g}", "Zone half-width in ATRs (zone mode atr only)."),
    ("ma_warmup", "MA warm-up", "earlier",
     "earlier = with a Start date, the MAs are calculated from the dataset's earlier bars too, and interactions are "
     "counted from the Start date only; none = the MAs start at the Start date (V1)."),
)
_V2_KEYS = {"chance_shuffles": "chance_shuffles", "chance_block": "chance_block_bars", "chance_seed": "chance_seed",
            "strength_rule": "strength_rule", "group_pct": "group_pct", "zone_mode": "zone_mode",
            "atr_period": "atr_period", "atr_multiple": "atr_multiple", "ma_warmup": "ma_warmup"}
_V2_KINDS = {"strength_rule": str, "zone_mode": str, "group_pct": float, "atr_multiple": float, "ma_warmup": str}
PARAMETERS = v1.PARAMETERS + tuple(Parameter(k, label, "text", default=default, help=help_)
                                   for k, label, default, help_ in _V2_FIELDS)
_BASE_FIELDS = {f.name for f in fields(qcfg.MAResearchSettings)}


def _parse_v2_fields(params: dict) -> tuple[dict, list[str]]:
    out, problems = {}, []
    for key, label, default, _help in _V2_FIELDS:
        text = str(params.get(key) if params.get(key) is not None else default).strip()
        kind = _V2_KINDS.get(key, int)
        if kind is str:
            out[_V2_KEYS[key]] = text.lower()
            continue
        try:
            out[_V2_KEYS[key]] = kind(text)
        except ValueError:
            problems.append(f"{label} must be a {'whole number' if kind is int else 'number'} (you typed '{text}').")
    return out, problems


def check_params(params: dict) -> tuple[dict, list[str]]:
    """V1's parameter checks (unchanged), then the V2 parameters; returns the cleaned parameters for Run_Metadata."""
    cleaned, problems = v1.check_params(params)
    extra, more = _parse_v2_fields(params)
    problems = problems + more
    raw = {"date_from": params.get("date_from"), "date_to": params.get("date_to"),
           **{k: params.get(k) for k, *_ in v1._FIELDS + _V2_FIELDS}}
    if problems:
        return raw, problems
    base = {k: (tuple(v) if isinstance(v, list) else v) for k, v in cleaned["qlopb_settings"].items()}
    s = MAAffinityV2Settings(**base, **extra)
    problems = s.problems()
    if problems:
        return raw, problems
    return {"date_from": params.get("date_from"), "date_to": params.get("date_to"), "v2_settings": asdict(s)}, []


def _settings(params: dict) -> MAAffinityV2Settings:
    s = MAAffinityV2Settings(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in params["v2_settings"].items()})
    return s.check()


def _frame_with_warmup(settings, db, dataset_id: int, params: dict, s):
    """(frame, table, warm-up rows). With MA warm-up 'earlier' and a Start date, the frame also holds the dataset's
    bars BEFORE the Start date (for the moving averages only); `warm-up rows` is how many. Otherwise exactly V1's
    frame of the chosen period and 0."""
    import pandas as pd

    start = params.get("date_from")
    if s.ma_warmup != "earlier" or not start:
        frame, table = v1._frame(settings, db, dataset_id, params)
        return frame, table, 0
    frame, table = v1._frame(settings, db, dataset_id, {**params, "date_from": None})
    return frame, table, int((frame.index < pd.Timestamp(start)).sum())


def _v1_view(params: dict) -> dict:
    """The parameters as V1's readiness checks expect them (V1 settings only)."""
    if "v2_settings" not in params:
        return params
    return {**params, "qlopb_settings": {k: v for k, v in params["v2_settings"].items() if k in _BASE_FIELDS}}


def dataset_checks(settings, db, dataset_id: int, params: dict, report) -> None:
    """V1's readiness items (unchanged), then: the in-sample part must hold enough blocks for the chance test."""
    v1.dataset_checks(settings, db, dataset_id, _v1_view(params), report)
    if report.failures or "v2_settings" not in params:
        return
    s = _settings(params)
    _warmup_check(settings, db, dataset_id, params, s, report)
    if report.failures:
        return
    if s.chance_shuffles == 0:
        report.add("ma_affinity_v2_chance", WARN, "Chance shuffles is 0: the chance test will not be run, so the "
                                                  "scores cannot be judged against luck.")
        return
    frame, _ = v1._frame(settings, db, dataset_id, params)
    is_bars = int(len(frame) * s.is_pct / 100)
    blocks = (is_bars - 1) // s.chance_block_bars
    if blocks < 5:
        report.add("ma_affinity_v2_chance", FAIL,
                   f"The in-sample part has {is_bars} bars, only {blocks} block(s) of {s.chance_block_bars} bars: too "
                   "few to shuffle meaningfully (at least 5 are needed). Use a smaller block or more data.")
    else:
        report.add("ma_affinity_v2_chance", PASS,
                   f"Chance test: {s.chance_shuffles} shuffles of {blocks} blocks of {s.chance_block_bars} bars "
                   f"(seed {s.chance_seed}); {s.n_candidates} candidates are re-scanned on each shuffle.")


def _warmup_check(settings, db, dataset_id: int, params: dict, s, report) -> None:
    """MA warm-up readiness: how much earlier history the moving averages can use, and whether it is clean."""
    if not params.get("date_from"):
        return
    if s.ma_warmup != "earlier":
        report.add("ma_affinity_v2_warmup", WARN,
                   f"MA warm-up is 'none': the moving averages start at the Start date ({fmt_date(params['date_from'])}), "
                   f"so an MA of N bars has no value for its first N-1 bars of the period (the V1 behaviour).")
        return
    frame, table, a = _frame_with_warmup(settings, db, dataset_id, params, s)
    flags = np.asarray(table.column("quality_flags").to_numpy(zero_copy_only=False), dtype=np.int64)[:a]
    if a and ((flags & v1.C.FLAG_CONFLICTING_OBSERVATION) != 0).any():
        report.add("ma_affinity_v2_warmup", FAIL,
                   f"The {a} bar(s) before the Start date, used to warm up the moving averages, include conflicting "
                   "observations (the same time with different values). Set MA warm-up to 'none', or choose a "
                   "dataset without conflicts.")
    elif a >= s.ma_end:
        report.add("ma_affinity_v2_warmup", PASS,
                   f"MA warm-up: {a} bar(s) before the Start date ({fmt_date(frame.index[0].date())} onwards) are used "
                   "to calculate the moving averages; interactions are counted from the Start date only.")
    else:
        report.add("ma_affinity_v2_warmup", WARN,
                   f"MA warm-up: only {a} bar(s) exist before the Start date, fewer than the longest MA ({s.ma_end}). "
                   f"MAs longer than {a + 1} bars still start inside the chosen period, so they have fewer bars "
                   "with a value (and usually fewer interactions).")


# ---- outputs -------------------------------------------------------------------------------------------------------
def _num(v, fmt="{:.2f}"):
    return v1._num(v, fmt)


def _chance_chart(res, folder: Path, stamp: str) -> Path | None:
    ch = res.chance
    tops = [float(x) for x in ch.get("null_top_scores", []) if np.isfinite(x)]
    if not tops or not np.isfinite(ch.get("real_top_score", np.nan)):
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.hist(tops, bins=min(30, max(5, len(tops) // 5)), color="#9fb6cd", edgecolor="white",
            label=f"#1 score on {ch['valid_shuffles']} valid of {ch['requested_shuffles']} requested shuffles")
    ax.axvline(ch["real_top_score"], color="#c0392b", lw=2, label=f"real #1 score {ch['real_top_score']:.2f}")
    ax.set_xlabel("Best (#1) in-sample affinity score")
    ax.set_ylabel("Shuffles")
    p_label = (f"p-value {ch['p_value']:.4f}" if np.isfinite(ch.get("p_value", np.nan))
               else "no empirical p-value (incomplete or not applicable)")
    ax.set_title(f"{res.label}\\nChance test: {ch['verdict']} ({p_label})", fontsize=10)
    ax.legend(fontsize=8)
    fig.text(0.5, 0.005, "Historical description only - not a prediction or trading signal.", ha="center", fontsize=7,
             color="#555555")
    path = Path(folder) / f"chance_test_distribution_{stamp}.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


_V2_COLUMNS = (("Finding", "finding"), ("Group leader", "group_leader"), ("Group members", "group_members"),
               ("Strength reference", "is_strength_reference"),
               ("Chance p (adjusted)", "chance_p"), ("Chance status", "chance_status"),
               ("Chance verdict", "chance_verdict"), ("IS baseline %", "is_baseline_sr"),
               ("IS edge vs baseline (pts)", "is_edge_vs_baseline"),
               ("IS exploratory p vs baseline", "is_p_vs_baseline"), ("OOS baseline %", "oos_baseline_sr"),
               ("OOS edge vs baseline (pts)", "oos_edge_vs_baseline"),
               ("OOS exploratory p vs baseline", "oos_p_vs_baseline"))


def _results_frame(res):
    from qlopb.reports.excel_report import results_frame

    df = results_frame(res)  # QLOPB's table, unchanged; the V2 columns are added after it
    by_label = {r["ma_label"]: r for r in res.results}
    for title, key in _V2_COLUMNS:
        df[title] = [by_label[m].get(key) for m in df["MA"]]
    return df


def write_excel(res, folder: Path, stamp: str, charts: dict) -> Path:
    import pandas as pd
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter
    from qlopb.reports.excel_report import TOP_FILL, WEAK_FILL, _kv, _write_df

    s, di, ch = res.settings, res.data_info, res.chance
    counts = res.counts()
    top = res.frozen_top_results()
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    rows = [("MA Affinity V2 research", ""), ("Instrument / dataset", res.label),
            ("Report date", dt.datetime.now().strftime(qcfg.DATETIME_FMT)), ("DISCLAIMER", qcfg.DISCLAIMER_TEXT),
            ("", ""), ("EXECUTIVE INTERPRETATION", "Plain English; every number is from this run's results")]
    rows += executive_interpretation(res.label.split(", Run ")[0], res)
    rows += [("", ""), ("CHANCE TEST VERDICT", ch["verdict"]),
            ("  real #1 in-sample score", _num(ch.get("real_top_score"))),
            ("  chance p-value", _num(ch.get("p_value"), "{:.4f}")),
            ("  luck-only #1 scores: mean / 95th pct / max",
             f"{_num(ch.get('null_mean'))} / {_num(ch.get('null_p95'))} / {_num(ch.get('null_max'))}"),
            ("  shuffles / block bars / seed", f"{ch['shuffles']} / {ch['block_bars']} / {ch['seed']}"), ("", ""),
            ("Bars analysed", di["n_bars"]), ("Data period", f"{di['first']} to {di['last']}"),
            ("In-sample", f"{di['is_bars']} bars ({di['is_first']} to {di['is_last']})"),
            ("Out-of-sample", f"{di['oos_bars']} bars ({di['oos_first']} to {di['oos_last']})"),
            ("Bar size", di["frequency"]), ("", ""), ("Candidates tested", len(res.results)),
            ("  with enough IS interactions (ranked)", counts.get("OK", 0)),
            ("  INSUFFICIENT_DATA (not ranked)", counts.get("INSUFFICIENT_DATA", 0)),
            ("  NO_INTERACTIONS (not ranked)", counts.get("NO_INTERACTIONS", 0)),
            ("Frozen Top-N", ", ".join(f"#{r['rank']} {r['ma_label']}" for r in top) or "none"), ("", ""),
            ("WARNINGS", "")]
    rows += [("  -", w) for w in res.warnings] or [("  -", "none")]
    rows += [("", ""), ("LIMITATIONS", "")] + [("  -", t) for t in LIMITATIONS_V2]
    _kv(ws, rows)
    for r in ws.iter_rows(min_row=1, max_row=len(rows)):
        r[1].alignment = Alignment(wrap_text=True, vertical="top")

    df = _results_frame(res)
    ws = wb.create_sheet("Top_N")
    leaders = {r["ma_label"] for r in top}
    topdf = df[df["MA"].isin(leaders)].sort_values("Finding", kind="stable")
    _write_df(ws, topdf)
    ws.cell(row=len(topdf) + 3, column=1,
            value="The Top-N are the leaders of distinct findings (neighbouring periods of one MA type are grouped; "
                  "'Group members'). Ranks use in-sample data only. OOS columns were calculated after the Top-N was "
                  "frozen and never changed a rank. 'Chance p (adjusted)' compares each score with the best score found "
                  "on shuffled prices, so it allows for the many candidates tested. Baselines are reported only.")
    ws = wb.create_sheet("Rankings")
    _write_df(ws, df, highlight=lambda row: TOP_FILL if row["MA"] in leaders
              else (WEAK_FILL if row["IS status"] != "OK" else None))
    ws.auto_filter.ref = f"A1:{get_column_letter(len(df.columns))}{len(df) + 1}"

    ws = wb.create_sheet("Chance_Test")
    _write_df(ws, pd.DataFrame({"Shuffle": range(1, len(ch["null_top_scores"]) + 1),
                                "#1 score": ch["null_top_scores"], "#1 candidate": ch.get("null_top_labels", [])}))

    ws = wb.create_sheet("Interactions")
    if res.interactions.empty:
        ws.cell(row=1, column=1, value="No interactions were recorded.")
    else:
        _write_df(ws, res.interactions)

    ws = wb.create_sheet("Settings")
    _kv(ws, [(k, v) for k, v in s.to_dict().items()] + [
        ("weights used (normalised)", {k: round(v / sum(s.weights.values()) * 100, 2) for k, v in s.weights.items()}),
        ("Forward Return component", "Directed IR - V1 formula kept, PENDING OWNER REVIEW"),
        ("Success baseline", "Score compares with 50% (as V1); drift baseline reported alongside"),
        ("Interaction strength", "relative: min(V1 reference, median interactions of the same type within +/-20% of the "
                                 "period)" if s.strength_rule == "relative" else "v1: fixed V1 reference"),
        ("Zone", f"{s.proximity_pct}% of the MA" if s.zone_mode == "percent" else
                 f"MA +/- {s.atr_multiple} x ATR({s.atr_period})"),
        ("IS/OOS consistency", "Report only - not part of the affinity score")])
    ws = wb.create_sheet("Data_Quality")
    _kv(ws, [(f"line {i + 1}", ln) for i, ln in enumerate(res.quality.to_text().splitlines())]
        if res.quality is not None else [("note", "No data note.")])
    if charts:
        ws = wb.create_sheet("Charts")
        row = 1
        for name, p in charts.items():
            try:
                img = XLImage(str(p))
                img.width, img.height = 900, int(900 * img.height / img.width)
                ws.add_image(img, f"A{row}")
                row += int(img.height / 20) + 3
            except Exception:
                ws.cell(row=row, column=1, value=f"[{name} not embedded]")
                row += 2
    path = Path(folder) / f"MA_Affinity_V2_{stamp}.xlsx"
    wb.save(path)
    return path


def write_pdf(res, folder: Path, stamp: str, charts: dict, heading: str) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    path = Path(folder) / f"MA_Affinity_V2_Report_{stamp}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title="MA Affinity V2")
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=8.5, leading=11)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#444444"))
    h = ss["Heading2"]
    s, di, ch = res.settings, res.data_info, res.chance
    counts = res.counts()
    verdict_color = {STANDS_OUT: "#1e7b34", NOT_DISTINGUISHABLE: "#b03a2e"}.get(ch["verdict"], "#7a5c00")
    st = [Paragraph("MA Affinity V2 research report", ss["Title"]),
          Paragraph(escape(heading) + f" &nbsp;|&nbsp; {dt.datetime.now().strftime(qcfg.DATETIME_FMT)}", body),
          Spacer(1, 0.2 * cm), Paragraph("<b>" + escape(qcfg.DISCLAIMER_TEXT) + "</b>", body), Spacer(1, 0.3 * cm),
          Paragraph("Executive interpretation", h)]
    st += [Paragraph(f"<b>{escape(head)}.</b> {escape(text)}", body)
           for head, text in executive_interpretation(res.label.split(", Run ")[0], res)]
    st += [PageBreak(), Paragraph("Chance test", h),
          Paragraph(f"<font color='{verdict_color}'><b>{escape(ch['verdict'])}</b></font>. Real #1 in-sample score "
                    f"{_num(ch.get('real_top_score'))}; chance p-value {_num(ch.get('p_value'), '{:.4f}')}. On "
                    f"{ch['shuffles']} block-shuffled copies of the in-sample prices ({ch['block_bars']}-bar blocks, "
                    f"seed {ch['seed']}) the #1 score averaged {_num(ch.get('null_mean'))} (95th percentile "
                    f"{_num(ch.get('null_p95'))}, highest {_num(ch.get('null_max'))}).", body),
          Paragraph("Data and sample sizes", h),
          Paragraph(f"{di['n_bars']} bars ({escape(str(di['frequency']))}), {di['first']} to {di['last']}. In-sample: "
                    f"{di['is_bars']} bars ({di['is_first']} to {di['is_last']}). Out-of-sample: {di['oos_bars']} bars "
                    f"({di['oos_first']} to {di['oos_last']}).", body),
          Paragraph(f"Candidates tested: {len(res.results)}; ranked: {counts.get('OK', 0)}; insufficient data: "
                    f"{counts.get('INSUFFICIENT_DATA', 0)}; no interactions: {counts.get('NO_INTERACTIONS', 0)}. "
                    f"Minimum interactions: {s.min_interactions}.", body)]
    if res.warnings:
        st.append(Paragraph("Warnings", h))
        st += [Paragraph("- " + escape(w), body) for w in res.warnings]
    st.append(Paragraph("Limitations", h))
    st += [Paragraph("- " + escape(t), small) for t in LIMITATIONS_V2]
    st.append(PageBreak())
    st.append(Paragraph(f"Frozen Top-{s.top_n} distinct findings (ranked on in-sample data only)", h))
    hdr = ["#", "Rank", "MA", "Group", "IS aff.", "Chance p", "IS n", "IS succ %", "IS base %", "Edge pts", "OOS outc.",
           "OOS succ %", "OOS base %", "Consistency"]
    data = [hdr] + [[r["finding"], r["rank"], r["ma_label"], r["group_size"], _num(r["is_affinity_score"]),
                     _num(r["chance_p"], "{:.4f}"), r["is_n"],
                     _num(r["is_overall_sr"]), _num(r["is_baseline_sr"]), _num(r["is_edge_vs_baseline"]),
                     _num(r.get("oos_n_outcomes"), "{:.0f}"), _num(r["oos_overall_sr"]), _num(r["oos_baseline_sr"]),
                     _num(r["is_oos_consistency_score"])] for r in res.frozen_top_results()]
    if len(data) == 1:
        data.append(["-"] * len(hdr))
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE6F0")),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7),
                           ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    st += [t, Spacer(1, 0.2 * cm),
           Paragraph("'-' means not available (missing), not zero. Group = how many neighbouring periods of the same "
                     "MA type form this finding (members in the Excel Top_N sheet). Chance p compares each score with the best score "
                     "found on shuffled prices. Base % = what price did anyway over the same bars (reported only; the "
                     "score still compares with 50%). Edge = success rate minus baseline.", small)]
    for c in (charts or {}).values():
        try:
            st.append(PageBreak())
            img = Image(str(c))
            sc = min((landscape(A4)[0] - 3 * cm) / img.drawWidth, (landscape(A4)[1] - 4 * cm) / img.drawHeight)
            img.drawWidth *= sc
            img.drawHeight *= sc
            st.append(img)
        except Exception:
            st.append(Paragraph(f"[chart {escape(Path(str(c)).name)} could not be embedded]", small))
    doc.build(st)
    return path


SMALL_SAMPLE = 30  # fewer outcomes than this: success rates can swing widely by chance (said in the interpretation)


def executive_interpretation(dataset_label: str, res) -> list[tuple[str, str]]:
    """The 'Executive interpretation' (10-Nov-26 reporting requirement): eight short plain-English answers, every
    number taken from the calculated results (nothing estimated or invented here). Used by the findings file, the Excel
    Summary sheet and the PDF. Returns [(heading, text)]."""
    s, di, ch = res.settings, res.data_info, res.chance
    pk = s.fwd_windows[0]
    top = res.frozen_top_results()
    counts = res.counts()
    warm = (f" The moving averages were also calculated from {di['warmup_bars']} earlier bar(s) (from "
            f"{di['warmup_first']}), but nothing before {di['first']} was counted." if di.get("warmup_bars") else "")
    out = [("1. Question investigated",
            f"{RESEARCH_QUESTION} Instrument: {dataset_label}."),
           ("2. Data and period",
            f"{di['n_bars']:,} bars from {di['first']} to {di['last']} (bar size: {di['frequency']}). The ranking "
            "used only the "
            f"first {di['is_bars']} bars ({di['is_first']} to {di['is_last']}, in-sample); the later {di['oos_bars']} "
            f"bars ({di['oos_first']} to {di['oos_last']}, out-of-sample) were kept aside to check the ranking "
            f"afterwards.{warm}")]
    if not top:
        out.append(("3. What the analysis found",
                    f"No candidate had the minimum {s.min_interactions} in-sample interactions, so nothing was ranked "
                    f"({len(res.results)} candidates tested). This means not enough data for these settings, not "
                    "poor results."))
    else:
        r = top[0]
        others = ", ".join(x["ma_label"] for x in top[1:])
        out.append(("3. What the analysis found",
                    f"Of {len(res.results)} moving averages tested ({counts.get('OK', 0)} with enough interactions to "
                    f"be ranked), the highest in-sample score was {r['ma_label']} with an affinity score of "
                    f"{_num(r['is_affinity_score'])} out of 100: price came near it {r['is_n']} time(s) in-sample and "
                    f"moved the expected way {pk} bars later in {_num(r['is_overall_sr'])}% of {r['is_n_outcomes']} "
                    f"usable outcome(s)." + (f" The other Top-{len(top)} findings: {others}." if others else "")))
    out.append(("4. What the scores and percentages mean",
                "The affinity score (0-100) combines four parts with fixed weights: how often price interacted with "
                "the MA, how often it then moved the expected way, how large that move was relative to its "
                "variability, and how steady the success rate was over time. It is a ranking score, not a "
                f"probability or a forecast. 'In-sample success %' is the share of qualifying in-sample outcomes in "
                f"which price moved the expected way after {pk} bars: higher after touching the MA from above "
                "(support), lower after touching it from below (resistance)."))
    if ch["verdict"] in (STANDS_OUT, NOT_DISTINGUISHABLE):
        finest = 1 / (ch["shuffles"] + 1)
        chance_text = (f"Verdict: {ch['verdict']}. On {ch['shuffles']} block-shuffled copies of the same in-sample "
                       f"prices (where any real link with a moving average is destroyed) the best score averaged "
                       f"{_num(ch['null_mean'])} and reached {_num(ch['null_max'])} at most; the real best score was "
                       f"{_num(ch['real_top_score'])} (chance p-value {_num(ch['p_value'], '{:.4f}')}). ")
        chance_text += ("The best real result is higher than nearly all luck-only results. That is evidence for this "
                        "instrument and period under the shuffle model's assumptions, not proof of a profitable or "
                        "lasting edge." if ch["verdict"] == STANDS_OUT else
                        "Luck alone often produced a best score this high, so the ranking may be chance and should "
                        "be treated as unproven.")
        chance_text += (f" With {ch['shuffles']} shuffles the smallest possible chance p-value is {finest:.4f}, so "
                        "p-values are approximate at that resolution.")
    elif ch["verdict"] == NOT_RUN:
        chance_text = "The chance test was not run (Chance shuffles = 0), so the scores cannot be judged against luck."
    elif ch.get("status") == "inconclusive":
        chance_text = (f"INCONCLUSIVE: {ch['invalid_shuffles']} of {ch['attempted_shuffles']} attempted shuffles "
                       f"were invalid and {ch['unattempted_shuffles']} of {ch['requested_shuffles']} requested "
                       f"shuffles were not completed. No empirical p-value or positive chance verdict is available.")
    elif ch.get("status") == "no_candidate":
        chance_text = (f"No candidate was ranked, so there was nothing to compare with chance. "
                       f"{ch['requested_shuffles']} shuffles were requested; none was run because no ranked candidate "
                       f"was available.")
    else:
        chance_text = f"{ch['verdict']}."
    out.append(("5. Comparison with chance", chance_text))
    if top:
        r = top[0]
        oos_part = ("It was not evaluated out-of-sample." if r["oos_status"] == "NOT_EVALUATED" else
                    f"Out-of-sample its success rate was {_num(r['oos_overall_sr'])}% over "
                    f"{int(r['oos_n_outcomes'] or 0)} outcome(s), against a baseline of {_num(r['oos_baseline_sr'])}% "
                    f"(edge {_num(r['oos_edge_vs_baseline'])} points).")
        out.append(("6. Comparison with the market's own movement (drift baseline)",
                    f"Over the same in-sample bars, price was higher or lower {pk} bars later anyway in "
                    f"{_num(r['is_baseline_sr'])}% of cases (weighted to {r['ma_label']}'s own support and "
                    f"resistance outcomes). Its {_num(r['is_overall_sr'])}% success is therefore "
                    f"{_num(r['is_edge_vs_baseline'])} percentage points above that baseline. {oos_part} The baseline "
                    "is reported only; the score still compares with 50%, as in V1."))
    else:
        out.append(("6. Comparison with the market's own movement (drift baseline)",
                    "Not applicable: nothing was ranked."))
    lim = ["the chance test uses one price history and one shuffle model (blocks of "
           f"{s.chance_block_bars} bars), so it does not prove that a result will persist",
           "the chance threshold 0.05, the 15-bar blocks, the strength rule, Group % and the ATR option are "
           "provisional beta defaults, not owner-approved methodology",
           "Directed IR and the score weights are pending owner review"]
    if top and (top[0]["is_n_outcomes"] or 0) < SMALL_SAMPLE:
        lim.insert(0, f"the #1 finding rests on only {top[0]['is_n_outcomes']} in-sample outcome(s), so its success "
                      "rate can swing widely by chance")
    if top and top[0]["oos_status"] != "NOT_EVALUATED" and (top[0].get("oos_n_outcomes") or 0) < SMALL_SAMPLE:
        lim.insert(1, f"the out-of-sample check rests on {int(top[0].get('oos_n_outcomes') or 0)} outcome(s)")
    text = "; ".join(lim)
    out.append(("7. Main limitations", text[:1].upper() + text[1:] + ". The full list is under 'How to read this' "
                                                                       "in the findings file and in the reports."))
    nxt = []
    if ch["verdict"] == NOT_DISTINGUISHABLE or not top:
        nxt.append("do not rely on this ranking; try a longer history, another timeframe or other instruments")
    elif ch["verdict"] == STANDS_OUT:
        nxt.append("confirm the finding on other instruments and later periods before relying on it")
        nxt.append("for a finer chance p-value, run again with more Chance shuffles (for example 1000; it takes "
                   "about five times longer)")
    elif ch["verdict"] == NOT_RUN:
        nxt.append("run again with Chance shuffles above 0 (default 200) so the result can be judged against luck")
    if top and r["oos_status"] != "NOT_EVALUATED" and not (r.get("oos_edge_vs_baseline") or 0) > 0:
        nxt.append("note that out-of-sample the #1 finding did not beat its baseline")
    nxt.append("look at the detailed tables (Excel Top_N and Rankings sheets, CSV files) for the evidence behind "
               "each number")
    text = "; ".join(nxt)
    out.append(("8. What to investigate next", text[:1].upper() + text[1:] + "."))
    return out


def _findings(ctx: RunContext, info, res) -> Path:
    s, di, ch = res.settings, res.data_info, res.chance
    pk = s.fwd_windows[0]
    lines = [f"MA Affinity V2 findings - {v1.dataset_label(info)} - Run {ctx.run_id}", "",
             "EXECUTIVE INTERPRETATION (plain English; every number below is from this run's calculated results)", ""]
    for head, text in executive_interpretation(v1.dataset_label(info), res):
        lines += [head, *textwrap.wrap(text, 110, initial_indent="  ", subsequent_indent="  "), ""]
    lines += ["DETAILED FINDINGS", "",
              "Research question", f"  {RESEARCH_QUESTION}", "",
              "Chance test", f"  VERDICT: {ch['verdict']}"]
    if ch["verdict"] in (STANDS_OUT, NOT_DISTINGUISHABLE):
        lines.append(f"  The real #1 in-sample score is {_num(ch['real_top_score'])}. On {ch['shuffles']} copies of the "
                     f"in-sample prices shuffled in blocks of {ch['block_bars']} bars (seed {ch['seed']}), the #1 score "
                     f"averaged {_num(ch['null_mean'])}, its 95th percentile was {_num(ch['null_p95'])} and the "
                     f"highest was {_num(ch['null_max'])}. Chance p-value {_num(ch['p_value'], '{:.4f}')} (the share "
                     "of shuffles that did at least as well, counting the real series).")
    lines += [f"  Requested/attempted/valid/invalid/unattempted shuffles: "
              f"{ch['requested_shuffles']}/{ch['attempted_shuffles']}/{ch['valid_shuffles']}/"
              f"{ch['invalid_shuffles']}/{ch['unattempted_shuffles']}",
              "", "Data", f"  {di['n_bars']} bars from {di['first']} to {di['last']}. Ranking used the in-sample part "
              f"only: {di['is_bars']} bars ({di['is_first']} to {di['is_last']}). The out-of-sample check used the "
              f"remaining {di['oos_bars']} bars ({di['oos_first']} to {di['oos_last']}).", "",
              f"Method: {len(res.results)} candidates ({', '.join(s.ma_types)}, periods {s.ma_start}-{s.ma_end}); an "
              "interaction is a bar entering the zone within " + (f"{s.proximity_pct}% of the MA" if s.zone_mode ==
                                                                 "percent" else f"{s.atr_multiple} x ATR({s.atr_period}) "
                                                                                "of the MA") +
              f"; success is a move in the expected direction after {pk} bars (support: up, resistance: down). "
              f"Interaction strength rule: {s.strength_rule}. Neighbouring periods grouped within "
              + (f"{s.group_pct:g}%." if float(s.group_pct) > 0 else "- (grouping off)."), ""]
    top = res.frozen_top_results()
    if not top:
        lines += ["Result", "  No candidate had enough in-sample interactions to be ranked. This means insufficient "
                            "data for these settings, not poor results."]
    else:
        lines.append(f"Frozen Top-{len(top)} distinct findings (chosen on in-sample data only, then checked "
                     "out-of-sample)")
        for r in top:
            oos = ("not evaluated" if r["oos_status"] == "NOT_EVALUATED" else
                   f"out-of-sample {_num(r['oos_overall_sr'])}% success over {int(r['oos_n_outcomes'] or 0)} "
                   f"outcome(s) against a baseline of {_num(r['oos_baseline_sr'])}% (consistency "
                   f"{_num(r['is_oos_consistency_score'])}, {r['is_oos_consistency_status']})")
            members = (f" (group of {r['group_size']}: {r['group_members']})" if r["group_size"] > 1 else "")
            lines.append(f"  {r['finding']}. {r['ma_label']}{members}, in-sample rank {r['rank']}: affinity "
                         f"{_num(r['is_affinity_score'])}, chance p "
                         f"{_num(r['chance_p'], '{:.4f}')}; in-sample {_num(r['is_overall_sr'])}% success over "
                         f"{r['is_n_outcomes']} outcome(s) against a baseline of {_num(r['is_baseline_sr'])}% (edge "
                         f"{_num(r['is_edge_vs_baseline'])} pts); {oos}.")
    lines += ["", "How to read this", *[f"  - {t}" for t in LIMITATIONS_V2], f"  - {qcfg.DISCLAIMER_TEXT}",
              "  - Full tables: MA_Affinity_V2_Candidates, MA_Affinity_V2_Interactions and MA_Affinity_V2_Chance_Shuffles "
              "(CSV), the Excel workbook and the PDF."]
    path = ctx.output(f"MA_Affinity_V2_Findings_{ctx.stamp}.txt")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _data_note(ctx: RunContext, info, frame):
    note = v1.QmapDataNote(ctx, info, frame)
    note.lines = [f"Method: {METHOD_SOURCE}" if ln.startswith("Method: ") else ln for ln in note.lines]
    note.lines = [f"  {RESEARCH_QUESTION}" if ln == f"  {v1.RESEARCH_QUESTION}" else ln for ln in note.lines]
    return note


def execute(ctx: RunContext) -> list[Path]:
    from qlopb.core.research_engine import RunCancelled as QlopbCancelled
    from qlopb.reports.chart_report import make_charts

    from ..core.errors import RunCancelled

    (dataset_id,) = ctx.dataset_ids
    info = get_dataset(ctx.db, dataset_id)
    s = _settings(ctx.params)
    full, _, a = _frame_with_warmup(ctx.settings, ctx.db, dataset_id, ctx.params, s)
    frame = full.iloc[a:]  # the chosen analysis period (what V1 would use)
    label = f"{v1.dataset_label(info)}, Run {ctx.run_id}"
    ctx.log(f"MA Affinity V2 on {label}: {len(frame)} bars, {fmt_date(frame.index[0].date())} to "
            f"{fmt_date(frame.index[-1].date())}. Method: {METHOD_SOURCE}.")
    if a:
        ctx.log(f"MA warm-up: {a} earlier bar(s) from {fmt_date(full.index[0].date())} are used to calculate the "
                "moving averages only; no interaction is counted before the Start date.")
    try:
        res = run_ma_affinity_v2(full, s, label=label, log=ctx.log, quality=_data_note(ctx, info, frame),
                                 progress=ctx.progress, cancel=ctx.cancel_requested, analysis_start=a)
    except QlopbCancelled:
        raise RunCancelled("Cancelled by the user.") from None
    ctx.stop_if_cancelled()  # a request that arrived during the last step stops the run before any report is written
    for w in res.warnings:
        ctx.log(f"WARNING: {w}")
    ch = res.chance
    ctx.details.update({
        "bars_used": {"count": int(len(frame)), "first": frame.index[0].date().isoformat(),
                      "last": frame.index[-1].date().isoformat()},
        "ma_warmup": {"rule": s.ma_warmup, "bars_before_start": a,
                      "first": full.index[0].date().isoformat() if a else None},
        "split": {k: res.data_info[k] for k in ("is_bars", "is_first", "is_last", "oos_bars", "oos_first", "oos_last")},
        "frozen_top": [f"{t}-{p}" for t, p in res.frozen_top], "status_counts": res.counts(),
        "engine": METHOD_SOURCE, "research_question": RESEARCH_QUESTION,
        "chance_test": {k: ch[k] for k in ("verdict", "status", "real_top_score", "p_value", "percentile",
                                           "shuffles", "requested_shuffles", "attempted_shuffles", "valid_shuffles",
                                           "invalid_shuffles", "unattempted_shuffles", "block_bars", "seed",
                                           "null_mean", "null_p95", "null_max")}})
    res.warnings.extend(f"Q-MAP data: {w}" for w in ctx.readiness_warnings)
    res.warnings.extend(f"Q-MAP dataset validation warning: {w}" for w in info.warnings)
    charts = make_charts(res, ctx.run_dir, ctx.stamp)
    chance_png = _chance_chart(res, ctx.run_dir, ctx.stamp)
    if chance_png is not None:
        charts = {"chance_test": chance_png, **charts}
    b = current_build()
    heading = (f"{v1.dataset_label(info)}, Run {ctx.run_id} | Q-MAP build: {build_label(b)} | Source fingerprint "
               f"(SHA-256): {b['source_fingerprint']} | Dataset checksum (SHA-256): {info.sha256}")
    outputs = [write_excel(res, ctx.run_dir, ctx.stamp, charts), write_pdf(res, ctx.run_dir, ctx.stamp, charts, heading)]
    outputs += list(charts.values())
    outputs.append(v1._csv(ctx.output(f"MA_Affinity_V2_Candidates_{ctx.stamp}.csv"), res.results))
    outputs.append(v1._csv(ctx.output(f"MA_Affinity_V2_Interactions_{ctx.stamp}.csv"),
                           res.interactions.to_dict("records")))
    outputs.append(v1._csv(ctx.output(f"MA_Affinity_V2_Chance_Shuffles_{ctx.stamp}.csv"),
                           [{"shuffle": i + 1, "top_score": sc, "top_candidate": lab} for i, (sc, lab) in
                            enumerate(zip(ch["null_top_scores"], ch.get("null_top_labels", [])))]
                           or [{"shuffle": "", "top_score": "", "top_candidate": ""}]))
    outputs.append(_findings(ctx, info, res))
    ctx.log(f"Frozen Top-{len(res.frozen_top)}: " + (", ".join(f"{t}-{p}" for t, p in res.frozen_top) or "none")
            + f". Chance test: {ch['verdict']}.")
    return [Path(p) for p in outputs]


SPEC = AnalysisSpec(
    analysis_id="ma_affinity_v2", name="MA Affinity V2 (chance-tested)", version=1,
    description="MA Affinity built on V1 (same MA formulas, interactions, in-sample ranking and out-of-sample "
                "check), plus a chance test against block-shuffled copies of the same prices, a drift baseline next "
                "to every success rate, an interaction strength that does not mark long MAs down, neighbouring "
                "periods grouped into one finding, and an optional ATR zone. Daily, weekly or monthly registered "
                "datasets; one dataset per run.",
    run_prefix="MAA2",
    requirement=DataRequirement(timeframes=TIMEFRAMES, min_rows=qcfg.MIN_ROWS_REQUIRED, allow_mixed=False),
    execute=execute, parameters=PARAMETERS, min_datasets=1, max_datasets=1,
    kind_note="exploratory historical research - not a trading signal; baseline p-values are exploratory diagnostics, "
              "not definitive inferential evidence; judge results by the chance test; Directed IR and the weight scheme "
              "are pending owner review",
    check_params=check_params, dataset_checks=dataset_checks, method_source=METHOD_SOURCE,
    result_tables=("MA_Affinity_V2_Candidates_", "MA_Affinity_V2_Interactions_", "MA_Affinity_V2_Chance_Shuffles_"),
)
