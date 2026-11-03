"""Each supported format, headered/headerless, column mapping, encodings and malformed input."""

import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from fixtures.builders import (HEADER, daily_rows, standard_columns, weekdays, write_delimited, write_parquet,
                               write_xlsx)
from fixtures.profiles import do_ingest, failed_names, make_profile, read_group
from qmap import CLEANING_CODE_VERSION
from qmap.storage.files import sha256_file

ROWS = daily_rows(10)
FIXTURE_XLS = Path(__file__).resolve().parents[1] / "fixtures" / "data" / "synthetic_daily.xls"


def canonical(settings, db, res):
    g = read_group(settings, db, res.dataset_ids[0])
    return {k: g[k] for k in ("session_date", "timestamp_utc", "open", "high", "low", "close", "volume", "src_row")}


def rejected_without_dataset(db, res):
    assert res.outcome == "rejected", res.message
    assert not db.query("SELECT 1 FROM datasets WHERE layer='cleaned'")
    assert db.one("SELECT outcome FROM ingest_attempts WHERE attempt_id=?", (res.attempt_id,))["outcome"] == "rejected"


# ---- every format gives the same canonical data ----------------------------------------------------
def make_all_formats(src):
    out = {
        "csv": write_delimited(src / "f.csv", HEADER, ROWS),
        "txt": write_delimited(src / "f.txt", HEADER, ROWS),
        "tsv_in_txt": write_delimited(src / "tab.txt", HEADER, ROWS, delimiter="\t"),
        "xlsx": write_xlsx(src / "f.xlsx", HEADER, ROWS),
        "parquet": write_parquet(src / "f.parquet", standard_columns([r[0] for r in ROWS], [r[1:] for r in ROWS])),
    }
    return out


@pytest.fixture
def formats(src):
    return make_all_formats(src)


@pytest.mark.parametrize("name", ["csv", "txt", "tsv_in_txt", "xlsx", "parquet"])
def test_each_supported_format_is_ingested(name, formats, run, settings, db):
    file_spec = {"header": True, "delimiter": "\t"} if name == "tsv_in_txt" else {"header": True}
    res = do_ingest(run, formats[name], make_profile(file=file_spec))
    assert res.outcome == "accepted", res.message
    c = canonical(settings, db, res)
    assert c["session_date"][0] == date(2026, 1, 5) and len(c["open"]) == 10
    raw = db.one("SELECT * FROM datasets WHERE layer='raw'")
    assert raw["file_format"] == {"csv": "delimited_text", "txt": "delimited_text", "tsv_in_txt": "delimited_text",
                                  "xlsx": "xlsx", "parquet": "parquet"}[name]


def test_all_formats_produce_identical_canonical_output(formats, run, settings, db):
    outputs = {}
    for name in ("csv", "xlsx", "parquet"):
        res = do_ingest(run, formats[name], make_profile(profile_id=f"p_{name}"))
        assert res.outcome == "accepted", (name, res.message)
        outputs[name] = canonical(settings, db, res)
    assert outputs["csv"] == outputs["xlsx"] == outputs["parquet"]


@pytest.mark.skipif(not FIXTURE_XLS.exists(), reason="synthetic .xls fixture missing")
def test_xls_is_read_when_xlrd_is_available(run, settings, db):
    pytest.importorskip("xlrd")
    res = do_ingest(run, FIXTURE_XLS, make_profile())
    assert res.outcome == "accepted", res.message
    assert db.one("SELECT file_format FROM datasets WHERE layer='raw'")["file_format"] == "xls"
    assert len(canonical(settings, db, res)["open"]) == 5


@pytest.mark.skipif(not FIXTURE_XLS.exists(), reason="synthetic .xls fixture missing")
def test_xls_without_xlrd_gives_a_clear_message(run, db, monkeypatch):
    monkeypatch.setitem(sys.modules, "xlrd", None)  # makes `import xlrd` fail
    res = do_ingest(run, FIXTURE_XLS, make_profile())
    assert res.outcome == "rejected" and "format_supported" in failed_names(res)
    assert "xlrd" in res.message and "E_XLS_UNSUPPORTED" in res.message


# ---- Excel / Parquet native types --------------------------------------------------------------------
def test_excel_native_dates_and_numbers(src, run, settings, db):
    rows = [[datetime.combine(d, datetime.min.time())] + r[1:] for d, r in zip(weekdays(5), ROWS)]
    p = write_xlsx(src / "native.xlsx", HEADER, rows)
    res = do_ingest(run, p, make_profile(datetime={"kind": "native", "precision": "date"}))
    assert res.outcome == "accepted", res.message
    assert canonical(settings, db, res)["session_date"][0] == date(2026, 1, 5)


