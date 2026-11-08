"""P4 (owner instruction 03-Nov-26, sections 7 and 8): default acceptance, reversible rejection, Stop, consolidated
exceptions, bulk corrections, and the same behaviour from the command line. All data are SYNTHETIC."""

from __future__ import annotations

import csv
import hashlib
import sqlite3

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.analytical_engine import DATASET_SUMMARY
from qmap.catalog import check_readiness, get_dataset, list_datasets
from qmap.cli import main as cli_main
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap.data_engine import user_decisions as UD
from qmap_gui import source_services as ss
from qmap_gui import workbench_services as ws


def daily(path, n=10, seed=1, fmt="%Y-%m-%d"):
    return write_delimited(path, HEADER, [[d.strftime(fmt)] + r for d, r in zip(weekdays(n), ohlcv(n, seed))])


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    f.mkdir()
    return f


def scan(settings, db, src, **kw):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, src.source_id, **kw)


# ---- default acceptance and consolidated exceptions --------------------------------------------------------------
def test_a_folder_of_many_routine_files_is_accepted_without_a_single_question(settings, db, folder):
    for i in range(40):
        daily(folder / f"STOCK{i:02d} ({i % 3}).csv" if i % 2 else folder / f"STOCK{i:02d}.csv", seed=i)
    src = D.add_folder_source(settings, db, folder)
    res = scan(settings, db, src)
    assert res.counts == {"imported": 40}  # no "needs your answer", no prompts
    groups = ss.exception_groups(settings, src.source_id)
    assert [g["kind"] for g in groups] == ["provisional"]  # one grouped line, not 40 messages
    assert len(groups[0]["files"]) == 40
    text = "".join(t for t, _ in ss.exceptions_text(groups))
    assert "1 kind(s) of exception" in text and "+34 more" in text


def test_assumed_day_first_dates_and_default_time_zone_are_grouped_and_correctable(settings, db, folder):
    from datetime import date

    days = [date(2025, 1, d) for d in (1, 2, 3, 6, 7, 8)]  # 01/01/2025 .. 08/01/2025: day/month order ambiguous
    write_delimited(folder / "NSE_ABC.csv", HEADER, [[d.strftime("%d/%m/%Y")] + r for d, r in zip(days, ohlcv(6))])
    src = D.add_folder_source(settings, db, folder)
    scan(settings, db, src)
    kinds = [g["kind"] for g in ss.exception_groups(settings, src.source_id)]
    assert "date_layout_assumed" in kinds
    (state,) = D.file_states(db, src.source_id)
    options = dict(ss.date_options(state))
    assert "DD/MM/YYYY" in options and "MM/DD/YYYY" in options  # the correction choices are offered
    ss.correct_files(settings, src.source_id, [state], {"date_format": options["MM/DD/YYYY"]})
    scan(settings, db, src)
    (state,) = D.file_states(db, src.source_id)
    assert state.interpretation["decisions"]["date_layout"] == "format:%m/%d/%Y"
    assert len(list_datasets(db)) == 2  # the corrected reading is a new dataset; the first is unchanged


# ---- reversible rejection ----------------------------------------------------------------------------------------
def test_reject_and_restore_are_reversible_recorded_and_change_nothing(settings, db, folder):
    p = daily(folder / "NSE_ABC.csv")
    src = D.add_folder_source(settings, db, folder)
    scan(settings, db, src)
    (ds,) = list_datasets(db)
    row = dict(db.one("SELECT * FROM datasets WHERE dataset_id = ?", (ds.dataset_id,)))
    stored = settings.data_path(ds.relative_path).read_bytes()
    source_sha = hashlib.sha256(p.read_bytes()).hexdigest()
    (state,) = D.file_states(db, src.source_id)

    res = ss.reject_files(settings, [state], "wrong timeframe")
    assert res.changed == [ds.dataset_id]
    info = get_dataset(db, ds.dataset_id)
    assert info.rejected_by_user and info.state_label == "Rejected by you"
    assert [d.dataset_id for d in ws.ready_datasets(settings)] == []  # not offered to analyses
    rep = check_readiness(settings, db, ds.dataset_id, DATASET_SUMMARY.requirement)
    assert not rep.ready and "You rejected this dataset" in rep.failures[0].detail
    assert ss.reject_files(settings, [state]).unchanged == [(ds.dataset_id, "already rejected")]
    assert ("NSE_ABC.csv" in [g["files"][0] for g in ss.exception_groups(settings, src.source_id)
                              if g["kind"] == "rejected_by_you"])

    assert ss.restore_files(settings, [state], "checked again").changed == [ds.dataset_id]
    assert [d.dataset_id for d in ws.ready_datasets(settings)] == [ds.dataset_id]
    assert check_readiness(settings, db, ds.dataset_id, DATASET_SUMMARY.requirement).ready
    hist = UD.history(db, ds.dataset_id)
    assert [(h["decision"], h["reason"], h["origin"]) for h in hist] == [("rejected", "wrong timeframe", "sources"),
                                                                          ("restored", "checked again", "sources")]
    # nothing else changed: the registry row, the stored file and the source file
    assert dict(db.one("SELECT * FROM datasets WHERE dataset_id = ?", (ds.dataset_id,))) == row
    assert settings.data_path(ds.relative_path).read_bytes() == stored
    assert hashlib.sha256(p.read_bytes()).hexdigest() == source_sha
    # the decisions are append-only and a raw original file can never be rejected
    with pytest.raises(sqlite3.IntegrityError):
        db.connection().execute("DELETE FROM dataset_user_decisions")
    raw = db.one("SELECT dataset_id FROM datasets WHERE layer = 'raw'")[0]
    assert UD.reject_datasets(db, [raw]).unchanged == [(raw, "an original source file is never rejected")]


