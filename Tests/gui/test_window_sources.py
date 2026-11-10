"""Real-window tests: Database Manager Sources screen (Blueprint v1.3 §8.5.8): add a folder, scan, answer a question,
scan again, and see the dataset in both applications. Source files must be unchanged afterwards."""

from __future__ import annotations

import hashlib

from fixtures.builders import HEADER, daily_rows, write_delimited


def _sha(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}


def _files(frame):
    return {s.relative_path: s for s in frame.file_rows.values()}


def ss_latest_answer(world, rel):
    from qmap.storage.db import open_database

    db = open_database(world.data / "Metadata" / "qmap_metadata.sqlite")
    try:
        return db.one("SELECT * FROM source_answers WHERE relative_path = ?", (rel,))
    finally:
        db.close()


def test_add_scan_answer_and_load_from_the_sources_screen(gui, world, tmp_path):
    market = tmp_path / "market_files"
    market.mkdir()
    write_delimited(market / "NSE_ABC.csv", HEADER, daily_rows(15))
    write_delimited(market / "prices.csv", HEADER, daily_rows(15, seed=4))
    before = _sha(market)

    app = gui.start()
    gui.choose_folders(app)
    app.screens["home"].module_rows["sources"]["button"].invoke()
    assert app.current == "sources"
    frame = app.screens["sources"]
    assert str(frame.scan_button.cget("state")) == "disabled"  # nothing to scan yet

    gui.dialogs.directories.append(str(market))
    frame.tz_var.set("Asia/Kolkata")
    frame.exch_var.set("NSE")
    frame.symname_var.set(False)  # the question-and-answer path (file-name identification switched off)
    frame.add_button.invoke()
    assert len(frame.source_rows) == 1 and frame.selected_source() is not None
    assert str(frame.scan_button.cget("state")) == "normal"

    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    assert frame.stage_var.get() == "Finished" and float(frame.progress["value"]) == 100  # a finished scan: full bar
    files = _files(frame)
    assert files["NSE_ABC.csv"].outcome == "imported"
    assert files["prices.csv"].outcome == "needs_answer"
    assert "need attention" in frame.final_label.cget("text")

    item = next(i for i, s in frame.file_rows.items() if s.relative_path == "prices.csv")
    frame.files_tree.selection_set(item)
    frame.on_file_select()
    assert str(frame.ans_sym_entry.cget("state")) == "normal"
    assert str(frame.ans_date_box.cget("state")) == "disabled"  # only the boxes the question needs
    # PR #9 finding F-01: the folder's default exchange and the file name's symbol are filled in as a suggestion only
    assert (frame.ans_exch.get(), frame.ans_sym.get()) == ("NSE", "PRICES")
    assert ss_latest_answer(world, "prices.csv") is None  # nothing is recorded until Save answer
    frame.ans_exch.set("")
    frame.ans_sym.set("")
    frame.answer_button.invoke()
    assert gui.dialogs.messages[-1][0] == "warn"  # boxes emptied: asked for the missing answer, nothing saved
    frame.ans_exch.set("NSE")
    frame.ans_sym.set("PRC")
    frame.answer_button.invoke()
    assert "Answer recorded" in frame.final_label.cget("text")

    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    files = _files(frame)
    assert files["prices.csv"].outcome == "imported" and files["NSE_ABC.csv"].change == "unchanged"
    assert frame.last_report is not None and frame.last_report.is_file()
    assert _sha(market) == before  # the source folder was only read

    datasets = app.screens["datasets"]
    app.show("datasets")
    assert {datasets.tree.item(i, "values")[1] for i in datasets.tree.get_children()} == {"NSE:ABC", "NSE:PRC"}


def test_the_sources_screen_refuses_q_map_own_folders(gui, world):
    app = gui.start()
    gui.choose_folders(app)
    frame = app.screens["sources"]
    gui.dialogs.directories.append(str(world.data))
    frame.add_button.invoke()
    assert gui.dialogs.messages[-1][0] == "error" and not frame.source_rows


def test_stop_using_a_folder_keeps_its_files_and_data(gui, world, tmp_path):
    market = tmp_path / "m"
    market.mkdir()
    write_delimited(market / "NSE_ABC.csv", HEADER, daily_rows(10))
    app = gui.start()
    gui.choose_folders(app)
    frame = app.screens["sources"]
    gui.dialogs.directories.append(str(market))
    frame.add_button.invoke()
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    frame.remove_button.invoke()
    assert not frame.source_rows and (market / "NSE_ABC.csv").is_file()
    app.show("datasets")
    assert len(app.screens["datasets"].rows) == 1


