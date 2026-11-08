"""Fixtures for the GUI tests. Real-window tests need a display (a desktop, or `xvfb-run` on Linux); without one they are skipped."""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Application"))

from fixtures.builders import HEADER, daily_rows, write_delimited  # noqa: E402

NET_HEADER = HEADER + ["Net Volume"]

TK_STARTUP_ATTEMPTS = 3

# Set to 1 where a desktop is guaranteed (the Windows CI job). Then the GUI tests are REQUIRED: a Tk/display start-up
# failure fails the window tests instead of skipping them, and the run fails if any GUI test was skipped or none ran.
# Unset (a laptop without tkinter, a Linux server without a screen) the window tests may still skip, as before.
REQUIRE_GUI_TESTS_ENV = "QMAP_REQUIRE_GUI_TESTS"
GUI_NODE_PREFIX = "Tests/gui/"


def gui_tests_required() -> bool:
    return os.environ.get(REQUIRE_GUI_TESTS_ENV, "").strip() == "1"


def failed_while_creating_the_tk_interpreter(exc: BaseException) -> bool:
    """True if a TclError was raised inside tkinter's own `Tk.__init__` / `_loadtk`, i.e. while the Tcl/Tk interpreter
    was being created, before any application code could run. Errors raised later (for example while the application
    builds its widgets) have no such frame in their traceback. A missing display is not a start-up fault."""
    import tkinter

    text = str(exc).lower()
    if "display" in text:  # "no display name and no $DISPLAY environment variable", "couldn't connect to display"
        return False
    tb = exc.__traceback__
    while tb is not None:
        frame = tb.tb_frame
        if (frame.f_globals.get("__name__") == "tkinter" and frame.f_code.co_name in ("__init__", "_loadtk")
                and isinstance(frame.f_locals.get("self"), tkinter.Tk)):
            return True
        tb = tb.tb_next
    return False


def create_with_tk_startup_retry(make):
    """Call `make()` (which creates a Tk window), retrying ONLY a failure of Tk's own start-up.

    On GitHub's Windows runner the Tcl/Tk interpreter occasionally fails to start because Tk cannot read its own library
    files from the Python install. The symptom varies from run to run: "Can't find a usable init.tcl",
    "couldn't read file ...auto.tcl: no such file or directory" (for a file that exists), or
    'invalid command name "tcl_findLibrary"'. All happen inside `Tk.__init__`, before any Q-MAP code runs, and the next
    window starts normally. So the rule is by phase, not by message: only a TclError raised inside Tk's own
    interpreter creation is retried (up to `TK_STARTUP_ATTEMPTS` attempts), every retry is reported as a warning, and
    anything else - including an error while the application builds its window, or a missing display - is raised at
    once. No assertion of any test is affected.
    """
    import time
    import tkinter
    import warnings

    for attempt in range(1, TK_STARTUP_ATTEMPTS + 1):
        try:
            return make()
        except tkinter.TclError as exc:
            if not failed_while_creating_the_tk_interpreter(exc) or attempt == TK_STARTUP_ATTEMPTS:
                raise
            warnings.warn(f"Tk start-up failed (attempt {attempt} of {TK_STARTUP_ATTEMPTS}), retrying: "
                          f"{str(exc).splitlines()[0]}", RuntimeWarning, stacklevel=2)
            time.sleep(0.5 * attempt)


