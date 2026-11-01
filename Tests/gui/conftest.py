"""Fixtures for the GUI tests. Real-window tests need a display (a desktop, or `xvfb-run` on Linux); without one they are skipped."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Application"))

from fixtures.builders import HEADER, daily_rows, write_delimited  # noqa: E402

NET_HEADER = HEADER + ["Net Volume"]

TK_STARTUP_ATTEMPTS = 3


def is_tk_library_read_failure(exc: Exception) -> bool:
    """Tk could not read one of its own library files while creating the interpreter (two known message forms)."""
    text = str(exc)
    return "Can't find a usable" in text or "couldn't read file" in text


def create_with_tk_startup_retry(make):
    """Call `make()` (which creates a Tk window), retrying ONLY Tk's own start-up failure.

    On GitHub's Windows runner a window occasionally fails to start because Tk cannot read one of its own library
    files (init.tcl, auto.tcl, tk.tcl, ttk/*.tcl) from the Python install: "Can't find a usable init.tcl", or
    "couldn't read file ...: No error" / "no such file or directory" for a file that exists. It happens while the
    interpreter is being created, before any Q-MAP code runs, and the next window starts normally.
    Only those two message forms are retried, and every retry is reported as a warning; any other error is raised at
    once, and a start-up that keeps failing is raised after `TK_STARTUP_ATTEMPTS` attempts. No assertion of any test is
    affected.
    """
    import time
    import tkinter
    import warnings

    for attempt in range(1, TK_STARTUP_ATTEMPTS + 1):
        try:
            return make()
        except tkinter.TclError as exc:
            if not is_tk_library_read_failure(exc) or attempt == TK_STARTUP_ATTEMPTS:
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
