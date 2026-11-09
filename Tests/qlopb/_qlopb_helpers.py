"""Shared test helpers (synthetic price data and project paths). Not a test file."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # Tests/

SBIN_FILE = ROOT / "fixtures" / "qlopb_data" / "NSE_SYNTHHOURLY, 60.csv"  # synthetic (09-Nov-26)
NIFTY_FILE = ROOT / "fixtures" / "qlopb_data" / "Synth500 Sector.txt"  # synthetic (09-Nov-26)
SBIN_SHA256 = "fb47e30767bdba83f9d0620f1492e36e790d975590b519a4475b291e4eb3f623"


def synthetic_ohlc(n=600, seed=7, start="2020-01-01", freq="B", drift=0.0003, vol=0.012):
    """A reproducible random-walk price table that obeys High>=Open/Close>=Low."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    close = 100 * np.cumprod(1 + rets)
    open_ = np.concatenate([[100.0], close[:-1]])
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    idx = pd.date_range(start, periods=n, freq=freq)
    df = pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close,
                       "volume": rng.integers(1000, 5000, n).astype(float)}, index=idx)
    df.index.name = "datetime"
    return df


def write_text(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="")
    return path
