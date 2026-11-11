"""Error types. Every error carries a stable code, a plain message and a suggested action."""

from __future__ import annotations


class QmapError(Exception):
    code = "E_QMAP"

    def __init__(self, message: str, *, code: str | None = None, action: str | None = None):
        super().__init__(message)
        if code:
            self.code = code
        self.message = message
        self.action = action

    def __str__(self) -> str:
        text = f"[{self.code}] {self.message}"
        if self.action:
            text += f" Action: {self.action}"
        return text


class RunCancelled(QmapError):
    """The person asked a running job to stop. The run is closed with status 'cancelled' (not 'failed')."""

    code = "E_CANCELLED"


class ConfigError(QmapError):
    code = "E_CONFIG"


class ProfileError(QmapError):
    code = "E_PROFILE"


class IngestError(QmapError):
    """A problem that stops one ingest attempt. `check` names the quality check it maps to."""

    code = "E_INGEST"

    def __init__(self, message: str, *, code: str | None = None, action: str | None = None,
                 check: str = "file_readable"):
        super().__init__(message, code=code, action=action)
        self.check = check
