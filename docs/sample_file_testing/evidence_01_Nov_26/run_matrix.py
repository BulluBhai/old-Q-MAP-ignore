"""Staged sample-file test of Q-MAP through the GUI's own service layer and load job.

Usage: python run_matrix.py <repo> <samples_dir> <test_root> <label>
Writes ONLY under <test_root>. The sample files are opened read-only and re-hashed at the end.
"""
import csv, hashlib, json, sys, traceback
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

REPO, SAMPLES, T, LABEL = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
sys.path.insert(0, str(REPO / "Application"))
import openpyxl, pyarrow.parquet as pq  # noqa: E402
from qmap.data_engine.format_detect import detect_format  # noqa: E402
from qmap.data_engine.profiles import load_profile  # noqa: E402
from qmap.storage.db import open_database  # noqa: E402
from qmap_gui import services  # noqa: E402
from qmap_gui.jobs import IngestJob  # noqa: E402

EX = "TEST"  # deliberately artificial exchange: the real identity of each sample must be confirmed by the owner
CASES = [  # (no, file, profile, symbol, timeframe or None if the profile fixes it, my reading of the layout)
    (1, "csv headers iso.xlsx", "xlsx_headers_iso_offset", "F01", "5m"),
    (2, "csv headers std.csv", "csv_headers_dd_mm_yy", "F02", "1D"),
    (3, "csv headers unix.csv", "csv_headers_unix_seconds", "F03", "1m"),
    (4, "csv noheaders iso.csv", "csv_noheaders_iso_offset", "F04", "5m"),
    (5, "csv noheaders unix.csv", "csv_noheaders_unix_seconds", "F05", "1D"),
    (6, "ONESOURCE.parquet", "example_parquet_naive_timestamp", "F06", None),
    (7, "text headers ymd.txt", "example_text_headered_iso_date", "F07", None),
    (8, "text no headers ymd.txt", "example_text_headerless_seven_columns", "F08", None),
    (9, "xls headers iso.csv", "csv_headers_iso_offset", "F09", "5m"),
    (10, "xls headers std.xlsx", "xlsx_headers_native_date", "F10", "1D"),
    (11, "xls noheaders iso.xlsx", "xlsx_noheaders_iso_offset", "F11", "5m"),
]
IST = timezone(timedelta(hours=5, minutes=30))
ev = T / "evidence" / LABEL
ev.mkdir(parents=True, exist_ok=True)
settings = services.build_core_settings(str(T / "DATA"), str(T / "OUTPUT"), REPO, T / "profiles")
profiles = {p.stem: load_profile(p) for p in (T / "profiles").glob("*.toml")}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def source_rows(path):
    """Independent re-reading of the source (NOT Q-MAP code): list of (time_utc or date, o, h, l, c, v, extra)."""
    head = path.read_bytes()[:4]
    if head == b"PAR1":
        t = pq.read_table(path).to_pylist()
        return [(r["Date"].replace(tzinfo=IST).astimezone(timezone.utc), r["Open"], r["High"], r["Low"], r["Close"],
                 float(r["Volume"]), r["index"]) for r in t]
    if head[:2] == b"PK":
        rows = [list(r) for r in openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0].iter_rows(values_only=True)]
    else:
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    if isinstance(rows[0][1], str) and not rows[0][1].replace(".", "").isdigit():
        rows = rows[1:]
    out = []
    for r in rows:
        v0 = r[0]
        if isinstance(v0, datetime):
            t = v0.date()
        elif str(v0).isdigit():
            t = datetime.fromtimestamp(int(v0), timezone.utc)
        elif "T" in str(v0):
            t = datetime.fromisoformat(str(v0)).astimezone(timezone.utc)
        elif len(str(v0)) == 8:
            t = datetime.strptime(str(v0), "%d-%m-%y").date()
        else:
            t = date.fromisoformat(str(v0))
        vol = float(r[5]) if len(r) > 5 else None
        extra = r[6] if len(r) > 6 else None
        out.append((t, float(r[1]), float(r[2]), float(r[3]), float(r[4]), vol, extra))
    return out


