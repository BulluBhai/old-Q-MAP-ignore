"""Compare a newly registered dataset with existing datasets of the same instrument and timeframe (REPORT ONLY).

Blueprint v1.3 §8.3 and §8.5.6; owner decisions DQ-1 (02-Nov-26) and DQ-9 (03-Nov-26): updates must not blindly append
or silently overwrite; overlaps and conflicts are reported in every import workflow (folder scan, Data Management, command
line). This module never changes, merges, supersedes, hides or deletes a dataset and never chooses a winner.
Findings are stored as quality checks on the NEW dataset:

  overlaps_existing_dataset       (info)     timestamps present in both, with identical observations
  conflicts_with_existing_dataset (warning)  timestamps present in both, with different open/high/low/close/volume

Bars are matched on their timestamp (intraday) or trading date (daily and longer). Since DQ-10 one timestamp can hold
several conflicting observations, so each timestamp is compared as a set of observations: identical when both datasets
hold the same observations (same count, pairwise equal after sorting), otherwise conflicting. Prices are equal when
they agree to within 1e-9 relative; volume is equal when both are missing or both agree to that tolerance.

`write_overlap_report` writes one consolidated CSV per run with every finding (datasets, source files, instrument,
timeframe, overlapping range, identical/conflicting counts, examples with both values).
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..core.config import Settings
from ..storage.db import Database, utc_now_iso
from ..storage.parquet_io import read_quant_columns
from .results import INFO, WARNING, CheckResult

FIELDS = ("open", "high", "low", "close", "volume")
MAX_EXAMPLES = 3


@dataclass
class OverlapFinding:
    other_dataset_id: int
    overlapping: int = 0  # timestamps present in both
    identical: int = 0
    conflicting: int = 0
    new_only: int = 0
    other_only: int = 0
    examples: list = field(default_factory=list)
    dataset_id: int | None = None
    instrument: str = ""
    timeframe: str = ""
    overlap_from: str = ""
    overlap_to: str = ""
    new_files: list = field(default_factory=list)
    other_files: list = field(default_factory=list)

    @property
    def repeated_import(self) -> bool:
        """Both datasets hold exactly the same observations: most likely the same data loaded twice."""
        return self.overlapping > 0 and self.conflicting == 0 and self.new_only == 0 and self.other_only == 0

    def note(self) -> str:
        if self.conflicting:
            return f"dataset {self.dataset_id}: {self.conflicting} bar(s) differ from dataset {self.other_dataset_id}"
        if self.repeated_import:
            return (f"dataset {self.dataset_id}: same data as dataset {self.other_dataset_id} "
                    f"({self.identical} identical bar(s); possibly a repeated import)")
        return f"dataset {self.dataset_id}: {self.identical} bar(s) identical to dataset {self.other_dataset_id}"

    def checks(self) -> list[CheckResult]:
        out = []
        span = f"overlap {self.overlap_from} to {self.overlap_to}; " if self.overlap_from else ""
        if self.conflicting:
            ex = "; ".join(self.examples)
            out.append(CheckResult(
                "conflicts_with_existing_dataset", WARNING, False, self.conflicting,
                f"{self.conflicting} of {self.overlapping} overlapping bar(s) differ from dataset "
                f"{self.other_dataset_id} ({span}e.g. {ex}). Both datasets are kept unchanged; choose which one to "
                "analyse (no automatic merge)."))
        if self.identical:
            extra = " This looks like a repeated import of the same data." if self.repeated_import else ""
            out.append(CheckResult(
                "overlaps_existing_dataset", INFO, True, 0,
                f"{self.identical} bar(s) are identical to dataset {self.other_dataset_id}; {self.new_only} bar(s) "
                f"are not in it ({span.rstrip('; ')}).{extra}"))
        return out


def _key_rows(table) -> dict:
    """timestamp (or date) -> list of observations (open, high, low, close, volume)."""
    ts = table.column("timestamp_utc").to_pylist()
    sd = table.column("session_date").to_pylist()
    intraday = any(t is not None for t in ts)
    keys = ts if intraday else sd
    cols = {f: table.column(f).to_pylist() for f in FIELDS}
    out: dict = {}
    for i, k in enumerate(keys):
        if k is not None:
            out.setdefault(k, []).append(tuple(cols[f][i] for f in FIELDS))
    return out


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _same(a, b) -> bool:
    if _missing(a) or _missing(b):
        return _missing(a) and _missing(b)
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=0.0)


def _sort_key(obs):
    return tuple((1, 0.0) if _missing(v) else (0, float(v)) for v in obs)


def _same_observations(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    return all(all(_same(x, y) for x, y in zip(p, q)) for p, q in zip(sorted(a, key=_sort_key), sorted(b, key=_sort_key)))


def _fmt(v) -> str:
    return "empty" if _missing(v) else f"{v:g}"


def _when(k) -> str:
    return k.isoformat() if hasattr(k, "isoformat") else str(k)


def _source_files(db: Database, dataset_id: int) -> list[str]:
    rows = db.query("SELECT DISTINCT e.original_filename FROM datasets d JOIN ingest_attempts a ON a.raw_dataset_id = "
                    "d.parent_dataset_id JOIN ingest_events e ON e.event_id = a.event_id WHERE d.dataset_id = ? AND "
                    "a.outcome IN ('accepted','reused') ORDER BY 1", (dataset_id,))
    return [r[0] for r in rows]


def compare_with_existing(settings: Settings, db: Database, dataset_id: int) -> list[OverlapFinding]:
    new = db.one("SELECT d.*, i.exchange, i.symbol FROM datasets d JOIN instruments i USING (instrument_id) "
                 "WHERE d.dataset_id = ?", (dataset_id,))
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
        f = OverlapFinding(o["dataset_id"], overlapping=len(common), new_only=len(set(mine) - set(theirs)),
                           other_only=len(set(theirs) - set(mine)), dataset_id=dataset_id,
                           instrument=f"{new['exchange']}:{new['symbol']}", timeframe=new["timeframe"],
                           overlap_from=_when(common[0]), overlap_to=_when(common[-1]),
                           new_files=_source_files(db, dataset_id), other_files=_source_files(db, o["dataset_id"]))
        for k in common:
            a, b = mine[k], theirs[k]
            if _same_observations(a, b):
                f.identical += 1
                continue
            f.conflicting += 1
            if len(f.examples) < MAX_EXAMPLES:
                if len(a) == 1 and len(b) == 1:
                    diff = [f"{n} {_fmt(y)} -> {_fmt(x)}" for n, x, y in zip(FIELDS, a[0], b[0]) if not _same(x, y)]
                    f.examples.append(f"{_when(k)}: {', '.join(diff)}")
                else:
                    f.examples.append(f"{_when(k)}: {len(b)} observation(s) there, {len(a)} here, not all equal")
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


def check_new_datasets(run, dataset_ids) -> list[OverlapFinding]:
    """Record overlap findings for every newly registered dataset of a run (used by every import workflow)."""
    out: list[OverlapFinding] = []
    for ds in dataset_ids:
        out.extend(record_overlaps(run.settings, run.db, run.run_id, ds))
    return out


REPORT_COLUMNS = ("New dataset", "New source file(s)", "Existing dataset", "Existing source file(s)", "Instrument",
                  "Timeframe", "Overlap from", "Overlap to", "Overlapping bars", "Identical bars", "Conflicting bars",
                  "Bars only in new", "Bars only in existing", "Finding", "Examples")


def write_overlap_report(run, findings: list[OverlapFinding]) -> Path | None:
    """One consolidated CSV per run (only when there is something to report). Report only: nothing else changes."""
    if not findings:
        return None
    stamp = datetime.now().strftime("%d_%b_%y_%H%M%S")
    path = run.output_path(f"Overlap_Report_{stamp}.csv")
    with open(path, "x", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(REPORT_COLUMNS)
        for f in findings:
            kind = ("Conflicting observations" if f.conflicting else
                    "Same data (possible repeated import)" if f.repeated_import else "Identical overlap")
            w.writerow((f.dataset_id, "; ".join(f.new_files), f.other_dataset_id, "; ".join(f.other_files),
                        f.instrument, f.timeframe, f.overlap_from, f.overlap_to, f.overlapping, f.identical,
                        f.conflicting, f.new_only, f.other_only, kind, "; ".join(f.examples)))
    return path
