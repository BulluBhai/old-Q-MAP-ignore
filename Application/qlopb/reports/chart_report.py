"""
Chart output (PNG files). Charts show the same numbers as the tables.

Fixes compared with V2: a missing value is never drawn as 50% (V2 turned a real
0% into 50% with `value or 50`); missing OOS results are labelled, not drawn as bars.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from qlopb.config import settings as cfg
from qlopb.references.moving_average import compute_ma

TYPE_COLORS = {"SMA": "#1f77b4", "EMA": "#2ca02c", "WMA": "#ff7f0e", "HMA": "#9467bd", "RMA": "#d62728"}
DPI = 120


def _num(x):
    return np.nan if x is None else float(x)


def _foot(fig):
    fig.text(0.5, 0.005, "Historical description only - not a prediction or trading signal.",
             ha="center", fontsize=7, color="#555555")


def _save(fig, folder, name, stamp):
    _foot(fig)
    path = Path(folder) / f"{name}_{stamp}.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def make_charts(res, folder, stamp) -> dict:
    paths = {}
    top = res.frozen_top_results()
    s = res.settings
    if top:
        paths["price_with_top_mas"] = _price_chart(res, top, folder, stamp)
        paths["is_vs_oos_success"] = _is_oos_chart(res, top, folder, stamp)
        paths["forward_returns_is"] = _fwd_chart(res, top, folder, stamp)
    ok = [r for r in res.results if r["is_status"] == "OK"]
    if ok:
        paths["score_by_period"] = _score_chart(res, folder, stamp)
        paths["interactions_and_sr"] = _interaction_chart(res, folder, stamp)
    return paths


def _price_chart(res, top, folder, stamp):
    df = res.price_frame
    fig, ax = plt.subplots(figsize=(13, 5.5))
    ax.plot(df.index, df["close"], color="#444444", lw=0.8, label="Close")
    is_end = res.data_info["is_bars"] - 1
    if 0 < is_end < len(df) - 1:
        ax.axvline(df.index[is_end], color="#6a3d9a", ls="--", lw=1.2, label="IS / OOS split")
    close = df["close"].to_numpy()
    for r in top:
        ma = compute_ma(close, r["ma_type"], r["ma_period"])
        ax.plot(df.index, ma, lw=1.1, color=TYPE_COLORS.get(r["ma_type"]),
                alpha=0.85, label=f"#{r['rank']} {r['ma_label']} (IS {r['is_affinity_score']:.1f})")
    ax.set_title(f"{res.label} - price with the frozen Top-{len(top)} (ranked on in-sample data only)")
    ax.legend(fontsize=7, ncol=2, loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b-%y"))
    fig.autofmt_xdate()
    return _save(fig, folder, "chart_price_top_mas", stamp)


def _score_chart(res, folder, stamp):
    fig, ax = plt.subplots(figsize=(13, 4.5))
    by_type = {}
    for r in res.results:
        if r["is_status"] == "OK":
            by_type.setdefault(r["ma_type"], []).append((r["ma_period"], r["is_affinity_score"]))
    for mt, pts in by_type.items():
        pts.sort()
        xs, ys = zip(*pts)
        ax.plot(xs, ys, lw=1.1, color=TYPE_COLORS.get(mt), label=mt)
    for r in res.frozen_top_results():
        ax.scatter([r["ma_period"]], [r["is_affinity_score"]], color="black", s=25, zorder=5)
        ax.annotate(r["ma_label"], (r["ma_period"], r["is_affinity_score"]),
                    textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7)
    ax.set_xlabel("MA period")
    ax.set_ylabel("In-sample affinity score")
    ax.set_title(f"{res.label} - in-sample affinity by period (only candidates with enough data; "
                 "black dots = Top-N)")
    ax.legend(fontsize=8)
    return _save(fig, folder, "chart_score_by_period", stamp)


def _interaction_chart(res, folder, stamp):
    rows = sorted((r for r in res.results if r["is_status"] == "OK"), key=lambda r: r["rank"])[:20]
    labels = [r["ma_label"] for r in rows]
    counts = [r["is_n"] for r in rows]
    srs = [_num(r["is_overall_sr"]) for r in rows]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(max(9, len(rows) * 0.6), 6.5), sharex=True)
    a1.bar(range(len(rows)), counts, color="#7fa6d6")
    a1.axhline(res.settings.min_interactions, color="red", ls="--", lw=0.8,
               label=f"minimum ({res.settings.min_interactions})")
    a1.set_ylabel("IS interactions")
    a1.legend(fontsize=8)
    a1.set_title(f"{res.label} - in-sample interactions and success rate (top 20 by rank)")
    a2.bar(range(len(rows)), [0 if np.isnan(v) else v for v in srs], color="#9bc59d")
    for i, v in enumerate(srs):
        if np.isnan(v):
            a2.text(i, 2, "n/a", ha="center", fontsize=7)
    a2.axhline(50, color="red", ls="--", lw=0.8)
    a2.set_ylim(0, 105)
    a2.set_ylabel("IS success rate %")
    a2.set_xticks(range(len(rows)))
    a2.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    return _save(fig, folder, "chart_interactions_sr", stamp)


def _is_oos_chart(res, top, folder, stamp):
    labels = [r["ma_label"] for r in top]
    x = np.arange(len(top))
    w = 0.38
    is_sr = [_num(r["is_overall_sr"]) for r in top]
    oos_sr = [_num(r["oos_overall_sr"]) for r in top]
    fig, ax = plt.subplots(figsize=(max(8, len(top) * 1.6), 5))
    ax.bar(x - w / 2, [0 if np.isnan(v) else v for v in is_sr], w, color="#1f77b4",
           label="In-sample (basis of rank)")
    for i, r in enumerate(top):
        v = oos_sr[i]
        if np.isnan(v):
            ax.text(x[i] + w / 2, 2, "OOS\nn/a", ha="center", fontsize=7)
            continue
        weak = r.get("oos_n_outcomes", 0) < res.settings.min_oos_outcomes_for_consistency
        ax.bar(x[i] + w / 2, v, w, color="#ff7f0e", alpha=0.45 if weak else 0.9,
               hatch="//" if weak else None, label="Out-of-sample" if i == 0 else None)
        ax.text(x[i] + w / 2, v + 1, f"{v:.0f}%\nn={int(r['oos_n_outcomes'])}", ha="center", fontsize=7)
    ax.axhline(50, color="red", ls="--", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 118)
    ax.set_ylabel("Success rate %")
    ax.set_title(f"{res.label} - IS vs OOS success rate of the frozen Top-{len(top)}\n"
                 f"hatched = fewer than {res.settings.min_oos_outcomes_for_consistency} OOS outcomes "
                 "(insufficient evidence)", fontsize=10)
    h, l = ax.get_legend_handles_labels()
    if h:
        ax.legend(dict(zip(l, h)).values(), dict(zip(l, h)).keys(), fontsize=8, loc="upper right")
    return _save(fig, folder, "chart_is_vs_oos", stamp)


def _fwd_chart(res, top, folder, stamp):
    wins = list(res.settings.fwd_windows)
    fig, axes = plt.subplots(1, len(top), figsize=(3.6 * len(top) + 1, 4.5), sharey=True, squeeze=False)
    for ax, r in zip(axes[0], top):
        fs = r["is_fwd_stats"]
        means = [_num(fs[w]["mean"]) for w in wins]
        stds = [_num(fs[w]["std"]) for w in wins]
        ax.bar(range(len(wins)), [0 if np.isnan(m) else m for m in means],
               color=["#2ca02c" if (not np.isnan(m) and m > 0) else "#d62728" for m in means], alpha=0.8)
        ax.errorbar(range(len(wins)), [0 if np.isnan(m) else m for m in means],
                    yerr=[0 if np.isnan(s) else s for s in stds], fmt="none", color="black",
                    alpha=0.5, capsize=3)
        ax.axhline(0, color="grey", lw=0.8)
        ax.set_xticks(range(len(wins)))
        ax.set_xticklabels([f"{w}b" for w in wins])
        ax.set_title(r["ma_label"], fontsize=9)
    axes[0][0].set_ylabel("Mean IS forward return % (all sides pooled)")
    fig.suptitle(f"{res.label} - raw forward returns after IS interactions (bars +/- 1 std)", y=1.02)
    return _save(fig, folder, "chart_forward_returns", stamp)
