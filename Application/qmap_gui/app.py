"""The Q-MAP windows: one shared shell and two applications.

* `QMapWindow` - the shell both applications share: scrollable body, navigation, remembered folders (the same
  remembered Q-MAP_DATA / Q-MAP_OUTPUT for both), background work and the shutdown sequence.
* `DatabaseManagerApp` - prepares and manages market data (launched by database_manager.py).
* `AnalyticalWorkbenchApp` - runs analyses on prepared data (launched by analytical_workbench.py).

Neither application needs the other to be running; both use the same Data Registry. Screens live in other files.
"""

from __future__ import annotations

import argparse
import gc
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

from .services import (GuiError, build_core_settings, check_locations, create_folder, prepare_standard_folders,
                       standard_folders)
from .settings_store import GuiSettings, GuiSettingsStore, StoreError, default_settings_dir
from .widgets import MUTED_COLOR, ScrollFrame

POLL_MS = 80
TITLE = "Q-MAP - Quantitative Market Analytics Platform"  # kept for compatibility; each app sets its own


class Dialogs:
    """Every pop-up goes through here, so tests can replace them (a real dialog would wait for a person)."""

    def ask_directory(self, title: str, initial: str = "") -> str:
        return filedialog.askdirectory(title=title, initialdir=initial or None, mustexist=False) or ""

    def ask_open_files(self, title: str, initial: str = "") -> tuple:
        types = [("Market data", "*.csv *.txt *.xlsx *.xls *.parquet"), ("All files", "*.*")]
        return tuple(filedialog.askopenfilenames(title=title, initialdir=initial or None, filetypes=types) or ())

    def ask_open_file(self, title: str, initial: str = "", types=None) -> str:
        return filedialog.askopenfilename(title=title, initialdir=initial or None,
                                          filetypes=types or [("Profile", "*.toml"), ("All files", "*.*")]) or ""

    def ask_string(self, title: str, prompt: str) -> str | None:
        return simpledialog.askstring(title, prompt)

    def yes_no(self, title: str, message: str) -> bool:
        return bool(messagebox.askyesno(title, message))

    def info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)

    def warn(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message)

    def error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message)


_live_workers: set = set()
_live_lock = threading.Lock()


def _hold_garbage_collector(thread: threading.Thread) -> None:
    """Called on the main thread BEFORE a worker starts.

    tkinter objects must not be garbage-collected from a worker thread: Tcl aborts the whole program
    ("Tcl_AsyncDelete: async handler deleted by the wrong thread"). Python's cyclic collector runs in whichever
    thread happens to allocate memory, so it is switched off while any worker is alive and run again - on the
    main thread - once they have all finished.
    """
    with _live_lock:
        if not _live_workers:
            gc.disable()
        _live_workers.add(thread)


def release_garbage_collector_if_idle() -> None:
    """Call on the main thread only."""
    with _live_lock:
        _live_workers.difference_update([t for t in _live_workers if not t.is_alive()])
        idle = not _live_workers
    if idle and not gc.isenabled():
        gc.enable()
        gc.collect()


class BackgroundTasks:
    """Run work in a worker thread. The worker only puts events on a queue; the main thread polls it with after()."""

    def __init__(self, app: "QMapApp"):
        self.app = app
        self.queue: queue.Queue = queue.Queue()
        self.threads: list[threading.Thread] = []
        self._poll()

    def start(self, work, on_event, on_error) -> threading.Thread:
        """work(emit) runs in a thread. on_event/on_error run later, on the main thread."""

        def target():
            try:
                work(lambda event: self.queue.put((on_event, event)))
            except Exception as exc:  # reported on the main thread, never raised into the void
                self.queue.put((on_error, f"{type(exc).__name__}: {exc}"))

        thread = threading.Thread(target=target, name="qmap-worker")  # not a daemon: a load finishes its current file
        self.threads.append(thread)
        _hold_garbage_collector(thread)
        thread.start()
        return thread

    def _poll(self):
        if getattr(self.app, "_closing", False):
            return
        try:
            for _ in range(200):
                callback, payload = self.queue.get_nowait()
                if getattr(self.app, "_closing", False):
                    return
                callback(payload)
        except queue.Empty:
            pass
        self.threads = [t for t in self.threads if t.is_alive()]
        release_garbage_collector_if_idle()
        self.app.after(POLL_MS, self._poll)

    def idle(self) -> bool:
        return self.queue.empty() and not any(t.is_alive() for t in self.threads)

    def join_all(self, timeout: float = 120.0) -> None:
        for t in list(self.threads):
            t.join(timeout)
        release_garbage_collector_if_idle()