def test_excel_numeric_yyyymmdd_cells(src, run, settings, db):
    rows = [[int(d.strftime("%Y%m%d"))] + r[1:] for d, r in zip(weekdays(5), ROWS)]
    p = write_xlsx(src / "yyyymmdd.xlsx", HEADER, rows)
    res = do_ingest(run, p, make_profile(datetime={"kind": "format", "format": "%Y%m%d"}))
    assert res.outcome == "accepted", res.message
    assert canonical(settings, db, res)["session_date"][1] == date(2026, 1, 6)


def test_parquet_native_types_date32_and_timestamps(src, run, settings, db):
    import pyarrow as pa

    d32 = pa.array([r[0] for r in [[d] for d in weekdays(5)]], type=pa.date32())
    cols = standard_columns(d32, [r[1:] for r in ROWS[:5]])
    p = write_parquet(src / "d32.parquet", cols)
    res = do_ingest(run, p, make_profile(profile_id="d32", datetime={"kind": "native", "precision": "date"}))
    assert res.outcome == "accepted", res.message

    times = pa.array([datetime(2026, 1, 5, 3, 45 + i, tzinfo=timezone.utc) for i in range(5)], type=pa.timestamp("ns", "UTC"))
    cols = standard_columns(times, [r[1:] for r in ROWS[:5]])
    p2 = write_parquet(src / "tz.parquet", cols)
    prof = make_profile(profile_id="tz", instrument={"timeframe": "1m"},
                        datetime={"kind": "native", "precision": "datetime", "exchange_timezone": "Asia/Kolkata"})
    res2 = do_ingest(run, p2, prof)
    assert res2.outcome == "accepted", res2.message
    c = canonical(settings, db, res2)
    assert c["timestamp_utc"][0].hour == 3 and c["session_date"][0] == date(2026, 1, 5)


def test_parquet_naive_timestamp_without_declared_zone_is_rejected(src, run, db):
    import pyarrow as pa

    times = pa.array([datetime(2026, 1, 5, 9, 15 + i) for i in range(5)], type=pa.timestamp("ns"))
    p = write_parquet(src / "naive.parquet", standard_columns(times, [r[1:] for r in ROWS[:5]]))
    res = do_ingest(run, p, make_profile(instrument={"timeframe": "1m"},
                                         datetime={"kind": "native", "precision": "datetime",
                                                   "exchange_timezone": "Asia/Kolkata"}))
    assert res.outcome == "rejected" and "timezone_declared" in failed_names(res) and "E_TZ_REQUIRED" in res.message


# ---- headered, headerless, mapping -----------------------------------------------------------------
def test_headerless_file_mapped_by_position(src, run, settings, db):
    p = write_delimited(src / "nohdr.csv", None, ROWS)
    prof = make_profile(file={"header": False},
                        columns={"date": {"position": 0}, "open": {"position": 1}, "high": {"position": 2},
                                 "low": {"position": 3}, "close": {"position": 4}},
                        volume={"rule": "use_column", "column": {"position": 5}})
    res = do_ingest(run, p, prof)
    assert res.outcome == "accepted", res.message
    assert canonical(settings, db, res)["open"][0] == ROWS[0][1]


def test_reordered_columns_different_case_and_aliases(src, run, settings, db):
    header = ["CLOSE", "Date", "Low", "OPEN", "volume", "High"]
    rows = [[r[4], r[0], r[3], r[1], r[5], r[2]] for r in ROWS]
    p = write_delimited(src / "reordered.csv", header, rows)
    prof = make_profile(columns={"date": {"name": "time", "aliases": ["date"]}, "open": {"name": "open"},
                                 "high": {"name": "high"}, "low": {"name": "low"}, "close": {"name": "close"}},
                        volume={"column": "volume"})
    res = do_ingest(run, p, prof)
    assert res.outcome == "accepted", res.message
    c = canonical(settings, db, res)
    assert c["close"][0] == ROWS[0][4] and c["high"][0] == ROWS[0][2] and c["volume"][0] == ROWS[0][5]


def test_mapping_is_recorded_in_the_attempt(src, run, db):
    p = write_delimited(src / "m.csv", HEADER, ROWS)
    res = do_ingest(run, p)
    import json

    row = db.one("SELECT * FROM ingest_attempts WHERE attempt_id=?", (res.attempt_id,))
    mapping = json.loads(row["column_mapping_json"])
    assert mapping["open"] == {"position": 1, "name": "open"}
    assert [c["name"] for c in json.loads(row["source_columns_json"])][:3] == ["time", "open", "high"]
    assert json.loads(row["datetime_rules_json"])["profile"]["kind"] == "iso"


