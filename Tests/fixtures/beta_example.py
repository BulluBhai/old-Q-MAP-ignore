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
# the release candidate's own acceptance evidence (its exact commit); the 09-Nov-26 folder above stays frozen
RELEASE_EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "acceptance_testing" / "rc_ma_affinity_v2"


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


# ---- provenance of the committed evidence (used by the worked example and by Tests/beta) ---------------------------
# the clean commit the frozen V1 evidence was generated from (the owner-tested 2c81d3a holds exactly this program)
FROZEN_V1_BUILD_COMMIT = "6280c7304e50a871fb98db04ee16734319fa7f55"
FROZEN_V1_OUT = EVIDENCE / "Worked_Example_Output"
RELEASE_V1_OUT = RELEASE_EVIDENCE / "Worked_Example_Output_V1"


def check_evidence_provenance(meta: dict) -> None:
    """The release candidate's evidence must come from a CLEAN checkout of exactly the program code under test: no
    uncommitted program change when it was made (git_modified False, a real commit recorded), and the same source
    fingerprint as the code running this test (SHA-256 over every program file; line endings do not matter). Any later
    change to the program code fails this until the evidence is regenerated (QMAP_WRITE_BETA_EVIDENCE=1 from a clean
    checkout)."""
    import re

    from qmap.core.build import current_build

    build = meta["build"]
    assert build["git_modified"] is False, "the evidence was generated from a working tree with uncommitted changes"
    assert re.fullmatch(r"[0-9a-f]{40}", build["git_commit"] or ""), "the evidence does not name its source commit"
    assert build["source_fingerprint"] == current_build()["source_fingerprint"], (
        "the program code changed since the evidence was generated; regenerate it from a clean checkout")


def check_frozen_v1_evidence(meta: dict) -> None:
    """The frozen V1 evidence still names the clean build the owner-tested beta was made from (it is never
    regenerated; later builds prove V1 parity by reproducing its result tables in the worked example)."""
    build = meta["build"]
    assert build["git_modified"] is False and build["git_commit"] == FROZEN_V1_BUILD_COMMIT, build
    assert meta["analysis_id"] == "ma_affinity" and meta["run_id"].startswith("MAAF_")
