"""
Research engine: runs the MA Affinity research workflow end to end.

Flow (fixed, as approved for V2):
   1. check settings and data
   2. IS: detect interactions and score EVERY candidate on in-sample data only
   3. rank on IS scores only, FREEZE the Top-N
   4. OOS: detect and score the frozen Top-N independently (or all, if asked)
   5. IS/OOS consistency is reported separately and never changes a rank

The engine does no GUI work and no file output (run_full_pipeline at the bottom
wires loading, research and reporting together).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from qlopb.analysis.affinity_engine import score_window
from qlopb.analysis.interaction_engine import build_interaction_records, detect_interaction_episodes
from qlopb.config import settings as cfg
from qlopb.config.settings import MAResearchSettings
from qlopb.core.timeframe_engine import resample_ohlc
from qlopb.core.validation import check_data_for_settings, validate_ohlc_frame
from qlopb.references.moving_average import compute_ma
from qlopb.storage.file_provider import FileProvider, RunLog, make_stamp, safe_name
from qlopb.validation.is_oos import compute_split, consistency, freeze_top_n, rank_candidates
from qlopb.validation.robustness import near_duplicate_pairs, neighbour_summary


class ResearchError(Exception):
    """The research run cannot proceed (message is plain English)."""


class RunCancelled(Exception):
    pass


def horizon_label(period: int) -> str:
    """V2 description label (descriptive only)."""
    if period <= 30: return "Short-term"
    if period <= 75: return "Short/Med"
    if period <= 150: return "Medium-term"
    if period <= 250: return "Med/Long"
    return "Long-term"


def _stamp(ts) -> str:
    ts = pd.Timestamp(ts)
    return ts.strftime(cfg.DATE_FMT if (ts.hour == 0 and ts.minute == 0) else cfg.DATETIME_FMT)


@dataclass
class ResearchResult:
    label: str
    settings: MAResearchSettings
    results: list                      # one dict per candidate
    interactions: pd.DataFrame
    data_info: dict
    frozen_top: list                   # [(ma_type, period), ...] in rank order
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    near_duplicates: list = field(default_factory=list)
    quality: object = None             # DataQualityReport or None
    seconds: float = 0.0
    price_frame: pd.DataFrame | None = None

    def frozen_top_results(self) -> list:
        lookup = {(r["ma_type"], r["ma_period"]): r for r in self.results}
        return [lookup[k] for k in self.frozen_top]

    def counts(self) -> dict:
        c = {"OK": 0, "INSUFFICIENT_DATA": 0, "NO_INTERACTIONS": 0}
        for r in self.results:
            c[r["is_status"]] = c.get(r["is_status"], 0) + 1
        return c


def run_ma_affinity(df: pd.DataFrame, settings: MAResearchSettings, label: str = "instrument",
                    progress=None, log=None, quality=None, cancel=None) -> ResearchResult:
    """progress(done, total, text); log(text); cancel() -> True to stop."""
    t0 = time.time()
    say = log or (lambda m: None)
    tick = progress or (lambda d, t, m: None)
    settings.check()
    problems = validate_ohlc_frame(df)
    if problems:
        raise ResearchError("The price table is not usable:\n- " + "\n- ".join(problems))

    notes, warnings = [], []
    df, tf_notes = resample_ohlc(df, settings.timeframe)
    notes.extend(tf_notes)
    errors, warns = check_data_for_settings(df, settings)
    if errors:
        raise ResearchError("\n".join(errors))
    warnings.extend(warns)

    close = df["close"].to_numpy(dtype=np.float64)
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)
    index = df.index
    n = len(df)
    is_end, oos_start = compute_split(n, settings.is_pct)
    pw = settings.primary_window
    fwd = list(settings.fwd_windows)
    # Regime MA (V2): only available when there are more bars than its period.
    reg = settings.regime_ma
    regime_ma = (pd.Series(close).rolling(reg, min_periods=reg).mean().to_numpy()
                 if n > reg else np.full(n, np.nan))

    candidates = [(mt, p) for mt in settings.ma_types
                  for p in range(settings.ma_start, settings.ma_end + 1)]
    total = len(candidates)
    freq_label = quality.inferred_frequency if quality is not None else "as loaded"
    data_info = {
        "n_bars": n, "first": _stamp(index[0]), "last": _stamp(index[-1]),
        "is_bars": is_end + 1, "oos_bars": n - oos_start,
        "is_first": _stamp(index[0]), "is_last": _stamp(index[is_end]),
        "oos_first": _stamp(index[oos_start]) if oos_start < n else "",
        "oos_last": _stamp(index[-1]) if oos_start < n else "",
        "frequency": freq_label, "timeframe_setting": settings.timeframe}
    say(f"Data: {n} bars, {data_info['first']} to {data_info['last']}. "
        f"IS {data_info['is_bars']} bars ({data_info['is_first']} to {data_info['is_last']}), "
        f"OOS {data_info['oos_bars']} bars.")
    say(f"Candidates: {total} ({', '.join(settings.ma_types)}, periods {settings.ma_start}-{settings.ma_end}). "
        f"Primary forward window {pw} bars.")

    # ---- Phase 1: IS detection + scoring for every candidate ----------------
    say("Phase 1/3: in-sample scoring of all candidates...")
    results, is_state, all_records = [], {}, []
    for k, (mt, period) in enumerate(candidates):
        if cancel and cancel():
            raise RunCancelled("Run cancelled by user.")
        tick(k, total, f"IS {mt}-{period}")
        ma = compute_ma(close, mt, period)
        events, final_iz, final_lev = detect_interaction_episodes(
            high, low, ma, 0, is_end, is_end, pw, settings.proximity_pct,
            settings.cooldown_bars, initial_in_zone=False, last_event_bar=-(period + 1))
        recs = build_interaction_records(events, ma, mt, period, is_end,
                                         close, high, low, index, regime_ma, fwd)
        sc = score_window(recs, settings)
        is_state[(mt, period)] = (final_iz, final_lev)
        results.append({
            "ma_type": mt, "ma_period": period, "ma_label": f"{mt}-{period}",
            "horizon": horizon_label(period), "rank": None, "rank_tie": False,
            **{f"is_{key}": v for key, v in sc.items()},
            # OOS fields start as 'not evaluated' (missing, not zero)
            "oos_status": "NOT_EVALUATED", "oos_n": np.nan, "oos_overall_sr": np.nan,
            "oos_n_outcomes": np.nan, "oos_affinity_score": np.nan,
            "is_oos_sr_diff": np.nan, "is_oos_consistency_raw": np.nan,
            "is_oos_consistency_score": np.nan, "is_oos_consistency_status": "NOT_EVALUATED"})
        all_records.extend({"period_type": "IS", **r} for r in recs)
    tick(total, total, "IS scoring complete")

    # ---- Phase 2: rank on IS only, freeze Top-N -----------------------------
    say("Phase 2/3: ranking on in-sample scores only and freezing the Top-N...")
    rank_candidates(results)
    frozen = freeze_top_n(results, settings.top_n)
    n_ok = sum(1 for r in results if r["is_status"] == "OK")
    say(f"{n_ok} of {total} candidates have enough in-sample interactions "
        f"(min {settings.min_interactions}). Frozen Top-{len(frozen)}: "
        + ", ".join(f"{t}-{p}" for t, p in frozen))
    if n_ok == 0:
        warnings.append("No candidate reached the minimum number of in-sample interactions, so "
                        "nothing was ranked. This means 'insufficient data', not 'poor results'.")
    elif len(frozen) < settings.top_n:
        warnings.append(f"Only {len(frozen)} candidates qualified for the Top-{settings.top_n} list.")
    ties = sorted({r["rank"] for r in results if r.get("rank_tie") and r["rank"] <= settings.top_n})
    if ties:
        warnings.append("Equal IS scores inside the Top-N (ranks " + ", ".join(map(str, ties))
                        + "): their order is arbitrary (candidate order).")
    dup_pairs = near_duplicate_pairs(frozen)
    if dup_pairs:
        warnings.append("Near-duplicate neighbours in the Top-N (periods within 3): "
                        + "; ".join(f"{a}/{b}" for a, b in dup_pairs) + ".")

    # ---- Phase 3: independent OOS ------------------------------------------
    to_eval = set(frozen) if settings.oos_scope == "top_n" else {(r["ma_type"], r["ma_period"]) for r in results}
    say(f"Phase 3/3: out-of-sample validation of {len(to_eval)} candidate(s) "
        f"(scope: {settings.oos_scope}). OOS never changes ranks.")
    lookup = {(r["ma_type"], r["ma_period"]): r for r in results}
    todo = [c for c in candidates if c in to_eval]
    for j, (mt, period) in enumerate(todo):
        if cancel and cancel():
            raise RunCancelled("Run cancelled by user.")
        tick(j, max(len(todo), 1), f"OOS {mt}-{period}")
        ma = compute_ma(close, mt, period)
        iz, lev = is_state[(mt, period)]
        events, _, _ = detect_interaction_episodes(
            high, low, ma, oos_start, n - 1, n - 1, pw, settings.proximity_pct,
            settings.cooldown_bars, initial_in_zone=iz, last_event_bar=lev)
        recs = build_interaction_records(events, ma, mt, period, n - 1,
                                         close, high, low, index, regime_ma, fwd)
        sc = score_window(recs, settings)
        r = lookup[(mt, period)]
        for key, v in sc.items():
            r[f"oos_{key}"] = v
        cons = consistency(r["is_overall_sr"], r["oos_overall_sr"], sc["n_outcomes"],
                           settings.min_oos_outcomes_for_consistency)
        r["is_oos_sr_diff"] = cons["diff"]
        r["is_oos_consistency_raw"] = cons["raw"]
        r["is_oos_consistency_score"] = cons["value"]
        r["is_oos_consistency_status"] = cons["status"]
        all_records.extend({"period_type": "OOS", **x} for x in recs)
    tick(len(todo), max(len(todo), 1), "OOS complete")

    for r in results:
        if r["rank"] and r["rank"] <= settings.top_n:
            r.update({f"nbr_{k}": v for k, v in neighbour_summary(results, r["ma_type"], r["ma_period"]).items()})

    inter = pd.DataFrame(all_records) if all_records else pd.DataFrame()
    secs = time.time() - t0
    say(f"Research finished in {secs:.1f}s. {len(inter)} interactions recorded.")
    return ResearchResult(label=label, settings=settings, results=results, interactions=inter,
                          data_info=data_info, frozen_top=frozen, warnings=warnings, notes=notes,
                          near_duplicates=dup_pairs, quality=quality, seconds=secs, price_frame=df)


# ── Full pipeline: file -> clean data -> research -> reports ───────────────
def run_full_pipeline(path, settings: MAResearchSettings, output_root=None, load_options=None,
                      make_excel=True, make_charts=True, make_pdf=True,
                      progress=None, log=None, cancel=None, label=None,
                      save_processed_copy=True) -> dict:
    """Run everything for one file and return a dict of output paths and the result."""
    from qlopb.core.data_engine import LoadOptions, load_file, save_processed

    runlog = RunLog(callback=log)
    stamp = make_stamp()
    label = label or safe_name(__import__("pathlib").Path(path).stem)
    fp = FileProvider(output_root)
    folder = fp.new_run_folder(label, stamp)
    outputs = {"folder": folder}
    try:
        runlog.info(f"Loading {path}")
        loaded = load_file(path, load_options or LoadOptions())
        for line in loaded.report.to_text().splitlines():
            runlog.info("DATA  " + line)
        if save_processed_copy:
            outputs.update(save_processed(loaded, folder, stamp))
        res = run_ma_affinity(loaded.df, settings, label=label, progress=progress,
                              log=runlog.info, quality=loaded.report, cancel=cancel)
        for w in res.warnings:
            runlog.warn(w)
        outputs["result"] = res
        if make_charts or make_pdf:
            from qlopb.reports.chart_report import make_charts as _charts
            outputs["charts"] = _charts(res, folder, stamp)
            runlog.info(f"{len(outputs['charts'])} chart(s) written")
        if make_excel:
            from qlopb.reports.excel_report import write_excel
            outputs["excel"] = write_excel(res, folder, stamp, outputs.get("charts"))
            runlog.info(f"Excel: {outputs['excel'].name}")
        if make_pdf:
            from qlopb.reports.pdf_report import write_pdf
            outputs["pdf"] = write_pdf(res, folder, stamp, outputs.get("charts"))
            runlog.info(f"PDF: {outputs['pdf'].name}")
        runlog.info("Finished.")
        status = "COMPLETED WITH WARNINGS" if runlog.warnings else "SUCCESS"
    except RunCancelled:
        runlog.warn("Cancelled by user.")
        status = "CANCELLED"
    except Exception as e:
        runlog.error(f"{type(e).__name__}: {e}")
        outputs["error"] = e
        status = "FAILED"
    outputs["status"] = status
    outputs["log"] = runlog.save(fp.out_path(folder, "run_log", "log", stamp))
    return outputs
