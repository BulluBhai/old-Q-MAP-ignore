"""Parquet reader. Types, timestamp units and time zones come from the file itself."""

from __future__ import annotations

from pathlib import Path

from ...core.errors import IngestError
from ..mapping import SourceTable


def read_parquet(path: Path) -> SourceTable:
    import pyarrow as pa
    import pyarrow.parquet as pq

    try:
        table = pq.ParquetFile(path).read()
    except Exception as exc:  # pyarrow raises ArrowInvalid / OSError for damaged files
        raise IngestError(f"The Parquet file could not be read (damaged or truncated?): {exc}.", code="E_MALFORMED",
                          check="file_readable") from exc
    nested = [f.name for f in table.schema if pa.types.is_nested(f.type)]
    if nested:
        raise IngestError(f"Nested Parquet column(s) are not supported: {nested}.", code="E_UNSUPPORTED_COLUMN_TYPE",
                          check="file_readable", action="Flatten the file before ingesting.")
    names = [f.name for f in table.schema]
    columns = [table.column(i).to_pylist() for i in range(table.num_columns)]
    types = [str(f.type) for f in table.schema]
    return SourceTable(names=names, columns=columns, source_types=types, source_format="parquet", reader="pyarrow",
                       reader_version=pa.__version__, transformations=[])
