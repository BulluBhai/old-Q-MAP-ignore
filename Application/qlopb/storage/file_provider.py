"""
File-based storage helpers. QLOPB deliberately uses plain files (no database).

FileProvider : builds time-stamped output names (dd_mmm_yy_hhmmss), creates
               folders, saves/reads tables.
RunLog       : collects timestamped log lines in memory, optionally forwards each
               line to a callback (the GUI) and can write the lines to a .log file.
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

import pandas as pd

from qlopb.config import settings as cfg


def make_stamp(now: _dt.datetime | None = None) -> str:
    """dd_mmm_yy_hhmmss, e.g. 11_Oct_26_142530 (owner's file-name rule)."""
    return (now or _dt.datetime.now()).strftime(cfg.FILE_STAMP_FMT)


def safe_name(text: str, limit: int = 40) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:limit] or "run"


class FileProvider:
    def __init__(self, output_root=None):
        self.output_root = Path(output_root) if output_root else cfg.OUTPUT_DIR

    def ensure(self, folder) -> Path:
        p = Path(folder)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def new_run_folder(self, label: str, stamp: str | None = None) -> Path:
        stamp = stamp or make_stamp()
        return self.ensure(self.output_root / f"{safe_name(label)}_{stamp}")

    @staticmethod
    def out_path(folder, base: str, ext: str, stamp: str) -> Path:
        return Path(folder) / f"{safe_name(base, 60)}_{stamp}.{ext.lstrip('.')}"

    @staticmethod
    def read_table(path) -> pd.DataFrame:
        path = Path(path)
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        if path.suffix.lower() in (".parquet", ".pq"):
            return pd.read_parquet(path)
        raise ValueError(f"Unsupported table type: {path.suffix}")

    @staticmethod
    def save_table(df: pd.DataFrame, path) -> Path:
        path = Path(path)
        if path.suffix.lower() == ".csv":
            df.to_csv(path, index=False)
        elif path.suffix.lower() in (".parquet", ".pq"):
            df.to_parquet(path, index=False)
        else:
            raise ValueError(f"Unsupported table type: {path.suffix}")
        return path


class RunLog:
    def __init__(self, callback=None):
        self.lines: list = []
        self.callback = callback
        self.warnings = 0
        self.errors = 0

    def _add(self, level: str, msg: str) -> None:
        line = f"{_dt.datetime.now().strftime('%H:%M:%S')}  {level:<7} {msg}"
        self.lines.append(line)
        if self.callback:
            try:
                self.callback(line)
            except Exception:       # a broken callback must never stop the research
                pass

    def info(self, msg): self._add("INFO", msg)

    def warn(self, msg):
        self.warnings += 1
        self._add("WARNING", msg)

    def error(self, msg):
        self.errors += 1
        self._add("ERROR", msg)

    def save(self, path) -> Path:
        path = Path(path)
        path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        return path
