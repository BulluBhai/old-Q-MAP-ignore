"""Shared test helpers (synthetic price data and project paths). Not a test file."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # Tests/

SBIN_FILE = ROOT / "fixtures" / "qlopb_data" / "NSE_SBIN, 60.csv"
NIFTY_FILE = ROOT / "fixtures" / "qlopb_data" / "Nifty500 Healthcare.txt"
SBIN_SHA256 = "9bb9d8ccaf1c603c1f89ca3e35a6ae6c3b343dbfc37b8399eb0fc437965ad4d3"


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
