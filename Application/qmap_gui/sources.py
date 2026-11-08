"""Sources screen (Database Manager): the folders Q-MAP reads market files from, scanning them, and the results.

Blueprint v1.3 §8.5.8: configure a source, discover data, review a short summary, answer only real ambiguities, and
see the resulting datasets. This file only builds the screen and reacts to clicks; the work is done by the Foundation
through qmap_gui.source_services, in a worker thread that only posts events to a queue.
"""

from __future__ import annotations

import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from . import source_services as ss
from .common import fmt_clock, fmt_duration, open_in_file_manager
from .widgets import ERROR_COLOR, MUTED_COLOR, OK_COLOR, WARN_COLOR, LogText, ReadOnlyText, section

SOURCE_COLUMNS = (("label", "Name", 140), ("folder", "Folder", 330), ("tz", "Market time zone", 120),
                  ("exch", "Default exchange", 110), ("symname", "Symbol from name", 115), ("sub", "Sub-folders", 80))
FILE_COLUMNS = (("file", "File", 230), ("result", "Result", 170), ("change", "Change", 75), ("ds", "Dataset(s)", 75),
                ("when", "Checked", 75), ("detail", "Detail", 330))
TAGS = {"imported": "ok", "reused": "ok", "needs_answer": "attention", "missing": "attention", "rejected": "bad",
        "blocked": "bad", "unsupported": "bad", "failed": "bad", "ignored": "muted"}


