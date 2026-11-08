"""Home screen: the planned modules and their GENUINE readiness (from qmap_gui.modules)."""

from __future__ import annotations

import sys
import tkinter as tk

from qmap import CLEANING_CODE_VERSION, __version__ as FOUNDATION_VERSION

from . import GUI_VERSION
from .locations import LocationsPanel
from .modules import MODULES, ModuleInfo
from .widgets import MUTED_COLOR, OK_COLOR, section


class HomeFrame(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        tk.Label(self, text="Welcome to Q-MAP", font=("TkDefaultFont", 13, "bold"), anchor="w").pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(self, anchor="w", justify="left", wraplength=940,
                 text="One platform for market data, price-behaviour research, strategy testing and risk. This first "
                      "version has one working area: Data Management. Everything else is marked Coming Soon until it "
                      "genuinely works.").pack(fill="x", padx=10)

        box = section(self, "Your folders (remembered between sessions)")
        self.locations_panel = LocationsPanel(box, app)
        self.locations_panel.pack(fill="x")

        self.module_rows: dict[str, dict] = {}
        for group in ("Application window", "Research module"):
            frame = section(self, "Planned application windows" if group == "Application window" else "Planned research modules")
            for r, module in enumerate(m for m in MODULES if m.group == group):
                self._row(frame, r, module)
            frame.columnconfigure(1, weight=1)

        tk.Label(self, fg=MUTED_COLOR, anchor="w",
                 text=f"Foundation {FOUNDATION_VERSION} (processing {CLEANING_CODE_VERSION})   |   GUI {GUI_VERSION}   |   "
                      f"Python {sys.version.split()[0]}   |   Tk {tk.TkVersion}").pack(fill="x", padx=10, pady=(2, 8))

    def _row(self, parent: tk.Frame, r: int, module: ModuleInfo) -> None:
        tk.Label(parent, text=module.name, font=("TkDefaultFont", 10, "bold"), anchor="w", width=26).grid(row=r * 2, column=0, sticky="w")
        tk.Label(parent, text=module.description, anchor="w", justify="left", wraplength=520).grid(row=r * 2, column=1, sticky="w")
        status = tk.Label(parent, text="READY" if module.is_ready else "COMING SOON", width=13,
                          fg="white", bg=OK_COLOR if module.is_ready else MUTED_COLOR)
        status.grid(row=r * 2, column=2, padx=6, pady=1)
        button = tk.Button(parent, text="Open", width=8, state="normal" if module.is_ready else "disabled",
                           command=(lambda: self.app.show("data")) if module.key == "data_management" else None)
        button.grid(row=r * 2, column=3)
        tk.Label(parent, text=module.note, anchor="w", justify="left", fg=MUTED_COLOR, wraplength=760).grid(
            row=r * 2 + 1, column=0, columnspan=4, sticky="w", padx=(0, 0), pady=(0, 3))
        self.module_rows[module.key] = {"status": status, "button": button}
