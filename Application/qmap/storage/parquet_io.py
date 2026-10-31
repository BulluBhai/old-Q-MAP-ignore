"""Parquet output for standardised (cleaned) datasets, with provenance in the file's own metadata."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from ..data_engine import canonical as C
from .files import fsync_path


def _extra_array(values: list) -> pa.Array:
    non_null = [v for v in values if v is not None]
    if non_null and all(isinstance(v, str) for v in non_null):
        return pa.array(values, type=pa.string())
    try:
        return pa.array(values)
    except (pa.ArrowInvalid, pa.ArrowTypeError, TypeError):
        return pa.array([None if v is None else str(v) for v in values], type=pa.string())


def build_table(group, metadata: dict) -> pa.Table:
    f = group.frame
    nan_mask = lambda a: np.isnan(np.asarray(a, dtype=float))  # noqa: E731
    arrays = {
        "session_date": pa.array(f["session_date"], type=pa.date32()),
        "timestamp_utc": pa.array(f["timestamp_utc"], type=pa.timestamp("ns", "UTC")),
    }
    for k in ("open", "high", "low", "close", "volume"):
        a = np.asarray(f[k], dtype=float)
        arrays[k] = pa.array(a, type=pa.float64(), mask=nan_mask(a))  # empty = null, never zero
    arrays["src_row"] = pa.array(np.asarray(f["src_row"], dtype=np.int64), type=pa.int64())
    arrays["quality_flags"] = pa.array(np.asarray(f["quality_flags"], dtype=np.int64), type=pa.int64())
    for name in group.extra_columns:
        arrays[name] = _extra_array(list(f[name]))
    table = pa.table(arrays)
    meta = {"qmap": json.dumps({
        "canonical_schema_version": C.CANONICAL_SCHEMA_VERSION,
        "quant_columns": list(C.QUANT_COLUMNS),
        "preserved_columns_are_not_quant_inputs": group.extra_columns,
        "flag_bits": {str(k): v for k, v in C.FLAG_DESCRIPTIONS.items()},
        "sort_rule": C.SORT_RULE,
        **metadata,
    }, default=str, sort_keys=True).encode("utf-8")}
    return table.replace_schema_metadata(meta)


def write_canonical_parquet(path: Path, group, metadata: dict) -> None:
    """Write to `path` (a temporary file) and flush it to disk. The caller renames it into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(build_table(group, metadata), str(path), compression="snappy")
    fsync_path(path)


def read_canonical(path: str | Path) -> pa.Table:
    return pq.read_table(str(path))


def read_canonical_metadata(path: str | Path) -> dict:
    meta = pq.ParquetFile(str(path)).schema_arrow.metadata or {}
    return json.loads(meta.get(b"qmap", b"{}").decode("utf-8"))


def read_quant_columns(path: str | Path) -> pa.Table:
    """The columns downstream modules may use as inputs: keys, OHLC, volume, src_row and quality_flags.

    Preserved original columns (x_...) are deliberately left out: they are data kept for audit, not
    quantitative inputs.
    """
    return pq.read_table(str(path), columns=list(C.CORE_COLUMNS))
