"""Independent reference implementation of MA Affinity (beta numerical validation, T4). Not a test file.

Written for the beta validation of 09-Nov-26 from the WRITTEN method definitions (the docstrings of QLOPB's
interaction, affinity and IS/OOS modules, and the Analytical Workbench user guide), not by reusing any QLOPB function.
Deliberately different technique:
  * pure Python lists and explicit loops, no numpy, pandas or scipy anywhere in the calculations;
  * moving averages by direct summation over each window (no rolling, convolution or recursion shortcuts except the
    EMA/RMA recursions, which ARE the definition);
  * the binomial p-value by exact summation with math.comb.
Any disagreement with the engine is a finding to investigate, never a reason to loosen the comparison.

Definitions (V2, unchanged; "the method" below):
  MAs     SMA mean of last n closes; WMA weights 1..n (newest n); EMA alpha 2/(n+1) and RMA alpha 1/n, both seeded with
          the SMA of the first n bars at bar n-1; HMA = WMA(2*WMA(n_half) - WMA(n), n_sqrt) with n_half = max(2, n//2)
          and n_sqrt = max(2, floor(sqrt(n))); a WMA window containing a missing value is missing.
  Zone    low <= MA*(1+p) and high >= MA*(1-p), MA present.
  Entry   in zone now and not in zone on the previous bar (state carried across the IS/OOS split).
  Record  entry bar i with i + primary_window <= period end, and i - last recorded >= cooldown.
          The first IS "last recorded" is -(period+1).
  Side    previous close > MA: Support; < MA: Resistance; equal: Neutral (bar 0 uses its own close).
  Forward (close[i+w] - close[i]) / close[i] * 100 when i+w <= period end, else missing.
  Outcome Support: success if fwd > 0; Resistance: success if fwd < 0; zero is failure; Neutral: no outcome.
  Scores  strength min(1, n/max(3*min_int, 20)); success clip((SR-0.5)/0.5, 0, 1) on the primary window (0 when
          no outcomes); directed IR per window = clip(mean/std_pop + 0.5, 0, 1) over Support returns and negated
          Resistance returns, when there are at least 3 (std 0 -> 1); the average over qualifying windows (0 if none);
          stability: 4 chunks of n//4 (n//4 >= 3), success rates of chunks with outcomes, needs 2+,
          clip(1 - 2*std_pop, 0, 1) (0 in the score when missing); affinity = 100 * sum(w_k/sum(w) * component_k).
  Status  no records: NO_INTERACTIONS; n < min_interactions: INSUFFICIENT_DATA; else OK.
  Split   is_end = int(n_bars * is_pct / 100) - 1; rank OK candidates by IS affinity (2 decimals), stable order;
          freeze the first top_n; OOS for the frozen ones only (scope top_n); consistency = max(0, 1 - 2*diff/100)*100,
          shown when OOS outcomes >= min_oos.
  Regime  SMA(regime_ma) of closes (only when n_bars > regime_ma): close > it Bullish, else Bearish; missing Unknown.
  Slope   with MA 5 bars earlier: (MA - MA_5) / (MA * 5) * 100 > 0.02 Rising, < -0.02 Declining, else Flat.
  Reliability (n outcomes >= 5): Wilson 95% lower bound (z = 1.96), clip((wlo-0.5)/0.5, 0, 1)*100.
  p-value (n >= 5): P(X >= wins), X ~ Binomial(n, 0.5).
"""

from __future__ import annotations

import math

MISSING = None


# ---- moving averages ---------------------------------------------------------------------------------------------
def sma(x, n):
    return [sum(x[i - n + 1:i + 1]) / n if i >= n - 1 else MISSING for i in range(len(x))]


def wma(x, n):
    out = []
    den = n * (n + 1) / 2
    for i in range(len(x)):
        if i < n - 1:
            out.append(MISSING)
            continue
        window = x[i - n + 1:i + 1]
        if any(v is MISSING for v in window):
            out.append(MISSING)
        else:
            out.append(sum((k + 1) * v for k, v in enumerate(window)) / den)
    return out


def _recursive(x, n, alpha):
    out = [MISSING] * len(x)
    if len(x) >= n:
        out[n - 1] = sum(x[:n]) / n
        for i in range(n, len(x)):
            out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def ema(x, n):
    return _recursive(x, n, 2 / (n + 1))


def rma(x, n):
    return _recursive(x, n, 1 / n)


