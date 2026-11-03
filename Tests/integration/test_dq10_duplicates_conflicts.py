"""DQ-9 and DQ-10 (owner instruction 03-Nov-26): exact duplicates, conflicting observations, overlap reporting.

Approved behaviour:
- rows identical in every source column: removed from the standardised copy only, counted and recorded;
- rows sharing a timestamp with any difference: ALL kept, flagged, warned; never resolved, never excluded, and they do
  not block analyses or weekly/monthly derivation; existing calculation rules are unchanged;
- overlaps between datasets are reported (scan, Data Management, command line) in a consolidated report; nothing is
  merged, overwritten or chosen.
All data are SYNTHETIC.
"""

from __future__ import annotations

import csv
import hashlib

import pytest

from fixtures.builders import HEADER, daily_rows, intraday_utc, ohlcv, weekdays, write_delimited
from fixtures.profiles import do_ingest, make_profile, profile_text, read_group
from qmap.analytical_engine import DATASET_SUMMARY, run_analysis
from qmap.catalog import DataRequirement, TIMEFRAME_ORDER, check_readiness, get_dataset, list_datasets
from qmap.cli import main as cli_main
from qmap.core.runs import run_context
from qmap.data_engine import canonical as C
from qmap.data_engine import discovery as D
from qmap.data_engine.derive import derive_timeframe

CONFLICT = C.FLAG_CONFLICTING_OBSERVATION


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def conflict_rows():
    """12 source rows: rows 4-5 share a date with different high and close; rows 7-8 share a date with different
    volume; row 12 repeats row 11 exactly."""
    rows = [list(r) for r in daily_rows(9)]
    rows.insert(4, [rows[3][0], rows[3][1], rows[3][2] + 1, rows[3][3], rows[3][4] + 0.5, rows[3][5]])
    rows.insert(7, [rows[6][0], *rows[6][1:5], rows[6][5] + 100])
    rows.append(list(rows[-1]))
    return rows


@pytest.fixture
def conflicted(src, run, settings, db):
    p = write_delimited(src / "conflicts.csv", HEADER, conflict_rows())
    before = sha(p)
    res = do_ingest(run, p)
    assert res.outcome == "accepted", res.message
    assert sha(p) == before  # the source file is never modified
    return res.dataset_ids[0], res


# ---- within one file ------------------------------------------------------------------------------------------
def test_ohlc_and_volume_conflicts_are_kept_flagged_and_reported_with_values(conflicted, settings, db):
    ds, res = conflicted
    g = read_group(settings, db, ds)
    assert g["src_row"] == list(range(1, 12))  # row 12 (exact copy of 11) removed, nothing else
    assert [bool(f & CONFLICT) for f in g["quality_flags"]] == [False] * 3 + [True, True] + [False] + [True, True] + [False] * 3
    assert g["close"][3] != g["close"][4] and g["volume"][6] != g["volume"][7]  # both observations, both values
    chk = next(c for c in res.checks if c.name == "conflicting_observations")
    assert chk.severity == "warning" and chk.rows_failed == 4
    assert "2 timestamp(s)" in chk.detail and "close" in chk.detail and "volume" in chk.detail and "high" in chk.detail
    dup = next(c for c in res.checks if c.name == "exact_duplicates_removed")
    assert dup.rows_failed == 1 and "12" in dup.detail
    with open(res.issues_report, newline="") as fh:
        issues = [r for r in csv.DictReader(fh) if r["check"] == "conflicting_observations"]
    assert {r["source_row"] for r in issues} == {"4", "5", "7", "8"}
    assert all(" / " in r["message"] for r in issues)  # both values shown


def test_a_conflicted_dataset_stays_usable_and_the_limitation_is_shown(conflicted, settings, db):
    ds, _ = conflicted
    info = get_dataset(db, ds)
    assert info.status == "active" and any(w.startswith("conflicting_observations") for w in info.warnings)
    rep = check_readiness(settings, db, ds, DataRequirement(timeframes=TIMEFRAME_ORDER, min_rows=2))
    assert rep.ready  # never excluded or blocked
    item = next(i for i in rep.items if i.name == "conflicts")
    assert item.status == "warn" and "has not chosen" in item.detail and "each stored row as a bar" in item.detail


