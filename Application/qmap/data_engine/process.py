"""Stages 3-5 of ingestion: map columns and parse dates, standardise, validate.

Input is a SourceTable (from any reader) and a SourceProfile; output is a ProcessResult with one
canonical frame per instrument plus every check result and row-level issue. Nothing here
modifies the source and nothing silently repairs or drops data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from ..core.config import Settings
from ..core.errors import IngestError
from . import canonical as C
from .datetime_parse import parse_times
from .instruments import instrument_key, normalise_exchange, normalise_symbol
from .mapping import SourceTable, resolve_column, safe_extra_name
from .numeric import INVALID, parse_number
from .profiles import MIXED, SourceProfile, canonical_timeframe
from .timeframe_infer import CONSISTENT, DEFAULT_SAMPLING, INSUFFICIENT, MIXED_STATUS, infer_from_parsed, infer_interval
from .results import ERROR, INFO, WARNING, CheckResult, Collector, Issue, examples
from .validation import GroupContext, merge_results, validate_group
from .volume import apply_volume

OHLC = ("open", "high", "low", "close")

# Checks that are produced from the parsing stages (always listed, passed or not).
_PARSE_CHECKS = (
    ("datetime_parseable", ERROR), ("date_in_range", ERROR), ("numeric_types", ERROR),
    ("volume_mapping_resolved", ERROR), ("instrument_declared", ERROR),
    ("date_order_unverified", WARNING), ("volume_columns_ignored", WARNING),
)


@dataclass
class GroupResult:
    exchange: str
    symbol: str
    timeframe: str
    frame: dict  # canonical columns (see canonical.py), sorted
    volume_status: str
    row_count: int
    date_from: str | None
    date_to: str | None
    is_instant: bool
    extra_columns: list
    volume_source_columns: list


@dataclass
class ProcessResult:
    accepted: bool
    groups: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    rows_read: int = 0
    rows_flagged: int = 0
    rows_accepted: int = 0
    transformations: list = field(default_factory=list)
    source_columns: list = field(default_factory=list)
    column_mapping: dict = field(default_factory=dict)
    datetime_rules: dict = field(default_factory=dict)
    volume_rule: dict = field(default_factory=dict)
    field_provenance: dict = field(default_factory=dict)
    fatal: IngestError | None = None


def _fatal(err: IngestError, rows_read: int, table: SourceTable | None, extra_checks=()) -> ProcessResult:
    checks = list(extra_checks) + [CheckResult(err.check, ERROR, False, 0, f"[{err.code}] {err.message}"
                                               + (f" Action: {err.action}" if err.action else ""))]
    issues = [Issue(err.check, ERROR, None, None, None, f"[{err.code}] {err.message}")]
    return ProcessResult(accepted=False, checks=checks, issues=issues, rows_read=rows_read,
                         source_columns=table.describe_columns() if table else [], fatal=err,
                         transformations=list(table.transformations) if table else [])


def _timeframe(profile: SourceProfile, filename: str, overrides: dict) -> str | None:
    """The DECLARED timeframe (profile, file-name pattern or typed value), or None. Since DQ-7 it is a cross-check
    only: the registered timeframe is the interval measured in the data (see _settle_timeframe)."""
    spec = profile.instrument
    tf = spec.timeframe
    if tf == "infer":
        return None
    if tf == "ingest":
        tf = overrides.get("timeframe")
        if not tf:
            return None
    elif tf == "filename_pattern":
        m = re.compile(spec.filename_pattern).search(filename)
        if not m or not m.group("timeframe"):
            raise IngestError(f"The file name {filename!r} does not fit this profile's file-name pattern "
                              f"{spec.filename_pattern!r}, so the timeframe cannot be read from it.",
                              code="E_TIMEFRAME_REQUIRED", check="instrument_declared",
                              action="Rename the file so that it fits the pattern, or use a profile that asks for the "
                                     "timeframe (timeframe = \"ingest\").")
        tf = dict(spec.timeframe_map).get(m.group("timeframe"), m.group("timeframe"))
    canon = canonical_timeframe(tf)
    if canon is None or canon == MIXED:
        raise IngestError(f"Timeframe {tf!r} is not a timeframe (examples: 1m, 5m, 75m, 1h, 2h, 1D, 1W, 1M).",
                          code="E_TIMEFRAME_REQUIRED", check="instrument_declared",
                          action="Add a timeframe_map to the profile, or correct the value.")
    return canon


def _settle_timeframe(declared: str | None, parsed, profile: SourceProfile, settings: Settings,
                      overrides: dict) -> tuple[str, list[CheckResult], dict]:
    """DQ-7: the interval MEASURED in the data (sampled blocks) is the timeframe. A declared value (profile, file name,
    typed) is a cross-check: a difference is a warning, never an override. MIXED when the blocks disagree."""
    zone = profile.datetime.exchange_timezone or profile.datetime.timezone or "UTC"
    cfg = {**DEFAULT_SAMPLING, **(getattr(settings, "timeframe_sampling", None) or {})}
    inf = infer_from_parsed(parsed, zone, cfg)
    record = inf.as_dict()
    source = {"ingest": "the value supplied when loading", "filename_pattern": "the file name"}.get(
        profile.instrument.timeframe, "the source profile")
    checks = []
    if inf.status == CONSISTENT and canonical_timeframe(inf.timeframe):
        tf = canonical_timeframe(inf.timeframe)
        why = f"{inf.summary}; {inf.rows_examined} of {inf.rows_total} rows examined"
    elif inf.status == MIXED_STATUS:
        tf = MIXED
        why = f"{inf.summary}; {inf.rows_examined} of {inf.rows_total} rows examined"
        checks.append(CheckResult("mixed_intervals", WARNING, False, len(inf.blocks),
                                  f"{inf.summary}. The data are kept as one dataset with timeframe MIXED; analyses "
                                  "that assume one uniform interval will say they cannot use it."))
    elif declared:
        tf = declared
        why = f"{inf.summary}; the declared {declared} from {source} is used"
        checks.append(CheckResult("timeframe_not_measurable", WARNING, False, 0,
                                  f"The bar interval could not be measured ({inf.reason}); the declared timeframe "
                                  f"{declared} from {source} was used without a cross-check."))
    else:
        raise IngestError(f"The bar interval cannot be measured from the data ({inf.reason}), and no timeframe was "
                          "declared.", code="E_TIMEFRAME_REQUIRED", check="instrument_declared",
                          action="Supply the timeframe when loading (it is used only when the data are too short to "
                                 "measure it).")
    record["registered"] = tf
    record["declared"] = declared
    checks.insert(0, CheckResult("timeframe_inferred", "info", True, 0, f"Timeframe {tf}: {why}."))
    if declared and tf != MIXED and inf.status == CONSISTENT and declared != tf:
        checks.append(CheckResult("timeframe_declared_differs", WARNING, False, 0,
                                  f"{source[:1].upper() + source[1:]} says {declared}, but the data are {tf} bars "
                                  f"({inf.summary.lower()}). The data are authoritative: registered as {tf}."))
    return tf, checks, record


def _per_instrument_timeframes(parsed, members: dict, order: list, tf_record: dict, profile: SourceProfile,
                               settings: Settings) -> list[CheckResult]:
    """DQ-7 applied to each instrument's own rows (file order). The file-level result must hold for every instrument
    that can be measured; otherwise one ERROR check (the file is rejected, with the per-instrument intervals). An
    instrument with too few rows to measure is reported as not verified (warning)."""
    zone = profile.datetime.exchange_timezone or profile.datetime.timezone or "UTC"
    cfg = {**DEFAULT_SAMPLING, **(getattr(settings, "timeframe_sampling", None) or {})}
    keys = list(parsed.ts_utc) if parsed.is_instant else list(parsed.session_dates)
    file_tf = tf_record.get("registered")
    per, differ, unmeasured = {}, [], []
    for ex_sym in order:
        label = instrument_key(*ex_sym)
        inf = infer_interval([keys[i] for i in members[ex_sym]], zone=zone, config=cfg)
        if inf.status == INSUFFICIENT:
            per[label] = "not measurable"
            unmeasured.append(label)
            continue
        tf = MIXED if inf.status == MIXED_STATUS else canonical_timeframe(inf.timeframe)
        per[label] = tf
        if tf != file_tf:
            differ.append(label)
    tf_record["per_instrument"] = per
    listing = "; ".join(f"{k}: {v}" for k, v in per.items())
    out = []
    if differ:
        out.append(CheckResult(
            "instrument_timeframes_differ", ERROR, False, len(differ),
            f"This file holds {len(order)} instruments. Measured on the whole file the bar interval is {file_tf}, but "
            f"measured on each instrument's own rows it is: {listing}. Q-MAP does not give one instrument another "
            "instrument's timeframe, so nothing from this file was registered. Action: split the file into one file "
            "per instrument (or per timeframe) and load those."))
    elif unmeasured:
        out.append(CheckResult(
            "instrument_timeframe_not_verified", WARNING, False, len(unmeasured),
            f"The bar interval of {', '.join(unmeasured)} could not be measured on its own rows (too few); the file's "
            f"interval {file_tf} is used for it. Per instrument: {listing}."))
    else:
        out.append(CheckResult("instrument_timeframes_agree", INFO, True, 0,
                               f"Every instrument in the file measured on its own rows has the file's interval "
                               f"{file_tf} ({listing})."))
    return out


def _scalar_instrument(kind: str, label: str, fixed, pattern: str | None, filename: str, override, normalise):
    if kind == "fixed":
        return normalise(fixed)
    if kind == "ingest":
        if not override:
            raise IngestError(f"The profile takes the {label} from the ingest request, but none was supplied.",
                              code="E_INSTRUMENT_REQUIRED", check="instrument_declared",
                              action=f"Supply the {label} when ingesting. Q-MAP never guesses instrument identity.")
        return normalise(override)
    if kind == "filename_pattern":
        m = re.compile(pattern).search(filename)
        if not m:
            # A value typed when loading is NOT used for a file-name profile (D2-26): do not suggest it.
            raise IngestError(f"The file name {filename!r} does not fit this profile's file-name pattern {pattern!r}, "
                              f"so the {label} cannot be read from it. This profile reads the {label} only from the "
                              "file name; a value typed when loading is not used.",
                              code="E_INSTRUMENT_REQUIRED", check="instrument_declared",
                              action="Rename the file so that it fits the pattern, or use a profile that asks for the "
                                     "exchange and symbol (exchange_from and symbol_from = \"ingest\").")
        return normalise(m.group(label))
    return None  # column-based: resolved per row


def _first_row_header_check(table: SourceTable, mapping: dict, profile: SourceProfile) -> CheckResult:
    """Profile says 'no header row', but row 1's date and price cells are all words such as 'time', 'open'.
    Advice only (a warning): row 1 is still treated as data, exactly as the profile declares, and its date and
    price checks still fail on their own."""
    cells = [table.columns[mapping[k]][0] for k in ("date", *OHLC)]
    wordy = all(isinstance(v, str) and re.search(r"[A-Za-z]", v)
                and parse_number(v, profile.file.decimal, profile.file.thousands)[1] == INVALID for v in cells)
    detail = ("" if not wordy else f"Row 1 looks like column names ({', '.join(repr(v) for v in cells)}), but the profile "
              "says the file has no header row. If it has one, choose a profile with header = true.")
    return CheckResult("first_row_looks_like_header", WARNING, not wordy, 1 if wordy else 0, detail)


def filename_identity_problem(profile: SourceProfile, filename: str) -> str | None:
    """None if every value this profile reads from the file NAME (exchange, symbol, timeframe) can be read from
    `filename` by the same rules ingestion uses; otherwise the reason, in plain words. Reads nothing from disk."""
    ins = profile.instrument
    try:
        for kind, label, normalise in ((ins.exchange_from, "exchange", normalise_exchange),
                                       (ins.symbol_from, "symbol", normalise_symbol)):
            if kind == "filename_pattern":
                _scalar_instrument(kind, label, None, ins.filename_pattern, filename, None, normalise)
        if ins.timeframe == "filename_pattern":
            _timeframe(profile, filename, {})
    except IngestError as exc:
        return f"{exc.message} {exc.action}".strip()
    return None


def process_table(table: SourceTable, profile: SourceProfile, settings: Settings, *, filename: str,
                  overrides: dict | None = None, today: date | None = None) -> ProcessResult:
    overrides = overrides or {}
    collector = Collector()
    n = table.n_rows
    checks_pre: list[CheckResult] = []

    try:
        if n == 0:
            return ProcessResult(
                accepted=False, rows_read=0, source_columns=table.describe_columns(),
                transformations=list(table.transformations),
                checks=[CheckResult("not_empty", ERROR, False, 0, "The file has a header but no data rows (or is empty).")],
                issues=[Issue("not_empty", ERROR, None, None, None, "No data rows were found.")])

        # --- map the mandatory columns ----------------------------------------------------
        mapping = {k: resolve_column(ref, table, field=k) for k, ref in profile.columns.items()}
        checks_pre.append(CheckResult("required_columns", ERROR, True, 0, ""))
        if not profile.file.header:
            checks_pre.append(_first_row_header_check(table, mapping, profile))
        timeframe = _timeframe(profile, filename, overrides)

        # --- instrument identity per row ---------------------------------------------------
        ispec = profile.instrument
        used = set(mapping.values())
        exch_const = _scalar_instrument(ispec.exchange_from, "exchange", ispec.exchange, ispec.filename_pattern, filename,
                                        overrides.get("exchange"), normalise_exchange)
        sym_const = _scalar_instrument(ispec.symbol_from, "symbol", ispec.symbol, ispec.filename_pattern, filename,
                                       overrides.get("symbol"), normalise_symbol)
        exch_idx = sym_idx = None
        if ispec.exchange_from == "column":
            exch_idx = resolve_column(ispec.exchange_column, table, field="exchange", check="instrument_declared")
            used.add(exch_idx)
        if ispec.symbol_from == "column":
            sym_idx = resolve_column(ispec.symbol_column, table, field="symbol", check="instrument_declared")
            used.add(sym_idx)
        row_instrument: list = [None] * n
        for i in range(n):
            try:
                e = exch_const if exch_idx is None else normalise_exchange(table.columns[exch_idx][i])
                s = sym_const if sym_idx is None else normalise_symbol(table.columns[sym_idx][i])
                row_instrument[i] = (e, s)
            except IngestError as exc:
                collector.add("instrument_declared", ERROR, i + 1, "instrument", None, exc.message)

        # --- numbers ---------------------------------------------------------------------
        ohlc = {}
        invalid = np.zeros(n, dtype=bool)
        for key in OHLC:
            arr = np.empty(n, dtype=float)
            for i, v in enumerate(table.columns[mapping[key]]):
                num, st = parse_number(v, profile.file.decimal, profile.file.thousands)
                arr[i] = num
                if st == INVALID:
                    invalid[i] = True
                    collector.add("numeric_types", ERROR, i + 1, key, v, f"{key.capitalize()} value {v!r} is not a number.")
            ohlc[key] = arr

        # --- dates -----------------------------------------------------------------------
        time_values = table.columns[mapping["time"]] if "time" in mapping else None
        parsed = parse_times(table.columns[mapping["date"]], profile.datetime, timeframe=None, settings=settings,
                             collector=collector, time_values=time_values, today=today)
        timeframe, tf_checks, tf_record = _settle_timeframe(timeframe, parsed, profile, settings, overrides)
        checks_pre.extend(tf_checks)

        # --- volume ----------------------------------------------------------------------
        vol = apply_volume(table, profile.volume, profile.file, collector)
    except IngestError as err:
        return _fatal(err, n, table, checks_pre)

    # Stop here if the row-level instrument identity could not be established.
    if collector.count("instrument_declared"):
        return _build_failed(collector, checks_pre, table, n, mapping, profile)

    # --- groups per instrument ---------------------------------------------------------------
    order_of_groups: list = []
    members: dict = {}
    for i, key in enumerate(row_instrument):
        if key not in members:
            members[key] = []
            order_of_groups.append(key)
        members[key].append(i)

    # Review 04-Nov-26 (C4): the timeframe is measured on the whole file. With several instruments in one file each
    # instrument is measured on its own as well; if any differs, nothing is registered (no instrument is given another
    # instrument's timeframe, and instruments with one interval each are not labelled MIXED because of each other).
    if len(order_of_groups) > 1:
        checks_pre.extend(_per_instrument_timeframes(parsed, members, order_of_groups, tf_record, profile, settings))
        if any(c.is_error for c in checks_pre):
            return _build_failed(collector, checks_pre, table, n, mapping, profile)

    require_volume = bool(settings.requirement_sets[profile.requirement_set].get("require_volume"))
    extra_idx = [j for j in range(table.n_cols) if (j not in used) and (profile.keep_unmapped or j in vol.source_indices)]
    taken: set = set(C.CORE_COLUMNS)
    extra_names = {j: safe_extra_name(table.names[j], j, taken) for j in extra_idx}

    groups: list[GroupResult] = []
    per_group_results: list = []
    all_removed: list = []  # (removed source row, kept source row), 1-based
    for ex_sym in order_of_groups:
        idx = members[ex_sym]
        label = instrument_key(*ex_sym)
        keys_src = [(parsed.ts_utc[i] if parsed.is_instant else parsed.session_dates[i]) for i in idx]
        inversions = sum(1 for a, b in zip(keys_src, keys_src[1:]) if a is not None and b is not None and a > b)
        order = sorted(range(len(idx)), key=lambda p: (keys_src[p] is None, keys_src[p] if keys_src[p] is not None else 0))
        moved = [order[p] != p for p in range(len(idx))]
        gi = [idx[p] for p in order]
        # repeated timestamps (DQ-10): drop exact duplicates, keep and flag conflicting observations
        keep, removed, conflicts = _repeated_timestamps(table, [keys_src[p] for p in order], gi)
        moved = [moved[r] for r in keep]
        gi = [gi[r] for r in keep]
        all_removed.extend(removed)

        frame: dict = {
            "session_date": [parsed.session_dates[i] for i in gi],
            "timestamp_utc": [parsed.ts_utc[i] for i in gi] if parsed.is_instant else [None] * len(gi),
        }
        for key in OHLC:
            frame[key] = ohlc[key][gi]
        has_vol = vol.values is not None
        frame["volume"] = np.array([vol.values[i] for i in gi], dtype=float) if has_vol else np.full(len(gi), np.nan)
        frame["src_row"] = np.array([i + 1 for i in gi], dtype=np.int64)
        flags = np.zeros(len(gi), dtype=np.int64)
        if has_vol:
            flags[~np.isfinite(frame["volume"])] |= C.FLAG_VOLUME_MISSING
        for p, i in enumerate(gi):
            if i in parsed.ambiguous_rows:
                flags[p] |= C.FLAG_DATE_ORDER_UNVERIFIED
            if moved[p]:
                flags[p] |= C.FLAG_MOVED_BY_SORT
            if i in conflicts:
                flags[p] |= C.FLAG_CONFLICTING_OBSERVATION
        frame["_sort_keys"] = [(parsed.ts_utc[i] if parsed.is_instant else parsed.session_dates[i]) for i in gi]

        gctx = GroupContext(label=label, settings=settings, profile=profile, timeframe=timeframe,
                            is_instant=parsed.is_instant, volume_status=vol.status, require_volume=require_volume,
                            source_inversions=inversions, invalid_ohlc=invalid[gi])
        out = validate_group(frame, gctx, collector)
        per_group_results.append((label, out.results + _repeat_checks(table, removed, conflicts, ohlc, vol, extra_idx,
                                                                      parsed, collector)))
        if out.large_move is not None and len(out.large_move) == len(gi):
            flags[out.large_move] |= C.FLAG_LARGE_MOVE
        frame["quality_flags"] = flags
        for j in extra_idx:
            frame[extra_names[j]] = [table.columns[j][i] for i in gi]
        dates = [d for d in frame["session_date"] if d is not None]
        groups.append(GroupResult(
            exchange=ex_sym[0], symbol=ex_sym[1], timeframe=timeframe, frame=frame, volume_status=vol.status,
            row_count=len(gi), date_from=min(dates).isoformat() if dates else None,
            date_to=max(dates).isoformat() if dates else None, is_instant=parsed.is_instant,
            extra_columns=[extra_names[j] for j in extra_idx],
            volume_source_columns=[extra_names[j] for j in vol.source_indices if j in extra_names]))

    # --- row accounting: every source row appears exactly once in the standardised output ---------
    # every source row is either in the standardised output or recorded as a removed exact duplicate
    seen = sorted([int(r) for g in groups for r in g.frame["src_row"]] + [r for r, _k in all_removed])
    accounted = seen == list(range(1, n + 1))
    checks_pre.append(CheckResult("row_accounting", ERROR, accounted, 0 if accounted else abs(n - len(seen)),
                                  f"{n} source row(s) read, {len(seen) - len(all_removed)} in the standardised output, "
                                  f"{len(all_removed)} removed as exact duplicates" if not accounted else ""))

    checks = checks_pre + _parse_check_results(collector) + merge_results(per_group_results)
    error_rows = sorted({i.row for i in collector.issues if i.severity == ERROR and i.row is not None})
    accepted = not any(c.is_error for c in checks)
    rows_flagged = len(error_rows)
    return ProcessResult(
        accepted=accepted, groups=groups, checks=checks, issues=list(collector.issues), rows_read=n,
        rows_flagged=rows_flagged, rows_accepted=n - rows_flagged,
        transformations=list(table.transformations) + _transformations(parsed, groups, per_group_results)
        + ([{"step": "exact_duplicates_removed", "rule": C.DUPLICATE_RULE, "count": len(all_removed),
             "removed_source_row_and_kept_source_row": sorted(all_removed)}] if all_removed else []),
        source_columns=table.describe_columns(),
        column_mapping={k: {"position": v, "name": table.names[v]} for k, v in mapping.items()},
        datetime_rules={"profile": {k: getattr(profile.datetime, k) for k in profile.datetime.__dataclass_fields__},
                        "applied": parsed.provenance, "timeframe": timeframe, "sort_rule": C.SORT_RULE,
                        "timeframe_inference": tf_record},
        volume_rule={"profile_rule": profile.volume.rule, "status": vol.status, **vol.provenance},
        field_provenance=_field_provenance(table, mapping, parsed, vol, extra_names, groups, profile))


def _cell(v):
    """A source cell for exact comparison: NaN equals NaN, everything else as read."""
    return None if isinstance(v, float) and v != v else v


def _repeated_timestamps(table: SourceTable, keys_sorted: list, gi: list) -> tuple[list, list, set]:
    """For one instrument's rows in time order: (positions to keep, removed exact duplicates as (row, kept row),
    source indices of conflicting observations). Exact duplicate = EVERY source column identical."""
    keep, removed, conflicts = [], [], set()
    p, n = 0, len(gi)
    while p < n:
        q = p
        while q + 1 < n and keys_sorted[p] is not None and keys_sorted[q + 1] == keys_sorted[p]:
            q += 1
        if q == p:
            keep.append(p)
        else:
            first_of: dict = {}
            kept_here = []
            for r in range(p, q + 1):  # stable sort: source order inside one timestamp
                sig = tuple(_cell(table.columns[j][gi[r]]) for j in range(table.n_cols))
                if sig in first_of:
                    removed.append((gi[r] + 1, gi[first_of[sig]] + 1))
                else:
                    first_of[sig] = r
                    kept_here.append(r)
            keep.extend(kept_here)
            if len(kept_here) > 1:
                conflicts.update(gi[r] for r in kept_here)
        p = q + 1
    return keep, removed, conflicts


def _when(k) -> str:
    return k.isoformat() if hasattr(k, "isoformat") else str(k)


def _repeat_checks(table, removed, conflicts, ohlc, vol, extra_idx, parsed, collector) -> list[CheckResult]:
    """exact_duplicates_removed (info) and conflicting_observations (warning, never an error: DQ-10)."""
    for r, kept in removed:
        collector.add("exact_duplicates_removed", INFO, r, "row", None,
                      f"Identical to source row {kept} in every column; removed from the standardised copy only.")
    dup = CheckResult("exact_duplicates_removed", INFO, True, len(removed),
                      "" if not removed else f"{len(removed)} exact duplicate row(s) removed from the standardised copy "
                      f"(the source file is unchanged): {examples([r for r, _k in removed])}")
    if not conflicts:
        return [dup, CheckResult("conflicting_observations", WARNING, True, 0, "")]
    key_of = (lambda i: parsed.ts_utc[i]) if parsed.is_instant else (lambda i: parsed.session_dates[i])
    by_key: dict = {}
    for i in sorted(conflicts):
        by_key.setdefault(key_of(i), []).append(i)
    fields_seen: set = set()
    extra_only = 0  # timestamps whose observations differ only in preserved extra columns, not in prices or volume
    shown = []
    for k in sorted(by_key):
        rows = by_key[k]
        diffs = []
        for name, values in [(f, [float(ohlc[f][i]) for i in rows]) for f in OHLC] + \
                [("volume", [None if vol.values is None else _cell(vol.values[i]) for i in rows])] + \
                [(table.names[j] or f"column {j + 1}", [_cell(table.columns[j][i]) for i in rows]) for j in extra_idx]:
            if len({repr(v) for v in values}) > 1:
                diffs.append((name, values))
                fields_seen.add(name)
        if diffs and all(name not in (*OHLC, "volume") for name, _v in diffs):
            extra_only += 1
        text = ", ".join(f"{name} " + " / ".join("" if v is None else f"{v:g}" if isinstance(v, float) else str(v)
                                                 for v in values) for name, values in diffs)
        msg = f"{_when(k)}: {len(rows)} observations (source rows {', '.join(str(i + 1) for i in rows)}) differ in {text}."
        for i in rows:
            collector.add("conflicting_observations", WARNING, i + 1, ", ".join(n for n, _v in diffs), None, msg)
        if len(shown) < 3:
            shown.append(msg)
    detail = (f"{len(by_key)} timestamp(s) have {len(conflicts)} conflicting observations (differing: "
              f"{', '.join(sorted(fields_seen))}). "
              + (f"{extra_only} of these timestamp(s) differ only in preserved extra column(s), not in open, high, "
                 "low, close or volume. " if extra_only else "")
              + f"All are kept and flagged; Q-MAP has not chosen between them. E.g. {' '.join(shown)}")
    return [dup, CheckResult("conflicting_observations", WARNING, False, len(conflicts), detail)]


def _build_failed(collector, checks_pre, table, n, mapping, profile) -> ProcessResult:
    error_rows = sorted({i.row for i in collector.issues if i.severity == ERROR and i.row is not None})
    return ProcessResult(
        accepted=False, checks=checks_pre + _parse_check_results(collector), issues=list(collector.issues), rows_read=n,
        rows_flagged=len(error_rows), rows_accepted=n - len(error_rows), transformations=list(table.transformations),
        source_columns=table.describe_columns(),
        column_mapping={k: {"position": v, "name": table.names[v]} for k, v in mapping.items()})


def _parse_check_results(collector: Collector) -> list[CheckResult]:
    out = []
    for name, severity in _PARSE_CHECKS:
        found = [i for i in collector.issues if i.check == name]
        rows = sorted({i.row for i in found if i.row is not None})
        detail = ""
        if found:
            detail = found[0].message if len(found) == 1 else f"{len(found)} issue(s); first: {found[0].message}"
            if rows:
                detail += f" ({examples(rows)})"
        out.append(CheckResult(name, severity, not found, len(rows), detail))
    return out


def _transformations(parsed, groups, per_group_results) -> list:
    steps = []
    if parsed.provenance.get("zero_padded_values"):
        steps.append({"step": "zero_padded_numeric_dates", "count": parsed.provenance["zero_padded_values"]})
    for g in groups:
        moved = int(np.sum((np.asarray(g.frame["quality_flags"]) & C.FLAG_MOVED_BY_SORT) != 0))
        steps.append({"step": "sorted_by_time", "instrument": f"{g.exchange}:{g.symbol}", "rows_moved": moved,
                      "rule": C.SORT_RULE})
    if parsed.is_instant:
        steps.append({"step": "converted_to_utc", "session_date": "derived in the declared exchange time zone"})
    return steps


def _field_provenance(table, mapping, parsed, vol, extra_names, groups, profile) -> dict:
    def src(i):
        return {"position": i, "name": table.names[i]}

    fp = {
        "session_date": ({"status": "derived", "rule": "date of the timestamp in the declared exchange time zone",
                          "source": src(mapping["date"])} if parsed.is_instant
                         else {"status": "mapped", "source": src(mapping["date"]), "rule": profile.datetime.kind}),
        "timestamp_utc": ({"status": "mapped", "source": src(mapping["date"]), "rule": f"{profile.datetime.kind} -> UTC"}
                          if parsed.is_instant else {"status": "absent", "reason": "source has dates without a time of day"}),
    }
    for k in OHLC:
        fp[k] = {"status": "mapped", "source": src(mapping[k])}
    fp["volume"] = ({"status": "absent", "reason": "the profile declares that the source has no volume"}
                    if vol.status == "absent" else {"status": vol.status, **vol.provenance})
    fp["src_row"] = {"status": "derived", "rule": "1-based position of the row in the source"}
    fp["quality_flags"] = {"status": "derived", "rule": {str(k): v for k, v in C.FLAG_DESCRIPTIONS.items()}}
    fp["preserved_columns"] = [{"column": name, "source": src(j)} for j, name in extra_names.items()]
    fp["note"] = "x_ columns are preserved original data and are not quantitative inputs"
    return fp
