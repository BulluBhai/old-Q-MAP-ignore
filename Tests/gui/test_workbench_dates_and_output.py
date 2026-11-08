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


@pytest.mark.parametrize("typed", ["01/01/0000", "0000-06-15", "29-Feb-0000"])
def test_year_0000_is_explained_and_blocked_in_feedback_check_and_run(an, world, typed):
    """Review finding (PR #4): such input used to raise Python's ValueError instead of the date message."""
    an.param_vars["date_from"].set(typed)  # live feedback next to the box
    assert "there is no year 0000" in an.date_entries["date_from"].feedback.cget("text")
    an.check()  # Check readiness
    assert an.readiness_box.get().startswith("INVALID DATE INPUT") and "there is no year 0000" in an.readiness_box.get()
    an.start_run()  # Run
    assert not an.running and an.last_result is None and "dates are not valid" in an.final_label.cget("text")
    assert not (world.output / "Research_Reports").exists()


def test_a_calendar_pick_outside_1969_2068_keeps_its_century(an):
    box = an.date_entries["date_from"]
    an.param_vars["date_from"].set("15/06/1950")
    box.open_calendar()
    assert box.popup.month_label.cget("text") == "June 1950"
    box.popup.day_buttons[20].invoke()
    assert an.param_vars["date_from"].get() == "20-Jun-1950"  # not 20-Jun-50, which would mean 2050
    assert box.feedback.cget("text") == "= 20-Jun-1950"


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


# ---- PR #9 acceptance: year navigation in the calendar (<< and >>) ----------------------------------------------------
def test_year_buttons_move_a_whole_year_and_keep_the_month(an):
    box = an.date_entries["date_from"]
    an.param_vars["date_from"].set("15-Mar-26")
    box.open_calendar()
    popup = box.popup
    assert popup.prev_year_button.cget("text") == "<<" and popup.next_year_button.cget("text") == ">>"
    assert popup.prev_button.cget("text") == "<" and popup.next_button.cget("text") == ">"  # month buttons kept
    for _ in range(28):  # 2026 -> 1998 without clicking through 336 months
        popup.prev_year_button.invoke()
    assert popup.month_label.cget("text") == "March 1998" and (popup.year, popup.month) == (1998, 3)
    popup.next_button.invoke()  # month navigation still works after year navigation
    assert popup.month_label.cget("text") == "April 1998"
    popup.next_year_button.invoke()
    assert popup.month_label.cget("text") == "April 1999"
    popup.prev_button.invoke()
    popup.prev_button.invoke()
    popup.prev_button.invoke()
    popup.prev_button.invoke()  # across a year boundary by months
    assert popup.month_label.cget("text") == "December 1998"
    assert 15 not in {d for d, b in popup.day_buttons.items() if b.cget("relief") == "sunken"}  # 15-Mar-26 not here


def test_dates_picked_in_1998_and_2026_reach_the_analysis_parameters(an):
    start, end = an.date_entries["date_from"], an.date_entries["date_to"]
    start.open_calendar()
    for _ in range(28):
        start.popup.prev_year_button.invoke()
    while (start.popup.year, start.popup.month) != (1998, 1):  # from whatever month it opened on
        start.popup.shift(-12 if start.popup.year > 1998 else (1 if start.popup.year < 1998 else -1))
    year, month = start.popup.year, start.popup.month
    start.popup.day_buttons[2].invoke()
    picked_start = date(year, month, 2)
    assert start.value() == (picked_start, None)
    end.open_calendar()
    while end.popup.year != 2026:
        end.popup.next_year_button.invoke() if end.popup.year < 2026 else end.popup.prev_year_button.invoke()
    while end.popup.month != 1:
        end.popup.prev_button.invoke()
    end.popup.day_buttons[20].invoke()
    assert end.value() == (date(2026, 1, 20), None)
    an.check()
    assert an.last_readiness is not None and an.last_readiness.params == {"date_from": picked_start,
                                                                           "date_to": date(2026, 1, 20)}


def test_range_validation_after_year_navigation(an):
    start, end = an.date_entries["date_from"], an.date_entries["date_to"]
    end.open_calendar()
    while (end.popup.year, end.popup.month) != (1998, 1):
        end.popup.shift(-12 if end.popup.year > 1998 else -1)
    end.popup.day_buttons[5].invoke()  # end 05-Jan-1998
    an.param_vars["date_from"].set("10-Jan-26")  # start after end: refused
    an.start_run()
    assert not an.running and an.last_result is None and "dates are not valid" in an.final_label.cget("text")
    assert "after the end date" in an.readiness_box.get()
    start.open_calendar()
    while (start.popup.year, start.popup.month) != (1998, 1):
        start.popup.shift(-12 if start.popup.year > 1998 else -1)
    start.popup.day_buttons[2].invoke()  # 02-Jan-1998 .. 05-Jan-1998: a valid range (no bars there, not a date error)
    an.check()
    assert not an.readiness_box.get().startswith("INVALID DATE INPUT")


# ---- PR #9 acceptance: Open Output Folder next to the completed-run message ---------------------------------------
def test_the_results_area_button_opens_the_recorded_folder_of_the_completed_run(an, gui, monkeypatch):
    calls = _opened(monkeypatch)
    assert an.result_open_button.cget("text") == "Open Output Folder"
    assert str(an.result_open_button.cget("state")) == "disabled"  # no completed run yet
    an.start_run()
    gui.wait(lambda: not an.running and an.last_result is not None, timeout=60)
    run_dir = an.last_result.run_dir
    from qmap_gui import workbench_services as ws

    assert ws.last_completed_run(an.app.core_settings) == (an.last_result.run_id, run_dir)  # the RECORDED folder
    assert str(an.result_open_button.cget("state")) == "normal"
    an.result_open_button.invoke()
    assert calls == [run_dir]
    shutil.rmtree(run_dir)
    an.result_open_button.invoke()
    assert calls == [run_dir] and "no longer exists" in an.app.dialogs.messages[-1][2]
