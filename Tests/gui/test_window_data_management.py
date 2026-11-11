"""Real-window tests: the Data Management workflow end to end (select, preview, profile, check, load, results)."""

import re
import shutil
import threading
import time
from pathlib import Path

import pytest

from fixtures.builders import daily_rows, write_delimited
from gui.conftest import NET_HEADER, REPO, dd_mm_yy_rows, repo_snapshot
from qmap.storage.db import open_database
from qmap_gui import jobs, services

CLOCK = re.compile(r"^\d{2}-[A-Z][a-z]{2}-\d{2} \d{2}:\d{2}:\d{2}$")  # dd-mmm-yy hh:mm:ss


def tree_files(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


@pytest.fixture
def dm(gui, world):
    app = gui.start()
    gui.choose_folders(app)
    app.show("data")
    frame = app.screens["data"]
    frame.gui = gui
    return frame


def choose_profile(dm, profile_id):
    idx = next(i for i, p in enumerate(dm.profile_infos) if p.profile and p.profile.profile_id == profile_id)
    dm.select_profile_index(idx)


def run_and_wait(dm, action):
    action()
    dm.gui.wait(dm.finished_event.is_set)


def rows(dm):
    return [dm.tree.item(i)["values"] for i in dm.tree.get_children()]


# ---- the whole workflow ---------------------------------------------------------------------------------------
def test_end_to_end_select_preview_check_and_load(dm, world):
    before_repo = repo_snapshot()
    gui = dm.gui
    gui.dialogs.files.append([str(world.good), str(world.bad)])
    dm.add_files()
    assert dm.count_label.cget("text") == "[2 files selected]"
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    assert "Ready" in dm.hint.cget("text") and str(dm.run_button.cget("state")) == "normal"

    # preview: shows the file, saves nothing
    data_before, out_before = tree_files(world.data), tree_files(world.output)
    dm.listbox.selection_set(0)
    dm.preview_selected()
    gui.wait(lambda: "Detected format" in dm.preview_box.get())
    assert "WOULD BE ACCEPTED" in dm.preview_box.get()
    assert (tree_files(world.data), tree_files(world.output)) == (data_before, out_before)

    # check: validates, saves nothing, explains
    run_and_wait(dm, dm.check_files)
    assert [r[1] for r in rows(dm)] == ["Would be accepted", "Would be rejected"]
    assert (tree_files(world.data), tree_files(world.output)) == (data_before, out_before)
    dm.tree.selection_set(dm.tree.get_children()[1])
    gui.pump(0.1)
    text = dm.details.get()
    assert "Nothing was saved" in dm.final_label.cget("text")
    assert "PROBLEM" in text and "What to do" in text and "[E_" not in text

    # load: the Foundation does the work
    run_and_wait(dm, dm.start_ingest)
    assert [r[1] for r in rows(dm)] == ["Accepted", "Rejected - see problems"]
    assert dm.stage_var.get() == "Finished" and dm.files_var.get() == "2 / 2" and dm.rows_var.get() == "24"
    assert CLOCK.match(dm.started_var.get()), dm.started_var.get()
    assert float(dm.progress["value"]) == 100.0 and "1 accepted, 1 rejected" in dm.counts_var.get()
    assert "Open the problem report" in dm.final_label.cget("text")

    db = open_database(dm.app.core_settings.db_path)
    assert db.one("SELECT COUNT(*) c FROM datasets WHERE layer='raw'")["c"] == 2
    assert db.one("SELECT COUNT(*) c FROM datasets WHERE layer='cleaned'")["c"] == 1
    assert db.one("SELECT COUNT(*) c FROM ingest_attempts WHERE outcome='rejected'")["c"] == 1  # audit trail kept
    db.close()

    # report locations: the run folder and the problem report are real files, outside the repository
    run_dir = dm.last_run_dir
    assert run_dir.is_dir() and world.output.resolve() in run_dir.parents and (run_dir / "run_manifest.json").is_file()
    dm.tree.selection_set(dm.tree.get_children()[1])
    gui.pump(0.1)
    report = dm.report_var.get()
    assert report.endswith(".csv") and Path(report).is_file() and world.output.resolve() in Path(report).resolve().parents
    assert "problem" in dm.details.get().lower()
    assert repo_snapshot() == before_repo  # nothing generated inside the code repository


def test_the_open_buttons_use_the_systems_file_manager(dm, world, monkeypatch):
    opened = []
    monkeypatch.setattr(services, "open_in_file_manager", lambda p: (opened.append(p), (True, "Opened."))[1])
    dm.add_paths([world.good, world.bad])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.start_ingest)
    dm.open_run_button.invoke()
    assert opened[-1] == dm.last_run_dir
    dm.tree.selection_set(dm.tree.get_children()[1])
    dm.gui.pump(0.1)
    assert str(dm.open_report_button.cget("state")) == "normal"
    dm.open_report_button.invoke()
    assert opened[-1].name.startswith("issues_event")
    dm.tree.selection_set(dm.tree.get_children()[0])
    dm.gui.pump(0.1)
    assert str(dm.open_report_button.cget("state")) == "disabled"  # an accepted file has no problem report


