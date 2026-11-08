"""Common intermediate table and explicit source-column resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..core.errors import IngestError
from .profiles import ColumnRef

_DUP = re.compile(r"^(.*)#(\d+)$")


@dataclass
class SourceTable:
    """What every reader produces: original names/positions, original values, source types."""

    names: list  # header text per column, or None (headerless / blank header cell)
    columns: list  # column-major original values
    source_types: list
    source_format: str
    reader: str
    reader_version: str
    transformations: list = field(default_factory=list)

    @property
    def n_cols(self) -> int:
        return len(self.columns)

    @property
    def n_rows(self) -> int:
        return len(self.columns[0]) if self.columns else 0

    def describe_columns(self) -> list[dict]:
        return [{"position": i, "name": n, "source_type": t} for i, (n, t) in enumerate(zip(self.names, self.source_types))]


def _norm(text) -> str:
    return str(text).strip().casefold()


def resolve_column(ref: ColumnRef, table: SourceTable, *, field: str, check: str = "required_columns") -> int:
    """Return the 0-based column index for a reference. Never guesses between candidates."""
    if ref.position is not None:
        if ref.position >= table.n_cols:
            raise IngestError(f"Column {ref.describe()} for '{field}' does not exist: the file has only "
                              f"{table.n_cols} column(s).", code="E_COLUMN_MISSING", check=check)
        return ref.position
    if all(n is None for n in table.names):
        raise IngestError(f"Column {ref.describe()} for '{field}' is referenced by name, but the file has no header.",
                          code="E_COLUMN_MISSING", check=check,
                          action="Refer to the column by position (position = 0, 1, 2 ...) or fix [file] header.")
    wanted = ref.name
    occurrence = None
    m = _DUP.match(wanted)
    candidates = [wanted, *ref.aliases]
    results: list[tuple[int, str]] = []
    if m and not any(_norm(n) == _norm(wanted) for n in table.names if n is not None):
        base, occurrence = m.group(1), int(m.group(2))
        candidates = [base]
    for cand in candidates:
        matches = [i for i, n in enumerate(table.names) if n is not None and _norm(n) == _norm(cand)]
        if occurrence is not None:
            if 1 <= occurrence <= len(matches):
                return matches[occurrence - 1]
            continue
        results.extend((i, cand) for i in matches)
    idxs = sorted({i for i, _ in results})
    if len(idxs) == 1:
        return idxs[0]
    if len(idxs) > 1:
        raise IngestError(f"Column {ref.describe()} for '{field}' matches {len(idxs)} columns (positions {idxs}).",
                          code="E_COLUMN_AMBIGUOUS", check=check,
                          action=f"Refer to it by position, or by occurrence, e.g. name = \"{wanted}#1\" (first match).")
    found = [n for n in table.names if n is not None]
    raise IngestError(f"Column {ref.describe()} for '{field}' was not found. Columns found: {found}.",
                      code="E_COLUMN_MISSING", check=check,
                      action="Fix the column name in the profile (or add an alias).")


def safe_extra_name(name, position: int, taken: set[str]) -> str:
    base = "x_" + re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip()).strip("_").lower() if name is not None else f"x_col{position}"
    if base == "x_":
        base = f"x_col{position}"
    out, n = base, 2
    while out in taken:
        out = f"{base}_{n}"
        n += 1
    taken.add(out)
    return out
