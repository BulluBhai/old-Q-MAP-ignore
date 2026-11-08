import pytest

from fixtures.builders import HEADER, ohlcv, standard_columns, weekdays, write_delimited, write_parquet, write_xlsx
from qmap.data_engine.format_detect import PARQUET, TEXT, UNSUPPORTED, XLS, XLSX, detect_format

ROWS = [[d.isoformat()] + r for d, r in zip(weekdays(5), ohlcv(5))]


def test_csv_and_txt_are_delimited_text(tmp_path):
    for name in ("a.csv", "a.txt"):
        p = write_delimited(tmp_path / name, HEADER, ROWS)
        d = detect_format(p)
        assert d.kind == TEXT and d.extension_matches


def test_parquet_detected_by_content(tmp_path):
    p = write_parquet(tmp_path / "a.parquet", standard_columns(["2026-01-05"], [[1.0, 2.0, 0.5, 1.5, 10]]))
    assert detect_format(p).kind == PARQUET


def test_xlsx_detected_by_content(tmp_path):
    p = write_xlsx(tmp_path / "a.xlsx", HEADER, ROWS)
    d = detect_format(p)
    assert d.kind == XLSX and d.extension_matches


def test_extension_mismatch_is_reported_but_content_wins(tmp_path):
    x = write_xlsx(tmp_path / "wrong.csv", HEADER, ROWS)
    d = detect_format(x)
    assert d.kind == XLSX and not d.extension_matches
    c = write_delimited(tmp_path / "wrong.xlsx", HEADER, ROWS)
    d = detect_format(c)
    assert d.kind == TEXT and not d.extension_matches
    q = write_parquet(tmp_path / "wrong2.csv", standard_columns(["2026-01-05"], [[1.0, 2.0, 0.5, 1.5, 10]]))
    d = detect_format(q)
    assert d.kind == PARQUET and not d.extension_matches


def test_xls_detected_by_ole2_signature(tmp_path):
    p = tmp_path / "a.xls"
    p.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 100 + "Workbook".encode("utf-16-le") + b"\x00" * 50)
    assert detect_format(p).kind == XLS


def test_password_protected_excel_is_unsupported(tmp_path):
    p = tmp_path / "locked.xlsx"
    p.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 100 + "EncryptedPackage".encode("utf-16-le"))
    d = detect_format(p)
    assert d.kind == UNSUPPORTED and "password" in d.reason


def test_ole2_that_is_not_excel_is_unsupported(tmp_path):
    p = tmp_path / "doc.xls"
    p.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 200)
    assert detect_format(p).kind == UNSUPPORTED


@pytest.mark.parametrize("name,payload,fragment", [
    ("empty.csv", b"", "empty"),
    ("doc.pdf", b"%PDF-1.7\n....", "PDF"),
    ("data.json", b'{"a": 1}', "JSON"),
    ("list.json", b'  [1, 2, 3]', "JSON"),
    ("blob.csv", bytes(range(256)) * 20, "binary"),
    ("nul.csv", b"a,b\x00c\n1,2\n", "binary"),
    ("archive.gz", b"\x1f\x8b\x08\x00" + b"\x00" * 50, "gzip"),
])
def test_unsupported_content_is_reported_with_reason(tmp_path, name, payload, fragment):
    p = tmp_path / name
    p.write_bytes(payload)
    d = detect_format(p)
    assert d.kind == UNSUPPORTED and fragment.lower() in d.reason.lower()


def test_zip_that_is_not_excel(tmp_path):
    import zipfile

    p = tmp_path / "data.csv"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("data.csv", "a,b\n1,2\n")
    d = detect_format(p)
    assert d.kind == UNSUPPORTED and "ZIP archive" in d.reason


def test_macro_enabled_workbook_is_unsupported(tmp_path):
    import zipfile

    p = tmp_path / "m.xlsx"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("[Content_Types].xml", "<x/>")
        zf.writestr("xl/workbook.xml", "<x/>")
        zf.writestr("xl/vbaProject.bin", b"\x00")
    d = detect_format(p)
    assert d.kind == UNSUPPORTED and "macro" in d.reason.lower()


def test_damaged_zip_is_unsupported(tmp_path):
    p = write_xlsx(tmp_path / "a.xlsx", HEADER, ROWS)
    p.write_bytes(p.read_bytes()[:200])
    d = detect_format(p)
    assert d.kind == UNSUPPORTED and "damaged" in d.reason


def test_utf16_text_is_text(tmp_path):
    p = tmp_path / "u16.csv"
    p.write_bytes("time,open\n1,2\n".encode("utf-16"))
    assert detect_format(p).kind == TEXT


def test_file_size_limit(tmp_path):
    p = write_delimited(tmp_path / "a.csv", HEADER, ROWS)
    d = detect_format(p, max_size_bytes=10)
    assert d.kind == UNSUPPORTED