def test_dataset_summary_runs_with_conflicts_and_keeps_its_method(conflicted, settings, db):
    ds, _ = conflicted
    res = run_analysis(settings, db, DATASET_SUMMARY, [ds], {})
    assert res.ok, res.message
    row = next(csv.DictReader(open(res.outputs[0], encoding="utf-8")))
    assert row["Bars"] == "11" and row["Conflicting timestamps"] == "2"
    assert row["Returns counted"] == "10"  # unchanged method: every stored row is a bar


def test_weekly_derivation_is_not_blocked_by_conflicts_and_says_so(conflicted, run, settings, db):
    ds, _ = conflicted
    out = derive_timeframe(run, ds, "1W")
    assert out.ok, out.message
    assert any("conflicting observations" in w for w in out.assessment.warnings)
    g = read_group(settings, db, out.dataset_id)
    assert any(f & CONFLICT for f in g["quality_flags"])
    chk = db.one("SELECT * FROM quality_checks WHERE dataset_id = ? AND check_name = 'period_has_conflicting_observations'",
                 (out.dataset_id,))
    assert chk is not None and chk["severity"] == "warning" and "not chosen" in chk["detail"]


def test_intraday_conflicts_and_exact_duplicates(src, run, settings, db):
    times = intraday_utc(12, step_minutes=5)
    rows = [[t.isoformat(), *r] for t, r in zip(times, ohlcv(12))]
    rows.insert(3, [rows[2][0], rows[2][1], rows[2][2], rows[2][3], rows[2][4] * 0.999, rows[2][5]])  # different close
    rows.insert(6, list(rows[5]))  # exact duplicate
    prof = make_profile(instrument={"timeframe": "5m"}, datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, write_delimited(src / "i.csv", HEADER, rows), prof)
    assert res.outcome == "accepted", res.message
    g = read_group(settings, db, res.dataset_ids[0])
    assert len(g["src_row"]) == 13 and 7 not in g["src_row"]
    assert sum(bool(f & CONFLICT) for f in g["quality_flags"]) == 2
    spacing = next(c for c in res.checks if c.name == "timeframe_spacing")
    assert spacing.passed  # a repeated timestamp is not a 0-minute bar interval


def test_rows_that_differ_only_in_an_extra_column_are_not_duplicates(src, run, settings, db):
    rows = [list(r) + ["x"] for r in daily_rows(6)]
    rows.insert(2, rows[1][:-1] + ["y"])
    res = do_ingest(run, write_delimited(src / "e.csv", HEADER + ["note"], rows))
    g = read_group(settings, db, res.dataset_ids[0])
    assert len(g["src_row"]) == 7 and sum(bool(f & CONFLICT) for f in g["quality_flags"]) == 2
    detail = next(c for c in res.checks if c.name == "conflicting_observations").detail
    assert "1 of these timestamp(s) differ only in preserved extra column(s)" in detail


# ---- across files: scan, Data Management, command line -----------------------------------------------------------
@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    f.mkdir()
    return f


def _daily(path, rows, start=None):
    days = weekdays(len(rows)) if start is None else weekdays(len(rows), start)
    return write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(days, rows)])


def _scan(settings, db, src):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, src.source_id)


def test_scan_writes_a_consolidated_overlap_report_and_keeps_both_datasets(settings, db, folder):
    rows = ohlcv(20)
    a = _daily(folder / "NSE_ABC.csv", rows)
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE")
    _scan(settings, db, src)
    revised = [list(r) for r in rows]
    revised[3][3] = round(revised[3][3] + 0.5, 2)
    revised[3][1] = max(revised[3][1], revised[3][3])
    b = _daily(folder / "NSE_ABC provider2.csv", revised)
    shas = {a: sha(a), b: sha(b)}
    res = _scan(settings, db, src)
    assert res.overlap_report_path is not None and res.overlap_report_path.parent.name == res.run_id
    rows_out = list(csv.DictReader(open(res.overlap_report_path, encoding="utf-8")))
    (r,) = rows_out
    assert r["Instrument"] == "NSE:ABC" and r["Conflicting bars"] == "1" and r["Identical bars"] == "19"
    assert r["New source file(s)"] == "NSE_ABC provider2.csv" and r["Existing source file(s)"] == "NSE_ABC.csv"
    assert r["Overlap from"] == weekdays(20)[0].isoformat() and r["Finding"] == "Conflicting observations"
    assert "close" in r["Examples"]
    assert sorted(d.status for d in list_datasets(db)) == ["active", "active"]  # no winner, nothing superseded
    assert {p: sha(p) for p in shas} == shas


