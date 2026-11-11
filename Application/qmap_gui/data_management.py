"""Data Management screen: select files, preview, choose a profile, check, load, and see the results.

This file only builds the screen and reacts to clicks. Every piece of real work (reading, validating, loading,
registering) is done by the Foundation through qmap_gui.services / qmap_gui.jobs.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from . import services
from .common import fmt_clock, fmt_duration  # noqa: F401 - also used by other screens
from .jobs import FileOutcome, IngestJob, RunSummary
from .locations import LocationsPanel
from .messages import OUTCOMES
from .widgets import ERROR_COLOR, MUTED_COLOR, OK_COLOR, WARN_COLOR, LogText, ReadOnlyText, combobox_index, section

TIMEFRAMES = ("", "1m", "5m", "15m", "30m", "1h", "3h", "4h", "1D", "1W", "1M")


class DataManagementFrame(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.files: list[Path] = []
        self.profile_infos: list[services.ProfileInfo] = []
        self.extra_profiles: list[services.ProfileInfo] = []
        self.current_info: services.ProfileInfo | None = None
        self.results: dict[str, object] = {}
        self.running = False
        self.mode = ""
        self.last_run_dir: Path | None = None
        self._job: IngestJob | None = None
        self._cancel_check = threading.Event()
        self._t0: float | None = None
        self._total = self._done = self._rows = 0
        self._counts: dict[str, int] = {}
        self.finished_event = threading.Event()  # set when a run/check has fully finished (used by tests)
        self._build()
        app.add_location_listener(self.on_locations_changed)
        self.on_locations_changed()
        self._tick()

    @property
    def _closing(self) -> bool:
        return bool(getattr(self.app, "_closing", False))

    # ------------------------------------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------------------------------------
    def _build(self) -> None:
        bold = tkfont.Font(weight="bold")
        # ---- 1. Input ----
        box = section(self, "1. Input - market-data files")
        row = tk.Frame(box)
        row.pack(fill="x")
        self.add_button = tk.Button(row, text="Add files...", command=self.add_files)
        self.remove_button = tk.Button(row, text="Remove selected", command=self.remove_selected)
        self.clear_button = tk.Button(row, text="Clear list", command=self.clear_files)
        for b in (self.add_button, self.remove_button, self.clear_button):
            b.pack(side="left", padx=2)
        self.count_label = tk.Label(row, text="[0 files selected]", fg=MUTED_COLOR)
        self.count_label.pack(side="left", padx=8)
        self.preview_button = tk.Button(row, text="Preview selected file", command=self.preview_selected)
        self.preview_button.pack(side="right", padx=2)
        lf = tk.Frame(box)
        lf.pack(fill="x", pady=4)
        self.listbox = tk.Listbox(lf, height=5, selectmode="extended", exportselection=False)
        sb = tk.Scrollbar(lf, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="x", expand=True)
        self.listbox.bind("<Double-Button-1>", lambda _e: self.preview_selected())
        tk.Label(box, text="Preview (reading a file here never saves anything):", anchor="w", fg=MUTED_COLOR).pack(fill="x")
        self.preview_box = ReadOnlyText(box, height=9)
        self.preview_box.pack(fill="x")

        # ---- 2. Output ----
        box = section(self, "2. Output - where Q-MAP keeps your data and results")
        self.locations_panel = LocationsPanel(box, self.app, show_help=False)
        self.locations_panel.pack(fill="x")
        row = tk.Frame(box)
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text="Last run folder:", width=18, anchor="w").pack(side="left")
        self.run_folder_var = tk.StringVar(self, value="(none yet)")
        tk.Label(row, textvariable=self.run_folder_var, anchor="w", fg=MUTED_COLOR).pack(side="left", fill="x", expand=True)
        self.open_run_button = tk.Button(row, text="Open run folder", state="disabled", command=self.open_run_folder)
        self.open_run_button.pack(side="right")
        row = tk.Frame(box)
        row.pack(fill="x")
        tk.Label(row, text="Problem report:", width=18, anchor="w").pack(side="left")
        self.report_var = tk.StringVar(self, value="(select a result below)")
        tk.Label(row, textvariable=self.report_var, anchor="w", fg=MUTED_COLOR).pack(side="left", fill="x", expand=True)
        self.open_report_button = tk.Button(row, text="Open report", state="disabled", command=self.open_report)
        self.open_report_button.pack(side="right")

        # ---- 3. Options ----
        box = section(self, "3. Options - source profile and file details")
        tk.Label(box, anchor="w", justify="left", wraplength=940, fg=MUTED_COLOR,
                 text="A source profile describes one file layout (header, date format, volume column ...). Q-MAP "
                      "never guesses these, so pick or create the profile that matches your file.").pack(fill="x")
        row = tk.Frame(box)
        row.pack(fill="x", pady=3)
        tk.Label(row, text="Source profile:", width=14, anchor="w").pack(side="left")
        self.profile_combo = ttk.Combobox(row, state="readonly", width=70)
        self.profile_combo.pack(side="left", fill="x", expand=True)
        self.profile_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_profile_selected())
        row = tk.Frame(box)
        row.pack(fill="x")
        self.refresh_button = tk.Button(row, text="Refresh list", command=lambda: self.refresh_profiles())
        self.browse_profile_button = tk.Button(row, text="Browse for a profile file...", command=self.browse_profile)
        self.edit_button = tk.Button(row, text="Edit / check profile...", command=self.edit_profile)
        self.copy_button = tk.Button(row, text="New profile from this one...", command=self.copy_profile)
        self.ask_identity_button = tk.Button(row, text="Copy so it asks me for exchange and symbol...",
                                             command=self.copy_profile_asking_for_identity, state="disabled")
        for b in (self.refresh_button, self.browse_profile_button, self.edit_button, self.copy_button,
                  self.ask_identity_button):
            b.pack(side="left", padx=2, pady=3)
        self.profile_details = ReadOnlyText(box, height=11, mono=False)
        self.profile_details.pack(fill="x", pady=3)

        grid = tk.Frame(box)
        grid.pack(fill="x", pady=3)
        self.exchange_var, self.symbol_var, self.timeframe_var = tk.StringVar(self), tk.StringVar(self), tk.StringVar(self)
        for var in (self.exchange_var, self.symbol_var, self.timeframe_var):  # re-check as the user types
            var.trace_add("write", lambda *_args: self._on_request_typed())
        self.label_var = tk.StringVar(self, value=self.app.gui_settings.source_label)
        self.note_var, self.force_var = tk.StringVar(self), tk.StringVar(self)
        tk.Label(grid, text="Exchange:", anchor="w", width=18).grid(row=0, column=0, sticky="w")
        self.exchange_entry = tk.Entry(grid, textvariable=self.exchange_var, width=14)
        self.exchange_entry.grid(row=0, column=1, sticky="w")
        tk.Label(grid, text="Symbol:", anchor="w", width=10).grid(row=0, column=2, sticky="w", padx=(10, 0))
        self.symbol_entry = tk.Entry(grid, textvariable=self.symbol_var, width=18)
        self.symbol_entry.grid(row=0, column=3, sticky="w")
        tk.Label(grid, text="Timeframe:", anchor="w", width=10).grid(row=0, column=4, sticky="w", padx=(10, 0))
        self.timeframe_combo = ttk.Combobox(grid, textvariable=self.timeframe_var, values=TIMEFRAMES, width=8, state="readonly")
        self.timeframe_combo.grid(row=0, column=5, sticky="w")
        tk.Label(grid, text="Where it came from:", anchor="w", width=18).grid(row=1, column=0, sticky="w", pady=2)
        tk.Entry(grid, textvariable=self.label_var, width=40).grid(row=1, column=1, columnspan=3, sticky="w")
        tk.Label(grid, text="Note:", anchor="w", width=10).grid(row=1, column=4, sticky="w", padx=(10, 0))
        tk.Entry(grid, textvariable=self.note_var, width=30).grid(row=1, column=5, columnspan=2, sticky="w")
        tk.Label(grid, text="Retry reason:", anchor="w", width=18).grid(row=2, column=0, sticky="w")
        tk.Entry(grid, textvariable=self.force_var, width=60).grid(row=2, column=1, columnspan=5, sticky="w")
        tk.Label(grid, anchor="w", justify="left", fg=MUTED_COLOR, wraplength=900,
                 text="Exchange, Symbol and Timeframe are needed only when the profile cannot read them from the file. "
                      "'Retry reason' is only for retrying, unchanged, a file that was rejected before.").grid(
            row=3, column=0, columnspan=7, sticky="w", pady=(2, 0))
        self.identity_note = tk.Label(grid, text="", anchor="w", justify="left", fg=MUTED_COLOR, wraplength=900)
        self.identity_note.grid(row=4, column=0, columnspan=7, sticky="w")
        self.hint = tk.Label(box, text="", anchor="w", justify="left", wraplength=940)
        self.hint.pack(fill="x", pady=(4, 2))
        row = tk.Frame(box)
        row.pack(fill="x", pady=2)
        self.check_button = tk.Button(row, text="Check files (nothing is saved)", command=self.check_files, padx=8, pady=4)
        self.run_button = tk.Button(row, text="LOAD FILES INTO Q-MAP", command=self.start_ingest, padx=14, pady=4, font=bold)
        self.cancel_button = tk.Button(row, text="Stop after this file", state="disabled", command=self.cancel, padx=8, pady=4)
        for b in (self.check_button, self.run_button, self.cancel_button):
            b.pack(side="left", padx=4)

        # ---- Progress / Status ----
        box = section(self, "Progress / Status")
        self.stage_var, self.file_var = tk.StringVar(self, value="Idle"), tk.StringVar(self, value="-")
        self.files_var, self.started_var = tk.StringVar(self, value="0 / 0"), tk.StringVar(self, value="-")
        self.elapsed_var, self.eta_var = tk.StringVar(self, value="-"), tk.StringVar(self, value="-")
        self.rows_var, self.counts_var = tk.StringVar(self, value="0"), tk.StringVar(self, value="-")
        items = (("Stage:", self.stage_var), ("Current file:", self.file_var), ("Files done:", self.files_var),
                 ("Started:", self.started_var), ("Elapsed:", self.elapsed_var), ("Time left (estimate):", self.eta_var),
                 ("Rows processed:", self.rows_var), ("Results so far:", self.counts_var))
        for i, (label, var) in enumerate(items):
            r, c = divmod(i, 2)
            tk.Label(box, text=label, anchor="w", width=20).grid(row=r, column=c * 2, sticky="w")
            tk.Label(box, textvariable=var, anchor="w", width=44, justify="left").grid(row=r, column=c * 2 + 1, sticky="w")
        self.progress = ttk.Progressbar(box, mode="determinate", maximum=100)
        self.progress.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.final_label = tk.Label(box, text="", anchor="w", justify="left", wraplength=940, font=bold)
        self.final_label.grid(row=5, column=0, columnspan=4, sticky="w")
        box.columnconfigure(1, weight=1)
        box.columnconfigure(3, weight=1)

        # ---- Results ----
        box = section(self, "Results (click a row to see what happened, in plain English)")
        tf = tk.Frame(box)
        tf.pack(fill="x")
        self.tree = ttk.Treeview(tf, columns=("file", "result", "rows", "message"), show="headings", height=5, selectmode="browse")
        for col, text, width in (("file", "File", 200), ("result", "Result", 170), ("rows", "Rows", 70), ("message", "What happened", 480)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        tsb = tk.Scrollbar(tf, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="x", expand=True)
        self.tree.tag_configure("ok", foreground=OK_COLOR)
        self.tree.tag_configure("bad", foreground=ERROR_COLOR)
        self.tree.tag_configure("muted", foreground=MUTED_COLOR)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.on_result_selected())
        self.details = ReadOnlyText(box, height=9, mono=False)
        self.details.pack(fill="x", pady=(4, 0))

        # ---- Live log ----
        box = section(self, "Live Log")
        self.log = LogText(box, height=9)
        self.log.pack(fill="x")

    # ------------------------------------------------------------------------------------------------
    # input files
    # ------------------------------------------------------------------------------------------------
    def add_paths(self, paths) -> None:
        for p in paths:
            path = Path(p)
            if path not in self.files:
                self.files.append(path)
                self.listbox.insert("end", str(path))
        self._after_files_changed()

    def add_files(self) -> None:
        chosen = self.app.dialogs.ask_open_files("Choose market-data files", self.app.gui_settings.last_input_dir)
        if chosen:
            self.app.remember(last_input_dir=str(Path(chosen[0]).parent))
            self.add_paths(chosen)

    def remove_selected(self) -> None:
        for index in sorted(self.listbox.curselection(), reverse=True):
            self.listbox.delete(index)
            del self.files[index]
        self._after_files_changed()

    def clear_files(self) -> None:
        self.listbox.delete(0, "end")
        self.files.clear()
        self._after_files_changed()

    def _after_files_changed(self) -> None:
        n = len(self.files)
        self.count_label.configure(text=f"[{n} file{'s' if n != 1 else ''} selected]")
        self.update_state()

    # ------------------------------------------------------------------------------------------------
    # profiles
    # ------------------------------------------------------------------------------------------------
    def on_locations_changed(self) -> None:
        if self.app.core_settings is not None:
            self.refresh_profiles()
        else:
            self.profile_infos = []
            self.profile_combo.configure(values=())
            self.profile_combo.set("")
            self.current_info = None
            self.profile_details.set("Choose your two folders in section 2 first; profiles are listed after that.", "muted")
        self.update_state()

    def refresh_profiles(self, select: Path | None = None) -> None:
        settings = self.app.core_settings
        if settings is None:
            return
        self.profile_infos = services.list_profiles(settings) + self.extra_profiles
        self.profile_combo.configure(values=[i.label for i in self.profile_infos])
        wanted = str(select) if select else self.app.gui_settings.last_profile
        index = next((n for n, i in enumerate(self.profile_infos) if str(i.path) == wanted), None)
        if index is not None:
            self.profile_combo.current(index)
        else:
            self.profile_combo.set("")
            self.current_info = None
        self.on_profile_selected()

    def on_profile_selected(self) -> None:
        index = combobox_index(self.profile_combo)
        self.current_info = self.profile_infos[index] if 0 <= index < len(self.profile_infos) else None
        info = self.current_info
        if info is None:
            self.profile_details.set("No profile chosen yet.", "muted")
        elif info.profile is None:
            self.profile_details.set(f"This profile cannot be used yet:\n{info.problem}\n\nUse 'Edit / check profile...' to fix it.", "error")
        else:
            lines = [f"{k}: {v}" for k, v in services.describe_profile(info.profile)]
            self.profile_details.set(f"{info.profile.title}\n{info.profile.description}\n" + "\n".join(lines))
            self.app.remember(last_profile=str(info.path))
        needs = services.profile_needs(info.profile) if info and info.profile else services.ProfileNeeds(False, False, False)
        self.exchange_entry.configure(state="normal" if needs.exchange else "disabled")
        self.symbol_entry.configure(state="normal" if needs.symbol else "disabled")
        self.timeframe_combo.configure(state="readonly" if needs.timeframe else "disabled")
        for var, used in ((self.exchange_var, needs.exchange), (self.symbol_var, needs.symbol),
                          (self.timeframe_var, needs.timeframe)):
            if not used and var.get():
                var.set("")  # a switched-off box must not show a value the profile will not use
        usable = bool(info and info.profile)
        self.identity_note.configure(text=services.identity_note(info.profile) if usable else "")
        self.ask_identity_button.configure(
            state="normal" if usable and services.reads_identity_from_filename(info.profile) else "disabled")
        self.update_state()

    def select_profile_index(self, index: int) -> None:
        self.profile_combo.current(index)
        self.on_profile_selected()

    def browse_profile(self) -> None:
        settings = self.app.core_settings
        if settings is None:
            self.app.dialogs.warn("Q-MAP", "Choose your Q-MAP_DATA and Q-MAP_OUTPUT folders first.")
            return
        chosen = self.app.dialogs.ask_open_file("Choose a source profile (.toml)")
        if chosen:
            info = services.load_profile_file(chosen, settings)
            self.extra_profiles = [i for i in self.extra_profiles if i.path != info.path] + [info]
            self.refresh_profiles(select=info.path)

    def _editor_text(self) -> tuple[str, str] | None:
        info = self.current_info
        if info is None:
            self.app.dialogs.info("Q-MAP", "Choose a source profile first.")
            return None
        text = info.path.read_text(encoding="utf-8")
        if info.where == "example":
            text = services.as_user_copy_text(text)
        note = (f"Editing a COPY of the Q-MAP library profile '{info.path.name}'." if info.where == "example"
                else f"Editing {info.path}.")
        return text, note

    def edit_profile(self) -> None:
        got = self._editor_text()
        if got is None:
            return
        from .profile_editor import ProfileEditor

        ProfileEditor(self.app, got[0], got[1], lambda path: self.refresh_profiles(select=path))

    def copy_profile(self) -> None:
        info = self.current_info
        if info is None:
            self.app.dialogs.info("Q-MAP", "Choose a source profile to copy first.")
            return
        name = self.app.dialogs.ask_string("New profile", "Name for your new profile (letters, digits, _ . - only):")
        if not name:
            return
        try:
            path = services.copy_example_as(info.path, name.strip(), self.app.store.profiles_dir)
        except services.GuiError as exc:
            self.app.dialogs.error("Q-MAP", str(exc))
            return
        self.refresh_profiles(select=path)

    def _on_request_typed(self) -> None:
        """Typing an exchange, symbol or timeframe must re-enable Check/Load at once (it used to wait for another event)."""
        if self._closing or not hasattr(self, "run_button"):
            return
        self.update_state()

    def copy_profile_asking_for_identity(self) -> None:
        info = self.current_info
        if info is None or info.profile is None or not services.reads_identity_from_filename(info.profile):
            return
        name = self.app.dialogs.ask_string(
            "New profile that asks for exchange and symbol",
            f"This makes a copy of '{info.profile.profile_id}' that asks you to type the exchange and symbol, instead of "
            "reading them from the file name. Everything else stays the same; the original is not changed.\n\n"
            "Name for the new profile (letters, digits, _ . - only):")
        if not name:
            return
        try:
            path = services.copy_profile_asking_for_identity(info.path, name.strip(), self.app.store.profiles_dir)
        except (services.GuiError, services.ProfileError) as exc:
            self.app.dialogs.error("Q-MAP", str(exc))
            return
        self.refresh_profiles(select=path)

    # ------------------------------------------------------------------------------------------------
    # state, hints and validation of what the user asked for
    # ------------------------------------------------------------------------------------------------
    def overrides(self) -> dict:
        return {"exchange": self.exchange_var.get().strip(), "symbol": self.symbol_var.get().strip(),
                "timeframe": self.timeframe_var.get().strip(), "source_label": self.label_var.get().strip(),
                "note": self.note_var.get().strip(), "force_reason": self.force_var.get().strip()}

    def problems(self) -> list[str]:
        out = []
        if self.app.core_settings is None:
            out.append("Choose your two folders in section 2 (data and output) first.")
            return out
        if not self.files:
            out.append("Add one or more files in section 1.")
        info = self.current_info
        if info is None:
            out.append("Choose a source profile in section 3.")
        elif info.profile is None:
            out.append(f"The chosen profile cannot be used: {info.problem}")
        else:
            ov = self.overrides()
            out += services.request_problems(info.profile, ov["exchange"], ov["symbol"], ov["timeframe"])
        return out

    def update_state(self) -> None:
        problems = self.problems()
        if self.running:
            self.hint.configure(text="Working...", fg=MUTED_COLOR)
        elif problems:
            self.hint.configure(text="Next step: " + problems[0], fg=WARN_COLOR)
        elif self.current_info and self.current_info.profile and services.file_name_notes(self.current_info.profile, self.files):
            notes = services.file_name_notes(self.current_info.profile, self.files)
            self.hint.configure(text=f"Note ({len(notes)} file(s)): " + notes[0], fg=WARN_COLOR)
        else:
            self.hint.configure(text="Ready. 'Check files' tests everything without saving; 'Load files into Q-MAP' loads them.",
                                fg=OK_COLOR)
        idle = "disabled" if self.running else "normal"
        for b in (self.add_button, self.remove_button, self.clear_button, self.refresh_button,
                  self.browse_profile_button, self.edit_button, self.copy_button):
            b.configure(state=idle)
        go = "normal" if (not self.running and not problems) else "disabled"
        self.check_button.configure(state=go)
        self.run_button.configure(state=go)
        self.cancel_button.configure(state="normal" if self.running else "disabled")
        self.preview_button.configure(state="normal" if self.files else "disabled")

    # ------------------------------------------------------------------------------------------------
    # preview (background, nothing saved)
    # ------------------------------------------------------------------------------------------------
    def preview_selected(self) -> None:
        sel = self.listbox.curselection()
        if not self.files:
            self.app.dialogs.info("Q-MAP", "Add a file first, then preview it.")
            return
        path = self.files[sel[0]] if sel else self.files[0]
        profile = self.current_info.profile if self.current_info else None
        settings, ov = self.app.core_settings, self.overrides()
        self.preview_box.set(f"Reading {path.name} ...", "muted")

        def work(emit):
            emit({"type": "preview", "text": services.make_preview(path, profile, settings, ov)})

        self.app.tasks.start(work, self._on_preview_event, self.on_task_error)

    def _on_preview_event(self, event: dict) -> None:
        self.preview_box.set(event["text"])

    # ------------------------------------------------------------------------------------------------
    # running: check (dry) and load (ingest)
    # ------------------------------------------------------------------------------------------------
    def _begin(self, mode: str, total: int) -> None:
        self.running, self.mode = True, mode
        self.finished_event.clear()
        self._t0 = time.monotonic()
        self._total, self._done, self._rows, self._counts = total, 0, 0, {}
        self.results.clear()
        self.tree.delete(*self.tree.get_children())
        self.details.set("")
        self.report_var.set("(select a result below)")
        self.open_report_button.configure(state="disabled")
        self.final_label.configure(text="")
        self.files_var.set(f"0 / {total}")
        self.file_var.set("-")
        self.rows_var.set("0")
        self.counts_var.set("-")
        self.eta_var.set("-")
        self.elapsed_var.set("0 s")
        self.started_var.set(fmt_clock(datetime.now()))
        self.progress.configure(value=0)
        self.stage_var.set("Starting" if mode == "load" else "Checking")
        self.log.append(f"---- {'Loading' if mode == 'load' else 'Checking'} {total} file(s) ----")
        self.update_state()

    def check_files(self) -> None:
        problems = self.problems()
        if problems:
            self.app.dialogs.warn("Q-MAP", problems[0])
            return
        settings, profile, ov, files = self.app.core_settings, self.current_info.profile, self.overrides(), list(self.files)
        self._cancel_check.clear()
        self._begin("check", len(files))

        def work(emit):
            for i, path in enumerate(files, start=1):
                if self._cancel_check.is_set():
                    break
                emit({"type": "file_start", "index": i, "total": len(files), "path": str(path)})
                report = services.check_file(path, profile, settings, ov)
                emit({"type": "check_done", "index": i, "total": len(files), "report": report})
            emit({"type": "check_finished"})

        self.app.tasks.start(work, self.on_job_event, self.on_task_error)

    def start_ingest(self) -> None:
        problems = self.problems()
        if problems:
            self.app.dialogs.warn("Q-MAP", problems[0])
            return
        ov = self.overrides()
        self.app.remember(source_label=ov["source_label"])
        job = IngestJob(self.app.core_settings, list(self.files), self.current_info.profile, exchange=ov["exchange"],
                        symbol=ov["symbol"], timeframe=ov["timeframe"], source_label=ov["source_label"],
                        note=ov["note"], force_reason=ov["force_reason"])
        self._job = job
        self.app.active_job = job
        self._begin("load", len(self.files))

        def work(emit):
            job.emit = emit
            job.run()

        self.app.tasks.start(work, self.on_job_event, self.on_task_error)

    def cancel(self) -> None:
        if self.mode == "load" and self._job is not None:
            self._job.cancel()
        else:
            self._cancel_check.set()
        self.stage_var.set("Stopping after the current file ...")
        self.cancel_button.configure(state="disabled")

    # ---- events from the worker (always handled on the main thread) -----------------------------------
    def on_job_event(self, ev: dict) -> None:
        kind = ev["type"]
        if kind == "log":
            self.log.append(ev["text"])
        elif kind == "stage":
            self.stage_var.set(ev["text"])
        elif kind == "run_started":
            self.last_run_dir = Path(ev["run_dir"])
            self.run_folder_var.set(str(self.last_run_dir))
            self.open_run_button.configure(state="normal")
        elif kind == "file_start":
            self.file_var.set(Path(ev["path"]).name)
            self.files_var.set(f"{self._done} / {self._total}  (working on {ev['index']})")
            self.stage_var.set(f"{'Loading' if self.mode == 'load' else 'Checking'} file {ev['index']} of {ev['total']}")
        elif kind == "file_done":
            self._add_result(ev["outcome"])
        elif kind == "check_done":
            self._add_result(ev["report"])
        elif kind == "done":
            self._finish(ev["summary"])
        elif kind == "check_finished":
            self._finish(None)

    def on_task_error(self, message: str) -> None:
        self.log.append(f"ERROR unexpected problem: {message}")
        if self.running:
            self.running, self._job, self.app.active_job = False, None, None
            self.stage_var.set("Stopped by a problem")
            self.final_label.configure(text=f"Something unexpected went wrong: {message}", fg=ERROR_COLOR)
            self.update_state()
            self.finished_event.set()
        else:
            self.preview_box.set(f"The preview could not be made: {message}", "error")

    def _add_result(self, obj) -> None:
        self._done += 1
        if isinstance(obj, FileOutcome):
            label, rows, message, path = obj.label, obj.rows_read, obj.message, obj.path
            tag = "ok" if obj.outcome == "accepted" else "muted" if obj.outcome in ("reused", "waiting") else "bad"
            key = obj.outcome
        else:  # CheckReport
            label, rows, message, path = OUTCOMES.get(obj.outcome, obj.outcome), obj.rows_read, "", obj.file
            tag = "ok" if obj.outcome == "would_be_accepted" else "bad"
            key = obj.outcome
            n_err, n_warn = len(obj.errors), len(obj.warnings)
            message = (f"{n_err} problem(s)" if n_err else "No problems") + (f", {n_warn} note(s)" if n_warn else "")
        self._counts[key] = self._counts.get(key, 0) + 1
        if rows:
            self._rows += rows
        iid = self.tree.insert("", "end", values=(path.name, label, "" if rows is None else rows, message), tags=(tag,))
        self.results[iid] = obj
        self.files_var.set(f"{self._done} / {self._total}")
        self.rows_var.set(f"{self._rows:,}")
        self.counts_var.set(", ".join(f"{v} {OUTCOMES.get(k, k).lower()}" for k, v in self._counts.items()))
        self.progress.configure(value=100.0 * self._done / max(self._total, 1))
        if self._done == 1:
            self.tree.selection_set(iid)

    def _finish(self, summary: RunSummary | None) -> None:
        self.running, self._job, self.app.active_job = False, None, None
        self.progress.configure(value=100.0 if self._done >= self._total else self.progress["value"])
        self.eta_var.set("-")
        if summary is not None and summary.error:
            self.stage_var.set("Stopped by a problem")
            self.final_label.configure(text=f"The run could not be completed: {summary.error}", fg=ERROR_COLOR)
        else:
            # a stopped check or load must never look like a finished one (10-Nov-26 progress review)
            cancelled = (summary is not None and summary.cancelled) or (self._done < self._total)
            self.stage_var.set("Stopped (as you asked)" if cancelled else "Finished")
            bad = sum(v for k, v in self._counts.items() if k not in ("accepted", "reused", "waiting", "would_be_accepted"))
            what = "Check" if self.mode == "check" else "Load"
            if cancelled:
                self.final_label.configure(
                    text=f"{what} stopped by you after {self._done} of {self._total} file(s): {self.counts_var.get()}. "
                         + ("Nothing was saved." if self.mode == "check" else
                            "Files already loaded are kept; the others were not loaded."), fg=WARN_COLOR)
            else:
                self.final_label.configure(
                    text=f"{what} finished: {self.counts_var.get()}." + (" Nothing was saved." if self.mode == "check"
                         else (" Open the problem report for rejected files." if bad else " Everything was loaded.")),
                    fg=ERROR_COLOR if bad else OK_COLOR)
        if self.mode == "load" and summary is not None and summary.run_dir:
            self.run_folder_var.set(str(summary.run_dir))
        self.update_state()
        self.finished_event.set()

    # ---- results ----------------------------------------------------------------------------------------
    def on_result_selected(self) -> None:
        sel = self.tree.selection()
        obj = self.results.get(sel[0]) if sel else None
        if obj is None:
            return
        parts: list[tuple[str, str | None]] = []
        findings = obj.findings
        if isinstance(obj, FileOutcome):
            parts.append((f"{obj.path.name}\n", "bold"))
            parts.append((f"Result: {obj.label}\n", "ok" if obj.ok else "error"))
            parts.append((f"{obj.message}\n", None))
            if obj.rows_read is not None:
                parts.append((f"Rows read: {obj.rows_read:,}   rows with problems: {obj.rows_flagged or 0:,}\n", None))
            if obj.datasets:
                parts.append((f"Loaded as dataset number(s): {', '.join(map(str, obj.datasets))}\n", "ok"))
            report = obj.issues_report
            self.report_var.set(str(report) if report else "(no problem report for this file)")
            self.open_report_button.configure(state="normal" if report else "disabled")
        else:
            parts.append((f"{obj.file.name}\n", "bold"))
            parts.append((f"Result: {OUTCOMES.get(obj.outcome, obj.outcome)} (nothing was saved)\n",
                          "ok" if obj.outcome == "would_be_accepted" else "error"))
            parts.append((f"Rows read: {obj.rows_read:,}\n", None))
            self.report_var.set("(a problem report is written only when files are loaded)")
            self.open_report_button.configure(state="disabled")
        parts.append(("\n", None))
        if not findings:
            parts.append(("No problems or notes.\n", "ok"))
        for f in findings:
            parts.append((f.text() + "\n\n", {"error": "error", "warning": "warning"}.get(f.severity, "muted")))
        self.details.set_parts(parts)

    def selected_result(self):
        sel = self.tree.selection()
        return self.results.get(sel[0]) if sel else None

    def open_run_folder(self) -> None:
        if self.last_run_dir is None:
            return
        ok, msg = services.open_in_file_manager(self.last_run_dir)
        if not ok:
            self.app.dialogs.error("Q-MAP", msg)

    def open_report(self) -> None:
        obj = self.selected_result()
        report = getattr(obj, "issues_report", None)
        if report is None:
            return
        target = Path(report)
        ok, msg = services.open_in_file_manager(target if target.exists() else target.parent)
        if not ok:
            self.app.dialogs.error("Q-MAP", msg)

    # ---- elapsed clock ------------------------------------------------------------------------------------
    def _tick(self) -> None:
        if getattr(self, "_closing", False):
            return
        if self.running and self._t0 is not None:
            elapsed = time.monotonic() - self._t0
            self.elapsed_var.set(fmt_duration(elapsed))
            if self._done and self._total > self._done:
                self.eta_var.set("about " + fmt_duration(elapsed / self._done * (self._total - self._done)))
        self.after(500, self._tick)