def test_missing_required_column_lists_the_columns_found(src, run, db):
    header = ["time", "open", "high", "low", "Volume"]
    p = write_delimited(src / "nocol.csv", header, [[r[0], r[1], r[2], r[3], r[5]] for r in ROWS])
    res = do_ingest(run, p)
    assert res.outcome == "rejected" and "required_columns" in failed_names(res)
    assert "E_COLUMN_MISSING" in res.message and "'close'" in res.message and "Columns found" in res.message
    rejected_without_dataset(db, res)


def test_header_declared_but_file_has_none(src, run, db):
    p = write_delimited(src / "nohdr2.csv", None, ROWS)
    res = do_ingest(run, p)  # profile says header = true
    assert res.outcome == "rejected" and "required_columns" in failed_names(res)


def test_headerless_declared_but_file_has_a_header_is_flagged_row_by_row(src, run, db):
    p = write_delimited(src / "hdr3.csv", HEADER, ROWS)
    prof = make_profile(file={"header": False},
                        columns={"date": {"position": 0}, "open": {"position": 1}, "high": {"position": 2},
                                 "low": {"position": 3}, "close": {"position": 4}},
                        volume={"rule": "none"})
    res = do_ingest(run, p, prof)
    assert res.outcome == "rejected"
    assert {"datetime_parseable", "numeric_types"} <= failed_names(res)


def test_name_reference_in_headerless_file_is_an_error(src, run, db):
    p = write_delimited(src / "hdr4.csv", None, ROWS)
    res = do_ingest(run, p, make_profile(file={"header": False}))
    assert res.outcome == "rejected" and "no header" in res.message


def test_column_position_out_of_range(src, run, db):
    p = write_delimited(src / "pos.csv", None, ROWS)
    prof = make_profile(file={"header": False},
                        columns={"date": {"position": 0}, "open": {"position": 1}, "high": {"position": 2},
                                 "low": {"position": 3}, "close": {"position": 40}}, volume={"rule": "none"})
    res = do_ingest(run, p, prof)
    assert res.outcome == "rejected" and "does not exist" in res.message


def test_unmapped_columns_are_preserved_but_are_not_quant_inputs(src, run, settings, db):
    from qmap.storage.parquet_io import read_canonical_metadata

    header = HEADER + ["Comment", "Open Interest"]
    rows = [r + ["note", 7] for r in ROWS]
    p = write_delimited(src / "extra.csv", header, rows)
    res = do_ingest(run, p)
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["x_comment"][0] == "note" and g["x_open_interest"][0] == "7"
    path = settings.data_path(db.one("SELECT relative_path FROM datasets WHERE dataset_id=?", (res.dataset_ids[0],))[0])
    meta = read_canonical_metadata(path)
    assert "x_comment" in meta["preserved_columns_are_not_quant_inputs"]
    assert not {"x_comment", "x_open_interest"} & set(meta["quant_columns"])


def test_keep_unmapped_false_drops_only_unused_columns_but_keeps_volume(src, run, settings, db):
    p = write_delimited(src / "extra2.csv", HEADER + ["Comment"], [r + ["n"] for r in ROWS])
    res = do_ingest(run, p, make_profile(keep_unmapped=False))
    g = read_group(settings, db, res.dataset_ids[0])
    assert "x_comment" not in g and "x_volume" in g


# ---- text details --------------------------------------------------------------------------------------
def test_semicolon_delimiter_with_decimal_comma_and_thousands(src, run, settings, db):
    rows = [[r[0], f"{r[1]:.2f}".replace(".", ","), f"{r[2]:.2f}".replace(".", ","), f"{r[3]:.2f}".replace(".", ","),
             f"{r[4]:.2f}".replace(".", ","), f"{r[5]:,}".replace(",", ".")] for r in ROWS]
    p = write_delimited(src / "eu.csv", HEADER, rows, delimiter=";")
    prof = make_profile(file={"delimiter": ";", "decimal": ",", "thousands": "."})
    res = do_ingest(run, p, prof)
    assert res.outcome == "accepted", res.message
    c = canonical(settings, db, res)
    assert c["open"][0] == pytest.approx(ROWS[0][1]) and c["volume"][0] == ROWS[0][5]


@pytest.mark.parametrize("kw", [{"bom": True}, {"newline": "\n"}, {"final_newline": False}, {"newline": "\r"}])
def test_bom_line_endings_and_missing_final_newline_are_accepted(kw, src, run, settings, db):
    p = write_delimited(src / "variant.csv", HEADER, ROWS, **kw)
    res = do_ingest(run, p)
    assert res.outcome == "accepted", res.message
    assert len(canonical(settings, db, res)["open"]) == 10


