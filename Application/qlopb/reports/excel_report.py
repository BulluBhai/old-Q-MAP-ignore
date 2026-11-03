"""
Excel workbook output. Missing values are left EMPTY (never 0) and every
candidate carries a status, so 'insufficient data' is never confused with a poor
result. Dates use dd-mmm-yy. Value cells carry no currency symbols.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from qlopb.config import settings as cfg

HDR_FILL = PatternFill("solid", fgColor="DDE6F0")
TOP_FILL = PatternFill("solid", fgColor="E3F1E3")
WEAK_FILL = PatternFill("solid", fgColor="EFEFEF")


def _clean(v):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        return None if (np.isnan(v) or np.isinf(v)) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


def results_frame(res) -> pd.DataFrame:
    """One row per candidate, in rank order (unranked candidates after the ranked ones)."""
    wins = list(res.settings.fwd_windows)
    rows = []
    for r in res.results:
        row = {
            "Rank": r["rank"], "Tie": "yes" if r.get("rank_tie") else "",
            "MA": r["ma_label"], "Type": r["ma_type"], "Period": r["ma_period"], "Horizon": r["horizon"],
            "IS status": r["is_status"], "IS affinity": r["is_affinity_score"],
            "IS interactions": r["is_n"], "IS outcomes": r["is_n_outcomes"],
            "IS success %": r["is_overall_sr"], "IS support %": r["is_support_sr"],
            "IS resistance %": r["is_resistance_sr"], "IS stability %": r["is_stability"],
            "IS reliability": r["is_reliability"], "IS p-value (uncorrected)": r["is_p_value"]}
        for w in wins:
            row[f"IS fwd{w} mean %"] = r["is_fwd_stats"][w]["mean"]
        sc = r["is_score_components"]
        row.update({"Comp: interaction": sc["interaction_strength"], "Comp: success": sc["success_rate"],
                    "Comp: fwd (Directed IR, under review)": sc["forward_return_directed_ir"],
                    "Comp: stability": sc["stability"]})
        row.update({"OOS status": r["oos_status"], "OOS interactions": r["oos_n"],
                    "OOS outcomes": r.get("oos_n_outcomes"), "OOS success %": r["oos_overall_sr"],
                    "OOS affinity": r["oos_affinity_score"],
                    "IS-OOS diff (pts)": r["is_oos_sr_diff"],
                    "Consistency (report only)": r["is_oos_consistency_score"],
                    "Consistency status": r["is_oos_consistency_status"]})
        rows.append(row)
    df = pd.DataFrame(rows)
    df["_r"] = df["Rank"].fillna(1e9)
    df = df.sort_values(["_r"], kind="stable").drop(columns="_r")
    return df.reset_index(drop=True)


def _write_df(ws, df, start_row=1, highlight=None):
    for c, name in enumerate(df.columns, 1):
        cell = ws.cell(row=start_row, column=c, value=str(name))
        cell.font = Font(bold=True)
        cell.fill = HDR_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(c)].width = max(11, min(28, len(str(name)) + 2))
    for r_i, (_, row) in enumerate(df.iterrows(), start_row + 1):
        fill = highlight(row) if highlight else None
        for c, v in enumerate(row, 1):
            cell = ws.cell(row=r_i, column=c, value=_clean(v))
            if fill:
                cell.fill = fill
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)


def _kv(ws, rows, start=1):
    for i, (k, v) in enumerate(rows, start):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=_clean(v) if not isinstance(v, (list, tuple, dict)) else str(v))
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 100


def write_excel(res, folder, stamp, charts=None) -> Path:
    s = res.settings
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    di = res.data_info
    counts = res.counts()
    top = res.frozen_top_results()
    rows = [("QLOPB - MA Affinity research", ""), ("Instrument / file", res.label),
            ("Report date", dt.datetime.now().strftime(cfg.DATETIME_FMT)),
            ("DISCLAIMER", cfg.DISCLAIMER_TEXT), ("", ""),
            ("Bars analysed", di["n_bars"]), ("Data period", f"{di['first']} to {di['last']}"),
            ("In-sample", f"{di['is_bars']} bars ({di['is_first']} to {di['is_last']})"),
            ("Out-of-sample", f"{di['oos_bars']} bars ({di['oos_first']} to {di['oos_last']})"),
            ("Bar size", di["frequency"]), ("", ""),
            ("Candidates tested", len(res.results)),
            ("  with enough IS interactions (ranked)", counts.get("OK", 0)),
            ("  INSUFFICIENT_DATA (not ranked)", counts.get("INSUFFICIENT_DATA", 0)),
            ("  NO_INTERACTIONS (not ranked)", counts.get("NO_INTERACTIONS", 0)),
            ("Frozen Top-N", ", ".join(f"#{r['rank']} {r['ma_label']}" for r in top) or "none"),
            ("", ""), ("WARNINGS", "")]
    rows += [("  -", w) for w in res.warnings] or [("  -", "none")]
    rows += [("", ""), ("LIMITATIONS", "")] + [("  -", t) for t in cfg.LIMITATIONS]
    _kv(ws, rows)
    for r in ws.iter_rows(min_row=1, max_row=len(rows)):
        r[1].alignment = Alignment(wrap_text=True, vertical="top")

    ws = wb.create_sheet("Top_N")
    df = results_frame(res)
    topdf = df[df["Rank"].notna() & (df["Rank"] <= s.top_n)]
    _write_df(ws, topdf)
    ws.cell(row=len(topdf) + 3, column=1,
            value="Ranks use in-sample data only. OOS columns were calculated after the Top-N was frozen "
                  "and never changed a rank. Consistency is shown only when OOS has enough outcomes.")

    ws = wb.create_sheet("Rankings")
    _write_df(ws, df, highlight=lambda row: TOP_FILL if (pd.notna(row["Rank"]) and row["Rank"] <= s.top_n)
              else (WEAK_FILL if row["IS status"] != "OK" else None))
    ws.auto_filter.ref = f"A1:{get_column_letter(len(df.columns))}{len(df) + 1}"

    ws = wb.create_sheet("Interactions")
    inter = res.interactions
    if inter.empty:
        ws.cell(row=1, column=1, value="No interactions were recorded.")
    else:
        _write_df(ws, inter)

    ws = wb.create_sheet("Forward_Returns")
    fr = []
    for r in sorted(res.results, key=lambda r: (r["rank"] is None, r["rank"] or 0)):
        for phase in ("is", "oos"):
            fs = r.get(f"{phase}_fwd_stats")
            if not isinstance(fs, dict):
                continue
            for w in s.fwd_windows:
                d = fs[w]
                fr.append({"MA": r["ma_label"], "Rank": r["rank"], "Phase": phase.upper(), "Window (bars)": w,
                           "N": d["n"], "Mean %": d["mean"], "Median %": d["median"], "Std %": d["std"],
                           "Share > 0 (%)": None if np.isnan(d["hit_rate"]) else d["hit_rate"] * 100})
    _write_df(ws, pd.DataFrame(fr))

    ws = wb.create_sheet("Settings")
    _kv(ws, [(k, v) for k, v in s.to_dict().items()] + [
        ("weights used (normalised)", {k: round(v / sum(s.weights.values()) * 100, 2)
                                       for k, v in s.weights.items()}),
        ("Forward Return component", "Directed IR - V2 formula kept, PENDING OWNER REVIEW"),
        ("IS/OOS consistency", "Report only - not part of the affinity score"),
        ("Data timeframe used", res.data_info["timeframe_setting"])] +
        [("note", n) for n in res.notes])

    ws = wb.create_sheet("Data_Quality")
    if res.quality is not None:
        _kv(ws, [(f"line {i + 1}", ln) for i, ln in enumerate(res.quality.to_text().splitlines())])
    else:
        ws.cell(row=1, column=1, value="No data-quality report (data was supplied as a table).")

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
    path = Path(folder) / f"QLOPB_MA_Affinity_{stamp}.xlsx"
    wb.save(path)
    return path
