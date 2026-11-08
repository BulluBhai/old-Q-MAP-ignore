"""Quality checks on the standardised data of one instrument/timeframe.

Checks never change data. Failed ERROR checks reject the whole attempt; warnings and info are
recorded. Optional fields are validated according to their availability and the intended use
(requirement set): a dataset without volume is valid price data unless the requirement set
says volume is required.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from ..core.config import Settings
from .profiles import INTRADAY_MINUTES, SourceProfile
from .results import ERROR, INFO, WARNING, CheckResult, Collector, examples


@dataclass
class GroupContext:
    label: str
    settings: Settings
    profile: SourceProfile
    timeframe: str
    is_instant: bool
    volume_status: str  # absent | mapped | derived_sum
    require_volume: bool
    source_inversions: int
    invalid_ohlc: np.ndarray  # rows whose OHLC text could not be read as a number (already reported)


@dataclass
class ValidationOutput:
    results: list = field(default_factory=list)
    large_move: np.ndarray | None = None


def _mask_result(out: list, collector: Collector, name: str, severity: str, mask: np.ndarray, src_row: np.ndarray,
                 field_: str, message, vals: dict | None = None) -> None:
    rows = [int(r) for r in src_row[mask]]
    if rows:
        for pos in np.flatnonzero(mask):
            collector.add(name, severity, int(src_row[pos]), field_, None, message(int(pos)))
    out.append(CheckResult(name, severity, not rows, len(rows), "" if not rows else f"{len(rows)} row(s): {examples(rows)}"))


def validate_group(frame: dict, ctx: GroupContext, collector: Collector) -> ValidationOutput:
    out: list[CheckResult] = []
    o, h, lo, c = (np.asarray(frame[k], dtype=float) for k in ("open", "high", "low", "close"))
    src = np.asarray(frame["src_row"], dtype=np.int64)
    vol = np.asarray(frame["volume"], dtype=float)
    keys = frame["_sort_keys"]
    n = len(src)
    s = ctx.settings
    has_volume = ctx.volume_status != "absent"

    out.append(CheckResult("not_empty", ERROR, n >= s.min_rows, 0 if n >= s.min_rows else n,
                           "" if n >= s.min_rows else f"{n} data row(s); at least {s.min_rows} required"))
    if n == 0:
        return ValidationOutput(out, np.zeros(0, dtype=bool))

    # --- finite OHLC values --------------------------------------------------------
    finite = np.isfinite(o) & np.isfinite(h) & np.isfinite(lo) & np.isfinite(c)
    missing = ~finite & ~ctx.invalid_ohlc

    def which(i):
        names = [k for k, arr in (("open", o), ("high", h), ("low", lo), ("close", c)) if not math.isfinite(arr[i])]
        return f"Missing or non-finite value in {', '.join(names)}."

    _mask_result(out, collector, "no_missing_values", ERROR, missing, src, "ohlc", which)
    ok = finite  # relation checks only look at rows with four usable numbers

    _mask_result(out, collector, "low_le_open_close", ERROR, ok & ((lo > o) | (lo > c)), src, "low",
                 lambda i: f"Low ({lo[i]}) is above Open ({o[i]}) or Close ({c[i]}).")
    _mask_result(out, collector, "high_ge_open_close", ERROR, ok & ((h < o) | (h < c)), src, "high",
                 lambda i: f"High ({h[i]}) is below Open ({o[i]}) or Close ({c[i]}).")
    _mask_result(out, collector, "low_le_high", ERROR, ok & (lo > h), src, "low",
                 lambda i: f"Low ({lo[i]}) is above High ({h[i]}).")
    _mask_result(out, collector, "prices_positive", ERROR, ok & ((o <= 0) | (h <= 0) | (lo <= 0) | (c <= 0)), src,
                 "ohlc", lambda i: f"Price is zero or negative (open {o[i]}, high {h[i]}, low {lo[i]}, close {c[i]}).")

    # --- volume: validated only according to availability and intended use ----------------
    if has_volume:
        present = np.isfinite(vol)
        _mask_result(out, collector, "volume_non_negative", ERROR, present & (vol < 0), src, "volume",
                     lambda i: f"Volume ({vol[i]}) is negative.")
        n_missing = int((~present).sum())
        if ctx.require_volume:
            miss_rows = [int(r) for r in src[~present]]
            for r in miss_rows:
                collector.add("volume_required", ERROR, r, "volume", None, "Volume is required by the requirement set but is empty.")
            out.append(CheckResult("volume_required", ERROR, n_missing == 0, n_missing,
                                   "" if n_missing == 0 else f"{n_missing} row(s) without volume: {examples(miss_rows)}"))
        vals = vol[present]
        const = vals.size >= 2 and bool(np.all(vals == vals[0]))
        out.append(CheckResult("constant_volume", WARNING, not const, int(vals.size) if const else 0,
                               "" if not const else f"Volume is {vals[0]:g} in every row, which looks like a placeholder."))
        if const:
            collector.add("constant_volume", WARNING, None, "volume", vals[0],
                          f"Volume is {vals[0]:g} in every row, which looks like a placeholder.")
        zeros = int((vals == 0).sum())
        out.append(CheckResult("zero_volume_bars", INFO, True, zeros, f"{zeros} bar(s) with zero volume" if zeros else ""))
    else:
        if ctx.require_volume:
            collector.add("volume_required", ERROR, None, "volume", None,
                          "The requirement set requires volume but the dataset has none.")
            out.append(CheckResult("volume_required", ERROR, False, n,
                                   "The requirement set requires volume but the dataset has none."))
        else:
            out.append(CheckResult("volume_required", INFO, True, 0, "Volume is absent and not required by the requirement set."))

    # --- order and duplicates -----------------------------------------------------------
    inv = ctx.source_inversions
    severity = ERROR if ctx.profile.on_unsorted == "error" else WARNING
    if inv:
        collector.add("source_order", severity, None, "date", None,
                      f"The source rows are not in time order ({inv} step(s) go backwards). "
                      "The standardised copy is sorted; src_row keeps the original positions.")
    out.append(CheckResult("source_order", severity, inv == 0, inv, "" if inv == 0 else f"{inv} out-of-order step(s) in the source"))

    dup_rows: list[int] = []
    for i in range(1, n):
        if keys[i] is not None and keys[i] == keys[i - 1]:
            dup_rows.extend([int(src[i - 1]), int(src[i])])
    dup_rows = sorted(set(dup_rows))
    for r in dup_rows:
        collector.add("no_duplicate_timestamps", ERROR, r, "date", None, "Another row has the same timestamp/date.")
    out.append(CheckResult("no_duplicate_timestamps", ERROR, not dup_rows, len(dup_rows),
                           "" if not dup_rows else f"{len(dup_rows)} row(s) share a timestamp: {examples(dup_rows)}"))

    # --- warnings about coverage and plausibility ----------------------------------------
    dates = [d for d in frame["session_date"] if d is not None]
    distinct = sorted(set(dates))
    gaps = [(a, b) for a, b in zip(distinct, distinct[1:]) if (b - a).days > s.max_gap_days]
    out.append(CheckResult("date_gaps", WARNING, not gaps, len(gaps),
                           "" if not gaps else "; ".join(f"{a} -> {b}" for a, b in gaps[:5]) + (" ..." if len(gaps) > 5 else "")))
    for a, b in gaps:
        collector.add("date_gaps", WARNING, None, "date", None, f"No data between {a} and {b} ({(b - a).days} days).")

    large = np.zeros(n, dtype=bool)
    if n > 1:
        prev = c[:-1]
        with np.errstate(divide="ignore", invalid="ignore"):
            move = np.abs(c[1:] / prev - 1.0) * 100.0
        big = np.isfinite(move) & (move > s.max_daily_move_pct)
        large[1:] = big
    for pos in np.flatnonzero(large):
        collector.add("large_moves", WARNING, int(src[pos]), "close", None,
                      f"Close moved more than {s.max_daily_move_pct:g}% from the previous bar.")
    out.append(CheckResult("large_moves", WARNING, not large.any(), int(large.sum()),
                           "" if not large.any() else f"{int(large.sum())} bar(s) moved more than {s.max_daily_move_pct:g}%: "
                           f"{examples([int(r) for r in src[large]])}"))

    if ctx.timeframe in INTRADAY_MINUTES and ctx.is_instant:
        expected = INTRADAY_MINUTES[ctx.timeframe]
        steps = [(keys[i] - keys[i - 1]).total_seconds() / 60.0 for i in range(1, n)
                 if keys[i] is not None and keys[i - 1] is not None and frame["session_date"][i] == frame["session_date"][i - 1]]
        med = float(np.median(steps)) if steps else float(expected)
        out.append(CheckResult("timeframe_spacing", WARNING, med == expected, 0 if med == expected else len(steps),
                               "" if med == expected else f"Bars are typically {med:g} minute(s) apart but the profile declares {ctx.timeframe}."))
        counts = Counter(d for d in frame["session_date"] if d is not None)
        if len(counts) >= 2:
            mode = Counter(counts.values()).most_common(1)[0][0]
            partial = sorted((d, k) for d, k in counts.items() if k < mode)
            detail = "; ".join(f"{d}: {k}/{mode} bars" for d, k in partial[:10]) + (" ..." if len(partial) > 10 else "")
            out.append(CheckResult("partial_session", WARNING, not partial, len(partial), "" if not partial else
                                   f"Sessions with fewer bars than the usual {mode}: {detail}"))
    elif ctx.timeframe in PERIOD_OF and (ctx.is_instant or ctx.timeframe != "1D"):
        # A daily/weekly/monthly dataset must have at most one bar per day/week/month. (Date-only daily data is already
        # covered by no_duplicate_timestamps.) Report-only: the declared timeframe is never changed or inferred.
        unit, key = PERIOD_OF[ctx.timeframe]
        per = Counter(key(d) for d in frame["session_date"] if d is not None)
        multi = sorted(k for k, cnt in per.items() if cnt > 1)
        detail = ("" if not multi else f"{len(multi)} {unit}(s) have more than one bar (e.g. "
                  + "; ".join(f"{k}: {per[k]} bars" for k in multi[:5])
                  + f"), so the data look finer than the declared timeframe {ctx.timeframe}.")
        out.append(CheckResult("one_bar_per_period", WARNING, not multi, len(multi), detail))
        if multi:
            collector.add("one_bar_per_period", WARNING, None, "date", None, detail)
    return ValidationOutput(out, large)


PERIOD_OF = {  # declared non-intraday timeframe -> (unit name, period key of a session date)
    "1D": ("day", lambda d: d.isoformat()),
    "1W": ("week", lambda d: "%04d-W%02d" % d.isocalendar()[:2]),
    "1M": ("month", lambda d: d.strftime("%Y-%m")),
}


def merge_results(per_group: list[tuple[str, list[CheckResult]]]) -> list[CheckResult]:
    """Combine same-named results from several instrument groups into one result per check."""
    merged: dict[str, CheckResult] = {}
    order: list[str] = []
    multi = len(per_group) > 1
    for label, results in per_group:
        for r in results:
            detail = (f"[{label}] {r.detail}" if multi and r.detail else r.detail)
            if r.name not in merged:
                merged[r.name] = CheckResult(r.name, r.severity, r.passed, r.rows_failed, detail)
                order.append(r.name)
            else:
                m = merged[r.name]
                m.passed = m.passed and r.passed
                m.rows_failed += r.rows_failed
                if detail:
                    m.detail = f"{m.detail}; {detail}" if m.detail else detail
    return [merged[k] for k in order]
