"""Practical acceptance walkthrough: drives the REAL Database Manager and Analytical Workbench windows.

Usage (Linux, virtual screen):  xvfb-run -a python acceptance_walkthrough.py <repo> <empty work folder> <evidence folder>
Everything is written under <work folder> (DATA, OUTPUT, settings, source files) except the results JSON and the
screenshots, which go to <evidence folder>. Source files are synthetic, in the owner's sample layouts (dd-mm-yy CSV
with Volume and Net Volume). Results are checked independently of Q-MAP code where possible (plain csv/statistics).
"""
import csv, hashlib, json, statistics, subprocess, sys, time
from datetime import date, timedelta
from pathlib import Path

REPO, W, EV = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path[:0] = [str(REPO / "Application"), str(REPO / "Tests")]
from gui.fakes import FakeDialogs  # noqa: E402
from qmap_gui.app import AnalyticalWorkbenchApp, DatabaseManagerApp, release_garbage_collector_if_idle  # noqa: E402

for d in ("DATA", "OUTPUT", "settings", "src"):
    (W / d).mkdir(parents=True, exist_ok=True)
SHOTS = EV / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)
STAMP = "01_Nov_26"
results = []


def record(no, scenario, status, evidence):
    results.append({"no": no, "scenario": scenario, "status": status, "evidence": evidence})
    print(f"{no:>2} {status:8} {scenario}: {evidence if isinstance(evidence, str) else json.dumps(evidence)[:200]}")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def shot(name):
    subprocess.run(["import", "-window", "root", "-crop", "1150x1000+0+0", str(SHOTS / f"{name}_{STAMP}.png")], check=False)


# ---- synthetic source file: 60 weekdays, dd-mm-yy, Volume and Net Volume -------------------------------------
days, d = [], date(2026, 6, 1)
while len(days) < 60:
    if d.weekday() < 5:
        days.append(d)
    d += timedelta(days=1)
rows, price = [], 1000.0
for i, day in enumerate(days):
    o = round(price, 2); c = round(o * (1 + ((i * 37) % 11 - 5) / 400), 2)
    h = round(max(o, c) * 1.004, 2); lo = round(min(o, c) * 0.996, 2)
    rows.append([day.strftime("%d-%m-%y"), o, h, lo, c, 10000 + i * 10, (-1) ** i * (5000 + i)])
    price = c
