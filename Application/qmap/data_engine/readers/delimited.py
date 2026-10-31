"""CSV / text reader. Everything is read as text so nothing is converted behind the scenes."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from ...core.errors import IngestError
from ..mapping import SourceTable
from ..profiles import FileSpec

MAX_LISTED = 10


def _decode(data: bytes, spec: FileSpec, notes: list) -> str:
    if data[:3] == b"\xef\xbb\xbf":
        notes.append({"step": "encoding", "detail": "UTF-8 byte-order mark detected and removed"})
        return data[3:].decode("utf-8")
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        notes.append({"step": "encoding", "detail": "UTF-16 byte-order mark detected"})
        return data.decode("utf-16")
    try:
        return data.decode(spec.encoding)
    except (UnicodeDecodeError, LookupError) as exc:
        raise IngestError(f"The file could not be decoded as {spec.encoding}: {exc}.", code="E_ENCODING",
                          check="file_readable",
                          action="Set the correct 'encoding' in the profile (for example \"cp1252\" or \"utf-16\").") from exc


def read_delimited(path: Path, spec: FileSpec) -> SourceTable:
    notes: list = []
    text = _decode(path.read_bytes(), spec, notes)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=spec.delimiter, quotechar=spec.quotechar, strict=True)
    rows: list[list[str]] = []
    line_of: list[int] = []
    blank_lines = 0
    try:
        for record in reader:
            if not record or (len(record) == 1 and not record[0].strip()):
                blank_lines += 1
                continue
            rows.append(record)
            line_of.append(reader.line_num)
    except csv.Error as exc:
        raise IngestError(f"The file is malformed near line {reader.line_num}: {exc}.", code="E_MALFORMED",
                          check="file_readable",
                          action="Check for an unclosed quote or a wrong delimiter/quote character in the profile.") from exc
    if blank_lines:
        notes.append({"step": "blank_lines_skipped", "count": blank_lines,
                      "detail": "completely blank lines are not data rows and are not counted as rows"})

    if spec.skip_rows:
        if len(rows) < spec.skip_rows:
            raise IngestError(f"skip_rows = {spec.skip_rows} but the file has only {len(rows)} line(s).",
                              code="E_MALFORMED", check="file_readable")
        notes.append({"step": "skip_rows", "count": spec.skip_rows})
        rows, line_of = rows[spec.skip_rows:], line_of[spec.skip_rows:]

    if not rows:
        return SourceTable(names=[], columns=[], source_types=[], source_format="delimited_text", reader="csv",
                           reader_version="python-stdlib", transformations=notes)

    if spec.header:
        names = [c.strip() for c in rows[0]]
        names = [n if n != "" else None for n in names]
        body, body_lines = rows[1:], line_of[1:]
        width = len(names)
    else:
        names = None
        body, body_lines = rows, line_of
        width = len(rows[0])
    ragged = [(ln, len(r)) for ln, r in zip(body_lines, body) if len(r) != width]
    if ragged:
        listed = ", ".join(f"line {ln} has {n}" for ln, n in ragged[:MAX_LISTED])
        more = f" (+{len(ragged) - MAX_LISTED} more)" if len(ragged) > MAX_LISTED else ""
        raise IngestError(f"{len(ragged)} row(s) do not have {width} fields: {listed}{more}.", code="E_RAGGED_ROWS",
                          check="file_readable",
                          action="Fix the file, or the delimiter/header setting in the profile. Rows are never dropped silently.")
    columns = [[r[i] for r in body] for i in range(width)]
    return SourceTable(names=names if names is not None else [None] * width, columns=columns,
                       source_types=["str"] * width, source_format="delimited_text", reader="csv",
                       reader_version="python-stdlib", transformations=notes)
