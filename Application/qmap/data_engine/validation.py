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
from datetime import datetime
from zoneinfo import ZoneInfo

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


def _distinct_in_order(dates: list, keys: list) -> list:
    """(date, key) pairs in stored order, each distinct timestamp once (a repeated timestamp is one bar position).
    Stored order, not a set: Counter.most_common breaks ties by first appearance, so the result must not depend on
    hash order."""
    seen, out = set(), []
    for d, k in zip(dates, keys):
        if d is not None and (d, k) not in seen:
            seen.add((d, k))
            out.append((d, k))
    return out


CHANGE_RUN = 30  # consecutive steps (or trading dates) that make a section "another interval" (= one sample block)
SAME_TIME_SHARE = 0.9  # share of one-bar dates at one time of day that makes a daily-like grid (= consistency_share)


def _classify_step_run(step: float, expected: int) -> str:
    """'definite' when missing bars cannot explain the step (it is not a whole multiple of the expected interval,
    e.g. 3 or 7 minutes in 5-minute data, or anything finer); 'uncertain' when it is a whole multiple (2, 3 ... times
    the interval): a REGULAR grid of k-times-the-interval steps is either another interval or bars systematically
    missing at every k-th position, and the timestamps cannot tell these apart.
    Randomly missing bars do not reach this function: with independent gaps a step of k intervals has probability
    q(1-q)^(k-1) <= 0.25, so CHANGE_RUN = 30 identical steps in a row have probability <= 0.25^30 (about 1e-18)."""
    ratio = step / expected
    return "uncertain" if ratio > 1 and abs(ratio - round(ratio)) < 1e-9 else "definite"


def _interval_changes(frame: dict, keys: list, src, expected: int, timeframe: str, collector: Collector,
                      zone: str | None = None) -> list[CheckResult]:
    """Full-file verification of the sampled timeframe (review 03-Nov-26, refined after the second review). Sampling
    can miss a short section between blocks; validation reads every row anyway. Report only: the registered timeframe
    is never changed here (owner decision DQ-14).

    Sections found (unchanged detection):
    - a run of at least CHANGE_RUN consecutive same-day steps that all have ONE other interval;
    - a run of at least CHANGE_RUN consecutive trading dates with a single bar each, while other dates have several.
    Classification (second review): a section is ASSERTED as another interval (`interval_change_detected`) only when
    missing observations cannot explain it; otherwise it is reported as UNCERTAIN (`interval_change_uncertain`), and
    scattered sparse observations are not reported at all:
    - steps that are not whole multiples of the interval -> detected;
    - a regular grid of whole multiples (2m in 1m data, 10m in 5m data, a 5-minute tail in 1-minute data) -> uncertain;
    - one-bar dates at one time of day (>= SAME_TIME_SHARE of them) outside the times of day the multi-bar dates use
      (e.g. midnight-stamped daily bars) -> detected; at one time of day inside that range -> uncertain;
    - one-bar dates at varying times of day -> a sparse instrument, not another interval: nothing reported here
      (the dates remain in partial_session)."""
    definite, uncertain = [], []
    run_val, run_start, run_len = None, None, 0
    dates = frame["session_date"]

    def close(end_row):
        if run_val is not None and run_val != expected and run_len >= CHANGE_RUN:
            text = f"source rows {run_start}-{end_row}: {run_len} consecutive steps of {run_val:g} minute(s)"
            if _classify_step_run(run_val, expected) == "definite":
                definite.append(text)
            else:
                uncertain.append(text + f" (a whole multiple of {expected:g}: another interval, or bars present "
                                        f"only every {round(run_val / expected)} intervals)")

    last_end = None
    for i in range(1, len(keys)):
        a, b = keys[i - 1], keys[i]
        if a is None or b is None or a == b or dates[i] != dates[i - 1]:
            continue
        step = (b - a).total_seconds() / 60.0
        if step == run_val and last_end == i - 1:
            run_len += 1
        else:
            close(int(src[last_end]) if last_end is not None else None)
            run_val, run_start, run_len = step, int(src[i - 1]), 1
        last_end = i
    close(int(src[last_end]) if last_end is not None else None)

    # daily-like section: consecutive trading dates with one bar each, while other dates have several. (Until the
    # third review this required the MOST COMMON date to have several bars, so a file with more one-bar dates than
    # intraday dates was never checked; the branch only runs when sampling found an intraday interval.)
    distinct = _distinct_in_order(dates, keys)
    per_date = Counter(d for d, _k in distinct)
    if per_date and any(v > 1 for v in per_date.values()):
        tz = _zone(zone)
        first_row, single_time = {}, {}
        multi_times = set()
        for d, r in zip(dates, src):
            first_row.setdefault(d, int(r))
        for d, k in distinct:
            if not isinstance(k, datetime):
                continue
            t = k.astimezone(tz).time() if tz is not None else k.time()
            if per_date[d] == 1:
                single_time[d] = t
            else:
                multi_times.add(t)
        lo_t, hi_t = (min(multi_times), max(multi_times)) if multi_times else (None, None)
        run = []
        for d in sorted(per_date) + [None]:
            if d is not None and per_date[d] == 1:
                run.append(d)
                continue
            if len(run) >= CHANGE_RUN:
                text = (f"source rows {first_row[run[0]]}-{first_row[run[-1]]}: {len(run)} consecutive trading "
                        f"dates with one bar each ({run[0]} to {run[-1]})")
                times = Counter(single_time.get(x) for x in run)
                t, cnt = times.most_common(1)[0]
                if t is None or cnt < SAME_TIME_SHARE * len(run):
                    pass  # varying times of day: a sparse instrument (missing observations), not another interval
                elif lo_t is not None and lo_t <= t <= hi_t:
                    uncertain.append(text + f", all at {t.strftime('%H:%M')}, a time the intraday bars also use "
                                            "(daily data, or only one intraday bar per date)")
                else:
                    definite.append(text + f", all at {t.strftime('%H:%M')}, outside the times of the intraday bars, "
                                           "like daily data")
            run = []

    out = []
    for name, sections, lead, advice in (
            ("interval_change_detected", definite, "the full file contains section(s) with another interval",
             "Treat results across these sections with care; consider splitting the file."),
            ("interval_change_uncertain", uncertain,
             "the full file contains section(s) on a regular coarser grid; the timestamps cannot show whether this is "
             "another interval or systematically missing bars",
             "Check the source for these sections; the registered timeframe is unchanged.")):
        detail = ""
        if sections:
            detail = (f"The sampled timeframe is {timeframe}, but {lead}: " + "; ".join(sections[:5])
                      + (" ..." if len(sections) > 5 else "") + ". " + advice)
            collector.add(name, WARNING, None, "date", None, detail)
        out.append(CheckResult(name, WARNING, not sections, len(sections), detail))
    return out


