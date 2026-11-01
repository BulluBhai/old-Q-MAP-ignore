"""Real-window tests: the clean-shutdown sequence, the polling loops, and the F5 launcher."""

import importlib.util
import os
import subprocess
import sys

import pytest

tk = pytest.importorskip("tkinter")

from gui.conftest import REPO
from qmap_gui import jobs
import time


def spy_on_closing(app):
    order = []

    def wrap(obj, name, label, *, first_only=False):
        original = getattr(obj, name)

        def recorder(*a, **k):
            if not (first_only and label in order):
                order.append(label)
                if label == "pack_forget":
                    order.append(f"closing_flag={app._closing}")
            return original(*a, **k)

        setattr(obj, name, recorder)

    wrap(app._scroll_frame, "pack_forget", "pack_forget")
    wrap(app._scroll_frame, "destroy", "scroll_destroy")
    wrap(app, "withdraw", "withdraw")
    wrap(app, "after_cancel", "after_cancel", first_only=True)
    wrap(app, "destroy", "destroy")
    return order


def test_closing_runs_the_steps_in_the_required_order(gui):
    app = gui.start()
    gui.pump(0.3)  # lets the polling loops register their after() callbacks
    order = spy_on_closing(app)
    assert app._closing is False
    app._on_closing()
    assert app._closing is True
    assert order == ["pack_forget", "closing_flag=True", "scroll_destroy", "withdraw", "after_cancel", "destroy"]
    with pytest.raises(tk.TclError):
        app.winfo_exists() and app.update()


def test_stdout_is_restored_if_it_was_redirected(gui):
    app = gui.start()
    real = sys.stdout

    class Redirect:
        def write(self, text):
            pass

        def flush(self):
            pass

    app._orig_stdout = real
    sys.stdout = Redirect()
    try:
        app._on_closing()
        assert sys.stdout is real
    finally:
        sys.stdout = real


def test_pending_timers_are_cancelled_and_loops_stop_rescheduling(gui):
    app = gui.start()
    dm = app.screens["data"]
    gui.pump(0.3)
    assert app.tk.call("after", "info")  # timers are pending while the app is open
    app._on_closing()
    # after closing, every recurring callback must return at once: it must NOT schedule itself again
    rescheduled = []
    app.after = lambda *a, **k: rescheduled.append(("app", a))
    dm.after = lambda *a, **k: rescheduled.append(("data_management", a))
    app.tasks._poll()
    dm._tick()
    assert rescheduled == [] and app._closing and dm._closing


def test_the_polling_loops_do_reschedule_themselves_while_the_app_is_open(gui):
    app = gui.start()
    dm = app.screens["data"]
    seen = []
    real_app_after, real_dm_after = app.after, dm.after
    app.after = lambda *a, **k: (seen.append("poll"), real_app_after(*a, **k))[1]
    dm.after = lambda *a, **k: (seen.append("tick"), real_dm_after(*a, **k))[1]
    gui.pump(0.8)
    assert "poll" in seen and "tick" in seen  # proves the check above is meaningful


def test_closing_twice_is_harmless(gui):
    app = gui.start()
    app._on_closing()
    app._on_closing()


def test_closing_while_a_load_is_running_stops_it_after_the_current_file(gui, world, monkeypatch):
    real = jobs.ingest_file
    started = []

    def slow(*a, **k):
        started.append(1)
        time.sleep(0.3)
        return real(*a, **k)

    monkeypatch.setattr(jobs, "ingest_file", slow)
    from fixtures.builders import write_delimited
    from gui.conftest import NET_HEADER, dd_mm_yy_rows

    files = [write_delimited(world.src / f"NSE_C{i}_1D.csv", NET_HEADER, dd_mm_yy_rows(6, i)) for i in range(1, 6)]
    app = gui.start()
    gui.choose_folders(app)
    dm = app.screens["data"]
    dm.add_paths(files)
    idx = next(i for i, p in enumerate(dm.profile_infos) if p.profile and p.profile.profile_id == "csv_hdr_ddmmyy_idfromname")
    dm.select_profile_index(idx)
    dm.start_ingest()
    gui.wait(lambda: started)
    app._on_closing()  # the window is closed mid-load
    app.tasks.join_all(60)  # the worker finishes its current file and stops; the app must not crash
    assert len(started) < 5
    from qmap.storage.db import open_database

    db = open_database(world.data / "Metadata" / "qmap_metadata.sqlite")
    try:
        # the Foundation's registry is consistent: every started receipt reached a final state, no half results
        assert db.one("SELECT COUNT(*) c FROM ingest_events WHERE status='started'")["c"] == 0
        assert db.one("SELECT COUNT(*) c FROM runs WHERE status='running'")["c"] == 0
    finally:
        db.close()


