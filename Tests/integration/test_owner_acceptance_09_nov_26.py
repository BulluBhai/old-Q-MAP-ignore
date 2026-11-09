"""Owner acceptance findings of 09-Nov-26 on PR #10 (Windows/IDLE, guide v2 of 08-Nov-26).

W08: with Include sub-folders off, a folder whose files are all in sub-folders scanned as "no supported files found"
     with nothing saying why, and the scan report did not record the setting. With it on, every file is found.
W14-W18: the whole-file checks (partial_session, interval_change_*) were recorded on each dataset but never shown in
     the Sources file details on PR #10's line. The details now carry them with PR #12's round-1 wording (finding O1),
     plus a "none" line when a dataset has no recorded warning. Detection itself is
     unchanged and is checked here against the same six synthetic files the owner scanned.
Also the folder-setting comparison behind the "settings not saved" question and the Add folder start location."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

from fixtures.builders import HEADER, daily_rows, write_delimited
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap_gui import source_services as ss

PATTERNS = Path(__file__).resolve().parents[2] / "docs" / "acceptance_testing" / "dq7_pattern_files_03_Nov_26"


def _stop_folder(tmp_path) -> Path:
    """Like the owner's W_Stop: no files at the top, three sub-folders with files."""
    root = tmp_path / "W_Stop"
    for i, sub in enumerate(("Batch_A", "Batch_B", "Batch_C")):
        (root / sub).mkdir(parents=True)
        for j in range(3):
            write_delimited(root / sub / f"NSE_S{i}{j}.csv", HEADER, daily_rows(12, seed=10 * i + j + 1))
    return root


def _scan(settings, db, sid):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, sid), run.dir


def _header(report: Path) -> list[str]:
    with open(report, newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh))


def test_w08_subfolders_off_says_why_nothing_was_found_and_the_report_records_it(settings, db, tmp_path):
    src = D.add_folder_source(settings, db, _stop_folder(tmp_path))
    res, run_dir = _scan(settings, db, src.source_id)
    assert res.counts == {} and res.subfolders_not_scanned == 3
    assert res.summary() == ("no supported files found (3 sub-folder(s) not scanned: Include sub-folders is off for "
                             "this folder)")
    head = _header(res.report_path)
    assert head[:6] == ["Source", "W_Stop", "Folder", str(src.location), "Scan", "complete"]
    assert head[6:] == ["Sub-folders", "not included (3 not scanned)", "Skip patterns", "none"]
    log = (run_dir / "run_log.txt").read_text(encoding="utf-8")
    assert "sub-folders not included" in log and "3 sub-folder(s) of 'W_Stop' not scanned (Batch_A, Batch_B, Batch_C)" in log


def test_w08_subfolders_on_finds_every_file_recursively_and_the_report_records_it(settings, db, tmp_path):
    root = _stop_folder(tmp_path)
    (root / "Batch_A" / "deeper").mkdir()
    write_delimited(root / "Batch_A" / "deeper" / "NSE_DEEP.csv", HEADER, daily_rows(12, seed=99))
    src = D.add_folder_source(settings, db, root, include_subfolders=True, exclude_patterns=["*S22*"])
    res, run_dir = _scan(settings, db, src.source_id)
    assert res.counts == {"imported": 9} and res.excluded == 1 and res.subfolders_not_scanned == 0
    assert {r for r, *_ in res.files} == {f"Batch_{c}/NSE_S{i}{j}.csv" for i, c in enumerate("ABC") for j in range(3)
                                          if (i, j) != (2, 2)} | {"Batch_A/deeper/NSE_DEEP.csv"}
    assert "not scanned" not in res.summary()
    assert _header(res.report_path)[6:] == ["Sub-folders", "included", "Skip patterns", "*S22*"]
    assert "sub-folders included; skip patterns: *S22*" in (run_dir / "run_log.txt").read_text(encoding="utf-8")


def test_w08_turning_subfolders_off_again_keeps_child_folders_out(settings, db, tmp_path):
    src = D.add_folder_source(settings, db, _stop_folder(tmp_path), include_subfolders=True)
    assert _scan(settings, db, src.source_id)[0].counts == {"imported": 9}
    D.update_folder_source(db, src.source_id, include_subfolders=False)
    res = _scan(settings, db, src.source_id)[0]
    assert res.counts == {"missing": 9} and res.subfolders_not_scanned == 3  # earlier data kept, never deleted


