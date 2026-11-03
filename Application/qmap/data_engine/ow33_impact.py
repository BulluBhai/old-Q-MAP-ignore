"""OW-33 step 1 (owner decision D5-49, 03-Nov-26): READ-ONLY impact report for Option C (sparse-only alignment).

Option C, if it were adopted: a sampled block whose dates all have ONE bar each, at VARYING local times of day, is
treated as missing observations (not measured) instead of a day interval - but only when another sampled block of the
same file measures a minute interval. Every other rule of the approved DQ-7 sampling is unchanged; in particular a
regular whole-multiple block still disagrees (MIXED).

This module does NOT change sampling, any dataset, the registry or any file. It reconstructs, for every active MIXED
cleaned dataset, the timestamps in the original FILE order from the stored standardised data (src_row) and the
recorded removal of exact duplicates, verifies that the recorded sampling seed and result are reproduced exactly, and
then evaluates Option C on the same blocks. A dataset whose seed or result cannot be reproduced is reported as
"not evaluable" with the reason; nothing is guessed.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

from . import timeframe_infer as T

SAME_TIME_SHARE = 0.9  # the same share the full-file check uses for "one time of day" (validation.SAME_TIME_SHARE)


@dataclass
class OptionCResult:
    status: str                  # consistent | mixed | insufficient
    timeframe: str | None
    excluded_blocks: list = field(default_factory=list)  # 1-based start rows of blocks treated as missing data
    patterns: dict = field(default_factory=dict)


def _is_sparse_block(part: list, zone: ZoneInfo) -> bool:
    """One distinct timestamp per date (no intraday steps) and times of day that vary (< SAME_TIME_SHARE alike)."""
    inst = [k for k in part if isinstance(k, datetime)]
    if len(inst) < T.MIN_STEPS + 1:
        return False
    local = [k.astimezone(zone) for k in inst]
    per_date: dict = {}
    for k in local:
        per_date.setdefault(k.date(), set()).add(k)
    if any(len(v) > 1 for v in per_date.values()):
        return False
    times = Counter(k.timetz().replace(tzinfo=None) for k in local)
    return times.most_common(1)[0][1] < SAME_TIME_SHARE * len(local)


def evaluate_option_c(keys: list, zone: str | None, config: dict | None = None) -> tuple[T.Inference, OptionCResult]:
    """(today's inference, Option C result) on the same blocks. Today's inference is computed by the unchanged
    timeframe_infer.infer_interval; Option C re-applies its agreement rule without the excluded blocks."""
    cfg = {**T.DEFAULT_SAMPLING, **(config or {})}
    today = T.infer_interval(keys, zone=zone, config=cfg)
    z = ZoneInfo(zone or "UTC")
    n = len(keys)
    size = n if (n < 2 * max(cfg["block_rows"], T.MIN_STEPS + 1)) else max(cfg["block_rows"], T.MIN_STEPS + 1)
    measured = []
    any_minutes = any(T._is_minutes(b.interval) for b in today.blocks if b.interval)
    excluded = []
    for b in today.blocks:
        if b.interval is None:
            continue
        part = keys[b.start_row - 1:b.start_row - 1 + size]
        if any_minutes and not T._is_minutes(b.interval) and _is_sparse_block(part, z):
            excluded.append(b.start_row)
            continue
        measured.append((b, part))
    res = OptionCResult(T.INSUFFICIENT, None, excluded)
    if not measured:
        return today, res
    counts = Counter(b.interval for b, _p in measured)
    dominant = counts.most_common(1)[0][0]
    unit = T._base_unit(dominant)
    agrees = []
    for b, part in measured:
        days = T._local_dates(part, z)
        _l, steps, _u = T._label_from_steps(part, days, T._is_intraday(part, days))
        multiples = [s for s in steps if s % unit == 0] if unit > 1 else steps
        share = len(multiples) / len(steps) if steps else 0.0
        has_base = b.interval == dominant or steps.count(unit) >= max(1, len(steps) // 10)
        same_kind = T._is_minutes(b.interval) == T._is_minutes(dominant)
        agrees.append(same_kind and share >= cfg["consistency_share"] and has_base)
    res.patterns = dict(counts)
    if all(agrees):
        res.status, res.timeframe = T.CONSISTENT, dominant
    else:
        res.status, res.timeframe = T.MIXED_STATUS, T.MIXED
    return today, res


# ---- registry (read-only) -----------------------------------------------------------------------------------------
REPORT_COLUMNS = ["dataset_id", "instrument", "display_name", "source_file", "current_classification",
                  "proposed_classification_option_c", "would_change", "reason", "recorded_seed", "seed_reproduced",
                  "blocks", "excluded_blocks", "derived_datasets", "runs_using_dataset", "processing_and_lineage"]


def open_read_only(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _file_order_keys(conn, data_path, attempt) -> tuple[list | None, str, str | None]:
    """(keys in file order, why not, zone) for the file of one ingest attempt."""
    n = attempt["rows_read"] or 0
    rules = json.loads(attempt["datetime_rules_json"] or "{}")
    prof = rules.get("profile", {})
    zone = prof.get("exchange_timezone") or prof.get("timezone") or "UTC"
    keys: list = [None] * n
    kids = conn.execute("SELECT relative_path FROM datasets WHERE created_by_attempt_id = ? AND layer = 'cleaned'",
                        (attempt["attempt_id"],)).fetchall()
    for kid in kids:
        path = data_path(kid["relative_path"])
        if not Path(path).is_file():
            return None, f"stored file missing: {kid['relative_path']}", zone
        tab = pq.read_table(str(path), columns=["src_row", "timestamp_utc", "session_date"])
        rows = tab.column("src_row").to_pylist()
        ts = tab.column("timestamp_utc").to_pylist()
        sd = tab.column("session_date").to_pylist()
        for r, t, d in zip(rows, ts, sd):
            if 1 <= r <= n:
                keys[r - 1] = t if t is not None else d
    for step in json.loads(attempt["transformations_json"] or "[]"):
        if isinstance(step, dict) and step.get("step") == "exact_duplicates_removed":
            for removed, kept in step.get("removed_source_row_and_kept_source_row", []):
                if 1 <= removed <= n and 1 <= kept <= n:
                    keys[removed - 1] = keys[kept - 1]
    missing = sum(1 for k in keys if k is None)
    if missing:
        return None, f"{missing} source row(s) cannot be placed in file order (e.g. rows of another source group)", zone
    return keys, "", zone


def impact_rows(conn, data_path) -> list[dict]:
    """One row per active cleaned MIXED dataset. `data_path(relative_path)` -> absolute Path (Settings.data_path)."""
    out = []
    sel = conn.execute(
        "SELECT d.dataset_id, d.created_by_attempt_id, i.exchange, i.symbol, i.name FROM datasets d "
        "JOIN instruments i ON i.instrument_id = d.instrument_id "
        "WHERE d.layer = 'cleaned' AND d.status = 'active' AND d.timeframe = 'MIXED' ORDER BY d.dataset_id").fetchall()
    for d in sel:
        attempt = conn.execute("SELECT * FROM ingest_attempts WHERE attempt_id = ?",
                               (d["created_by_attempt_id"],)).fetchone()
        src = conn.execute("SELECT e.original_filename FROM ingest_attempts a JOIN ingest_events e USING (event_id) "
                           "WHERE a.attempt_id = ?", (d["created_by_attempt_id"],)).fetchone()
        derived = [r[0] for r in conn.execute("SELECT dataset_id FROM datasets WHERE parent_dataset_id = ? "
                                              "AND layer = 'timeframe'", (d["dataset_id"],))]
        runs = conn.execute("SELECT COUNT(*) FROM run_inputs WHERE dataset_id = ?", (d["dataset_id"],)).fetchone()[0]
        row = {"dataset_id": d["dataset_id"], "instrument": f"{d['exchange']}:{d['symbol']}",
               "display_name": d["name"] or "", "source_file": src[0] if src else "",
               "current_classification": "MIXED", "derived_datasets": " ".join(map(str, derived)) or "none",
               "runs_using_dataset": runs}
        rules = json.loads(attempt["datetime_rules_json"] or "{}") if attempt else {}
        rec = rules.get("timeframe_inference") or {}
        row["recorded_seed"] = rec.get("seed", "")
        row["blocks"] = "; ".join(f"{b['start_row']}:{b['interval']}" for b in rec.get("blocks", []))
        cfg = json.loads(attempt["validation_settings_json"] or "{}").get("timeframe_sampling") if attempt else None
        keys, why, zone = _file_order_keys(conn, data_path, attempt) if attempt else (None, "no ingest attempt", None)
        if keys is None or not rec:
            row.update(proposed_classification_option_c="not evaluable", would_change="unknown", seed_reproduced="no",
                       excluded_blocks="", reason=why or "no recorded timeframe inference")
        else:
            today, opt = evaluate_option_c(keys, zone, cfg)
            ok = today.seed == rec.get("seed") and today.status == rec.get("status")
            row["seed_reproduced"] = "yes" if ok else "no"
            row["excluded_blocks"] = " ".join(map(str, opt.excluded_blocks))
            if not ok:
                row.update(proposed_classification_option_c="not evaluable", would_change="unknown",
                           reason=f"recorded sampling not reproduced (seed {today.seed} vs {rec.get('seed')}, "
                                  f"status {today.status} vs {rec.get('status')}); nothing assumed")
            else:
                proposed = opt.timeframe or "INSUFFICIENT"
                change = proposed != "MIXED"
                row.update(proposed_classification_option_c=proposed, would_change="yes" if change else "no",
                           reason=(f"{len(opt.excluded_blocks)} sampled block(s) of one-bar dates at varying times "
                                   f"(rows {row['excluded_blocks']}) would count as missing observations; remaining "
                                   f"blocks: {opt.patterns}") if change else
                           ("no sparse one-bar block; MIXED comes from other intervals" if not opt.excluded_blocks
                            else f"sparse block(s) excluded, but the remaining blocks still disagree: {opt.patterns}"))
        row["processing_and_lineage"] = _lineage_note(row, derived, runs)
        out.append(row)
    return out


def _lineage_note(row, derived, runs) -> str:
    if row.get("would_change") != "yes":
        return ("unchanged label; under a vs3 identity change it would still be processed once more (new number, "
                "same content, old one superseded)")
    note = (f"would be re-registered as {row['proposed_classification_option_c']} (new dataset and storage path, since "
            "the timeframe is part of the path); this dataset kept and marked superseded; nothing deleted")
    if derived:
        note += f"; derived dataset(s) {' '.join(map(str, derived))} stay linked to it and are not rebuilt (OW-32)"
    if runs:
        note += f"; {runs} earlier run(s) keep it as their recorded input"
    return note


def summary(rows: list[dict]) -> dict:
    return {"mixed_datasets": len(rows), "would_change": sum(r["would_change"] == "yes" for r in rows),
            "unchanged": sum(r["would_change"] == "no" for r in rows),
            "not_evaluable": sum(r["would_change"] == "unknown" for r in rows)}


def write_report(rows: list[dict], folder: Path, stamp: str) -> tuple[Path, Path]:
    import csv

    folder.mkdir(parents=True, exist_ok=True)
    csv_path = folder / f"OW33_Impact_Report_{stamp}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=REPORT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    s = summary(rows)
    txt = folder / f"OW33_Impact_Summary_{stamp}.txt"
    txt.write_text(
        "OW-33 step 1 - read-only impact report for Option C (sparse-only alignment)\n"
        f"Active MIXED datasets examined: {s['mixed_datasets']}\n"
        f"Would change classification:    {s['would_change']}\n"
        f"Would stay MIXED:               {s['unchanged']}\n"
        f"Not evaluable (see reason):     {s['not_evaluable']}\n"
        "Nothing was changed: no dataset, registry entry or file was written except this report.\n"
        "Option C, the vs3 identity change and any reprocessing are NOT applied (owner approval required).\n",
        encoding="utf-8")
    return csv_path, txt


__all__ = ["OptionCResult", "REPORT_COLUMNS", "evaluate_option_c", "impact_rows", "open_read_only", "summary",
           "write_report"]
