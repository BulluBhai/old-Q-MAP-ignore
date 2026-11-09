"""PDF summary report (reportlab). Disclaimer, sample sizes and limitations on the first pages."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from qlopb.config import settings as cfg


def _f(v, d=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    return f"{v:.{d}f}" if isinstance(v, (float, np.floating)) else str(v)


def write_pdf(res, folder, stamp, charts=None) -> Path:
    path = Path(folder) / f"QLOPB_MA_Affinity_Report_{stamp}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=f"QLOPB MA Affinity - {res.label}")
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=8.5, leading=11)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#444444"))
    h = ss["Heading2"]
    s = res.settings
    di = res.data_info
    counts = res.counts()
    st = [Paragraph("QLOPB - MA Affinity research report", ss["Title"]),
          Paragraph(f"<b>{res.label}</b> &nbsp;|&nbsp; {dt.datetime.now().strftime(cfg.DATETIME_FMT)}", body),
          Spacer(1, 0.2 * cm),
          Paragraph("<b>" + cfg.DISCLAIMER_TEXT + "</b>", body), Spacer(1, 0.3 * cm),
          Paragraph("Data and sample sizes", h),
          Paragraph(f"{di['n_bars']} bars ({di['frequency']}), {di['first']} to {di['last']}. "
                    f"In-sample: {di['is_bars']} bars ({di['is_first']} to {di['is_last']}). "
                    f"Out-of-sample: {di['oos_bars']} bars ({di['oos_first']} to {di['oos_last']}).", body),
          Paragraph(f"Candidates tested: {len(res.results)} &nbsp; ranked (enough IS interactions): "
                    f"{counts.get('OK', 0)} &nbsp; insufficient data: {counts.get('INSUFFICIENT_DATA', 0)} "
                    f"&nbsp; no interactions: {counts.get('NO_INTERACTIONS', 0)}. "
                    f"Minimum interactions: {s.min_interactions}.", body)]
    if res.warnings:
        st.append(Paragraph("Warnings", h))
        st += [Paragraph("- " + w, body) for w in res.warnings]
    st.append(Paragraph("Limitations", h))
    st += [Paragraph("- " + t, small) for t in cfg.LIMITATIONS]
    st.append(PageBreak())

    st.append(Paragraph(f"Frozen Top-{s.top_n} (ranked on in-sample data only)", h))
    hdr = ["Rank", "MA", "IS aff.", "IS n", "IS succ %", "IS rel.", "IS p (uncorr.)",
           "OOS status", "OOS n", "OOS outc.", "OOS succ %", "Consistency", "Cons. status"]
    data = [hdr]
    for r in res.frozen_top_results():
        data.append([r["rank"], r["ma_label"], _f(r["is_affinity_score"]), r["is_n"], _f(r["is_overall_sr"]),
                     _f(r["is_reliability"]), _f(r["is_p_value"], 4), r["oos_status"], _f(r["oos_n"], 0),
                     _f(r.get("oos_n_outcomes"), 0), _f(r["oos_overall_sr"]),
                     _f(r["is_oos_consistency_score"]), r["is_oos_consistency_status"]])
    if len(data) == 1:
        data.append(["-"] * len(hdr))
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE6F0")),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7),
                           ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    st += [t, Spacer(1, 0.2 * cm),
           Paragraph("'-' means not available (missing), not zero. OOS columns were calculated after the "
                     "Top-N was frozen and never changed a rank. Forward Return uses the V2 Directed IR "
                     "formula, pending owner review. p-values are not corrected for the number of "
                     "candidates tested.", small)]
    for c in (charts or {}).values():
        try:
            st.append(PageBreak())
            img = Image(str(c))
            sc = min((landscape(A4)[0] - 3 * cm) / img.drawWidth, (landscape(A4)[1] - 4 * cm) / img.drawHeight)
            img.drawWidth *= sc
            img.drawHeight *= sc
            st.append(img)
        except Exception:
            st.append(Paragraph(f"[chart {Path(str(c)).name} could not be embedded]", small))
    doc.build(st)
    return path
