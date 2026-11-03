"""OW-33 step 1 (owner decision D5-49, 03-Nov-26): READ-ONLY impact report for Option C (sparse-only alignment).

Option C, if it were adopted: a sampled block whose dates all have ONE bar each, at VARYING local times of day, is
treated as missing observations (not measured) instead of a day interval - but only when another sampled block of the
same inference measures a minute interval. Every other rule of the approved DQ-7 sampling is unchanged; in particular
a regular whole-multiple block still disagrees (MIXED). Option C is evaluated here only; the production sampling
(`timeframe_infer.py`) is not changed.

What the registered inference was computed on (process.py, `_settle_timeframe`): ONE inference per ingest attempt,
over the parsed timestamps of EVERY row of the file, in file order, before the rows are split into instrument groups;
every cleaned dataset of that attempt registers that same timeframe. The exact input of one dataset's inference is
therefore the whole file's sequence. It is rebuilt only if it can be PROVEN complete and exact:

1. every cleaned dataset created by the attempt (all statuses) is read; each stored row's `src_row` (1-based file
   position) must be unique across them, inside 1..rows_read, with a key; each file's row count must equal the
   registry's;
2. the attempt's recorded exact-duplicate removals (`removed_source_row_and_kept_source_row`, count included) fill the
   removed positions with their kept row's timestamp (an exact duplicate is identical in every column, so also in time);
   a removed row must not be stored, its kept row must be;
3. every position 1..rows_read must then be filled exactly once;
4. the unchanged sampling is re-run on the rebuilt sequence with the recorded configuration and must reproduce the
   recorded evidence exactly: observation count, seed, candidate, number of blocks, every block's start row, size,
   measured interval, step count, agreeing share and agreement, the block patterns, rows examined, status, timeframe
   and the registered timeframe.

Any failure -> NOT EVALUABLE with the precise reason, and no Option C conclusion for that dataset. Nothing is
written anywhere except the report files (CSV and summary) in the folder the caller gives.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

from . import timeframe_infer as T

NOT_EVALUABLE = "NOT EVALUABLE"
SAME_TIME_SHARE = 0.9  # the share the full-file check uses for "one time of day" (validation.SAME_TIME_SHARE)


# ---- Option C on given blocks -------------------------------------------------------------------------------------
def sparse_test(part: list, zone: ZoneInfo) -> dict:
    """Why a block does or does not qualify as a sparse one-bar-date stretch."""
    inst = [k for k in part if isinstance(k, datetime)]
    if len(inst) != len(part) or len(inst) < T.MIN_STEPS + 1:
        return {"qualifies": False, "why": "not timestamps with a time of day (date-only or too short)"}
    local = [k.astimezone(zone) for k in inst]
    per_date: dict = {}
    for k in local:
        per_date.setdefault(k.date(), set()).add(k)
    max_bars = max(len(v) for v in per_date.values())
    distinct = sorted({k for k in local})
    times = Counter(k.time() for k in distinct)
    top = times.most_common(1)[0][1]
    share = top / len(distinct)
    facts = (f"{len(part)} rows, {len(per_date)} date(s), at most {max_bars} distinct bar(s) per date, "
             f"{len(times)} distinct time(s) of day, most common time {top}/{len(distinct)} = {share:.0%}")
    if max_bars > 1:
        return {"qualifies": False, "why": facts + ": some date has several bars (intraday steps exist)"}
    if share >= SAME_TIME_SHARE:
        return {"qualifies": False, "why": facts + f": one time of day (>= {SAME_TIME_SHARE:.0%}), a daily grid"}
    return {"qualifies": True, "why": facts + f": one bar per date at varying times (< {SAME_TIME_SHARE:.0%} alike)"}


@dataclass
class OptionC:
    status: str
    timeframe: str | None
    dominant: str | None
    blocks: list = field(default_factory=list)  # per block: original evidence + sparse test + role + agrees_under_c

    @property
    def excluded(self) -> list:
        return [b["start_row"] for b in self.blocks if b["role"] == "excluded"]


def evaluate_option_c(keys: list, zone: str | None, config: dict | None = None,
                      original: T.Inference | None = None) -> tuple[T.Inference, OptionC]:
    """(original inference by the unchanged sampling, Option C on the same blocks)."""
    cfg = {**T.DEFAULT_SAMPLING, **(config or {})}
    orig = original or T.infer_interval(keys, zone=zone, config=cfg)
    z = ZoneInfo(zone or "UTC")
    any_minutes = any(T._is_minutes(b.interval) for b in orig.blocks if b.interval)
    rows, used = [], []
    for b in orig.blocks:
        part = keys[b.start_row - 1:b.start_row - 1 + b.rows]
        row = {"start_row": b.start_row, "rows": b.rows, "interval": b.interval, "steps": b.steps,
               "agreeing_share": round(b.agreeing_share, 3), "agrees_original": b.agrees}
        if b.interval is None:
            row.update(sparse="", role="not measured", agrees_under_c="")
        elif T._is_minutes(b.interval):
            row.update(sparse="minute interval: never excluded", role="used")
            used.append((row, part))
        else:
            st = sparse_test(part, z)
            if st["qualifies"] and any_minutes:
                row.update(sparse=st["why"], role="excluded", agrees_under_c="")
            else:
                why = st["why"] if any_minutes else st["why"] + "; no minute block in this inference: never excluded"
                row.update(sparse=why, role="used")
                used.append((row, part))
        rows.append(row)
    res = OptionC(T.INSUFFICIENT, None, None, rows)
    if not used:
        return orig, res
    dominant = Counter(r["interval"] for r, _p in used).most_common(1)[0][0]
    unit = T._base_unit(dominant)
    for r, part in used:  # the approved agreement rule, unchanged (timeframe_infer.infer_interval, steps 3/4)
        days = T._local_dates(part, z)
        _l, steps, _u = T._label_from_steps(part, days, T._is_intraday(part, days))
        multiples = [s for s in steps if s % unit == 0] if unit > 1 else steps
        share = len(multiples) / len(steps) if steps else 0.0
        has_base = r["interval"] == dominant or steps.count(unit) >= max(1, len(steps) // 10)
        same_kind = T._is_minutes(r["interval"]) == T._is_minutes(dominant)
        r["agrees_under_c"] = same_kind and share >= cfg["consistency_share"] and has_base
    res.dominant = dominant
    if all(r["agrees_under_c"] for r, _p in used):
        res.status, res.timeframe = T.CONSISTENT, dominant
    else:
        res.status, res.timeframe = T.MIXED_STATUS, T.MIXED
    return orig, res


# ---- exact reconstruction (read-only) -----------------------------------------------------------------------------
@dataclass
class Reconstruction:
    keys: list | None
    reason: str = ""
    attempt_id: int | None = None
    rows_read: int = 0
    stored_rows: int = 0
    removed_rows: int = 0
    siblings: list = field(default_factory=list)
    zone: str | None = None
    config: dict | None = None
    record: dict | None = None


def open_read_only(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fail(rec: Reconstruction, why: str) -> Reconstruction:
    rec.keys, rec.reason = None, why
    return rec


def reconstruct_input(conn, data_path, dataset_id: int) -> Reconstruction:
    rec = Reconstruction(None)
    d = conn.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
    if d is None or d["layer"] != "cleaned":
        return _fail(rec, "not a cleaned dataset")
    a = conn.execute("SELECT * FROM ingest_attempts WHERE attempt_id = ?", (d["created_by_attempt_id"],)).fetchone()
    if a is None:
        return _fail(rec, "the ingest attempt that created the dataset is not recorded")
    rec.attempt_id, rec.rows_read = a["attempt_id"], int(a["rows_read"] or 0)
    if a["outcome"] != "accepted":
        return _fail(rec, f"the creating attempt's outcome is {a['outcome']!r}, not 'accepted'")
    try:
        rules = json.loads(a["datetime_rules_json"] or "{}")
        vset = json.loads(a["validation_settings_json"] or "{}")
        steps = json.loads(a["transformations_json"] or "[]")
    except ValueError as exc:
        return _fail(rec, f"the attempt's recorded evidence is not readable JSON ({exc})")
    rec.record = rules.get("timeframe_inference")
    rec.config = vset.get("timeframe_sampling")
    prof = rules.get("profile") or {}
    rec.zone = prof.get("exchange_timezone") or prof.get("timezone") or "UTC"
    if not rec.record:
        return _fail(rec, "no recorded timeframe inference for the attempt")
    if not rec.config:
        return _fail(rec, "the sampling configuration used is not recorded")
    if rec.record.get("rows_total") != rec.rows_read:
        return _fail(rec, f"recorded observation count {rec.record.get('rows_total')} differs from the attempt's "
                          f"rows read {rec.rows_read}")
    sibs = conn.execute("SELECT dataset_id, relative_path, row_count, timeframe FROM datasets WHERE "
                        "created_by_attempt_id = ? AND layer = 'cleaned' ORDER BY dataset_id", (a["attempt_id"],)).fetchall()
    rec.siblings = [s["dataset_id"] for s in sibs]
    registered = rec.record.get("registered")
    other_tf = [s["dataset_id"] for s in sibs if s["timeframe"] != registered]
    if other_tf:
        return _fail(rec, f"dataset(s) {other_tf} of the same attempt are not registered as {registered}; the shared "
                          "inference cannot be attributed safely")
    n = rec.rows_read
    keys: list = [None] * n
    filled = [False] * n
    kinds = set()
    for s in sibs:
        path = Path(data_path(s["relative_path"]))
        if not path.is_file():
            return _fail(rec, f"stored file of dataset {s['dataset_id']} is missing ({s['relative_path']})")
        tab = pq.read_table(str(path), columns=["src_row", "timestamp_utc", "session_date"])
        if tab.num_rows != s["row_count"]:
            return _fail(rec, f"dataset {s['dataset_id']} has {tab.num_rows} stored rows, the registry says "
                              f"{s['row_count']}")
        for r, t, dd in zip(tab.column("src_row").to_pylist(), tab.column("timestamp_utc").to_pylist(),
                            tab.column("session_date").to_pylist()):
            if r is None or not 1 <= r <= n:
                return _fail(rec, f"dataset {s['dataset_id']} has src_row {r} outside 1..{n}")
            if filled[r - 1]:
                return _fail(rec, f"source row {r} is stored more than once (dataset {s['dataset_id']})")
            k = t if t is not None else dd
            if k is None:
                return _fail(rec, f"source row {r} has no timestamp in dataset {s['dataset_id']}")
            kinds.add("instant" if t is not None else "date")
            keys[r - 1], filled[r - 1] = k, True
            rec.stored_rows += 1
    if len(kinds) > 1:
        return _fail(rec, "the stored rows mix timestamps and date-only values")
    dup_steps = [x for x in steps if isinstance(x, dict) and x.get("step") == "exact_duplicates_removed"]
    for x in dup_steps:
        pairs = x.get("removed_source_row_and_kept_source_row")
        if not isinstance(pairs, list) or x.get("count") != len(pairs):
            return _fail(rec, "the duplicate-removal record is incomplete (count and listed rows differ)")
        for pair in pairs:
            try:
                removed, kept = int(pair[0]), int(pair[1])
            except (TypeError, ValueError, IndexError):
                return _fail(rec, f"unreadable duplicate-removal entry {pair!r}")
            if not (1 <= removed <= n and 1 <= kept <= n):
                return _fail(rec, f"duplicate-removal entry {removed}->{kept} outside 1..{n}")
            if filled[removed - 1]:
                return _fail(rec, f"source row {removed} is recorded as a removed duplicate but is stored")
            if not filled[kept - 1]:
                return _fail(rec, f"kept row {kept} of removed duplicate {removed} is not stored")
            keys[removed - 1], filled[removed - 1] = keys[kept - 1], True
            rec.removed_rows += 1
    missing = [i + 1 for i, f in enumerate(filled) if not f]
    if missing:
        hint = "" if dup_steps else " (no duplicate-removal record exists for the attempt)"
        return _fail(rec, f"{len(missing)} source row(s) cannot be placed, e.g. {missing[:5]}: neither stored in any "
                          f"dataset of the attempt nor recorded as removed duplicates{hint}")
    rec.keys = keys
    return rec


def compare_with_record(inf: T.Inference, record: dict, registered_dataset_tf: str) -> list[str]:
    """Every difference between the re-run inference and the recorded evidence (empty = reproduced exactly)."""
    out = []
    for name, got, want in (("observation count", inf.rows_total, record.get("rows_total")),
                            ("seed", inf.seed, record.get("seed")),
                            ("candidate", inf.candidate, record.get("candidate")),
                            ("number of blocks", len(inf.blocks), len(record.get("blocks") or [])),
                            ("rows examined", inf.rows_examined, record.get("rows_examined")),
                            ("block patterns", inf.patterns, record.get("patterns")),
                            ("status", inf.status, record.get("status")),
                            ("timeframe", inf.timeframe, record.get("timeframe")),
                            ("registered timeframe", registered_dataset_tf, record.get("registered"))):
        if got != want:
            out.append(f"{name}: reconstructed {got!r}, recorded {want!r}")
    for i, (b, rb) in enumerate(zip(inf.blocks, record.get("blocks") or []), 1):
        got = b.as_dict()
        for k in ("start_row", "rows", "interval", "steps", "agreeing_share", "agrees"):
            if got.get(k) != rb.get(k):
                out.append(f"block {i} (recorded start row {rb.get('start_row')}): {k} reconstructed "
                           f"{got.get(k)!r}, recorded {rb.get(k)!r}")
    return out


# ---- the report -----------------------------------------------------------------------------------------------------
REPORT_COLUMNS = [
    "row_type", "dataset_id", "instrument", "display_name", "source_file", "attempt_id", "datasets_sharing_inference",
    "current_classification", "reproduction", "reconstructed_rows", "stored_rows", "removed_duplicates",
    "recorded_seed", "candidate", "proposed_classification_option_c", "would_change", "reason",
    "block_start_row", "block_rows", "block_interval", "block_steps", "block_agreeing_share", "block_agrees_original",
    "option_c_role", "sparse_test", "block_agrees_under_option_c",
    "derived_datasets", "runs_using_dataset", "processing_and_lineage"]


def impact_rows(conn, data_path) -> list[dict]:
    """Dataset rows and block rows for every active cleaned MIXED dataset."""
    out = []
    sel = conn.execute(
        "SELECT d.dataset_id, d.timeframe, i.exchange, i.symbol, i.name FROM datasets d "
        "JOIN instruments i ON i.instrument_id = d.instrument_id "
        "WHERE d.layer = 'cleaned' AND d.status = 'active' AND d.timeframe = 'MIXED' ORDER BY d.dataset_id").fetchall()
    for d in sel:
        rec = reconstruct_input(conn, data_path, d["dataset_id"])
        src = conn.execute("SELECT e.original_filename FROM ingest_attempts a JOIN ingest_events e USING (event_id) "
                           "WHERE a.attempt_id = ?", (rec.attempt_id,)).fetchone() if rec.attempt_id else None
        derived = [r[0] for r in conn.execute("SELECT dataset_id FROM datasets WHERE parent_dataset_id = ? "
                                              "AND layer = 'timeframe'", (d["dataset_id"],))]
        runs = conn.execute("SELECT COUNT(*) FROM run_inputs WHERE dataset_id = ?", (d["dataset_id"],)).fetchone()[0]
        row = {k: "" for k in REPORT_COLUMNS}
        row.update(row_type="dataset", dataset_id=d["dataset_id"], instrument=f"{d['exchange']}:{d['symbol']}",
                   display_name=d["name"] or "", source_file=src[0] if src else "", attempt_id=rec.attempt_id or "",
                   datasets_sharing_inference=" ".join(map(str, rec.siblings)), current_classification=d["timeframe"],
                   reconstructed_rows=rec.rows_read if rec.keys is not None else "", stored_rows=rec.stored_rows,
                   removed_duplicates=rec.removed_rows, recorded_seed=(rec.record or {}).get("seed", ""),
                   candidate=(rec.record or {}).get("candidate", ""),
                   derived_datasets=" ".join(map(str, derived)) or "none", runs_using_dataset=runs)
        blocks: list = []
        if rec.keys is None:
            row.update(reproduction=f"{NOT_EVALUABLE}: {rec.reason}", proposed_classification_option_c=NOT_EVALUABLE,
                       would_change="unknown", reason="input not reconstructed exactly; no Option C conclusion")
        else:
            orig = T.infer_interval(rec.keys, zone=rec.zone, config={**T.DEFAULT_SAMPLING, **rec.config})
            diffs = compare_with_record(orig, rec.record, d["timeframe"])
            if diffs:
                row.update(reproduction=f"{NOT_EVALUABLE}: recorded inference not reproduced - " + "; ".join(diffs),
                           proposed_classification_option_c=NOT_EVALUABLE, would_change="unknown",
                           reason="no Option C conclusion")
            else:
                _o, opt = evaluate_option_c(rec.keys, rec.zone, rec.config, original=orig)
                proposed = opt.timeframe or "INSUFFICIENT"
                change = proposed != d["timeframe"]
                used = [b for b in opt.blocks if b["role"] == "used"]
                row.update(reproduction=f"verified: {len(orig.blocks)} block(s), seed, candidate, status and every "
                                        "block's evidence identical to the record",
                           proposed_classification_option_c=proposed, would_change="yes" if change else "no",
                           reason=(f"excluded block(s) {opt.excluded} (one-bar dates at varying times); remaining "
                                   f"{len(used)} block(s) dominant {opt.dominant}, all agree" if change else
                                   ("no block qualifies for exclusion; MIXED is unchanged" if not opt.excluded else
                                    f"excluded block(s) {opt.excluded}, but the remaining blocks still disagree "
                                    f"(dominant {opt.dominant})")))
                for b in opt.blocks:
                    br = {k: "" for k in REPORT_COLUMNS}
                    br.update(row_type="block", dataset_id=d["dataset_id"], block_start_row=b["start_row"],
                              block_rows=b["rows"], block_interval=b["interval"], block_steps=b["steps"],
                              block_agreeing_share=b["agreeing_share"], block_agrees_original=b["agrees_original"],
                              option_c_role=b["role"], sparse_test=b["sparse"],
                              block_agrees_under_option_c=b["agrees_under_c"])
                    blocks.append(br)
        row["processing_and_lineage"] = _lineage_note(row, derived, runs, rec.siblings)
        out.append(row)
        out.extend(blocks)
    return out


def _lineage_note(row, derived, runs, siblings) -> str:
    shared = [s for s in siblings if s != row["dataset_id"]]
    lead = f"shares one inference with dataset(s) {' '.join(map(str, shared))}; " if shared else ""
    if row.get("would_change") == "unknown":
        return lead + "not evaluated"
    if row.get("would_change") != "yes":
        return lead + ("label unchanged; under a vs3 identity change it would still be processed once more (new "
                       "number, same content, old one superseded)")
    note = (lead + f"would be re-registered as {row['proposed_classification_option_c']} (new dataset and storage "
            "path, since the timeframe is part of the path); this dataset kept and marked superseded; nothing deleted")
    if derived:
        note += f"; derived dataset(s) {' '.join(map(str, derived))} stay linked to it and are not rebuilt (OW-32)"
    if runs:
        note += f"; {runs} earlier run(s) keep it as their recorded input"
    return note


def summary(rows: list[dict]) -> dict:
    ds = [r for r in rows if r["row_type"] == "dataset"]
    return {"mixed_datasets": len(ds), "would_change": sum(r["would_change"] == "yes" for r in ds),
            "unchanged": sum(r["would_change"] == "no" for r in ds),
            "not_evaluable": sum(r["would_change"] == "unknown" for r in ds)}


def write_report(rows: list[dict], folder: Path, stamp: str) -> tuple[Path, Path]:
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
        f"NOT EVALUABLE (see reason):     {s['not_evaluable']}\n"
        "A dataset is evaluated only when its inference input was rebuilt exactly and the recorded sampling evidence "
        "(seed, candidate, every block, status) was reproduced.\n"
        "Block rows in the CSV show every sampled block, whether Option C excludes it and why.\n"
        "Nothing was changed: no dataset, registry entry or file was written except this report.\n"
        "Option C, the vs3 identity change and any reprocessing are NOT applied (owner approval required).\n",
        encoding="utf-8")
    return csv_path, txt


__all__ = ["NOT_EVALUABLE", "OptionC", "REPORT_COLUMNS", "Reconstruction", "compare_with_record", "evaluate_option_c",
           "impact_rows", "open_read_only", "reconstruct_input", "sparse_test", "summary", "write_report"]
