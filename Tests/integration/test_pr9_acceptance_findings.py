"""Regression tests for the PR #9 Windows/IDLE acceptance findings (02-Nov-26), F-01 ... F-04 and OW-25.

All data here is SYNTHETIC; only names and layouts mirror the owner's files (5PAISA_30min.csv, AKZOINDIA.parquet,
ICICIBANK.txt, OLAELEC.xlsx, VERANDA_1min.csv, CRYPTO_RIVERUSD, 180.csv, UJJIVAN.txt). Results with the owner's
actual files are in docs/acceptance_testing/Q-MAP_PR9_Acceptance_Findings_02_Nov_26_210000.md.

F-01  plain file names ("ICICIBANK.txt") gave no symbol suggestion; "_30min"/"_1min" tokens were not recognised
F-02  CRYPTO_ files got the folder's default exchange (NSE); a timeframe answer could relabel measured bars (180-minute
      bars registered as "4h"). 3h support itself is in test_pr9_timeframe_3h.py (owner approval pending, DQ-7)
F-03  headerless files with separate date and time columns were rejected
F-04  a rules-version change must not re-create datasets for unchanged files, nor discard recorded answers
OW-25 a dataset loaded through Data Management is compared when a later file is scanned; both are kept
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pyarrow.parquet as pq
import pytest

from fixtures.builders import HEADER, intraday_utc, ohlcv, weekdays, write_delimited, write_parquet
from qmap.catalog import get_dataset, list_datasets
from qmap.core.runs import run_context
from qmap.data_engine import auto_interpret as A
from qmap.data_engine import discovery as D
from qmap.data_engine.ingest import ingest_file

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    f.mkdir()
    return f


def _source(settings, db, folder, **kw):
    kw.setdefault("market_timezone", "Asia/Kolkata")
    kw.setdefault("default_exchange", "NSE")
    return D.add_folder_source(settings, db, folder, **kw)


def scan(settings, db, source):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, source.source_id)


def result_for(res, rel):
    return next(f for f in res.files if f[0] == rel)


def daily(path, n=12, seed=1):
    return write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(n), ohlcv(n, seed))])


def intraday_ist(path, n, step, seed=1, header=("date", "open", "high", "low", "close", "volume")):
    times = intraday_utc(n, step_minutes=step)
    return write_delimited(path, list(header), [[t.astimezone(IST).isoformat()] + r
                                                for t, r in zip(times, ohlcv(n, seed))])


def _load(run, path, interp):
    o = interp.overrides
    return ingest_file(run, path, interp.profile, exchange=o.get("exchange"), symbol=o.get("symbol"),
                       timeframe=o.get("timeframe"))


def _stored(settings, db, dataset_id):
    rel = db.one("SELECT relative_path FROM datasets WHERE dataset_id = ?", (dataset_id,))[0]
    return pq.read_table(settings.data_path(rel))


# =====================================================================================================================
# F-01: file-name interpretation
# =====================================================================================================================

@pytest.mark.parametrize("stem, expected", [
    ("5PAISA_30min", "30m"), ("VERANDA_1min", "1m"), ("ABC_5min", "5m"), ("ABC_15min", "15m"),
    ("NSE_BANKNIFTY, 15", "15m"), ("ABC, 60", "1h"), ("ABC_4h", "4h"), ("ABC, 1D", "1D"),
    ("ICICIBANK", None), ("OLAELEC", None), ("ABC_7min", None), ("ABC_minutes", None),
])
def test_timeframe_tokens_in_file_names(stem, expected):
    assert A.timeframe_from_name(stem) == expected


@pytest.mark.parametrize("stem, symbol", [
    ("ICICIBANK", "ICICIBANK"), ("OLAELEC", "OLAELEC"), ("AKZOINDIA", "AKZOINDIA"), ("5PAISA_30min", "5PAISA"),
    ("VERANDA_1min", "VERANDA"), ("M&M, 1D", "M&M"), ("BAJAJ-AUTO_5", "BAJAJ-AUTO"),
    # not a plain symbol name: something other than a timeframe token follows the first word
    ("CRYPTO_RIVERUSD, 180", None), ("BINANCE_BTCUSDT", None), ("csv headers std", None), ("12345", None),
])
def test_plain_symbol_only_when_the_rest_of_the_name_is_a_timeframe_token(stem, symbol):
    assert A._plain_symbol(stem) == symbol


@pytest.mark.parametrize("name, step, tf", [("ICICIBANK.csv", None, "1D"), ("5PAISA_30min.csv", 30, "30m"),
                                            ("VERANDA_1min.csv", 1, "1m"), ("OLAELEC.csv", 1, "1m")])
def test_plain_name_is_suggested_when_the_folder_option_is_off_and_used_when_it_is_on(settings, src, name, step, tf):
    p = daily(src / name) if step is None else intraday_ist(src / name, 40, step)
    sym = name.split("_")[0].split(".")[0]
    kw = dict(default_exchange="NSE", market_timezone="Asia/Kolkata")
    it = A.interpret_file(p, settings, **kw)
    assert it.status == A.NEEDS_ANSWER and [(q.key, q.options) for q in it.questions] == [("identity", (sym,))]
    assert f"suggests {sym}" in it.message and it.overrides == {}
    it = A.interpret_file(p, settings, answers={"symbol": sym}, **kw)  # the user confirms
    assert it.status == A.READY and it.overrides["symbol"] == sym
    on = A.interpret_file(p, settings, symbol_from_filename=True, **kw)
    assert on.status == A.READY and on.overrides == {"exchange": "NSE", "symbol": sym, "timeframe": tf}


def test_a_minute_token_in_the_name_is_evidence_that_agrees_or_is_asked(settings, src):
    ok = intraday_ist(src / "VERANDA_1min.csv", 30, 1)
    it = A.interpret_file(ok, settings, market_timezone="Asia/Kolkata", default_exchange="NSE",
                          symbol_from_filename=True)
    assert it.status == A.READY and it.overrides["timeframe"] == "1m"
    assert any("the file name agrees (1m)" in e for e in it.evidence)
    bad = intraday_ist(src / "VERANDA_5min.csv", 30, 1)
    q = next(q for q in A.interpret_file(bad, settings, market_timezone="Asia/Kolkata", default_exchange="NSE",
                                         symbol_from_filename=True).questions if q.key == "timeframe")
    assert set(q.options) == {"1m", "5m"}


def test_explicit_identity_in_the_file_still_wins_over_a_plain_name(settings, src):
    rows = [[d.isoformat(), "INFY"] + r for d, r in zip(weekdays(10), ohlcv(10))]
    p = write_delimited(src / "ICICIBANK.csv", ["date", "symbol", "open", "high", "low", "close", "volume"], rows)
    it = A.interpret_file(p, settings, default_exchange="NSE", symbol_from_filename=True)
    assert it.status == A.READY and "symbol" not in it.overrides  # the column is used, the name is not


def test_the_sources_screen_fills_in_the_suggestion_without_saving_it(settings, db, folder):
    from qmap_gui import source_services as ss

    src = _source(settings, db, folder)
    daily(folder / "ICICIBANK.txt")
    scan(settings, db, src)
    (state,) = D.file_states(db, src.source_id)
    assert state.outcome == "needs_answer" and ss.suggested_answers(state) == ("NSE", "ICICIBANK", "")
    assert D.latest_answer(db, src.source_id, "ICICIBANK.txt") is None  # nothing recorded until Save answer
    D.record_answer(db, src.source_id, "ICICIBANK.txt", {"symbol": "ICICIBANK"})
    res = scan(settings, db, src)
    assert result_for(res, "ICICIBANK.txt")[3] == "imported"
    assert [d.instrument for d in list_datasets(db)] == ["NSE:ICICIBANK"]


# =====================================================================================================================
# F-02: crypto identity, and timeframe answers that would relabel bars (180-minute data: see test_pr9_timeframe_3h.py)
# =====================================================================================================================

def three_hourly(path, n=40, seed=2, step=180):
    """A 24/7 market file in the layout of CRYPTO_RIVERUSD, 180.csv (offset times, OHLC, an empty indicator column)."""
    t0 = datetime(2025, 9, 22, 9, 0, tzinfo=timezone.utc)  # 14:30 +05:30
    times = [t0 + timedelta(minutes=step * i) for i in range(n)]
    header = ["time", "open", "high", "low", "close", "ATR in %"]
    rows = [[t.astimezone(IST).isoformat()] + r[:4] + [""] for t, r in zip(times, ohlcv(n, seed, volume=False))]
    return write_delimited(path, header, rows, newline="\n"), times


def test_a_crypto_prefix_gives_the_symbol_but_never_the_default_exchange(settings, run, db, src):
    p, times = three_hourly(src / "CRYPTO_BTCUSD, 60.csv", step=60)
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata", default_exchange="NSE")
    assert it.status == A.NEEDS_ANSWER and [q.key for q in it.questions] == ["exchange"]  # NOT NSE
    assert "CRYPTO_ prefix" in it.questions[0].text and it.overrides == {}
    assert any("default exchange (NSE) is not applied" in e for e in it.evidence)
    assert it.decisions["timeframe"] == "1h" and it.decisions["identity"] == {"symbol": "BTCUSD"}
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata", default_exchange="NSE",
                          answers={"exchange": "BINANCE"})
    assert it.status == A.READY and it.overrides == {"exchange": "BINANCE", "symbol": "BTCUSD", "timeframe": "1h"}
    res = _load(run, p, it)
    ds = get_dataset(db, res.dataset_ids[0])
    assert (ds.instrument, ds.timeframe, ds.row_count) == ("BINANCE:BTCUSD", "1h", 40)
    assert _stored(settings, db, ds.dataset_id).column("timestamp_utc").to_pylist() == times


def test_the_symbol_option_never_turns_a_market_prefix_into_a_symbol(settings, src):
    p, _ = three_hourly(src / "CRYPTO_BTCUSD, 60.csv", step=60)
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata", default_exchange="NSE",
                          symbol_from_filename=True)
    assert it.decisions["identity"] == {"symbol": "BTCUSD"} and [q.key for q in it.questions] == ["exchange"]


def test_a_recorded_answer_that_contradicts_the_measured_interval_is_asked_again(settings, src):
    p, _ = three_hourly(src / "CRYPTO_BTCUSD.csv", step=60)
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata",
                          answers={"exchange": "BINANCE", "timeframe": "4h"})
    q = next(q for q in it.questions if q.key == "timeframe")
    assert it.status == A.NEEDS_ANSWER and q.options == ("1h",) and "does not relabel" in q.text
    assert A.interpret_file(p, settings, market_timezone="Asia/Kolkata",
                            answers={"exchange": "BINANCE", "timeframe": "1h"}).status == A.READY


def test_a_clear_but_unsupported_bar_interval_is_rejected_never_relabelled(settings, src, monkeypatch):
    """Without a matching timeframe (e.g. if 3h were not approved), no answer can be valid: rejected with the reason."""
    p, _ = three_hourly(src / "CRYPTO_RIVERUSD, 180.csv")
    monkeypatch.setattr(A, "INTRADAY_STEPS", {k: v for k, v in A.INTRADAY_STEPS.items() if k != 180})
    for answers in ({"exchange": "BINANCE"}, {"exchange": "BINANCE", "timeframe": "4h"}):
        it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata", answers=answers)
        assert it.status == A.REJECTED and "180 minutes apart" in it.message and "does not relabel" in it.message
    assert "would relabel them" in it.message


def test_intraday_data_answered_as_daily_is_asked_again(settings, src):
    p = intraday_ist(src / "NSE_ABC.csv", 40, 5)
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata", answers={"timeframe": "1D"})
    assert [(q.key, q.options) for q in it.questions] == [("timeframe", ("5m",))]


def test_a_non_intraday_answer_to_a_name_versus_data_question_is_still_accepted(settings, src):
    """The new contradiction check is limited to measured intraday intervals, so it cannot loop on daily data."""
    p = daily(src / "NSE_ABC, 1W.csv", n=20)
    it = A.interpret_file(p, settings)
    assert {q.key for q in it.questions} == {"timeframe"}
    assert A.interpret_file(p, settings, answers={"timeframe": "1W"}).overrides["timeframe"] == "1W"


def test_the_owner_s_earlier_4h_answer_for_180_minute_bars_is_no_longer_used(settings, db, folder, monkeypatch):
    """The owner's state before this fix: RIVERUSD registered as 4h from a recorded answer. After the fix the unchanged
    file is interpreted again (rules version 3); the answer would relabel the bars, so it is not used, and the
    earlier dataset is left exactly as it was (nothing is deleted or rewritten automatically)."""
    src = _source(settings, db, folder)
    p, _ = three_hourly(folder / "CRYPTO_RIVERUSD, 180.csv")
    monkeypatch.setattr(A, "INTRADAY_STEPS", {k: v for k, v in A.INTRADAY_STEPS.items() if k != 180})
    monkeypatch.setattr(A, "_measured_step", lambda *_a: None)  # the earlier rules did not check answers
    monkeypatch.setattr(A, "RULES_VERSION", 2)
    scan(settings, db, src)
    D.record_answer(db, src.source_id, "CRYPTO_RIVERUSD, 180.csv", {"exchange": "CRYPTO", "timeframe": "4h"})
    scan(settings, db, src)
    (old,) = list_datasets(db)
    assert old.timeframe == "4h" and any(w.startswith("timeframe_spacing") for w in old.warnings)
    old_row = dict(db.one("SELECT * FROM datasets WHERE dataset_id = ?", (old.dataset_id,)))
    monkeypatch.undo()  # the current rules
    rel, change, action, outcome, detail = result_for(scan(settings, db, src), "CRYPTO_RIVERUSD, 180.csv")
    assert (change, action) == ("unchanged", "processed") and outcome in ("needs_answer", "rejected")
    assert "4h" in detail and ("does not relabel" in detail or "would relabel" in detail)
    assert dict(db.one("SELECT * FROM datasets WHERE dataset_id = ?", (old.dataset_id,))) == old_row  # untouched
    assert [d.timeframe for d in list_datasets(db)] == ["4h"]  # no second dataset under a wrong label


# =====================================================================================================================
# F-03: headerless date + time columns (UJJIVAN.txt layout)
# =====================================================================================================================

def _ujjivan_rows(n=30, step=5, extra=False):
    times = [t.astimezone(IST) for t in intraday_utc(n, start=datetime(2024, 1, 22, 3, 50, tzinfo=timezone.utc),
                                                      step_minutes=step)]
    rows = [[t.date().isoformat(), t.strftime("%H:%M:%S")] + r + ([r[4] // 2] if extra else [])
            for t, r in zip(times, ohlcv(n, 4))]
    return rows, times


def test_headerless_date_and_time_columns_are_read_and_loaded_exactly(settings, run, db, src):
    rows, times = _ujjivan_rows()
    p = write_delimited(src / "UJJIVAN.txt", None, rows)
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata", default_exchange="NSE",
                          symbol_from_filename=True)
    assert it.status == A.READY, it.message
    assert {k: v["position"] for k, v in it.decisions["mapping"].items()} == {
        "date": 0, "time": 1, "open": 2, "high": 3, "low": 4, "close": 5, "volume": 6}
    assert any("column 2 = time of day" in e and "column 7 = volume" in e for e in it.evidence)
    assert it.overrides == {"exchange": "NSE", "symbol": "UJJIVAN", "timeframe": "5m"}
    res = _load(run, p, it)
    assert res.ok
    t = _stored(settings, db, res.dataset_ids[0])
    assert t.column("timestamp_utc").to_pylist() == [x.astimezone(timezone.utc) for x in times]  # IST applied
    assert t.column("session_date").to_pylist() == [x.date() for x in times]
    for i, f in enumerate(("open", "high", "low", "close", "volume")):
        assert t.column(f).to_pylist() == [r[2 + i] for r in rows]


def test_headerless_date_and_time_with_an_eighth_column_keeps_it_and_never_uses_it_as_volume(settings, src):
    rows, _ = _ujjivan_rows(extra=True)
    p = write_delimited(src / "UJJIVAN.txt", None, rows)
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata", default_exchange="NSE",
                          symbol_from_filename=True)
    assert it.status == A.READY and it.decisions["mapping"]["volume"]["position"] == 6
    assert any("column 8 kept unchanged, never used as volume" in e for e in it.evidence)


def test_headerless_date_and_time_without_a_market_time_zone_is_asked(settings, src):
    rows, _ = _ujjivan_rows()
    p = write_delimited(src / "NSE_UJJIVAN.txt", None, rows)
    it = A.interpret_file(p, settings)
    assert it.status == A.NEEDS_ANSWER and "market_timezone" in [q.key for q in it.questions]


@pytest.mark.parametrize("mutate, words", [
    (lambda r: r.__setitem__(1, "noon"), "column 2 is not a number"),  # one time cell is not a time: old rule applies
    (lambda r: r.__setitem__(3, r[2] - 50), "columns 3-6 do not behave like open, high, low, close"),
])
def test_headerless_date_and_time_layouts_that_are_not_unambiguous_are_still_rejected(settings, src, mutate, words):
    rows, _ = _ujjivan_rows()
    mutate(rows[5])
    p = write_delimited(src / "NSE_UJJIVAN.txt", None, rows)
    it = A.interpret_file(p, settings, market_timezone="Asia/Kolkata")
    assert it.status == A.REJECTED and words in it.message


def test_a_repeated_day_is_rejected_never_deduplicated(settings, db, folder):
    """UJJIVAN.txt repeats 26-Mar-24 (75 identical bars twice): validation rejects it; nothing is dropped."""
    rows, _ = _ujjivan_rows(n=150)
    p = write_delimited(folder / "UJJIVAN.txt", None, rows[:75] + rows[:75] + rows[75:])
    before = p.read_bytes()
    src = _source(settings, db, folder, symbol_from_filename=True)
    rel, change, action, outcome, detail = result_for(scan(settings, db, src), "UJJIVAN.txt")
    assert outcome == "rejected" and "no_duplicate_timestamps: 150 row(s) share a timestamp" in detail
    assert list_datasets(db) == [] and p.read_bytes() == before


def test_the_original_rejection_message_no_longer_applies_to_the_owner_layout(settings, src):
    rows, _ = _ujjivan_rows()
    it = A.interpret_file(write_delimited(src / "UJJIVAN.txt", None, rows), settings, market_timezone="Asia/Kolkata")
    assert "column 2 is not a number on every row" not in it.message


# =====================================================================================================================
# F-04: a rules change must not churn datasets or drop answers
# =====================================================================================================================

def test_rules_upgrade_reuses_datasets_of_unchanged_files_and_keeps_answers(settings, db, folder, monkeypatch):
    src = _source(settings, db, folder)
    daily(folder / "NSE_ABC.csv")
    daily(folder / "custom name.csv", seed=3)
    scan(settings, db, src)
    D.record_answer(db, src.source_id, "custom name.csv", {"symbol": "XYZ"})
    scan(settings, db, src)
    before = {d.dataset_id: (d.instrument, d.status) for d in list_datasets(db)}
    assert sorted(v[0] for v in before.values()) == ["NSE:ABC", "NSE:XYZ"]
    monkeypatch.setattr(A, "RULES_VERSION", A.RULES_VERSION + 1)  # any later rules change
    res = scan(settings, db, src)
    for rel in ("NSE_ABC.csv", "custom name.csv"):
        _rel, change, action, outcome, detail = result_for(res, rel)
        assert (change, action, outcome) == ("unchanged", "processed", "reused"), detail
        assert "not reused" not in detail  # the recorded answer still applies
    assert {d.dataset_id: (d.instrument, d.status) for d in list_datasets(db)} == before  # nothing new, nothing superseded


# =====================================================================================================================
# OW-25: overlap with a dataset loaded through Data Management (report only, both kept)
# =====================================================================================================================

def test_a_data_management_dataset_is_compared_when_a_later_file_is_scanned_and_both_are_kept(
        settings, run, db, folder, tmp_path):
    rows = ohlcv(20)
    dm_dir = tmp_path / "dm"
    dm_dir.mkdir()
    dm_file = write_delimited(dm_dir / "NSE_ABC.csv", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(20), rows)])
    dm = _load(run, dm_file, A.interpret_file(dm_file, settings))  # Data Management: ingest only
    (dm_id,) = dm.dataset_ids
    # OW-25 (documented limitation): the Data Management load itself records no overlap/conflict check
    assert db.one("SELECT COUNT(*) FROM quality_checks WHERE check_name LIKE '%existing_dataset'")[0] == 0
    dm_row = dict(db.one("SELECT * FROM datasets WHERE dataset_id = ?", (dm_id,)))
    revised = [list(r) for r in rows]
    revised[4][3] = round(revised[4][3] + 0.5, 2)
    revised[4][1] = max(revised[4][1], revised[4][3])
    write_delimited(folder / "NSE_ABC provider2.csv", HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(20), revised)])
    src = _source(settings, db, folder)
    rel, change, action, outcome, detail = result_for(scan(settings, db, src), "NSE_ABC provider2.csv")
    assert outcome == "imported" and f"1 bar(s) differ from dataset {dm_id}" in detail
    assert dict(db.one("SELECT * FROM datasets WHERE dataset_id = ?", (dm_id,))) == dm_row
    assert sorted(d.status for d in list_datasets(db)) == ["active", "active"]
    assert _stored(settings, db, dm_id).column("close").to_pylist() == [r[3] for r in rows]