def hma(x, n):
    half, root = max(2, n // 2), max(2, int(math.floor(math.sqrt(n))))
    a, b = wma(x, half), wma(x, n)
    raw = [MISSING if (p is MISSING or q is MISSING) else 2 * p - q for p, q in zip(a, b)]
    return wma(raw, root)


MA = {"SMA": sma, "EMA": ema, "WMA": wma, "HMA": hma, "RMA": rma}


# ---- interactions ------------------------------------------------------------------------------------------------
def events(high, low, ma, start, end, period_end, pw, prox_pct, cooldown, in_zone_before, last_event):
    p = prox_pct / 100
    found = []
    prev = in_zone_before
    last = last_event
    for i in range(start, end + 1):
        now = ma[i] is not MISSING and low[i] <= ma[i] * (1 + p) and high[i] >= ma[i] * (1 - p)
        if now and not prev and i <= period_end - pw and i - last >= cooldown:
            found.append(i)
            last = i
        prev = now
    return found, prev, last


def record(i, ma, close, period_end, windows, regime):
    prev_close = close[i - 1] if i > 0 else close[i]
    side = "Support" if prev_close > ma[i] else "Resistance" if prev_close < ma[i] else "Neutral"
    slope = "Unknown"
    if i >= 5 and ma[i - 5] is not MISSING:
        sp = (ma[i] - ma[i - 5]) / (ma[i] * 5) * 100
        slope = "Rising" if sp > 0.02 else "Declining" if sp < -0.02 else "Flat"
    reg = "Unknown" if regime[i] is MISSING else ("Bullish" if close[i] > regime[i] else "Bearish")
    rec = {"bar_idx": i, "side": side, "ma_slope": slope, "regime": reg, "ma_value": ma[i]}
    for w in windows:
        j = i + w
        if j <= period_end and j < len(close):
            r = (close[j] - close[i]) / close[i] * 100
            rec[f"fwd_{w}"] = r
            rec[f"outcome_{w}"] = ("Neutral" if side == "Neutral" else
                                  "Success" if (r > 0 if side == "Support" else r < 0) else "Failure")
        else:
            rec[f"fwd_{w}"] = MISSING
            rec[f"outcome_{w}"] = "NoData"
    return rec


# ---- statistics --------------------------------------------------------------------------------------------------
def mean(v):
    return sum(v) / len(v)


def std_pop(v):
    m = mean(v)
    return math.sqrt(sum((a - m) ** 2 for a in v) / len(v))


def std_sample(v):
    m = mean(v)
    return math.sqrt(sum((a - m) ** 2 for a in v) / (len(v) - 1))


def median(v):
    s = sorted(v)
    k = len(s) // 2
    return s[k] if len(s) % 2 else (s[k - 1] + s[k]) / 2


def clip01(x):
    return max(0.0, min(1.0, x))


def success_rate(recs, key):
    outs = [r[key] for r in recs if r[key] in ("Success", "Failure")]
    if not outs:
        return MISSING, 0, 0
    wins = outs.count("Success")
    return wins / len(outs), len(outs), wins


def wilson_lower(wins, n, z=1.96):
    p = wins / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def p_value(wins, n):
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def score(recs, windows, min_int, weights):
    if not recs:
        return {"status": "NO_INTERACTIONS", "n": 0}
    key = f"outcome_{windows[0]}"
    n = len(recs)
    sup = [r for r in recs if r["side"] == "Support"]
    res = [r for r in recs if r["side"] == "Resistance"]
    sr, n_out, wins = success_rate(recs, key)
    out = {"status": "OK" if n >= min_int else "INSUFFICIENT_DATA", "n": n, "n_support": len(sup),
           "n_resistance": len(res), "n_outcomes": n_out, "sr": sr, "wins": wins,
           "support_sr": success_rate(sup, key)[0], "resistance_sr": success_rate(res, key)[0]}
    fwd = {}
    for w in windows:
        vals = [r[f"fwd_{w}"] for r in recs if r[f"fwd_{w}"] is not MISSING]
        fwd[w] = {"n": len(vals), "mean": mean(vals) if vals else MISSING, "median": median(vals) if vals else MISSING,
                  "std": std_sample(vals) if len(vals) > 1 else MISSING,
                  "hit_rate": sum(1 for v in vals if v > 0) / len(vals) if vals else MISSING}
    out["fwd"] = fwd
    chunk = n // 4
    stability = MISSING
    if chunk >= 3:
        rates = [success_rate(recs[k * chunk:(k + 1) * chunk], key)[0] for k in range(4)]
        rates = [x for x in rates if x is not MISSING]
        if len(rates) >= 2:
            stability = clip01(1 - 2 * std_pop(rates))
    out["stability"] = stability
    s_int = min(1.0, n / max(3 * min_int, 20))
    s_sr = clip01((sr - 0.5) / 0.5) if n_out else 0.0
    irs = []
    for w in windows:
        d = [r[f"fwd_{w}"] for r in sup if r[f"fwd_{w}"] is not MISSING] + \
            [-r[f"fwd_{w}"] for r in res if r[f"fwd_{w}"] is not MISSING]
        if len(d) >= 3:
            s = std_pop(d)
            irs.append(clip01(mean(d) / (s if s > 0 else 1.0) + 0.5))
    s_fwd = mean(irs) if irs else 0.0
    s_stab = stability if stability is not MISSING else 0.0
    total = sum(weights.values())
    comps = {"interaction_strength": s_int, "success_rate": s_sr, "forward_return": s_fwd, "stability": s_stab}
    out["components"] = comps
    out["affinity"] = 100 * sum(weights[k] / total * v for k, v in comps.items())
    out["reliability"] = clip01((wilson_lower(wins, n_out) - 0.5) / 0.5) * 100 if n_out >= 5 else MISSING
    out["p_value"] = p_value(wins, n_out) if n_out >= 5 else MISSING
    return out


# ---- the whole method --------------------------------------------------------------------------------------------
def run(close, high, low, *, ma_types, ma_start, ma_end, proximity_pct, cooldown_bars, fwd_windows, min_interactions,
        is_pct, regime_ma, top_n, weights, min_oos):
    """Returns {"candidates": {(type, period): {...}}, "frozen": [...], "interactions": [records with period_type]}."""
    close, high, low = [float(v) for v in close], [float(v) for v in high], [float(v) for v in low]
    n = len(close)
    is_end = int(n * is_pct / 100) - 1
    pw = fwd_windows[0]
    regime = sma(close, regime_ma) if n > regime_ma else [MISSING] * n
    cands, inter, state = {}, [], {}
    for mt in ma_types:
        for p in range(ma_start, ma_end + 1):
            ma = MA[mt](close, p)
            ev, iz, last = events(high, low, ma, 0, is_end, is_end, pw, proximity_pct, cooldown_bars, False, -(p + 1))
            recs = [record(i, ma, close, is_end, fwd_windows, regime) for i in ev]
            state[(mt, p)] = (ma, iz, last)
            cands[(mt, p)] = {"is": score(recs, fwd_windows, min_interactions, weights), "oos": None}
            inter += [dict(r, period_type="IS", ma_type=mt, ma_period=p) for r in recs]
    ok = [k for k in cands if cands[k]["is"]["status"] == "OK"]
    ok.sort(key=lambda k: -round(cands[k]["is"]["affinity"], 2))  # stable: equal scores keep candidate order
    for rank, k in enumerate(ok, 1):
        cands[k]["rank"] = rank
    frozen = ok[:top_n]
    for k in frozen:
        ma, iz, last = state[k]
        ev, _, _ = events(high, low, ma, is_end + 1, n - 1, n - 1, pw, proximity_pct, cooldown_bars, iz, last)
        recs = [record(i, ma, close, n - 1, fwd_windows, regime) for i in ev]
        o = score(recs, fwd_windows, min_interactions, weights)
        cands[k]["oos"] = o
        i_sr, o_sr = cands[k]["is"].get("sr"), o.get("sr")
        if i_sr is MISSING or o_sr is MISSING:
            cands[k]["consistency"] = ("NOT_AVAILABLE", MISSING)
        else:
            diff = round(abs(round(i_sr * 100, 2) - round(o_sr * 100, 2)), 2)
            raw = round(max(0.0, 1 - 2 * diff / 100) * 100, 2)
            cands[k]["consistency"] = ("OK", raw) if o["n_outcomes"] >= min_oos else ("INSUFFICIENT_OOS_EVIDENCE", raw)
        inter += [dict(r, period_type="OOS", ma_type=k[0], ma_period=k[1]) for r in recs]
    return {"candidates": cands, "frozen": frozen, "interactions": inter, "is_end": is_end}
