"""Identify a file's format from its actual structure. The extension is only a hint."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

PARQUET = "parquet"
XLSX = "xlsx"
XLS = "xls"
TEXT = "delimited_text"
UNSUPPORTED = "unsupported"

SUPPORTED_KINDS = (PARQUET, XLSX, XLS, TEXT)

EXTENSION_KIND = {
    ".csv": TEXT, ".txt": TEXT, ".tsv": TEXT, ".dat": TEXT,
    ".parquet": PARQUET, ".pq": PARQUET,
    ".xlsx": XLSX, ".xls": XLS,
}

# Extension used for the stored raw copy (content-addressed store).
STORED_EXTENSION = {PARQUET: "parquet", XLSX: "xlsx", XLS: "xls", TEXT: "txt"}

_OLE2 = bytes.fromhex("D0CF11E0A1B11AE1")
_SAMPLE = 64 * 1024


@dataclass(frozen=True)
class DetectedFormat:
    kind: str
    reason: str = ""
    extension: str = ""
    extension_matches: bool = False

    @property
    def supported(self) -> bool:
        return self.kind in SUPPORTED_KINDS


def _result(kind: str, ext: str, reason: str = "") -> DetectedFormat:
    return DetectedFormat(kind=kind, reason=reason, extension=ext,
                          extension_matches=(EXTENSION_KIND.get(ext) == kind and kind != UNSUPPORTED))


def _looks_binary(sample: bytes) -> bool:
    if b"\x00" in sample:
        return True
    if not sample:
        return False
    odd = sum(1 for b in sample if b < 9 or 14 <= b < 32 and b != 27)
    return odd / len(sample) > 0.30


def detect_format(path: str | Path, *, max_size_bytes: int | None = None) -> DetectedFormat:
    path = Path(path)
    ext = path.suffix.lower()
    size = path.stat().st_size
    if size == 0:
        return _result(UNSUPPORTED, ext, "The file is empty (0 bytes).")
    if max_size_bytes is not None and size > max_size_bytes:
        return _result(UNSUPPORTED, ext, f"The file is larger than the configured limit of {max_size_bytes // (1024 * 1024)} MB.")

    with open(path, "rb") as fh:
        head = fh.read(_SAMPLE)

    if head[:4] == b"PAR1":
        return _result(PARQUET, ext)

    if head[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile:
            return _result(UNSUPPORTED, ext, "The file starts like a ZIP/Excel file but is damaged or truncated.")
        if "[Content_Types].xml" in names and "xl/workbook.xml" in names:
            if "xl/vbaProject.bin" in names:
                return _result(UNSUPPORTED, ext, "Macro-enabled Excel workbooks (.xlsm) are not supported. "
                                                 "Save a copy as .xlsx (without macros).")
            return _result(XLSX, ext)
        return _result(UNSUPPORTED, ext, "This is a ZIP archive that is not an Excel workbook. "
                                         "Extract the data file and ingest that instead.")

    if head[:8] == _OLE2:
        data = path.read_bytes()
        if "EncryptedPackage".encode("utf-16-le") in data:
            return _result(UNSUPPORTED, ext, "The Excel file is password-protected. Remove the password and try again.")
        if "Workbook".encode("utf-16-le") in data or "Book".encode("utf-16-le") in data:
            return _result(XLS, ext)
        return _result(UNSUPPORTED, ext, "This is an old Office (OLE2) file that is not an Excel workbook.")

    if head[:5] == b"%PDF-":
        return _result(UNSUPPORTED, ext, "This is a PDF document, not market data.")
    if head[:2] == b"\x1f\x8b":
        return _result(UNSUPPORTED, ext, "This is a gzip archive. Decompress it and ingest the data file.")
    if head[:6] in (b"7z\xbc\xaf\x27\x1c", b"Rar!\x1a\x07"):
        return _result(UNSUPPORTED, ext, "This is a compressed archive. Extract the data file and ingest that.")

    if head[:2] in (b"\xff\xfe", b"\xfe\xff") or head[:3] == b"\xef\xbb\xbf":
        text_like = True
    else:
        text_like = not _looks_binary(head)
    if not text_like:
        return _result(UNSUPPORTED, ext, "The file contains binary data and is not a supported format "
                                         "(supported: Parquet, Excel .xlsx/.xls, CSV and text).")
    stripped = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    if stripped[:1] in (b"{", b"["):
        return _result(UNSUPPORTED, ext, "This looks like JSON, which is not a supported format.")
    return _result(TEXT, ext)
