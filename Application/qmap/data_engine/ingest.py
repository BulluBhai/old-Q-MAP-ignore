"""Ingestion orchestration: source file -> registered raw file -> canonical cleaned dataset.

Stages: (1) preserve and register the original, (2) read with the right format reader,
(3) map columns and parse dates, (4) standardise, (5) validate, (6) register the result with its
processing version and lineage. Failed attempts stay in the audit trail.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .. import CLEANING_CODE_VERSION, __version__
from ..core.errors import IngestError
from ..core.runs import Run
from ..storage.db import utc_now_iso
from ..storage.faults import maybe_fail
from ..storage.files import safe_remove, sha256_file, unique_tmp_name
from ..storage.parquet_io import write_canonical_parquet
from ..storage.registry import Receipt, receive_file
from . import canonical as C
from .instruments import get_or_create_instrument
from .process import _fatal, process_table
from .profiles import (SourceProfile, check_profile_against_settings, processing_version,
                       register_profile_snapshot)
from .readers import read_source
from .results import ERROR, INFO, WARNING, CheckResult

REPORT_COLUMNS = ("check", "severity", "source_row", "field", "value", "message")


@dataclass
class IngestResult:
    outcome: str  # accepted | rejected | reused | blocked | unsupported | failed
    message: str = ""
    event_id: int | None = None
    raw_dataset_id: int | None = None
    attempt_id: int | None = None
    dataset_ids: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    issues_report: Path | None = None
    receipt_status: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome in ("accepted", "reused")

    def failed_checks(self) -> list:
        return [c for c in self.checks if c.is_error]


def _j(obj) -> str:
    return json.dumps(obj, default=str, sort_keys=True)


def _insert_attempt(conn, **values) -> int:
    """INSERT built from named columns, so the column/placeholder counts can never drift apart."""
    cols = list(values)
    cur = conn.execute(f"INSERT INTO ingest_attempts({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                       [values[c] for c in cols])
    return int(cur.lastrowid)


def _request_json(overrides: dict) -> str:
    """The ingest-request values (exchange/symbol/timeframe) that influence the result but are not in the profile."""
    clean = {}
    for k, v in overrides.items():
        if v is not None and str(v).strip():
            clean[k] = str(v).strip().upper() if k in ("exchange", "symbol") else str(v).strip()
    return _j(clean)


def _write_issue_report(run: Run, event_id: int, issues: list) -> Path | None:
    if not issues:
        return None
    path = run.output_path(f"issues_event{event_id}.csv")
    with open(path, "x", newline="", encoding="utf-8") as fh:  # exclusive: never overwrite
        w = csv.writer(fh)
        w.writerow(REPORT_COLUMNS)
        for i in issues:
            v = "" if i.value is None else str(i.value)
            w.writerow([i.check, i.severity, "" if i.row is None else i.row, i.field or "", v[:200], i.message])
    return path


def ingest_file(run: Run, path: str | os.PathLike, profile: SourceProfile, *, source_label: str | None = None,
                note: str | None = None, force_reason: str | None = None, exchange: str | None = None,
                symbol: str | None = None, timeframe: str | None = None, today: date | None = None) -> IngestResult:
    """Ingest one file. Never modifies the source; always records the receipt."""
    check_profile_against_settings(profile, run.settings)
    path = Path(path)
    receipt = receive_file(run, path, source_label=source_label or profile.source_label, note=note)
    if not receipt.ok:
        return IngestResult(outcome=receipt.status, message=receipt.detail or "", event_id=receipt.event_id,
                            receipt_status=receipt.status)
    with run.db.transaction() as conn:
        conn.execute("INSERT OR IGNORE INTO run_inputs(run_id, dataset_id) VALUES (?, ?)",
                     (run.run_id, receipt.raw_dataset_id))
    overrides = {"exchange": exchange, "symbol": symbol, "timeframe": timeframe}
    return _process_registered(run, receipt, path, profile, force_reason, overrides, today, retry=True)


def _process_registered(run: Run, receipt: Receipt, src: Path, profile: SourceProfile, force_reason, overrides,
                        today, *, retry: bool) -> IngestResult:
    db, settings, log = run.db, run.settings, run.logger
    register_profile_snapshot(db, profile)
    pv = processing_version(profile, CLEANING_CODE_VERSION)
    raw = db.one("SELECT * FROM datasets WHERE dataset_id = ?", (receipt.raw_dataset_id,))

    request_json = _request_json(overrides)
    prior = [a for a in db.query(
        "SELECT * FROM ingest_attempts WHERE raw_dataset_id = ? AND processing_version = ? ORDER BY attempt_id",
        (raw["dataset_id"], pv)) if (a["ingest_request_json"] or "{}") == request_json]
    accepted_prior = next((a for a in prior if a["outcome"] == "accepted"), None)
    if accepted_prior is not None:
        return _record_reuse(run, receipt, accepted_prior, pv)
    rejected_same = [a for a in prior if a["outcome"] == "rejected"]
    if rejected_same and not (force_reason and force_reason.strip()):
        msg = (f"This file was already processed under {pv} and rejected (attempt {rejected_same[-1]['attempt_id']}). "
               "Reprocessing it unchanged is blocked. Fix the profile (new profile_version) or the processing, or "
               "retry deliberately with a written force_reason.")
        with db.transaction() as conn:
            conn.execute("UPDATE ingest_events SET detail = ? WHERE event_id = ?", (msg, receipt.event_id))
        log.warning(msg)
        return IngestResult(outcome="blocked", message=msg, event_id=receipt.event_id, raw_dataset_id=raw["dataset_id"],
                            attempt_id=rejected_same[-1]["attempt_id"], receipt_status=receipt.status)
    last_rejected = db.one("SELECT attempt_id FROM ingest_attempts WHERE raw_dataset_id = ? AND outcome = 'rejected' "
                           "ORDER BY attempt_id DESC LIMIT 1", (raw["dataset_id"],))

    # ---- stages 2-5: read, map/parse, standardise, validate (from the REGISTERED raw copy) ----------
    stored = settings.data_path(raw["relative_path"])
    pre_checks = [CheckResult("format_supported", ERROR, True, 0, f"detected as {raw['file_format']}")]
    if not receipt.detected.extension_matches:
        pre_checks.append(CheckResult(
            "extension_matches_content", WARNING, False, 0,
            f"The file extension {receipt.detected.extension or '(none)'} does not match its content "
            f"({raw['file_format']}). It was read by its content."))
    reader_name, reader_version = "n/a", None
    try:
        table = read_source(stored, raw["file_format"], profile.file)
    except IngestError as err:
        result = _fatal(err, 0, None)
    else:
        reader_name, reader_version = table.reader, table.reader_version
        pre_checks.append(CheckResult("file_readable", ERROR, True, 0, ""))
        result = process_table(table, profile, settings, filename=src.name, overrides=overrides, today=today)
    checks = pre_checks + result.checks
    accepted = result.accepted and not any(c.is_error for c in checks)
    report = _write_issue_report(run, receipt.event_id, result.issues)

    # ---- write cleaned files (temp -> atomic rename to a path unique to this run) ---------------------
    written: list[tuple] = []
    try:
        if accepted:
            pv_hash = hashlib.sha256(pv.encode()).hexdigest()[:8]
            for g in result.groups:
                rel = (f"Cleaned_Data/{g.exchange}/{g.symbol}/{g.timeframe}/"
                       f"{raw['sha256'][:12]}_{pv_hash}_{run.run_id}.parquet")
                final = settings.data_path(rel)
                tmp = settings.cleaned_incoming_dir / unique_tmp_name()
                meta = {"run_id": run.run_id, "processing_version": pv, "profile_id": profile.profile_id,
                        "profile_version": profile.profile_version, "source_raw_sha256": raw["sha256"],
                        "exchange": g.exchange, "symbol": g.symbol, "timeframe": g.timeframe,
                        "volume_status": g.volume_status, "requirement_set": profile.requirement_set,
                        "qmap_version": __version__, "cleaning_code_version": CLEANING_CODE_VERSION,
                        "field_provenance": result.field_provenance, "row_count": g.row_count}
                write_canonical_parquet(tmp, g, meta)
                maybe_fail("after_cleaned_temp")
                final.parent.mkdir(parents=True, exist_ok=True)
                os.replace(tmp, final)
                maybe_fail("after_cleaned_rename")
                written.append((g, rel, final, sha256_file(final)))

        # ---- stage 6: one transaction registers the attempt, its checks and the datasets -------------
        dataset_ids: list[int] = []
        with db.transaction() as conn:
            maybe_fail("before_result_commit")
            attempt_id = _insert_attempt(
                conn, event_id=receipt.event_id, run_id=run.run_id, raw_dataset_id=raw["dataset_id"],
                outcome="accepted" if accepted else "rejected", profile_id=profile.profile_id,
                profile_version=profile.profile_version, processing_version=pv, detected_format=raw["file_format"],
                extension_matches=int(receipt.detected.extension_matches), reader=reader_name,
                reader_version=reader_version, source_columns_json=_j(result.source_columns),
                column_mapping_json=_j(result.column_mapping), datetime_rules_json=_j(result.datetime_rules),
                volume_rule_json=_j(result.volume_rule), transformations_json=_j(result.transformations),
                field_provenance_json=_j(result.field_provenance), rows_read=result.rows_read,
                rows_accepted=result.rows_accepted, rows_flagged=result.rows_flagged,
                issues_report_path=f"{run.relative_dir}/{report.name}" if report else None,
                revalidation_of_attempt_id=last_rejected["attempt_id"] if last_rejected else None,
                force_reason=force_reason.strip() if force_reason and force_reason.strip() else None,
                ingest_request_json=request_json, created_at=utc_now_iso())
            extra_checks: list[CheckResult] = []
            if accepted:
                for g, rel, final, sha in written:
                    instrument_id, created = get_or_create_instrument(conn, g.exchange, g.symbol)
                    if created:
                        extra_checks.append(CheckResult("instrument_registered", INFO, True, 0,
                                                        f"New instrument {g.exchange}:{g.symbol} created (first time seen)."))
                        log.warning("New instrument registered: %s:%s", g.exchange, g.symbol)
                    old = conn.execute(
                        "SELECT dataset_id FROM datasets WHERE layer = 'cleaned' AND parent_dataset_id = ? AND "
                        "instrument_id = ? AND timeframe = ? AND status = 'active'",
                        (raw["dataset_id"], instrument_id, g.timeframe)).fetchone()
                    if old:
                        conn.execute("UPDATE datasets SET status = 'superseded' WHERE dataset_id = ?", (old["dataset_id"],))
                    cur = conn.execute(
                        "INSERT INTO datasets(layer, instrument_id, timeframe, relative_path, sha256, row_count, date_from, "
                        "date_to, parent_dataset_id, processing_version, canonical_schema_version, volume_status, "
                        "requirement_set, created_by_attempt_id, created_at) "
                        "VALUES ('cleaned', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (instrument_id, g.timeframe, rel, sha, g.row_count, g.date_from, g.date_to, raw["dataset_id"], pv,
                         C.CANONICAL_SCHEMA_VERSION, g.volume_status, profile.requirement_set, attempt_id, utc_now_iso()))
                    new_id = int(cur.lastrowid)
                    if old:
                        conn.execute("UPDATE datasets SET superseded_by_dataset_id = ? WHERE dataset_id = ?",
                                     (new_id, old["dataset_id"]))
                    dataset_ids.append(new_id)
            now = utc_now_iso()
            conn.executemany(
                "INSERT INTO quality_checks(run_id, attempt_id, check_name, severity, passed, rows_failed, detail, checked_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [(run.run_id, attempt_id, c.name, c.severity, int(c.passed), c.rows_failed, c.detail, now)
                 for c in checks + extra_checks])
    except sqlite3.IntegrityError:
        for _, _, final, _ in written:  # these files are unique to this run: safe to remove
            safe_remove(final)
        if retry:
            # most likely a concurrent identical ingest registered first: re-evaluate (will become 'reused')
            return _process_registered(run, receipt, src, profile, force_reason, overrides, today, retry=False)
        raise

    failed =[c for c in checks if c.is_error]
    if accepted:
        log.info("Ingest accepted: %s -> %d dataset(s) %s [%s]", src.name, len(dataset_ids), dataset_ids, pv)
        return IngestResult("accepted", f"{len(dataset_ids)} dataset(s) created", receipt.event_id, raw["dataset_id"],
                            attempt_id, dataset_ids, checks + extra_checks, report, receipt.status)
    names = ", ".join(c.name for c in failed)
    log.error("Ingest REJECTED: %s [%s] failed checks: %s", src.name, pv, names)
    detail = "; ".join(f"{c.name}: {c.detail}" if c.detail else c.name for c in failed[:5])
    return IngestResult("rejected", f"Rejected. Failed check(s): {detail}", receipt.event_id, raw["dataset_id"],
                        attempt_id, [], checks, report, receipt.status)


def _record_reuse(run: Run, receipt: Receipt, original, pv: str) -> IngestResult:
    db, log = run.db, run.logger
    with db.transaction() as conn:
        attempt_id = _insert_attempt(
            conn, event_id=receipt.event_id, run_id=run.run_id, raw_dataset_id=original["raw_dataset_id"],
            outcome="reused", profile_id=original["profile_id"], profile_version=original["profile_version"],
            processing_version=pv, detected_format=original["detected_format"],
            extension_matches=int(receipt.detected.extension_matches), reader=original["reader"],
            reader_version=original["reader_version"], source_columns_json=original["source_columns_json"],
            column_mapping_json=original["column_mapping_json"], datetime_rules_json=original["datetime_rules_json"],
            volume_rule_json=original["volume_rule_json"], transformations_json=original["transformations_json"],
            field_provenance_json=original["field_provenance_json"], rows_read=original["rows_read"],
            rows_accepted=original["rows_accepted"], rows_flagged=original["rows_flagged"],
            issues_report_path=original["issues_report_path"], reused_of_attempt_id=original["attempt_id"],
            ingest_request_json=original["ingest_request_json"], created_at=utc_now_iso())
        ids = [r["dataset_id"] for r in conn.execute(
            "SELECT dataset_id FROM datasets WHERE created_by_attempt_id = ? ORDER BY dataset_id",
            (original["attempt_id"],))]
    log.info("Reused: raw dataset %s already processed under %s (attempt %s); no new dataset",
             original["raw_dataset_id"], pv, original["attempt_id"])
    return IngestResult("reused", f"Already processed under {pv}; existing dataset(s) {ids} reused.", receipt.event_id,
                        original["raw_dataset_id"], attempt_id, ids, [], None, receipt.status)