class QMapWindow(tk.Tk):
    """The shared shell. Subclasses say which screens they have (`build_screens`); the first one is Home."""

    APP_KEY = ""
    APP_NAME = "Q-MAP"
    WINDOW_TITLE = TITLE
    SUBTITLE = "Quantitative Market Analytics Platform"
    SCREEN_KEYS: tuple[str, ...] = ("home",)

    def screens_planned(self) -> tuple[str, ...]:
        """The screens this application has (known before they are built, so Home can offer Open buttons)."""
        return self.SCREEN_KEYS

    def build_screens(self, container: tk.Frame) -> list[tuple[str, str, tk.Frame]]:
        """[(key, navigation label, frame)], Home first."""
        raise NotImplementedError

    def __init__(self, code_root: str | Path, settings_dir: str | Path | None = None, dialogs: Dialogs | None = None,
                 standard_parent: str | Path | None = None):
        super().__init__()
        self._closing = False
        self._orig_stdout = None  # set only if this app ever redirects sys.stdout
        self.code_root = Path(code_root).resolve()
        self.dialogs = dialogs or Dialogs()
        self.title(self.WINDOW_TITLE)
        self.geometry("1040x800")
        self.minsize(860, 560)

        self.store = GuiSettingsStore(settings_dir or default_settings_dir(), self.code_root)
        self.gui_settings: GuiSettings = self.store.load()
        self.data_var = tk.StringVar(self, value=self.gui_settings.data_root)
        self.output_var = tk.StringVar(self, value=self.gui_settings.output_root)
        self.locations = check_locations("", "", self.code_root)
        self.core_settings = None
        self.core_problem = ""
        # where the standard Q-MAP_DATA and Q-MAP_OUTPUT folders belong: next to the program folder (None = do not
        # prepare them, e.g. in tests that choose their own folders)
        self.standard_parent = Path(standard_parent).expanduser().resolve() if standard_parent else None
        self.folder_note, self.folder_note_kind = "", "info"  # shown under the two folders (info | ok | error)
        self._location_listeners: list = []
        self.active_job = None
        self.tasks = BackgroundTasks(self)

        self._scroll_frame = ScrollFrame(self)
        self._scroll_frame.pack(fill="both", expand=True)
        body = self._scroll_frame.inner

        header = tk.Frame(body)
        header.pack(fill="x", padx=8, pady=(8, 2))
        tk.Label(header, text=self.APP_NAME, font=("TkDefaultFont", 16, "bold")).pack(side="left")
        tk.Label(header, text=self.SUBTITLE, fg=MUTED_COLOR).pack(side="left", padx=8)
        nav = tk.Frame(header)
        nav.pack(side="right")
        self.container = tk.Frame(body)
        self.container.pack(fill="both", expand=True)
        self.screens, self.nav_buttons = {}, {}
        for key, text, frame in self.build_screens(self.container):
            self.screens[key] = frame
            b = tk.Button(nav, text=text, command=lambda k=key: self.show(k))
            b.pack(side="left", padx=2)
            self.nav_buttons[key] = b
        self.current = ""
        self.show("home")
        if self.store.load_warning:
            self.after(200, lambda: self.dialogs.warn("Q-MAP", self.store.load_warning))
        prepared = self._prepare_standard_folders_at_start()
        self.apply_locations(remember=prepared)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ---- navigation -----------------------------------------------------------------------------
    def show(self, name: str) -> None:
        for key, frame in self.screens.items():
            frame.pack_forget()
        self.screens[name].pack(fill="both", expand=True)
        self.current = name
        for key, b in self.nav_buttons.items():
            b.configure(relief="sunken" if key == name else "raised")
        on_show = getattr(self.screens[name], "on_show", None)
        if on_show is not None:
            on_show()
        self._scroll_frame.canvas.yview_moveto(0)

    # ---- remembered folders ---------------------------------------------------------------------
    def add_location_listener(self, callback) -> None:
        self._location_listeners.append(callback)

    def remember(self, **changes) -> None:
        # Both applications share one settings file: start from what is on disk now, so a change made by the
        # other application in the meantime is not overwritten with this window's older copy.
        current = self.store.load()
        if self.store.load_warning is None:
            self.gui_settings = current
        for key, value in changes.items():
            setattr(self.gui_settings, key, value)
        try:
            self.store.save(self.gui_settings)
        except StoreError as exc:
            self.dialogs.warn("Q-MAP", str(exc))

    def apply_locations(self, remember: bool = True) -> bool:
        """Validate the two folders with the Foundation's rules; remember them when they are usable."""
        data, out = self.data_var.get().strip(), self.output_var.get().strip()
        self.locations = check_locations(data, out, self.code_root)
        self.core_settings, self.core_problem = None, ""
        if self.locations.overall_ok:
            try:
                self.core_settings = build_core_settings(data, out, self.code_root, self.store.profiles_dir)
                if remember:
                    self.remember(data_root=data, output_root=out)
            except GuiError as exc:
                self.core_problem = str(exc)
        for callback in self._location_listeners:
            callback()
        return self.core_settings is not None

    def _prepare_standard_folders_at_start(self) -> bool:
        """First start (no folder remembered yet): prepare and use the standard folders next to the program folder.
        Folders already remembered are never replaced silently; when they differ from the standard ones the screen
        says so and offers 'Use standard folders'. Returns True when the standard folders were put into use."""
        if self.standard_parent is None:
            return False
        data_std, out_std = standard_folders(self.standard_parent)
        remembered = (self.data_var.get().strip(), self.output_var.get().strip())
        if all(remembered):
            if (_same_path(remembered[0], data_std) and _same_path(remembered[1], out_std)):
                self.folder_note, self.folder_note_kind = "Using the standard folders next to the Q-MAP program folder.", "ok"
            else:
                self.folder_note, self.folder_note_kind = (
                    f"You are using the folders you chose earlier (remembered). The standard folders for this copy of "
                    f"Q-MAP would be {data_std} and {out_std}. To use those instead, press 'Use standard folders'; "
                    "your current folders and their contents are not changed.", "info")
            return False
        prep = prepare_standard_folders(self.standard_parent, self.code_root)
        if not prep.ok:
            self.folder_note, self.folder_note_kind = ("The standard folders could not be prepared automatically: "
                                                       + prep.problem), "error"
            return False
        if not remembered[0]:
            self.data_var.set(str(prep.data))
        if not remembered[1]:
            self.output_var.set(str(prep.output))
        self.folder_note, self.folder_note_kind = (
            f"Folders prepared automatically next to the Q-MAP program folder: {prep.describe()}.", "ok")
        return True

    def use_standard_folders(self) -> None:
        """'Use standard folders': switch to the standard folders next to the program folder (after asking)."""
        if self.standard_parent is None:
            return
        data_std, out_std = standard_folders(self.standard_parent)
        if not self.dialogs.yes_no(
                "Use standard folders",
                f"Use these folders from now on?\n\nQ-MAP_DATA: {data_std}\nQ-MAP_OUTPUT: {out_std}\n\n"
                "A missing folder is created empty. Your current folders and everything in them stay exactly as they "
                "are; nothing is moved, copied or deleted. Data registered in your current folders are not visible "
                "from the new ones."):
            return
        prep = prepare_standard_folders(self.standard_parent, self.code_root)
        if not prep.ok:
            self.dialogs.error("Q-MAP", prep.problem)
            return
        self.data_var.set(str(prep.data))
        self.output_var.set(str(prep.output))
        self.folder_note, self.folder_note_kind = (
            f"Now using the standard folders next to the Q-MAP program folder ({prep.describe()}).", "ok")
        self.apply_locations()

    def browse_location(self, which: str) -> None:
        var = self.data_var if which == "data" else self.output_var
        title = "Choose the Q-MAP_DATA folder" if which == "data" else "Choose the Q-MAP_OUTPUT folder"
        chosen = self.dialogs.ask_directory(title, var.get() or str(Path.home()))
        if chosen:
            var.set(str(Path(chosen)))
            self.folder_note = ""  # a folder chosen by hand: the note about the standard folders no longer applies
            self.apply_locations()

    def create_location(self, which: str) -> None:
        var, other = (self.data_var, self.output_var) if which == "data" else (self.output_var, self.data_var)
        label = "Q-MAP_DATA" if which == "data" else "Q-MAP_OUTPUT"
        try:
            if not self.dialogs.yes_no("Create folder", f"Create this folder for {label}?\n\n{var.get().strip()}"):
                return
            create_folder(var.get(), label, self.code_root, other.get())
        except GuiError as exc:
            self.dialogs.error("Q-MAP", str(exc))
            return
        self.apply_locations()

    # ---- shutdown ------------------------------------------------------------------------------------
    def _on_closing(self):
        self._closing = True  # (1)
        if self._orig_stdout is not None:  # (2)
            try:
                sys.stdout = self._orig_stdout
            except Exception:
                pass
        try:  # (3) destroy the scroll frame (and its canvas) before the window is hidden
            self._scroll_frame.pack_forget()
            self._scroll_frame.destroy()
        except Exception:
            pass
        try:  # (4)
            self.withdraw()
        except Exception:
            pass
        try:  # (5) cancel every pending after() callback
            for cb in self.tk.call("after", "info"):
                try:
                    self.after_cancel(cb)
                except Exception:
                    pass
        except Exception:
            pass
        try:  # (6)
            self.destroy()
        except Exception:
            pass
        job = self.active_job  # not one of the six steps: ask a running load to stop after its current file
        if job is not None:
            try:
                job.cancel()
            except Exception:
                pass


