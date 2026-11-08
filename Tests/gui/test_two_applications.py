"""Real-window tests: Database Manager and Analytical Workbench are separate applications on one shared Data Registry."""

from __future__ import annotations

import csv
import os
import subprocess
import sys

import pytest

from gui.conftest import REPO, repo_snapshot


def _prepare(world):
    """Load world.good with the example dd-mm-yy profile through the Foundation (as Database Manager would)."""
    from qmap.core.runs import run_context
    from qmap.data_engine.ingest import ingest_file
    from qmap.storage.db import open_database
    from qmap_gui.services import build_core_settings, list_profiles

    settings = build_core_settings(str(world.data), str(world.output), REPO)
    profile = next(p.profile for p in list_profiles(settings) if p.profile and p.profile.profile_id == "csv_hdr_ddmmyy_idfromname")
    db = open_database(settings.db_path)
    try:
        with run_context(settings, db, "FOUND", area="Ingestion") as run:
            res = ingest_file(run, world.good, profile)
        assert res.outcome == "accepted", res.message
        return res.dataset_ids[0]
    finally:
        db.close()


def _select(tree_frame, dataset_id):
    item = next(i for i, d in tree_frame.rows.items() if d == dataset_id)
    tree_frame.tree.selection_set(item)
    tree_frame.on_select() if hasattr(tree_frame, "on_select") else tree_frame._selection_changed()


# ---- entry points -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("entry", ["database_manager.py", "analytical_workbench.py", "Q-MAP.py"])
def test_each_entry_point_opens_its_own_window_and_closes_cleanly(gui, world, entry):
    done = subprocess.run([sys.executable, str(REPO / entry), "--selftest", "--settings-dir", str(world.settings)],
                          capture_output=True, text=True, timeout=120, env=dict(os.environ), cwd=world.src)
    assert done.returncode == 0, done.stderr
    assert "SELFTEST OK" in done.stdout


def test_both_applications_can_be_open_at_the_same_time_and_share_folders(gui, world):
    dbm = gui.start(app_key="database_manager")
    gui.choose_folders(dbm)
    awb = gui.start(app_key="analytical_workbench")  # remembered folders are shared
    assert awb.core_settings is not None and awb.core_settings.data_root == dbm.core_settings.data_root
    assert "Database Manager" in dbm.title() and "Analytical Workbench" in awb.title()
    assert set(dbm.screens) == {"home", "sources", "data", "datasets"} and set(awb.screens) == {"home", "analysis"}
    assert "data" not in awb.screens  # the Workbench has no import screen


def test_remembering_in_one_application_keeps_the_others_choice(gui, world):
    dbm = gui.start(app_key="database_manager")
    awb = gui.start(app_key="analytical_workbench")
    gui.choose_folders(awb)  # the Workbench chooses the folders
    dbm.remember(last_profile="something")  # the older Database Manager window saves an unrelated choice
    import json

    saved = json.loads((world.settings / "gui_settings.json").read_text())
    assert saved["data_root"] == str(world.data) and saved["last_profile"] == "something"


# ---- Database Manager: Datasets and Storage ---------------------------------------------------------------------
def test_datasets_screen_lists_and_explains_a_prepared_dataset(gui, world):
    dataset_id = _prepare(world)
    app = gui.start()
    gui.choose_folders(app)
    app.show("datasets")
    ds = app.screens["datasets"]
    assert list(ds.rows.values()) == [dataset_id]
    _select(ds, dataset_id)
    text = ds.details.get()
    assert "NSE:NIFTY" in text and "Permanent" in text and "NSE_NIFTY_1D1.csv" in text and "Lineage" in text
    assert "[1 selected of 1]" in ds.count_label.cget("text")


def test_move_to_temporary_derive_and_delete_from_the_screen(gui, world):
    dataset_id = _prepare(world)
    before = repo_snapshot()
    app = gui.start()
    gui.choose_folders(app)
    app.show("datasets")
    ds = app.screens["datasets"]
    _select(ds, dataset_id)
    ds.reason_var.set("exploration")
    ds.storage_action("temporary")
    gui.wait(lambda: not ds.running and "done" in ds.final_label.cget("text"))
    assert "All 1 done" in ds.final_label.cget("text")
    assert any("MOVE TO TEMPORARY" in m[2] for m in gui.dialogs.messages if m[0] == "yes_no")
    assert "Temporary" in ds.tree.item(ds.tree.get_children()[0])["values"]
    assert (world.data / "Temporary" / "Cleaned_Data").is_dir()  # Blueprint v1.2 folder (OD-8)
    assert not (world.data / "Temporary_Data").exists()

    _select(ds, dataset_id)
    ds.derive_vars["1M"].set(True)  # weekly is ticked by default
    ds.derive_action()
    gui.wait(lambda: not ds.running and "done" in ds.final_label.cget("text"))
    assert len(ds.rows) == 3  # daily + weekly + monthly

    # the daily dataset now has dependents: deleting it is refused with the reason, nothing happens
    _select(ds, dataset_id)
    gui.dialogs.messages.clear()
    ds.storage_action("delete")
    assert gui.dialogs.messages[0][0] == "warn" and "built from this one" in gui.dialogs.messages[0][2]
    assert repo_snapshot() == before  # nothing written into the program folder


