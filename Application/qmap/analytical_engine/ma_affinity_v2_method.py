"""MA Affinity V2 - the calculation (no files, no GUI, no registry). Beta method: the owner gave the direction on
10-Nov-26 (chance test with 200 block shuffles, drift baseline reported only, rescaled strength); the thresholds, block
mechanics, strength rule, grouping, ATR and warm-up details are PROVISIONAL implementation choices, not owner-approved
final methodology.

V2 keeps every V1 definition (QLOPB MA Affinity Scanner V2, Application/qlopb, which is NOT changed and is reused here):
the five MA formulas, zone entry and cooldown, the forward-window rule, Support/Resistance, the four score
components and their weights, in-sample (IS) ranking, freezing the Top-N, and the independent out-of-sample (OOS)
check. V2 ADDS:

  1. Chance test (block shuffle). The IS part of the price history is cut into blocks of `chance_block_bars`
     consecutive bars, the blocks are put in a random order and a new price series is rebuilt from them. Every bar
     keeps its own shape (gap, body, wicks) and the series keeps the same overall move and volatility, but any real
     link between price and a moving average is destroyed. The full IS scan is run on `chance_shuffles` such series
     (fixed `chance_seed`, so a run can be repeated exactly) and the best (#1) score of each is recorded. The real #1
     score is compared with these luck-only #1 scores only when every requested shuffle produced a finite maximum
     score. Any invalid shuffle makes the chance test inconclusive; invalid/no-candidate shuffles never count as low
     scores. Requested, valid and invalid counts are recorded, and no empirical p-value is reported for an incomplete
     null distribution. Each frozen Top-N candidate follows the same completeness rule for its candidate-adjusted
     p-value. The max-statistic comparison allows for the many candidates tested. V1 binomial p-values are retained
     only as exploratory reference diagnostics.
  2. Drift baseline. For each candidate the success rate is shown next to what the stock did anyway over the same
     bars: the share of all bars (from the first bar with an MA value to the last bar whose primary forward window
     fits) after which price was higher (the Support baseline) or lower (the Resistance baseline), weighted by the
     candidate's own Support and Resistance outcomes. `edge` = success rate - baseline (percentage points), with a
     one-sided binomial p-value against the baseline. The baseline is REPORTED ONLY: the affinity score still
     compares the success rate with 50%, as in V1 (owner direction 10-Nov-26).
  3. Fairer interaction strength (`strength_rule` "relative", the default). V1 gives full strength at 30 interactions
     (max(3 x min interactions, 20)) for every period, but long MAs produce fewer interactions, so they were marked down
     for their length. V2 uses as the reference the SMALLER of the V1 number and the median interaction count of the
     same MA type at nearby periods (within +/-20%, at least +/-2 periods) on the same data:
        strength = min(1, interactions / reference)
     A candidate with fewer interactions than is usual for its period still scores lower; a long MA is no longer
     marked down only for being long. The reference is never stricter than V1. Out-of-sample, the in-sample reference
     is scaled by the number of usable out-of-sample bars over in-sample bars. `strength_rule` "v1" keeps the V1 rule.
  4. Neighbour grouping (`group_pct`, default 10). Neighbouring periods of one MA type are nearly the same line, so the
     Top-N list is built from distinct findings: going down the in-sample ranking, a candidate of the same type within
     `group_pct`% of a group leader's period (at least 1 period) joins that group instead of taking a Top-N place.
     The frozen Top-N are the group leaders; each lists its members. 0 = no grouping (the V1 Top-N).
  5. Optional volatility zone (`zone_mode` "atr"): the zone is the MA +/- `atr_multiple` x ATR(`atr_period`) (Wilder's
     average true range up to and including the bar) instead of +/- `proximity_pct`% of the MA, so the zone means the
     same thing for quiet and volatile instruments. "percent" (the default) is the V1 zone, calculated by V1's code.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from qlopb.analysis.affinity_engine import score_window
from qlopb.analysis.interaction_engine import build_interaction_records, detect_interaction_episodes
from qlopb.config import settings as qcfg
from qlopb.config.settings import MAResearchSettings
from qlopb.core.research_engine import ResearchError, ResearchResult, RunCancelled, horizon_label
from qlopb.core.validation import check_data_for_settings, validate_ohlc_frame
from qlopb.references.moving_average import compute_ma
from qlopb.validation.is_oos import compute_split, consistency, rank_candidates
from qlopb.validation.robustness import near_duplicate_pairs, neighbour_summary

METHOD_NAME = "MA Affinity V2"
CHANCE_ALPHA = 0.05
STANDS_OUT, NOT_DISTINGUISHABLE, NOT_RUN = ("STANDS OUT FROM CHANCE", "NOT DISTINGUISHABLE FROM CHANCE",
                                            "CHANCE TEST NOT RUN")
NAN = float("nan")

LIMITATIONS_V2 = (
    "A historical rank is a description of the past, not evidence that a moving average will work in future.",
    "The chance test compares the real #1 score with the #1 scores found on block-shuffled copies of the same "
    "in-sample prices. It allows for the many candidates tested, but it is still a test on one history: a result that "
    "stands out from chance on one instrument should be confirmed on others before it is relied on.",
    "The chance result is conditional on the shuffle model: blocks of bars keep each bar's shape, the overall move and "
    "short-term patterns within a block, but not longer trends or volatility regimes. Standing out from this "
    "simulated chance is not proof of a profitable or persistent trading edge.",
    "With N shuffles the smallest possible chance p-value is 1/(N+1) (0.0050 with 200), so chance p-values are "
    "approximate at that resolution; use more shuffles (for example 1000) for a finer value.",
    "The chance threshold (0.05), the 15-bar blocks, the relative strength rule (+/-20% median), Group % (10), the ATR "
    "option (14 bars, 1.0 x) and MA warm-up are PROVISIONAL beta defaults, documented and configurable; they are not "
    "owner-approved final methodology.",
    "The legacy binomial baseline p-values are EXPLORATORY, not definitive inferential evidence. Their usual "
    "interpretation assumes independent observations; market observations can be dependent and forward windows "
    "overlap, so nominal p-values may be overconfident. The calculations are retained unchanged; treat these "
    "values as descriptive diagnostics, not proof of significance.",
    "The block-shuffle chance test is inconclusive if any requested shuffle has no finite maximum score. Requested, "
    "valid and invalid counts are recorded, and overall and candidate-adjusted p-values are suppressed.",
    "Success is scored against 50% (as in V1). The drift baseline (what price did anyway over the same bars) is "
    "reported alongside; a success rate close to its baseline mostly reflects the stock's own trend.",
    "Neighbouring MA periods are almost identical. V2 groups them (Group %), so each Top-N place is a distinct "
    "finding; MA types are not grouped with each other, so an EMA and an SMA of similar period can both appear.",
    "Forward windows longer than the primary window overlap each other, so those statistics are not independent "
    "observations.",
    "Forward Return (Directed IR) methodology is PENDING OWNER REVIEW. The V1 formula is kept unchanged.",
    "The official affinity weight scheme is still undecided. The four V1 weights are kept in their original "
    "proportions and normalised.",
    "Out-of-sample samples can be small. Where the OOS sample is below the minimum, consistency is reported as "
    "insufficient evidence.",
)


@dataclass
class MAAffinityV2Settings(MAResearchSettings):
    """V1 settings (unchanged meaning and defaults) plus the V2 chance-test options."""

    chance_shuffles: int = 200  # 0 = do not run the chance test (the report then says it was not run)
    chance_block_bars: int = 15
    chance_seed: int = 1
    strength_rule: str = "relative"  # relative | v1
    group_pct: float = 10.0  # 0 = no grouping
    zone_mode: str = "percent"  # percent | atr
    atr_period: int = 14
    atr_multiple: float = 1.0
    ma_warmup: str = "earlier"  # earlier = MAs use the bars before the Start date (counted from it only) | none = V1

    def problems(self) -> list:
        out = super().problems()

        def is_int(v):
            return isinstance(v, int) and not isinstance(v, bool)

        if not is_int(self.chance_shuffles) or not 0 <= self.chance_shuffles <= 5000:
            out.append("Chance shuffles must be a whole number from 0 to 5000 (0 = chance test not run).")
        if not is_int(self.chance_block_bars) or not 2 <= self.chance_block_bars <= 500:
            out.append("Chance block bars must be a whole number from 2 to 500.")
        if not is_int(self.chance_seed) or self.chance_seed < 0:
            out.append("Chance seed must be a whole number of 0 or more.")
        if self.strength_rule not in ("relative", "v1"):
            out.append("Strength rule must be 'relative' or 'v1'.")
        try:
            if not 0 <= float(self.group_pct) <= 100:
                out.append("Group % must be from 0 to 100 (0 = no grouping).")
        except (TypeError, ValueError):
            out.append("Group % must be a number.")
        if self.zone_mode not in ("percent", "atr"):
            out.append("Zone mode must be 'percent' or 'atr'.")
        if not is_int(self.atr_period) or not 1 <= self.atr_period <= 500:
            out.append("ATR period must be a whole number from 1 to 500.")
        try:
            if not 0 < float(self.atr_multiple) <= 20:
                out.append("ATR multiple must be above 0 and at most 20.")
        except (TypeError, ValueError):
            out.append("ATR multiple must be a number.")
        if self.ma_warmup not in ("earlier", "none"):
            out.append("MA warm-up must be 'earlier' or 'none'.")
        if self.timeframe != "as_loaded":
            out.append("MA Affinity V2 always runs on the dataset's own timeframe (as_loaded).")
        return out


@dataclass
class V2Result(ResearchResult):
    """QLOPB's ResearchResult (so QLOPB's chart writer can draw it) plus the V2 chance test."""

    chance: dict = field(default_factory=dict)


# ---- helpers ------------------------------------------------------------------------------------------------------
def _fast_records(events, ma_vals, close, fwd_end_bar, fwd_windows) -> list:
    """Only the fields `score_window` reads (side, outcome_<w>, fwd_<w>), built exactly as QLOPB's
    build_interaction_records builds them. Used for the shuffled series, where dates and labels are not needed."""
    n = len(close)
    recs = []
    for i in events:
        ma = float(ma_vals[i])
        cl = float(close[i])
        prev = float(close[i - 1]) if i > 0 else cl
        side = "Support" if prev > ma else "Resistance" if prev < ma else "Neutral"
        r = {"side": side}
        for w in fwd_windows:
            fi = i + w
            if fi <= fwd_end_bar and fi < n:
                fr = (float(close[fi]) - cl) / cl * 100
                r[f"fwd_{w}"] = fr
                if side == "Support":
                    r[f"outcome_{w}"] = "Success" if fr > 0 else "Failure"
                elif side == "Resistance":
                    r[f"outcome_{w}"] = "Success" if fr < 0 else "Failure"
                else:
                    r[f"outcome_{w}"] = "Neutral"
            else:
                r[f"fwd_{w}"] = np.nan
                r[f"outcome_{w}"] = "NoData"
        recs.append(r)
    return recs


def affinity_only(records: list, s, ref_n: float | None = None) -> tuple:
    """(status, affinity score rounded to 2 decimals) exactly as QLOPB's `score_window` computes them, without the
    descriptive statistics, reliability and p-values that a shuffled series does not need (about 4x faster).
    A test checks that both give the same status and score. `ref_n` replaces V1's interaction-strength reference
    (max(3 x min interactions, 20)) when given."""
    n = len(records)
    if n == 0:
        return "NO_INTERACTIONS", NAN
    status = "OK" if n >= s.min_interactions else "INSUFFICIENT_DATA"
    pk = f"outcome_{s.fwd_windows[0]}"

    def sr(recs):
        outs = [r[pk] for r in recs if r.get(pk) in ("Success", "Failure")]
        return (sum(1 for x in outs if x == "Success") / len(outs), len(outs)) if outs else (NAN, 0)

    all_sr, all_n = sr(records)
    chunk_n = n // 4
    stability = NAN
    if chunk_n >= 3:
        srs = [sr(records[k * chunk_n:(k + 1) * chunk_n])[0] for k in range(4)]
        srs = [x for x in srs if not np.isnan(x)]
        if len(srs) >= 2:
            stability = float(max(0.0, min(1.0, 1.0 - 2 * np.std(srs))))
    s_inter = strength(n, s, ref_n)
    s_success = float(max(0.0, min(1.0, (all_sr - 0.5) / 0.5))) if all_n > 0 else 0.0
    dir_scores = []
    for w in s.fwd_windows:
        vs = [r[f"fwd_{w}"] for r in records if r["side"] == "Support" and not np.isnan(r[f"fwd_{w}"])]
        vr = [r[f"fwd_{w}"] for r in records if r["side"] == "Resistance" and not np.isnan(r[f"fwd_{w}"])]
        directed = np.array(vs + [-x for x in vr], dtype=float)
        if len(directed) >= 3:
            m, sd = directed.mean(), directed.std()
            sd = sd if sd > 0 else 1.0
            dir_scores.append(float(max(0.0, min(1.0, m / sd + 0.5))))
    s_fwd = float(np.mean(dir_scores)) if dir_scores else 0.0
    s_stab = stability if not np.isnan(stability) else 0.0
    weights = s.weights
    wsum = sum(weights.values())
    affinity = sum((weights[k] / wsum) * v for k, v in (
        ("interaction_strength", s_inter), ("success_rate", s_success),
        ("forward_return", s_fwd), ("stability", s_stab))) * 100
    return status, round(affinity, 2)


def v1_reference(s) -> int:
    return max(s.min_interactions * 3, 20)


def strength(n: int, s, ref_n: float | None) -> float:
    ref = v1_reference(s) if ref_n is None else max(float(ref_n), 1.0)
    return min(1.0, n / ref)


def strength_references(counts: dict, s) -> dict:
    """(type, period) -> interaction-strength reference. "v1": V1's fixed number. "relative": the smaller of V1's
    number and the median interaction count of the same MA type at periods within +/-20% (at least +/-2)."""
    v1ref = v1_reference(s)
    if s.strength_rule == "v1":
        return {k: float(v1ref) for k in counts}
    by_type: dict = {}
    for (mt, p), n in counts.items():
        by_type.setdefault(mt, []).append((p, n))
    refs = {}
    for mt, items in by_type.items():
        periods = np.array([p for p, _ in items])
        ns = np.array([n for _, n in items], dtype=float)
        for p, _ in items:
            width = max(2.0, 0.2 * p)
            near = ns[np.abs(periods - p) <= width]
            refs[(mt, p)] = float(min(v1ref, np.median(near)))
    return refs


def score_v2(records: list, s, ref_n: float) -> dict:
    """QLOPB's score_window (all descriptive numbers unchanged) with the V2 interaction strength and the affinity
    score recalculated from it. With ref_n = V1's reference the result equals score_window exactly."""
    sc = score_window(records, s)
    if sc["status"] == "NO_INTERACTIONS":
        return sc
    status, score = affinity_only(records, s, ref_n)
    sc["affinity_score"] = score
    sc["score_components"] = {**sc["score_components"],
                              "interaction_strength": round(strength(len(records), s, ref_n) * 100, 2)}
    sc["strength_reference"] = round(float(ref_n), 2)
    return sc


