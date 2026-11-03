"""Q-MAP OW-33 impact report (READ-ONLY). Open this file in IDLE or Thonny and press F5.

Owner decision D5-49 (03-Nov-26), step 1 only: lists every active MIXED dataset and shows whether Option C
(sparse-only alignment of the timeframe sampling) WOULD change its classification. Nothing is changed: the registry
is opened read-only, no dataset or file is touched, Option C is not applied and nothing is reprocessed.
The report (CSV for Excel, and a short summary) is saved in Q-MAP_OUTPUT\\OW33_Impact\\.
"""

import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "Application"))

TITLE = "Q-MAP OW-33 impact report (read-only)"


def _roots(root_window):
    """The Q-MAP_DATA / Q-MAP_OUTPUT folders the Q-MAP applications remember; asked for if not remembered."""
    from tkinter import filedialog

    from qmap_gui.settings_store import GuiSettingsStore, default_settings_dir

    data, out = "", ""
    try:
        saved = GuiSettingsStore(default_settings_dir(), HERE).load()
        data, out = saved.data_root, saved.output_root
    except Exception:  # noqa: BLE001 - fall back to asking
        pass
    if not data or not Path(data).is_dir():
        data = filedialog.askdirectory(parent=root_window, title="Choose your Q-MAP_DATA folder")
    if not out or not Path(out).is_dir():
        out = filedialog.askdirectory(parent=root_window, title="Choose your Q-MAP_OUTPUT folder")
    return data, out


def main() -> int:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    try:
        data, out = _roots(root)
        if not data or not out:
            messagebox.showinfo(TITLE, "No folder chosen; nothing was done.", parent=root)
            return 1
        from qmap.core.config import load_settings
        from qmap.data_engine import ow33_impact as O

        settings = load_settings(None, env={"QMAP_DATA_ROOT": data, "QMAP_OUTPUT_ROOT": out}, code_root=HERE,
                                 create_layout=False)
        if not settings.db_path.is_file():
            messagebox.showerror(TITLE, f"No Q-MAP registry found in {data}.", parent=root)
            return 1
        conn = O.open_read_only(settings.db_path)
        try:
            rows = O.impact_rows(conn, settings.data_path)
        finally:
            conn.close()
        stamp = datetime.now().strftime("%d_%b_%y_%H%M%S")
        csv_path, txt = O.write_report(rows, settings.output_root / "OW33_Impact", stamp)
        s = O.summary(rows)
        messagebox.showinfo(TITLE, f"Active MIXED datasets examined: {s['mixed_datasets']}\n"
                                   f"Would change classification: {s['would_change']}\n"
                                   f"Would stay MIXED: {s['unchanged']}\n"
                                   f"Not evaluable: {s['not_evaluable']}\n\n"
                                   f"Nothing was changed.\n\nReport saved:\n{csv_path}\n{txt}", parent=root)
        return 0
    except Exception as exc:  # noqa: BLE001 - shown to the user, nothing was changed
        messagebox.showerror(TITLE, f"The report could not be produced: {exc}\n\nNothing was changed.", parent=root)
        return 1
    finally:
        try:
            root.destroy()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