def test_raw_and_permanent_rules_are_explained_not_executed(gui, world):
    dataset_id = _prepare(world)
    app = gui.start()
    gui.choose_folders(app)
    app.show("datasets")
    ds = app.screens["datasets"]
    _select(ds, dataset_id)
    ds.storage_action("delete")  # still Permanent
    assert gui.dialogs.messages[-1][0] == "warn" and "Only Temporary" in gui.dialogs.messages[-1][2]
    ds.storage_action("permanent")  # already Permanent
    assert "already Permanent" in gui.dialogs.messages[-1][2]
    assert not ds.running


def test_datasets_screen_without_folders_says_what_to_do(gui):
    app = gui.start()
    app.show("datasets")
    ds = app.screens["datasets"]
    assert "Home screen" in ds.hint.cget("text")
    assert str(ds.temp_button.cget("state")) == "disabled"


# ---- Analytical Workbench ---------------------------------------------------------------------------------------
def test_workbench_without_prepared_data_points_to_database_manager(gui, world):
    app = gui.start(app_key="analytical_workbench")
    gui.choose_folders(app)
    app.show("analysis")
    an = app.screens["analysis"]
    assert not an.rows
    assert "database_manager.py" in an.empty_note.cget("text")
    assert str(an.run_button.cget("state")) == "disabled"


def test_workbench_checks_readiness_runs_and_saves_results(gui, world):
    dataset_id = _prepare(world)
    app = gui.start(app_key="analytical_workbench")
    gui.choose_folders(app)
    app.show("analysis")
    an = app.screens["analysis"]
    assert an.choice.analysis_id == "dataset_summary"
    _select(an, dataset_id)
    an.check()
    assert an.last_readiness.ready and an.readiness_box.get().startswith("READY")
    an.start_run()
    gui.wait(lambda: not an.running and an.last_result is not None, timeout=60)
    res = an.last_result
    assert res.ok, res.message
    assert res.run_dir.parent == world.output / "Research_Reports"
    assert res.run_id in an.run_id_var.get() and "Completed" in an.final_label.cget("text")
    with open(res.outputs[0], newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["Instrument"] == "NSE:NIFTY" and int(rows[0]["Bars"]) == 12
    assert res.metadata_path.exists()


def test_workbench_blocks_an_unreliable_run_and_explains_why(gui, world):
    dataset_id = _prepare(world)
    app = gui.start(app_key="analytical_workbench")
    gui.choose_folders(app)
    app.show("analysis")
    an = app.screens["analysis"]
    _select(an, dataset_id)
    an.param_vars["date_from"].set("01-Jan-35")  # no data in that period
    an.start_run()
    assert not an.running and an.last_result is None
    assert "Not started" in an.final_label.cget("text")
    # Requirement 2.4 (enhancement, 01-Nov-26): a valid period with no bars is reported as such, not as a generic
    # "not ready" and never as a date error
    assert "NO DATA IN THIS PERIOD" in an.readiness_box.get() and "Database Manager" in an.readiness_box.get()
    assert "no bars between" in an.final_label.cget("text") or "no bars in the chosen period" in an.final_label.cget("text")
    assert not (world.output / "Research_Reports").exists() or not any((world.output / "Research_Reports").iterdir())


def test_data_moved_in_database_manager_is_seen_by_the_workbench(gui, world):
    dataset_id = _prepare(world)
    dbm = gui.start()
    gui.choose_folders(dbm)
    dbm.show("datasets")
    ds = dbm.screens["datasets"]
    _select(ds, dataset_id)
    ds.storage_action("temporary")
    gui.wait(lambda: not ds.running and "done" in ds.final_label.cget("text"), app=dbm)
    awb = gui.start(app_key="analytical_workbench")
    awb.show("analysis")
    an = awb.screens["analysis"]
    assert an.tree.item(an.tree.get_children()[0])["values"][7] == "Temporary"
    _select(an, dataset_id)
    an.check()
    assert an.last_readiness.ready and "Temporary dataset" in an.readiness_box.get()


def test_a_late_selection_event_does_not_wipe_the_readiness_result(gui, world):
    """Found in practical acceptance: Tk delivers <<TreeviewSelect>> after the click is processed; an event for an
    unchanged selection must not clear a readiness result that is already shown."""
    dataset_id = _prepare(world)
    app = gui.start(app_key="analytical_workbench")
    gui.choose_folders(app)
    app.show("analysis")
    an = app.screens["analysis"]
    item = next(i for i, d in an.rows.items() if d == dataset_id)
    an.tree.selection_set(item)  # the event is still queued
    an.param_vars["date_from"].set("01-Jan-35")
    an.start_run()
    gui.pump(0.3)  # now the queued selection event arrives
    assert "NO DATA IN THIS PERIOD" in an.readiness_box.get() and an.last_readiness is not None
    # Refresh DOES ask for a new check on purpose: the data may have changed in Database Manager meanwhile.
    an.refresh()
    gui.pump(0.3)
    assert an.last_readiness is None and "Check readiness" in an.readiness_box.get()


def test_every_window_variable_belongs_to_its_own_window(gui, world):
    """Found in practical acceptance: with both applications in one process, a Tk variable created without its owner
    attached itself to the FIRST window, so the second window showed empty labels."""
    dbm = gui.start()
    gui.choose_folders(dbm)
    awb = gui.start(app_key="analytical_workbench")
    an = awb.screens["analysis"]
    assert awb.data_var._tk is awb.tk and an.output_var._tk is awb.tk and an.stage_var._tk is awb.tk
    assert "Research_Reports" in an.output_var.get()
    label_texts = [w.cget("text") for w in an.winfo_children()[1].winfo_children() if isinstance(w, __import__("tkinter").Label)]
    assert any("Research_Reports" in t for t in label_texts)
