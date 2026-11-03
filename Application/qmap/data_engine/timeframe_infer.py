"""Timeframe inference from the timestamps themselves, by SAMPLING (owner instruction DQ-7, 03-Nov-26).

The bar interval is a property of the data, not of a label list, a file name, a typed value or an exchange calendar.

Method (reproducible and explainable):
1. The first `initial_rows` (about 20) observations give a CANDIDATE interval.
2. The candidate decides how many validation BLOCKS to sample (configurable, `[timeframe_sampling]`):
   1-2 minutes 20, 3-15 minutes 15, 16-59 minutes 10, hourly and multi-hour 10, daily 5, weekly or longer 5.
   Each block is `block_rows` successive observations. Block positions are stratified over the file (one random
   position inside each equal part), drawn from a random generator seeded from the data's own size and first/last
   timestamps plus the configuration, so the same file and configuration always give the same blocks.
   Small files get fewer blocks (as many as fit); a file shorter than two blocks is examined whole.
3. In every block the steps between successive observations are measured: intraday steps only between observations
   of the same trading date (so overnight, weekend and holiday gaps are ignored), daily-and-longer steps in calendar
   days. Repeated timestamps (zero steps) are ignored. The block's interval is its most common step.
4. The dominant interval is the most common block interval. A block agrees with it when at least `consistency_share`
   of its steps are whole multiples of it (gaps of 2, 3 ... intervals are missing bars, not another timeframe) AND the
   interval itself occurs in the block, or is the block's own most common step. If every block agrees: CONSISTENT. If
   blocks show materially different intervals: MIXED (reported; never forced into one timeframe).
5. No exchange or session calendar is used anywhere: a gap is never explained or filled, only measured.

Only the sampled observations are examined for the timeframe; every row is still parsed and validated elsewhere,
because data integrity (dates, OHLC, duplicates) needs all of them.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from ..core.timeframes import MIXED, minutes_label

DEFAULT_SAMPLING = {
    "initial_rows": 20,      # observations used for the candidate interval
    "block_rows": 30,        # successive observations per validation block
    "blocks_1_2m": 20,       # candidate about 1-2 minutes
    "blocks_3_15m": 15,      # 3-15 minutes
    "blocks_16_59m": 10,     # above 15 and below 60 minutes
    "blocks_hourly": 10,     # hourly and multi-hour
    "blocks_daily": 5,
    "blocks_weekly": 5,      # weekly or longer
    "consistency_share": 0.9,  # share of a block's steps that must be whole multiples of the interval
    "seed": 20261103,        # part of the reproducible sampling seed
}

CONSISTENT, MIXED_STATUS, INSUFFICIENT = "consistent", "mixed", "insufficient"
MIN_STEPS = 2  # a block (or the whole file) needs at least this many measured steps


@dataclass
class Block:
    start_row: int  # 1-based position of the block's first observation in the file
    rows: int
    interval: str | None
    steps: int
    agreeing_share: float = 0.0
    agrees: bool = False

    def as_dict(self) -> dict:
        return {"start_row": self.start_row, "rows": self.rows, "interval": self.interval, "steps": self.steps,
                "agreeing_share": round(self.agreeing_share, 3), "agrees": self.agrees}


@dataclass
class Inference:
    status: str                      # consistent | mixed | insufficient
    timeframe: str | None            # e.g. 5m, 75m, 2h, 1D, 1W, 1M; MIXED when mixed; None when insufficient
    candidate: str | None = None
    blocks: list = field(default_factory=list)
    rows_total: int = 0
    rows_examined: int = 0
    seed: int = 0
    patterns: dict = field(default_factory=dict)  # interval -> number of blocks (useful for MIXED)
    reason: str = ""

    @property
    def summary(self) -> str:
        n = len(self.blocks)
        if self.status == CONSISTENT:
            return f"Consistent across {n} sampled block(s)"
        if self.status == MIXED_STATUS:
            pats = ", ".join(f"{k} in {v} block(s)" for k, v in sorted(self.patterns.items(), key=lambda kv: -kv[1]))
            return f"Mixed or inconsistent intervals across {n} sampled block(s): {pats}"
        return f"Not enough observations to measure the interval ({self.reason})"

    def as_dict(self) -> dict:
        return {"status": self.status, "timeframe": self.timeframe, "candidate": self.candidate,
                "summary": self.summary, "rows_total": self.rows_total, "rows_examined": self.rows_examined,
                "seed": self.seed, "patterns": self.patterns, "blocks": [b.as_dict() for b in self.blocks],
                "method": "sampled successive-row blocks; same-day steps for intraday; no exchange calendar"}


# ---- step measurement -------------------------------------------------------------------------------------------
def _local_dates(keys: list, zone: ZoneInfo) -> list:
    return [k.astimezone(zone).date() if isinstance(k, datetime) else k for k in keys]


def _intraday_steps(keys: list, days: list) -> list[int]:
    """Minutes between successive observations of the same trading date (zero steps ignored, any direction)."""
    out = []
    for a, b, da, db in zip(keys, keys[1:], days, days[1:]):
        if a is None or b is None or da != db:
            continue
        m = int(round(abs((b - a).total_seconds()) / 60))
        if m:
            out.append(m)
    return out


def _day_steps(days: list) -> list[int]:
    out = []
    for a, b in zip(days, days[1:]):
        if a is None or b is None:
            continue
        d = abs((b - a).days)
        if d:
            out.append(d)
    return out


def _month_steps(days: list) -> list[int]:
    out = []
    for a, b in zip(days, days[1:]):
        if a is None or b is None:
            continue
        m = abs((b.year - a.year) * 12 + b.month - a.month)
        if m:
            out.append(m)
    return out


def _is_intraday(keys: list, days: list) -> bool:
    """More than one distinct timestamp on some trading date."""
    seen: dict = {}
    for k, d in zip(keys, days):
        if k is None or d is None:
            continue
        s = seen.setdefault(d, set())
        s.add(k)
        if len(s) > 1:
            return True
    return False


def _label_from_steps(keys: list, days: list, intraday: bool) -> tuple[str | None, list[int], str]:
    """(interval label, steps in the label's unit, unit) for one run of successive observations."""
    if intraday:
        steps = _intraday_steps(keys, days)
        if len(steps) < MIN_STEPS:
            return None, steps, "minute"
        return minutes_label(Counter(steps).most_common(1)[0][0]), steps, "minute"
    steps = _day_steps(days)
    if len(steps) < MIN_STEPS:
        return None, steps, "day"
    mode = Counter(steps).most_common(1)[0][0]
    if mode <= 4:  # trading days: 1 (3 over a weekend, more over holidays)
        return "1D", steps, "day"
    if 5 <= mode <= 10:
        return "1W", [max(1, round(s / 7)) for s in steps], "week"
    m_steps = _month_steps(days)
    if 26 <= mode <= 35 and m_steps:
        return "1M", m_steps, "month"
    if 85 <= mode <= 95 and m_steps:
        return "1Q", [max(1, round(s / 3)) for s in m_steps], "quarter"
    if 360 <= mode <= 370:
        return "1Y", [max(1, round(s / 365)) for s in steps], "year"
    return f"{mode}d", steps, "day"


def _base_unit(label: str) -> int:
    """The interval expressed in the unit its steps are measured in (minutes, or 1 for D/W/M/Q/Y)."""
    if label.endswith("h"):
        return int(label[:-1]) * 60
    if label.endswith("m"):
        return int(label[:-1])
    if label.endswith("d"):
        return int(label[:-1])
    return 1


def _blocks_for(candidate: str | None, intraday: bool, cfg: dict) -> int:
    if candidate is None:
        return cfg["blocks_daily"]
    if intraday:
        m = _base_unit(candidate)
        if m <= 2:
            return cfg["blocks_1_2m"]
        if m <= 15:
            return cfg["blocks_3_15m"]
        if m < 60:
            return cfg["blocks_16_59m"]
        return cfg["blocks_hourly"]
    return cfg["blocks_daily"] if candidate == "1D" else cfg["blocks_weekly"]


def sampling_seed(keys: list, cfg: dict) -> int:
    """Reproducible: the same observations (count, first and last timestamp) and configuration give the same seed."""
    firsts = [k for k in keys[:5] if k is not None]
    lasts = [k for k in keys[-5:] if k is not None]
    payload = json.dumps({"n": len(keys), "first": [str(k) for k in firsts], "last": [str(k) for k in lasts],
                          "cfg": cfg}, sort_keys=True, default=str)
    return int(hashlib.sha256(payload.encode()).hexdigest()[:12], 16)


def block_starts(n: int, blocks: int, block_rows: int, seed: int) -> list[int]:
    """0-based start positions: one random position inside each of `blocks` equal parts of the file."""
    span = n - block_rows
    if span <= 0:
        return [0]
    blocks = max(1, min(blocks, (n // block_rows)))
    rng = random.Random(seed)
    out = []
    for i in range(blocks):
        lo = (span * i) // blocks
        hi = max(lo, (span * (i + 1)) // blocks - 1) if i < blocks - 1 else span
        out.append(rng.randint(lo, hi))
    return sorted(set(out))


def infer_interval(keys: list, *, zone: str | None, config: dict | None = None) -> Inference:
    """`keys`: the parsed timestamps (aware datetimes, UTC) or trading dates, in FILE order (None = unparseable).
    `zone`: the market time zone that defines a trading date for timestamps (no calendar is used)."""
    cfg = {**DEFAULT_SAMPLING, **(config or {})}
    n = len(keys)
    z = ZoneInfo(zone or "UTC")
    seed = sampling_seed(keys, cfg)
    inf = Inference(INSUFFICIENT, None, rows_total=n, seed=seed)
    if n < MIN_STEPS + 1:
        inf.reason = f"{n} observation(s)"
        return inf

    # 1. candidate from the first observations
    init = keys[:max(cfg["initial_rows"], MIN_STEPS + 1)]
    init_days = _local_dates(init, z)
    intraday = _is_intraday(init, init_days)
    candidate, _s, _u = _label_from_steps(init, init_days, intraday)
    inf.candidate = candidate

    # 2. validation blocks
    block_rows = max(cfg["block_rows"], MIN_STEPS + 1)
    if n < 2 * block_rows:
        starts, size = [0], n
    else:
        starts, size = block_starts(n, _blocks_for(candidate, intraday, cfg), block_rows, seed), block_rows
    examined = set()
    for st in starts:
        part = keys[st:st + size]
        days = _local_dates(part, z)
        label, steps, _unit = _label_from_steps(part, days, intraday or _is_intraday(part, days))
        inf.blocks.append(Block(st + 1, len(part), label, len(steps)))
        examined.update(range(st, st + len(part)))
    inf.rows_examined = len(examined) + (0 if not init else len(set(range(len(init))) - examined))

    measured = [b for b in inf.blocks if b.interval is not None]
    if not measured:
        inf.reason = "too few successive observations within a trading date or between dates"
        return inf

    # 3./4. dominant interval and agreement
    counts = Counter(b.interval for b in measured)
    dominant = counts.most_common(1)[0][0]
    unit = _base_unit(dominant)
    for b, st in zip(inf.blocks, starts):
        if b.interval is None:
            continue
        part = keys[st:st + size]
        days = _local_dates(part, z)
        _l, steps, _u = _label_from_steps(part, days, intraday or _is_intraday(part, days))
        multiples = [s for s in steps if s % unit == 0] if unit > 1 else steps
        b.agreeing_share = len(multiples) / len(steps) if steps else 0.0
        # the dominant interval itself must occur in the block: a block of only 5-minute steps is not "1-minute data
        # with missing bars", but a block of mostly 2-minute steps with some 1-minute steps is
        has_base = b.interval == dominant or steps.count(unit) >= max(1, len(steps) // 10)
        b.agrees = b.agreeing_share >= cfg["consistency_share"] and has_base
    inf.patterns = dict(counts)
    if all(b.agrees for b in measured):
        inf.status, inf.timeframe = CONSISTENT, dominant
    else:
        inf.status, inf.timeframe = MIXED_STATUS, MIXED
    return inf


def _as_keys(parsed) -> list:
    return list(parsed.ts_utc) if parsed.is_instant else list(parsed.session_dates)


def infer_from_parsed(parsed, zone: str | None, config: dict | None = None) -> Inference:
    """Convenience wrapper for a ParsedTimes result (datetime_parse.parse_times)."""
    return infer_interval(_as_keys(parsed), zone=zone, config=config)


__all__ = ["CONSISTENT", "DEFAULT_SAMPLING", "INSUFFICIENT", "MIXED_STATUS", "Block", "Inference", "block_starts",
           "infer_from_parsed", "infer_interval", "sampling_seed"]
