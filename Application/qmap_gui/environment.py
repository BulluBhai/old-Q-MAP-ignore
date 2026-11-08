"""Check that this Python can run Q-MAP, in words a non-programmer can act on. No third-party imports here."""

from __future__ import annotations

import importlib.util
import subprocess
import sys

MIN_PYTHON = (3, 11)
# (import name, pip name)
REQUIRED_PACKAGES = (("numpy", "numpy"), ("pyarrow", "pyarrow"), ("openpyxl", "openpyxl"), ("tzdata", "tzdata"))


def python_problem() -> str | None:
    if sys.version_info < MIN_PYTHON:
        have = ".".join(map(str, sys.version_info[:3]))
        return (f"Q-MAP needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer, but this is Python {have}.\n"
                "In Thonny: Tools > Options > Interpreter, and choose a newer Python (or the Q-MAP environment).\n"
                "In IDLE: start IDLE from a newer Python installation.")
    return None


def missing_packages() -> list[str]:
    """pip names of the required packages this Python cannot import."""
    return [pip for mod, pip in REQUIRED_PACKAGES if importlib.util.find_spec(mod) is None]


def tkinter_problem() -> str | None:
    if importlib.util.find_spec("tkinter") is None:
        return ("This Python does not include tkinter, which Q-MAP's window needs.\n"
                "Windows/macOS: reinstall Python from python.org and keep 'tcl/tk and IDLE' ticked.\n"
                "Linux: install the 'python3-tk' package.")
    return None


def pip_install_command(packages: list[str]) -> list[str]:
    return [sys.executable, "-m", "pip", "install", *packages]


def describe_environment() -> list[str]:
    """Plain-English problems that stop Q-MAP starting (empty list = ready to start)."""
    problems = []
    for p in (python_problem(), tkinter_problem()):
        if p:
            problems.append(p)
    missing = missing_packages()
    if missing:
        problems.append("These required Python packages are not installed: " + ", ".join(missing) + ".\n"
                        "Install them with this command (it installs into the Python you are running now):\n  "
                        + " ".join(pip_install_command(missing)))
    return problems


def install_packages(packages: list[str]) -> tuple[bool, str]:
    """Run pip for the given packages. Returns (success, output text)."""
    try:
        done = subprocess.run(pip_install_command(packages), capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Could not run pip: {exc}"
    return done.returncode == 0, (done.stdout + "\n" + done.stderr).strip()
