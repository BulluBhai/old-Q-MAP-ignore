"""Fault-injection hook used only by tests to prove crash recovery.

In normal operation `maybe_fail` does nothing. A test enables a named step with
`inject("after_rename")`; the next time that step is reached an InjectedFault is
raised, simulating a crash at exactly that point.
"""

from __future__ import annotations

import contextlib
import threading

_lock = threading.Lock()
_active: set[str] = set()


class InjectedFault(RuntimeError):
    """Simulated crash. Deliberately not caught by ingestion code."""


STEPS = (
    "after_hash",
    "after_event_started",
    "after_temp_copy",
    "after_rename",
    "before_db_commit",
    "after_db_commit",
    "after_cleaned_temp",
    "after_cleaned_rename",
    "before_result_commit",
)


def maybe_fail(step: str) -> None:
    if _active:
        with _lock:
            if step in _active:
                raise InjectedFault(f"injected fault at step '{step}'")


@contextlib.contextmanager
def inject(step: str):
    if step not in STEPS:
        raise ValueError(f"unknown fault step {step!r}")
    with _lock:
        _active.add(step)
    try:
        yield
    finally:
        with _lock:
            _active.discard(step)
