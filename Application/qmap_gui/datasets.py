"""Datasets and Storage screen (Database Manager): what has been prepared, where it is, and what can be done with it.

This file only builds the screen and reacts to clicks. Listing, checking, moving, deleting and deriving are done by
the Foundation through qmap_gui.registry_services, in a worker thread that only posts events to a queue.
"""

from __future__ import annotations

import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from . import registry_services as rs
from .common import fmt_clock, fmt_duration, open_in_file_manager
from .widgets import ERROR_COLOR, MUTED_COLOR, OK_COLOR, WARN_COLOR, LogText, ReadOnlyText, section

COLUMNS = (("id", "Dataset", 60), ("instrument", "Instrument", 150), ("tf", "Timeframe", 90), ("kind", "Type", 100),
           ("bars", "Bars", 60), ("from", "From", 80), ("to", "To", 80), ("validation", "Validation", 140),
           ("storage", "Storage", 85), ("state", "State", 90))
TIMEFRAME_FILTER = ("", "1m", "5m", "15m", "30m", "1h", "3h", "4h", "1D", "1W", "1M", "1Q", "1Y")


class DatasetsFrame(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.rows: dict[str, int] = {}  # tree item -> dataset id
        self.running = False
        self.last_run_dir: Path | None = None
        self._job = None
        self._t0: float | None = None
        self._total = self._done = 0
        self._ok = self._bad = 0
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
        box = section(self, "1. Input - prepared datasets in the Data Registry")
        row = tk.Frame(box)
        row.pack(fill="x")
        tk.Label(row, text="Timeframe:").pack(side="left")
        self.tf_var = tk.StringVar(self, value="")
        tf = ttk.Combobox(row, textvariable=self.tf_var, values=TIMEFRAME_FILTER, width=6, state="readonly")
        tf.pack(side="left", padx=(2, 10))
        tf.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.superseded_var, self.deleted_var = tk.BooleanVar(self, value=False), tk.BooleanVar(self, value=False)
        tk.Checkbutton(row, text="Show superseded", variable=self.superseded_var, command=self.refresh).pack(side="left")
        tk.Checkbutton(row, text="Show deleted", variable=self.deleted_var, command=self.refresh).pack(side="left")
        tk.Button(row, text="Refresh", command=self.refresh).pack(side="left", padx=6)
        self.count_label = tk.Label(row, text="[0 selected of 0]", fg=MUTED_COLOR)
        self.count_label.pack(side="left", padx=8)
        tf_frame = tk.Frame(box)
        tf_frame.pack(fill="x", pady=4)
        self.tree = ttk.Treeview(tf_frame, columns=[c[0] for c in COLUMNS], show="headings", height=9, selectmode="extended")
        for key, text, width in COLUMNS:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="w", stretch=key in ("instrument", "validation"))
        sb = tk.Scrollbar(tf_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="x", expand=True)
        self.tree.tag_configure("temporary", foreground=WARN_COLOR)
        self.tree.tag_configure("inactive", foreground=MUTED_COLOR)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.on_select())
        tk.Label(box, text="Details of the selected dataset:", anchor="w", fg=MUTED_COLOR).pack(fill="x")
        self.details = ReadOnlyText(box, height=9, mono=False)
        self.details.pack(fill="x")

        box = section(self, "2. Output - where datasets are kept")
        self.where_var = tk.StringVar(self, value="-")
        tk.Label(box, textvariable=self.where_var, anchor="w", justify="left", wraplength=940).pack(fill="x")
        row = tk.Frame(box)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text="Last run folder:", width=18, anchor="w").pack(side="left")
        self.run_folder_var = tk.StringVar(self, value="(none yet)")
        tk.Label(row, textvariable=self.run_folder_var, anchor="w", fg=MUTED_COLOR).pack(side="left", fill="x", expand=True)
        self.open_run_button = tk.Button(row, text="Open run folder", state="disabled", command=self.open_run_folder)
        self.open_run_button.pack(side="right")
        self.open_data_button = tk.Button(row, text="Open data folder", command=self.open_data_folder)
        self.open_data_button.pack(side="right", padx=4)

        box = section(self, "3. Options - actions on the selected dataset(s)")
        tk.Label(box, anchor="w", justify="left", wraplength=940, fg=MUTED_COLOR,
                 text="Permanent data are kept for good. Temporary data are kept in a separate folder until YOU delete "
                      "them; they never expire. Original source files are never moved, changed or deleted. Every "
                      "action is checked first and you see what it will do before anything happens.").pack(fill="x")
        row = tk.Frame(box)
        row.pack(fill="x", pady=3)
        self.temp_button = tk.Button(row, text="Move to Temporary", command=lambda: self.storage_action(rs.TEMPORARY))
        self.perm_button = tk.Button(row, text="Make Permanent", command=lambda: self.storage_action(rs.PERMANENT))
        self.delete_button = tk.Button(row, text="Delete Temporary dataset...", fg=ERROR_COLOR,
                                       command=lambda: self.storage_action("delete"))
        for b in (self.temp_button, self.perm_button, self.delete_button):
            b.pack(side="left", padx=2)
        row = tk.Frame(box)
        row.pack(fill="x", pady=3)
        tk.Label(row, text="Derive from daily data:").pack(side="left")
        self.derive_vars = {}
        for tf_key in rs.DERIVABLE:
            var = tk.BooleanVar(self, value=tf_key == "1W")
            tk.Checkbutton(row, text=rs.timeframe_label(tf_key), variable=var).pack(side="left")
            self.derive_vars[tf_key] = var
        self.derive_button = tk.Button(row, text="DERIVE SELECTED TIMEFRAMES", font=bold, padx=10,
                                       command=self.derive_action)
        self.derive_button.pack(side="left", padx=8)
        tk.Label(box, anchor="w", justify="left", wraplength=940, fg=MUTED_COLOR,
                 text="Weekly/monthly/quarterly/yearly bars: first open, highest high, lowest low, last close, summed "
                      "volume. Each bar is dated by its last trading day, so it never appears before its data exist. "
                      "The first and last period may be incomplete (there is no trading calendar yet) and are "
                      "flagged.").pack(fill="x")
        self.reason_var = tk.StringVar(self)
        row = tk.Frame(box)
        row.pack(fill="x", pady=3)
        tk.Label(row, text="Reason (recorded):", width=18, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=self.reason_var, width=70).pack(side="left")
        self.hint = tk.Label(box, text="", anchor="w", justify="left", wraplength=940)
        self.hint.pack(fill="x", pady=(4, 0))

        box = section(self, "Progress / Status")
        self.stage_var, self.item_var = tk.StringVar(self, value="Idle"), tk.StringVar(self, value="-")
        self.items_var, self.started_var = tk.StringVar(self, value="0 / 0"), tk.StringVar(self, value="-")
        self.elapsed_var, self.counts_var = tk.StringVar(self, value="-"), tk.StringVar(self, value="-")
        for i, (label, var) in enumerate((("Stage:", self.stage_var), ("Current item:", self.item_var),
                                          ("Items done:", self.items_var), ("Started:", self.started_var),
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
            self.where_var.set("Choose your two folders on the Home screen first.")
            self.details.set("")
            self._update_state()
            return
        self.where_var.set(f"Permanent: {settings.data_root / 'Cleaned_Data'} and {settings.timeframe_dir}\n"
                           f"Temporary: {settings.temporary_dir}\nOriginal files (never changed): {settings.raw_dir}")
        try:
            infos = rs.datasets(settings, include_superseded=self.superseded_var.get(),
                                include_deleted=self.deleted_var.get(), timeframe=self.tf_var.get())
        except Exception as exc:
            self.details.set(f"The Data Registry could not be read: {exc}", "error")
            self._update_state()
            return
        for d in infos:
            tags = ("temporary",) if d.storage_class == rs.TEMPORARY else ()
            if d.status != "active" or not d.available:
                tags = tags + ("inactive",)
            item = self.tree.insert("", "end", values=rs.row_values(d), tags=tags)
            self.rows[item] = d.dataset_id
            if d.dataset_id in keep:
                self.tree.selection_add(item)
        if not infos:
            self.details.set("No prepared datasets yet. Load files in Data Management first." if not
                             (self.tf_var.get() or self.superseded_var.get() or self.deleted_var.get())
                             else "No dataset matches this filter.", "muted")
        self._update_state()

    def on_select(self) -> None:
        ids = self.selected_ids()
        if len(ids) == 1 and self.app.core_settings is not None:
            try:
                self.details.set_parts(rs.details(self.app.core_settings, ids[0]))
            except Exception as exc:
                self.details.set(f"Could not read this dataset's details: {exc}", "error")
        elif len(ids) > 1:
            self.details.set(f"{len(ids)} datasets selected. Actions apply to each of them; each is checked first.",
                             "muted")
        self._update_state()

    def _update_state(self) -> None:
        n, total = len(self.selected_ids()), len(self.rows)
        self.count_label.configure(text=f"[{n} selected of {total}]")
        can = n > 0 and not self.running and self.app.core_settings is not None
        for b in (self.temp_button, self.perm_button, self.delete_button, self.derive_button):
            b.configure(state="normal" if can else "disabled")
        if self.running:
            self.hint.configure(text="Working...", fg=MUTED_COLOR)
        elif self.app.core_settings is None:
            self.hint.configure(text="Next step: choose your two folders on the Home screen.", fg=WARN_COLOR)
        elif not n:
            self.hint.configure(text="Select one or more datasets in section 1.", fg=MUTED_COLOR)
        else:
            self.hint.configure(text="Ready. Choose an action.", fg=OK_COLOR)

    # ---- actions ---------------------------------------------------------------------------------------------------
    def storage_action(self, action: str) -> None:
        ids, settings = self.selected_ids(), self.app.core_settings
        if not ids or settings is None or self.running:
            return
        assessments = rs.assess_storage(settings, ids, action)
        verb = {"delete": "DELETE", rs.TEMPORARY: "MOVE TO TEMPORARY", rs.PERMANENT: "MAKE PERMANENT"}[action]
        text, any_ok = rs.confirmation_text(assessments, verb)
        if not any_ok:
            self.app.dialogs.warn("Nothing can be done", text)
            return
        confirm_runs = False
        if action == "delete":
            if not self.app.dialogs.yes_no("Delete Temporary data", text + "\n\nThe data files will be deleted. This "
                                           "cannot be undone. Continue?"):
                return
            if any(a.allowed and a.run_uses for a in assessments):
                confirm_runs = self.app.dialogs.yes_no(
                    "Used by research runs", "Some of these datasets were used by research runs. Their results stay, "
                    "but could no longer be reproduced from these datasets.\n\nDelete them anyway?")
                if not confirm_runs:
                    return
        elif not self.app.dialogs.yes_no(verb.capitalize(), text + "\n\nContinue?"):
            return
        items = rs.storage_items(assessments, action, reason=self.reason_var.get(), confirm_run_inputs=confirm_runs)
        self._start(f"storage:{action}", items, {"dataset_ids": [a.dataset_id for a in assessments if a.allowed],
                                                  "reason": self.reason_var.get().strip()})

    def derive_action(self) -> None:
        ids, settings = self.selected_ids(), self.app.core_settings
        tfs = [tf for tf, var in self.derive_vars.items() if var.get()]
        if not ids or settings is None or self.running:
            return
        if not tfs:
            self.app.dialogs.warn("Q-MAP", "Tick at least one timeframe to derive.")
            return
        assessments = rs.assess_derive(settings, ids, tfs)
        text, any_ok = rs.confirmation_text(assessments, "DERIVE")
        if not any_ok:
            self.app.dialogs.warn("Nothing can be derived", text)
            return
        if not self.app.dialogs.yes_no("Derive timeframes", text + "\n\nContinue?"):
            return
        self._start("derive", rs.derive_items(assessments), {"dataset_ids": ids, "timeframes": tfs})

    def _start(self, title: str, items, params) -> None:
        if not items:
            return
        job = rs.OperationJob(self.app.core_settings, title, items, params)
        self._job = job
        self.app.active_job = job
        self.running, self._t0 = True, time.monotonic()
        self._total, self._done, self._ok, self._bad = len(items), 0, 0, 0
        self.started_var.set(fmt_clock(datetime.now()))
        self.elapsed_var.set("0 s")
        self.items_var.set(f"0 / {len(items)}")
        self.counts_var.set("-")
        self.progress.configure(value=0)
        self.final_label.configure(text="", fg="black")
        self.log.append(f"--- {title}: {len(items)} item(s) ---")
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
        if kind == "log":
            self.log.append(ev["text"])
        elif kind == "stage":
            self.stage_var.set(ev["text"])
        elif kind == "run_started":
            self.last_run_dir = Path(ev["run_dir"])
            self.run_folder_var.set(str(self.last_run_dir))
            self.open_run_button.configure(state="normal")
        elif kind == "item_start":
            self.item_var.set(ev["label"])
            self.stage_var.set(f"Working on item {ev['index']} of {ev['total']}")
        elif kind == "item_done":
            self._done = ev["index"]
            if ev["ok"]:
                self._ok += 1
            else:
                self._bad += 1
            self.items_var.set(f"{self._done} / {self._total}")
            self.progress.configure(value=100 * self._done / max(self._total, 1))
            self.counts_var.set(f"{self._ok} done, {self._bad} not done")
            self.log.append(("OK      " if ev["ok"] else "NOT DONE ") + f"{ev['label']}: {ev['message']}")
        elif kind == "done":
            self._finish(ev["summary"])

    def on_task_error(self, text: str) -> None:
        if self._closing:
            return
        self.log.append(f"ERROR {text}")
        self._finish(rs.OperationSummary(error=text))

    def _finish(self, summary) -> None:
        self.running = False
        self.app.active_job = None
        self.stage_var.set("Finished")
        self.item_var.set("-")
        if summary.error:
            self.final_label.configure(text=f"Stopped: {summary.error}", fg=ERROR_COLOR)
        elif summary.failed:
            self.final_label.configure(text=f"{len(summary.done)} done, {len(summary.failed)} not done - see the log "
                                            "for the reason of each.", fg=WARN_COLOR)
        else:
            self.final_label.configure(text=f"All {len(summary.done)} done. Run {summary.run_id}.", fg=OK_COLOR)
        self.refresh()
        self.on_select()

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

    def open_data_folder(self) -> None:
        if self.app.core_settings is not None:
            ok, msg = open_in_file_manager(self.app.core_settings.data_root)
            if not ok:
                self.app.dialogs.warn("Q-MAP", msg)
