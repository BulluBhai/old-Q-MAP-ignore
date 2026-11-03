"""
Affinity engine: scores one set of interactions (in-sample OR out-of-sample).

Formulas are the V2 formulas, unchanged. In plain English:

  Interaction strength = min(1, n / ref_n),  ref_n = max(3 x min_interactions, 20)
  Success rate         = clip((success_rate - 0.5) / 0.5, 0, 1)      [primary window]
  Forward return       = "Directed IR" (PENDING OWNER REVIEW): for each forward window,
                         directed returns = Support returns and the NEGATED Resistance
                         returns; if there are at least 3, clip(mean/std + 0.5, 0, 1);
                         the final component is the average over the windows that qualify.
  Stability            = split the interactions (in time order) into 4 equal chunks of
                         n//4; needs chunks of at least 3; clip(1 - 2 x std(chunk success
                         rates), 0, 1); otherwise 0 in the score.
  Affinity (0-100)     = sum( weight_i / sum(weights) x component_i ) x 100.
Weights are always divided by their sum, so they need not add up to 100.
IS/OOS consistency is NOT part of this score.

Status values
  NO_INTERACTIONS   : nothing was recorded (score is reported as missing, not 0).
  INSUFFICIENT_DATA : fewer than min_interactions (numbers are shown but never ranked).
  OK                : enough interactions.
"""
from __future__ import annotations

import numpy as np

from qlopb.config.settings import SettingsError, weight_problems
from qlopb.validation.statistical_tests import binomial_pvalue_greater, reliability_score

NAN = float("nan")


def _is_nan(x) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x))


def _pct(v):
    return NAN if _is_nan(v) else round(float(v) * 100, 2)


def _primary_sr(records, pk):
    outs = [r[pk] for r in records if r.get(pk) in ("Success", "Failure")]
    if not outs:
        return NAN, 0, 0
    wins = sum(1 for o in outs if o == "Success")
    return wins / len(outs), len(outs), wins


def score_window(records: list, settings) -> dict:
    fwd_w = list(settings.fwd_windows)
    min_int = settings.min_interactions
    weights = settings.weights
    pk = f"outcome_{fwd_w[0]}"

    bad_w = weight_problems(weights)      # checked first, even when there are no records
    if bad_w:
        raise SettingsError("Invalid affinity weights: " + " ".join(bad_w))

    empty_fs = {w: {"mean": NAN, "median": NAN, "std": NAN, "n": 0, "hit_rate": NAN} for w in fwd_w}
    if not records:
        return {"status": "NO_INTERACTIONS", "n": 0, "n_support": 0, "n_resistance": 0,
                "n_outcomes": 0, "overall_sr": NAN, "support_sr": NAN, "resistance_sr": NAN,
                "stability": NAN, "affinity_score": NAN, "reliability": NAN, "p_value": NAN,
                "score_components": {"interaction_strength": NAN, "success_rate": NAN,
                                     "forward_return_directed_ir": NAN, "stability": NAN},
                "fwd_stats": empty_fs}

    n = len(records)
    status = "OK" if n >= min_int else "INSUFFICIENT_DATA"
    sup = [r for r in records if r["side"] == "Support"]
    res = [r for r in records if r["side"] == "Resistance"]
    all_sr, all_n, all_wins = _primary_sr(records, pk)
    sup_sr, sup_n, _ = _primary_sr(sup, pk)
    res_sr, res_n, _ = _primary_sr(res, pk)

    fwd_stats = {}
    for w in fwd_w:
        vals = np.array([r[f"fwd_{w}"] for r in records if not np.isnan(r[f"fwd_{w}"])], dtype=float)
        fwd_stats[w] = {
            "mean": float(vals.mean()) if len(vals) else NAN,
            "median": float(np.median(vals)) if len(vals) else NAN,
            "std": float(vals.std(ddof=1)) if len(vals) > 1 else NAN,   # sample std, as V2/pandas
            "n": int(len(vals)),
            "hit_rate": float((vals > 0).mean()) if len(vals) else NAN}

    # stability: 4 chronological chunks of n//4 interactions
    chunk_n = n // 4
    stability = NAN
    if chunk_n >= 3:
        srs = [_primary_sr(records[k * chunk_n:(k + 1) * chunk_n], pk)[0] for k in range(4)]
        srs = [s for s in srs if not np.isnan(s)]
        if len(srs) >= 2:
            stability = float(max(0.0, min(1.0, 1.0 - 2 * np.std(srs))))

    ref_n = max(min_int * 3, 20)
    s_inter = min(1.0, n / ref_n)
    s_success = float(max(0.0, min(1.0, (all_sr - 0.5) / 0.5))) if all_n > 0 else 0.0

    dir_scores = []
    for w in fwd_w:
        vs = [r[f"fwd_{w}"] for r in sup if not np.isnan(r[f"fwd_{w}"])]
        vr = [r[f"fwd_{w}"] for r in res if not np.isnan(r[f"fwd_{w}"])]
        directed = np.array(vs + [-x for x in vr], dtype=float)
        if len(directed) >= 3:
            m, s = directed.mean(), directed.std()          # population std (ddof=0), as V2
            s = s if s > 0 else 1.0
            dir_scores.append(float(max(0.0, min(1.0, m / s + 0.5))))
    s_fwd = float(np.mean(dir_scores)) if dir_scores else 0.0
    s_stab = stability if not np.isnan(stability) else 0.0

    wsum = sum(weights.values())
    affinity = sum((weights[k] / wsum) * v for k, v in (
        ("interaction_strength", s_inter), ("success_rate", s_success),
        ("forward_return", s_fwd), ("stability", s_stab))) * 100

    return {
        "status": status, "n": n, "n_support": len(sup), "n_resistance": len(res),
        "n_outcomes": all_n,
        "overall_sr": _pct(all_sr), "support_sr": _pct(sup_sr), "resistance_sr": _pct(res_sr),
        "stability": _pct(stability),
        "affinity_score": round(affinity, 2),
        "reliability": (NAN if np.isnan(reliability_score(all_wins, all_n))
                        else round(reliability_score(all_wins, all_n), 2)),
        "p_value": (NAN if np.isnan(binomial_pvalue_greater(all_wins, all_n))
                    else round(binomial_pvalue_greater(all_wins, all_n), 4)),
        "score_components": {
            "interaction_strength": round(s_inter * 100, 2),
            "success_rate": round(s_success * 100, 2),
            "forward_return_directed_ir": round(s_fwd * 100, 2),
            "stability": round(s_stab * 100, 2)},
        "fwd_stats": fwd_stats}