def test_a_file_without_an_exchange_is_imported_under_nse_without_a_question(gui, world, tmp_path):
    """DQ-2 kept (the symbol column is the file's own information); DQ-8 (03-Nov-26): NSE is the default exchange, so
    nothing is asked and the file is imported."""
    market = tmp_path / "m"
    market.mkdir()
    rows = [[d[0], "INFY", *d[1:]] for d in daily_rows(10)]
    write_delimited(market / "prices.csv", ["date", "symbol", "open", "high", "low", "close", "volume"], rows)
    app = gui.start()
    gui.choose_folders(app)
    frame = app.screens["sources"]
    frame.exch_var.set("")
    assert frame.symname_var.get() is True  # file-name identification is ON for a new folder
    gui.dialogs.directories.append(str(market))
    frame.add_button.invoke()
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    assert next(s for s in frame.file_rows.values() if s.relative_path == "prices.csv").outcome == "imported"
    app.show("datasets")
    assert {app.screens["datasets"].tree.item(i, "values")[1] for i in app.screens["datasets"].tree.get_children()} \
        == {"NSE:INFY"}


# ---- P4 (owner instruction 03-Nov-26): default acceptance, review, reversible rejection, Stop -------------------------
def _scanned_frame(gui, tmp_path, names, rows=None):
    market = tmp_path / "p4"
    market.mkdir()
    for i, n in enumerate(names):
        write_delimited(market / n, HEADER, rows or daily_rows(10, seed=i + 1))
    app = gui.start()
    gui.choose_folders(app)
    frame = app.screens["sources"]
    gui.dialogs.directories.append(str(market))
    frame.add_button.invoke()
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    return app, frame, market


def _select(frame, *names):
    items = [i for i, s in frame.file_rows.items() if s.relative_path in names]
    frame.files_tree.selection_set(items)
    frame.on_file_select()


def test_files_are_accepted_by_default_and_the_detail_shows_timeframe_validation_and_status(gui, world, tmp_path):
    app, frame, _ = _scanned_frame(gui, tmp_path, ["RELIANCE (1).csv", "TCS - Copy.csv"])
    assert {s.outcome for s in frame.file_rows.values()} == {"imported"}  # no question, no confirmation window
    assert not [m for m in gui.dialogs.messages if m[0] in ("yes_no", "warn", "error")]
    _select(frame, "RELIANCE (1).csv")
    text = frame.details.get()
    assert "Detected timeframe: Daily" in text and "Validation: Consistent across" in text
    assert "Status: Accepted by default" in text and "Instrument: NSE:RELIANCE (provisional)" in text
    values = frame.files_tree.item(next(iter(frame.files_tree.selection())), "values")
    assert values[2] == "Daily" and values[3] == "NSE:RELIANCE (provisional)"
    groups = frame.exceptions_box.get()
    assert "Instrument not in the alias registry (provisional): 2 file(s)" in groups


def test_reject_and_restore_selected_files_in_bulk(gui, world, tmp_path):
    app, frame, _ = _scanned_frame(gui, tmp_path, ["AAA.csv", "BBB.csv", "CCC.csv"])
    _select(frame, "AAA.csv", "BBB.csv")
    assert str(frame.reject_button.cget("state")) == "normal"
    frame.reason_var.set("not needed")
    frame.reject_button.invoke()
    results = {s.relative_path: frame.files_tree.item(i, "values")[1] for i, s in frame.file_rows.items()}
    assert results == {"AAA.csv": "Rejected by you", "BBB.csv": "Rejected by you", "CCC.csv": "Imported"}
    assert "Rejected by you: 2 file(s)" in frame.exceptions_box.get()
    wb = gui.start(app_key="analytical_workbench")
    gui.choose_folders(wb)
    wb.show("analysis")
    assert len(wb.screens["analysis"].rows) == 1  # only CCC is offered to analyses
    _select(frame, "AAA.csv", "BBB.csv")
    frame.restore_button.invoke()
    # UAT 06-Nov-26 (O3): Restore re-offers the data; it does not import anything again, so the row says so
    results = {s.relative_path: frame.files_tree.item(i, "values")[1] for i, s in frame.file_rows.items()}
    assert results == {"AAA.csv": "Available again (restored by you)", "BBB.csv": "Available again (restored by you)",
                       "CCC.csv": "Imported"}


def test_bulk_correction_and_alias_registry_update(gui, world, tmp_path):
    app, frame, _ = _scanned_frame(gui, tmp_path, ["RIL.csv", "RELIANCE_EQ.csv"])
    _select(frame, "RIL.csv", "RELIANCE_EQ.csv")
    frame.alias_var.set("RELIANCE")
    frame.alias_button.invoke()
    from qmap.data_engine.instrument_names import registry_path
    from qmap_gui.services import build_core_settings

    reg = registry_path(build_core_settings(str(world.data), str(world.output), world.repo)).read_text(encoding="utf-8")
    row = next(line.split(",") for line in reg.splitlines() if line.startswith("RELIANCE,"))
    assert set(row[1:]) == {"RIL", "RELIANCE EQ"}
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    assert "Instrument not in the alias registry" not in frame.exceptions_box.get()
    _select(frame, "RIL.csv")
    frame.ans_exch.set("BSE")  # a correction of an imported file (exchange)
    frame.answer_button.invoke()
    assert "Correction recorded for 1 file(s)" in frame.final_label.cget("text")


