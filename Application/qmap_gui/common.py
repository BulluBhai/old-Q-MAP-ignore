"""Small helpers shared by both applications' screens and logic. No tkinter, and no data-preparation code, so the
Analytical Workbench can use them without importing anything that reads or registers source files."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable


def fmt_duration(seconds: float) -> str:
    s = int(round(seconds))
    if s < 60:
        return f"{s} s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m} min {s:02d} s"
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min"


def fmt_clock(moment: datetime) -> str:
    return moment.strftime("%d-%b-%y %H:%M:%S")  # dd-mmm-yy


def open_in_file_manager(path: str | Path) -> tuple[bool, str]:
    p = Path(path)
    if not p.exists():
        return False, f"{p} does not exist."
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except OSError as exc:
        return False, f"Could not open {p}: {exc}"
    return True, "Opened."


class EmitHandler(logging.Handler):
    """Forwards Foundation log lines to the screen's queue (thread-safe: it only puts onto a queue)."""

    def __init__(self, emit: Callable[[dict], None]):
        super().__init__(level=logging.INFO)
        self.emit_event = emit
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:  # noqa: A003 - logging API name
        try:
            self.emit_event({"type": "log", "text": self.format(record)})
        except Exception:  # never let logging break a run
            pass
