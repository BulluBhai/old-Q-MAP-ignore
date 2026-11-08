"""Shared result types for ingestion and validation."""

from __future__ import annotations

from dataclasses import dataclass, field

ERROR, WARNING, INFO = "error", "warning", "info"
MAX_EXAMPLES = 10


@dataclass
class Issue:
    """One problem found in the source data. Issues are reported, never repaired."""

    check: str
    severity: str
    row: int | None  # 1-based position of the data row in the source (src_row); None = whole file
    field: str | None
    value: object
    message: str


@dataclass
class CheckResult:
    name: str
    severity: str
    passed: bool
    rows_failed: int = 0
    detail: str = ""

    @property
    def is_error(self) -> bool:
        return self.severity == ERROR and not self.passed


def examples(rows: list[int], limit: int = MAX_EXAMPLES) -> str:
    shown = ", ".join(str(r) for r in rows[:limit])
    more = f" (+{len(rows) - limit} more)" if len(rows) > limit else ""
    return f"source rows {shown}{more}"


@dataclass
class Collector:
    """Accumulates issues and turns them into per-check results."""

    issues: list[Issue] = field(default_factory=list)

    def add(self, check: str, severity: str, row: int | None, field_: str | None, value, message: str) -> None:
        self.issues.append(Issue(check, severity, row, field_, value, message))

    def rows_for(self, check: str) -> list[int]:
        return sorted({i.row for i in self.issues if i.check == check and i.row is not None})

    def count(self, check: str) -> int:
        return sum(1 for i in self.issues if i.check == check)
