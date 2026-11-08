"""Derived timeframes: weekly, monthly, quarterly and yearly bars built from a registered DAILY dataset.

Aggregation rules (method `ohlcv_period_aggregation`, version 1) - standard market-data conventions, no averaging:

  open    first session's open in the period
  high    highest high in the period
  low     lowest low in the period
  close   last session's close in the period
  volume  sum of the period's volumes. If the source has no volume, empty. If volume is mapped but empty on any
          session of the period, the period's volume is EMPTY (never a partial sum) and flagged `volume_missing`.

Periods are calendar periods: ISO week (Monday-Sunday), calendar month, calendar quarter, calendar year.

Look-ahead protection: each derived bar's `session_date` is the LAST session actually included in it - the date on
which the bar became complete - never the period's start. `period_start`/`period_end` give the calendar bounds and
`first_session_date` the first included session.

No trading calendar exists yet, so Q-MAP cannot know whether the first or last period of the data is complete. Such
an edge period is flagged `period_may_be_incomplete` when the data start after the period's calendar start or end
before its calendar end. Interior periods are not checked against a calendar (a holiday week simply has fewer
sessions; `bars_in_period` shows how many).

Only daily (1D) datasets with exactly one bar per date are accepted as a source. Deriving daily bars from intraday
data needs exchange-session rules and incomplete-day detection, which do not exist yet; it is refused.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .. import __version__
from ..core.config import Settings
from ..core.runs import Run
from ..storage.db import Database, utc_now_iso
from ..storage.files import fsync_path, place_without_overwrite, safe_remove, sha256_file, unique_tmp_name
from ..storage.parquet_io import read_canonical, read_canonical_metadata
from ..storage.paths import derived_relative_path
from . import canonical as C

METHOD = "ohlcv_period_aggregation"
METHOD_VERSION = 1
PROCESSING_VERSION = f"derive:{METHOD}@{METHOD_VERSION}"
SOURCE_TIMEFRAME = "1D"
DERIVED_TIMEFRAMES = {"1W": "week", "1M": "month", "1Q": "quarter", "1Y": "year"}
TIMEFRAME_LABELS = {"1D": "Daily", "1W": "Weekly", "1M": "Monthly", "1Q": "Quarterly", "1Y": "Yearly"}

FLAG_PERIOD_MAY_BE_INCOMPLETE = 16  # first/last period of the data may not contain every session (no calendar)
DERIVED_FLAG_DESCRIPTIONS = {**C.FLAG_DESCRIPTIONS, FLAG_PERIOD_MAY_BE_INCOMPLETE: "period_may_be_incomplete"}
# a period inherits these if any of its sessions has them (DQ-10: a period built from conflicting observations says so)
PROPAGATED_FLAGS = C.FLAG_DATE_ORDER_UNVERIFIED | C.FLAG_CONFLICTING_OBSERVATION
DERIVED_COLUMNS = C.CORE_COLUMNS + ("period_start", "period_end", "first_session_date", "bars_in_period")
RULES_TEXT = ("open=first, high=max, low=min, close=last, volume=sum (empty if any session's volume is empty); "
              "calendar periods (ISO week Mon-Sun, month, quarter, year); bar dated by its last included session")


def period_bounds(d: date, timeframe: str) -> tuple[date, date]:
    """Calendar start and end (inclusive) of the period that contains `d`."""
    kind = DERIVED_TIMEFRAMES[timeframe]
    if kind == "week":
        start = d - timedelta(days=d.weekday())
        return start, start + timedelta(days=6)
    if kind == "month":
        start = d.replace(day=1)
    elif kind == "quarter":
        start = date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)
    else:
        start = date(d.year, 1, 1)
    months = {"month": 1, "quarter": 3, "year": 12}[kind]
    y, m = divmod(start.month - 1 + months, 12)
    return start, date(start.year + y, m + 1, 1) - timedelta(days=1)


class DerivationError(Exception):
    """The source cannot be aggregated reliably; the message explains why in plain English."""


@dataclass
class Aggregated:
    columns: dict
    row_count: int
    edge_flags: int  # number of periods flagged period_may_be_incomplete
    volume_missing_periods: int
    conflict_periods: int = 0  # periods that include conflicting observations of one date (DQ-10)


def aggregate_daily(table: pa.Table, timeframe: str) -> Aggregated:
    """Aggregate a canonical daily table. Refuses anything that is not one ordered bar per date with full OHLC."""
    if timeframe not in DERIVED_TIMEFRAMES:
        raise DerivationError(f"{timeframe!r} is not a derived timeframe; choose one of {', '.join(DERIVED_TIMEFRAMES)}.")
    if table.num_rows == 0:
        raise DerivationError("The daily dataset has no rows.")
    dates = table.column("session_date").to_pylist()
    if any(d is None for d in dates):
        raise DerivationError("Some daily bars have no trading date.")
    flags_all = np.asarray(table.column("quality_flags").to_numpy(zero_copy_only=False), dtype=np.int64)
    conflict_row = (flags_all & C.FLAG_CONFLICTING_OBSERVATION) != 0
    # A repeated date is accepted only as conflicting observations of that date (DQ-10, 03-Nov-26: conflicts must
    # not block derivations). The existing rules then apply unchanged to all rows of the period, in stored order
    # (open = first row, close = last row, high/low over all, volume summed); the period is flagged and warned.
    if any(b < a or (b == a and not (conflict_row[i] and conflict_row[i + 1]))
           for i, (a, b) in enumerate(zip(dates, dates[1:]))):
        raise DerivationError("The daily dataset has more than one bar on some dates, or is not in date order. "
                              "Derived timeframes need exactly one bar per trading date.")
    o, h, lo, c = (np.asarray(table.column(k).to_numpy(zero_copy_only=False), dtype=float)
                   for k in ("open", "high", "low", "close"))
    if np.isnan(o).any() or np.isnan(h).any() or np.isnan(lo).any() or np.isnan(c).any():
        raise DerivationError("Some daily bars have an empty open, high, low or close.")
    vol_col = table.column("volume")
    vol_null = np.asarray(vol_col.is_null().to_numpy(zero_copy_only=False), dtype=bool)
    v = np.asarray(vol_col.to_numpy(zero_copy_only=False), dtype=float)
    volume_absent = bool(vol_null.all())
    flags_in = np.asarray(table.column("quality_flags").to_numpy(zero_copy_only=False), dtype=np.int64)

    keys = [period_bounds(d, timeframe) for d in dates]
    starts = [0] + [i for i in range(1, len(keys)) if keys[i] != keys[i - 1]]
    ends = starts[1:] + [len(keys)]
    out = {k: [] for k in DERIVED_COLUMNS}
    edge = vol_missing = conflict_periods = 0
    for n, (a, b) in enumerate(zip(starts, ends)):
        p_start, p_end = keys[a]
        flags = int(np.bitwise_or.reduce(flags_in[a:b] & PROPAGATED_FLAGS))
        if flags & C.FLAG_CONFLICTING_OBSERVATION:
            conflict_periods += 1
        if (n == 0 and dates[a] > p_start) or (n == len(starts) - 1 and dates[b - 1] < p_end):
            flags |= FLAG_PERIOD_MAY_BE_INCOMPLETE
            edge += 1
        if volume_absent:
            volume = None
        elif vol_null[a:b].any():
            volume, flags = None, flags | C.FLAG_VOLUME_MISSING
            vol_missing += 1
        else:
            volume = float(v[a:b].sum())
        out["session_date"].append(dates[b - 1])
        out["timestamp_utc"].append(None)
        out["open"].append(float(o[a]))
        out["high"].append(float(h[a:b].max()))
        out["low"].append(float(lo[a:b].min()))
        out["close"].append(float(c[b - 1]))
        out["volume"].append(volume)
        out["src_row"].append(None)  # a derived bar has no single source row; see first_session_date/session_date
        out["quality_flags"].append(flags)
        out["period_start"].append(p_start)
        out["period_end"].append(p_end)
        out["first_session_date"].append(dates[a])
        out["bars_in_period"].append(b - a)
    return Aggregated(out, len(starts), edge, vol_missing, conflict_periods)


def build_derived_table(agg: Aggregated, metadata: dict) -> pa.Table:
    cols = agg.columns
    table = pa.table({
        "session_date": pa.array(cols["session_date"], type=pa.date32()),
        "timestamp_utc": pa.array(cols["timestamp_utc"], type=pa.timestamp("ns", "UTC")),
        **{k: pa.array(cols[k], type=pa.float64()) for k in ("open", "high", "low", "close", "volume")},
        "src_row": pa.array(cols["src_row"], type=pa.int64()),
        "quality_flags": pa.array(cols["quality_flags"], type=pa.int64()),
        "period_start": pa.array(cols["period_start"], type=pa.date32()),
        "period_end": pa.array(cols["period_end"], type=pa.date32()),
        "first_session_date": pa.array(cols["first_session_date"], type=pa.date32()),
        "bars_in_period": pa.array(cols["bars_in_period"], type=pa.int64()),
    })
    meta = {"qmap": json.dumps({
        "canonical_schema_version": C.CANONICAL_SCHEMA_VERSION,
        "quant_columns": list(C.QUANT_COLUMNS),
        "preserved_columns_are_not_quant_inputs": [],
        "flag_bits": {str(k): name for k, name in DERIVED_FLAG_DESCRIPTIONS.items()},
        "aggregation_rules": RULES_TEXT,
        **metadata,
    }, default=str, sort_keys=True).encode("utf-8")}
    return table.replace_schema_metadata(meta)


# ---- assessment and registration -------------------------------------------------------------------------------
@dataclass
class DerivationAssessment:
    source_dataset_id: int
    timeframe: str
    label: str = ""
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    existing_dataset_id: int | None = None  # already derived the same way: reused, never duplicated

    @property
    def allowed(self) -> bool:
        return not self.blockers


@dataclass
class DerivationResult:
    outcome: str  # created | reused | refused | failed
    message: str
    dataset_id: int | None = None
    assessment: DerivationAssessment | None = None

    @property
    def ok(self) -> bool:
        return self.outcome in ("created", "reused")


def assess_derivation(settings: Settings, db: Database, source_dataset_id: int, timeframe: str) -> DerivationAssessment:
    a = DerivationAssessment(source_dataset_id, timeframe)
    if timeframe not in DERIVED_TIMEFRAMES:
        a.blockers.append(f"{timeframe!r} cannot be derived; choose weekly, monthly, quarterly or yearly.")
        return a
    row = db.one("SELECT d.*, i.exchange, i.symbol FROM datasets d LEFT JOIN instruments i USING (instrument_id) "
                 "WHERE d.dataset_id = ?", (source_dataset_id,))
    if row is None:
        a.blockers.append(f"Dataset {source_dataset_id} is not registered.")
        return a
    a.label = f"{row['exchange']}:{row['symbol']} {TIMEFRAME_LABELS.get(timeframe, timeframe)} from dataset {source_dataset_id}"
    if row["layer"] != "cleaned" or row["timeframe"] != SOURCE_TIMEFRAME:
        a.blockers.append("Derived timeframes are built from a standardised DAILY (1D) dataset. Building them from "
                          "intraday data needs trading-session rules that Q-MAP does not have yet.")
        return a
    if row["file_deleted_at"]:
        a.blockers.append("The daily dataset's file was deleted; nothing can be derived from it.")
        return a
    if not row["config_fingerprint"]:
        a.blockers.append("This daily dataset was created before validation settings were recorded; load it again "
                          "(new processing) before deriving from it.")
    if row["status"] != "active":
        a.warnings.append(f"The daily dataset is SUPERSEDED (by dataset {row['superseded_by_dataset_id']}); the newer "
                          "one is normally the right source.")
    if db.one("SELECT 1 FROM quality_checks WHERE attempt_id = ? AND check_name = 'conflicting_observations' AND "
              "passed = 0", (row["created_by_attempt_id"],)) is not None:
        a.warnings.append("The daily dataset has unresolved conflicting observations (same date, different values). "
                          "Derivation continues; the periods concerned are flagged and depend on those conflicts.")
    bad = db.one("SELECT detail FROM quality_checks WHERE attempt_id = ? AND check_name = 'one_bar_per_period' "
                 "AND passed = 0", (row["created_by_attempt_id"],))
    if bad is not None:
        a.blockers.append("Validation found more than one bar per day in this 'daily' dataset, so it is probably "
                          "intraday data declared as 1D. It cannot be aggregated as daily bars.")
    path = settings.data_path(row["relative_path"])
    if not path.is_file():
        a.blockers.append(f"The daily dataset's file is missing ({row['relative_path']}). Run 'verify'.")
    if row["storage_class"] == "temporary":
        a.warnings.append("The daily dataset is Temporary. The derived dataset is created as Permanent; the daily "
                          "dataset cannot be deleted while the derived one exists.")
    existing = db.one("SELECT dataset_id FROM datasets WHERE layer = 'timeframe' AND parent_dataset_id = ? AND "
                      "processing_version = ? AND timeframe = ? AND config_fingerprint IS ? AND file_deleted_at IS NULL",
                      (source_dataset_id, PROCESSING_VERSION, timeframe, row["config_fingerprint"]))
    if existing is not None:
        a.existing_dataset_id = int(existing["dataset_id"])
    elif db.one("SELECT 1 FROM datasets WHERE layer = 'timeframe' AND parent_dataset_id = ? AND processing_version = ? "
                "AND timeframe = ? AND config_fingerprint IS ?",
                (source_dataset_id, PROCESSING_VERSION, timeframe, row["config_fingerprint"])) is not None:
        a.blockers.append("This timeframe was derived before and its file was deleted by you. Re-creating it with the "
                          "same method version is not supported yet (see the outstanding-work register).")
    return a


def derive_timeframe(run: Run, source_dataset_id: int, timeframe: str) -> DerivationResult:
    """Derive one timeframe from one daily dataset, register it with full provenance, or explain why not."""
    settings, db, log = run.settings, run.db, run.logger
    a = assess_derivation(settings, db, source_dataset_id, timeframe)
    if not a.allowed:
        return DerivationResult("refused", " ".join(a.blockers), assessment=a)
    if a.existing_dataset_id is not None:
        return DerivationResult("reused", f"Already derived with the same method and source: dataset "
                                f"{a.existing_dataset_id}. Nothing was duplicated.", a.existing_dataset_id, a)
    src = db.one("SELECT d.*, i.exchange, i.symbol FROM datasets d JOIN instruments i USING (instrument_id) "
                 "WHERE d.dataset_id = ?", (source_dataset_id,))
    src_path = settings.data_path(src["relative_path"])
    if sha256_file(src_path) != src["sha256"]:
        return DerivationResult("refused", "The daily dataset's file does not match its registered checksum; run "
                                "'verify' and investigate before deriving from it.", assessment=a)
    try:
        agg = aggregate_daily(read_canonical(src_path), timeframe)
    except DerivationError as exc:
        return DerivationResult("refused", str(exc), assessment=a)
    src_meta = read_canonical_metadata(src_path)
    params = {"timeframe": timeframe, "period": DERIVED_TIMEFRAMES[timeframe], "rules": RULES_TEXT}
    meta = {"run_id": run.run_id, "processing_version": PROCESSING_VERSION, "method": METHOD,
            "method_version": METHOD_VERSION, "parameters": params, "source_dataset_id": source_dataset_id,
            "source_sha256": src["sha256"], "source_processing_version": src["processing_version"],
            "exchange": src["exchange"], "symbol": src["symbol"], "timeframe": timeframe,
            "volume_status": src["volume_status"], "requirement_set": src["requirement_set"],
            "config_fingerprint": src["config_fingerprint"], "qmap_version": __version__,
            "source_field_provenance": src_meta.get("field_provenance"), "row_count": agg.row_count}
    rel = derived_relative_path(src["exchange"], src["symbol"], timeframe, src["sha256"], PROCESSING_VERSION, run.run_id)
    final = settings.data_path(rel)
    tmp = settings.timeframe_incoming_dir / f"{run.run_id}.{unique_tmp_name()}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    placed = False
    try:
        pq.write_table(build_derived_table(agg, meta), str(tmp), compression="snappy")
        fsync_path(tmp)
        final.parent.mkdir(parents=True, exist_ok=True)
        place_without_overwrite(tmp, final)
        placed = True
        sha = sha256_file(final)
        dates = agg.columns["session_date"]
        with db.transaction() as conn:
            old = conn.execute("SELECT dataset_id FROM datasets WHERE layer = 'timeframe' AND parent_dataset_id = ? AND "
                               "instrument_id = ? AND timeframe = ? AND status = 'active'",
                               (source_dataset_id, src["instrument_id"], timeframe)).fetchone()
            if old:
                conn.execute("UPDATE datasets SET status = 'superseded' WHERE dataset_id = ?", (old["dataset_id"],))
            cur = conn.execute(
                "INSERT INTO datasets(layer, instrument_id, timeframe, relative_path, sha256, row_count, date_from, "
                "date_to, parent_dataset_id, processing_version, canonical_schema_version, volume_status, "
                "requirement_set, created_by_attempt_id, config_fingerprint, created_at) "
                "VALUES ('timeframe', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (src["instrument_id"], timeframe, rel, sha, agg.row_count,
                 agg.columns["first_session_date"][0].isoformat(), dates[-1].isoformat(), source_dataset_id,
                 PROCESSING_VERSION, C.CANONICAL_SCHEMA_VERSION, src["volume_status"], src["requirement_set"],
                 src["created_by_attempt_id"], src["config_fingerprint"], utc_now_iso()))
            new_id = int(cur.lastrowid)
            if old:
                conn.execute("UPDATE datasets SET superseded_by_dataset_id = ? WHERE dataset_id = ?",
                             (new_id, old["dataset_id"]))
            conn.execute("INSERT INTO dataset_derivations(dataset_id, run_id, method, method_version, source_dataset_id, "
                         "source_sha256, parameters_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
                         (new_id, run.run_id, METHOD, METHOD_VERSION, source_dataset_id, src["sha256"],
                          json.dumps(params, sort_keys=True), utc_now_iso()))
            conn.execute("INSERT OR IGNORE INTO run_inputs(run_id, dataset_id) VALUES (?, ?)", (run.run_id, source_dataset_id))
            now = utc_now_iso()
            checks = [("derivation_source_daily", "info", 1, 0, f"{src['row_count']} daily bars -> {agg.row_count} "
                       f"{DERIVED_TIMEFRAMES[timeframe]} bars ({RULES_TEXT})"),
                      ("period_may_be_incomplete", "warning", int(agg.edge_flags == 0), agg.edge_flags,
                       "The first and/or last period may not contain every trading session (no trading calendar)."
                       if agg.edge_flags else "")]
            if agg.conflict_periods:
                checks.append(("period_has_conflicting_observations", "warning", 0, agg.conflict_periods,
                               f"{agg.conflict_periods} period(s) include dates with conflicting observations in the "
                               "daily dataset. The usual rules were applied to all of them unchanged (open = first "
                               "row, close = last row in stored order, volume summed over every row), so these "
                               "periods depend on unresolved conflicts. Q-MAP has not chosen between them."))
            if agg.volume_missing_periods:
                checks.append(("period_volume_missing", "warning", 0, agg.volume_missing_periods,
                               "Some periods have an empty volume because a session's volume is empty."))
            conn.executemany("INSERT INTO quality_checks(run_id, dataset_id, check_name, severity, passed, rows_failed, "
                             "detail, checked_at) VALUES (?,?,?,?,?,?,?,?)",
                             [(run.run_id, new_id, *ck, now) for ck in checks])
    except Exception as exc:
        safe_remove(tmp)
        if placed:
            safe_remove(final)  # unregistered and unique to this run
        log.error("Derivation of %s from dataset %s failed: %s", timeframe, source_dataset_id, exc)
        return DerivationResult("failed", f"Deriving {timeframe} failed ({type(exc).__name__}: {exc}). Nothing was "
                                "registered.", assessment=a)
    log.info("Derived %s dataset %s from daily dataset %s (%d bars, %s)", timeframe, new_id, source_dataset_id,
             agg.row_count, PROCESSING_VERSION)
    note = f" {agg.edge_flags} edge period(s) flagged as possibly incomplete." if agg.edge_flags else ""
    return DerivationResult("created", f"{a.label}: {agg.row_count} bars created (dataset {new_id}).{note}", new_id, a)