def test_loading_the_same_files_again_says_nothing_new_was_loaded(dm, world):
    dm.add_paths([world.good])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.start_ingest)
    run_and_wait(dm, dm.start_ingest)
    assert rows(dm)[0][1] == "Already loaded (nothing new)"
    assert "Everything was loaded" in dm.final_label.cget("text")


def test_rejected_files_cannot_be_retried_unchanged_without_a_reason(dm, world):
    dm.add_paths([world.bad])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.start_ingest)
    run_and_wait(dm, dm.start_ingest)
    assert rows(dm)[0][1] == "Not retried (already rejected)"
    dm.force_var.set("Vendor says the file is final")
    run_and_wait(dm, dm.start_ingest)
    assert rows(dm)[0][1] == "Rejected - see problems"  # retried (and still rejected), not blocked


def test_a_file_rejected_only_for_future_dates_is_shown_as_waiting_not_as_rejected(dm, world):
    from datetime import datetime, timedelta, timezone

    today = datetime.now(timezone.utc).date()  # the Foundation's "today" for the future-date limit is the UTC date
    data = dd_mm_yy_rows(8)
    for i, row in enumerate(data):  # 8 consecutive days ending 3 days after today: the last 2 are beyond today + 1
        row[0] = (today + timedelta(days=i - 4)).strftime("%d-%m-%y")
    f = write_delimited(world.src / "NSE_FUTURE_1D.csv", NET_HEADER, data)
    dm.add_paths([f])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.start_ingest)
    assert rows(dm)[0][1] == "Rejected - see problems"
    run_and_wait(dm, dm.start_ingest)
    assert rows(dm)[0][1] == "Waiting - its dates are not allowed yet"
    assert (today + timedelta(days=2)).strftime("%d-%b-%y") in rows(dm)[0][3]
    assert "Open the problem report" not in dm.final_label.cget("text")


def test_a_profile_that_cannot_read_the_instrument_asks_for_it(dm, world):
    f = write_delimited(world.src / "weird_name.txt", ["date", "open", "high", "low", "close", "Volume"],
                        [r[:6] for r in daily_rows(8)])
    dm.add_paths([f])
    choose_profile(dm, "txt_hdr_isodate")
    assert str(dm.run_button.cget("state")) == "disabled"
    assert "exchange" in dm.hint.cget("text").lower()
    assert str(dm.exchange_entry.cget("state")) == "normal"
    dm.exchange_var.set("nse")
    assert "symbol" in dm.problems()[0].lower()
    dm.symbol_var.set("demo")
    dm.update_state()
    assert str(dm.run_button.cget("state")) == "normal"
    run_and_wait(dm, dm.start_ingest)
    assert rows(dm)[0][1] == "Accepted"
    db = open_database(dm.app.core_settings.db_path)
    assert db.one("SELECT exchange, symbol FROM instruments")["exchange"] == "NSE"
    db.close()


