"""Synthetic test-data builders. No real market data is ever used in tests."""

from __future__ import annotations

import csv
import io
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HEADER = ["time", "open", "high", "low", "close", "Volume"]


def weekdays(n: int, start: date = date(2026, 1, 5)) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def ohlcv(n: int, seed: int = 1, base: float = 100.0, volume: bool = True) -> list[list]:
    """n valid OHLC(V) rows: Low <= Open,Close <= High, prices > 0, volume >= 0."""
    rnd = random.Random(seed)
    rows, price = [], base
    for _ in range(n):
        o = round(price, 2)
        c = round(o * (1 + rnd.uniform(-0.01, 0.01)), 2)
        h = round(max(o, c) * (1 + rnd.uniform(0, 0.005)), 2)
        low = round(min(o, c) * (1 - rnd.uniform(0, 0.005)), 2)
        row = [o, h, low, c]
        if volume:
            row.append(rnd.randint(1000, 90000))
        rows.append(row)
        price = c
    return rows


def intraday_utc(n: int, start: datetime = datetime(2026, 1, 5, 3, 45, tzinfo=timezone.utc),
                 step_minutes: int = 1) -> list[datetime]:
    """n consecutive bar times; sessions of 375 bars (09:15-15:30 in UTC+05:30), weekdays only."""
    out, t, in_session = [], start, 0
    while len(out) < n:
        out.append(t)
        in_session += 1
        t += timedelta(minutes=step_minutes)
        if in_session * step_minutes >= 375:
            in_session = 0
            t = (t.replace(hour=3, minute=45) + timedelta(days=1))
            while t.weekday() >= 5:
                t += timedelta(days=1)
    return out


def write_delimited(path: Path, header: list[str] | None, rows: list[list], *, delimiter: str = ",",
                    newline: str = "\r\n", final_newline: bool = True, bom: bool = False,
                    encoding: str = "utf-8") -> Path:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter, lineterminator=newline)
    if header is not None:
        writer.writerow(header)
    writer.writerows(rows)
    text = buf.getvalue()
    if not final_newline and text.endswith(newline):
        text = text[: -len(newline)]
    data = text.encode(encoding)
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    return path


def write_xlsx(path: Path, header: list[str] | None, rows: list[list], *, sheet: str = "Sheet1",
               extra_sheets: dict[str, list[list]] | None = None) -> Path:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    if header is not None:
        ws.append(header)
    for r in rows:
        ws.append(r)
    for name, extra in (extra_sheets or {}).items():
        w2 = wb.create_sheet(name)
        for r in extra:
            w2.append(r)
    wb.save(path)
    return path


def write_parquet(path: Path, columns: dict) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(pa.table(columns), path)
    return path


def standard_columns(times: list, rows: list[list], time_name: str = "time") -> dict:
    """Column dict {time, open, high, low, close, Volume} for write_parquet."""
    return {
        time_name: times,
        "open": [r[0] for r in rows], "high": [r[1] for r in rows],
        "low": [r[2] for r in rows], "close": [r[3] for r in rows],
        "Volume": [r[4] for r in rows],
    }


def daily_rows(n: int = 10, seed: int = 1, start: date = date(2026, 1, 5)) -> list[list]:
    """n valid daily rows: [iso date, open, high, low, close, volume]."""
    return [[d.isoformat()] + r for d, r in zip(weekdays(n, start), ohlcv(n, seed))]