def test_a_rejected_file_stays_rejected_when_scanned_again_unchanged(settings, db, folder):
    daily(folder / "NSE_ABC.csv")
    src = D.add_folder_source(settings, db, folder)
    scan(settings, db, src)
    ss.reject_files(settings, D.file_states(db, src.source_id))
    scan(settings, db, src)
    assert [d.rejected_by_user for d in list_datasets(db)] == [True]


# ---- Stop ---------------------------------------------------------------------------------------------------------
def test_stop_finishes_the_current_file_and_reports_what_was_not_processed(settings, db, folder):
    for i in range(6):
        daily(folder / f"NSE_S{i}.csv", seed=i)
    src = D.add_folder_source(settings, db, folder)
    asked = []

    def stop_after_two():
        asked.append(1)
        return len(asked) > 2

    res = scan(settings, db, src, should_stop=stop_after_two)
    assert res.stopped and len(res.files) == 2 and len(res.not_processed) == 4
    assert "STOPPED by you: 4 file(s) not processed" in res.summary()
    assert len(list_datasets(db)) == 2  # completed work kept, nothing half-written
    assert not list((settings.cleaned_dir / "_incoming").glob("*")) if (settings.cleaned_dir / "_incoming").exists() else True
    rows = list(csv.reader(open(res.report_path, encoding="utf-8")))
    assert sum(1 for r in rows if "Not processed (scan stopped by you)" in r) == 4
    summary = db.one("SELECT summary_json FROM source_scans WHERE scan_id = ?", (res.scan_id,))[0]
    assert '"stopped": true' in summary
    rest = scan(settings, db, src)  # the next scan processes the rest
    assert len(list_datasets(db)) == 6 and not rest.stopped


def test_the_scan_job_stop_button_path(settings, db, folder):
    for i in range(3):
        daily(folder / f"NSE_S{i}.csv", seed=i)
    src = D.add_folder_source(settings, db, folder)
    job = ss.ScanJob(settings, src.source_id)
    job.cancel()  # pressed before the first file: nothing is processed, the stop is reported
    out = job.run()
    assert out.stopped and len(out.not_processed) == 3 and not list_datasets(db)


# ---- command line ------------------------------------------------------------------------------------------------
def test_command_line_scan_reject_and_restore(settings, roots, folder, tmp_path, capsys):
    cfg = tmp_path / "qmap.local.toml"
    cfg.write_text(f'[paths]\ndata_root = "{roots["data"].as_posix()}"\noutput_root = "{roots["output"].as_posix()}"\n')
    daily(folder / "RELIANCE (1).csv")
    assert cli_main(["--config", str(cfg), "scan", "--folder", str(folder)]) == 0
    out = capsys.readouterr().out
    assert "IMPORTED" in out and "Identification exceptions:" in out
    from qmap.storage.db import open_database

    db = open_database(settings.db_path)
    (ds,) = list_datasets(db)
    assert ds.instrument == "NSE:RELIANCE"
    assert cli_main(["--config", str(cfg), "reject", "--dataset-id", str(ds.dataset_id), "--reason", "test"]) == 0
    assert get_dataset(db, ds.dataset_id).rejected_by_user
    assert cli_main(["--config", str(cfg), "restore", "--dataset-id", str(ds.dataset_id)]) == 0
    assert not get_dataset(db, ds.dataset_id).rejected_by_user
    assert cli_main(["--config", str(cfg), "scan", "--folder", str(folder)]) == 0  # existing folder reused
    assert len(D.list_sources(db)) == 1
