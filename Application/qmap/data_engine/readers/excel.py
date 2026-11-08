"""Excel readers (.xlsx via openpyxl, .xls via the optional xlrd). Values only; nothing is executed."""

from __future__ import annotations

from pathlib import Path

from ...core.errors import IngestError
from ..format_detect import XLS, XLSX
from ..mapping import SourceTable
from ..profiles import FileSpec


def _type_name(values) -> str:
    for v in values:
        if v is not None:
            return type(v).__name__
    return "empty"


def _pick_sheet(names: list[str], nonempty: list[str], spec: FileSpec) -> str:
    if spec.sheet is not None:
        if isinstance(spec.sheet, int):
            if 0 <= spec.sheet < len(names):
                return names[spec.sheet]
        elif spec.sheet in names:
            return spec.sheet
        raise IngestError(f"Sheet {spec.sheet!r} was not found. Sheets in the workbook: {names}.",
                          code="E_SHEET_NOT_FOUND", check="file_readable", action="Fix 'sheet' in the profile.")
    if not nonempty:
        raise IngestError("The workbook has no sheet with data.", code="E_EMPTY_FILE", check="file_readable")
    if len(nonempty) > 1:
        raise IngestError(f"The workbook has {len(nonempty)} sheets with data ({nonempty}) and the profile does not name one.",
                          code="E_SHEET_REQUIRED", check="file_readable",
                          action="Set 'sheet' (name or 0-based number) in the profile.")
    return nonempty[0]


def _assemble(rows: list[tuple], spec: FileSpec, reader: str, version: str, kind: str) -> SourceTable:
    notes: list = []
    rows = [list(r) for r in rows]
    if spec.skip_rows:
        notes.append({"step": "skip_rows", "count": spec.skip_rows})
        rows = rows[spec.skip_rows:]
    empty_rows = sum(1 for r in rows if all(c is None or (isinstance(c, str) and not c.strip()) for c in r))
    rows = [r for r in rows if not all(c is None or (isinstance(c, str) and not c.strip()) for c in r)]
    if empty_rows:
        notes.append({"step": "blank_lines_skipped", "count": empty_rows,
                      "detail": "completely empty rows are not data rows and are not counted as rows"})
    if not rows:
        return SourceTable([], [], [], kind, reader, version, notes)
    width = max(len(r) for r in rows)
    for r in rows:
        r.extend([None] * (width - len(r)))
    if spec.header:
        head, body = rows[0], rows[1:]
        names = [str(h).strip() if h is not None and str(h).strip() else None for h in head]
    else:
        names, body = [None] * width, rows
    keep = [i for i in range(width) if not (names[i] is None and all(r[i] is None for r in body))]
    if len(keep) != width:
        notes.append({"step": "empty_unnamed_columns_dropped", "count": width - len(keep)})
    columns = [[r[i] for r in body] for i in keep]
    return SourceTable([names[i] for i in keep], columns, [_type_name(c) for c in columns], kind, reader, version, notes)


def read_excel(path: Path, spec: FileSpec, kind: str) -> SourceTable:
    if kind == XLSX:
        return _read_xlsx(path, spec)
    if kind == XLS:
        return _read_xls(path, spec)
    raise IngestError(f"Not an Excel format: {kind}", code="E_UNSUPPORTED_FORMAT", check="format_supported")


def _read_xlsx(path: Path, spec: FileSpec) -> SourceTable:
    import openpyxl

    # Opened through a file object, so the CONTENT decides (format detection already did): openpyxl refuses a file
    # NAME that does not end in .xlsx/.xlsm, e.g. an Excel workbook saved as "prices.csv".
    with path.open("rb") as fh:
        try:
            wb = openpyxl.load_workbook(fh, read_only=True, data_only=True)
        except Exception as exc:  # openpyxl raises a variety of errors for damaged files
            raise IngestError(f"The Excel file could not be opened: {exc}.", code="E_MALFORMED", check="file_readable") from exc
        try:
            names = list(wb.sheetnames)
            nonempty = [n for n in names if any(any(c is not None for c in row) for row in wb[n].iter_rows(values_only=True))]
            sheet = _pick_sheet(names, nonempty, spec)
            rows = list(wb[sheet].iter_rows(values_only=True))
        finally:
            wb.close()
    table = _assemble(rows, spec, "openpyxl", openpyxl.__version__, XLSX)
    table.transformations.append({"step": "sheet", "name": sheet})
    return table


def _read_xls(path: Path, spec: FileSpec) -> SourceTable:
    try:
        import xlrd
    except ImportError as exc:
        raise IngestError("Reading .xls files needs the optional 'xlrd' package, which is not installed.",
                          code="E_XLS_UNSUPPORTED", check="format_supported",
                          action="Install it with: pip install xlrd (or save the file as .xlsx).") from exc
    try:
        book = xlrd.open_workbook(str(path))
    except Exception as exc:
        raise IngestError(f"The .xls file could not be opened: {exc}.", code="E_MALFORMED", check="file_readable") from exc
    names = book.sheet_names()
    nonempty = [n for n in names if book.sheet_by_name(n).nrows > 0]
    sheet = _pick_sheet(names, nonempty, spec)
    ws = book.sheet_by_name(sheet)
    rows = []
    for r in range(ws.nrows):
        row = []
        for c in range(ws.ncols):
            cell = ws.cell(r, c)
            if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                row.append(None)
            elif cell.ctype == xlrd.XL_CELL_DATE:
                try:
                    row.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
                except Exception:
                    row.append(cell.value)
            elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                row.append(bool(cell.value))
            else:
                row.append(cell.value)
        rows.append(tuple(row))
    table = _assemble(rows, spec, "xlrd", xlrd.__version__, XLS)
    table.transformations.append({"step": "sheet", "name": sheet})
    return table
