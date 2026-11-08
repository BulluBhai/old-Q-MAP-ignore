"""The two-folder chooser shared by the Home and Data Management screens (same state, remembered between sessions)."""

from __future__ import annotations

import tkinter as tk

from .widgets import ERROR_COLOR, OK_COLOR


class LocationsPanel(tk.Frame):
    def __init__(self, master, app, show_help: bool = True):
        super().__init__(master)
        self.app = app
        self.rows = {}
        for r, (which, label, var) in enumerate((("data", "Q-MAP_DATA folder", app.data_var),
                                                  ("output", "Q-MAP_OUTPUT folder", app.output_var))):
            tk.Label(self, text=label, anchor="w").grid(row=r * 2, column=0, sticky="w")
            entry = tk.Entry(self, textvariable=var, width=60)
            entry.grid(row=r * 2, column=1, sticky="ew", padx=4)
            entry.bind("<Return>", lambda _e: app.apply_locations())
            entry.bind("<FocusOut>", lambda _e: app.apply_locations())
            browse = tk.Button(self, text="Browse...", command=lambda w=which: app.browse_location(w))
            browse.grid(row=r * 2, column=2, padx=2)
            create = tk.Button(self, text="Create folder", command=lambda w=which: app.create_location(w))
            create.grid(row=r * 2, column=3, padx=2)
            status = tk.Label(self, text="", anchor="w", justify="left", wraplength=760)
            status.grid(row=r * 2 + 1, column=1, columnspan=3, sticky="w", padx=4, pady=(0, 4))
            self.rows[which] = {"entry": entry, "browse": browse, "create": create, "status": status}
        self.summary = tk.Label(self, text="", anchor="w", justify="left", wraplength=860)
        self.summary.grid(row=4, column=0, columnspan=4, sticky="w")
        if show_help:
            tk.Label(self, anchor="w", justify="left", fg="#667085", wraplength=860,
                     text="Keep these two folders separate and outside the Q-MAP program folder. Your choice is "
                          "remembered. Q-MAP never puts data or results inside its program folder.").grid(
                row=5, column=0, columnspan=4, sticky="w")
        self.columnconfigure(1, weight=1)
        app.add_location_listener(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        state = self.app.locations
        for which, status in (("data", state.data), ("output", state.output)):
            row = self.rows[which]
            row["status"].configure(text=("OK - this folder can be used." if status.ok else status.message),
                                    fg=OK_COLOR if status.ok else ERROR_COLOR)
            row["create"].configure(state="normal" if status.can_create else "disabled")
        if self.app.core_settings is not None:
            self.summary.configure(text="Both folders are ready and remembered.", fg=OK_COLOR)
        else:
            self.summary.configure(text=self.app.core_problem or state.summary, fg=ERROR_COLOR)
