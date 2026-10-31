"""Explicit volume handling.

The canonical `volume` is filled ONLY by a rule declared in the source profile:
  none          the source has no volume (valid; volume stays empty, never zero)
  use_column    one named column (optionally verified against duplicate columns)
  sum_columns   split volume, added up, with a written justification

Original volume fields are always preserved, nothing is added, discarded or equated without
a rule, and two volume columns that differ are never merged automatically.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..core.errors import IngestError
from .mapping import SourceTable, resolve_column
from .numeric import INVALID, MISSING, parse_number
from .profiles import FileSpec, VolumeSpec
from .results import ERROR, WARNING, Collector

ABSENT, MAPPED, DERIVED_SUM = "absent", "mapped", "derived_sum"


@dataclass
class VolumeResult:
    values: list | None
    status: str
    source_indices: set = field(default_factory=set)  # every volume-related source column (kept as x_ columns)
    provenance: dict = field(default_factory=dict)


def _column_values(table: SourceTable, idx: int, file_spec: FileSpec, collector: Collector, label: str) -> list:
    out = []
    for i, v in enumerate(table.columns[idx]):
        num, status = parse_number(v, file_spec.decimal, file_spec.thousands)
        if status == INVALID:
            collector.add("numeric_types", ERROR, i + 1, label, v, f"Volume value {v!r} is not a number.")
            out.append(math.nan)
        elif status == MISSING:
            out.append(math.nan)
        elif not math.isfinite(num):
            collector.add("numeric_types", ERROR, i + 1, label, v, f"Volume value {v!r} is not a finite number.")
            out.append(math.nan)
        else:
            out.append(num)
    return out


def _same(a: float, b: float) -> bool:
    return (math.isnan(a) and math.isnan(b)) or a == b


def apply_volume(table: SourceTable, spec: VolumeSpec, file_spec: FileSpec, collector: Collector) -> VolumeResult:
    check = "volume_mapping_resolved"
    prov: dict = {"rule": spec.rule}
    kept: set[int] = set()
    used: set[int] = set()
    values: list | None = None
    status = ABSENT

    preserved: set[int] = set()
    absent_preserved = []
    for ref in spec.preserved_not_volume:
        try:
            preserved.add(resolve_column(ref, table, field="preserved_not_volume", check=check))
        except IngestError:
            absent_preserved.append(ref.describe())
    if absent_preserved:
        prov["preserved_not_volume_absent_in_file"] = absent_preserved

    if spec.rule == "use_column":
        idx = resolve_column(spec.column, table, field="volume", check=check)
        used.add(idx)
        values = _column_values(table, idx, file_spec, collector, "volume")
        status = MAPPED
        prov["source_column"] = {"position": idx, "name": table.names[idx]}
        if spec.verify_identical:
            checked = []
            for ref in spec.verify_identical:
                j = resolve_column(ref, table, field="volume (verify_identical)", check=check)
                used.add(j)
                other = _column_values(table, j, file_spec, collector, "volume_duplicate")
                bad = [i for i, (a, b) in enumerate(zip(values, other)) if not _same(a, b)]
                for i in bad:
                    collector.add(check, ERROR, i + 1, "volume", table.columns[j][i],
                                  f"Duplicate volume columns differ: {table.names[idx] or idx} = {table.columns[idx][i]!r} "
                                  f"but {table.names[j] or j} = {table.columns[j][i]!r}. They are not merged automatically.")
                checked.append({"position": j, "name": table.names[j], "rows_differing": len(bad)})
            prov["verified_identical_to"] = checked
    elif spec.rule == "sum_columns":
        idxs = [resolve_column(ref, table, field="volume (sum_columns)", check=check) for ref in spec.columns]
        used.update(idxs)
        parts = [_column_values(table, j, file_spec, collector, "volume_part") for j in idxs]
        values = [math.nan if any(math.isnan(p[i]) for p in parts) else sum(p[i] for p in parts)
                  for i in range(table.n_rows)]
        status = DERIVED_SUM
        prov["source_columns"] = [{"position": j, "name": table.names[j]} for j in idxs]
        prov["justification"] = spec.justification
    else:
        prov["note"] = "the profile declares that the source has no volume"

    kept = used | preserved
    like = [i for i, n in enumerate(table.names) if n is not None and "vol" in str(n).casefold()]
    ignored = [i for i in like if i not in used and i not in preserved]
    if ignored:
        names = [table.names[i] for i in ignored]
        collector.add("volume_columns_ignored", WARNING, None, "volume", None,
                      f"Volume-like column(s) {names} exist but the profile does not use them. They are kept as x_ columns; "
                      "name them under [volume] preserved_not_volume to acknowledge this.")
        prov["volume_like_columns_ignored"] = names
        kept |= set(ignored)
    return VolumeResult(values=values, status=status, source_indices=kept, provenance=prov)
