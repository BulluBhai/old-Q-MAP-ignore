"""Regression tests for the owner decisions recorded on PR #9 (02-Nov-26).

DQ-1  Conflicting overlapping price bars: REPORT ONLY. Both datasets are kept unchanged; no winner is chosen, nothing is
      merged or overwritten, and the conflict stays visible.
DQ-2a Headerless files: positional convention Date, Open, High, Low, Close; Volume only when the validation rules
      support it (column 6, every value a whole number >= 0).
DQ-2b File-name identity (`NSE_NIFTY, 1D.csv`) is allowed, but explicit instrument information inside the file is
      never silently overridden by the file name.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date

import pyarrow.parquet as pq
import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.catalog import DataRequirement, check_readiness, get_dataset, list_datasets
from qmap.core.runs import run_context
from qmap.data_engine import auto_interpret as A
from qmap.data_engine import discovery as D
from qmap.data_engine.ingest import ingest_file


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    f.mkdir()
    return f


@pytest.fixture
def source(settings, db, folder):
    return D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata")


def scan(settings, db, source):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, source.source_id)


def result_for(res, rel):
    return next(f for f in res.files if f[0] == rel)


def daily_file(path, rows, start=date(2026, 1, 5)):
    return write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(len(rows), start), rows)])


def row_snapshot(db, dataset_id):
    return dict(db.one("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,)))


def stored(settings, db, dataset_id):
    return pq.read_table(settings.data_path(get_dataset(db, dataset_id).relative_path))


# =====================================================================================================================
# DQ-1: report only
# =====================================================================================================================

def _revise(rows, index, delta):
    out = [list(r) for r in rows]
    out[index][3] = round(out[index][3] + delta, 2)  # close
    out[index][1] = max(out[index][1], out[index][3])  # keep the bar valid: high >= close
    out[index][2] = min(out[index][2], out[index][3])
    return out


def test_dq1_conflict_is_reported_and_both_datasets_stay_exactly_as_they_were(settings, db, source, folder):
    rows = ohlcv(30)
    daily_file(folder / "NSE_ABC.csv", rows[:20])
    scan(settings, db, source)
    (old_id,) = [d.dataset_id for d in list_datasets(db)]
    old_row = row_snapshot(db, old_id)
    old_file = settings.data_path(old_row["relative_path"])
    old_bytes = old_file.read_bytes()
    old_checks = db.query("SELECT * FROM quality_checks WHERE dataset_id = ? OR attempt_id = ?",
                          (old_id, old_row["created_by_attempt_id"]))

    # a second file from another provider: bars 6-25, two of the shared bars revised, five new bars
    revised = _revise(_revise(rows, 8, 0.5), 12, -0.25)
    daily_file(folder / "NSE_ABC other provider.csv", revised[5:25], start=weekdays(6)[-1])
    res = scan(settings, db, source)
    rel, change, action, outcome, detail = result_for(res, "NSE_ABC other provider.csv")
    assert outcome == "imported"
    assert f"2 bar(s) differ from dataset {old_id}" in detail  # reported in the scan result and report

    new_id = max(d.dataset_id for d in list_datasets(db))
    # the earlier dataset: registry row, file and checks are untouched; still active and still ready
    assert row_snapshot(db, old_id) == old_row
    assert old_file.read_bytes() == old_bytes
    assert db.query("SELECT * FROM quality_checks WHERE dataset_id = ? OR attempt_id = ?",
                    (old_id, old_row["created_by_attempt_id"])) == old_checks
    assert get_dataset(db, old_id).status == "active" and get_dataset(db, old_id).warnings == []
    # the new dataset holds exactly its own file's values: nothing merged in either direction, no winner chosen
    new = get_dataset(db, new_id)
    assert new.status == "active" and new.row_count == 20
    assert stored(settings, db, new_id).column("close").to_pylist() == [r[3] for r in revised[5:25]]
    assert stored(settings, db, old_id).column("close").to_pylist() == [r[3] for r in rows[:20]]
    assert db.one("SELECT COUNT(*) FROM datasets WHERE status = 'superseded'")[0] == 0
    # the conflict is visible where datasets are chosen
    conflict = [w for w in new.warnings if w.startswith("conflicts_with_existing_dataset")]
    assert len(conflict) == 1 and "2 of 15 overlapping bar(s) differ" in conflict[0] and f"dataset {old_id}" in conflict[0]
    assert "close" in conflict[0]  # names the field and both values
    rep = check_readiness(settings, db, new_id, DataRequirement(timeframes=("1D",)))
    assert rep.ready and any("conflicts_with_existing_dataset" in w.detail for w in rep.warnings)
    assert check_readiness(settings, db, old_id, DataRequirement(timeframes=("1D",))).ready


def test_dq1_the_conflict_stays_visible_on_later_scans_and_is_not_recorded_twice(settings, db, source, folder):
    rows = ohlcv(20)
    daily_file(folder / "NSE_ABC.csv", rows)
    scan(settings, db, source)
    daily_file(folder / "NSE_ABC v2.csv", _revise(rows, 3, 1.0))
    scan(settings, db, source)
    n_checks = db.one("SELECT COUNT(*) FROM quality_checks")[0]
    res = scan(settings, db, source)
    rel, change, action, outcome, detail = result_for(res, "NSE_ABC v2.csv")
    assert (change, action) == ("unchanged", "skipped") and "differ from dataset" in detail
    assert db.one("SELECT COUNT(*) FROM quality_checks")[0] == n_checks
    assert sum(1 for d in list_datasets(db) if d.warnings) == 1


def test_dq1_identical_overlap_is_information_only(settings, db, source, folder):
    rows = ohlcv(20)
    daily_file(folder / "NSE_ABC.csv", rows[:15])
    scan(settings, db, source)
    daily_file(folder / "NSE_ABC longer.csv", rows)
    res = scan(settings, db, source)
    assert "15 bar(s) identical" in result_for(res, "NSE_ABC longer.csv")[4]
    assert all(d.validation_status == "passed" for d in list_datasets(db))


def test_dq1_a_different_instrument_or_timeframe_is_not_compared(settings, db, source, folder):
    rows = ohlcv(20)
    daily_file(folder / "NSE_ABC.csv", rows)
    daily_file(folder / "NSE_XYZ.csv", _revise(rows, 3, 1.0))
    scan(settings, db, source)
    assert all(not d.warnings for d in list_datasets(db))


# =====================================================================================================================
# DQ-2a: headerless positional convention
# =====================================================================================================================

def _headerless(path, rows):
    return write_delimited(path, None, [[d.isoformat()] + r for d, r in zip(weekdays(len(rows)), rows)])


def test_dq2_headerless_columns_are_date_open_high_low_close(settings, run, db, src):
    rows = ohlcv(12, volume=False)
    p = _headerless(src / "NSE_ABC.csv", rows)
    it = A.interpret_file(p, settings)
    assert it.status == A.READY
    assert {k: v["position"] for k, v in it.decisions["mapping"].items()} == \
        {"date": 0, "open": 1, "high": 2, "low": 3, "close": 4}
    res = ingest_file(run, p, it.profile, **{k: it.overrides[k] for k in ("exchange", "symbol", "timeframe")})
    t = stored(settings, db, res.dataset_ids[0])
    for i, name in enumerate(("open", "high", "low", "close")):
        assert t.column(name).to_pylist() == [r[i] for r in rows], name
    assert t.column("session_date").to_pylist() == weekdays(12)  # row 1 is data, not a header
    assert get_dataset(db, res.dataset_ids[0]).volume_status == "absent"


def test_dq2_headerless_sixth_column_is_volume_only_when_every_value_is_a_whole_number_of_zero_or_more(
        settings, run, db, src):
    rows = ohlcv(12)
    p = _headerless(src / "NSE_ABC.csv", rows)
    it = A.interpret_file(p, settings)
    assert it.decisions["mapping"]["volume"]["position"] == 5
    res = ingest_file(run, p, it.profile, **{k: it.overrides[k] for k in ("exchange", "symbol", "timeframe")})
    assert stored(settings, db, res.dataset_ids[0]).column("volume").to_pylist() == [float(r[4]) for r in rows]


@pytest.mark.parametrize("sixth, why", [
    (lambda i: -5 if i == 3 else 100, "a negative value"),
    (lambda i: 10.5 if i == 3 else 100, "a fraction"),
    (lambda i: "" if i == 3 else 100, "a blank value"),
    (lambda i: "n/a" if i == 3 else 100, "text"),
])
def test_dq2_headerless_sixth_column_that_fails_the_volume_rules_is_kept_but_never_used_as_volume(
        settings, run, db, src, sixth, why):
    rows = [r[:4] + [sixth(i)] for i, r in enumerate(ohlcv(12))]
    p = _headerless(src / "NSE_ABC.csv", rows)
    it = A.interpret_file(p, settings)
    assert it.status == A.READY and "volume" not in it.decisions["mapping"], why
    assert any("not used as volume" in e for e in it.evidence)
    res = ingest_file(run, p, it.profile, **{k: it.overrides[k] for k in ("exchange", "symbol", "timeframe")})
    assert res.outcome == "accepted"
    t = stored(settings, db, res.dataset_ids[0])
    assert get_dataset(db, res.dataset_ids[0]).volume_status == "absent"
    assert t.column("x_col5").to_pylist() == [str(sixth(i)) for i in range(12)]  # preserved as read


def test_dq2_headerless_seventh_and_later_columns_are_never_volume(settings, src):
    rows = [r[:4] + [-1 if i % 2 else 3, 1000 + i] for i, r in enumerate(ohlcv(12))]  # col 6 fails, col 7 would pass
    it = A.interpret_file(_headerless(src / "NSE_ABC.csv", rows), settings)
    assert it.status == A.READY and "volume" not in it.decisions["mapping"]


@pytest.mark.parametrize("rows, words", [
    ([[r[0], r[1], r[2], r[1] + 1, r[4]] if i == 4 else r for i, r in enumerate(ohlcv(12))], "order cannot be confirmed"),
    ([r[:3] for r in ohlcv(12)], "separated"),  # date + 3 columns: too few
])
def test_dq2_headerless_files_that_do_not_fit_the_convention_are_rejected(settings, src, rows, words):
    it = A.interpret_file(_headerless(src / "NSE_ABC.csv", rows), settings)
    assert it.status == A.REJECTED and words in it.message


def test_dq2_headerless_first_column_must_be_a_date(settings, src):
    p = write_delimited(src / "NSE_ABC.csv", None, [[f"bar{i}"] + r for i, r in enumerate(ohlcv(10))])
    it = A.interpret_file(p, settings)
    assert it.status == A.REJECTED


# =====================================================================================================================
# DQ-2b: identity from the file name, never overriding the file's contents
# =====================================================================================================================

def _with_id_columns(path, cols, values):
    header = ["date", *cols, "open", "high", "low", "close", "volume"]
    rows = [[d.isoformat(), *values(i), *r] for i, (d, r) in enumerate(zip(weekdays(10), ohlcv(10)))]
    return write_delimited(path, header, rows)


def test_dq2_file_name_supplies_identity_when_the_file_has_none(settings, db, source, folder):
    daily_file(folder / "NSE_NIFTY, 1D.csv", ohlcv(20))
    res = scan(settings, db, source)
    assert result_for(res, "NSE_NIFTY, 1D.csv")[3] == "imported"
    assert [d.instrument for d in list_datasets(db)] == ["NSE:NIFTY"]
    interp = D.file_states(db, source.source_id)[0].interpretation
    assert any("from the file name" in e for e in interp["evidence"])  # recorded, not silent


def test_dq2_columns_that_agree_with_the_name_are_used(settings, src):
    p = _with_id_columns(src / "NSE_TCS.csv", ["exchange", "symbol"], lambda i: ["NSE", "TCS"])
    it = A.interpret_file(p, settings)
    assert it.status == A.READY and it.profile.instrument.exchange_from == "column"
    assert it.profile.instrument.symbol_from == "column" and "exchange" not in it.overrides


@pytest.mark.parametrize("name, cols, values, field", [
    ("NSE_TCS.csv", ["symbol"], lambda i: ["INFY"], "symbol"),
    ("NSE_TCS.csv", ["exchange", "symbol"], lambda i: ["BSE", "TCS"], "exchange"),
    ("NSE_TCS.csv", ["exchange"], lambda i: ["BSE"], "exchange"),  # was silently read as NSE before 02-Nov-26
    ("NSE_TCS.csv", ["symbol"], lambda i: ["INFY" if i % 2 else "WIPRO"], "symbol"),  # several symbols, none TCS
])
def test_dq2_a_name_that_contradicts_the_file_is_rejected_never_used(settings, db, source, folder, name, cols, values,
                                                                     field):
    _with_id_columns(folder / name, cols, values)
    res = scan(settings, db, source)
    rel, change, action, outcome, detail = result_for(res, name)
    assert outcome == "rejected" and f"says {field}" in detail and "never overridden" in detail
    assert list_datasets(db) == []


def test_dq2_exchange_column_with_symbol_from_the_name(settings, db, source, folder):
    _with_id_columns(folder / "BSE_TCS.csv", ["exchange"], lambda i: ["BSE"])
    res = scan(settings, db, source)
    assert result_for(res, "BSE_TCS.csv")[3] == "imported"
    assert [d.instrument for d in list_datasets(db)] == ["BSE:TCS"]


def test_dq2_symbol_column_without_an_exchange_asks_only_for_the_exchange(settings, db, source, folder):
    _with_id_columns(folder / "prices.csv", ["symbol"], lambda i: ["INFY"])
    res = scan(settings, db, source)
    assert result_for(res, "prices.csv")[3] == "needs_answer"
    state = D.file_states(db, source.source_id)[0]
    assert [q["key"] for q in state.questions] == ["exchange"]
    D.record_answer(db, source.source_id, "prices.csv", {"exchange": "NSE"})
    assert result_for(scan(settings, db, source), "prices.csv")[3] == "imported"
    assert [d.instrument for d in list_datasets(db)] == ["NSE:INFY"]


def test_dq2_unrecognised_name_prefix_is_never_identity(settings, src):
    p = daily_file(src / "DATA_PRICES.csv", ohlcv(10))
    it = A.interpret_file(p, settings)
    assert [q.key for q in it.questions] == ["identity"]
    assert json.dumps(it.as_dict())  # the question is serialisable for the scan record


def test_source_files_are_unchanged_by_all_of_the_above(settings, db, source, folder):
    rows = ohlcv(20)
    paths = [daily_file(folder / "NSE_ABC.csv", rows), daily_file(folder / "NSE_ABC v2.csv", _revise(rows, 2, 1.0)),
             _with_id_columns(folder / "NSE_TCS.csv", ["symbol"], lambda i: ["INFY"]),
             _headerless(folder / "NSE_HDL.csv", ohlcv(10))]
    before = {p: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in paths}
    scan(settings, db, source)
    scan(settings, db, source)
    assert {p: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in paths} == before