def dd_mm_yy_rows(n=12, seed=1):
    return [[datetime.fromisoformat(r[0]).strftime("%d-%m-%y")] + r[1:] + [r[5] // 3] for r in daily_rows(n, seed)]


@pytest.fixture
def world(tmp_path):
    """Four separate folders (all outside the repository) and two synthetic files in the dd-mm-yy layout."""
    w = type("World", (), {})()
    for name in ("data", "output", "src", "settings"):
        setattr(w, name, tmp_path / name)
        getattr(w, name).mkdir()
    w.good = write_delimited(w.src / "NSE_NIFTY_1D1.csv", NET_HEADER, dd_mm_yy_rows())
    bad = dd_mm_yy_rows(12, 2)
    bad[3][3] = 99999  # low far above high
    bad[8][4] = "N/A"  # not a number
    w.bad = write_delimited(w.src / "NSE_BADFILE_1D.csv", NET_HEADER, bad)
    w.repo = REPO
    return w


@pytest.fixture(scope="session")
def display():
    try:
        import tkinter

        create_with_tk_startup_retry(tkinter.Tk).destroy()
    except Exception as exc:  # no display / no tkinter
        if gui_tests_required():
            pytest.fail(f"{REQUIRE_GUI_TESTS_ENV}=1 but tkinter could not open a window: {exc}", pytrace=False)
        pytest.skip(f"no usable display for tkinter ({exc}). Run under xvfb-run, or on a desktop.")


def repo_snapshot() -> set:
    skip = {"__pycache__", ".git", ".pytest_cache", "qmap.egg-info"}
    out = set()
    for p in REPO.rglob("*"):
        if p.is_file() and not (skip & set(p.relative_to(REPO).parts)) and not p.suffix == ".pyc":
            out.add(str(p.relative_to(REPO)))
    return out


class Gui:
    """Creates real windows, pumps their event loop and tidies up."""

    def __init__(self, world):
        from gui.fakes import FakeDialogs

        self.world, self.dialogs, self.apps = world, FakeDialogs(), []

    def start(self, settings_dir=None):
        from qmap_gui.app import QMapApp

        app = create_with_tk_startup_retry(
            lambda: QMapApp(REPO, settings_dir=settings_dir or self.world.settings, dialogs=self.dialogs))
        app.geometry("1100x900+0+0")
        self.apps.append(app)
        self.pump(0.05, app)
        return app

    def pump(self, seconds=0.2, app=None):
        import time

        app = app or self.apps[-1]
        end = time.time() + seconds
        while time.time() < end:
            app.update()
            time.sleep(0.01)

    def wait(self, condition, timeout=60, app=None):
        import time

        app = app or self.apps[-1]
        end = time.time() + timeout
        while time.time() < end and not condition():
            app.update()
            time.sleep(0.01)
        assert condition(), "timed out waiting for the window"

    def choose_folders(self, app, data=None, output=None):
        app.data_var.set(str(data or self.world.data))
        app.output_var.set(str(output or self.world.output))
        assert app.apply_locations()

    def close(self):
        import gc

        from qmap_gui.app import release_garbage_collector_if_idle

        for app in self.apps:
            if not getattr(app, "_closing", False):
                app._on_closing()
            app.tasks.join_all(30)
        self.apps.clear()
        release_garbage_collector_if_idle()
        gc.collect()  # leftover windows are freed here, on the main thread, never inside a worker thread


@pytest.fixture
def gui(world, display):
    g = Gui(world)
    yield g
    g.close()


# ---- closed windows are freed on the main thread, before any later test can start threads ---------------------------
def collect_tk_garbage_on_the_main_thread() -> None:
    """Free, now and on this (the main) thread, every Tk window that is no longer used but still sits in a reference
    cycle. Otherwise the cyclic garbage collector frees it later in whichever thread happens to allocate memory - for
    example the 20 threads of `Tests/unit/test_runs.py` - and Tcl aborts the whole test process ("Tcl_AsyncDelete:
    async handler deleted by the wrong thread"), seen as "Illegal instruction" or "Segmentation fault". The same hazard
    inside the application is handled by D3-08 (`qmap_gui.app._hold_garbage_collector`)."""
    import gc

    gc.collect()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    yield
    # Only here are the test's fixture values (windows, frames) released: a fixture's own teardown is too early.
    if item.nodeid.replace("\\", "/").startswith(GUI_NODE_PREFIX):
        collect_tk_garbage_on_the_main_thread()


# ---- GUI test accounting: visible in every run, enforced where GUI tests are required -------------------------------
_gui_outcomes: Counter = Counter()


def _is_gui(report) -> bool:
    return report.nodeid.replace("\\", "/").startswith(GUI_NODE_PREFIX)


def pytest_runtest_logreport(report):
    """One count per GUI test: its call outcome, or the setup outcome if it never got that far, plus teardown errors."""
    if not _is_gui(report):
        return
    if report.when == "call":
        _gui_outcomes[report.outcome] += 1
    elif report.when == "setup" and not report.passed:
        _gui_outcomes["skipped" if report.skipped else "error"] += 1
    elif report.when == "teardown" and report.failed:
        _gui_outcomes["error"] += 1


def pytest_collectreport(report):
    """A whole GUI test module skipped at import (e.g. importorskip("tkinter")) or failing to import."""
    if _is_gui(report) and not report.passed:
        _gui_outcomes["skipped" if report.skipped else "error"] += 1


def gui_summary_problem(outcomes: Counter, required: bool) -> str:
    """Why a run whose GUI tests are required must fail, or "" if it need not."""
    if not required:
        return ""
    if outcomes["skipped"]:
        return f"{outcomes['skipped']} GUI test(s) were skipped although {REQUIRE_GUI_TESTS_ENV}=1"
    if not outcomes["passed"] + outcomes["failed"]:
        return f"no GUI test ran although {REQUIRE_GUI_TESTS_ENV}=1"
    return ""


def pytest_sessionfinish(session, exitstatus):
    if gui_summary_problem(_gui_outcomes, gui_tests_required()) and session.exitstatus == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    o, required = _gui_outcomes, gui_tests_required()
    line = (f"GUI tests: {o['passed']} passed, {o['skipped']} skipped, {o['failed']} failed, {o['error']} errors "
            f"(required here: {'yes' if required else 'no'})")
    problem = gui_summary_problem(o, required)
    bad = bool(problem or o["failed"] or o["error"])
    terminalreporter.write_sep("-", line, red=bad, green=not bad)
    if problem:
        terminalreporter.write_line(f"FAILED: {problem}.", red=True)
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as fh:
                fh.write(f"**{line}**" + (f"  \n**FAILED: {problem}.**" if problem else "") + "\n")
        except OSError:
            pass