class SourcesFrame(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.source_rows: dict[str, int] = {}  # tree item -> source id
        self.file_rows: dict[str, object] = {}  # tree item -> FileState
        self.running = False
        self.last_run_dir: Path | None = None
        self.last_report: Path | None = None
        self._t0: float | None = None
        self._job = None
        self._build()
        app.add_location_listener(self.refresh)
        self.refresh()
        self._tick()

    @property
    def _closing(self) -> bool:
        return bool(getattr(self.app, "_closing", False))

    # ---- layout ------------------------------------------------------------------------------------------------
    def _build(self) -> None:
        bold = tkfont.Font(weight="bold")
        box = section(self, "1. Input - folders Q-MAP reads market files from")
        tk.Label(box, anchor="w", justify="left", wraplength=940, fg=MUTED_COLOR,
                 text="Add the folder where your files are kept (any folder, including a OneDrive or Google Drive "
                      "folder on this computer). Q-MAP only reads it: nothing in it is ever changed, moved or deleted. "
                      "Scanning works out each file's layout by itself and asks you only when something is unclear."
                 ).pack(fill="x")
        row = tk.Frame(box)
        row.pack(fill="x", pady=3)
        self.add_button = tk.Button(row, text="Add folder...", command=self.add_folder)
        self.add_button.pack(side="left")
        self.save_button = tk.Button(row, text="Save settings of selected folder", command=self.save_settings)
        self.save_button.pack(side="left", padx=4)
        self.remove_button = tk.Button(row, text="Stop using selected folder", command=self.remove_folder)
        self.remove_button.pack(side="left")
        self.source_count = tk.Label(row, text="[0 folders]", fg=MUTED_COLOR)
        self.source_count.pack(side="left", padx=8)
        frame = tk.Frame(box)
        frame.pack(fill="x", pady=3)
        self.sources_tree = ttk.Treeview(frame, columns=[c[0] for c in SOURCE_COLUMNS], show="headings", height=4,
                                         selectmode="browse")
        for key, text, width in SOURCE_COLUMNS:
            self.sources_tree.heading(key, text=text)
            self.sources_tree.column(key, width=width, anchor="w", stretch=key == "folder")
        self.sources_tree.pack(fill="x")
        self.sources_tree.bind("<<TreeviewSelect>>", lambda _e: self.on_source_select())
        form = tk.Frame(box)
        form.pack(fill="x", pady=3)
        self.tz_var, self.exch_var = tk.StringVar(self, value="Asia/Kolkata"), tk.StringVar(self, value="NSE")
        self.symname_var, self.sub_var = tk.BooleanVar(self, value=False), tk.BooleanVar(self, value=False)
        self.exclude_var = tk.StringVar(self, value="")
        tk.Label(form, text="Market time zone:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(form, textvariable=self.tz_var, values=ss.COMMON_ZONES, width=18).grid(row=0, column=1, sticky="w")
        tk.Label(form, text="Default exchange:").grid(row=0, column=2, sticky="w", padx=(10, 0))
        tk.Entry(form, textvariable=self.exch_var, width=8).grid(row=0, column=3, sticky="w")
        tk.Checkbutton(form, text="File name is the symbol (e.g. RELIANCE.csv)", variable=self.symname_var).grid(
            row=0, column=4, sticky="w", padx=(10, 0))
        tk.Checkbutton(form, text="Include sub-folders", variable=self.sub_var).grid(row=1, column=0, columnspan=2,
                                                                                     sticky="w")
        tk.Label(form, text="Skip files matching:").grid(row=1, column=2, sticky="w", padx=(10, 0))
        tk.Entry(form, textvariable=self.exclude_var, width=40).grid(row=1, column=3, columnspan=2, sticky="w")
        tk.Label(box, anchor="w", justify="left", wraplength=940, fg=MUTED_COLOR,
                 text="The market time zone is used to work out each bar's trading date, and for times written without "
                      "an offset. It is recorded with every file loaded. Skip patterns: e.g. *backup*, old/*").pack(fill="x")

        box = section(self, "2. Output - files found in the selected folder")
        row = tk.Frame(box)
        row.pack(fill="x")
        self.attention_var = tk.BooleanVar(self, value=False)
        tk.Checkbutton(row, text="Show only files that need attention", variable=self.attention_var,
                       command=self.refresh_files).pack(side="left")
        tk.Button(row, text="Refresh", command=self.refresh_files).pack(side="left", padx=6)
        self.files_count = tk.Label(row, text="", fg=MUTED_COLOR)
        self.files_count.pack(side="left", padx=8)
        frame = tk.Frame(box)
        frame.pack(fill="x", pady=3)
        self.files_tree = ttk.Treeview(frame, columns=[c[0] for c in FILE_COLUMNS], show="headings", height=8,
                                       selectmode="browse")
        for key, text, width in FILE_COLUMNS:
            self.files_tree.heading(key, text=text)
            self.files_tree.column(key, width=width, anchor="w", stretch=key == "detail")
        sb = tk.Scrollbar(frame, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.files_tree.pack(side="left", fill="x", expand=True)
        self.files_tree.tag_configure("ok", foreground=OK_COLOR)
        self.files_tree.tag_configure("attention", foreground=WARN_COLOR)
        self.files_tree.tag_configure("bad", foreground=ERROR_COLOR)
        self.files_tree.tag_configure("muted", foreground=MUTED_COLOR)
        self.files_tree.bind("<<TreeviewSelect>>", lambda _e: self.on_file_select())
        self.details = ReadOnlyText(box, height=9, mono=False)
        self.details.pack(fill="x")
        row = tk.Frame(box)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text="Last scan report:", width=16, anchor="w").pack(side="left")
        self.report_var = tk.StringVar(self, value="(none yet)")
        tk.Label(row, textvariable=self.report_var, anchor="w", fg=MUTED_COLOR).pack(side="left", fill="x", expand=True)
        self.open_run_button = tk.Button(row, text="Open run folder", state="disabled", command=self.open_run_folder)
        self.open_run_button.pack(side="right")

        box = section(self, "3. Options - scan, and answer questions about a file")
        row = tk.Frame(box)
        row.pack(fill="x", pady=3)
        self.scan_button = tk.Button(row, text="SCAN SELECTED FOLDER NOW", font=bold, padx=10, command=self.scan)
        self.scan_button.pack(side="left")
        self.hint = tk.Label(row, text="", anchor="w", justify="left", wraplength=640)
        self.hint.pack(side="left", padx=10)
        tk.Label(box, anchor="w", fg=MUTED_COLOR, justify="left", wraplength=940,
                 text="Answer for the selected file (only the boxes its question needs are switched on). Answers are "
                      "recorded and used by the next scan, as long as the file keeps the same layout.").pack(fill="x")
        form = tk.Frame(box)
        form.pack(fill="x", pady=3)
        self.ans_exch, self.ans_sym = tk.StringVar(self), tk.StringVar(self)
        self.ans_tf, self.ans_date, self.ans_tz = tk.StringVar(self), tk.StringVar(self), tk.StringVar(self)
        tk.Label(form, text="Exchange:").grid(row=0, column=0, sticky="w")
        self.ans_exch_entry = tk.Entry(form, textvariable=self.ans_exch, width=8)
        self.ans_exch_entry.grid(row=0, column=1, sticky="w")
        tk.Label(form, text="Symbol:").grid(row=0, column=2, sticky="w", padx=(10, 0))
        self.ans_sym_entry = tk.Entry(form, textvariable=self.ans_sym, width=16)
        self.ans_sym_entry.grid(row=0, column=3, sticky="w")
        tk.Label(form, text="Timeframe:").grid(row=0, column=4, sticky="w", padx=(10, 0))
        self.ans_tf_box = ttk.Combobox(form, textvariable=self.ans_tf, values=ss.TIMEFRAMES, width=6, state="readonly")
        self.ans_tf_box.grid(row=0, column=5, sticky="w")
        tk.Label(form, text="Date layout:").grid(row=1, column=0, sticky="w")
        self.ans_date_box = ttk.Combobox(form, textvariable=self.ans_date, values=(), width=24, state="readonly")
        self.ans_date_box.grid(row=1, column=1, columnspan=3, sticky="w")
        tk.Label(form, text="Market time zone:").grid(row=1, column=4, sticky="w", padx=(10, 0))
        self.ans_tz_box = ttk.Combobox(form, textvariable=self.ans_tz, values=ss.COMMON_ZONES, width=16)
        self.ans_tz_box.grid(row=1, column=5, sticky="w")
        self.answer_button = tk.Button(form, text="Save answer", command=self.save_answer)
        self.answer_button.grid(row=0, column=6, rowspan=2, padx=10)
        self._date_ids: dict[str, str] = {}

        box = section(self, "Progress / Status")
        self.stage_var, self.item_var = tk.StringVar(self, value="Idle"), tk.StringVar(self, value="-")
        self.items_var, self.started_var = tk.StringVar(self, value="0 / 0"), tk.StringVar(self, value="-")
        self.elapsed_var, self.counts_var = tk.StringVar(self, value="-"), tk.StringVar(self, value="-")
        for i, (label, var) in enumerate((("Stage:", self.stage_var), ("Current file:", self.item_var),
                                          ("Files done:", self.items_var), ("Started:", self.started_var),
                                          ("Elapsed:", self.elapsed_var), ("Results so far:", self.counts_var))):
            r, c = divmod(i, 2)
            tk.Label(box, text=label, anchor="w", width=16).grid(row=r, column=c * 2, sticky="w")
            tk.Label(box, textvariable=var, anchor="w", width=48, justify="left").grid(row=r, column=c * 2 + 1, sticky="w")
        self.progress = ttk.Progressbar(box, mode="determinate", maximum=100)
        self.progress.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.final_label = tk.Label(box, text="", anchor="w", justify="left", wraplength=940, font=bold)
        self.final_label.grid(row=4, column=0, columnspan=4, sticky="w")
        box.columnconfigure(1, weight=1)
        box.columnconfigure(3, weight=1)

        box = section(self, "Live Log")
        self.log = LogText(box, height=9)
        self.log.pack(fill="both", expand=True)

    # ---- data ------------------------------------------------------------------------------------------------------
    def on_show(self) -> None:
        if not self.running:
            self.refresh()

    def selected_source(self) -> int | None:
        sel = self.sources_tree.selection()
        return self.source_rows.get(sel[0]) if sel else None

    def selected_file(self):
        sel = self.files_tree.selection()
        return self.file_rows.get(sel[0]) if sel else None

    def refresh(self) -> None:
        if self._closing:
            return
        keep = self.selected_source()
        self.sources_tree.delete(*self.sources_tree.get_children())
        self.source_rows.clear()
        settings = self.app.core_settings
        if settings is not None:
            try:
                items = ss.sources(settings)
            except Exception as exc:
                self.details.set(f"The Data Registry could not be read: {exc}", "error")
                items = []
            for s in items:
                item = self.sources_tree.insert("", "end", values=ss.source_row(s))
                self.source_rows[item] = s.source_id
                if s.source_id == keep or (keep is None and len(items) == 1):
                    self.sources_tree.selection_set(item)
        self.source_count.configure(text=f"[{len(self.source_rows)} folder(s)]")
        self.refresh_files()

    def on_source_select(self) -> None:
        sid, settings = self.selected_source(), self.app.core_settings
        if sid is not None and settings is not None:
            src = next((s for s in ss.sources(settings) if s.source_id == sid), None)
            if src is not None:
                self.tz_var.set(src.market_timezone or "")
                self.exch_var.set(src.default_exchange or "")
                self.symname_var.set(src.symbol_from_filename)
                self.sub_var.set(src.include_subfolders)
                self.exclude_var.set(", ".join(src.exclude_patterns))
        self.refresh_files()

    def refresh_files(self) -> None:
        if self._closing:
            return
        keep = self.selected_file()
        keep_path = keep.relative_path if keep is not None else None
        self.files_tree.delete(*self.files_tree.get_children())
        self.file_rows.clear()
        sid, settings = self.selected_source(), self.app.core_settings
        states = []
        if sid is not None and settings is not None:
            try:
                states = ss.files(settings, sid)
            except Exception as exc:
                self.details.set(f"Could not read the scan results: {exc}", "error")
        shown = [s for s in states if not self.attention_var.get() or s.outcome in ss.ATTENTION]
        for s in shown:
            item = self.files_tree.insert("", "end", values=ss.file_row(s), tags=(TAGS.get(s.outcome, ""),))
            self.file_rows[item] = s
            if s.relative_path == keep_path:
                self.files_tree.selection_set(item)
        self.files_count.configure(text=ss.counts_text(states) if sid is not None else "")
        if not self.files_tree.selection():
            if settings is None:
                self.details.set("Choose your two folders on the Home screen first.", "muted")
            elif sid is None:
                self.details.set("Add a folder, or select one in section 1." if not self.source_rows
                                 else "Select a folder in section 1.", "muted")
            elif not states:
                self.details.set("This folder has not been scanned yet. Press SCAN SELECTED FOLDER NOW.", "muted")
            else:
                self.details.set("Select a file to see how it was read, and any question about it.", "muted")
        self.on_file_select()

    def on_file_select(self) -> None:
        s = self.selected_file()
        keys = ss.question_keys(s) if s is not None else set()
        if s is not None:
            self.details.set_parts(ss.file_details(s))
        opts = ss.date_options(s) if s is not None else []
        self._date_ids = dict(opts)
        self.ans_date_box.configure(values=[label for label, _ in opts])
        for var in (self.ans_exch, self.ans_sym, self.ans_tf, self.ans_date, self.ans_tz):
            var.set("")
        states = {self.ans_exch_entry: bool(keys & {"identity", "exchange"}), self.ans_sym_entry: "identity" in keys,
                  self.ans_tf_box: "timeframe" in keys, self.ans_date_box: "date_format" in keys,
                  self.ans_tz_box: "market_timezone" in keys}
        for widget, on in states.items():
            readonly = widget in (self.ans_tf_box, self.ans_date_box)
            widget.configure(state=("readonly" if readonly else "normal") if on and not self.running else "disabled")
        self._update_state()

    def _update_state(self) -> None:
        settings, sid, f = self.app.core_settings, self.selected_source(), self.selected_file()
        idle = not self.running and settings is not None
        self.add_button.configure(state="normal" if idle else "disabled")
        for b in (self.save_button, self.remove_button, self.scan_button):
            b.configure(state="normal" if idle and sid is not None else "disabled")
        self.answer_button.configure(state="normal" if idle and f is not None and f.questions else "disabled")
        if self.running:
            self.hint.configure(text="Scanning...", fg=MUTED_COLOR)
        elif settings is None:
            self.hint.configure(text="Next step: choose your two folders on the Home screen.", fg=WARN_COLOR)
        elif not self.source_rows:
            self.hint.configure(text="Next step: Add folder... (section 1).", fg=WARN_COLOR)
        elif sid is None:
            self.hint.configure(text="Select a folder in section 1.", fg=MUTED_COLOR)
        else:
            waiting = sum(1 for s in self.file_rows.values() if s.outcome == "needs_answer")
            self.hint.configure(text=(f"{waiting} file(s) need your answer: select one in section 2." if waiting
                                      else "Ready to scan."), fg=WARN_COLOR if waiting else OK_COLOR)

    # ---- actions ---------------------------------------------------------------------------------------------------
    def _source_options(self) -> dict:
        return {"market_timezone": self.tz_var.get().strip() or None, "default_exchange": self.exch_var.get().strip() or None,
                "symbol_from_filename": bool(self.symname_var.get()), "include_subfolders": bool(self.sub_var.get()),
                "exclude_patterns": ss.parse_patterns(self.exclude_var.get())}

    def add_folder(self) -> None:
        settings = self.app.core_settings
        if settings is None or self.running:
            return
        folder = self.app.dialogs.ask_directory("Choose the folder with your market-data files", str(Path.home()))
        if not folder:
            return
        try:
            src = ss.add_source(settings, folder, **self._source_options())
        except (ss.SourceError, ValueError) as exc:
            self.app.dialogs.error("Q-MAP", ss.plain(exc))
            return
        self.log.append(f"Folder added: {src.label} ({src.location})")
        self.refresh()
        item = next(i for i, sid in self.source_rows.items() if sid == src.source_id)
        self.sources_tree.selection_set(item)
        self.on_source_select()

    def save_settings(self) -> None:
        sid, settings = self.selected_source(), self.app.core_settings
        if sid is None or settings is None or self.running:
            return
        try:
            ss.update_source(settings, sid, **self._source_options())
        except (ss.SourceError, ValueError) as exc:
            self.app.dialogs.error("Q-MAP", ss.plain(exc))
            return
        self.log.append("Folder settings saved. Files that were waiting are read again by the next scan.")
        self.refresh()

    def remove_folder(self) -> None:
        sid, settings = self.selected_source(), self.app.core_settings
        if sid is None or settings is None or self.running:
            return
        if not self.app.dialogs.yes_no("Stop using this folder", "Q-MAP will stop scanning this folder. Nothing is "
                                       "deleted: the folder and its files stay as they are, and data already loaded "
                                       "from it stay in Q-MAP.\n\nContinue?"):
            return
        ss.remove_source(settings, sid)
        self.log.append("Folder no longer scanned (its history and data are kept).")
        self.refresh()

    def save_answer(self) -> None:
        sid, f, settings = self.selected_source(), self.selected_file(), self.app.core_settings
        if sid is None or f is None or settings is None or self.running:
            return
        answers = {"exchange": self.ans_exch.get(), "symbol": self.ans_sym.get(), "timeframe": self.ans_tf.get(),
                   "date_format": self._date_ids.get(self.ans_date.get(), ""), "market_timezone": self.ans_tz.get()}
        keys = ss.question_keys(f)
        missing = [name for key, name, given in (("identity", "exchange and symbol", answers["exchange"] and answers["symbol"]),
                                                 ("exchange", "exchange", answers["exchange"]),
                                                 ("timeframe", "timeframe", answers["timeframe"]),
                                                 ("date_format", "date layout", answers["date_format"]),
                                                 ("market_timezone", "market time zone", answers["market_timezone"]))
                   if key in keys and not given]
        if missing:
            self.app.dialogs.warn("Q-MAP", "Please give: " + ", ".join(missing) + ".")
            return
        try:
            ss.save_answer(settings, sid, f.relative_path, {k: v for k, v in answers.items() if v})
        except (ss.SourceError, ValueError) as exc:
            self.app.dialogs.error("Q-MAP", ss.plain(exc))
            return
        self.log.append(f"Answer recorded for {f.relative_path}. Scan again to load it.")
        self.final_label.configure(text="Answer recorded. Press SCAN SELECTED FOLDER NOW to load the file.", fg=OK_COLOR)

    def scan(self) -> None:
        sid, settings = self.selected_source(), self.app.core_settings
        if sid is None or settings is None or self.running:
            return
        job = ss.ScanJob(settings, sid)
        self._job = job
        self.app.active_job = job
        self.running, self._t0 = True, time.monotonic()
        self.started_var.set(fmt_clock(datetime.now()))
        self.elapsed_var.set("0 s")
        self.items_var.set("0 / ?")
        self.counts_var.set("-")
        self.progress.configure(value=0)
        self.final_label.configure(text="", fg="black")
        self.log.append("--- scan ---")
        self.on_file_select()

        def work(emit):
            job.emit = emit
            job.run()

        self.app.tasks.start(work, self.on_job_event, self.on_task_error)

    # ---- events from the worker (always handled on the main thread) -----------------------------------
    def on_job_event(self, ev: dict) -> None:
        if self._closing:
            return
        kind = ev["type"]
        if kind == "log":
            self.log.append(ev["text"])
        elif kind == "stage":
            self.stage_var.set(ev["text"])
        elif kind == "run_started":
            self.last_run_dir = Path(ev["run_dir"])
            self.open_run_button.configure(state="normal")
        elif kind == "progress":
            self.item_var.set(ev["label"] or "-")
            self.items_var.set(f"{ev['done']} / {ev['total']}")
            self.progress.configure(value=100 * ev["done"] / max(ev["total"], 1))
        elif kind == "file":
            self.log.append(ev["text"])
        elif kind == "done":
            self._finish(ev["summary"])

    def on_task_error(self, text: str) -> None:
        if self._closing:
            return
        self.log.append(f"ERROR {text}")
        self._finish(ss.ScanSummary(error=text))

    def _finish(self, summary) -> None:
        self.running = False
        self.app.active_job = None
        self.stage_var.set("Finished")
        self.item_var.set("-")
        if summary.report_path:
            self.last_report = summary.report_path
            self.report_var.set(str(summary.report_path))
        self.counts_var.set(summary.summary or "-")
        if summary.error:
            self.final_label.configure(text=f"Stopped: {summary.error}", fg=ERROR_COLOR)
        elif getattr(summary, "incomplete", None):
            self.final_label.configure(
                text=f"Scan INCOMPLETE: {summary.incomplete} The files that could be read were processed. Fix the "
                     f"folder's access and scan again. Run {summary.run_id}.", fg=ERROR_COLOR)
        else:
            attention = sum(n for k, n in summary.counts.items() if k in ss.ATTENTION)
            self.final_label.configure(
                text=f"Scan finished ({summary.summary}). Run {summary.run_id}." +
                     (" Some files need attention: see section 2." if attention else ""),
                fg=WARN_COLOR if attention else OK_COLOR)
        self.refresh()

    def _tick(self) -> None:
        if getattr(self, "_closing", False):
            return
        if self.running and self._t0 is not None:
            self.elapsed_var.set(fmt_duration(time.monotonic() - self._t0))
        self.after(500, self._tick)

    def open_run_folder(self) -> None:
        if self.last_run_dir is not None:
            ok, msg = open_in_file_manager(self.last_run_dir)
            if not ok:
                self.app.dialogs.warn("Q-MAP", msg)