# ---- launcher ---------------------------------------------------------------------------------------------------
def test_launcher_opens_the_window_and_closes_it_cleanly(gui, world):
    done = subprocess.run([sys.executable, str(REPO / "Q-MAP.py"), "--selftest", "--settings-dir", str(world.settings)],
                          capture_output=True, text=True, timeout=120, env=dict(os.environ), cwd=world.src)
    assert done.returncode == 0, done.stderr
    assert "SELFTEST OK" in done.stdout


def load_launcher():
    spec = importlib.util.spec_from_file_location("qmap_launcher", REPO / "Q-MAP.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_explains_a_missing_package_and_offers_to_install_it(monkeypatch):
    from qmap_gui import environment

    launcher = load_launcher()
    shown = []
    monkeypatch.setattr(environment, "describe_environment", lambda: ["These required Python packages are not installed: pyarrow."])
    monkeypatch.setattr(environment, "missing_packages", lambda: ["pyarrow"])
    monkeypatch.setattr(launcher, "_show_problem", lambda text, offer=None: shown.append((text, offer)))
    assert launcher.main() == 1
    assert "pyarrow" in shown[0][0] and shown[0][1] == ["pyarrow"]


def test_launcher_does_not_offer_to_install_when_python_itself_is_too_old(monkeypatch):
    from qmap_gui import environment

    launcher = load_launcher()
    shown = []
    monkeypatch.setattr(environment, "python_problem", lambda: "Q-MAP needs Python 3.11 or newer")
    monkeypatch.setattr(environment, "describe_environment", lambda: ["Q-MAP needs Python 3.11 or newer"])
    monkeypatch.setattr(launcher, "_show_problem", lambda text, offer=None: shown.append((text, offer)))
    assert launcher.main() == 1 and shown[0][1] is None


def test_launcher_adds_only_the_application_folder_to_the_path():
    launcher = load_launcher()
    assert str(REPO / "Application") in sys.path and launcher.HERE == REPO


def test_garbage_collection_is_held_off_while_a_worker_runs_and_resumes_on_the_main_thread(gui):
    """Tk objects must never be garbage-collected inside a worker thread (Tcl would abort the whole program)."""
    import gc
    import threading

    app = gui.start()
    gc_state_in_worker, main_thread_collect = [], []
    done = threading.Event()

    def work(emit):
        time.sleep(0.3)
        gc_state_in_worker.append(gc.isenabled())
        emit({"type": "finished"})
        done.set()

    assert gc.isenabled()
    app.tasks.start(work, lambda event: None, lambda message: None)
    assert gc.isenabled() is False  # off before the worker even starts running
    gui.wait(done.is_set)
    gui.wait(lambda: gc.isenabled(), timeout=10)  # switched back on by the main thread once the worker has ended
    assert gc_state_in_worker == [False]
    main_thread_collect.append(threading.current_thread() is threading.main_thread())
    assert main_thread_collect == [True]


def test_garbage_collection_stays_off_until_every_worker_has_finished(gui):
    import gc
    import threading

    app = gui.start()
    release = threading.Event()
    app.tasks.start(lambda emit: release.wait(10), lambda e: None, lambda m: None)
    app.tasks.start(lambda emit: time.sleep(0.1), lambda e: None, lambda m: None)
    gui.pump(0.4)
    assert gc.isenabled() is False  # one worker is still alive
    release.set()
    gui.wait(lambda: gc.isenabled(), timeout=10)
