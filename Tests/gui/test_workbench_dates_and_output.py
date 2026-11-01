"""Real-window tests: Workbench calendar date boxes and typed dates (requirement 2), Open Output Folder (3)."""

from __future__ import annotations

import shutil
from datetime import date

import pytest

from gui.test_two_applications import _prepare, _select


@pytest.fixture
def an(gui, world):
    """The Run an analysis screen, with one prepared daily dataset (12 bars, 05-Jan-26 .. 20-Jan-26) selected."""
    dataset_id = _prepare(world)
    app = gui.start(app_key="analytical_workbench")
    gui.choose_folders(app)
    app.show("analysis")
    screen = app.screens["analysis"]
    _select(screen, dataset_id)
    gui.pump(0.2)
    return screen


# ---- 2.1 / 2.2: calendar and typing ----------------------------------------------------------------------------
def test_both_date_fields_are_calendar_date_boxes(an):
    assert set(an.date_entries) == {"date_from", "date_to"}
    for box in an.date_entries.values():
        assert box.button.cget("text") == "Calendar..." and str(box.entry.cget("state")) == "normal"


@pytest.mark.parametrize("typed", ["12/01/26", "12-01-26", "12-Jan-26", "120126"])
def test_typed_formats_are_confirmed_next_to_the_box(an, typed):
    an.param_vars["date_from"].set(typed)
    assert an.date_entries["date_from"].feedback.cget("text") == "= 12-Jan-2026"


def test_an_impossible_or_unknown_date_is_explained_next_to_the_box(an):
    an.param_vars["date_to"].set("31/02/26")
    assert "February 2026 has 28 days" in an.date_entries["date_to"].feedback.cget("text")
    an.param_vars["date_to"].set("31.01.26")
    assert "25/02/26, 25-02-26, 25-Feb-26 or 250226" in an.date_entries["date_to"].feedback.cget("text")
    an.param_vars["date_to"].set("")
    assert "empty = to the last bar" in an.date_entries["date_to"].feedback.cget("text")


def test_the_calendar_picks_clears_and_changes_month(an, gui):
    box = an.date_entries["date_from"]
    an.param_vars["date_from"].set("15-Jan-26")
    box.open_calendar()
    popup = box.popup
    assert popup.winfo_exists() and popup.month_label.cget("text") == "January 2026"
    assert popup.day_buttons[15].cget("relief") == "sunken"  # the typed date is shown as selected
    popup.next_button.invoke()
    assert popup.month_label.cget("text") == "February 2026"
    popup.day_buttons[3].invoke()
    assert an.param_vars["date_from"].get() == "03-Feb-26" and not popup.winfo_exists()
    box.open_calendar()
    box.popup.prev_button.invoke()
    assert box.popup.month_label.cget("text") == "January 2026"
    box.popup.clear()
    assert an.param_vars["date_from"].get() == ""
    an.param_vars["date_from"].set("05-01-26")  # typing still works after using the calendar
    assert an.date_entries["date_from"].feedback.cget("text") == "= 05-Jan-2026"


# ---- 2.4 / 2.5 in the window -------------------------------------------------------------------------------------
def test_invalid_dates_are_reported_as_invalid_input_and_nothing_starts(an, world):
    an.param_vars["date_from"].set("20-Jan-26")
    an.param_vars["date_to"].set("10-Jan-26")
    an.start_run()
    assert not an.running and an.last_result is None
    assert an.readiness_box.get().startswith("INVALID DATE INPUT") and "after the end date" in an.readiness_box.get()
    assert "dates are not valid" in an.final_label.cget("text")
    assert not (world.output / "Research_Reports").exists()


def test_a_valid_but_empty_period_is_not_called_a_date_error(an):
    an.param_vars["date_from"].set("01/03/26")
    an.check()
    text = an.readiness_box.get()
    assert text.startswith("NO DATA IN THIS PERIOD") and "INVALID" not in text and "05-Jan-26 to 20-Jan-26" in text


def test_a_valid_period_with_bars_runs(an, gui):
    an.param_vars["date_from"].set("070126")
    an.param_vars["date_to"].set("14/01/26")
    an.start_run()
    gui.wait(lambda: not an.running and an.last_result is not None, timeout=60)
    assert an.last_result.ok and an.last_result.readiness.params == {"date_from": date(2026, 1, 7),
                                                                       "date_to": date(2026, 1, 14)}


# ---- 3: Open Output Folder ---------------------------------------------------------------------------------------
def _opened(monkeypatch):
    import qmap_gui.common as common

    calls = []
    monkeypatch.setattr(common, "open_in_file_manager", lambda p: (calls.append(p), (True, "Opened."))[1])
    return calls


def test_open_output_folder_is_disabled_until_a_run_has_completed(an, monkeypatch):
    calls = _opened(monkeypatch)
    assert an.open_run_button.cget("text") == "Open Output Folder"
    assert str(an.open_run_button.cget("state")) == "disabled" and "no completed run" in an.run_folder_var.get()
    an.open_run_folder()  # even if called, it explains instead of opening anything
    assert calls == [] and "No analysis run has completed yet" in an.app.dialogs.messages[-1][2]


def test_it_opens_the_exact_folder_of_the_latest_completed_run(an, gui, monkeypatch):
    calls = _opened(monkeypatch)
    an.start_run()
    gui.wait(lambda: not an.running and an.last_result is not None, timeout=60)
    run_dir = an.last_result.run_dir
    assert str(an.open_run_button.cget("state")) == "normal" and an.run_folder_var.get() == str(run_dir)
    assert str(an.run_folder_entry.cget("state")) == "readonly"  # visible, selectable, copyable, not editable
    an.open_run_button.invoke()
    assert calls == [run_dir] and run_dir.is_dir() and any(run_dir.iterdir())  # opened only; nothing changed


def test_a_refused_or_failed_request_does_not_replace_the_last_completed_run(an, gui):
    an.start_run()
    gui.wait(lambda: not an.running and an.last_result is not None, timeout=60)
    good = an.last_result.run_dir
    an.param_vars["date_from"].set("01-Jan-30")
    an.start_run()
    assert an.run_folder_var.get() == str(good)


def test_after_a_restart_the_latest_completed_run_comes_from_the_registry(an, gui, world):
    an.start_run()
    gui.wait(lambda: not an.running and an.last_result is not None, timeout=60)
    run_dir = an.last_result.run_dir
    again = gui.start(app_key="analytical_workbench").screens["analysis"]
    assert again.run_folder_var.get() == str(run_dir) and str(again.open_run_button.cget("state")) == "normal"


def test_a_missing_folder_is_explained_not_a_crash(an, gui, monkeypatch):
    calls = _opened(monkeypatch)
    an.start_run()
    gui.wait(lambda: not an.running and an.last_result is not None, timeout=60)
    shutil.rmtree(an.last_result.run_dir)
    an.open_run_button.invoke()
    assert calls == [] and "no longer exists" in an.app.dialogs.messages[-1][2]


def test_an_operating_system_refusal_is_explained(an, gui, monkeypatch):
    import qmap_gui.common as common

    an.start_run()
    gui.wait(lambda: not an.running and an.last_result is not None, timeout=60)

    def refuse(_path):
        raise OSError("Access is denied")

    monkeypatch.setattr(common.subprocess, "Popen", refuse)
    monkeypatch.setattr(common.os, "startfile", refuse, raising=False)
    an.open_run_button.invoke()
    assert "Could not open" in an.app.dialogs.messages[-1][2] and "Access is denied" in an.app.dialogs.messages[-1][2]
