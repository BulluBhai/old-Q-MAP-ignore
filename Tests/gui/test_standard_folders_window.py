"""Both applications prepare and show the standard folders at start (10-Nov-26 usability requirement 1), share them
through the one remembered settings file, and never silently replace folders the user chose earlier."""

from __future__ import annotations

from gui.conftest import create_with_tk_startup_retry


def _start(gui, world, parent, app_key="database_manager"):
    from qmap_gui.app import APPS

    app = create_with_tk_startup_retry(lambda: APPS[app_key](world.repo, settings_dir=world.settings,
                                                             dialogs=gui.dialogs, standard_parent=parent))
    gui.apps.append(app)
    gui.pump(0.05, app)
    return app


def test_first_start_prepares_uses_and_remembers_the_standard_folders(gui, world, tmp_path):
    parent = tmp_path / "Beta_Test"
    parent.mkdir()
    dm = _start(gui, world, parent)
    assert dm.core_settings is not None  # ready to use at once
    assert dm.data_var.get() == str(parent / "Q-MAP_DATA") and dm.output_var.get() == str(parent / "Q-MAP_OUTPUT")
    panel = dm.screens["home"].locations_panel
    assert "prepared automatically" in panel.note.cget("text") and "created Q-MAP_DATA and Q-MAP_OUTPUT" in panel.note.cget("text")
    assert panel.summary.cget("text") == "Both folders are ready and remembered."
    # the Workbench opened afterwards uses the same (remembered) folders: one source of truth
    wb = _start(gui, world, parent, "analytical_workbench")
    assert wb.core_settings is not None and wb.core_settings.data_root == dm.core_settings.data_root
    assert "Using the standard folders" in wb.screens["home"].locations_panel.note.cget("text")


def test_remembered_folders_are_kept_and_the_standard_ones_offered(gui, world, tmp_path):
    first = gui.start()
    gui.choose_folders(first)  # the user chose world.data and world.output earlier
    parent = tmp_path / "New_Copy"
    parent.mkdir()
    dm = _start(gui, world, parent)
    assert dm.data_var.get() == str(world.data) and dm.output_var.get() == str(world.output)
    assert not (parent / "Q-MAP_DATA").exists()  # nothing created behind the user's back
    note = dm.screens["home"].locations_panel.note.cget("text")
    assert "folders you chose earlier" in note and str(parent / "Q-MAP_DATA") in note
    # 'Use standard folders' asks first; No changes nothing
    gui.dialogs.yes = False
    dm.screens["home"].locations_panel.standard_button.invoke()
    assert dm.data_var.get() == str(world.data) and not (parent / "Q-MAP_DATA").exists()
    gui.dialogs.yes = True
    (world.data / "keep.txt").write_text("mine")
    dm.screens["home"].locations_panel.standard_button.invoke()
    assert dm.data_var.get() == str(parent / "Q-MAP_DATA") and dm.core_settings is not None
    assert (world.data / "keep.txt").read_text() == "mine"  # the old folder is untouched
    assert dm.store.load().data_root == str(parent / "Q-MAP_DATA")  # remembered for both applications


def test_a_problem_is_explained_and_manual_choice_still_works(gui, world, tmp_path):
    parent = tmp_path / "Odd"
    parent.mkdir()
    (parent / "Q-MAP_DATA").write_text("a file")
    dm = _start(gui, world, parent)
    panel = dm.screens["home"].locations_panel
    assert dm.core_settings is None and "could not be prepared automatically" in panel.note.cget("text")
    assert (parent / "Q-MAP_DATA").read_text() == "a file"
    gui.choose_folders(dm)  # Browse... / typing still works
    assert dm.core_settings is not None


def test_tests_and_callers_without_a_standard_parent_get_no_automatic_folders(gui, world):
    dm = gui.start()
    assert dm.standard_parent is None and dm.data_var.get() == "" and dm.folder_note == ""
    assert not dm.screens["home"].locations_panel.standard_button.winfo_ismapped()
