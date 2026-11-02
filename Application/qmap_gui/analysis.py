"""Run an analysis screen (Analytical Workbench): choose an analysis and prepared datasets, check readiness, run.

This file only builds the screen and reacts to clicks. Readiness checks and runs are done by the analytical engine
through qmap_gui.workbench_services, in a worker thread that only posts events to a queue. Nothing here imports or
prepares source files.
"""

from __future__ import annotations

import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from . import workbench_services as ws
from .common import fmt_clock, fmt_duration, open_folder
from .widgets import (ERROR_COLOR, MUTED_COLOR, OK_COLOR, WARN_COLOR, DateEntry, LogText, ReadOnlyText, combobox_index,
                      section)

COLUMNS = (("id", "Dataset", 60), ("instrument", "Instrument", 150), ("tf", "Timeframe", 90), ("bars", "Bars", 60),
           ("from", "From", 80), ("to", "To", 80), ("validation", "Validation", 150), ("storage", "Storage", 85),
           ("state", "State", 90))
TIMEFRAME_FILTER = ("", "1m", "5m", "15m", "30m", "1h", "4h", "1D", "1W", "1M", "1Q", "1Y")


class AnalysisFrame(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.choices = ws.analyses()
        self.rows: dict[str, int] = {}
        self.param_vars: dict[str, tk.StringVar] = {}
        self.date_entries: dict[str, DateEntry] = {}
        self.running = False
        self.last_run_dir: Path | None = None  # folder of the latest COMPLETED run, as recorded for that run
        self.last_run_id: str | None = None
        self.last_result = None
        self.last_readiness = None
        self._last_selection: tuple = ()
        self._t0: float | None = None
        self._build()
        app.add_location_listener(self.refresh)
        self.refresh()
        self._tick()

    @property
    def _closing(self) -> bool:
        return bool(getattr(self.app, "_closing", False))

    @property
    def choice(self) -> ws.AnalysisChoice | None:
        i = combobox_index(self.analysis_combo)
        return self.choices[i] if 0 <= i < len(self.choices) else None

    # ---- layout ------------------------------------------------------------------------------------------------
    def _build(self) -> None:
        bold = tkfont.Font(weight="bold")
        box = section(self, "1. Input - analysis and prepared datasets")
        row = tk.Frame(box)
        row.pack(fill="x")
        tk.Label(row, text="Analysis:", width=10, anchor="w").pack(side="left")
        self.analysis_combo = ttk.Combobox(row, state="readonly", width=40, values=[c.name for c in self.choices])
        self.analysis_combo.pack(side="left")
        self.analysis_combo.bind("<<ComboboxSelected>>", lambda _e: self.on_analysis_selected())
        self.about = tk.Label(box, text="", anchor="w", justify="left", wraplength=940, fg=MUTED_COLOR)
        self.about.pack(fill="x", pady=(2, 4))
        row = tk.Frame(box)
        row.pack(fill="x")
        tk.Label(row, text="Timeframe:").pack(side="left")
        self.tf_var = tk.StringVar(self, value="")
        tf = ttk.Combobox(row, textvariable=self.tf_var, values=TIMEFRAME_FILTER, width=6, state="readonly")
        tf.pack(side="left", padx=(2, 10))
        tf.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.superseded_var = tk.BooleanVar(self, value=False)
        tk.Checkbutton(row, text="Show superseded", variable=self.superseded_var, command=self.refresh).pack(side="left")
        tk.Button(row, text="Refresh", command=self.refresh).pack(side="left", padx=6)
        self.count_label = tk.Label(row, text="[0 selected of 0]", fg=MUTED_COLOR)
        self.count_label.pack(side="left", padx=8)
        frame = tk.Frame(box)
        frame.pack(fill="x", pady=4)
        self.tree = ttk.Treeview(frame, columns=[c[0] for c in COLUMNS], show="headings", height=8, selectmode="extended")
        for key, text, width in COLUMNS:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="w", stretch=key in ("instrument", "validation"))
        sb = tk.Scrollbar(frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="x", expand=True)
        self.tree.tag_configure("inactive", foreground=MUTED_COLOR)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._selection_changed())
        self.empty_note = tk.Label(box, text="", anchor="w", justify="left", wraplength=940, fg=WARN_COLOR)
        self.empty_note.pack(fill="x")

        box = section(self, "2. Output - where results are saved")
        self.output_var = tk.StringVar(self, value="-")
        tk.Label(box, textvariable=self.output_var, anchor="w", justify="left", wraplength=940).pack(fill="x")
        row = tk.Frame(box)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text="Last run folder:", width=18, anchor="w").pack(side="left")
        self.run_folder_var = tk.StringVar(self, value="(no completed run yet)")
        # read-only Entry, not a Label: the path can be selected and copied (Ctrl+C)
        self.run_folder_entry = tk.Entry(row, textvariable=self.run_folder_var, state="readonly", relief="flat",
                                         readonlybackground=self.cget("background"))
        self.run_folder_entry.pack(side="left", fill="x", expand=True)
        self.open_run_button = tk.Button(row, text="Open Output Folder", state="disabled", command=self.open_run_folder)
        self.open_run_button.pack(side="right")

        box = section(self, "3. Options - parameters")
        self.params_frame = tk.Frame(box)
        self.params_frame.pack(fill="x")
        row = tk.Frame(box)
        row.pack(fill="x", pady=(6, 2))
        self.check_button = tk.Button(row, text="Check readiness (nothing is saved)", command=self.check, padx=8, pady=4)
        self.run_button = tk.Button(row, text="RUN ANALYSIS", command=self.start_run, padx=14, pady=4, font=bold)
        self.check_button.pack(side="left", padx=4)
        self.run_button.pack(side="left", padx=4)
        self.hint = tk.Label(box, text="", anchor="w", justify="left", wraplength=940)
        self.hint.pack(fill="x", pady=(4, 2))
        tk.Label(box, text="Readiness of the selected data:", anchor="w", fg=MUTED_COLOR).pack(fill="x")
        self.readiness_box = ReadOnlyText(box, height=10, mono=False)
        self.readiness_box.pack(fill="x")

        box = section(self, "Progress / Status")
        self.stage_var, self.started_var = tk.StringVar(self, value="Idle"), tk.StringVar(self, value="-")
        self.elapsed_var, self.datasets_var = tk.StringVar(self, value="-"), tk.StringVar(self, value="-")
        self.run_id_var = tk.StringVar(self, value="-")
        for i, (label, var) in enumerate((("Stage:", self.stage_var), ("Datasets:", self.datasets_var),
                                          ("Started:", self.started_var), ("Elapsed:", self.elapsed_var),
                                          ("Run ID:", self.run_id_var))):
            r, c = divmod(i, 2)
            tk.Label(box, text=label, anchor="w", width=12).grid(row=r, column=c * 2, sticky="w")
            tk.Label(box, textvariable=var, anchor="w", width=52, justify="left").grid(row=r, column=c * 2 + 1, sticky="w")
        self.progress = ttk.Progressbar(box, mode="indeterminate")
        self.progress.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.final_label = tk.Label(box, text="", anchor="w", justify="left", wraplength=940, font=bold)
        self.final_label.grid(row=4, column=0, columnspan=4, sticky="w")
        # the same action as section 2's button, next to the completion message: opens the completed run's own folder
        self.result_open_button = tk.Button(box, text="Open Output Folder", state="disabled",
                                            command=self.open_run_folder)
        self.result_open_button.grid(row=5, column=0, columnspan=4, sticky="w", pady=(4, 0))
        box.columnconfigure(1, weight=1)
        box.columnconfigure(3, weight=1)

        box = section(self, "Live Log")
        self.log = LogText(box, height=9)
        self.log.pack(fill="both", expand=True)

        if self.choices:
            self.analysis_combo.current(0)
            self.on_analysis_selected()

    # ---- state -------------------------------------------------------------------------------------------------
    def on_show(self) -> None:
        if not self.running:
            self.refresh()

    def on_analysis_selected(self) -> None:
        c = self.choice
        for w in self.params_frame.winfo_children():
            w.destroy()
        self.param_vars.clear()
        if c is None:
            self.about.configure(text="")
            return
        self.about.configure(text=f"{c.description}\nResult type: {c.kind_note}.")
        self.date_entries.clear()
        for r, p in enumerate(c.parameters):
            tk.Label(self.params_frame, text=p.label + ":", width=14, anchor="w").grid(row=r * 2, column=0, sticky="w")
            var = tk.StringVar(self)
            var.trace_add("write", lambda *_a: self._invalidate())
            if p.kind == "date":
                empty = p.help.split("Empty = ", 1)[1].rstrip(".") if "Empty = " in p.help else "not used"
                field = DateEntry(self.params_frame, var, parse=ws.parse_date_input, to_text=ws.date_to_entry_text,
                                  confirm=ws.date_confirmation, empty_note=f"(empty = {empty})")
                field.grid(row=r * 2, column=1, sticky="w")
                self.date_entries[p.key] = field
            else:
                tk.Entry(self.params_frame, textvariable=var, width=14).grid(row=r * 2, column=1, sticky="w")
            tk.Label(self.params_frame, text=p.help, fg=MUTED_COLOR, anchor="w").grid(row=r * 2 + 1, column=1, sticky="w")
            self.param_vars[p.key] = var
        self._invalidate()

    def selected_ids(self) -> list[int]:
        return [self.rows[i] for i in self.tree.selection() if i in self.rows]

    def refresh(self) -> None:
        if self._closing:
            return
        keep = set(self.selected_ids())
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        settings = self.app.core_settings
        if settings is None:
            self.output_var.set("Choose your two folders on the Home screen first.")
            self.empty_note.configure(text="")
            self._update_state()
            return
        self.output_var.set(f"Each run gets its own folder (named by its Run ID) in {ws.output_folder(settings)}. "
                            "An earlier run is never overwritten.")
        if not self.running:
            try:
                latest = ws.last_completed_run(settings)
            except Exception:  # an unreadable registry is reported below by the dataset list
                latest = None
            self._show_last_run(*(latest or (None, None)))
        try:
            infos = ws.ready_datasets(settings, include_superseded=self.superseded_var.get(), timeframe=self.tf_var.get())
        except Exception as exc:
            self.empty_note.configure(text=f"The Data Registry could not be read: {exc}", fg=ERROR_COLOR)
            self._update_state()
            return
        for d in infos:
            item = self.tree.insert("", "end", values=ws.row_values(d), tags=() if d.status == "active" else ("inactive",))
            self.rows[item] = d.dataset_id
            if d.dataset_id in keep:
                self.tree.selection_add(item)
        if not infos and not self.tf_var.get():
            self.empty_note.configure(text="No prepared datasets are available. " + ws.PREPARE_HINT, fg=WARN_COLOR)
        elif not infos:
            self.empty_note.configure(text="No prepared dataset has this timeframe. " + ws.PREPARE_HINT, fg=WARN_COLOR)
        else:
            self.empty_note.configure(text="")
        self._invalidate()

    def _selection_changed(self) -> None:
        # Tk delivers <<TreeviewSelect>> later, also when a refresh re-selects the same rows: only a REAL change of
        # the selection makes the readiness shown out of date.
        current = tuple(self.selected_ids())
        if current != self._last_selection:
            self._last_selection = current
            self._invalidate()
        else:
            self._update_state()

    def _invalidate(self) -> None:
        """Any change of choice means the readiness shown is out of date."""
        self.last_readiness = None
        if not self.running:
            self.readiness_box.set("Press 'Check readiness' (or Run) to check the selected data.", "muted")
        self._update_state()

    def params(self) -> dict:
        return {k: v.get() for k, v in self.param_vars.items()}

    def _update_state(self) -> None:
        n = len(self.selected_ids())
        self.count_label.configure(text=f"[{n} selected of {len(self.rows)}]")
        can = n > 0 and not self.running and self.app.core_settings is not None and self.choice is not None
        for b in (self.check_button, self.run_button):
            b.configure(state="normal" if can else "disabled")
        if self.running:
            self.hint.configure(text="Working...", fg=MUTED_COLOR)
        elif self.app.core_settings is None:
            self.hint.configure(text="Next step: choose your two folders on the Home screen.", fg=WARN_COLOR)
        elif not n:
            self.hint.configure(text="Next step: select one or more datasets in section 1.", fg=WARN_COLOR)
        else:
            self.hint.configure(text="Ready to check or run.", fg=OK_COLOR)

    # ---- actions -----------------------------------------------------------------------------------------------
    def check(self) -> None:
        c, settings = self.choice, self.app.core_settings
        if c is None or settings is None or not self.selected_ids():
            return
        try:
            res = ws.check(settings, c.analysis_id, self.selected_ids(), self.params())
        except Exception as exc:
            self.readiness_box.set(f"The readiness check could not be done: {exc}", "error")
            return
        self.last_readiness = res
        self._last_selection = tuple(self.selected_ids())  # the selection this result is for
        self.readiness_box.set_parts(ws.readiness_parts(res))
        self.log.append(f"Readiness checked: {'READY' if res.ready else 'NOT READY'} "
                        f"({len(res.reports)} dataset(s), {len(res.warnings)} warning(s))")

    def start_run(self) -> None:
        c, settings, ids = self.choice, self.app.core_settings, self.selected_ids()
        if c is None or settings is None or not ids or self.running:
            return
        self.check()  # always show the current readiness; the engine checks again itself before it starts
        if self.last_readiness is not None and not self.last_readiness.ready:
            why = {ws.INVALID_INPUT: "the dates are not valid", ws.NO_ELIGIBLE_DATA: "there are no bars in the chosen period"
                   }.get(self.last_readiness.state, "some selected datasets have no bars in the chosen period"
                         if self.last_readiness.partial_period_note else "the data are not ready")
            self.final_label.configure(text=f"Not started: {why} (see the readiness box).", fg=ERROR_COLOR)
            return
        job = ws.AnalysisJob(settings, c.analysis_id, ids, self.params())
        self.running, self._t0 = True, time.monotonic()
        self.started_var.set(fmt_clock(datetime.now()))
        self.elapsed_var.set("0 s")
        self.datasets_var.set(str(len(ids)))
        self.run_id_var.set("-")
        self.final_label.configure(text="", fg="black")
        self.progress.start(80)
        self.log.append(f"--- {c.name}: {len(ids)} dataset(s) ---")
        self._update_state()

        def work(emit):
            job.emit = emit
            job.run()

        self.app.tasks.start(work, self.on_job_event, self.on_task_error)

    # ---- events from the worker (always handled on the main thread) -----------------------------------
    def on_job_event(self, ev: dict) -> None:
        if self._closing:
            return
        kind = ev["type"]
        if kind in ("log", "progress"):
            self.log.append(ev["text"])
            if kind == "progress":
                self.stage_var.set(ev["text"][:90])
        elif kind == "stage":
            self.stage_var.set(ev["text"])
        elif kind == "done":
            self._finish(ev["result"])

    def on_task_error(self, text: str) -> None:
        if self._closing:
            return
        self.log.append(f"ERROR {text}")
        self._finish(ws.AnalysisRunResult("failed", text))

    def _finish(self, result) -> None:
        self.running = False
        self.last_result = result
        self.progress.stop()
        self.stage_var.set("Finished")
        if result.run_id:
            self.run_id_var.set(result.run_id)
        if result.ok and result.run_dir:  # only a COMPLETED run becomes "the last run"; its own recorded folder
            self._show_last_run(result.run_id, Path(result.run_dir))
        color = {"completed": OK_COLOR, "blocked": WARN_COLOR}.get(result.outcome, ERROR_COLOR)
        text = result.message
        if result.ok:
            text = (f"Completed. Run {result.run_id}: {', '.join(p.name for p in result.outputs)} and "
                    f"{result.metadata_path.name} saved in {result.run_dir}")
            if result.readiness and result.readiness.warnings:
                text += f"  ({len(result.readiness.warnings)} warning(s) - see the readiness box and the metadata file)"
        self.final_label.configure(text=text, fg=color)
        self._update_state()

    def _tick(self) -> None:
        if getattr(self, "_closing", False):
            return
        if self.running and self._t0 is not None:
            self.elapsed_var.set(fmt_duration(time.monotonic() - self._t0))
        self.after(500, self._tick)

    def _show_last_run(self, run_id: str | None, folder: Path | None) -> None:
        self.last_run_id, self.last_run_dir = run_id, folder
        self.run_folder_var.set(str(folder) if folder else "(no completed run yet)")
        for b in (self.open_run_button, self.result_open_button):
            b.configure(state="normal" if folder else "disabled")

    def open_run_folder(self) -> None:
        """Open the latest completed run's own folder. Only opens it; nothing is changed."""
        ok, msg = open_folder(self.last_run_dir, f"run {self.last_run_id}" if self.last_run_id else "this run")
        if not ok:
            self.app.dialogs.warn("Open Output Folder", msg)
