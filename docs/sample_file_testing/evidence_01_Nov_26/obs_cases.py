"""Observation cases A-E: the exact messages the Data Management window shows (services.check_file + Finding.text()).
Writes only under <test_root>/obs_work (renamed COPIES of samples) and the evidence folder."""
import json, shutil, sys
from pathlib import Path
REPO, SAMPLES, T, LABEL = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
sys.path.insert(0, str(REPO / "Application"))
from qmap.data_engine.profiles import load_profile, parse_profile  # noqa: E402
from qmap_gui import services  # noqa: E402

settings = services.build_core_settings(str(T / "DATA_obs"), str(T / "OUTPUT_obs"), REPO, T / "profiles") \
    if (T / "DATA_obs").exists() else None
for d in ("DATA_obs", "OUTPUT_obs", "obs_work"):
    (T / d).mkdir(exist_ok=True)
settings = services.build_core_settings(str(T / "DATA_obs"), str(T / "OUTPUT_obs"), REPO, T / "profiles")
EX = REPO / "Configuration" / "source_profiles"
P = lambda name: load_profile((T / "profiles" / f"{name}.toml") if (T / "profiles" / f"{name}.toml").exists() else EX / f"{name}.toml")  # noqa: E731


def variant(name, **edits):
    text = (T / "profiles" / f"{name}.toml").read_text()
    for old, new in edits.items():
        assert old in text, old
        text = text.replace(old, new)
    return parse_profile(text)


def copy_as(src, new):
    dst = T / "obs_work" / new
    shutil.copyfile(SAMPLES / src, dst)
    return dst


