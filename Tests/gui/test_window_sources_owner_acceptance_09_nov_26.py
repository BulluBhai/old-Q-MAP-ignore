"""Real-window tests for the owner acceptance findings of 09-Nov-26 on PR #10 (Sources screen).

W08: Include sub-folders ticked but not saved, then SCAN: the scan used the saved setting (off), found nothing, and
     the refresh put the box back to off. Now the screen and the scan can never disagree: Q-MAP asks, saves (Yes) or
     puts the screen back (No), and the box keeps the setting the scan used.
W14-W18: the file details show the whole-file checks recorded on the file's dataset.
Add folder...: opens at the application folder the first time, then at the folder chosen last, also after a restart."""

from __future__ import annotations

import shutil
from pathlib import Path

from fixtures.builders import HEADER, daily_rows, write_delimited

PATTERNS = Path(__file__).resolve().parents[2] / "docs" / "acceptance_testing" / "dq7_pattern_files_03_Nov_26"


def _stop_folder(tmp_path) -> Path:
    root = tmp_path / "W_Stop"
    for i, sub in enumerate(("Batch_A", "Batch_B", "Batch_C")):
        (root / sub).mkdir(parents=True)
        for j in range(2):
            write_delimited(root / sub / f"NSE_S{i}{j}.csv", HEADER, daily_rows(12, seed=10 * i + j + 1))
    return root


def _sources(gui, tmp_path, folder):
    app = gui.start()
    gui.choose_folders(app)
    app.show("sources")
    frame = app.screens["sources"]
    gui.dialogs.directories.append(str(folder))
    frame.add_button.invoke()  # added with Include sub-folders off (the default)
    gui.pump(0.1)
    assert frame.selected_source() is not None and frame.sub_var.get() is False
    return app, frame


def _scan(gui, frame):
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    gui.pump(0.2)  # the selection events of the refresh are handled too, as in the real window


def _saved_subfolders(frame) -> bool:
    from qmap_gui import source_services as ss

    return next(s for s in ss.sources(frame.app.core_settings) if s.source_id == frame.selected_source()).include_subfolders


def test_w08_ticked_but_not_saved_yes_saves_and_scans_recursively_and_the_box_stays_ticked(gui, tmp_path):
    app, frame = _sources(gui, tmp_path, _stop_folder(tmp_path))
    frame.sub_var.set(True)  # ticked, Save settings NOT pressed
    gui.dialogs.yes = True
    _scan(gui, frame)
    kind, title, message = gui.dialogs.messages[-1]
    assert kind == "yes_no" and title == "Folder settings not saved"
    assert "Include sub-folders: on screen on, saved off" in message
    assert _saved_subfolders(frame) is True and frame.sub_var.get() is True  # the box keeps what the scan used
    assert {s.relative_path for s in frame.file_rows.values()} == {f"Batch_{c}/NSE_S{i}{j}.csv"
                                                                   for i, c in enumerate("ABC") for j in range(2)}
    assert all(s.outcome == "imported" for s in frame.file_rows.values())
    assert "Folder settings saved before the scan: Include sub-folders on" in frame.log.get()
    n = len(gui.dialogs.messages)
    _scan(gui, frame)  # nothing differs any more: no question
    assert len(gui.dialogs.messages) == n and frame.sub_var.get() is True


def test_w08_ticked_but_not_saved_no_scans_with_the_saved_setting_and_shows_it(gui, tmp_path):
    app, frame = _sources(gui, tmp_path, _stop_folder(tmp_path))
    frame.sub_var.set(True)
    gui.dialogs.yes = False
    _scan(gui, frame)
    assert gui.dialogs.messages[-1][1] == "Folder settings not saved"
    assert _saved_subfolders(frame) is False and frame.sub_var.get() is False  # the screen shows what was used
    assert not frame.file_rows
    text = frame.final_label.cget("text")
    assert "no supported files found (3 sub-folder(s) not scanned: Include sub-folders is off" in text
    assert frame.last_report is not None
    assert "Sub-folders,not included (3 not scanned)" in frame.last_report.read_text(encoding="utf-8")


def test_w14_w18_file_details_show_the_whole_file_checks(gui, tmp_path):
    folder = tmp_path / "W_Pattern"
    folder.mkdir()
    for name in ("NSE_EVERYOTHER.csv", "NSE_SPARSE.csv"):
        shutil.copy2(PATTERNS / name, folder / name)
    app, frame = _sources(gui, tmp_path, folder)
    _scan(gui, frame)
    shown = {}
    for item, s in frame.file_rows.items():
        frame.files_tree.selection_set(item)
        frame.on_file_select()
        shown[s.relative_path] = frame.details.get()
    every = shown["NSE_EVERYOTHER.csv"]
    assert "WARNING: Part of the file may have another bar interval" in every and "cannot show whether" in every
    assert "Detected timeframe: 5 minutes" in every
    sparse = shown["NSE_SPARSE.csv"]
    assert "WARNING: Some days have fewer bars than usual" in sparse and "bar interval" not in sparse


def test_add_folder_opens_at_the_application_folder_then_at_the_last_folder_also_after_restart(gui, tmp_path):
    from qmap_gui.app import Dialogs

    seen = []
    real = type(gui.dialogs).ask_directory

    def recording(self, title, initial=""):
        seen.append(initial)
        return real(self, title, initial)

    type(gui.dialogs).ask_directory = recording
    try:
        first, second = tmp_path / "W_Market", tmp_path / "W_Pattern"
        first.mkdir()
        second.mkdir()
        app = gui.start()
        gui.choose_folders(app)
        app.show("sources")
        frame = app.screens["sources"]
        assert app.gui_settings.last_source_dir == ""
        gui.dialogs.directories.append(str(first))
        frame.add_button.invoke()
        assert seen[-1] == str(app.code_root)  # first use: where Q-MAP runs from (not the working directory)
        gui.dialogs.directories.append(str(second))
        frame.add_button.invoke()
        assert seen[-1] == str(first)
        frame.add_button.invoke()  # cancelled: nothing chosen, nothing forgotten
        assert seen[-1] == str(second)
        gui.close()
        app = gui.start()  # restart: remembered in gui_settings.json
        gui.choose_folders(app)
        app.show("sources")
        app.screens["sources"].add_button.invoke()
        assert seen[-1] == str(second)
    finally:
        type(gui.dialogs).ask_directory = real
    assert Dialogs.ask_directory is not recording