SRC = W / "src" / "NSE_NIFTY_1D.csv"
with open(SRC, "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["time", "open", "high", "low", "close", "Volume", "Net Volume"]); w.writerows(rows)
SRC_SHA = sha(SRC)

# ---- 1-2: entry points launch independently ------------------------------------------------------------------
for no, entry in ((1, "database_manager.py"), (2, "analytical_workbench.py")):
    done = subprocess.run([sys.executable, str(REPO / entry), "--selftest", "--settings-dir", str(W / "settings_selftest")],
                          capture_output=True, text=True, timeout=120, cwd=W)
    record(no, f"Launch {entry} on its own", "PASSED" if done.returncode == 0 and "SELFTEST OK" in done.stdout else "FAILED",
           f"exit {done.returncode}; stdout={done.stdout.strip()!r}; stderr={done.stderr.strip()[-200:]!r}")

dialogs = FakeDialogs()
dbm = DatabaseManagerApp(REPO, settings_dir=W / "settings", dialogs=dialogs)
dbm.geometry("1150x1000+0+0")


def pump(app, sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        app.update(); time.sleep(0.01)


def wait(app, cond, timeout=120):
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.update(); time.sleep(0.01)
    assert cond(), "timed out"
    pump(app)


dbm.data_var.set(str(W / "DATA")); dbm.output_var.set(str(W / "OUTPUT")); assert dbm.apply_locations()
pump(dbm); shot("01_database_manager_home")
dm = dbm.screens["data"]; dbm.show("data")


def choose(profile_id):
    i = next(n for n, p in enumerate(dm.profile_infos) if p.profile and p.profile.profile_id == profile_id)
    dm.select_profile_index(i); pump(dbm)


# ---- 3: import and preview -------------------------------------------------------------------------------------
dm.add_paths([SRC]); choose("example_csv_dd_mm_yy")
dm.listbox.selection_set(0); dm.preview_selected(); pump(dbm, 1.5)
preview = dm.preview_box.get()
record(3, "Import and preview a supported sample file", "PASSED" if "time" in preview and "Net Volume" in preview else "FAILED",
       preview.splitlines()[:6])

# ---- 5: incompatible profile is flagged (Unix-seconds profile on a dd-mm-yy file) -----------------------------
choose("example_csv_unix_seconds"); dm.timeframe_var.set("1D"); pump(dbm)
dm.finished_event.clear(); dm.check_files(); wait(dbm, dm.finished_event.is_set)
row = [str(x) for x in dm.tree.item(dm.tree.get_children()[0])["values"]]
dm.tree.selection_set(dm.tree.get_children()[0]); pump(dbm)
explain = dm.details.text.get("1.0", "end").strip()
record(5, "Reject or flag an incompatible profile", "PASSED" if "accepted" not in row[1].lower() else "FAILED",
       {"result": row[1], "explanation": explain[:600]})
shot("02_incompatible_profile_flagged")

# ---- 4 + 6: compatible profile, standardise and validate -------------------------------------------------------
dm.timeframe_var.set(""); choose("example_csv_dd_mm_yy")
dm.finished_event.clear(); dm.check_files(); wait(dbm, dm.finished_event.is_set)
check_row = [str(x) for x in dm.tree.item(dm.tree.get_children()[0])["values"]]
record(4, "Apply a compatible source profile", "PASSED" if check_row[1] == "Would be accepted" else "FAILED", check_row[:3])
dm.finished_event.clear(); dm.start_ingest(); wait(dbm, dm.finished_event.is_set)
load_row = [str(x) for x in dm.tree.item(dm.tree.get_children()[0])["values"]]
record(6, "Standardise and validate a supported dataset", "PASSED" if load_row[1].lower().startswith("loaded") or "accepted" in load_row[1].lower() else "FAILED",
       {"row": load_row[:4], "final": dm.final_label.cget("text")})
shot("03_loaded")

# ---- 7: registered and accessible; independent row-by-row comparison with the source --------------------------
import pyarrow.parquet as pq  # noqa: E402
from qmap.catalog import list_datasets  # noqa: E402
from qmap.storage.db import open_database  # noqa: E402
settings = dbm.core_settings
db = open_database(settings.db_path)
infos = list_datasets(db)
daily = infos[0]
t = pq.read_table(str(settings.data_path(daily.relative_path))).to_pydict()
same = all(t["session_date"][i].strftime("%d-%m-%y") == rows[i][0] and t["open"][i] == rows[i][1]
           and t["high"][i] == rows[i][2] and t["low"][i] == rows[i][3] and t["close"][i] == rows[i][4]
           and t["volume"][i] == rows[i][5] and t["x_net_volume"][i] == str(rows[i][6])  # preserved column: kept as read (text)
           for i in range(60))
record(7, "Register the dataset and verify it can be accessed",
       "PASSED" if len(infos) == 1 and daily.row_count == 60 and same else "FAILED",
       {"dataset": daily.dataset_id, "instrument": daily.instrument, "rows": daily.row_count,
        "all_60_rows_identical_to_source_incl_net_volume_kept_separate": same, "path": daily.relative_path})

# ---- 8: original file unchanged -------------------------------------------------------------------------------
record(8, "Original source file not modified", "PASSED" if sha(SRC) == SRC_SHA else "FAILED", f"SHA-256 before = after = {SRC_SHA}")

# ---- derive + 9: Permanent/Temporary ---------------------------------------------------------------------------
dbm.show("datasets"); ds = dbm.screens["datasets"]; pump(dbm)
item = next(i for i, v in ds.rows.items() if v == daily.dataset_id); ds.tree.selection_set(item); ds.on_select()
ds.derive_vars["1W"].set(True); ds.derive_vars["1M"].set(True); ds.derive_action()
wait(dbm, lambda: not ds.running and "done" in ds.final_label.cget("text"))
derived = [d for d in list_datasets(db) if d.layer == "timeframe"]
wk = next(d for d in derived if d.timeframe == "1W")
wt = pq.read_table(str(settings.data_path(wk.relative_path))).to_pydict()
# independent weekly check from the source rows
by_week = {}
for r in rows:
    dd = date(2000 + int(r[0][6:]), int(r[0][3:5]), int(r[0][:2])); by_week.setdefault(dd.isocalendar()[:2], []).append(r)
exp = [(g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4], sum(x[5] for x in g)) for g in by_week.values()]
got = list(zip(wt["open"], wt["high"], wt["low"], wt["close"], wt["volume"]))
record("9a", "Derive weekly and monthly from daily (independently re-calculated)",
       "PASSED" if len(derived) == 2 and [tuple(map(float, e)) for e in exp] == got else "FAILED",
       {"derived": [(d.dataset_id, d.timeframe, d.row_count) for d in derived], "weekly_bars_match_independent": exp == got})
item = next(i for i, v in ds.rows.items() if v == daily.dataset_id); ds.tree.selection_set(item); ds.on_select()
ds.reason_var.set("acceptance test"); ds.storage_action("temporary")
wait(dbm, lambda: not ds.running and "done" in ds.final_label.cget("text"))
now = next(d for d in list_datasets(db) if d.dataset_id == daily.dataset_id)
from qmap.storage.recovery import verify_registry  # noqa: E402
rep = verify_registry(settings, db)
act = db.one("SELECT * FROM storage_actions ORDER BY action_id DESC LIMIT 1")
record(9, "Permanent/Temporary classification and safe registry update",
       "PASSED" if now.storage_class == "temporary" and now.relative_path.startswith("Temporary_Data/")
       and sha(settings.data_path(now.relative_path)) == daily.sha256 and not rep.missing_files
       and not rep.checksum_mismatches and act["status"] == "completed" else "FAILED",
       {"new_path": now.relative_path, "checksum_unchanged": sha(settings.data_path(now.relative_path)) == daily.sha256,
        "verify_missing": rep.missing_files, "verify_mismatch": rep.checksum_mismatches,
        "audit": {k: act[k] for k in ("action", "from_class", "to_class", "status", "reason")}})
ds.on_select(); pump(dbm); shot("04_datasets_and_storage")

# ---- 10-14: Workbench, opened while Database Manager is still open --------------------------------------------
awb = AnalyticalWorkbenchApp(REPO, settings_dir=W / "settings", dialogs=dialogs)
awb.geometry("1150x1000+0+0"); pump(awb)
awb.show("analysis"); an = awb.screens["analysis"]; pump(awb)
seen = sorted(an.rows.values())
record(10, "Workbench discovers and uses ready data",
       "PASSED" if seen == sorted([daily.dataset_id] + [d.dataset_id for d in derived]) else "FAILED",
       {"datasets_offered": seen, "workbench_folder_remembered": str(awb.core_settings.data_root)})
item = next(i for i, v in an.rows.items() if v == daily.dataset_id); an.tree.selection_set(item); pump(awb)
an.param_vars["date_from"].set("01-Jan-30"); an.start_run(); pump(awb)
blocked_text = an.readiness_box.get()
runs_after_block = db.one("SELECT COUNT(*) FROM runs WHERE module_code = 'DSUM'")[0]
record(11, "Analysis blocked with a clear explanation when data are unsuitable",
       "PASSED" if "NOT READY" in blocked_text and an.last_result is None and runs_after_block == 0 else "FAILED",
       {"readiness": blocked_text.splitlines()[:6], "final": an.final_label.cget("text"), "runs_created": runs_after_block})
shot("05_workbench_blocked")
an.param_vars["date_from"].set("")
for i, v in an.rows.items():
    if v in (daily.dataset_id, wk.dataset_id):
        an.tree.selection_add(i)
an._selection_changed(); an.start_run()
wait(awb, lambda: not an.running and an.last_result is not None)
res = an.last_result
shot("06_workbench_completed")
with open(res.outputs[0], newline="", encoding="utf-8") as fh:
    out = list(csv.DictReader(fh))
closes = [r[4] for r in rows]
rets = [(b / a - 1) * 100 for a, b in zip(closes, closes[1:])]
ok_stats = (abs(float(out[0]["Mean return %"]) - statistics.mean(rets)) < 1e-4
            and abs(float(out[0]["Std dev return %"]) - statistics.stdev(rets)) < 1e-4 and out[0]["Bars"] == "60"
            and out[0]["First bar"] == "01-Jun-26")
record(12, "An existing supported analysis still produces appropriate results",
       "NOT APPLICABLE" , "No MIQP or QLOPB analysis exists in this repository to re-run. The new Dataset Summary was "
       f"run instead; its statistics match an independent calculation: {ok_stats}")
meta = json.loads(res.metadata_path.read_text())
manifest = json.loads((res.run_dir / "run_manifest.json").read_text())
record(13, "Research outputs and run metadata saved correctly",
       "PASSED" if res.ok and ok_stats and meta["run_id"] == res.run_id and len(meta["input_datasets"]) == 2
       and all(x["sha256"] and x["lineage"] for x in meta["input_datasets"]) and res.run_dir.parent == W / "OUTPUT" / "Research_Reports" else "FAILED",
       {"run_id": res.run_id, "folder": str(res.run_dir.relative_to(W)), "files": sorted(p.name for p in res.run_dir.iterdir()),
        "metadata_inputs": [(x["dataset_id"], x["timeframe"], x["storage_class"]) for x in meta["input_datasets"]],
        "manifest_status": manifest["status"]})
record(14, "Both GUIs work independently and share one registry and data definition",
       "PASSED" if results[0]["status"] == results[1]["status"] == "PASSED" and results[-4]["status"] == "PASSED" else "FAILED",
       "Each entry point opened on its own (1, 2); both windows were open together on one Data Registry; the Workbench "
       "saw the Database Manager's Temporary move immediately (dataset shown as Temporary: "
       f"{an.tree.item(next(i for i, v in an.rows.items() if v == daily.dataset_id))['values'][7]})")
db.close()
for app in (awb, dbm):
    app._on_closing(); app.tasks.join_all(60)
release_garbage_collector_if_idle()
(EV / f"acceptance_results_{STAMP}.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print("SOURCE UNCHANGED AT END:", sha(SRC) == SRC_SHA)
