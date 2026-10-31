"""The GUI stays separate from processing, storage and the registry; nothing is written into the repository."""

import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUI = REPO / "Application" / "qmap_gui"
SCREEN_FILES = ("app.py", "home.py", "data_management.py", "profile_editor.py", "locations.py", "widgets.py")


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
