"""SYNTHETIC replacements (09-Nov-26) for the two QLOPB sample files that appeared to hold real market data
(`NSE_SBIN, 60.csv` and `Nifty500 Healthcare.txt`; their provenance and permitted public use were not documented).

The prices are a seeded random walk: they describe no real instrument. Each file keeps the LAYOUT the tests rely on:

  NSE_SYNTHHOURLY, 60.csv  header `time,open,high,low,close,ATR in %,ATR,Daily ATR Closing to Closing%`; hourly bars
                           09:15..15:15 with a +05:30 offset, from 11-Feb-25 13:15 to 09-Oct-26 14:15; one weekend
                           session (Sunday 01-Feb-26 09:15); no volume; "ATR in %" empty, the two ATR columns filled.
  Synth500 Sector.txt      no header; `date,open,high,low,close,volume`; 228 daily bars from 10-Nov-25 to 09-Oct-26
                           (weekdays, 12 holiday dates left out); one zero-volume day (02-Dec-25).

`write_all(folder)` rebuilds both files byte for byte; test_qlopb_synthetic_fixtures checks the committed copies.
"""

from __future__ import annotations

import csv
import io
import random
from datetime import date, datetime, timedelta
from pathlib import Path

HOURLY_NAME = "NSE_SYNTHHOURLY, 60.csv"
DAILY_NAME = "Synth500 Sector.txt"
DAILY_HOLIDAYS = {date(2025, 11, 26), date(2025, 12, 25), date(2026, 1, 26), date(2026, 2, 17), date(2026, 3, 3),
                  date(2026, 3, 31), date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 8, 14), date(2026, 9, 14),
                  date(2026, 10, 2)}
LOW_VOLUME_DAY = date(2025, 12, 2)


def _walk(rng: random.Random, n: int, start: float, vol: float, drift: float = 0.0):
    price = start
    for _ in range(n):
        o = price
        c = round(o * (1 + rng.gauss(drift, vol)), 2)
        h = round(max(o, c) * (1 + abs(rng.gauss(0, vol / 3))), 2)
        lo = round(min(o, c) * (1 - abs(rng.gauss(0, vol / 3))), 2)
        price = c
        yield round(o, 2), h, lo, c


def hourly_text() -> str:
    rng = random.Random(20251)
    stamps = []
    day = date(2025, 2, 11)
    while day <= date(2026, 10, 9):
        if day.weekday() < 5 or day == date(2026, 2, 1):
            for hour in range(9, 16):
                t = datetime(day.year, day.month, day.day, hour, 15)
                if datetime(2025, 2, 11, 13, 15) <= t <= datetime(2026, 10, 9, 14, 15):
                    stamps.append(t)
        day += timedelta(days=1)
    out = io.StringIO(newline="")
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["time", "open", "high", "low", "close", "ATR in %", "ATR", "Daily ATR Closing to Closing%"])
    for t, (o, h, lo, c) in zip(stamps, _walk(rng, len(stamps), 700.0, 0.004, 0.00005)):
        w.writerow([t.strftime("%Y-%m-%dT%H:%M:%S+05:30"), o, h, lo, c, "", round(rng.uniform(4, 9), 6),
                    round(rng.uniform(0.8, 1.6), 6)])
    return out.getvalue()


def daily_text() -> str:
    rng = random.Random(20252)
    days, day = [], date(2025, 11, 10)
    while day <= date(2026, 10, 9):
        if day.weekday() < 5 and day not in DAILY_HOLIDAYS:
            days.append(day)
        day += timedelta(days=1)
    assert len(days) == 228, len(days)
    out = io.StringIO(newline="")
    w = csv.writer(out, lineterminator="\n")
    for d, (o, h, lo, c) in zip(days, _walk(rng, len(days), 19000.0, 0.009, 0.0002)):
        vol = 0 if d == LOW_VOLUME_DAY else rng.randint(25_000_000, 60_000_000)
        w.writerow([d.isoformat(), o, h, lo, c, vol])
    return out.getvalue()


def write_all(folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, text in ((HOURLY_NAME, hourly_text()), (DAILY_NAME, daily_text())):
        p = folder / name
        p.write_bytes(text.encode("utf-8"))
        paths.append(p)
    return paths


if __name__ == "__main__":  # rebuild the committed copies (run from the Tests folder)
    for p in write_all(Path(__file__).resolve().parent / "qlopb_data"):
        print(p)
