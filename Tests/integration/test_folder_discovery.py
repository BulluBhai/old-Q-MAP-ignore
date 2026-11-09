"""Folder sources and scanning (Blueprint v1.3 §8.5.2, §8.5.6, §8.3 updates; assignment scenarios 1, 13-35)."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, timedelta

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.catalog import DataRequirement, check_readiness, get_dataset, list_datasets
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap.storage.schema import LATEST_VERSION


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    f.mkdir()
    return f


@pytest.fixture
def source(settings, db, folder):
    return D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE")


def scan(settings, db, source, **kw):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, source.source_id, **kw)


def daily(path, n=20, seed=1, start=date(2026, 1, 5), rows=None):
    rows = rows or ohlcv(n, seed)
    return write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(len(rows), start), rows)])


def outcome_of(result, rel):
    return next(f for f in result.files if f[0] == rel)


def checksums(folder):
    return {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in folder.rglob("*")
            if p.is_file()}


def test_schema_10_is_the_latest():
    assert LATEST_VERSION == 10  # 9: file-name identification ON (DQ-8); 10: reversible user decisions


# ---- sources ---------------------------------------------------------------------------------------------------

def test_q_map_own_folders_and_bad_settings_are_refused(settings, db, tmp_path):
    for bad in (settings.data_root, settings.output_root / "x"):
        bad.mkdir(parents=True, exist_ok=True)
        with pytest.raises(D.SourceError):
            D.add_folder_source(settings, db, bad)
    with pytest.raises(D.SourceError):
        D.add_folder_source(settings, db, tmp_path / "does-not-exist")
    ok = tmp_path / "ok"
    ok.mkdir()
    with pytest.raises(D.SourceError):
        D.add_folder_source(settings, db, ok, market_timezone="Mars/Olympus")
    # DQ-8 (03-Nov-26): file-name identification no longer needs a folder exchange (NSE is the default)
    assert D.add_folder_source(settings, db, ok).symbol_from_filename  # ON by default, no exchange needed
    with pytest.raises(D.SourceError):
        D.add_folder_source(settings, db, ok)  # already a source


def test_removing_a_source_keeps_its_history_and_data(settings, db, source, folder):
    daily(folder / "NSE_ABC.csv")
    scan(settings, db, source)
    D.remove_folder_source(db, source.source_id)
    assert D.list_sources(db) == [] and len(list_datasets(db)) == 1
    with pytest.raises(D.SourceError):
        scan(settings, db, source)
    again = D.add_folder_source(settings, db, folder)
    assert again.source_id == source.source_id and D.file_states(db, again.source_id)


# ---- 1, 25, 26, 31: discovery, idempotency, new files, sources untouched --------------------------------------------

def test_scan_discovers_imports_and_a_second_scan_changes_nothing(settings, db, source, folder):
    daily(folder / "NSE_ABC.csv")
    (folder / "notes.docx").write_bytes(b"PK not data")
    (folder / ".hidden.csv").write_text("x")
    (folder / "~$lock.xlsx").write_text("x")
    before = checksums(folder)
    r1 = scan(settings, db, source)
    assert outcome_of(r1, "NSE_ABC.csv")[1:4] == ("new", "processed", "imported")
    assert outcome_of(r1, "notes.docx")[3] == "ignored"
    assert {f[0] for f in r1.files} == {"NSE_ABC.csv", "notes.docx"}  # hidden and lock files are never touched
    n_datasets = db.one("SELECT COUNT(*) FROM datasets")[0]
    n_events = db.one("SELECT COUNT(*) FROM ingest_events")[0]
    r2 = scan(settings, db, source)
    # UAT 06-Nov-26 (O4): this scan imported nothing; the earlier import is shown as such and not counted again
    assert outcome_of(r2, "NSE_ABC.csv")[1:4] == ("unchanged", "skipped", "unchanged_loaded")
    assert r2.counts.get("imported", 0) == 0 and r2.counts["unchanged_loaded"] == 1
    assert D.file_history(db, source.source_id, "NSE_ABC.csv")[-1]["outcome"] == "imported"  # registry unchanged
    assert db.one("SELECT COUNT(*) FROM datasets")[0] == n_datasets
    assert db.one("SELECT COUNT(*) FROM ingest_events")[0] == n_events  # unchanged files are not even re-registered
    daily(folder / "NSE_XYZ.csv", seed=3)
    r3 = scan(settings, db, source)
    assert outcome_of(r3, "NSE_XYZ.csv")[1:4] == ("new", "processed", "imported")
    assert outcome_of(r3, "NSE_ABC.csv")[2] == "skipped"
    before.update({k: v for k, v in checksums(folder).items() if k == "NSE_XYZ.csv"})
    assert checksums(folder) == before  # 31: no source file was changed, moved or added by Q-MAP
    assert r3.report_path.is_file() and r3.report_path.name.startswith("Scan_Report_")


def test_a_touched_but_identical_file_is_recognised_by_its_checksum(settings, db, source, folder):
    p = daily(folder / "NSE_ABC.csv")
    scan(settings, db, source)
    os.utime(p, ns=(p.stat().st_atime_ns, p.stat().st_mtime_ns + 5_000_000_000))
    r = scan(settings, db, source)
    assert outcome_of(r, "NSE_ABC.csv")[1:3] == ("unchanged", "skipped")


def test_the_same_content_under_two_names_is_loaded_once(settings, db, source, folder):
    daily(folder / "NSE_ABC.csv")
    daily(folder / "NSE_ABC copy.csv")
    r = scan(settings, db, source)
    assert sorted(f[3] for f in r.files) == ["imported", "reused"]
    assert len(list_datasets(db)) == 1


def test_subfolders_and_exclusions(settings, db, folder):
    (folder / "sub").mkdir()
    daily(folder / "sub" / "NSE_SUB.csv")
    daily(folder / "NSE_TOP.csv")
    daily(folder / "NSE_SKIP.csv")
    src = D.add_folder_source(settings, db, folder, exclude_patterns=["*SKIP*"])
    r = scan(settings, db, src)
    assert {f[0] for f in r.files} == {"NSE_TOP.csv"} and r.excluded == 1
    D.update_folder_source(db, src.source_id, include_subfolders=True)
    r = scan(settings, db, src)
    assert "sub/NSE_SUB.csv" in {f[0] for f in r.files}


# ---- 27, 28, 29: changed files, overlaps and conflicts -----------------------------------------------------------------

def test_an_extended_file_is_a_new_version_and_identical_overlap_is_reported(settings, db, source, folder):
    rows = ohlcv(25)
    p = daily(folder / "NSE_ABC.csv", rows=rows[:20])
    first = scan(settings, db, source)
    old_id = json.loads(D.file_history(db, source.source_id, "NSE_ABC.csv")[-1]["dataset_ids_json"])[0]
    daily(p, rows=rows)  # the provider appended five more days
    r = scan(settings, db, source)
    rel, change, action, outcome, detail = outcome_of(r, "NSE_ABC.csv")
    assert (change, outcome) == ("changed", "imported") and "20 bar(s) identical" in detail
    new_id = json.loads(D.file_history(db, source.source_id, "NSE_ABC.csv")[-1]["dataset_ids_json"])[0]
    assert new_id != old_id
    assert get_dataset(db, old_id).status == "active" and get_dataset(db, new_id).row_count == 25
    assert get_dataset(db, new_id).validation_status == "passed"  # an identical overlap is information only
    assert first.files and len(D.file_history(db, source.source_id, "NSE_ABC.csv")) == 2


def test_conflicting_overlap_is_a_visible_warning_and_nothing_is_overwritten(settings, db, source, folder):
    rows = ohlcv(20)
    p = daily(folder / "NSE_ABC.csv", rows=rows)
    scan(settings, db, source)
    old_id = list_datasets(db)[0].dataset_id
    old_file = settings.data_path(get_dataset(db, old_id).relative_path)
    old_sha = hashlib.sha256(old_file.read_bytes()).hexdigest()
    revised = [list(r) for r in rows]
    revised[5][3] = round(revised[5][3] + 0.01, 2)  # one close revised by the provider
    revised[5][1] = max(revised[5][1], revised[5][3])
    daily(p, rows=revised)
    r = scan(settings, db, source)
    assert "1 bar(s) differ" in outcome_of(r, "NSE_ABC.csv")[4]
    new_id = max(d.dataset_id for d in list_datasets(db))
    info = get_dataset(db, new_id)
    assert info.validation_status == "passed_with_warnings"
    assert any(w.startswith("conflicts_with_existing_dataset") and f"dataset {old_id}" in w for w in info.warnings)
    assert hashlib.sha256(old_file.read_bytes()).hexdigest() == old_sha  # the earlier dataset is untouched
    rep = check_readiness(settings, db, new_id, DataRequirement(timeframes=("1D",)))
    assert rep.ready and "validation" in {w.name for w in rep.warnings}  # usable, but the conflict is shown


def test_a_file_that_disappears_is_reported_and_its_data_kept(settings, db, source, folder):
    p = daily(folder / "NSE_ABC.csv")
    scan(settings, db, source)
    p.unlink()
    r = scan(settings, db, source)
    assert outcome_of(r, "NSE_ABC.csv")[3] == "missing"
    assert len(list_datasets(db)) == 1 and check_readiness(settings, db, list_datasets(db)[0].dataset_id,
                                                           DataRequirement(timeframes=("1D",))).ready
    r = scan(settings, db, source)
    assert "NSE_ABC.csv" not in {f[0] for f in r.files}  # reported once, not on every scan
    daily(p)
    assert outcome_of(scan(settings, db, source), "NSE_ABC.csv")[1:4] == ("new", "processed", "reused")


# ---- 13-24: validation through a scan; failed data never becomes ready ------------------------------------------------

@pytest.mark.parametrize("mutate, check", [
    (lambda rows: rows.__setitem__(3, rows[3][:1] + ["abc"] + rows[3][2:]), "numeric_types"),
    (lambda rows: rows.__setitem__(4, [rows[4][0], rows[4][1], rows[4][2], rows[4][1] * 2, rows[4][4], rows[4][5]]),
     "low_le_open_close"),  # was a repeated date: since DQ-10 that is a conflict (kept, warned), not a rejection
    (lambda rows: rows.__setitem__(2, [rows[2][0], rows[2][1], rows[2][2] * 0.5, rows[2][3], rows[2][4], rows[2][5]]),
     "high_ge_open_close"),
])
def test_invalid_data_is_rejected_and_never_registered(settings, db, source, folder, mutate, check):
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(10), ohlcv(10))]
    mutate(rows)
    write_delimited(folder / "NSE_BAD.csv", HEADER, rows)
    r = scan(settings, db, source)
    rel, change, action, outcome, detail = outcome_of(r, "NSE_BAD.csv")
    assert outcome == "rejected" and check in detail.lower().replace(" ", "_")
    assert list_datasets(db) == []  # nothing the Workbench could select
    attempt = D.file_history(db, source.source_id, "NSE_BAD.csv")[-1]["attempt_id"]
    assert db.one("SELECT COUNT(*) FROM quality_checks WHERE attempt_id = ? AND severity = 'error' AND passed = 0",
                  (attempt,))[0] >= 1  # 24: validation results are recorded
    assert scan(settings, db, source).files[0][1:4] == ("unchanged", "skipped", "unchanged_rejected")
    assert D.file_history(db, source.source_id, "NSE_BAD.csv")[-1]["outcome"] == "rejected"  # registry unchanged


def test_weekend_gaps_are_not_errors_and_long_gaps_are_warnings(settings, db, source, folder):
    days = weekdays(10) + [weekdays(10)[-1] + timedelta(days=20)]
    write_delimited(folder / "NSE_GAP.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, ohlcv(11))])
    r = scan(settings, db, source)
    assert outcome_of(r, "NSE_GAP.csv")[3] == "imported"
    info = list_datasets(db)[0]
    assert info.validation_status == "passed_with_warnings" and len(info.warnings) == 1  # only the 20-day gap


def test_readiness_still_applies_per_analysis(settings, db, source, folder):
    daily(folder / "NSE_ABC.csv")
    scan(settings, db, source)
    ds = list_datasets(db)[0].dataset_id
    assert check_readiness(settings, db, ds, DataRequirement(timeframes=("1D",))).ready
    assert not check_readiness(settings, db, ds, DataRequirement(timeframes=("5m",))).ready
    assert not check_readiness(settings, db, ds, DataRequirement(timeframes=("1D",), require_volume=True,
                                                                  min_rows=500)).ready


# ---- questions and answers -------------------------------------------------------------------------------------------

def test_a_question_is_recorded_answered_and_the_answer_reused_only_for_the_same_structure(settings, db, folder):
    src = D.add_folder_source(settings, db, folder, symbol_from_filename=False)  # questions only arise with it off
    p = daily(folder / "prices.csv")
    r = scan(settings, db, src)
    assert outcome_of(r, "prices.csv")[3] == "needs_answer" and list_datasets(db) == []
    state = D.file_states(db, src.source_id)[0]
    assert state.questions[0]["key"] == "identity"
    with pytest.raises(D.SourceError):
        D.record_answer(db, src.source_id, "other.csv", {"symbol": "X"})
    for bad in ({"exchange": "NSE", "symbol": "A B?"}, {"timeframe": "2D"}, {"market_timezone": "Nowhere/City"}):
        with pytest.raises(D.SourceError):
            D.record_answer(db, src.source_id, "prices.csv", bad)
    D.record_answer(db, src.source_id, "prices.csv", {"exchange": "NSE", "symbol": "ABC"})
    r = scan(settings, db, src)
    assert outcome_of(r, "prices.csv")[3] == "imported"
    assert list_datasets(db)[0].instrument == "NSE:ABC"
    # same structure, more rows: the answer still applies
    daily(p, n=25)
    assert outcome_of(scan(settings, db, src), "prices.csv")[3] == "imported"
    # different structure (semicolons): the answer is NOT reused
    write_delimited(p, HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(10), ohlcv(10))], delimiter=";")
    rel, change, action, outcome, detail = outcome_of(scan(settings, db, src), "prices.csv")
    assert outcome == "needs_answer" and "not reused" in detail


def test_changing_the_source_settings_reprocesses_waiting_files(settings, db, folder):
    src = D.add_folder_source(settings, db, folder, default_exchange="NSE", symbol_from_filename=False)
    daily(folder / "RELIANCE.csv")
    assert outcome_of(scan(settings, db, src), "RELIANCE.csv")[3] == "needs_answer"
    D.update_folder_source(db, src.source_id, symbol_from_filename=True)
    assert outcome_of(scan(settings, db, src), "RELIANCE.csv")[3] == "imported"


# ---- 30: failures and safe retries -------------------------------------------------------------------------------------

def test_an_unexpected_failure_is_recorded_and_the_next_scan_retries(settings, db, source, folder, monkeypatch):
    daily(folder / "NSE_ABC.csv")
    real = D.ingest_file
    monkeypatch.setattr(D, "ingest_file", lambda *a, **k: (_ for _ in ()).throw(OSError("disk busy")))
    r = scan(settings, db, source)
    assert outcome_of(r, "NSE_ABC.csv")[3] == "failed" and "disk busy" in outcome_of(r, "NSE_ABC.csv")[4]
    assert list_datasets(db) == []
    monkeypatch.setattr(D, "ingest_file", real)
    r = scan(settings, db, source)
    assert outcome_of(r, "NSE_ABC.csv")[3] == "imported" and len(list_datasets(db)) == 1
    assert db.one("SELECT status FROM source_scans ORDER BY scan_id LIMIT 1")[0] == "completed"


def test_future_dated_file_is_retried_by_a_later_scan(settings, db, source, folder):
    start = date.today() - timedelta(days=10)
    days = [start + timedelta(days=i) for i in range(14)]  # four days in the future
    write_delimited(folder / "NSE_FUT.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, ohlcv(14))])
    r = scan(settings, db, source)
    assert outcome_of(r, "NSE_FUT.csv")[3] == "rejected" and "again automatically" in outcome_of(r, "NSE_FUT.csv")[4]
    assert outcome_of(scan(settings, db, source), "NSE_FUT.csv")[2] == "skipped"
    later = scan(settings, db, source, today=date.today() + timedelta(days=10))
    assert outcome_of(later, "NSE_FUT.csv")[3] == "imported"


def test_scan_records_are_append_only(settings, db, source, folder):
    daily(folder / "NSE_ABC.csv")
    scan(settings, db, source)
    for sql in ("UPDATE source_file_observations SET outcome = 'failed'", "DELETE FROM source_file_observations",
                "DELETE FROM source_scans", "UPDATE source_scans SET status = 'running'", "DELETE FROM data_sources",
                "UPDATE data_sources SET location = 'elsewhere'"):
        with pytest.raises(Exception):
            with db.transaction() as conn:
                conn.execute(sql)


def test_an_unavailable_folder_is_explained(settings, db, source, folder):
    folder.rename(folder.with_name("renamed"))
    with pytest.raises(D.SourceError, match="not available"):
        scan(settings, db, source)
