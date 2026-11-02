"""Compare a newly registered dataset with existing datasets of the same instrument and timeframe.

Blueprint v1.3 §8.3 and §8.5.6: updates must not blindly append or silently overwrite; overlaps and conflicts are
reported. The resolution policy is an open owner decision (audit DQ-1), so this module REPORTS only. It never changes,
merges, supersedes or hides a dataset. Findings are stored as quality checks on the NEW dataset:

  overlaps_existing_dataset  (info)     bars present in both, with identical values
  conflicts_with_existing_dataset (warning)  bars present in both, with different open/high/low/close/volume

Bars are matched on their timestamp (intraday) or trading date (daily and longer). Prices are equal when they agree
to within 1e-9 relative (they were parsed from text, so equal text gives an equal number); volume is equal when both
are missing or both agree to that tolerance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..core.config import Settings
from ..storage.db import Database, utc_now_iso
from ..storage.parquet_io import read_quant_columns
from .results import INFO, WARNING, CheckResult

FIELDS = ("open", "high", "low", "close", "volume")
MAX_EXAMPLES = 3


@dataclass
class OverlapFinding:
    other_dataset_id: int
    overlapping: int = 0
    identical: int = 0
    conflicting: int = 0
    new_only: int = 0
    examples: list = field(default_factory=list)

    def checks(self) -> list[CheckResult]:
        out = []
        if self.conflicting:
            ex = "; ".join(self.examples)
            out.append(CheckResult(
                "conflicts_with_existing_dataset", WARNING, False, self.conflicting,
                f"{self.conflicting} of {self.overlapping} overlapping bar(s) differ from dataset {self.other_dataset_id} "
                f"(e.g. {ex}). Both datasets are kept unchanged; choose which one to analyse (no automatic merge)."))
        if self.identical:
            out.append(CheckResult(
                "overlaps_existing_dataset", INFO, True, 0,
                f"{self.identical} bar(s) are identical to dataset {self.other_dataset_id}; {self.new_only} bar(s) are "
                "not in it."))
        return out


def _key_rows(table) -> dict:
    ts = table.column("timestamp_utc").to_pylist()
    sd = table.column("session_date").to_pylist()
    intraday = any(t is not None for t in ts)
    keys = ts if intraday else sd
    cols = {f: table.column(f).to_pylist() for f in FIELDS}
    return {k: tuple(cols[f][i] for f in FIELDS) for i, k in enumerate(keys) if k is not None}


def _same(a, b) -> bool:
    if a is None or b is None or (isinstance(a, float) and math.isnan(a)) or (isinstance(b, float) and math.isnan(b)):
        return (a is None or (isinstance(a, float) and math.isnan(a))) and (b is None or (isinstance(b, float) and math.isnan(b)))
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=0.0)


def compare_with_existing(settings: Settings, db: Database, dataset_id: int) -> list[OverlapFinding]:
    new = db.one("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,))
    if new is None or new["layer"] == "raw":
        return []
    others = db.query(
        "SELECT dataset_id, relative_path FROM datasets WHERE layer = ? AND instrument_id = ? AND timeframe = ? "
        "AND status = 'active' AND file_deleted_at IS NULL AND dataset_id <> ? ORDER BY dataset_id",
        (new["layer"], new["instrument_id"], new["timeframe"], dataset_id))
    if not others:
        return []
    mine = _key_rows(read_quant_columns(settings.data_path(new["relative_path"])))
    findings = []
    for o in others:
        try:
            theirs = _key_rows(read_quant_columns(settings.data_path(o["relative_path"])))
        except (OSError, ValueError):
            continue  # an unreadable file is reported by verify/readiness, not here
        common = sorted(set(mine) & set(theirs))
        if not common:
            continue
        f = OverlapFinding(o["dataset_id"], overlapping=len(common), new_only=len(set(mine) - set(theirs)))
        for k in common:
            a, b = mine[k], theirs[k]
            if all(_same(x, y) for x, y in zip(a, b)):
                f.identical += 1
            else:
                f.conflicting += 1
                if len(f.examples) < MAX_EXAMPLES:
                    diff = [f"{n} {y} -> {x}" for n, x, y in zip(FIELDS, a, b) if not _same(x, y)]
                    when = k.isoformat() if hasattr(k, "isoformat") else str(k)
                    f.examples.append(f"{when}: {', '.join(diff)}")
        findings.append(f)
    return findings


def record_overlaps(settings: Settings, db: Database, run_id: str, dataset_id: int) -> list[OverlapFinding]:
    """Compare and store the findings as quality checks on `dataset_id` (append-only)."""
    findings = compare_with_existing(settings, db, dataset_id)
    rows = [c for f in findings for c in f.checks()]
    if rows:
        now = utc_now_iso()
        with db.transaction() as conn:
            conn.executemany(
                "INSERT INTO quality_checks(run_id, dataset_id, check_name, severity, passed, rows_failed, detail, "
                "checked_at) VALUES (?,?,?,?,?,?,?,?)",
                [(run_id, dataset_id, c.name, c.severity, int(c.passed), c.rows_failed, c.detail, now) for c in rows])
    return findings