def test_fields_the_profile_reads_itself_are_not_editable(dm):
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    for w in (dm.exchange_entry, dm.symbol_entry, dm.timeframe_combo):
        assert str(w.cget("state")) == "disabled"
    choose_profile(dm, "csv_hdr_unixs_idfromname")
    assert str(dm.timeframe_combo.cget("state")) == "readonly" and str(dm.exchange_entry.cget("state")) == "disabled"


def test_a_switched_off_box_does_not_keep_showing_an_earlier_value(dm):
    choose_profile(dm, "csv_hdr_unixs_idfromname")
    dm.timeframe_var.set("5m")
    choose_profile(dm, "parquet_hdr_naivedt")  # timeframe fixed in the profile (1m)
    assert str(dm.timeframe_combo.cget("state")) == "disabled" and dm.timeframe_var.get() == ""
    assert "Timeframe: fixed in the profile (1m)" in dm.identity_note.cget("text")


def test_typing_the_exchange_and_symbol_enables_check_and_load_at_once(dm, world):
    """Regression: typing used to leave Check/Load disabled until some other event refreshed the window."""
    f = write_delimited(world.src / "weird_name.txt", ["date", "open", "high", "low", "close", "Volume"],
                        [r[:6] for r in daily_rows(8)])
    dm.add_paths([f])
    choose_profile(dm, "txt_hdr_isodate")
    assert str(dm.run_button.cget("state")) == "disabled"
    dm.exchange_entry.insert("end", "NSE")  # what a key press does: the box's text changes, nothing else is called
    dm.symbol_entry.insert("end", "NIFTY")
    dm.gui.pump(0.05)
    assert str(dm.run_button.cget("state")) == "normal" and str(dm.check_button.cget("state")) == "normal"
    assert dm.hint.cget("text").startswith("Ready")
    dm.symbol_entry.delete(0, "end")
    dm.symbol_entry.insert("end", "NIFTY 50")  # not a valid symbol: explained before anything runs
    assert str(dm.run_button.cget("state")) == "disabled" and "'NIFTY 50' is not valid" in dm.hint.cget("text")


def test_a_file_name_profile_explains_its_switched_off_boxes_and_can_be_copied_to_ask_for_them(dm, world):
    f = write_delimited(world.src / "csv headers std.csv", NET_HEADER, dd_mm_yy_rows())
    dm.add_paths([f])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    assert str(dm.exchange_entry.cget("state")) == "disabled"
    assert "read from the file name" in dm.identity_note.cget("text")
    assert dm.hint.cget("text").startswith("Note (1 file(s)):") and "does not fit" in dm.hint.cget("text")
    assert str(dm.run_button.cget("state")) == "normal"  # advice only; the engine decides per file
    run_and_wait(dm, dm.check_files)
    assert rows(dm)[0][1] == "Would be rejected"
    assert str(dm.ask_identity_button.cget("state")) == "normal"
    dm.gui.dialogs.strings.append("std_csv_asks")
    dm.ask_identity_button.invoke()
    assert dm.current_info.profile.profile_id == "std_csv_asks"
    assert dm.current_info.path.parent == dm.app.store.profiles_dir  # the user's own folder, not the repository
    assert str(dm.exchange_entry.cget("state")) == "normal" and str(dm.ask_identity_button.cget("state")) == "disabled"
    dm.exchange_entry.insert("end", "NSE")
    dm.symbol_entry.insert("end", "NIFTY")
    dm.gui.pump(0.05)
    run_and_wait(dm, dm.start_ingest)
    assert rows(dm)[0][1] == "Accepted"
    db = open_database(dm.app.core_settings.db_path)
    assert dict(db.one("SELECT exchange, symbol FROM instruments")) == {"exchange": "NSE", "symbol": "NIFTY"}
    db.close()


