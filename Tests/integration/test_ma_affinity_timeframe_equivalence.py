"""Owner condition 3 (03-Nov-26): before MA Affinity may use Q-MAP's registered weekly/monthly datasets, show numerically
that they are suitable for the existing MA Affinity methodology, i.e. that they equal what QLOPB's own aggregation
(`qlopb.core.timeframe_engine.resample_ohlc`, which the Workbench never uses) builds from the same daily data.

Compared for each daily dataset and each of 1W/1M/1Q (Q-MAP derive) vs W/M/Q (QLOPB):
  bar dates, open/high/low/close, and the FULL MA Affinity result (every candidate row and every interaction).
Data: the real daily file shipped with QLOPB (Nifty500 Healthcare, 228 bars) and a 16-year synthetic daily series built
to contain the edge periods: start and end inside a week, month and quarter; ISO week 53 (2020); weeks across year
ends; a leap day; random holidays; a week with no session; a week with one session; Saturday and Sunday special
sessions; and sessions with empty volume.

Known, explained differences that do NOT reach MA Affinity (it reads only open, high, low, close and the bar date):
  - volume: Q-MAP leaves a period's volume empty if any session's volume is empty; QLOPB sums the others;
  - edge periods: Q-MAP flags `period_may_be_incomplete` only when the data start/end inside the period; QLOPB marks the
    first and last period `boundary_period` always. Neither flag is used by the calculation.
"""

from __future__ import annotations

import csv
import random
import shutil
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qlopb.config.settings import MAResearchSettings
from qlopb.core.research_engine import ResearchError, run_ma_affinity
from qlopb.core.timeframe_engine import resample_ohlc
from qmap.catalog import list_datasets, read_dataset
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap.data_engine.derive import derive_timeframe

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "qlopb_data"
PAIRS = {"1W": "W", "1M": "M", "1Q": "Q"}


def _synthetic_daily(path: Path) -> None:
    rnd = random.Random(5)
    px = 1000.0
    special = {date(2020, 2, 1), date(2025, 2, 1), date(2023, 11, 12), date(2024, 11, 2)}  # Saturday/Sunday sessions
    no_session = {date(2016, 3, 7) + timedelta(days=i) for i in range(7)}
    one_session = {date(2018, 8, 6) + timedelta(days=i) for i in range(4)}  # only Friday 10-Aug-18 is kept
    rows, d = [], date(2009, 12, 30)  # starts on a Wednesday, inside a week, month and quarter
    while d <= date(2025, 11, 19):  # ends on a Wednesday, inside a week, month and quarter
        trade = ((d.weekday() < 5 and rnd.random() > 0.04) or d in special) and d not in no_session | one_session
        if trade:
            o = px
            c = max(1.0, o * (1 + rnd.gauss(0.0003, 0.012)))
            h = max(o, c) * (1 + abs(rnd.gauss(0, 0.004)))
            lo = min(o, c) * (1 - abs(rnd.gauss(0, 0.004)))
            vol = "" if rnd.random() < 0.01 else rnd.randint(1000, 90000)
            rows.append([d.isoformat(), round(o, 2), round(h, 2), round(lo, 2), round(c, 2), vol])
            px = c
        d += timedelta(days=1)
    assert date(2024, 2, 29).isoformat() in {r[0] for r in rows}
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        w.writerows(rows)


@pytest.fixture(scope="module")
def registered(tmp_path_factory):
    from qmap.core.config import load_settings
    from qmap.storage.db import open_database

    base = tmp_path_factory.mktemp("tf_equivalence")
    roots = {k: base / k for k in ("code", "data", "output", "src")}
    for p in roots.values():
        p.mkdir()
    shutil.copy2(FIXTURES / "Nifty500 Healthcare.txt", roots["src"] / "Nifty500 Healthcare.txt")
    _synthetic_daily(roots["src"] / "NSE_SYNTHEDGE, 1D.csv")
    settings = load_settings(None, env={"QMAP_DATA_ROOT": str(roots["data"]), "QMAP_OUTPUT_ROOT": str(roots["output"])},
                             code_root=roots["code"])
    db = open_database(settings.db_path)
    src = D.add_folder_source(settings, db, roots["src"], market_timezone="Asia/Kolkata")
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        result = D.scan_source(run, src.source_id)
    assert [f[3] for f in result.files] == ["imported", "imported"], result.files
    daily = {d.instrument: d for d in list_datasets(db) if d.timeframe == "1D"}
    derived = {}
    for inst, d in daily.items():
        for tf in PAIRS:
            with run_context(settings, db, "DRV", area="Data_Management") as run:
                derive_timeframe(run, d.dataset_id, tf)
            derived[(inst, tf)] = next(x for x in list_datasets(db) if x.instrument == inst and x.timeframe == tf)
    yield settings, db, daily, derived
    db.close()