def atr_wilder(high, low, close, period: int) -> np.ndarray:
    """Wilder's average true range; causal (bar i uses bars up to i); NaN until `period` true ranges exist."""
    high, low, close = (np.asarray(x, dtype=np.float64) for x in (high, low, close))
    n = len(close)
    tr = high - low
    if n > 1:
        tr[1:] = np.maximum(tr[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    out = np.full(n, np.nan)
    if n >= period:
        out[period - 1] = tr[:period].mean()
        for i in range(period, n):
            out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def detect_entries(high, low, ma_vals, half_width, start_bar, end_bar, fwd_end_bar, primary_window, cooldown_bars,
                   initial_in_zone=False, last_event_bar=-999999):
    """QLOPB's detect_interaction_episodes with the zone given as MA +/- half_width (an array, e.g. k x ATR) instead of
    +/- a percentage. Same entry, cooldown, eligibility and IS->OOS carry-over rules. A bar without an MA or a
    half-width value is never in the zone."""
    n = len(ma_vals)
    scan_s, scan_e = max(start_bar, 0), min(end_bar, n - 1)
    if scan_s > scan_e:
        return [], initial_in_zone, last_event_bar
    ma_s, hw_s = ma_vals[scan_s: scan_e + 1], half_width[scan_s: scan_e + 1]
    valid = ~np.isnan(ma_s) & ~np.isnan(hw_s)
    zone_up = np.where(valid, ma_s + hw_s, np.inf)
    zone_lo = np.where(valid, ma_s - hw_s, -np.inf)
    in_zone = valid & (low[scan_s: scan_e + 1] <= zone_up) & (high[scan_s: scan_e + 1] >= zone_lo)
    entries = in_zone & ~np.concatenate([[initial_in_zone], in_zone[:-1]])
    record_end = min(scan_e, fwd_end_bar - primary_window)
    events, last_ev = [], last_event_bar
    for local_i in np.where(entries)[0]:
        i = int(local_i) + scan_s
        if i > record_end:
            continue
        if (i - last_ev) >= cooldown_bars:
            events.append(i)
            last_ev = i
    return events, bool(in_zone[-1]), last_ev


class _Zone:
    """Interaction detection for the chosen zone: V1's own function for "percent", detect_entries for "atr"."""

    def __init__(self, s, high, low, close):
        self.s, self.high, self.low = s, high, low
        self.atr_hw = (atr_wilder(high, low, close, s.atr_period) * float(s.atr_multiple)
                       if s.zone_mode == "atr" else None)

    def detect(self, ma, start, end, fwd_end, initial_in_zone, last_event_bar):
        s = self.s
        if self.atr_hw is None:
            return detect_interaction_episodes(self.high, self.low, ma, start, end, fwd_end, s.primary_window,
                                               s.proximity_pct, s.cooldown_bars, initial_in_zone=initial_in_zone,
                                               last_event_bar=last_event_bar)
        return detect_entries(self.high, self.low, ma, self.atr_hw, start, end, fwd_end, s.primary_window,
                              s.cooldown_bars, initial_in_zone=initial_in_zone, last_event_bar=last_event_bar)


def group_neighbours(results: list, s) -> list:
    """Distinct findings from the in-sample ranking. Returns the groups in rank order, each a list of results (leader
    first). Only ranked (status OK) candidates are grouped; group_pct 0 makes every candidate its own group."""
    ranked = sorted((r for r in results if r.get("rank")), key=lambda r: r["rank"])
    groups = []
    for r in ranked:
        home = None
        if float(s.group_pct) > 0:
            for g in groups:
                lead = g[0]
                width = max(1, math.ceil(lead["ma_period"] * float(s.group_pct) / 100))
                if lead["ma_type"] == r["ma_type"] and abs(lead["ma_period"] - r["ma_period"]) <= width:
                    home = g
                    break
        if home is None:
            groups.append([r])
        else:
            home.append(r)
    return groups


class _Baseline:
    """Share of bars after which price was higher / lower `pw` bars later, over any bar range (cumulative sums)."""

    def __init__(self, close: np.ndarray, pw: int):
        n = len(close)
        up = np.zeros(n, dtype=np.int64)
        down = np.zeros(n, dtype=np.int64)
        if n > pw:
            fwd = close[pw:] - close[:-pw]
            up[: n - pw] = fwd > 0
            down[: n - pw] = fwd < 0
        self.cs_up = np.concatenate([[0], np.cumsum(up)])
        self.cs_down = np.concatenate([[0], np.cumsum(down)])

    def rates(self, first: int, last: int) -> tuple:
        if last < first:
            return NAN, NAN, 0
        k = last - first + 1
        return ((self.cs_up[last + 1] - self.cs_up[first]) / k, (self.cs_down[last + 1] - self.cs_down[first]) / k, k)


def _baseline_fields(prefix: str, recs: list, ma, baseline: _Baseline, start: int, record_end: int, pk: str) -> dict:
    """Drift baseline for one candidate in one period (IS or OOS). Reporting only - the score does not use it."""
    from scipy import stats as sci_stats

    valid = np.flatnonzero(~np.isnan(ma[start: record_end + 1])) if record_end >= start else np.array([], int)
    out = {f"{prefix}_baseline_sr": NAN, f"{prefix}_edge_vs_baseline": NAN, f"{prefix}_p_vs_baseline": NAN,
           f"{prefix}_baseline_bars": 0}
    if len(valid) == 0:
        return out
    p_up, p_down, k = baseline.rates(start + int(valid[0]), record_end)
    out[f"{prefix}_baseline_bars"] = int(k)
    sup = [r for r in recs if r["side"] == "Support" and r.get(pk) in ("Success", "Failure")]
    res = [r for r in recs if r["side"] == "Resistance" and r.get(pk) in ("Success", "Failure")]
    n_out = len(sup) + len(res)
    if n_out == 0 or k == 0:
        return out
    expected = (len(sup) * p_up + len(res) * p_down) / n_out
    wins = sum(1 for r in sup + res if r[pk] == "Success")
    out[f"{prefix}_baseline_sr"] = round(expected * 100, 2)
    out[f"{prefix}_edge_vs_baseline"] = round((wins / n_out - expected) * 100, 2)
    if n_out >= 5 and 0 < expected < 1:
        out[f"{prefix}_p_vs_baseline"] = round(float(sci_stats.binomtest(wins, n_out, p=expected,
                                                                         alternative="greater").pvalue), 4)
    return out


def block_shuffle_ohlc(o, h, l, c, block: int, rng: np.random.Generator) -> tuple:
    """A price series with the same bars in a different order of `block`-bar blocks.

    Each bar is described relative to the previous close (gap = open / previous close, body = close / open, upper and
    lower wick ratios), so every rebuilt bar is internally consistent (low <= open, close <= high). The first bar is
    kept; the product of all bar moves, so the overall move from the first to the last close, is unchanged. The block
    grid starts at a random offset so that block edges differ between shuffles."""
    o, h, l, c = (np.asarray(x, dtype=np.float64) for x in (o, h, l, c))
    n = len(c)
    if n < 3:
        return o.copy(), h.copy(), l.copy(), c.copy()
    gap = o[1:] / c[:-1]
    body = c[1:] / o[1:]
    upper = h[1:] / np.maximum(o[1:], c[1:])
    lower = l[1:] / np.minimum(o[1:], c[1:])
    m = n - 1
    offset = int(rng.integers(0, block))
    edges = sorted({0, m, *range(offset, m, block)})
    blocks = [np.arange(a, b) for a, b in zip(edges[:-1], edges[1:]) if b > a]
    order = rng.permutation(len(blocks))
    idx = np.concatenate([blocks[k] for k in order])
    g, b, up, dn = gap[idx], body[idx], upper[idx], lower[idx]
    c2 = np.empty(n)
    o2 = np.empty(n)
    c2[0], o2[0] = c[0], o[0]
    c2[1:] = c[0] * np.cumprod(g * b)
    o2[1:] = c2[:-1] * g
    h2 = np.empty(n)
    l2 = np.empty(n)
    h2[0], l2[0] = h[0], l[0]
    h2[1:] = np.maximum(o2[1:], c2[1:]) * up
    l2[1:] = np.minimum(o2[1:], c2[1:]) * dn
    return o2, h2, l2, c2


def _is_top_score(o, h, l, c, s: MAAffinityV2Settings, candidates: list, is_end: int, start: int = 0) -> tuple:
    """Run the IS scan on one (shuffled) series exactly as on the real one (same zone, same strength rule, same first
    bar `start` after the MA warm-up bars); return (#1 IS affinity among ranked candidates, its label)."""
    best, best_label = -math.inf, ""
    fwd = list(s.fwd_windows)
    zone = _Zone(s, h, l, c)
    recs = {}
    for mt, period in candidates:
        ma = compute_ma(c, mt, period)
        events, _, _ = zone.detect(ma, start, is_end, is_end, False, start - (period + 1))
        recs[(mt, period)] = _fast_records(events, ma, c, is_end, fwd)
    refs = strength_references({k: len(v) for k, v in recs.items()}, s)
    for (mt, period), r in recs.items():
        status, score = affinity_only(r, s, refs[(mt, period)])
        if status == "OK" and score > best:
            best, best_label = score, f"{mt}-{period}"
    return (best if best > -math.inf else NAN), best_label


def _valid_null_scores(null_tops: list) -> np.ndarray:
    """Return finite shuffle maxima; NaN, infinity and non-numeric values are invalid, never low scores."""
    valid = []
    for value in null_tops:
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(score):
            valid.append(score)
    return np.asarray(valid, dtype=float)


def chance_summary(real_top: float, null_tops: list, shuffles: int, block: int, seed: int) -> dict:
    """Compare real and shuffled maxima; an incomplete null distribution is inconclusive."""
    requested = int(shuffles)
    attempted = min(len(null_tops), requested)
    sample = list(null_tops)[:requested]
    arr = _valid_null_scores(sample)
    valid = len(arr)
    invalid = attempted - valid
    unattempted = requested - attempted
    base = {"shuffles": requested, "requested_shuffles": requested, "attempted_shuffles": attempted,
            "valid_shuffles": valid, "invalid_shuffles": invalid, "unattempted_shuffles": unattempted,
            "block_bars": block, "seed": seed, "null_top_scores": list(null_tops)}
    stats = {"null_mean": round(float(arr.mean()), 2) if len(arr) else NAN,
             "null_p95": round(float(np.percentile(arr, 95)), 2) if len(arr) else NAN,
             "null_max": round(float(arr.max()), 2) if len(arr) else NAN}
    if requested == 0:
        return {**base, **stats, "real_top_score": real_top, "p_value": NAN, "percentile": NAN,
                "verdict": NOT_RUN, "status": "not_run", "test_run": False}
    real_is_valid = real_top is not None and math.isfinite(float(real_top))
    if not real_is_valid and attempted == 0:
        return {**base, **stats, "real_top_score": real_top, "p_value": NAN, "percentile": NAN,
                "verdict": "NO RANKED CANDIDATE - CHANCE TEST SKIPPED", "status": "no_candidate",
                "test_run": False}
    if invalid or unattempted:
        return {**base, **stats, "real_top_score": real_top, "p_value": NAN, "percentile": NAN,
                "verdict": "INCONCLUSIVE - INCOMPLETE NULL DISTRIBUTION", "status": "inconclusive",
                "test_run": attempted > 0}
    if not real_is_valid:
        return {**base, **stats, "real_top_score": real_top, "p_value": NAN, "percentile": NAN,
                "verdict": "NO RANKED CANDIDATE - nothing to test", "status": "no_candidate"}
    at_least = int((arr >= float(real_top)).sum())
    p = (1 + at_least) / (requested + 1)
    return {**base, **stats, "real_top_score": real_top, "p_value": round(p, 4),
            "percentile": round((requested - at_least) / requested * 100, 1),
            "verdict": STANDS_OUT if p <= CHANCE_ALPHA else NOT_DISTINGUISHABLE, "status": "complete",
            "test_run": True}


def chance_p_for(score: float, null_tops: list, shuffles: int) -> float:
    """Candidate-adjusted p-value; defined only for a complete finite null distribution."""
    if shuffles == 0 or score is None or not math.isfinite(float(score)):
        return NAN
    arr = _valid_null_scores(null_tops)
    if len(arr) != shuffles:
        return NAN
    return round((1 + int((arr >= float(score)).sum())) / (shuffles + 1), 4)


def _stamp(ts) -> str:
    ts = pd.Timestamp(ts)
    return ts.strftime(qcfg.DATE_FMT if (ts.hour == 0 and ts.minute == 0) else qcfg.DATETIME_FMT)


# ---- the run ------------------------------------------------------------------------------------------------------
def run_ma_affinity_v2(df: pd.DataFrame, s: MAAffinityV2Settings, *, label: str = "instrument", log=None,
                       progress=None, cancel=None, quality=None, analysis_start: int = 0) -> V2Result:
    """progress(done, total, text); log(text); cancel() -> True to stop (raises RunCancelled).

    `analysis_start` (MA warm-up, 10-Nov-26): the first `analysis_start` rows of `df` are history BEFORE the chosen
    analysis period. They are used only to calculate the moving averages (and the regime MA and ATR), so a long MA does
    not restart at the chosen start date; no interaction, outcome, baseline bar or split is counted in them. The
    in-sample / out-of-sample split is made on the analysis period alone, exactly as if it were the whole frame.
    0 (the default) = no earlier history: the V1 behaviour."""
    t0 = time.time()
    say = log or (lambda m: None)
    tick = progress or (lambda d, t, m: None)
    s.check()
    problems = validate_ohlc_frame(df)
    if problems:
        raise ResearchError("The price table is not usable:\n- " + "\n- ".join(problems))
    a = int(analysis_start)
    if not 0 <= a < len(df):
        raise ResearchError(f"The analysis period starts at row {a}, outside the {len(df)} rows given.")
    errors, warns = check_data_for_settings(df.iloc[a:], s)  # the analysis period must be long enough on its own
    if errors:
        raise ResearchError("\n".join(errors))
    warnings = list(warns)

    o = df["open"].to_numpy(dtype=np.float64)
    close = df["close"].to_numpy(dtype=np.float64)
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)
    index = df.index
    n = len(df)
    is_end, oos_start = (a + k for k in compute_split(n - a, s.is_pct))  # split of the analysis period only
    pw = s.primary_window
    pk = f"outcome_{pw}"
    fwd = list(s.fwd_windows)
    reg = s.regime_ma
    regime_ma = (pd.Series(close).rolling(reg, min_periods=reg).mean().to_numpy() if n > reg else np.full(n, np.nan))
    baseline = _Baseline(close, pw)
    zone = _Zone(s, high, low, close)

    candidates = [(mt, p) for mt in s.ma_types for p in range(s.ma_start, s.ma_end + 1)]
    n_c = len(candidates)
    n_oos_est = n_c if s.oos_scope == "all" else min(s.top_n, n_c)
    total = n_c + s.chance_shuffles * n_c + n_oos_est
    done = 0
    data_info = {
        "n_bars": n - a, "first": _stamp(index[a]), "last": _stamp(index[-1]),
        "is_bars": is_end - a + 1, "oos_bars": n - oos_start,
        "is_first": _stamp(index[a]), "is_last": _stamp(index[is_end]),
        "warmup_bars": a, "warmup_first": _stamp(index[0]) if a else "",
        "oos_first": _stamp(index[oos_start]) if oos_start < n else "",
        "oos_last": _stamp(index[-1]) if oos_start < n else "",
        "frequency": quality.inferred_frequency if quality is not None else "as loaded",
        "timeframe_setting": s.timeframe}
    say(f"Data: {n} bars, {data_info['first']} to {data_info['last']}. IS {data_info['is_bars']} bars "
        f"({data_info['is_first']} to {data_info['is_last']}), OOS {data_info['oos_bars']} bars.")
    say(f"Candidates: {n_c} ({', '.join(s.ma_types)}, periods {s.ma_start}-{s.ma_end}). Primary forward window {pw} "
        f"bars. Chance test: {s.chance_shuffles} shuffles of {s.chance_block_bars}-bar blocks (seed {s.chance_seed}). "
        f"Zone: " + (f"{s.proximity_pct}% of the MA" if s.zone_mode == "percent" else
                     f"{s.atr_multiple} x ATR({s.atr_period})") +
        f". Strength rule: {s.strength_rule}. Grouping: " + (f"{s.group_pct}%" if float(s.group_pct) > 0 else "off") + ".")

    def stop_if_asked():
        if cancel and cancel():
            raise RunCancelled("Run cancelled by user.")

    # ---- Phase 1: IS scoring of every candidate ------------------------------------------------------------------
    say("Phase 1/4: in-sample scoring of all candidates...")
    results, is_state, all_records, scanned = [], {}, [], {}
    for mt, period in candidates:
        stop_if_asked()
        tick(done, total, f"In-sample {mt}-{period}")
        ma = compute_ma(close, mt, period)
        events, final_iz, final_lev = zone.detect(ma, a, is_end, is_end, False, a - (period + 1))
        recs = build_interaction_records(events, ma, mt, period, is_end, close, high, low, index, regime_ma, fwd)
        scanned[(mt, period)] = (ma, recs)
        is_state[(mt, period)] = (final_iz, final_lev)
        done += 1
    refs = strength_references({k: len(v[1]) for k, v in scanned.items()}, s)
    for mt, period in candidates:
        ma, recs = scanned.pop((mt, period))
        sc = score_v2(recs, s, refs[(mt, period)])
        results.append({
            "ma_type": mt, "ma_period": period, "ma_label": f"{mt}-{period}", "horizon": horizon_label(period),
            "rank": None, "rank_tie": False,
            **{f"is_{key}": v for key, v in sc.items()},
            "is_strength_reference": round(refs[(mt, period)], 2),
            **_baseline_fields("is", recs, ma, baseline, a, min(is_end, is_end - pw), pk),
            "chance_p": NAN, "finding": None, "group_leader": "", "group_size": np.nan, "group_members": "",
            "oos_status": "NOT_EVALUATED", "oos_n": np.nan, "oos_overall_sr": np.nan, "oos_n_outcomes": np.nan,
            "oos_affinity_score": np.nan, "is_oos_sr_diff": np.nan, "is_oos_consistency_raw": np.nan,
            "is_oos_consistency_score": np.nan, "is_oos_consistency_status": "NOT_EVALUATED",
            "oos_baseline_sr": np.nan, "oos_edge_vs_baseline": np.nan, "oos_p_vs_baseline": np.nan,
            "oos_baseline_bars": 0})
        all_records.extend({"period_type": "IS", **r} for r in recs)

    # ---- Phase 2: rank on IS only and freeze the Top-N -----------------------------------------------------------
    say("Phase 2/4: ranking on in-sample scores only and freezing the Top-N...")
    rank_candidates(results)
    groups = group_neighbours(results, s)
    for k, g in enumerate(groups, 1):
        for r in g:
            r["group_leader"] = g[0]["ma_label"]
        g[0].update({"finding": k, "group_size": len(g),
                     "group_members": ", ".join(r["ma_label"] for r in g)})
    frozen = [(g[0]["ma_type"], g[0]["ma_period"]) for g in groups[: s.top_n]]
    n_ok = sum(1 for r in results if r["is_status"] == "OK")
    say(f"{n_ok} of {n_c} candidates have enough in-sample interactions (min {s.min_interactions}); "
        f"{len(groups)} distinct finding(s) after grouping. Frozen Top-{len(frozen)}: "
        + ", ".join(f"{t}-{p}" for t, p in frozen))
    if n_ok == 0:
        warnings.append("No candidate reached the minimum number of in-sample interactions, so nothing was ranked. "
                        "This means 'insufficient data', not 'poor results'.")
    elif len(frozen) < s.top_n:
        warnings.append(f"Only {len(frozen)} distinct findings qualified for the Top-{s.top_n} list.")
    lookup = {(r["ma_type"], r["ma_period"]): r for r in results}
    ties = sorted({lookup[k]["rank"] for k in frozen if lookup[k].get("rank_tie")})
    if ties:
        warnings.append("Equal IS scores among the Top-N leaders (ranks " + ", ".join(map(str, ties))
                        + "): their order is arbitrary (candidate order).")
    dup_pairs = near_duplicate_pairs(frozen)
    if dup_pairs:
        warnings.append("Near-duplicate neighbours in the Top-N (periods within 3): "
                        + "; ".join(f"{a}/{b}" for a, b in dup_pairs) + ".")

    # ---- Phase 3: chance test on block-shuffled IS prices -----------------------------------------------------------
    null_tops, null_labels = [], []
    if s.chance_shuffles > 0 and frozen:
        say(f"Phase 3/4: chance test - {s.chance_shuffles} block-shuffled copies of the in-sample prices...")
        rng = np.random.default_rng(s.chance_seed)
        # the in-sample bars are shuffled; with MA warm-up, the warm-up bars stay as they are in front of them (the
        # last warm-up bar anchors the shuffled series), so the MAs warm up exactly as in the real scan
        anchor = max(a - 1, 0)
        seg = slice(anchor, is_end + 1)
        for k in range(s.chance_shuffles):
            stop_if_asked()
            tick(done, total, f"Chance test: shuffle {k + 1} of {s.chance_shuffles}")
            so, sh, sl, sc_ = block_shuffle_ohlc(o[seg], high[seg], low[seg], close[seg], s.chance_block_bars, rng)
            if anchor:
                so, sh, sl, sc_ = (np.concatenate([x[:anchor], y]) for x, y in ((o, so), (high, sh), (low, sl),
                                                                               (close, sc_)))
            top, top_label = _is_top_score(so, sh, sl, sc_, s, candidates, is_end, a)
            null_tops.append(top)
            null_labels.append(top_label)
            if not math.isfinite(float(top)):
                say(f"Chance test: shuffle {k + 1} of {s.chance_shuffles} produced no valid maximum score.")
            done += n_c
            if (k + 1) % 20 == 0 or k + 1 == s.chance_shuffles:
                say(f"  chance test: {k + 1} of {s.chance_shuffles} shuffles done")
    elif s.chance_shuffles > 0:
        say(f"Chance test NOT RUN: {s.chance_shuffles} shuffles requested, but no candidate qualified for ranking. "
            "No shuffle was attempted.")
    else:
        say("Phase 3/4: chance test not run (Chance shuffles = 0).")
    real_top = lookup[frozen[0]]["is_affinity_score"] if frozen else NAN
    chance = chance_summary(real_top, null_tops, s.chance_shuffles, s.chance_block_bars, s.chance_seed)
    chance["null_top_labels"] = null_labels
    for key in frozen:
        lookup[key]["chance_p"] = chance_p_for(lookup[key]["is_affinity_score"], null_tops, s.chance_shuffles)
        lookup[key]["chance_status"] = chance["status"]
        lookup[key]["chance_verdict"] = (
            chance["verdict"] if chance["status"] == "inconclusive"
            else STANDS_OUT if lookup[key]["chance_p"] <= CHANCE_ALPHA
            else NOT_DISTINGUISHABLE if math.isfinite(lookup[key]["chance_p"]) else NOT_RUN
        )
    for row in results:
        row.setdefault("chance_p", NAN)
        row.setdefault("chance_status", chance["status"])
        row.setdefault("chance_verdict", chance["verdict"] if chance["status"] in ("no_candidate", "inconclusive")
                       else NOT_RUN if chance["status"] == "not_run" else "NOT_EVALUATED - NOT IN FROZEN TOP-N")
    if chance["verdict"] in (STANDS_OUT, NOT_DISTINGUISHABLE):
        say(f"Chance test: real #1 score {real_top:.2f}; luck-only #1 scores average {chance['null_mean']:.2f}, 95th "
            f"percentile {chance['null_p95']:.2f}; chance p-value {chance['p_value']:.4f} -> {chance['verdict']}.")
    if chance["verdict"] == NOT_DISTINGUISHABLE:
        warnings.append(f"Chance test: the #1 score ({real_top:.2f}) is NOT distinguishable from chance (chance "
                        f"p-value {chance['p_value']:.4f}; block-shuffled prices reached a #1 score at least this high "
                        f"in {int(round(chance['p_value'] * (s.chance_shuffles + 1))) - 1} of {s.chance_shuffles} "
                        "shuffles). Treat the ranking as unproven.")
    elif chance.get("status") == "no_candidate":
        warnings.append(f"Chance test NOT RUN: no candidate qualified. {chance['requested_shuffles']} shuffle(s) "
                        "were requested, but 0 were attempted; 0 were invalid.")
    elif chance.get("status") == "inconclusive":
        warnings.append(f"Chance test INCONCLUSIVE: {chance['invalid_shuffles']} of "
                        f"{chance['attempted_shuffles']} attempted shuffles were invalid and "
                        f"{chance['unattempted_shuffles']} requested shuffles were not completed; "
                        "no empirical p-value or positive chance verdict is available.")
    elif chance["verdict"] == NOT_RUN:
        warnings.append("The chance test was not run (Chance shuffles = 0), so the scores cannot be judged against "
                        "luck.")

    # ---- Phase 4: independent OOS -------------------------------------------------------------------------------
    to_eval = set(frozen) if s.oos_scope == "top_n" else {(r["ma_type"], r["ma_period"]) for r in results}
    say(f"Phase 4/4: out-of-sample validation of {len(to_eval)} candidate(s) (scope: {s.oos_scope}). OOS never "
        "changes ranks.")
    todo = [c for c in candidates if c in to_eval]
    is_usable, oos_usable = max(is_end - pw - a + 1, 1), max((n - 1 - pw) - oos_start + 1, 0)
    for mt, period in todo:
        stop_if_asked()
        tick(done, total, f"Out-of-sample {mt}-{period}")
        ma = compute_ma(close, mt, period)
        iz, lev = is_state[(mt, period)]
        events, _, _ = zone.detect(ma, oos_start, n - 1, n - 1, iz, lev)
        recs = build_interaction_records(events, ma, mt, period, n - 1, close, high, low, index, regime_ma, fwd)
        oos_ref = (refs[(mt, period)] if s.strength_rule == "v1"
                   else max(1.0, refs[(mt, period)] * oos_usable / is_usable))
        sc = score_v2(recs, s, oos_ref)
        r = lookup[(mt, period)]
        for key, v in sc.items():
            r[f"oos_{key}"] = v
        r.update(_baseline_fields("oos", recs, ma, baseline, oos_start, n - 1 - pw, pk))
        cons = consistency(r["is_overall_sr"], r["oos_overall_sr"], sc["n_outcomes"],
                           s.min_oos_outcomes_for_consistency)
        r["is_oos_sr_diff"], r["is_oos_consistency_raw"] = cons["diff"], cons["raw"]
        r["is_oos_consistency_score"], r["is_oos_consistency_status"] = cons["value"], cons["status"]
        all_records.extend({"period_type": "OOS", **x} for x in recs)
        done += 1
    tick(total, total, "Finished")

    for key in frozen:
        r = lookup[key]
        r.update({f"nbr_{k}": v for k, v in neighbour_summary(results, r["ma_type"], r["ma_period"]).items()})
    inter = pd.DataFrame(all_records) if all_records else pd.DataFrame()
    secs = time.time() - t0
    say(f"Research finished in {secs:.1f}s. {len(inter)} interactions recorded.")
    return V2Result(label=label, settings=s, results=results, interactions=inter, data_info=data_info,
                    frozen_top=frozen, warnings=warnings, notes=[], near_duplicates=dup_pairs, quality=quality,
                    seconds=secs, price_frame=df, chance=chance)
