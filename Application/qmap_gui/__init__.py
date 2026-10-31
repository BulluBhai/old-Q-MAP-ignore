"""Q-MAP graphical application.

Layering (the GUI never contains data-processing logic):
  qmap_gui.app / home / data_management / profile_editor / widgets   - tkinter screens only
  qmap_gui.services / jobs / messages / settings_store / modules     - plain Python, no tkinter, fully testable
  qmap                                                               - the Foundation (processing, storage, registry)

The Foundation never imports anything from this package.
"""

GUI_VERSION = "0.1.0"
