"""A closed Tk window left in a reference cycle must be freed on the main thread (Tests/gui/conftest.py).

If the cyclic garbage collector frees it in another thread, Tcl aborts the whole process: this is what made full test
runs crash with "Illegal instruction" or "Segmentation fault" inside the threads of Tests/unit/test_runs.py."""

import os
import subprocess
import sys

import pytest

pytest.importorskip("tkinter")

from gui import conftest  # noqa: E402

SCENARIO = '''
import gc, sys, threading, tkinter
sys.path[:0] = [{tests!r}, {app!r}]
from gui import conftest
root = tkinter.Tk(); root.cycle = root; root.update(); root.destroy()  # closed, but kept alive by a reference cycle
gc.disable(); del root  # garbage now, waiting for the cyclic collector
if sys.argv[1] == "with_cleanup":
    conftest.collect_tk_garbage_on_the_main_thread()
worker = threading.Thread(target=gc.collect); worker.start(); worker.join()  # what a later test's thread may do
print("process survived")
'''


def run_scenario(tmp_path, mode):
    script = tmp_path / "scenario.py"
    script.write_text(SCENARIO.format(tests=str(conftest.REPO / "Tests"), app=str(conftest.REPO / "Application")),
                      encoding="utf-8")
    return subprocess.run([sys.executable, str(script), mode], capture_output=True, text=True, timeout=120,
                          env=dict(os.environ))


def test_a_closed_window_freed_on_the_main_thread_cannot_crash_a_later_thread(display, tmp_path):
    proc = run_scenario(tmp_path, "with_cleanup")
    assert proc.returncode == 0 and "process survived" in proc.stdout, proc.stdout + proc.stderr
