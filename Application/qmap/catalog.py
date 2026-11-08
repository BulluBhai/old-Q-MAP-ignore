"""The data catalogue: one read-only view of the Data Registry, shared by Database Manager and Analytical Workbench.

It answers "what data is there?" and "is this dataset ready for THIS use?". It never changes anything.

Three different things are kept apart on purpose:

* processing outcome  - the file was loaded (an accepted ingest attempt / a registered derivation);
* validation status   - what the quality checks found (`passed` or `passed_with_warnings`);
* readiness           - whether a dataset satisfies one analysis's specific requirements (`check_readiness`).

A dataset that loaded and validated can still be NOT ready for a given analysis (wrong timeframe, too little history,
no volume, superseded, file deleted ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pyarrow.compute as pc
import pyarrow.parquet as pq

from .core.config import Settings
from .core.dates import format_for_entry
from .data_engine import canonical as C
from .storage.db import Database
from .storage.files import sha256_file

TIMEFRAME_LABELS = {"1m": "1 minute", "5m": "5 minutes", "15m": "15 minutes", "30m": "30 minutes", "1h": "Hourly",
                    "4h": "4 hours", "1D": "Daily", "1W": "Weekly", "1M": "Monthly", "1Q": "Quarterly", "1Y": "Yearly"}
TIMEFRAME_ORDER = tuple(TIMEFRAME_LABELS)
INTRADAY_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h")
LAYER_LABELS = {"raw": "Original file", "cleaned": "Standardised", "timeframe": "Derived timeframe"}
VALIDATION_LABELS = {"passed": "Passed", "passed_with_warnings": "Passed with warnings"}
READ_COLUMNS = ("session_date", "timestamp_utc", "open", "high", "low", "close", "volume", "quality_flags")


def timeframe_label(tf: str | None) -> str:
    return TIMEFRAME_LABELS.get(tf or "", tf or "")


@dataclass
class DatasetInfo:
    dataset_id: int
    layer: str
    exchange: str
    symbol: str
    timeframe: str
    row_count: int | None
    date_from: str | None
    date_to: str | None
    storage_class: str
    relative_path: str
    status: str  # active | superseded
    file_deleted_at: str | None
    processing_version: str | None
    canonical_schema_version: int | None
    volume_status: str | None
    requirement_set: str | None
    config_fingerprint: str | None
    sha256: str
    created_at: str
    parent_dataset_id: int | None
    validation_status: str = "passed"
    warnings: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)  # original file name(s) this data came from

    @property
    def instrument(self) -> str:
        return f"{self.exchange}:{self.symbol}" if self.exchange else ""

    @property
    def timeframe_label(self) -> str:
        return timeframe_label(self.timeframe)

    @property
    def available(self) -> bool:
        return self.file_deleted_at is None

    @property
    def state_label(self) -> str:
        if self.file_deleted_at:
            return "File deleted"
        return "Active" if self.status == "active" else "Superseded"

    @property
    def storage_label(self) -> str:
        return "Temporary" if self.storage_class == "temporary" else "Permanent"


def _warnings_for(db: Database, row) -> list[str]:
    if row["layer"] == "cleaned":
        # the checks of the attempt that created it, plus checks recorded later on the dataset itself (for example
        # a conflict with another dataset found when it was registered from a folder scan)
        checks = db.query("SELECT check_name, detail FROM quality_checks WHERE (attempt_id = ? OR dataset_id = ?) AND "
                          "severity = 'warning' AND passed = 0 ORDER BY check_id",
                          (row["created_by_attempt_id"], row["dataset_id"]))
    else:
        checks = db.query("SELECT check_name, detail FROM quality_checks WHERE dataset_id = ? AND severity = 'warning' "
                          "AND passed = 0 ORDER BY check_id", (row["dataset_id"],))
    return [f"{c['check_name']}: {c['detail']}" if c["detail"] else c["check_name"] for c in checks]


def _source_files(db: Database, row) -> list[str]:
    attempt = row["created_by_attempt_id"]
    if attempt is None:
        return []
    names = db.query("SELECT DISTINCT e.original_filename FROM ingest_attempts a JOIN ingest_events e USING (event_id) "
                     "WHERE a.raw_dataset_id = (SELECT raw_dataset_id FROM ingest_attempts WHERE attempt_id = ?) "
                     "AND a.outcome IN ('accepted','reused') ORDER BY 1", (attempt,))
    return [r["original_filename"] for r in names]


def _info(db: Database, row, details: bool = True) -> DatasetInfo:
    info = DatasetInfo(
        dataset_id=row["dataset_id"], layer=row["layer"], exchange=row["exchange"] or "", symbol=row["symbol"] or "",
        timeframe=row["timeframe"] or "", row_count=row["row_count"], date_from=row["date_from"], date_to=row["date_to"],
        storage_class=row["storage_class"], relative_path=row["relative_path"], status=row["status"],
        file_deleted_at=row["file_deleted_at"], processing_version=row["processing_version"],
        canonical_schema_version=row["canonical_schema_version"], volume_status=row["volume_status"],
        requirement_set=row["requirement_set"], config_fingerprint=row["config_fingerprint"], sha256=row["sha256"],
        created_at=row["created_at"], parent_dataset_id=row["parent_dataset_id"])
    if details and row["layer"] != "raw":
        info.warnings = _warnings_for(db, row)
        info.validation_status = "passed_with_warnings" if info.warnings else "passed"
        info.source_files = _source_files(db, row)
    return info


_SELECT = ("SELECT d.*, i.exchange, i.symbol FROM datasets d LEFT JOIN instruments i USING (instrument_id) ")


def list_datasets(db: Database, *, include_superseded: bool = True, include_deleted: bool = True,
                  timeframes: tuple[str, ...] | None = None, details: bool = True) -> list[DatasetInfo]:
    """Every managed (standardised or derived) dataset, ordered by instrument, timeframe and dataset number."""
    rows = db.query(_SELECT + "WHERE d.layer <> 'raw' ORDER BY i.exchange, i.symbol, d.timeframe, d.dataset_id")
    out = []
    for r in rows:
        if not include_superseded and r["status"] != "active":
            continue
        if not include_deleted and r["file_deleted_at"]:
            continue
        if timeframes is not None and r["timeframe"] not in timeframes:
            continue
        out.append(_info(db, r, details))
    order = {tf: n for n, tf in enumerate(TIMEFRAME_ORDER)}
    out.sort(key=lambda d: (d.exchange, d.symbol, order.get(d.timeframe, 99), d.dataset_id))
    return out


def get_dataset(db: Database, dataset_id: int) -> DatasetInfo | None:
    row = db.one(_SELECT + "WHERE d.dataset_id = ?", (dataset_id,))
    return _info(db, row) if row is not None else None


@dataclass
class DataOverview:
    instruments: int
    datasets_active: int
    datasets_superseded: int
    datasets_deleted: int
    permanent: int
    temporary: int
    raw_files: int
    by_timeframe: dict  # timeframe -> number of active datasets with a file


def overview(db: Database) -> DataOverview:
    one = lambda sql: db.one(sql)[0]  # noqa: E731
    by_tf = {r["timeframe"]: r["n"] for r in db.query(
        "SELECT timeframe, COUNT(*) AS n FROM datasets WHERE layer <> 'raw' AND status = 'active' AND file_deleted_at "
        "IS NULL GROUP BY timeframe")}
    return DataOverview(
        instruments=one("SELECT COUNT(*) FROM instruments"),
        datasets_active=one("SELECT COUNT(*) FROM datasets WHERE layer <> 'raw' AND status = 'active' AND file_deleted_at IS NULL"),
        datasets_superseded=one("SELECT COUNT(*) FROM datasets WHERE layer <> 'raw' AND status = 'superseded' AND file_deleted_at IS NULL"),
        datasets_deleted=one("SELECT COUNT(*) FROM datasets WHERE file_deleted_at IS NOT NULL"),
        permanent=one("SELECT COUNT(*) FROM datasets WHERE layer <> 'raw' AND storage_class = 'permanent' AND file_deleted_at IS NULL"),
        temporary=one("SELECT COUNT(*) FROM datasets WHERE layer <> 'raw' AND storage_class = 'temporary' AND file_deleted_at IS NULL"),
        raw_files=one("SELECT COUNT(*) FROM datasets WHERE layer = 'raw'"),
        by_timeframe={tf: by_tf[tf] for tf in sorted(by_tf, key=lambda t: TIMEFRAME_ORDER.index(t) if t in TIMEFRAME_ORDER else 99)})


def provenance(db: Database, dataset_id: int) -> list[str]:
    """Plain-English lineage from this dataset back to the original file(s)."""
    lines, current, seen = [], dataset_id, set()
    while current is not None and current not in seen:
        seen.add(current)
        row = db.one(_SELECT + "WHERE d.dataset_id = ?", (current,))
        if row is None:
            break
        if row["layer"] == "raw":
            files = db.query("SELECT original_filename, received_at FROM ingest_events WHERE raw_dataset_id = ? "
                             "ORDER BY event_id", (current,))
            names = ", ".join(sorted({f["original_filename"] for f in files})) or "(unknown name)"
            lines.append(f"Original file (dataset {current}), preserved unchanged, SHA-256 {row['sha256'][:16]}...: {names}")
        elif row["layer"] == "timeframe":
            d = db.one("SELECT * FROM dataset_derivations WHERE dataset_id = ?", (current,))
            how = f"{d['method']} v{d['method_version']} (run {d['run_id']})" if d else row["processing_version"]
            lines.append(f"Derived {timeframe_label(row['timeframe'])} dataset {current}: {how}, from dataset "
                         f"{row['parent_dataset_id']}")
        else:
            a = db.one("SELECT run_id, profile_id, profile_version, config_fingerprint FROM ingest_attempts "
                       "WHERE attempt_id = ?", (row["created_by_attempt_id"],))
            lines.append(f"Standardised {timeframe_label(row['timeframe'])} dataset {current}: "
                         f"{row['processing_version']}, settings {row['config_fingerprint']}"
                         + (f", run {a['run_id']}" if a else "") + f", from original file dataset {row['parent_dataset_id']}")
        current = row["parent_dataset_id"]
    return lines


# ---- readiness --------------------------------------------------------------------------------------------------
PASS, WARN, FAIL = "pass", "warn", "fail"


@dataclass(frozen=True)
class DataRequirement:
    """What one analysis needs from each dataset it uses."""

    timeframes: tuple[str, ...]
    min_rows: int = 1
    require_volume: bool = False
    date_from: date | None = None  # the analysis window, if any
    date_to: date | None = None
    allow_superseded: bool = False
    required_columns: tuple[str, ...] = ("session_date", "open", "high", "low", "close")


@dataclass
class ReadinessItem:
    name: str
    status: str  # pass | warn | fail
    detail: str


@dataclass
class ReadinessReport:
    dataset_id: int
    label: str
    items: list[ReadinessItem] = field(default_factory=list)
    rows_in_window: int | None = None
    no_eligible_bars: bool = False  # valid period, but not a single bar of this dataset falls inside it

    @property
    def ready(self) -> bool:
        return not any(i.status == FAIL for i in self.items)

    @property
    def failures(self) -> list[ReadinessItem]:
        return [i for i in self.items if i.status == FAIL]

    @property
    def warnings(self) -> list[ReadinessItem]:
        return [i for i in self.items if i.status == WARN]

    def add(self, name: str, status: str, detail: str) -> None:
        self.items.append(ReadinessItem(name, status, detail))


def fmt_date(iso: str | date | None) -> str:
    """dd-mmm-yy for people (registry dates are stored as ISO text)."""
    if iso is None or iso == "":
        return "-"
    d = iso if isinstance(iso, date) else date.fromisoformat(str(iso)[:10])
    # Not strftime: on Windows "%y" refuses years before 1900, and a person may type such a start date. The shared
    # writer gives the same text for 1969-2068 (05-Jan-26) and keeps four digits otherwise (01-Jan-0001).
    return format_for_entry(d)


def check_readiness(settings: Settings, db: Database, dataset_id: int, req: DataRequirement, *,
                    verify_checksum: bool = True) -> ReadinessReport:
    """Check one dataset against one analysis's requirements. Registration alone never means ready."""
    info = get_dataset(db, dataset_id)
    rep = ReadinessReport(dataset_id, f"dataset {dataset_id}")
    if info is None:
        rep.add("registered", FAIL, f"Dataset {dataset_id} is not in the Data Registry.")
        return rep
    rep.label = f"{info.instrument} {info.timeframe_label} (dataset {dataset_id})"
    rep.add("registered", PASS, f"Registered: {LAYER_LABELS.get(info.layer, info.layer)}, {info.storage_label}.")
    if info.layer == "raw":
        rep.add("standardised", FAIL, "This is an original source file. Analyses use standardised datasets; prepare it "
                                      "in Database Manager first.")
        return rep
    if info.file_deleted_at:
        rep.add("file_present", FAIL, f"Its file was deleted on {fmt_date(info.file_deleted_at)}. Prepare the data "
                                      "again in Database Manager.")
        return rep
    if info.status != "active":
        rep.add("current", WARN if req.allow_superseded else FAIL,
                "This dataset has been SUPERSEDED by a newer processing of the same data; use the active dataset.")
    else:
        rep.add("current", PASS, "Active (not superseded).")
    path = settings.data_path(info.relative_path)
    try:
        schema = pq.read_schema(str(path))
    except (OSError, ValueError) as exc:
        rep.add("file_readable", FAIL, f"The registered file cannot be read ({info.relative_path}): {exc}. Run 'verify' "
                                       "in Database Manager.")
        return rep
    rep.add("file_readable", PASS, "File present and readable.")
    if verify_checksum:
        if sha256_file(path) != info.sha256:
            rep.add("checksum", FAIL, "The file does not match its registered checksum; it may have been changed or "
                                      "damaged. Do not use it until it is investigated.")
            return rep
        rep.add("checksum", PASS, "Checksum matches the registry.")
    if (info.canonical_schema_version or 0) > C.CANONICAL_SCHEMA_VERSION:
        rep.add("schema", FAIL, f"Written with a newer data structure (version {info.canonical_schema_version}) than "
                                f"this Q-MAP understands ({C.CANONICAL_SCHEMA_VERSION}).")
    else:
        rep.add("schema", PASS, f"Data structure version {info.canonical_schema_version}.")
    missing = [c for c in req.required_columns if c not in schema.names]
    rep.add("columns", FAIL if missing else PASS,
            f"Missing column(s): {', '.join(missing)}." if missing else "All required columns are present.")
    if info.timeframe in req.timeframes:
        rep.add("timeframe", PASS, f"Timeframe {info.timeframe_label} is supported by this analysis.")
    else:
        wanted = ", ".join(timeframe_label(t) for t in req.timeframes)
        rep.add("timeframe", FAIL, f"Timeframe {info.timeframe_label} is not supported here (needs: {wanted}).")
    if req.require_volume and info.volume_status == "absent":
        rep.add("volume", FAIL, "This analysis needs volume, and this dataset has none.")
    elif req.require_volume:
        rep.add("volume", PASS, "Volume is available.")
    rep.add("validation", WARN if info.warnings else PASS,
            ("Validated with warnings: " + "; ".join(info.warnings[:4])) if info.warnings else "Validation passed.")
    if info.storage_class == "temporary":
        rep.add("storage", WARN, "Temporary dataset: results will reference it, but you may delete it later.")

    # history inside the requested window
    window = info.row_count or 0
    if req.date_from or req.date_to:
        try:
            table = pq.read_table(str(path), columns=["session_date"])
            dates = table.column("session_date")
            mask = None
            if req.date_from:
                mask = pc.greater_equal(dates, req.date_from)
            if req.date_to:
                m2 = pc.less_equal(dates, req.date_to)
                mask = m2 if mask is None else pc.and_(mask, m2)
            window = int(pc.sum(pc.cast(mask, "int64")).as_py() or 0)
        except Exception as exc:  # reading failed although the schema could be read
            rep.add("coverage", FAIL, f"The dates could not be read: {exc}.")
            return rep
        first, last = (date.fromisoformat(info.date_from[:10]) if info.date_from else None,
                       date.fromisoformat(info.date_to[:10]) if info.date_to else None)
        if req.date_from and first and first > req.date_from:
            rep.add("coverage_start", WARN, f"The data start on {fmt_date(first)}, after the requested start "
                                            f"{fmt_date(req.date_from)}.")
        if req.date_to and last and last < req.date_to:
            rep.add("coverage_end", WARN, f"The data end on {fmt_date(last)}, before the requested end "
                                          f"{fmt_date(req.date_to)}.")
    rep.rows_in_window = window
    if window == 0 and (req.date_from or req.date_to):
        rep.no_eligible_bars = True
        period = f"{fmt_date(req.date_from) if req.date_from else 'the first bar'} to " \
                 f"{fmt_date(req.date_to) if req.date_to else 'the last bar'}"
        rep.add("history", FAIL, f"The dates are valid, but this dataset has no bars from {period}. Its data cover "
                                 f"{fmt_date(info.date_from)} to {fmt_date(info.date_to)}. This analysis needs at least "
                                 f"{req.min_rows} bar(s).")
    elif window < req.min_rows:
        rep.add("history", FAIL, f"Only {window} bar(s) in the chosen period; this analysis needs at least {req.min_rows}.")
    else:
        rep.add("history", PASS, f"{window} bar(s) available "
                                 f"({fmt_date(info.date_from)} to {fmt_date(info.date_to)} overall).")
    return rep


def read_dataset(settings: Settings, db: Database, dataset_id: int, *, date_from: date | None = None,
                 date_to: date | None = None):
    """The quantitative columns of a registered dataset (never the preserved x_ columns), optionally for a window."""
    info = get_dataset(db, dataset_id)
    if info is None or not info.available:
        raise ValueError(f"dataset {dataset_id} is not available")
    path = settings.data_path(info.relative_path)
    names = pq.read_schema(str(path)).names
    table = pq.read_table(str(path), columns=[c for c in READ_COLUMNS if c in names])
    if date_from or date_to:
        dates = table.column("session_date")
        mask = None
        if date_from:
            mask = pc.greater_equal(dates, date_from)
        if date_to:
            m2 = pc.less_equal(dates, date_to)
            mask = m2 if mask is None else pc.and_(mask, m2)
        table = table.filter(mask)
    return table
