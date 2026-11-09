"""Real-window tests: home screen readiness, choosing and remembering the two folders, safeguards."""

import json

from gui.conftest import REPO, repo_snapshot
import pytest

from qmap_gui.modules import modules_for


def test_everything_lives_inside_the_scroll_frame(gui):
    from qmap_gui.widgets import ScrollFrame

    app = gui.start()
    assert isinstance(app._scroll_frame, ScrollFrame)
    assert app.container.master is app._scroll_frame.inner
    assert app.protocol("WM_DELETE_WINDOW")  # the close handler is installed


@pytest.mark.parametrize("app_key, expected_ready", [
    ("database_manager", ["sources", "data_management", "datasets"]),  # Sources added 02-Nov-26 (Blueprint v1.3)
    ("analytical_workbench", ["dataset_summary", "ma_research"]),  # MA Research (QLOPB) added 03-Nov-26 (owner approval)
])
def test_home_lists_its_own_modules_with_genuine_readiness(gui, app_key, expected_ready):
    home = gui.start(app_key=app_key).screens["home"]
    mine = modules_for(app_key)
    assert set(home.module_rows) == {m.key for m in mine}
    for m in mine:
        row = home.module_rows[m.key]
        assert row["status"].cget("text") == ("READY" if m.is_ready else "COMING SOON")
        assert str(row["button"].cget("state")) == ("normal" if m.is_ready else "disabled")
    ready = [k for k, r in home.module_rows.items() if r["status"].cget("text") == "READY"]
    assert ready == expected_ready


def test_open_button_for_data_management_switches_screen(gui):
    app = gui.start()
    app.screens["home"].module_rows["data_management"]["button"].invoke()
    assert app.current == "data"


def test_first_start_asks_for_folders_in_plain_words(gui):
    app = gui.start()
    row = app.screens["home"].locations_panel.rows["data"]
    assert row["status"].cget("text") == "Not chosen yet."
    dm = app.screens["data"]
    assert str(dm.run_button.cget("state")) == "disabled"
    assert "folders" in dm.hint.cget("text").lower()
    assert app.core_settings is None


def test_choosing_folders_remembers_them_outside_the_repository(gui, world):
    before = repo_snapshot()
    app = gui.start()
    gui.choose_folders(app)
    panel = app.screens["home"].locations_panel
    assert panel.rows["data"]["status"].cget("text").startswith("OK")
    assert "ready and remembered" in panel.summary.cget("text")
    saved = json.loads((world.settings / "gui_settings.json").read_text())
    assert saved["data_root"] == str(world.data) and saved["output_root"] == str(world.output)
    assert repo_snapshot() == before  # nothing was written into the code repository
    # the Foundation's own layout was created in the chosen folders, not in the repository
    assert (world.data / "Raw_Data").is_dir() and (world.output / "Logs").is_dir()

    gui.close()  # "restart" Q-MAP: the choice must come back by itself
    app2 = gui.start()
    assert app2.data_var.get() == str(world.data) and app2.output_var.get() == str(world.output)
    assert app2.core_settings is not None and app2.core_settings.data_root == world.data.resolve()


def test_browse_buttons_choose_and_apply(gui, world):
    app = gui.start()
    gui.dialogs.directories += [str(world.data), str(world.output)]
    app.screens["home"].locations_panel.rows["data"]["browse"].invoke()
    app.screens["home"].locations_panel.rows["output"]["browse"].invoke()
    assert app.core_settings is not None


def test_a_missing_folder_can_be_created_after_confirmation(gui, world):
    app = gui.start()
    new = world.data / "brand_new"
    app.data_var.set(str(new))
    app.output_var.set(str(world.output))
    app.apply_locations()
    panel = app.screens["home"].locations_panel
    assert str(panel.rows["data"]["create"].cget("state")) == "normal" and not new.exists()
    gui.dialogs.yes = False
    panel.rows["data"]["create"].invoke()
    assert not new.exists()  # said no: nothing happens
    gui.dialogs.yes = True
    panel.rows["data"]["create"].invoke()
    assert new.is_dir() and app.core_settings is not None
    assert app.core_settings.data_root == new.resolve()


def test_a_folder_inside_the_program_folder_is_refused_and_never_created(gui, world):
    app = gui.start()
    inside = REPO / "docs"  # exists, inside the repository
    app.data_var.set(str(inside))
    app.output_var.set(str(world.output))
    assert not app.apply_locations()
    panel = app.screens["home"].locations_panel
    assert "inside the code folder" in panel.rows["data"]["status"].cget("text")
    assert app.core_settings is None
    assert str(app.screens["data"].run_button.cget("state")) == "disabled"
    # creating a not-yet-existing folder inside the repository is refused too, and nothing is made
    ghost = REPO / "my_new_data_folder"
    app.data_var.set(str(ghost))
    app.apply_locations()
    assert str(panel.rows["data"]["create"].cget("state")) == "disabled"
    app.create_location("data")
    assert not ghost.exists() and any(kind == "error" for kind, *_ in gui.dialogs.messages)


def test_an_unusable_choice_is_not_remembered(gui, world):
    app = gui.start()
    app.data_var.set(str(REPO / "docs"))
    app.output_var.set(str(world.output))
    app.apply_locations()
    assert not (world.settings / "gui_settings.json").exists()


def test_overlapping_folders_are_refused(gui, world):
    app = gui.start()
    nested = world.data / "results"
    nested.mkdir()
    app.data_var.set(str(world.data))
    app.output_var.set(str(nested))
    assert not app.apply_locations()
    assert "overlap" in app.screens["home"].locations_panel.rows["output"]["status"].cget("text")


def test_a_remembered_folder_that_has_vanished_is_explained_not_a_crash(gui, world):
    app = gui.start()
    gui.choose_folders(app)
    gui.close()
    import shutil

    shutil.rmtree(world.data)
    app2 = gui.start()
    text = app2.screens["home"].locations_panel.rows["data"]["status"].cget("text")
    assert "does not exist" in text and app2.core_settings is None


def test_a_damaged_settings_file_warns_and_still_starts(gui, world):
    (world.settings / "gui_settings.json").write_text("{ nope")
    app = gui.start()
    gui.pump(0.5)
    warnings = [m for kind, _, m in gui.dialogs.messages if kind == "warn"]
    assert warnings and "could not be read" in warnings[0]
    assert app.core_settings is None