def test_stop_scan_stops_safely_after_the_current_file(gui, world, tmp_path, monkeypatch):
    import time as _time

    from qmap.data_engine import discovery as D

    market = tmp_path / "slow"
    market.mkdir()
    for i in range(8):
        write_delimited(market / f"NSE_S{i}.csv", HEADER, daily_rows(10, seed=i + 1))
    real = D._scan_one

    def slow(*a, **k):
        _time.sleep(0.3)
        return real(*a, **k)

    monkeypatch.setattr(D, "_scan_one", slow)
    app = gui.start()
    gui.choose_folders(app)
    frame = app.screens["sources"]
    gui.dialogs.directories.append(str(market))
    frame.add_button.invoke()
    frame.scan_button.invoke()
    gui.wait(lambda: str(frame.stop_button.cget("state")) == "normal", timeout=10)
    gui.pump(0.4)
    frame.stop_button.invoke()
    gui.wait(lambda: not frame.running, timeout=30)
    assert "Stopped by you" in frame.final_label.cget("text") and "not processed" in frame.final_label.cget("text")
    assert frame.stage_var.get() == "Stopped (as you asked)" and float(frame.progress["value"]) < 100
    done = [s for s in frame.file_rows.values() if s.outcome == "imported"]
    assert 0 < len(done) < 8
    app.show("datasets")
    assert len(app.screens["datasets"].rows) == len(done)  # completed work kept, nothing half-written


def test_datasets_screen_reject_and_restore(gui, world, tmp_path):
    app, frame, _ = _scanned_frame(gui, tmp_path, ["NSE_ABC.csv"])
    app.show("datasets")
    ds = app.screens["datasets"]
    item = next(iter(ds.rows))
    ds.tree.selection_set(item)
    ds.on_select()
    ds.reject_button.invoke()
    assert ds.tree.item(next(iter(ds.rows)), "values")[-1] == "Rejected by you"
    ds.tree.selection_set(next(iter(ds.rows)))
    ds.on_select()
    ds.restore_button.invoke()
    assert ds.tree.item(next(iter(ds.rows)), "values")[-1] == "Active"


def test_the_detail_pane_shows_recorded_quality_warnings_and_a_rescan_shows_unchanged(gui, world, tmp_path):
    """UAT 06-Nov-26, O1 and O4, on the real window: a pattern file's recorded warning appears in plain English in the
    detail pane, and after a second scan the file is listed as unchanged, not imported again."""
    import shutil
    from pathlib import Path

    patterns = Path(__file__).resolve().parents[2] / "docs" / "acceptance_testing" / "dq7_pattern_files_03_Nov_26"
    market = tmp_path / "patterns"
    market.mkdir()
    shutil.copy2(patterns / "NSE_EVERYOTHER.csv", market / "NSE_EVERYOTHER.csv")
    app = gui.start()
    gui.choose_folders(app)
    frame = app.screens["sources"]
    gui.dialogs.directories.append(str(market))
    frame.add_button.invoke()
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    _select(frame, "NSE_EVERYOTHER.csv")
    text = frame.details.get()
    assert "WARNING: Part of the file may have another bar interval" in text and "cannot show whether" in text
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    row = next(frame.files_tree.item(i, "values") for i, s in frame.file_rows.items())
    assert row[1] == "Unchanged (imported earlier)"
    assert "1 unchanged (imported earlier)" in frame.files_count.cget("text")


def test_a_restored_file_shows_the_next_scans_result_on_the_window(gui, world, tmp_path):
    """UAT round 2 (R2-O2): "Available again (restored by you)" right after Restore; after the next scan the row shows
    that scan's result ("Unchanged (imported earlier)"). Display only."""
    app, frame, _ = _scanned_frame(gui, tmp_path, ["AAA.csv", "BBB.csv"])
    _select(frame, "AAA.csv")
    frame.reject_button.invoke()
    _select(frame, "AAA.csv")
    frame.restore_button.invoke()
    rows = {s.relative_path: frame.files_tree.item(i, "values")[1] for i, s in frame.file_rows.items()}
    assert rows == {"AAA.csv": "Available again (restored by you)", "BBB.csv": "Imported"}
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    rows = {s.relative_path: frame.files_tree.item(i, "values")[1] for i, s in frame.file_rows.items()}
    assert rows == {"AAA.csv": "Unchanged (imported earlier)", "BBB.csv": "Unchanged (imported earlier)"}