class DatabaseManagerApp(QMapWindow):
    """Prepares and manages market data: load and validate files, look after datasets and their storage."""

    APP_KEY = "database_manager"
    APP_NAME = "Q-MAP Database Manager"
    WINDOW_TITLE = "Q-MAP Database Manager - prepare and manage market data"
    SUBTITLE = "Prepare, validate, store and manage market data"
    SCREEN_KEYS = ("home", "sources", "data", "datasets")

    def build_screens(self, container):
        from .data_management import DataManagementFrame
        from .datasets import DatasetsFrame
        from .home import HomeFrame
        from .sources import SourcesFrame

        return [("home", "Home", HomeFrame(container, self)),
                ("sources", "Sources", SourcesFrame(container, self)),
                ("data", "Data Management", DataManagementFrame(container, self)),
                ("datasets", "Datasets and Storage", DatasetsFrame(container, self))]


class AnalyticalWorkbenchApp(QMapWindow):
    """Runs analyses on prepared, registered data. It never imports source files."""

    APP_KEY = "analytical_workbench"
    APP_NAME = "Q-MAP Analytical Workbench"
    WINDOW_TITLE = "Q-MAP Analytical Workbench - research on prepared data"
    SUBTITLE = "Research and analysis on prepared, registered data"
    SCREEN_KEYS = ("home", "analysis")

    def build_screens(self, container):
        from .analysis import AnalysisFrame
        from .home import HomeFrame

        return [("home", "Home", HomeFrame(container, self)),
                ("analysis", "Run an analysis", AnalysisFrame(container, self))]