def test_a_problem_in_a_column_name_is_explained_without_codes(dm, world):
    f = write_delimited(world.src / "NSE_X_1D.csv", ["time", "open", "high", "low", "Volume"], [r[:4] + [r[5]] for r in dm_rows()])
    dm.add_paths([f])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.start_ingest)
    dm.tree.selection_set(dm.tree.get_children()[0])
    dm.gui.pump(0.1)
    text = dm.details.get()
    assert "required column is missing" in text and "'close'" in text and "[E_" not in text and "E_COLUMN" not in text


def dm_rows():
    return [[r[0]] + r[1:] for r in dd_mm_yy_rows(8)]


def test_a_vanished_file_is_reported_not_a_crash(dm, world):
    gone = write_delimited(world.src / "NSE_GONE_1D.csv", NET_HEADER, dm_rows_net())
    dm.add_paths([gone, world.good])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    gone.unlink()
    run_and_wait(dm, dm.start_ingest)
    out = rows(dm)
    assert out[0][1] == "Failed" and "could not read" in out[0][3].lower() and out[1][1] == "Accepted"


def dm_rows_net():
    return dd_mm_yy_rows(6)


def test_unsupported_files_are_reported_with_the_reason(dm, world):
    j = world.src / "data.json"
    j.write_text("{}")
    dm.add_paths([j])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.start_ingest)
    assert rows(dm)[0][1] == "File type not supported" and "JSON" in rows(dm)[0][3]


# ---- file list ------------------------------------------------------------------------------------------------
def test_adding_removing_and_clearing_files(dm, world):
    dm.gui.dialogs.files.append([str(world.good), str(world.bad)])
    dm.add_files()
    dm.add_paths([world.good])  # duplicates are ignored
    assert len(dm.files) == 2 and dm.listbox.size() == 2
    assert dm.app.gui_settings.last_input_dir == str(world.src)  # remembered for next time
    dm.listbox.selection_set(0)
    dm.remove_selected()
    assert dm.files == [world.bad] and dm.count_label.cget("text") == "[1 file selected]"
    dm.clear_files()
    assert not dm.files and str(dm.preview_button.cget("state")) == "disabled"


def test_preview_needs_a_file_and_explains(dm):
    dm.preview_selected()
    assert dm.app.dialogs.messages[-1][0] == "info" and "Add a file first" in dm.app.dialogs.messages[-1][2]


# ---- running state, cancel, threads ------------------------------------------------------------------------------
def slow_ingest(monkeypatch, delay=0.25):
    real = jobs.ingest_file

    def slow(*a, **k):
        time.sleep(delay)
        return real(*a, **k)

    monkeypatch.setattr(jobs, "ingest_file", slow)


def test_buttons_are_locked_while_running_and_free_afterwards(dm, world, monkeypatch):
    slow_ingest(monkeypatch)
    dm.add_paths([world.good, world.bad])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    dm.start_ingest()
    dm.gui.pump(0.1)
    assert dm.running and str(dm.run_button.cget("state")) == "disabled"
    assert str(dm.check_button.cget("state")) == "disabled" and str(dm.add_button.cget("state")) == "disabled"
    assert str(dm.cancel_button.cget("state")) == "normal" and dm.hint.cget("text") == "Working..."
    dm.gui.wait(dm.finished_event.is_set)
    assert not dm.running and str(dm.run_button.cget("state")) == "normal" and str(dm.cancel_button.cget("state")) == "disabled"


