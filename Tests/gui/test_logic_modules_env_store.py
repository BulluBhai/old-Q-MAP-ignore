"""Pure-logic tests (no window): module readiness, environment check and remembered settings."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Application"))

from qmap_gui import environment
from qmap_gui.modules import (ANALYTICAL_WORKBENCH, COMING_SOON, DATABASE_MANAGER, MODULES, READY, modules_for,
                              ready_modules)
from qmap_gui.settings_store import (ENV_SETTINGS_DIR, GuiSettings, GuiSettingsStore, StoreError,
                                     default_settings_dir)

REPO = Path(__file__).resolve().parents[2]


# ---- module readiness is genuine ---------------------------------------------------------------------
def test_only_genuinely_working_modules_are_ready():
    # Requirement changed 01-Nov-26 (two applications): Database Manager has Data Management and Datasets and
    # Storage; Analytical Workbench has Dataset Summary. Changed 02-Nov-26 (Blueprint v1.3 §8.5): Database Manager
    # also has Sources (automatic loading). Everything else must stay COMING SOON.
    assert [(m.key, m.app) for m in ready_modules()] == [("sources", DATABASE_MANAGER),
                                                         ("data_management", DATABASE_MANAGER),
                                                         ("datasets", DATABASE_MANAGER),
                                                         ("dataset_summary", ANALYTICAL_WORKBENCH)]
    assert all(m.status in (READY, COMING_SOON) for m in MODULES)
    assert len({m.key for m in MODULES}) == len(MODULES)
    assert all(m.screen for m in ready_modules()) and not any(m.screen for m in MODULES if not m.is_ready)


def test_research_modules_belong_to_the_workbench_and_data_preparation_to_the_database_manager():
    assert {m.key for m in modules_for(DATABASE_MANAGER)} == {"sources", "data_management", "datasets"}
    research = {m.key for m in modules_for(ANALYTICAL_WORKBENCH)}
    assert {"market_intelligence", "ma_research", "stage_analysis", "dataset_summary"} <= research
    assert "data_management" not in research


def test_every_planned_module_is_listed_by_one_of_the_two_applications():
    assert {m.key for m in MODULES} == {m.key for a in (DATABASE_MANAGER, ANALYTICAL_WORKBENCH) for m in modules_for(a)}


def test_every_coming_soon_module_says_where_it_sits_on_the_roadmap():
    for m in MODULES:
        assert m.note.strip() and m.description.strip()
        if not m.is_ready:
            assert "Stage" in m.note or "no screen or workflow" in m.note, m.key


def test_blueprint_modules_are_all_listed():
    names = " ".join(m.name for m in MODULES)
    for expected in ("Dashboard", "Market Overview", "Sector Explorer", "Stock Explorer", "Opportunity Scanner",
                     "Price Behaviour Lab", "Strategy Backtesting Lab", "Portfolio and Risk", "Research Library",
                     "Market Intelligence", "MA Research", "CPR", "Ichimoku", "Candlestick", "Volume Research", "Proprietary"):
        assert expected in names


def test_data_management_is_honest_about_what_is_not_built():
    for m in ready_modules(DATABASE_MANAGER):
        assert "Not built yet" in m.note


# ---- environment check ----------------------------------------------------------------------------------
def test_this_environment_can_run_qmap_or_says_exactly_what_is_missing():
    import importlib.util

    problems = environment.describe_environment()
    if importlib.util.find_spec("tkinter") is None:
        assert len(problems) == 1 and "tkinter" in problems[0]  # nothing else is wrong; the one gap is explained
    else:
        assert problems == []


def test_missing_package_is_explained_with_the_exact_command(monkeypatch):
    real = environment.importlib.util.find_spec
    monkeypatch.setattr(environment.importlib.util, "find_spec", lambda name: None if name == "pyarrow" else real(name))
    problems = environment.describe_environment()
    text = "\n".join(problems)
    assert "pyarrow" in text and "pip install pyarrow" in text and sys.executable in text
    assert environment.missing_packages() == ["pyarrow"]


def test_old_python_gets_an_actionable_message(monkeypatch):
    monkeypatch.setattr(environment.sys, "version_info", (3, 9, 1, "final", 0))
    msg = environment.python_problem()
    assert "3.11" in msg and "3.9.1" in msg and "Thonny" in msg and "IDLE" in msg


def test_missing_tkinter_is_explained(monkeypatch):
    real = environment.importlib.util.find_spec
    monkeypatch.setattr(environment.importlib.util, "find_spec", lambda name: None if name == "tkinter" else real(name))
    assert "tkinter" in environment.tkinter_problem() and "python.org" in environment.tkinter_problem()


def test_install_runs_pip_with_this_python_and_reports_failure(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no internet")

    monkeypatch.setattr(environment.subprocess, "run", fake_run)
    ok, output = environment.install_packages(["numpy"])
    assert not ok and "no internet" in output
    assert calls == [[sys.executable, "-m", "pip", "install", "numpy"]]


def test_install_handles_pip_not_runnable(monkeypatch):
    def boom(*a, **k):
        raise OSError("nope")

    monkeypatch.setattr(environment.subprocess, "run", boom)
    ok, output = environment.install_packages(["numpy"])
    assert not ok and "Could not run pip" in output


# ---- remembered settings are stored outside the repository -----------------------------------------------
@pytest.mark.parametrize("platform,env,expected_part", [
    ("win32", {"APPDATA": "C:\\Users\\me\\AppData\\Roaming"}, "Q-MAP"),
    ("darwin", {}, "Application Support"),
    ("linux", {"XDG_CONFIG_HOME": "/home/me/.cfg"}, "q-map"),
])
def test_default_location_is_the_users_own_settings_folder(platform, env, expected_part):
    path = default_settings_dir(env, platform)
    assert expected_part in str(path)
    assert REPO not in path.parents and path != REPO


def test_environment_override_for_the_settings_folder(tmp_path):
    assert default_settings_dir({ENV_SETTINGS_DIR: str(tmp_path / "x")}, "linux") == tmp_path / "x"


def test_settings_cannot_be_stored_inside_the_code_repository(tmp_path):
    code = tmp_path / "code"
    (code / "inner").mkdir(parents=True)
    with pytest.raises(StoreError, match="outside the Q-MAP code repository"):
        GuiSettingsStore(code / "inner", code)
    with pytest.raises(StoreError):
        GuiSettingsStore(code, code)


def test_save_and_load_round_trip_and_atomic_write(tmp_path):
    store = GuiSettingsStore(tmp_path / "s", tmp_path / "code")
    assert store.load() == GuiSettings()
    store.save(GuiSettings(data_root="D", output_root="O", last_profile="p.toml", source_label="vendor"))
    assert GuiSettingsStore(tmp_path / "s", tmp_path / "code").load().data_root == "D"
    assert not [p for p in (tmp_path / "s").iterdir() if p.name.endswith(".tmp")]
    assert store.profiles_dir == (tmp_path / "s").resolve() / "profiles"


def test_corrupt_settings_file_falls_back_with_a_plain_warning(tmp_path):
    store = GuiSettingsStore(tmp_path / "s", tmp_path / "code")
    (tmp_path / "s").mkdir()
    store.path.write_text("{ not json")
    assert store.load() == GuiSettings()
    assert "could not be read" in store.load_warning and "Nothing else is affected" in store.load_warning


def test_unknown_keys_in_the_settings_file_are_ignored(tmp_path):
    store = GuiSettingsStore(tmp_path / "s", tmp_path / "code")
    (tmp_path / "s").mkdir()
    store.path.write_text('{"data_root": "D", "future_option": 1}')
    assert store.load().data_root == "D"


def test_unwritable_settings_location_gives_a_plain_message(tmp_path):
    blocker = tmp_path / "file_not_folder"
    blocker.write_text("x")
    store = GuiSettingsStore(blocker / "sub", tmp_path / "code")
    with pytest.raises(StoreError, match="could not be remembered"):
        store.save(GuiSettings())