def test_utf16_file(src, run, db):
    p = src / "u16.csv"
    text = "\r\n".join([",".join(HEADER)] + [",".join(str(x) for x in r) for r in ROWS]) + "\r\n"
    p.write_bytes(text.encode("utf-16"))
    assert do_ingest(run, p).outcome == "accepted"


def test_cp1252_needs_the_declared_encoding_and_a_wrong_one_is_an_error(src, run, db):
    header = ["time", "open", "high", "low", "close", "Volume", "Comment"]
    p = write_delimited(src / "cp.csv", header, [r + ["café ₹"[:4]] for r in ROWS], encoding="cp1252")
    res = do_ingest(run, p)  # profile default utf-8
    assert res.outcome == "rejected" and "E_ENCODING" in res.message
    res2 = do_ingest(run, p, make_profile(profile_id="cp", file={"encoding": "cp1252"}))
    assert res2.outcome == "accepted", res2.message


def test_blank_lines_are_not_rows_and_are_recorded(src, run, settings, db):
    p = src / "blank.csv"
    lines = [",".join(HEADER)] + [",".join(str(x) for x in r) for r in ROWS]
    lines.insert(3, "")
    lines.append("")
    p.write_bytes(("\r\n".join(lines) + "\r\n").encode())
    res = do_ingest(run, p)
    assert res.outcome == "accepted"
    import json

    notes = json.loads(db.one("SELECT transformations_json FROM ingest_attempts")[0])
    assert {"step": "blank_lines_skipped", "count": 2, "detail": "completely blank lines are not data rows and are not counted as rows"} in notes


def test_skip_rows_preamble(src, run, db):
    p = src / "pre.csv"
    p.write_bytes(("Exported by vendor\r\n\r\n" + ",".join(HEADER) + "\r\n"
                   + "\r\n".join(",".join(str(x) for x in r) for r in ROWS) + "\r\n").encode())
    assert do_ingest(run, p, make_profile(file={"skip_rows": 1})).outcome == "accepted"


# ---- malformed input -------------------------------------------------------------------------------------
def test_ragged_rows_are_listed_and_never_dropped(src, run, db):
    p = src / "ragged.csv"
    lines = [",".join(HEADER)] + [",".join(str(x) for x in r) for r in ROWS]
    lines[3] = lines[3] + ",extra"
    lines[5] = ",".join(lines[5].split(",")[:4])
    p.write_bytes(("\r\n".join(lines) + "\r\n").encode())
    res = do_ingest(run, p)
    assert res.outcome == "rejected" and "E_RAGGED_ROWS" in res.message and "line 4" in res.message and "line 6" in res.message
    rejected_without_dataset(db, res)


def test_unclosed_quote(src, run, db):
    p = src / "quote.csv"
    p.write_bytes((",".join(HEADER) + '\r\n2026-01-05,"100,101,99,100,5\r\n').encode())
    res = do_ingest(run, p)
    assert res.outcome == "rejected" and "E_MALFORMED" in res.message


def test_non_numeric_price_is_reported_with_its_row(src, run, db):
    rows = [list(r) for r in ROWS]
    rows[2][4] = "N/A"
    p = write_delimited(src / "na.csv", HEADER, rows)
    res = do_ingest(run, p)
    assert res.outcome == "rejected" and "numeric_types" in failed_names(res)
    report = Path(res.issues_report).read_text()
    assert "numeric_types" in report and ",3," in report  # source row 3


def test_header_only_file_is_rejected_as_empty(src, run, db):
    p = write_delimited(src / "hdronly.csv", HEADER, [])
    res = do_ingest(run, p)
    assert res.outcome == "rejected" and "not_empty" in failed_names(res)


def test_empty_file_is_unsupported_and_recorded(src, run, db):
    p = src / "empty.csv"
    p.write_bytes(b"")
    res = do_ingest(run, p)
    assert res.outcome == "unsupported"
    assert db.one("SELECT status FROM ingest_events")["status"] == "unsupported"


def test_truncated_parquet_is_rejected_with_a_clear_error(src, run, db):
    p = write_parquet(src / "t.parquet", standard_columns([r[0] for r in ROWS], [r[1:] for r in ROWS]))
    p.write_bytes(p.read_bytes()[:-40])
    res = do_ingest(run, p)
    assert res.outcome == "rejected" and "E_MALFORMED" in res.message
    assert db.one("SELECT file_format FROM datasets WHERE layer='raw'")["file_format"] == "parquet"  # original preserved