def test_progress_is_shown_while_files_are_processed(dm, world, monkeypatch):
    slow_ingest(monkeypatch, 0.3)
    dm.add_paths([world.good, world.bad])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    dm.start_ingest()
    dm.gui.wait(lambda: dm.files_var.get().startswith("1 / 2"))
    assert 0 < float(dm.progress["value"]) < 100
    assert dm.file_var.get() in ("NSE_NIFTY_1D1.csv", "NSE_BADFILE_1D.csv") and dm.stage_var.get().startswith("Loading file")
    assert CLOCK.match(dm.started_var.get()) and dm.elapsed_var.get().endswith("s")
    dm.gui.wait(dm.finished_event.is_set)
    assert dm.eta_var.get() == "-"


def test_stop_after_this_file(dm, world, monkeypatch):
    slow_ingest(monkeypatch, 0.3)
    files = [write_delimited(world.src / f"NSE_F{i}_1D.csv", NET_HEADER, dd_mm_yy_rows(6, i)) for i in range(1, 6)]
    dm.add_paths(files)
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    dm.start_ingest()
    dm.gui.wait(lambda: dm._done >= 1)
    dm.cancel()
    dm.gui.wait(dm.finished_event.is_set)
    assert 1 <= len(rows(dm)) < 5 and dm.stage_var.get() == "Stopped (as you asked)"
    assert "Cancelled by you" in dm.log.get()
    # a stopped load never looks finished (10-Nov-26 progress review): partial bar, amber 'stopped by you' message
    assert float(dm.progress["value"]) < 100 and dm.final_label.cget("text").startswith("Load stopped by you after")


def test_a_finished_load_ends_with_a_full_bar(dm, world):
    dm.add_paths([world.good, world.bad])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    dm.start_ingest()
    dm.gui.wait(dm.finished_event.is_set)
    assert float(dm.progress["value"]) == 100 and dm.stage_var.get() == "Finished"


def test_the_screen_is_only_ever_updated_from_the_main_thread(dm, world, monkeypatch):
    slow_ingest(monkeypatch, 0.1)
    seen = []
    original = dm.on_job_event

    def spy(event):
        seen.append(threading.current_thread() is threading.main_thread())
        original(event)

    dm.on_job_event = spy
    dm.add_paths([world.good, world.bad])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.start_ingest)
    assert seen and all(seen)
    workers = [t for t in threading.enumerate() if t.name == "qmap-worker" and t.is_alive()]
    assert not workers


def test_the_live_log_shows_the_foundations_messages(dm, world):
    dm.add_paths([world.good, world.bad])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.start_ingest)
    log = dm.log.get()
    assert "Receipt" in log and "Ingest accepted" in log and "Ingest REJECTED" in log and "started" in log


def test_an_unexpected_failure_in_the_worker_is_shown_not_swallowed(dm, world, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("worker exploded")

    monkeypatch.setattr(jobs.IngestJob, "run", boom)
    dm.add_paths([world.good])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.start_ingest)
    assert not dm.running and "worker exploded" in dm.final_label.cget("text") and "worker exploded" in dm.log.get()


# ---- profiles -----------------------------------------------------------------------------------------------------
def test_profile_details_are_shown_in_plain_english(dm):
    choose_profile(dm, "csv_hdr_unixs_idfromname")
    text = dm.profile_details.get()
    assert "Unix timestamps in SECONDS" in text and "First row is a header: Yes" in text and "Net Volume" in text


def test_browse_for_a_valid_and_an_invalid_profile(dm, world):
    good = world.src / "elsewhere.toml"
    good.write_text((REPO / "Configuration/source_profiles/csv_hdr_isodt_idfromname.toml").read_text().replace("csv_hdr_isodt_idfromname", "elsewhere"))
    dm.gui.dialogs.file.append(str(good))
    dm.browse_profile()
    assert dm.current_info.profile.profile_id == "elsewhere" and dm.current_info.where == "file"
    bad = world.src / "bad.toml"
    bad.write_text('profile_id = "x"\n')
    dm.gui.dialogs.file.append(str(bad))
    dm.browse_profile()
    assert dm.current_info.profile is None and "cannot be used yet" in dm.profile_details.get()
    assert "profile_version" in dm.profile_details.get() and str(dm.run_button.cget("state")) == "disabled"