def test_a_repeated_import_under_another_layout_is_reported_as_such(settings, db, folder):
    rows = ohlcv(10)
    _daily(folder / "NSE_ABC.csv", rows)
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata")
    _scan(settings, db, src)
    days = weekdays(10)
    write_delimited(folder / "NSE_ABC copy.csv", HEADER, [[d.isoformat()] + r for d, r in zip(days, rows)], delimiter=";")
    res = _scan(settings, db, src)
    detail = next(f for f in res.files if f[0] == "NSE_ABC copy.csv")[4]
    assert "possibly a repeated import" in detail
    r = next(csv.DictReader(open(res.overlap_report_path, encoding="utf-8")))
    assert r["Finding"] == "Same data (possible repeated import)"


def test_datasets_with_internal_conflicts_are_compared_as_sets_of_observations(settings, db, folder):
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(6), ohlcv(6))]
    rows.insert(2, [rows[1][0], rows[1][1], rows[1][2], rows[1][3], rows[1][4] + 0.01, rows[1][5]])
    write_delimited(folder / "NSE_ABC.csv", HEADER, rows)
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata")
    _scan(settings, db, src)
    write_delimited(folder / "NSE_ABC same.csv", HEADER, list(reversed(rows)), delimiter=";")
    res = _scan(settings, db, src)
    r = next(csv.DictReader(open(res.overlap_report_path, encoding="utf-8")))
    assert (r["Conflicting bars"], r["Identical bars"]) == ("0", "6")  # same two observations on that date


def test_data_management_job_reports_overlap_and_writes_the_report(settings, db, run, src):
    from qmap_gui.jobs import IngestJob

    rows = daily_rows(10)
    do_ingest(run, write_delimited(src / "first.csv", HEADER, rows))
    changed = [list(r) for r in rows]
    changed[2][4] = round(changed[2][4] * 1.001, 2)
    changed[2][2] = max(changed[2][2], changed[2][4])
    second = write_delimited(src / "second.csv", HEADER, changed)
    summary = IngestJob(settings, [second], make_profile(profile_version=2, source_label="v2")).run()
    (o,) = summary.outcomes
    assert o.ok and "differ from dataset" in o.message
    assert summary.overlap_report is not None and summary.overlap_report.is_file()
    assert sorted(d.status for d in list_datasets(db)) == ["active", "active"]  # both kept, no winner


def test_command_line_ingest_reports_overlap(src, roots, tmp_path, capsys):
    cfg = tmp_path / "qmap.local.toml"
    cfg.write_text(f'[paths]\ndata_root = "{roots["data"].as_posix()}"\noutput_root = "{roots["output"].as_posix()}"\n')
    p1, p2 = tmp_path / "p1.toml", tmp_path / "p2.toml"
    p1.write_text(profile_text(profile_id="cli_a"))
    p2.write_text(profile_text(profile_id="cli_b"))
    rows = daily_rows(8)
    f1 = write_delimited(src / "a.csv", HEADER, rows)
    changed = [list(r) for r in rows]
    changed[1][4] = round(changed[1][4] * 1.002, 2)
    changed[1][2] = max(changed[1][2], changed[1][4])
    f2 = write_delimited(src / "b.csv", HEADER, changed)
    assert cli_main(["--config", str(cfg), "ingest", "--profile", str(p1), str(f1)]) == 0
    capsys.readouterr()
    assert cli_main(["--config", str(cfg), "ingest", "--profile", str(p2), str(f2)]) == 0
    out = capsys.readouterr().out
    assert "overlap: dataset" in out and "differ from dataset" in out and "Overlap report:" in out
