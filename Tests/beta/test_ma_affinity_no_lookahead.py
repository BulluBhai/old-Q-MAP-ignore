"""Beta leakage tests (T6, 09-Nov-26): later data can never change earlier results.

(a) Changing every bar AFTER the in-sample period leaves every in-sample number, every in-sample interaction, the
    ranking and the frozen Top-N exactly unchanged (OOS can never feed back into selection).
(b) Each moving average is causal: changing bars after bar t leaves every MA value up to t unchanged (all five types).
(c) Through Q-MAP: a run with an End date gives exactly the same result tables as a run on a dataset that simply
    ends at that date, so bars after the End date are never used."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "qlopb"))
import _qlopb_helpers as H  # noqa: E402

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited  # noqa: E402
from qlopb.config.settings import MAResearchSettings  # noqa: E402
from qlopb.core.research_engine import run_ma_affinity  # noqa: E402
from qlopb.references.moving_average import compute_ma  # noqa: E402
from qlopb.validation.is_oos import compute_split  # noqa: E402
from qmap.analytical_engine import MA_AFFINITY, run_analysis  # noqa: E402
from qmap.catalog import list_datasets  # noqa: E402
from qmap.core.runs import run_context  # noqa: E402
from qmap.data_engine import discovery as D  # noqa: E402

SETTINGS = dict(ma_types=("SMA", "EMA", "WMA", "HMA", "RMA"), ma_start=5, ma_end=35, fwd_windows=(5, 10),
                min_interactions=5, regime_ma=50, top_n=5, oos_scope="all")


def _perturb_after(df, first_bar, seed=99):
    out = df.copy()
    rng = np.random.default_rng(seed)
    k = len(out) - first_bar
    factor = 1 + rng.normal(0, 0.05, k)
    for c in ("open", "high", "low", "close"):
        out.iloc[first_bar:, out.columns.get_loc(c)] = out[c].to_numpy()[first_bar:] * factor
    out.iloc[first_bar:, out.columns.get_loc("high")] = out[["open", "high", "low", "close"]].iloc[first_bar:].max(axis=1)
    out.iloc[first_bar:, out.columns.get_loc("low")] = out[["open", "high", "low", "close"]].iloc[first_bar:].min(axis=1)
    return out


def _is_view(res):
    rows = [{k: v for k, v in r.items() if k.startswith("is_") and not k.startswith("is_oos")} |
            {"key": (r["ma_type"], r["ma_period"]), "rank": r["rank"]} for r in res.results]
    inter = res.interactions
    is_inter = inter[inter["period_type"] == "IS"].reset_index(drop=True)
    return rows, is_inter, list(res.frozen_top)


def test_out_of_sample_bars_cannot_change_in_sample_results_or_the_frozen_top_n():
    df = H.synthetic_ohlc(n=600, seed=5, drift=0.0005)
    s = MAResearchSettings(**SETTINGS)
    is_end, oos_start = compute_split(len(df), s.is_pct)
    base = run_ma_affinity(df, s)
    changed = run_ma_affinity(_perturb_after(df, oos_start), s)
    a, b = _is_view(base), _is_view(changed)
    assert not df["close"].iloc[oos_start:].equals(_perturb_after(df, oos_start)["close"].iloc[oos_start:])
    assert repr(a[0]) == repr(b[0]), "in-sample scores and ranks must not depend on out-of-sample bars"
    pd.testing.assert_frame_equal(a[1], b[1])
    assert a[2] == b[2]
    # and the out-of-sample part DID change, so the test is not vacuous
    assert not base.interactions[base.interactions["period_type"] == "OOS"].reset_index(drop=True).equals(
        changed.interactions[changed.interactions["period_type"] == "OOS"].reset_index(drop=True))


def test_in_sample_forward_windows_never_reach_into_the_out_of_sample_period():
    df = H.synthetic_ohlc(n=600, seed=8)
    s = MAResearchSettings(**SETTINGS)
    is_end, _ = compute_split(len(df), s.is_pct)
    res = run_ma_affinity(df, s)
    is_rows = res.interactions[res.interactions["period_type"] == "IS"]
    assert len(is_rows) > 100
    assert (is_rows["bar_idx"] + max(s.fwd_windows)).where(is_rows[f"fwd_{max(s.fwd_windows)}"].notna(), 0).max() <= is_end
    assert (is_rows["bar_idx"] + s.primary_window).max() <= is_end


@pytest.mark.parametrize("ma_type", ["SMA", "EMA", "WMA", "HMA", "RMA"])
def test_every_moving_average_is_causal(ma_type):
    close = H.synthetic_ohlc(n=300, seed=4)["close"].to_numpy()
    for t in (40, 150, 260):
        later = close.copy()
        later[t + 1:] *= 1.3
        a, b = compute_ma(close, ma_type, 21), compute_ma(later, ma_type, 21)
        np.testing.assert_array_equal(a[:t + 1], b[:t + 1])
        assert not np.allclose(a[t + 1:], b[t + 1:], equal_nan=True)


def test_an_end_date_uses_no_bar_after_it(settings, db, tmp_path):
    folder = tmp_path / "files"
    folder.mkdir()
    days = weekdays(700, date(2021, 1, 4))
    rows = [[d.isoformat()] + r for d, r in zip(days, ohlcv(700, seed=12, base=300.0))]
    cut = 520
    write_delimited(folder / "NSE_FULL.csv", HEADER, rows)
    write_delimited(folder / "NSE_CUT.csv", HEADER, rows[:cut])
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE")
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        D.scan_source(run, src.source_id)
    ids = {d.instrument.split(":")[-1]: d.dataset_id for d in list_datasets(db)}
    params = {"ma_end": "40", "fwd_windows": "5,10"}
    full = run_analysis(settings, db, MA_AFFINITY, [ids["FULL"]], dict(params, date_to=days[cut - 1].isoformat()))
    cut_run = run_analysis(settings, db, MA_AFFINITY, [ids["CUT"]], params)
    assert full.ok and cut_run.ok, (full.message, cut_run.message)
    for prefix in MA_AFFINITY.result_tables:
        a = next(full.run_dir.glob(prefix + "*.csv")).read_bytes()
        b = next(cut_run.run_dir.glob(prefix + "*.csv")).read_bytes()
        assert a == b, prefix