CASES = [
    ("A1", "Filename pattern, name 'NSE_NIFTY, 1(1).csv' (renamed copy of file 9)", copy_as("xls headers iso.csv", "NSE_NIFTY, 1(1).csv"),
     P("example_csv_iso_offset"), {"timeframe": "5m"}),
    ("A2", "Filename pattern, original name of file 9", SAMPLES / "xls headers iso.csv", P("example_csv_iso_offset"), {"timeframe": "5m"}),
    ("A3", "Filename pattern, a name that matches ('NSE_NIFTY_5m.csv', copy of file 9)", copy_as("xls headers iso.csv", "NSE_NIFTY_5m.csv"),
     P("example_csv_iso_offset"), {"timeframe": "5m"}),
    ("A4", "Profile asks for identity, none typed", SAMPLES / "xls headers iso.csv", P("csv_headers_iso_offset"), {"timeframe": "5m"}),
    ("A5", "Profile asks for identity, invalid values typed ('NSE 1', 'NIFTY 50')", SAMPLES / "xls headers iso.csv",
     P("csv_headers_iso_offset"), {"exchange": "NSE 1", "symbol": "NIFTY 50", "timeframe": "5m"}),
    ("A6", "Filename pattern, values typed anyway (window disables the boxes; checking the engine)", copy_as("xls headers iso.csv", "NSE_NIFTY, 1(1).csv"),
     P("example_csv_iso_offset"), {"exchange": "NSE", "symbol": "NIFTY", "timeframe": "5m"}),
    ("B1", "Headerless file 4 with a HEADERED profile", SAMPLES / "csv noheaders iso.csv", P("csv_headers_iso_offset"),
     {"exchange": "TEST", "symbol": "B1", "timeframe": "5m"}),
    ("B2", "Headerless file 4 with the example 'duplicated volume' profile (col 7 is Net Volume, not a copy)", SAMPLES / "csv noheaders iso.csv",
     variant("example_text_headerless_seven_columns", **{'kind = "iso"': 'kind = "iso"\nexchange_timezone = "Asia/Kolkata"', 'timeframe = "1D"': 'timeframe = "5m"'}),
     {"exchange": "TEST", "symbol": "B2"}),
    ("B3", "Headered file 9 with a HEADERLESS profile", SAMPLES / "xls headers iso.csv", P("csv_noheaders_iso_offset"),
     {"exchange": "TEST", "symbol": "B3", "timeframe": "5m"}),
    ("C1", "Parquet without exchange/symbol (the observed E_INSTRUMENT_REQUIRED)", SAMPLES / "ONESOURCE.parquet", P("example_parquet_naive_timestamp"), {}),
    ("C2", "Parquet with exchange/symbol", SAMPLES / "ONESOURCE.parquet", P("example_parquet_naive_timestamp"), {"exchange": "TEST", "symbol": "C2"}),
    ("D1", "XLSX file 1 with a CSV profile", SAMPLES / "csv headers iso.xlsx", P("csv_headers_iso_offset"), {"exchange": "TEST", "symbol": "D1", "timeframe": "5m"}),
    ("D2", "File 9 (named 'xls', really CSV) with an XLSX profile", SAMPLES / "xls headers iso.csv", P("xlsx_headers_iso_offset"),
     {"exchange": "TEST", "symbol": "D2", "timeframe": "5m"}),
    ("D3", "XLSX file 1 renamed to .csv (copy) with an XLSX profile", copy_as("csv headers iso.xlsx", "renamed_xlsx.csv"), P("xlsx_headers_iso_offset"),
     {"exchange": "TEST", "symbol": "D3", "timeframe": "5m"}),
    ("E1", "5-minute file, no timeframe supplied", SAMPLES / "xls headers iso.csv", P("csv_headers_iso_offset"), {"exchange": "TEST", "symbol": "E1"}),
    ("E2", "5-minute file declared 1m", SAMPLES / "xls headers iso.csv", P("csv_headers_iso_offset"), {"exchange": "TEST", "symbol": "E2", "timeframe": "1m"}),
    ("E3", "5-minute file declared 1D", SAMPLES / "xls headers iso.csv", P("csv_headers_iso_offset"), {"exchange": "TEST", "symbol": "E3", "timeframe": "1D"}),
    ("E4", "Daily DD-MM-YY file read as MM-DD-YY", SAMPLES / "csv headers std.csv", variant("csv_headers_dd_mm_yy", **{'"%d-%m-%y"': '"%m-%d-%y"'}),
     {"exchange": "TEST", "symbol": "E4", "timeframe": "1D"}),
    ("E5", "Unix-seconds file declared as milliseconds", SAMPLES / "csv headers unix.csv", variant("csv_headers_unix_seconds", **{'"unix_s"': '"unix_ms"'}),
     {"exchange": "TEST", "symbol": "E5", "timeframe": "1m"}),
    ("E6", "Naive Parquet timestamps with NO time zone declared", SAMPLES / "ONESOURCE.parquet",
     variant("example_parquet_naive_timestamp", **{'timezone = "Asia/Kolkata"            #': '#'}), {"exchange": "TEST", "symbol": "E6"}),
    ("E7", "ISO-offset file with NO exchange_timezone (trading date source)", SAMPLES / "xls headers iso.csv",
     variant("csv_headers_iso_offset", **{'exchange_timezone = "Asia/Kolkata"': ''}), {"exchange": "TEST", "symbol": "E7", "timeframe": "5m"}),
    ("E8", "Daily ISO-date file declared 5m", SAMPLES / "text headers ymd.txt",
     variant("example_text_headered_iso_date", **{'timeframe = "1D"': 'timeframe = "ingest"'}), {"exchange": "TEST", "symbol": "E8", "timeframe": "5m"}),
]

out = []
for cid, what, path, prof, ov in CASES:
    needs = services.profile_needs(prof)
    rep = services.check_file(path, prof, settings, ov)
    shown = "\n".join(f.text() for f in rep.findings if f.severity in ("error", "warning"))
    out.append({"case": cid, "what": what, "file": path.name, "profile": prof.profile_id, "request": ov,
                "window_boxes_enabled": {"exchange": needs.exchange, "symbol": needs.symbol, "timeframe": needs.timeframe},
                "outcome": rep.outcome, "rows_read": rep.rows_read, "shown_to_user": shown})
    print(f"--- {cid} {what}\n    boxes enabled: exch={needs.exchange} sym={needs.symbol} tf={needs.timeframe} | outcome: {rep.outcome}")
    print("    " + shown.replace("\n", "\n    ")[:1500])
ev = T / "evidence" / LABEL
ev.mkdir(parents=True, exist_ok=True)
(ev / "observation_cases.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
