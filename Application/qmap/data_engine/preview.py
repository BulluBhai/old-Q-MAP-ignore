"""Dry-run report for a source file. Registers nothing and writes nothing.

Use it to inspect a new file and to write or check a source profile. Suggestions here are
only suggestions: ingestion itself never infers formats, units, time zones or volume mappings.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from ..core.config import Settings
from ..core.errors import IngestError
from .format_detect import TEXT, detect_format
from .mapping import SourceTable
from .process import process_table
from .profiles import FileSpec, SourceProfile
from .readers import read_source


def _looks_numeric(s) -> bool:
    return isinstance(s, (int, float)) or bool(re.fullmatch(r"[+-]?\d+(\.\d+)?", str(s).strip()))


def _date_hints(values: list) -> list[str]:
    sample = [str(v).strip() for v in values[:50] if v is not None and str(v).strip()]
    if not sample:
        return []
    hints = []
    if all(re.fullmatch(r"\d{10}", s) for s in sample):
        hints.append("10-digit integers: could be Unix seconds (declare kind = \"unix_s\")")
    if all(re.fullmatch(r"\d{13}", s) for s in sample):
        hints.append("13-digit integers: could be Unix milliseconds (declare kind = \"unix_ms\")")
    if all(re.fullmatch(r"\d{8}", s) for s in sample):
        hints.append("8-digit integers: could be YYYYMMDD (declare kind = \"format\", format = \"%Y%m%d\")")
    if all(re.fullmatch(r"\d{6}", s) for s in sample):
        hints.append("6-digit integers: could be DDMMYY, YYMMDD or MMDDYY - ambiguous, YOU must declare the order")
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) for s in sample):
        hints.append("ISO dates (declare kind = \"iso\")")
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:?\d{2})?", s) for s in sample):
        offsets = {m.group(1) for s in sample if (m := re.search(r"(Z|[+-]\d{2}:?\d{2})$", s))}
        hints.append("ISO timestamps (declare kind = \"iso\")"
                     + (f"; UTC offsets seen: {sorted(offsets)}" if offsets else "; NO UTC offset: a time zone must be declared"))
    if all(re.fullmatch(r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}", s) for s in sample):
        hints.append("day/month/year-style text: day-first vs month-first (and the century of two-digit years) must be "
                     "declared by you; it is never guessed")
    return hints or ["no standard pattern recognised: declare an explicit format"]


def _sniff_text(path: Path) -> list[str]:
    lines: list[str] = []
    try:
        data = path.read_bytes()[:200_000]
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ["Could not decode as UTF-8: set [file] encoding in the profile."]
    try:
        d = csv.Sniffer().sniff(text.split("\n", 20)[0] + "\n" + "\n".join(text.split("\n")[1:20]), delimiters=",;\t|")
        lines.append(f"Suggested delimiter: {d.delimiter!r}")
    except csv.Error:
        lines.append("Could not suggest a delimiter.")
    rows = list(csv.reader(io.StringIO(text), delimiter=",")) if "," in text.split("\n", 1)[0] else []
    if len(rows) >= 2 and rows[0] and not any(_looks_numeric(c) for c in rows[0]) and any(_looks_numeric(c) for c in rows[1]):
        lines.append("The first row looks like a header (text above numbers). Confirm with [file] header = true.")
    elif len(rows) >= 2:
        lines.append("The first row looks like DATA, so the file may have no header. Confirm [file] header.")
    return lines


def preview_file(path: str | Path, profile: SourceProfile | None = None, settings: Settings | None = None, *,
                 max_rows: int = 8, exchange: str | None = None, symbol: str | None = None,
                 timeframe: str | None = None) -> str:
    path = Path(path)
    out = [f"PREVIEW (nothing is registered or written): {path.name}"]
    det = detect_format(path, max_size_bytes=(settings.max_file_size_mb * 1024 * 1024) if settings else None)
    out.append(f"Detected format: {det.kind}" + ("" if det.supported else f"  -> {det.reason}"))
    if det.supported and not det.extension_matches:
        out.append(f"Note: the extension {det.extension or '(none)'} does not match the content; content wins.")
    if not det.supported:
        return "\n".join(out)
    spec = profile.file if profile else FileSpec(header=True)
    if det.kind == TEXT:
        out.extend(_sniff_text(path))
    try:
        table: SourceTable = read_source(path, det.kind, spec)
    except IngestError as exc:
        out.append(f"Could not read the file with these settings: {exc}")
        return "\n".join(out)
    out.append(f"Rows: {table.n_rows}   Columns: {table.n_cols}   Reader: {table.reader} {table.reader_version}")
    for note in table.transformations:
        out.append(f"Reader note: {note}")
    out.append("Columns (position: name [source type]):")
    for c in table.describe_columns():
        out.append(f"  {c['position']}: {c['name']!r} [{c['source_type']}]")
    vol_like = [c["name"] for c in table.describe_columns() if c["name"] and "vol" in str(c["name"]).casefold()]
    if vol_like:
        out.append(f"Volume-like columns: {vol_like}. Decide in [volume] which one is volume; nothing is merged for you.")
    out.append(f"First {min(max_rows, table.n_rows)} row(s):")
    for i in range(min(max_rows, table.n_rows)):
        out.append("  " + " | ".join(str(col[i]) for col in table.columns))
    if table.n_cols:
        out.append("Date/time suggestions for column 0 (suggestions only, never applied automatically):")
        out.extend("  - " + h for h in _date_hints(table.columns[0]))
    if profile and settings:
        res = process_table(table, profile, settings, filename=path.name,
                            overrides={"exchange": exchange, "symbol": symbol, "timeframe": timeframe})
        failed = [c for c in res.checks if c.is_error]
        warned = [c for c in res.checks if c.severity == "warning" and not c.passed]
        out.append(f"With profile {profile.profile_id} v{profile.profile_version}: "
                   + ("WOULD BE ACCEPTED" if res.accepted else "WOULD BE REJECTED"))
        for c in failed:
            out.append(f"  ERROR   {c.name}: {c.detail}")
        for c in warned:
            out.append(f"  WARNING {c.name}: {c.detail}")
    return "\n".join(out)
