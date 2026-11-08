"""Where GUI tests are required (QMAP_REQUIRE_GUI_TESTS=1, set on the Windows CI job), a Tk start-up failure must make
the run fail; elsewhere the window tests may still skip. Checked by running pytest itself with Tk deliberately broken."""

import os
import subprocess
import sys
from collections import Counter

import pytest

from gui import conftest

# Loaded into the inner pytest with -p: every attempt to create a Tcl/Tk interpreter fails, inside tkinter's own
# Tk.__init__, exactly like the start-up fault seen on GitHub's Windows runner (so the retry runs and then gives up).
BREAK_TK = '''
import tkinter

def _broken_create(*args, **kwargs):
    raise tkinter.TclError("Can't find a usable init.tcl (deliberately broken for a test)")

tkinter._tkinter.create = _broken_create
'''

WINDOW_TESTS = "Tests/gui/test_window_home_and_folders.py"


def run_inner_pytest(tmp_path, required: str):
    (tmp_path / "break_tk.py").write_text(BREAK_TK, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(tmp_path) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    env[conftest.REQUIRE_GUI_TESTS_ENV] = required
    env.pop("GITHUB_STEP_SUMMARY", None)  # the inner run must not write into the outer CI summary
    proc = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "break_tk", "-q",
                           WINDOW_TESTS], cwd=conftest.REPO, env=env, capture_output=True, text=True, timeout=300)
    return proc.returncode, proc.stdout + proc.stderr


def test_broken_tk_start_fails_the_run_where_gui_tests_are_required(tmp_path):
    pytest.importorskip("tkinter")  # Tk is broken deliberately, so it must exist
    code, out = run_inner_pytest(tmp_path, "1")
    assert code != 0, out
    assert "GUI tests: 0 passed, 0 skipped" in out and "(required here: yes)" in out
    assert "could not open a window" in out and "FAILED: no GUI test ran" in out


def test_broken_tk_start_still_skips_where_gui_tests_are_not_required(tmp_path):
    pytest.importorskip("tkinter")  # Tk is broken deliberately, so it must exist
    code, out = run_inner_pytest(tmp_path, "0")
    assert code == 0, out
    assert "GUI tests: 0 passed" in out and "(required here: no)" in out and "FAILED:" not in out
    assert "no usable display for tkinter" in out


def test_any_skipped_gui_test_fails_a_required_run():
    assert conftest.gui_summary_problem(Counter(passed=120, skipped=1), True).startswith("1 GUI test(s) were skipped")


def test_a_required_run_in_which_no_gui_test_ran_fails():
    assert conftest.gui_summary_problem(Counter(), True).startswith("no GUI test ran")
    assert conftest.gui_summary_problem(Counter(error=46), True).startswith("no GUI test ran")


def test_a_complete_required_run_and_any_unrequired_run_pass():
    assert conftest.gui_summary_problem(Counter(passed=127), True) == ""
    assert conftest.gui_summary_problem(Counter(skipped=46), False) == ""
