"""Drive the REAL Data Management window (under a virtual display) with the owner's 11 sample files.

For each file: Add file -> Browse for the profile file -> type exchange/symbol/timeframe into the boxes (as typing
does) -> Check files -> Load files into Q-MAP. Records what the window shows and saves a screenshot per file.
Writes only under <test_root>/gui_run. The samples are opened read-only.
"""
import json, subprocess, sys, tempfile, time
from pathlib import Path
REPO, SAMPLES, T = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path[:0] = [str(REPO / "Application"), str(REPO / "Tests")]
from gui.fakes import FakeDialogs  # noqa: E402
from qmap_gui.app import QMapApp, release_garbage_collector_if_idle  # noqa: E402

CASES = [(1, "csv headers iso.xlsx", "xlsx_headers_iso_offset", "F01", "5m"),
         (2, "csv headers std.csv", "csv_headers_dd_mm_yy", "F02", "1D"),
         (3, "csv headers unix.csv", "csv_headers_unix_seconds", "F03", "1m"),
         (4, "csv noheaders iso.csv", "csv_noheaders_iso_offset", "F04", "5m"),
         (5, "csv noheaders unix.csv", "csv_noheaders_unix_seconds", "F05", "1D"),
         (6, "ONESOURCE.parquet", "example_parquet_naive_timestamp", "F06", None),
         (7, "text headers ymd.txt", "example_text_headered_iso_date", "F07", None),
         (8, "text no headers ymd.txt", "example_text_headerless_seven_columns", "F08", None),
         (9, "xls headers iso.csv", "csv_headers_iso_offset", "F09", "5m"),
         (10, "xls headers std.xlsx", "xlsx_headers_native_date", "F10", "1D"),
         (11, "xls noheaders iso.xlsx", "xlsx_noheaders_iso_offset", "F11", "5m")]
G = T / "gui_run"
for d in ("DATA", "OUTPUT", "settings", "shots"):
    (G / d).mkdir(parents=True, exist_ok=True)
dialogs = FakeDialogs()
app = QMapApp(REPO, settings_dir=G / "settings", dialogs=dialogs)
app.geometry("1100x1000+0+0")
app.data_var.set(str(G / "DATA")); app.output_var.set(str(G / "OUTPUT")); assert app.apply_locations()
app.show("data"); dm = app.screens["data"]


def pump(sec=0.2):
    end = time.time() + sec
    while time.time() < end:
        app.update(); time.sleep(0.01)


def wait():
    end = time.time() + 300
    while time.time() < end and not dm.finished_event.is_set():
        app.update(); time.sleep(0.01)
    assert dm.finished_event.is_set()
    pump(0.3)


def rows():
    return [dm.tree.item(i)["values"] for i in dm.tree.get_children()]


out = []
for no, name, pid, sym, tf in CASES:
    r = {"no": no, "file": name, "profile": pid}
    dm.clear_files(); dm.add_paths([SAMPLES / name])
    dialogs.file.append(str(T / "profiles" / f"{pid}.toml")); dm.browse_profile(); pump()
    r["profile_selected"] = dm.current_info.profile.profile_id if dm.current_info and dm.current_info.profile else None
    r["boxes_enabled"] = {k: str(w.cget("state")) for k, w in (("exchange", dm.exchange_entry), ("symbol", dm.symbol_entry),
                                                                 ("timeframe", dm.timeframe_combo))}
    for w, text in ((dm.exchange_entry, "TEST"), (dm.symbol_entry, sym)):
        w.delete(0, "end")
        if str(w.cget("state")) == "normal":
            w.insert("end", text)
    if tf and str(dm.timeframe_combo.cget("state")) != "disabled":
        dm.timeframe_var.set(tf)
    pump()
    r["hint_before"] = dm.hint.cget("text")
    r["load_button"] = str(dm.run_button.cget("state"))
    dm.listbox.selection_clear(0, "end"); dm.listbox.selection_set(0); dm.preview_selected(); pump(1.5)
    r["preview_first_lines"] = dm.preview_box.text.get("1.0", "end").strip().splitlines()[:3]
    dm.check_files(); wait(); r["check_row"] = [str(x) for x in rows()[0]]
    dm.tree.selection_set(dm.tree.get_children()[0]); pump()
    r["check_explanation"] = dm.details.text.get("1.0", "end").strip()[:1500]
    if r["check_row"][1] == "Would be accepted":
        dm.start_ingest(); wait(); r["load_row"] = [str(x) for x in rows()[0]]
        r["final_line"] = dm.final_label.cget("text")
    else:
        r["load_row"] = "not attempted (check did not pass)"
    shot = G / "shots" / f"F{no:02d}_window.png"
    subprocess.run(["import", "-window", "root", "-crop", "1100x1000+0+0", str(shot)], check=False)
    r["screenshot"] = shot.name
    out.append(r)
    print(f"F{no:02d} {name:24} profile={r['profile_selected']:40} boxes={r['boxes_enabled']} load_btn={r['load_button']}"
          f" | check={r['check_row'][1]} | load={r['load_row'] if isinstance(r['load_row'], str) else r['load_row'][1]}")
(G / "gui_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
app._on_closing(); app.tasks.join_all(60); release_garbage_collector_if_idle()