def test_unsaved_changes_compares_the_screen_with_the_saved_settings(settings, db, tmp_path):
    src = D.add_folder_source(settings, db, _stop_folder(tmp_path), market_timezone="Asia/Kolkata",
                              default_exchange="NSE")
    same = {"include_subfolders": False, "exclude_patterns": [], "market_timezone": " Asia/Kolkata ",
            "default_exchange": "nse", "symbol_from_filename": True}
    assert ss.unsaved_changes(src, same) == []
    assert ss.unsaved_changes(src, dict(same, include_subfolders=True)) == [("Include sub-folders", "on", "off")]
    changed = dict(same, exclude_patterns=["old/*"], symbol_from_filename=False)
    assert [c[0] for c in ss.unsaved_changes(src, changed)] == ["Skip files matching",
                                                                "Identify the instrument from the file name"]


def test_add_folder_start_location_falls_back_sensibly(tmp_path):
    app_dir, last = tmp_path / "Q-MAP_APP", tmp_path / "PR10_Test" / "W_Market"
    app_dir.mkdir()
    last.mkdir(parents=True)
    assert ss.first_existing_folder("", str(app_dir)) == str(app_dir)  # first use: the application folder
    assert ss.first_existing_folder(str(last), str(app_dir)) == str(last)  # then the folder chosen last
    shutil.rmtree(last)
    assert ss.first_existing_folder(str(last), str(app_dir)) == str(tmp_path / "PR10_Test")  # nearest existing parent
    assert ss.first_existing_folder("", "") == str(Path.home())


# W14-W18: the owner's checklist strings, read from the Sources file details (text the window shows)
EXPECT = {
    "NSE_RANDOMGAPS.csv": (["WARNING: Some days have fewer bars than usual"], ["bar interval"]),
    "NSE_EVERYOTHER.csv": (["WARNING: Part of the file may have another bar interval", "cannot show whether",
                            "Detected timeframe: 5 minutes"], ["has another bar interval"]),
    "NSE_GENUINE3M.csv": (["WARNING: Part of the file has another bar interval", "3 minute(s)"],
                          ["may have another bar interval"]),
    "NSE_DAILY0000.csv": (["WARNING: Part of the file has another bar interval", "outside the times of the intraday bars"],
                          ["may have another bar interval", "fewer bars than usual"]),
    "NSE_DAILY0915.csv": (["WARNING: Part of the file may have another bar interval",
                           "a time the intraday bars also use"], ["has another bar interval", "fewer bars than usual"]),
    "NSE_SPARSE.csv": (["WARNING: Some days have fewer bars than usual"], ["bar interval"]),
}


def test_w14_to_w18_the_file_details_show_the_whole_file_checks(settings, db, tmp_path):
    folder = tmp_path / "W_Pattern"
    folder.mkdir()
    for name in EXPECT:
        shutil.copy2(PATTERNS / name, folder / name)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    src = D.add_folder_source(settings, db, folder)
    assert _scan(settings, db, src.source_id)[0].counts == {"imported": 6}
    states = {s.relative_path: s for s in ss.files(settings, src.source_id)}
    warnings = ss.dataset_warnings(settings, [i for s in states.values() for i in s.dataset_ids])
    for name, (present, absent) in EXPECT.items():
        text = "".join(t for t, _ in ss.file_details(states[name], {}, warnings))
        assert "Detected timeframe: 5 minutes" in text and f"Quality warnings recorded for dataset {states[name].dataset_ids[0]}:\n" in text, name
        for p in present:
            assert p in text, (name, p, text)
        for a in absent:
            assert a not in text, (name, a, text)
        assert "interval_change" not in text and "partial_session" not in text, name  # no technical codes shown
    # without the recorded checks (older callers) the details are as before: nothing is invented
    plain = "".join(t for t, _ in ss.file_details(states["NSE_SPARSE.csv"]))
    assert "fewer bars" not in plain and "Quality warnings recorded" not in plain
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before  # source files only read


def test_a_file_with_no_warnings_says_so(settings, db, tmp_path):
    folder = tmp_path / "clean"
    folder.mkdir()
    write_delimited(folder / "NSE_CLEAN.csv", HEADER, daily_rows(30, seed=3))
    src = D.add_folder_source(settings, db, folder)
    _scan(settings, db, src.source_id)
    st = ss.files(settings, src.source_id)[0]
    w = ss.dataset_warnings(settings, st.dataset_ids)
    text = "".join(t for t, _ in ss.file_details(st, {}, w))
    assert w == {st.dataset_ids[0]: []}
    assert f"Quality warnings recorded for dataset {st.dataset_ids[0]}: none" in text and "WARNING:" not in text

