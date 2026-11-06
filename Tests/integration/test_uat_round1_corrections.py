"""Corrections after the first Windows UAT round (06-Nov-26), owner-approved display corrections only.

O1: the Sources file detail shows the quality warnings recorded for the file's dataset, in plain English, with the
    same wording as Datasets and Storage (W2, W14-W18). Nothing is recalculated.
O3/O4: a file skipped because it is unchanged is shown, reported and counted as unchanged, never again as imported;
    a restored dataset is described as available again, not as imported (W7, A4).
W5: the duplicate left by an alias correction is removed from analyses by the existing reversible rejection; nothing is
    deleted, earlier research runs keep their record, Restore undoes it, the canonical dataset stays available.
Isolated synthetic data only (pytest temporary folders).
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.analytical_engine import DATASET_SUMMARY
from qmap.analytical_engine.base import run_analysis
from qmap.catalog import get_dataset
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap_gui import registry_services as rs
from qmap_gui import source_services as ss
from qmap_gui import workbench_services as ws
from qmap_gui.messages import describe_warning, warning_lines

PATTERNS = Path(__file__).resolve().parents[2] / "docs" / "acceptance_testing" / "dq7_pattern_files_03_Nov_26"


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    f.mkdir()
    return f


def scan(settings, db, source):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, source.source_id)


def daily(path, n=30, seed=1, start=date(2025, 1, 6)):
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(n, start), ohlcv(n, seed))]
    return write_delimited(path, HEADER, rows)


def detail_text(settings, db, source, rel):
    state = next(s for s in D.file_states(db, source.source_id) if s.relative_path == rel)
    decisions = ss.dataset_decisions(settings, state.dataset_ids)
    warnings = ss.dataset_warnings(settings, state.dataset_ids)
    return "".join(t for t, _ in ss.file_details(state, decisions, warnings)), state


# ---- O1: warning descriptions ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("recorded, title", [
    ("conflicting_observations: 2 timestamp(s) with different values", "Some dates/times have more than one different value"),
    ("partial_session: Sessions with fewer bars than the usual 65", "Some days have fewer bars than usual"),
    ("interval_change_uncertain: rows 10-20 cannot show whether", "Part of the file may have another bar interval"),
    ("interval_change_detected: rows 10-20 have 3-minute steps", "Part of the file has another bar interval"),
])
def test_recorded_warnings_get_their_plain_english_title_and_keep_their_detail(recorded, title):
    got_title, detail, name = describe_warning(recorded)
    assert got_title == title and detail == recorded.split(": ", 1)[1] and recorded.startswith(name + ": ")
    assert warning_lines([recorded]) == [f"{title} ({name}): {detail}"]


def test_an_unknown_or_plain_warning_is_shown_unchanged():
    assert describe_warning("Something unusual happened") == ("Something unusual happened", "", "")
    assert describe_warning("partial_session") == ("Some days have fewer bars than usual", "", "partial_session")


def test_w2_conflicting_observations_appear_in_the_sources_detail(settings, db, folder):
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(30, date(2025, 1, 6)), ohlcv(30))]
    clash = list(rows[5])
    clash[4] = round(clash[4] * 1.001, 2)  # same date, a different close: a conflicting observation (DQ-10)
    clash[2] = max(clash[2], clash[4])
    write_delimited(folder / "NSE_CLASH.csv", HEADER, rows[:6] + [clash] + rows[6:])
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata")
    scan(settings, db, src)
    text, state = detail_text(settings, db, src, "NSE_CLASH.csv")
    assert "Quality warnings recorded for dataset" in text
    assert "WARNING: Some dates/times have more than one different value" in text
    # the same warning, with the same title, in Datasets and Storage (the screens cannot disagree)
    ds_text = "".join(t for t, _ in rs.details(settings, state.dataset_ids[0]))
    assert "Some dates/times have more than one different value (conflicting_observations)" in ds_text


def test_w14_to_w18_pattern_files_show_their_warnings_in_the_sources_detail(settings, db, tmp_path):
    folder = tmp_path / "patterns"
    folder.mkdir()
    for p in PATTERNS.glob("*.csv"):
        shutil.copy2(p, folder / p.name)
    src = D.add_folder_source(settings, db, folder)
    scan(settings, db, src)
    may, has = "Part of the file may have another bar interval", "Part of the file has another bar interval"
    expected = {  # file -> (interval title expected or None, partial-session note expected)
        "NSE_RANDOMGAPS.csv": (None, True), "NSE_EVERYOTHER.csv": (may, None), "NSE_GENUINE3M.csv": (has, None),
        "NSE_DAILY0000.csv": (has, None), "NSE_DAILY0915.csv": (may, None), "NSE_SPARSE.csv": (None, True)}
    for name, (interval, partial) in expected.items():
        text, _ = detail_text(settings, db, src, name)
        for title in (may, has):
            assert (f"WARNING: {title}" in text) == (title == interval), (name, text)
        if partial:
            assert "WARNING: Some days have fewer bars than usual" in text, (name, text)
    assert "cannot show whether" in detail_text(settings, db, src, "NSE_EVERYOTHER.csv")[0]
    assert "a time the intraday bars also use" in detail_text(settings, db, src, "NSE_DAILY0915.csv")[0]
    assert "outside the times of the intraday bars" in detail_text(settings, db, src, "NSE_DAILY0000.csv")[0]


def test_warnings_stay_visible_for_an_unchanged_skipped_file(settings, db, tmp_path):
    folder = tmp_path / "p"
    folder.mkdir()
    shutil.copy2(PATTERNS / "NSE_EVERYOTHER.csv", folder / "NSE_EVERYOTHER.csv")
    src = D.add_folder_source(settings, db, folder)
    scan(settings, db, src)
    scan(settings, db, src)  # unchanged: skipped
    text, state = detail_text(settings, db, src, "NSE_EVERYOTHER.csv")
    assert state.action == "skipped" and "WARNING: Part of the file may have another bar interval" in text


# ---- O3/O4: scan results describe this scan ------------------------------------------------------------------------

def test_scan_results_describe_only_what_this_scan_did(settings, db, folder):
    daily(folder / "NSE_AAA.csv")
    src = D.add_folder_source(settings, db, folder)
    r1 = scan(settings, db, src)  # 1. first scan imports the file
    assert r1.counts == {"imported": 1}
    r2 = scan(settings, db, src)  # 2./3. second scan: unchanged, zero new imports
    assert r2.counts == {"unchanged_loaded": 1} and "imported" not in r2.counts  # 4. not counted again
    assert r2.files[0][1:4] == ("unchanged", "skipped", "unchanged_loaded")
    assert "1 unchanged (imported earlier)" in r2.summary() and " imported," not in r2.summary() + ","
    state = D.file_states(db, src.source_id)[0]
    assert state.outcome == "imported"  # the registry still records the earlier import, unchanged
    assert state.outcome_label == "Unchanged (imported earlier)" and ss.file_row(state)[1] == "Unchanged (imported earlier)"
    assert ss.counts_text([state]) == "1 unchanged (imported earlier)"
    report = r2.report_path.read_text(encoding="utf-8")
    assert "NSE_AAA.csv,unchanged,skipped,Unchanged (imported earlier)" in report
    daily(folder / "NSE_BBB.csv", seed=2)  # 5. a genuinely new file is still counted as imported
    daily(folder / "NSE_AAA.csv", seed=3)  # and a changed file is processed again
    r3 = scan(settings, db, src)
    assert r3.counts == {"imported": 2}, r3.counts


def test_a_restored_dataset_is_described_as_available_again_not_imported(settings, db, folder):
    daily(folder / "NSE_AAA.csv")
    src = D.add_folder_source(settings, db, folder)
    scan(settings, db, src)
    state = D.file_states(db, src.source_id)[0]
    ss.reject_files(settings, [state], "test")
    assert ss.file_row(state, ss.dataset_decisions(settings, state.dataset_ids))[1] == "Rejected by you"
    ss.restore_files(settings, [state], "test")
    decisions = ss.dataset_decisions(settings, state.dataset_ids)
    assert ss.file_row(state, decisions)[1] == "Available again (restored by you)"  # 6.
    text = "".join(t for t, _ in ss.file_details(state, decisions))
    assert "Available again (restored by you); nothing was imported again" in text
    assert db.one("SELECT COUNT(*) FROM datasets WHERE layer = 'cleaned'")[0] == 1  # nothing imported again


# ---- W5: the duplicate left by an alias correction -----------------------------------------------------------------

def test_w5_duplicate_is_removed_from_analyses_by_reversible_rejection(settings, db, folder):
    daily(folder / "RELIANCE_EQ.csv", n=40)
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata")
    scan(settings, db, src)
    old = D.file_states(db, src.source_id)[0].dataset_ids[0]
    assert get_dataset(db, old).instrument == "NSE:RELIANCE_EQ"
    # an analysis run on the old dataset before the correction
    run = run_analysis(settings, db, DATASET_SUMMARY, [old], {})
    assert run.outcome == "completed"
    ss.add_to_alias_registry(settings, "RELIANCE", ["RELIANCE EQ"])
    scan(settings, db, src)
    new = D.file_states(db, src.source_id)[0].dataset_ids[0]
    a, b = get_dataset(db, old), get_dataset(db, new)
    assert b.instrument == "NSE:RELIANCE" and new != old
    # the identity check the manual asks for: same original file, bars, dates and timeframe
    assert (a.source_files, a.row_count, a.date_from, a.date_to, a.timeframe) == \
           (b.source_files, b.row_count, b.date_from, b.date_to, b.timeframe)
    offered = lambda: {d.dataset_id for d in ws.ready_datasets(settings)}  # noqa: E731 - the Workbench list
    assert offered() == {old, new}  # the first-round observation O2
    stored = settings.data_path(a.relative_path)
    res = rs.record_decision(settings, [old], "reject", "duplicate after alias correction (W5)")
    assert res.changed == [old]
    assert offered() == {new}  # removed from the Workbench; the canonical dataset stays
    assert stored.is_file() and get_dataset(db, old) is not None  # nothing deleted
    assert db.one("SELECT COUNT(*) FROM run_inputs WHERE run_id = ? AND dataset_id = ?", (run.run_id, old))[0] == 1
    assert run.run_dir.is_dir()  # the earlier research run and its record are untouched
    rs.record_decision(settings, [old], "restore", "undo")
    assert offered() == {old, new}  # reversible
