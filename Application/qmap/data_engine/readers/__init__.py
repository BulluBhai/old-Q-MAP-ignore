"""Format readers. Each returns a SourceTable; none of them modify the source file."""

from __future__ import annotations

from pathlib import Path

from ...core.errors import IngestError
from ..format_detect import PARQUET, TEXT, XLS, XLSX
from ..mapping import SourceTable
from ..profiles import FileSpec


def read_source(path: Path, kind: str, spec: FileSpec) -> SourceTable:
    if spec.expected_format and spec.expected_format != kind:
        raise IngestError(
            f"The profile expects a '{spec.expected_format}' file but this file is '{kind}'.",
            code="E_FORMAT_MISMATCH", check="format_matches_profile",
            action="Use the matching profile, or correct expected_format in the profile.")
    if kind == TEXT:
        from .delimited import read_delimited

        return read_delimited(path, spec)
    if kind in (XLSX, XLS):
        from .excel import read_excel

        return read_excel(path, spec, kind)
    if kind == PARQUET:
        from .parquet_reader import read_parquet

        return read_parquet(path)
    raise IngestError(f"Unsupported file format '{kind}'.", code="E_UNSUPPORTED_FORMAT", check="format_supported")
