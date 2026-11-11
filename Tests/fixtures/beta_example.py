"""The MA Affinity beta worked example and acceptance dataset (09-Nov-26): one SYNTHETIC daily file.

`NSE_BETADEMO.csv`: 1,500 weekday bars from 01-Jan-19 (seeded random walk with a small upward drift; no real
instrument), columns time, open, high, low, close, volume. The committed copy for the owner is
docs/acceptance_testing/beta_ma_affinity_09_Nov_26/NSE_BETADEMO.csv; test_beta_worked_example checks it equals this
generator's output byte for byte.

Acceptance parameters: MA types `SMA,EMA`; every other box left at its default.
"""

from __future__ import annotations

import csv
import io
import random
from datetime import date, timedelta
from pathlib import Path

NAME = "NSE_BETADEMO.csv"
INSTRUMENT = "NSE:BETADEMO"
PARAMS = {"ma_types": "SMA,EMA"}
EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "acceptance_testing" / "beta_ma_affinity_09_Nov_26"


def text() -> str:
    rng = random.Random(2026)
    out = io.StringIO(newline="")
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["time", "open", "high", "low", "close", "volume"])
    day, price, n = date(2019, 1, 1), 1000.0, 0
    while n < 1500:
        if day.weekday() < 5:
            o = price
            c = round(o * (1 + rng.gauss(0.0004, 0.012)), 2)
            h = round(max(o, c) * (1 + abs(rng.gauss(0, 0.004))), 2)
            lo = round(min(o, c) * (1 - abs(rng.gauss(0, 0.004))), 2)
            w.writerow([day.isoformat(), round(o, 2), h, lo, c, rng.randint(200_000, 900_000)])
            price, n = c, n + 1
        day += timedelta(days=1)
    return out.getvalue()


def write(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / NAME
    p.write_bytes(text().encode("utf-8"))
    return p


if __name__ == "__main__":
    print(write(EVIDENCE))