def _frame(settings, db, dataset_id) -> pd.DataFrame:
    t = read_dataset(settings, db, dataset_id).to_pandas()
    return pd.DataFrame({k: pd.to_numeric(t[k], errors="coerce").astype(float).values
                         for k in ("open", "high", "low", "close", "volume")},
                        index=pd.DatetimeIndex(pd.to_datetime(t["session_date"]), name="datetime"))


CASES = [(inst, tf) for inst in ("NSE:NIFTY500_HEALTHCARE", "NSE:SYNTHEDGE") for tf in PAIRS]


@pytest.mark.parametrize("instrument,timeframe", CASES)
def test_registered_period_bars_equal_qlopb_aggregation(registered, instrument, timeframe):
    settings, db, daily, derived = registered
    q = _frame(settings, db, derived[(instrument, timeframe)].dataset_id)
    ql, _ = resample_ohlc(_frame(settings, db, daily[instrument].dataset_id), PAIRS[timeframe])
    assert q.index.equals(ql.index), "bar dates differ"
    cols = ["open", "high", "low", "close"]
    assert np.array_equal(q[cols].to_numpy(), ql[cols].to_numpy()), "OHLC differ"


@pytest.mark.parametrize("instrument,timeframe", CASES)
def test_ma_affinity_results_identical_on_both(registered, instrument, timeframe):
    settings, db, daily, derived = registered
    q = _frame(settings, db, derived[(instrument, timeframe)].dataset_id)
    fd = _frame(settings, db, daily[instrument].dataset_id)
    s = MAResearchSettings(ma_start=5, ma_end=40 if len(q) < 300 else 60, min_interactions=5, fwd_windows=(3, 5, 10),
                           regime_ma=20)
    s_ql = MAResearchSettings(**{**s.__dict__, "timeframe": PAIRS[timeframe]})
    is_bars = int(len(q) * s.is_pct / 100)
    if is_bars < s.ma_start + s.primary_window + 1:  # too short (real file: 12 monthly, 5 quarterly bars)
        with pytest.raises(ResearchError) as ea:
            run_ma_affinity(q, s, label="x")
        with pytest.raises(ResearchError) as eb:
            run_ma_affinity(fd, s_ql, label="x")
        assert str(ea.value) == str(eb.value)  # both routes refuse with the same reason
        return
    a = run_ma_affinity(q, s, label="x")
    b = run_ma_affinity(fd, s_ql, label="x")
    assert a.frozen_top == b.frozen_top
    pd.testing.assert_frame_equal(pd.DataFrame(a.results), pd.DataFrame(b.results))
    pd.testing.assert_frame_equal(a.interactions.reset_index(drop=True), b.interactions.reset_index(drop=True))
    assert len(a.interactions) > 0


def test_the_edge_periods_are_present_and_only_volume_and_edge_flags_differ(registered):
    settings, db, daily, derived = registered
    w = _frame(settings, db, derived[("NSE:SYNTHEDGE", "1W")].dataset_id)
    ql, _ = resample_ohlc(_frame(settings, db, daily["NSE:SYNTHEDGE"].dataset_id), "W")
    dates = set(w.index.date)
    assert date(2016, 3, 7) not in dates and not any(date(2016, 3, 7) <= d <= date(2016, 3, 13) for d in dates)
    assert date(2018, 8, 10) in dates  # the one-session week is one bar dated by its only session
    assert any(tuple(d.isocalendar())[:2] == (2020, 53) for d in dates)  # ISO week 53 (28-Dec-20..03-Jan-21)
    assert date(2023, 11, 12) in dates and date(2024, 11, 2) in dates  # Sunday/Saturday sessions close their week
    differing = ~np.isclose(w["volume"].to_numpy(), ql["volume"].to_numpy(), equal_nan=True)
    assert differing.any() and np.isnan(w["volume"].to_numpy()[differing]).all()  # Q-MAP: empty; QLOPB: partial sum
