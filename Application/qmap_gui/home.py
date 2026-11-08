"""Home screen of either application: folders, the application's modules and their GENUINE readiness."""

from __future__ import annotations

import sys
import tkinter as tk

from qmap import CLEANING_CODE_VERSION, __version__ as FOUNDATION_VERSION

from . import GUI_VERSION
from .locations import LocationsPanel
from .modules import ANALYTICAL_WORKBENCH, DATABASE_MANAGER, ModuleInfo, modules_for
from .widgets import MUTED_COLOR, OK_COLOR, ReadOnlyText, section

INTRO = {
    DATABASE_MANAGER: ("Welcome to Q-MAP Database Manager",
                       "Prepare the market data that every analysis depends on: load and check source files, see what "
                       "has been prepared and where it is stored, keep it Permanent or Temporary, and derive weekly, "
                       "monthly, quarterly and yearly data. Original files are never changed. Research runs in the "
                       "separate Analytical Workbench (analytical_workbench.py), which uses the data prepared here."),
    ANALYTICAL_WORKBENCH: ("Welcome to Q-MAP Analytical Workbench",
                           "Run analyses on data already prepared in Database Manager. Each analysis checks that the "
                           "data it needs are ready before it starts, and every run is saved with a Run ID and a full "
                           "record of its inputs. The Workbench never imports source files: prepare data in Database "
                           "Manager (database_manager.py). Modules marked COMING SOON are not built yet."),
}


class HomeFrame(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        key = getattr(app, "APP_KEY", DATABASE_MANAGER) or DATABASE_MANAGER
        title, text = INTRO[key]
        tk.Label(self, text=title, font=("TkDefaultFont", 13, "bold"), anchor="w").pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(self, anchor="w", justify="left", wraplength=940, text=text).pack(fill="x", padx=10)

        box = section(self, "Your folders (remembered between sessions, shared by both Q-MAP applications)")
        self.locations_panel = LocationsPanel(box, app)
        self.locations_panel.pack(fill="x")

        self.overview_box = None
        if key == DATABASE_MANAGER:
            box = section(self, "Data at a glance")
            self.overview_box = ReadOnlyText(box, height=2, mono=False)
            self.overview_box.pack(fill="x")
            app.add_location_listener(self.refresh_overview)
            self.refresh_overview()

        self.module_rows: dict[str, dict] = {}
        modules = modules_for(key)
        for group in dict.fromkeys(m.group for m in modules):
            heading = {"Application window": "Planned application windows",
                       "Research module": "Planned research modules"}.get(group, group)
            frame = section(self, heading)
            for r, module in enumerate(m for m in modules if m.group == group):
                self._row(frame, r, module)
            frame.columnconfigure(1, weight=1)

        tk.Label(self, fg=MUTED_COLOR, anchor="w",
                 text=f"Foundation {FOUNDATION_VERSION} (processing {CLEANING_CODE_VERSION})   |   GUI {GUI_VERSION}   |   "
                      f"Python {sys.version.split()[0]}   |   Tk {tk.TkVersion}").pack(fill="x", padx=10, pady=(2, 8))

    def refresh_overview(self) -> None:
        if getattr(self.app, "_closing", False) or self.overview_box is None:
            return
        if self.app.core_settings is None:
            self.overview_box.set("Choose your two folders above to see your data.", "muted")
            return
        from .registry_services import overview_text

        try:
            self.overview_box.set(overview_text(self.app.core_settings))
        except Exception as exc:  # a damaged registry must not stop the window from opening
            self.overview_box.set(f"The data registry could not be read: {exc}", "error")

    def on_show(self) -> None:
        self.refresh_overview()

    def _row(self, parent: tk.Frame, r: int, module: ModuleInfo) -> None:
        tk.Label(parent, text=module.name, font=("TkDefaultFont", 10, "bold"), anchor="w", width=26).grid(row=r * 2, column=0, sticky="w")
        tk.Label(parent, text=module.description, anchor="w", justify="left", wraplength=520).grid(row=r * 2, column=1, sticky="w")
        status = tk.Label(parent, text="READY" if module.is_ready else "COMING SOON", width=13,
                          fg="white", bg=OK_COLOR if module.is_ready else MUTED_COLOR)
        status.grid(row=r * 2, column=2, padx=6, pady=1)
        target = module.screen if module.is_ready and module.screen in self.app.screens_planned() else ""
        button = tk.Button(parent, text="Open", width=8, state="normal" if target else "disabled",
                           command=(lambda t=target: self.app.show(t)) if target else None)
        button.grid(row=r * 2, column=3)
        tk.Label(parent, text=module.note, anchor="w", justify="left", fg=MUTED_COLOR, wraplength=760).grid(
            row=r * 2 + 1, column=0, columnspan=4, sticky="w", padx=(0, 0), pady=(0, 3))
        self.module_rows[module.key] = {"status": status, "button": button}