def test_corrupt_xlsx_is_unsupported(src, run, db):
    p = write_xlsx(src / "c.xlsx", HEADER, ROWS)
    p.write_bytes(p.read_bytes()[:300])
    assert do_ingest(run, p).outcome == "unsupported"


@pytest.mark.parametrize("name,payload", [("a.json", b'{"x": 1}'), ("a.pdf", b"%PDF-1.4 ..."),
                                          ("a.bin", bytes(range(256)) * 10)])
def test_unsupported_formats_are_reported_not_skipped(name, payload, src, run, db):
    p = src / name
    p.write_bytes(payload)
    res = do_ingest(run, p)
    assert res.outcome == "unsupported" and res.message
    ev = db.one("SELECT * FROM ingest_events")
    assert ev["status"] == "unsupported" and ev["detail"] == res.message


def test_zip_archive_and_macro_workbook_are_unsupported(src, run):
    z = src / "arch.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.csv", "x")
    assert do_ingest(run, z).outcome == "unsupported"


def test_multi_sheet_workbook_needs_a_declared_sheet(src, run, settings, db):
    p = write_xlsx(src / "multi.xlsx", HEADER, ROWS, sheet="Prices", extra_sheets={"Notes": [["hello"], ["world"]]})
    res = do_ingest(run, p)
    assert res.outcome == "rejected" and "E_SHEET_REQUIRED" in res.message
    res2 = do_ingest(run, p, make_profile(profile_id="named", file={"sheet": "Prices"}))
    assert res2.outcome == "accepted", res2.message
    res3 = do_ingest(run, p, make_profile(profile_id="byindex", file={"sheet": 0}))
    assert res3.outcome == "accepted", res3.message  # a different profile id is a different processing version
    res4 = do_ingest(run, p, make_profile(profile_id="nosuch", file={"sheet": "Nope"}))
    assert res4.outcome == "rejected" and "E_SHEET_NOT_FOUND" in res4.message


def test_extension_mismatch_is_read_by_content_with_a_warning(src, run, db):
    p = write_xlsx(src / "really_excel.csv", HEADER, ROWS)
    res = do_ingest(run, p)
    assert res.outcome == "accepted"
    chk = [c for c in res.checks if c.name == "extension_matches_content"][0]
    assert not chk.passed and chk.severity == "warning"
    assert db.one("SELECT extension_matches FROM ingest_attempts")["extension_matches"] == 0


def test_expected_format_in_profile_must_match(src, run, db):
    p = write_delimited(src / "e.csv", HEADER, ROWS)
    res = do_ingest(run, p, make_profile(file={"expected_format": "parquet"}))
    assert res.outcome == "rejected" and "E_FORMAT_MISMATCH" in res.message


# ---- original preserved + lineage ---------------------------------------------------------------------
def test_original_is_untouched_raw_is_registered_and_cleaned_links_to_it(src, run, settings, db):
    p = write_delimited(src / "orig.csv", HEADER, ROWS)
    before = sha256_file(p)
    res = do_ingest(run, p)
    assert sha256_file(p) == before
    raw = db.one("SELECT * FROM datasets WHERE layer='raw'")
    cleaned = db.one("SELECT * FROM datasets WHERE layer='cleaned'")
    assert raw["sha256"] == before and cleaned["parent_dataset_id"] == raw["dataset_id"]
    assert cleaned["created_by_attempt_id"] == res.attempt_id
    assert cleaned["processing_version"] == f"test_profile@1+{CLEANING_CODE_VERSION}" and cleaned["row_count"] == 10
    assert (cleaned["date_from"], cleaned["date_to"]) == ("2026-01-05", "2026-01-16")
    assert db.one("SELECT run_id FROM run_inputs")["run_id"] == run.run_id


def test_quant_reader_excludes_preserved_columns(src, run, settings, db):
    from qmap.data_engine import canonical as C
    from qmap.storage.parquet_io import read_quant_columns

    p = write_delimited(src / "q.csv", HEADER + ["Comment", "Net Volume"], [r + ["n", 5] for r in ROWS])
    res = do_ingest(run, p, make_profile(volume={"preserved_not_volume": ["Net Volume"]}))
    path = settings.data_path(db.one("SELECT relative_path FROM datasets WHERE dataset_id=?", (res.dataset_ids[0],))[0])
    full = read_group(settings, db, res.dataset_ids[0])
    assert "x_comment" in full and "x_net_volume" in full
    assert read_quant_columns(path).column_names == list(C.CORE_COLUMNS)