def verify(case, outcome, db):
    """Compare every stored row with the independent source reading."""
    no, name = case[0], case[1]
    src = source_rows(SAMPLES / name)
    ds = db.query("SELECT d.*, i.exchange, i.symbol FROM datasets d JOIN instruments i USING(instrument_id) "
                  "WHERE layer='cleaned' AND relative_path LIKE ?", (f"%{outcome.datasets[0]}%",)) if False else None
    rows = db.query("SELECT d.*, i.exchange, i.symbol FROM datasets d JOIN instruments i USING(instrument_id) "
                    "WHERE d.dataset_id IN (%s)" % ",".join(str(int(x)) for x in outcome.datasets))
    assert len(rows) == 1, f"expected one cleaned dataset, got {len(rows)}"
    d = rows[0]
    table = pq.read_table(settings.data_root / d["relative_path"]).to_pylist()
    raw = db.one("SELECT * FROM datasets WHERE dataset_id=?", (d["parent_dataset_id"],))
    checks = {}
    checks["identity"] = f"{d['exchange']}:{d['symbol']} timeframe {d['timeframe']}"
    checks["raw_copy_identical_to_source"] = raw["sha256"] == sha(SAMPLES / name) == sha(settings.data_root / raw["relative_path"])
    checks["row_count"] = f"stored {len(table)} vs source {len(src)}"
    checks["row_count_equal"] = len(table) == len(src) == d["row_count"]
    order = sorted(range(len(table)), key=lambda i: table[i]["src_row"])
    mism = []
    for k, i in enumerate(order):
        st, s = table[i], src[k]
        t = s[0]
        if isinstance(t, datetime):
            ok_t = st["timestamp_utc"] == t and st["session_date"] == t.astimezone(IST).date()
        else:
            ok_t = st["session_date"] == t
        ok_px = (st["open"], st["high"], st["low"], st["close"]) == s[1:5]
        ok_v = (st["volume"] == s[5]) if s[5] is not None else st["volume"] is None
        if not (ok_t and ok_px and ok_v):
            mism.append((k, st, s))
    checks["rows_identical_time_ohlc_volume"] = not mism
    checks["first_mismatches"] = [str(m) for m in mism[:3]]
    xcols = [c for c in table[0] if c.startswith("x_")]
    checks["preserved_extra_columns"] = xcols
    same = lambda a, b: (a is None and b is None) or (a is not None and b is not None and float(a) == float(b))  # noqa: E731
    vol_copy = [c for c in xcols if c in ("x_volume", "x_col5")]  # the original Volume column, kept verbatim
    other = [c for c in xcols if c not in vol_copy]
    if vol_copy:
        checks["preserved_volume_copy_identical"] = all(same(table[i][vol_copy[0]], s[5]) for i, s in zip(order, src))
    if other and src[0][6] is not None or (other and any(s[6] is not None for s in src)):
        checks["preserved_extra_column"] = other[0]
        checks["extra_column_values_identical"] = all(same(table[i][other[0]], s[6]) for i, s in zip(order, src))
    checks["src_row_is_1_to_n"] = sorted(r["src_row"] for r in table) == list(range(min(r["src_row"] for r in table),
                                                                                   min(r["src_row"] for r in table) + len(table)))
    checks["first_last_session_date"] = f"{min(r['session_date'] for r in table)} .. {max(r['session_date'] for r in table)}"
    checks["quality_flags_nonzero_rows"] = sum(1 for r in table if r["quality_flags"])
    checks["stored_dataset_path"] = d["relative_path"]
    return checks


before = {p.name: sha(p) for p in SAMPLES.iterdir()}
results = []
for case in CASES:
    no, name, pid, sym, tf = case
    path, prof = SAMPLES / name, profiles[pid]
    ov = {"exchange": EX, "symbol": sym, "timeframe": tf or ""}
    r = {"no": no, "file": name, "profile": f"{pid}@{prof.profile_version}", "request": ov}
    try:
        det = detect_format(path)
        r["1_format"] = {"kind": det.kind, "extension": det.extension, "extension_matches": det.extension_matches}
        prev = services.make_preview(path, prof, settings, ov)
        (ev / f"F{no:02d}_preview.txt").write_text(prev, encoding="utf-8")
        r["2_preview"] = "ok" if "Traceback" not in prev else "error"
        rep = services.check_file(path, prof, settings, ov)
        r["3_check"] = {"outcome": rep.outcome, "rows_read": rep.rows_read,
                        "errors": [f"{f.title}: {f.detail}" for f in rep.errors],
                        "warnings": [f"{f.title}: {f.detail}" for f in rep.warnings],
                        "info": [f"{f.title}: {f.detail}" for f in rep.findings if f.severity == "info"]}
        (ev / f"F{no:02d}_check.txt").write_text("\n\n".join(f.text() for f in rep.findings) or "(no findings)", encoding="utf-8")
        if rep.outcome == "would_be_accepted":
            events = []
            summary = IngestJob(settings, [path], prof, exchange=EX, symbol=sym, timeframe=tf or "",
                                source_label="owner sample test", emit=events.append).run()
            o = summary.outcomes[0]
            r["4_ingest"] = {"outcome": o.outcome, "label": o.label, "message": o.message, "run_id": summary.run_id,
                             "datasets": o.datasets, "issues_report": str(o.issues_report) if o.issues_report else None}
            if o.outcome == "accepted":
                db = open_database(settings.db_path)
                try:
                    r["5_verification"] = verify(case, o, db)
                finally:
                    db.close()
        else:
            r["4_ingest"] = "not attempted (check did not pass)"
    except Exception as exc:
        r["exception"] = f"{type(exc).__name__}: {exc}"
        r["traceback"] = traceback.format_exc()
    results.append(r)

after = {p.name: sha(p) for p in SAMPLES.iterdir()}
summary = {"label": LABEL, "repo_head": (REPO / ".git").exists() and "see git", "samples_unchanged": before == after,
           "results": results}
(ev / "matrix_results.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
for r in results:
    chk = r.get("3_check", {})
    ing = r.get("4_ingest")
    ing_s = ing if isinstance(ing, str) else ing.get("outcome") if ing else "-"
    v = r.get("5_verification", {})
    vs = "" if not v else ("VERIFIED" if v.get("row_count_equal") and v.get("rows_identical_time_ohlc_volume")
                           and v.get("raw_copy_identical_to_source") and v.get("extra_column_values_identical", True) and v.get("preserved_volume_copy_identical", True) else "VERIFY-FAIL")
    print(f"F{r['no']:02d} {r['file']:26} {r['profile']:42} fmt={r.get('1_format',{}).get('kind')} "
          f"check={chk.get('outcome')} err={len(chk.get('errors',[]))} warn={len(chk.get('warnings',[]))} "
          f"ingest={ing_s} {vs} {r.get('exception','')}")
print("samples unchanged:", before == after)