QMapApp = DatabaseManagerApp  # the first graphical version's name for what is now Database Manager
APPS = {DatabaseManagerApp.APP_KEY: DatabaseManagerApp, AnalyticalWorkbenchApp.APP_KEY: AnalyticalWorkbenchApp}


def _same_path(text: str, path: Path) -> bool:
    try:
        return Path(text).expanduser().resolve() == path
    except OSError:
        return False


def _enable_windows_dpi() -> None:
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
        except Exception:
            pass


def main(code_root: str | Path, argv: list[str] | None = None, app_key: str = DatabaseManagerApp.APP_KEY,
         prog: str = "database_manager.py") -> int:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("--selftest", action="store_true", help="open the window, close it again and exit (for testing)")
    parser.add_argument("--settings-dir", help="where remembered choices are kept (default: your user profile)")
    parser.add_argument("--standard-parent", help="where the standard Q-MAP_DATA and Q-MAP_OUTPUT folders are prepared "
                                                  "(default: the folder that holds the Q-MAP program folder)")
    args = parser.parse_args(argv or [])
    _enable_windows_dpi()
    try:
        app = APPS[app_key](code_root, settings_dir=args.settings_dir,
                            standard_parent=args.standard_parent or Path(code_root).resolve().parent)
    except StoreError as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APPS[app_key].APP_NAME, str(exc))
        root.destroy()
        return 1
    if args.selftest:
        app.after(400, app._on_closing)
    app.mainloop()
    app.tasks.join_all()  # let a load that was running finish its current file before the program ends
    if args.selftest:
        print("SELFTEST OK")
    return 0
