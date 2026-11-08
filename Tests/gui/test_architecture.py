"""The GUI stays separate from processing, storage and the registry; nothing is written into the repository."""

import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUI = REPO / "Application" / "qmap_gui"
SCREEN_FILES = ("app.py", "home.py", "data_management.py", "profile_editor.py", "locations.py", "widgets.py",
                "datasets.py", "analysis.py")


def run_python(code: str) -> str:
    """Run code in a fresh Python that sees only this checkout (not any installed copy of qmap)."""
    code = f"import sys; sys.path.insert(0, {str(REPO / 'Application')!r})\n" + code
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def imports_of(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = ("." * node.level) + (node.module or "")
            names.add(module)
            names.update(f"{module}.{a.name}" for a in node.names)
    return names


def test_the_foundation_never_imports_the_gui_or_tkinter():
    out = run_python(
        "import sys, qmap, qmap.cli, qmap.core.config, qmap.core.runs, qmap.data_engine.ingest, qmap.data_engine.preview, "
        "qmap.storage.registry, qmap.storage.recovery\n"
        "print('qmap_gui' in sys.modules, 'tkinter' in sys.modules)")
    assert out == "False False"


def test_the_gui_logic_layer_has_no_tkinter():
    out = run_python(
        "import sys\n"
        "import qmap_gui.services, qmap_gui.jobs, qmap_gui.messages, qmap_gui.settings_store, qmap_gui.modules, qmap_gui.environment\n"
        "import qmap_gui.registry_services, qmap_gui.workbench_services, qmap_gui.common, qmap_gui.launch\n"
        "print('tkinter' in sys.modules)")
    assert out == "False"


def test_screens_contain_no_processing_storage_or_registry_code():
    """Screens may import only tkinter, the GUI package itself and the two version constants from `qmap`."""
    for name in SCREEN_FILES:
        for imported in imports_of(GUI / name):
            allowed = imported in ("qmap.__version__", "qmap.CLEANING_CODE_VERSION")  # the two version constants
            assert allowed or not imported.startswith("qmap."), f"{name} imports Foundation code directly: {imported}"
            assert imported not in ("sqlite3", "pyarrow", "openpyxl", "numpy", "csv", "hashlib"), f"{name} imports {imported}"
    assert imports_of(GUI / "home.py") & {"qmap"}  # only the version constants


def test_logic_layer_uses_the_foundation_public_services_not_its_own_copies():
    source = (GUI / "services.py").read_text() + (GUI / "jobs.py").read_text()
    for needed in ("load_settings", "run_context", "ingest_file", "preview_file", "process_table", "load_profile"):
        assert needed in source
    for forbidden in ("def parse_times", "def validate_group", "def read_delimited", "CREATE TABLE", "sha256_file("):
        assert forbidden not in source


def test_the_launcher_is_at_the_top_level_and_needs_no_installation_step():
    launcher = (REPO / "Q-MAP.py").read_text()
    compile(launcher, "Q-MAP.py", "exec")
    assert 'sys.path.insert(0, str(HERE / "Application"))' in launcher
    top_level = {n.names[0].name.split(".")[0] for n in ast.parse(launcher).body if isinstance(n, ast.Import)}
    top_level |= {n.module.split(".")[0] for n in ast.parse(launcher).body if isinstance(n, ast.ImportFrom) and n.module}
    assert top_level <= {"sys", "pathlib"}  # nothing third-party at import time: problems are explained, not crashed on


# ---- two applications, one platform (01-Nov-26) -----------------------------------------------------------------
ENTRY_POINTS = ("database_manager.py", "analytical_workbench.py", "Q-MAP.py")
DATA_PREPARATION = ("qmap.data_engine.ingest", "qmap.data_engine.process", "qmap.data_engine.profiles",
                    "qmap.data_engine.readers", "qmap.data_engine.preview", "qmap.data_engine.derive",
                    "qmap.storage.registry", "qmap.storage.storage_class", "qmap_gui.jobs", "qmap_gui.services",
                    "qmap_gui.registry_services", "qmap_gui.data_management", "qmap_gui.datasets",
                    "qmap.data_engine.discovery", "qmap.data_engine.auto_interpret", "qmap_gui.source_services",
                    "qmap_gui.sources")


def test_both_entry_points_are_in_the_application_folder_and_need_no_installation_step():
    for name in ENTRY_POINTS:
        launcher = (REPO / name).read_text()
        compile(launcher, name, "exec")
        assert 'sys.path.insert(0, str(HERE / "Application"))' in launcher, name
        tree = ast.parse(launcher)
        top = {n.names[0].name.split(".")[0] for n in tree.body if isinstance(n, ast.Import)}
        top |= {n.module.split(".")[0] for n in tree.body if isinstance(n, ast.ImportFrom) and n.module}
        assert top <= {"sys", "pathlib"}, name
    assert 'APP_KEY = "database_manager"' in (REPO / "database_manager.py").read_text()
    assert 'APP_KEY = "analytical_workbench"' in (REPO / "analytical_workbench.py").read_text()


def test_the_workbench_never_loads_data_preparation_code():
    """The Workbench analyses prepared data only: its screen, logic and engine must not import ingestion,
    profiles, readers, registration, storage changes or the Database Manager's screens."""
    out = run_python(
        "import sys, qmap_gui.workbench_services, qmap.analytical_engine, qmap.catalog\n"
        f"print(sorted(m for m in sys.modules if m in {DATA_PREPARATION!r}))")
    assert out == "[]"
    for imported in imports_of(GUI / "analysis.py"):
        assert imported not in (".services", ".jobs", ".data_management", ".registry_services", ".datasets",
                                ".source_services", ".sources"), imported


def test_both_applications_share_one_registry_and_one_data_definition():
    """One authoritative implementation: both logic layers use qmap.catalog, neither defines its own SQL."""
    for name in ("registry_services.py", "workbench_services.py", "source_services.py"):
        source = (GUI / name).read_text()
        assert "from qmap.catalog import" in source, name
        for forbidden in ("SELECT ", "INSERT ", "UPDATE ", "CREATE TABLE", "sqlite3"):
            assert forbidden not in source, f"{name} contains {forbidden!r}"


def test_the_analytical_engine_does_not_depend_on_any_gui():
    out = run_python("import sys, qmap.analytical_engine, qmap.catalog\n"
                     "print('qmap_gui' in sys.modules, 'tkinter' in sys.modules)")
    assert out == "False False"