def _zone(name: str | None):
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - an unknown zone falls back to UTC times of day (comparison stays consistent)
        return None


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

    # Repeated timestamps (instruction DQ-10, 03-Nov-26): exact duplicate rows were removed before validation and
    # rows that share a timestamp with different values are kept and reported as conflicting_observations (both done
    # in process.py). Neither rejects the file. The checks below count DISTINCT timestamps where that matters.

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
                 if keys[i] is not None and keys[i - 1] is not None and keys[i] != keys[i - 1]
                 and frame["session_date"][i] == frame["session_date"][i - 1]]
        med = float(np.median(steps)) if steps else float(expected)
        out.append(CheckResult("timeframe_spacing", WARNING, med == expected, 0 if med == expected else len(steps),
                               "" if med == expected else f"Bars are typically {med:g} minute(s) apart but the profile declares {ctx.timeframe}."))
        counts = Counter(d for d, _k in _distinct_in_order(frame["session_date"], keys))
        if len(counts) >= 2:
            mode = Counter(counts.values()).most_common(1)[0][0]
            partial = sorted((d, k) for d, k in counts.items() if k < mode)
            detail = "; ".join(f"{d}: {k}/{mode} bars" for d, k in partial[:10]) + (" ..." if len(partial) > 10 else "")
            out.append(CheckResult("partial_session", WARNING, not partial, len(partial), "" if not partial else
                                   f"Sessions with fewer bars than the usual {mode}: {detail}"))
        out.extend(_interval_changes(frame, keys, src, expected, ctx.timeframe, collector,
                                     ctx.profile.datetime.exchange_timezone))
    elif ctx.timeframe in PERIOD_OF and (ctx.is_instant or ctx.timeframe != "1D"):
        # A daily/weekly/monthly dataset must have at most one bar per day/week/month. (Date-only daily data is already
        # a repeated date is a conflict, reported separately.) Report-only: the timeframe is never changed here.
        # Distinct timestamps are counted, so conflicting observations of ONE timestamp do not look like finer data.
        unit, key = PERIOD_OF[ctx.timeframe]
        per = Counter(key(d) for d, _k in _distinct_in_order(frame["session_date"], keys))
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