def test_new_profile_from_an_example_lands_in_my_profiles_not_the_repository(dm, world):
    before = repo_snapshot()
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    dm.gui.dialogs.strings.append("my_daily")
    dm.copy_profile()
    assert dm.current_info.where == "mine" and dm.current_info.profile.profile_id == "my_daily"
    assert (world.settings / "profiles" / "my_daily.toml").is_file()
    assert repo_snapshot() == before
    dm.gui.dialogs.strings.append("bad name!")
    dm.copy_profile()
    assert dm.gui.dialogs.messages[-1][0] == "error" and "letters, digits" in dm.gui.dialogs.messages[-1][2]


def test_the_profile_choice_is_remembered(dm, gui, world):
    choose_profile(dm, "csv_hdr_isodt_idfromname")
    gui.close()
    dm2 = gui.start().screens["data"]
    assert dm2.current_info is not None and dm2.current_info.profile.profile_id == "csv_hdr_isodt_idfromname"


def test_profile_editor_checks_saves_and_protects_examples(dm, world):
    from qmap_gui.profile_editor import ProfileEditor

    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    dm.edit_profile()
    editor = next(w for w in dm.app.winfo_children() if isinstance(w, ProfileEditor))
    assert "Editing a COPY of the Q-MAP library profile" in editor.message.master.winfo_children()[0].cget("text")
    assert 'status          = "custom"' in editor.text.get("1.0", "end")  # the copy is labelled as yours
    assert not editor.check() and "Q-MAP library profile" in editor.message.cget("text")  # keep your own name
    editor.text.delete("1.0", "end")
    editor.text.insert("1.0", (REPO / "Configuration/source_profiles/csv_hdr_ddmmyy_idfromname.toml").read_text()
                       .replace("csv_hdr_ddmmyy_idfromname", "edited_daily").replace("two_digit_year_pivot = 69", ""))
    assert not editor.check() and "two-digit year" in editor.message.cget("text")
    editor.text.delete("1.0", "end")
    editor.text.insert("1.0", (REPO / "Configuration/source_profiles/csv_hdr_ddmmyy_idfromname.toml").read_text()
                       .replace("csv_hdr_ddmmyy_idfromname", "edited_daily"))
    editor.save()
    assert (world.settings / "profiles" / "edited_daily.toml").is_file() and "Saved" in editor.message.cget("text")
    assert dm.current_info.profile.profile_id == "edited_daily"
    editor.destroy()
    # use it, then change it without a new version: the editor refuses and says why
    dm.add_paths([world.good])
    run_and_wait(dm, dm.start_ingest)
    dm.edit_profile()
    editor2 = [w for w in dm.app.winfo_children() if isinstance(w, ProfileEditor)][-1]
    editor2.text.insert("1.0", "# a comment changes the content\n")
    assert not editor2.check() and "profile_version" in editor2.message.cget("text")
    editor2.destroy()


def test_nothing_is_added_to_the_repository_during_the_whole_workflow(dm, world):
    before = repo_snapshot()
    dm.add_paths([world.good, world.bad])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.check_files)
    run_and_wait(dm, dm.start_ingest)
    dm.preview_selected()
    dm.gui.pump(0.5)
    assert repo_snapshot() == before
    assert tree_files(world.output) and tree_files(world.data)


def test_a_file_deleted_between_two_runs_does_not_affect_the_stored_original(dm, world):
    dm.add_paths([world.good])
    choose_profile(dm, "csv_hdr_ddmmyy_idfromname")
    run_and_wait(dm, dm.start_ingest)
    shutil.copy(world.good, world.src / "backup.csv")
    world.good.unlink()
    dm.clear_files()
    dm.add_paths([world.src / "backup.csv"])
    run_and_wait(dm, dm.start_ingest)
    assert rows(dm)[0][1] == "Already loaded (nothing new)"  # same content, different name
