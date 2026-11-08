"""Structured logging. Library code only logs; it never prints.

Each run gets its own log file in its run folder. Every line carries the Run ID.
"""

from __future__ import annotations

import contextvars
import logging
from pathlib import Path

_current_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("qmap_run_id", default="-")

LOGGER_NAME = "qmap"
_FORMAT = "%(asctime)s %(levelname)-7s [%(run_id)s] %(name)s: %(message)s"


class _RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _current_run_id.get()
        return True


class _OnlyRun(logging.Filter):
    """A run's log file only receives lines emitted while that run is the current one (safe for threads)."""

    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "run_id", None) == self.run_id


def get_logger(name: str | None = None) -> logging.Logger:
    base = logging.getLogger(LOGGER_NAME)
    return base if not name else base.getChild(name)


def _formatter() -> logging.Formatter:
    fmt = logging.Formatter(_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S")
    fmt.converter = __import__("time").gmtime  # UTC timestamps
    return fmt


def configure_console(level: str = "INFO") -> logging.Handler:
    """Optional console output for command-line use."""
    logger = get_logger()
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(_formatter())
    handler.addFilter(_RunIdFilter())
    logger.addHandler(handler)
    return handler


def attach_run_log(run_dir: Path, run_id: str, level: str = "INFO") -> logging.Handler:
    """Start writing this run's log to <run_dir>/run_log.txt and tag all lines with the Run ID."""
    logger = get_logger()
    logger.setLevel(min(logger.level or logging.INFO, getattr(logging, level, logging.INFO)) or logging.INFO)
    _current_run_id.set(run_id)
    handler = logging.FileHandler(Path(run_dir) / "run_log.txt", mode="a", encoding="utf-8")
    handler.setFormatter(_formatter())
    handler.addFilter(_RunIdFilter())
    handler.addFilter(_OnlyRun(run_id))
    logger.addHandler(handler)
    return handler


def detach_run_log(handler: logging.Handler) -> None:
    get_logger().removeHandler(handler)
    handler.close()
    _current_run_id.set("-")
