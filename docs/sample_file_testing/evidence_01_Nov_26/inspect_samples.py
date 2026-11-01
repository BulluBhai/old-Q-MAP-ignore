"""Read-only inspection of the owner's sample files. Never writes into the sample folder."""
import csv, sys, re, statistics
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
import openpyxl, pyarrow.parquet as pq

D = Path(sys.argv[1])
FILES = ["csv headers iso.xlsx","csv headers std.csv","csv headers unix.csv","csv noheaders iso.csv","csv noheaders unix.csv",
         "ONESOURCE.parquet","text headers ymd.txt","text no headers ymd.txt","xls headers iso.csv","xls headers std.xlsx","xls noheaders iso.xlsx"]

def rows_of(p):
    head = p.read_bytes()[:4]
    if head == b"PAR1":
        t = pq.read_table(p); cols = t.column_names
        return "parquet", [cols] + [list(r.values()) for r in t.to_pylist()], {f.name: str(f.type) for f in t.schema}
    if head[:2] == b"PK":
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        ws = wb.worksheets; out = [list(r) for r in ws[0].iter_rows(values_only=True)]
        return f"xlsx (sheets={[w.title for w in ws]})", out, None
    with p.open(newline="", encoding="utf-8-sig") as f:
        return "delimited text", [r for r in csv.reader(f)], None

def as_time(v):
    if isinstance(v, datetime): return v, "native datetime (" + ("tz-aware" if v.tzinfo else "naive") + ")"
    s = str(v).strip()
    if re.fullmatch(r"\d{9,11}", s): return datetime.fromtimestamp(int(s), timezone.utc), "unix seconds"
    if re.fullmatch(r"\d{12,14}", s): return datetime.fromtimestamp(int(s)/1000, timezone.utc), "unix milliseconds"
    if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d)?[+-]\d\d:\d\d", s): return datetime.fromisoformat(s), "ISO timestamp with offset"
    if re.fullmatch(r"\d{4}-\d\d-\d\d", s): return datetime.fromisoformat(s), "ISO date"
    if re.fullmatch(r"\d\d-\d\d-\d\d", s): return datetime.strptime(s, "%d-%m-%y"), "DD-MM-YY (assumed day-first for inspection)"
    return None, f"unrecognised: {s!r}"

for name in FILES:
    p = D / name; kind, rows, schema = rows_of(p)
    print("="*100); print(f"{name} | signature format: {kind} | size {p.stat().st_size}")
    if schema: print("  parquet schema:", schema)
    widths = Counter(len(r) for r in rows); print("  row widths:", dict(widths), "| total rows incl any header:", len(rows))
    first = rows[0]; hdr = all(isinstance(v, str) and re.search(r"[A-Za-z]", v) for v in first)
    print("  first row:", first[:8], "=> header" if hdr else "=> data")
    data = rows[1:] if hdr else rows
    tvals = [as_time(r[0]) for r in data]
    kinds = Counter(k for _, k in tvals); print("  time column kinds:", dict(kinds))
    ts = [t for t, _ in tvals if t is not None]
    if ts:
        aware = [t for t in ts if t.tzinfo]; offs = Counter(str(t.utcoffset()) for t in aware)
        print("  first/last:", ts[0], "|", ts[-1], "| offsets:", dict(offs) if offs else "none (naive/date-only)")
        if kinds.get("unix seconds"):
            ist = [t.astimezone(timezone(timedelta(hours=5, minutes=30))) for t in ts]
            print("  unix first/last as UTC:", ts[0], ts[-1], "| as IST:", ist[0], ist[-1])
            print("  IST time-of-day set (first 8):", sorted({x.strftime('%H:%M') for x in ist})[:8], "count distinct:", len({x.strftime('%H:%M') for x in ist}))
        key = [t.astimezone(timezone.utc).replace(tzinfo=None) if t.tzinfo else t for t in ts]
        dup = [k for k, c in Counter(key).items() if c > 1]; back = sum(1 for a, b in zip(key, key[1:]) if b < a)
        steps = Counter(int((b - a).total_seconds() // 60) for a, b in zip(key, key[1:]))
        print(f"  duplicates: {len(dup)} {dup[:3]} | backward steps: {back} | step minutes (top 6): {steps.most_common(6)}")
        days = Counter(k.date() for k in key); print("  distinct dates:", len(days), "| bars per date (top 4):", Counter(days.values()).most_common(4))
    ncol = len(first)
    for c in range(1, ncol):
        vals = [r[c] if c < len(r) else None for r in data]
        miss = sum(1 for v in vals if v in (None, "") or (isinstance(v, float) and v != v))
        nums = []
        for v in vals:
            try: nums.append(float(v))
            except (TypeError, ValueError): pass
        label = first[c] if hdr else f"col{c+1}"
        extra = f"min {min(nums):g} max {max(nums):g}" if nums else ""
        print(f"  [{c+1}] {label!s:12} missing={miss:5} numeric={len(nums):5} {extra}")
    if ncol >= 5:
        bad = 0; neg = 0
        for r in data:
            try:
                o, h, l, c_ = (float(r[i]) for i in (1, 2, 3, 4))
                if not (l <= min(o, c_) and h >= max(o, c_) and l <= h): bad += 1
            except (TypeError, ValueError): pass
        print("  OHLC inconsistent rows:", bad)
    if ncol >= 7:
        same = sum(1 for r in data if r[5] is not None and r[6] is not None and str(r[5]) == str(r[6]))
        absequal = sum(1 for r in data if r[5] not in (None, "") and r[6] not in (None, "") and abs(float(r[5])) == abs(float(r[6])))
        print(f"  col6 vs col7: identical in {same}/{len(data)} rows; equal in magnitude in {absequal}/{len(data)}")
