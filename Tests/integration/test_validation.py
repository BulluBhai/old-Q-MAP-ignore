"""Data correctness: OHLC rules, non-finite values, duplicates, ordering, reporting. Nothing is repaired or dropped."""

import csv
import json
from datetime import date

import pytest

from fixtures.builders import HEADER, daily_rows, intraday_utc, write_delimited
from fixtures.profiles import do_ingest, failed_names, make_profile, read_group
from qmap.storage.files import sha256_file

ROWS = daily_rows(8)


def with_row(index, **cols):
    """ROWS with one row's cells replaced. cols: open/high/low/close/volume."""
    idx = {"open": 1, "high": 2, "low": 3, "close": 4, "volume": 5}
    rows = [list(r) for r in ROWS]
    for k, v in cols.items():
        rows[index][idx[k]] = v
    return rows


def ingest_rows(src, run, rows, name="v.csv", profile=None):
    return do_ingest(run, write_delimited(src / name, HEADER, rows), profile)


def issue_rows(res):
    with open(res.issues_report, newline="") as fh:
        return list(csv.DictReader(fh))


def assert_rejected_cleanly(db, res, expected_check):
    assert res.outcome == "rejected" and expected_check in failed_names(res), res.message
    assert not db.query("SELECT 1 FROM datasets WHERE layer='cleaned'")  # nothing registered
    assert db.one("SELECT outcome FROM ingest_attempts WHERE attempt_id=?", (res.attempt_id,))["outcome"] == "rejected"
    stored = {r["check_name"]: r for r in db.query("SELECT * FROM quality_checks WHERE attempt_id=?", (res.attempt_id,))}
    assert expected_check in stored and stored[expected_check]["passed"] == 0 and stored[expected_check]["rows_failed"] >= 1


# ---- the five separate OHLC / value rules, one invalid record each ----------------------------------------
@pytest.mark.parametrize("label,cells,check", [
    ("low above open", dict(open=100, high=105, low=101, close=104), "low_le_open_close"),
    ("low above close", dict(open=105, high=106, low=102, close=100), "low_le_open_close"),
    ("high below open", dict(open=105, high=104, low=99, close=100), "high_ge_open_close"),
    ("high below close", dict(open=100, high=104, low=99, close=105), "high_ge_open_close"),
    ("low above high", dict(open=100, high=99, low=101, close=100), "low_le_high"),
    ("zero price", dict(open=0, high=105, low=0, close=100), "prices_positive"),
    ("negative price", dict(open=100, high=105, low=-5, close=100), "prices_positive"),
    ("negative volume", dict(volume=-1), "volume_non_negative"),
])
def test_each_rule_rejects_a_record_that_breaks_it(label, cells, check, src, run, db):
    res = ingest_rows(src, run, with_row(3, **cells))
    assert_rejected_cleanly(db, res, check)
    reported = [r for r in issue_rows(res) if r["check"] == check]
    assert [r["source_row"] for r in reported] == ["4"]  # the 4th data row, 1-based


@pytest.mark.parametrize("cells,expected_only", [
    (dict(open=100, high=105, low=101, close=104), {"low_le_open_close"}),
    (dict(open=105, high=104, low=99, close=100), {"high_ge_open_close"}),
    (dict(volume=-1), {"volume_non_negative"}),
])
def test_a_single_defect_fails_only_the_matching_check(cells, expected_only, src, run, db):
    res = ingest_rows(src, run, with_row(2, **cells))
    assert failed_names(res) == expected_only


def test_equal_values_are_valid_boundaries(src, run, settings, db):
    rows = with_row(0, open=100, high=100, low=100, close=100)
    rows[1][1:5] = [100, 105, 100, 105]  # low == open, close == high
    res = ingest_rows(src, run, rows)
    assert res.outcome == "accepted", res.message
    for name in ("low_le_open_close", "high_ge_open_close", "low_le_high", "prices_positive"):
        assert [c for c in res.checks if c.name == name][0].passed


def test_multiple_violations_report_every_row_and_the_count(src, run, db):
    rows = with_row(1, low=500)
    rows[5][3] = 600
    rows[6][3] = 700
    res = ingest_rows(src, run, rows)
    chk = [c for c in res.checks if c.name == "low_le_open_close"][0]
    assert chk.rows_failed == 3 and "source rows 2, 6, 7" in chk.detail
    assert [r["source_row"] for r in issue_rows(res) if r["check"] == "low_le_open_close"] == ["2", "6", "7"]


# ---- non-finite and unreadable numbers -----------------------------------------------------------------------
@pytest.mark.parametrize("token", ["", "  ", "nan", "NaN", "inf", "-inf", "Infinity"])
def test_blank_nan_and_infinite_prices_are_rejected_as_missing_or_non_finite(token, src, run, db):
    res = ingest_rows(src, run, with_row(2, close=token))
    assert_rejected_cleanly(db, res, "no_missing_values")
    assert "numeric_types" not in failed_names(res)  # a readable token is not a text error


@pytest.mark.parametrize("token", ["N/A", "abc", "1,5", "12abc", "--5", "0x10", "1e"])
def test_unreadable_price_text_is_a_numeric_error_and_not_double_counted(token, src, run, db):
    res = ingest_rows(src, run, with_row(2, open=token))
    assert_rejected_cleanly(db, res, "numeric_types")
    assert "no_missing_values" not in failed_names(res)


def test_non_finite_numbers_inside_excel_and_parquet_cells(src, run, db):
    import math

    from fixtures.builders import standard_columns, write_parquet

    rows = [list(r) for r in ROWS]
    rows[2][4] = math.nan
    rows[3][2] = math.inf
    px = write_parquet(src / "nf.parquet", standard_columns([r[0] for r in ROWS], [r[1:] for r in rows]))
    res = do_ingest(run, px)
    assert res.outcome == "rejected" and "no_missing_values" in failed_names(res)
    assert [c for c in res.checks if c.name == "no_missing_values"][0].rows_failed >= 2


# ---- timestamps: duplicates and order ------------------------------------------------------------------------
def test_conflicting_observations_are_kept_flagged_and_warned_never_rejected(src, run, settings, db):
    """DQ-10 (03-Nov-26): same timestamp, different values -> both rows kept, flagged, WARNING; not rejected."""
    rows = [list(r) for r in ROWS]
    rows[4][0] = rows[3][0]
    res = ingest_rows(src, run, rows)
    assert res.outcome == "accepted", res.message
    assert [r["source_row"] for r in issue_rows(res) if r["check"] == "conflicting_observations"] == ["4", "5"]
    chk = [c for c in res.checks if c.name == "conflicting_observations"][0]
    assert chk.severity == "warning" and not chk.passed and chk.rows_failed == 2 and "not chosen" in chk.detail
    assert [c for c in res.checks if c.name == "row_accounting"][0].passed  # all rows accounted for
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["src_row"] == [1, 2, 3, 4, 5, 6, 7, 8]  # both observations, in source order
    assert [bool(f & 32) for f in g["quality_flags"]] == [False, False, False, True, True, False, False, False]
    assert g["open"][3:5] == [rows[3][1], rows[4][1]]  # the values of both, unchanged


def test_exact_duplicate_rows_are_removed_from_the_copy_and_recorded(src, run, settings, db):
    rows = [list(r) for r in ROWS]
    rows.insert(5, list(rows[4]))  # source row 6 repeats source row 5 in every column
    p = write_delimited(src / "dups.csv", HEADER, rows)
    before = sha256_file(p)
    res = do_ingest(run, p)
    assert res.outcome == "accepted", res.message
    assert sha256_file(p) == before  # the source file is never modified
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["src_row"] == [1, 2, 3, 4, 5, 7, 8, 9] and not any(f & 32 for f in g["quality_flags"])
    chk = [c for c in res.checks if c.name == "exact_duplicates_removed"][0]
    assert chk.severity == "info" and chk.rows_failed == 1
    assert [r["source_row"] for r in issue_rows(res) if r["check"] == "exact_duplicates_removed"] == ["6"]
    notes = json.loads(db.one("SELECT transformations_json FROM ingest_attempts")[0])
    step = next(n for n in notes if n["step"] == "exact_duplicates_removed")
    assert step["count"] == 1 and step["removed_source_row_and_kept_source_row"] == [[6, 5]]
    assert db.one("SELECT row_count FROM datasets WHERE layer='cleaned'")[0] == 8
    assert [c for c in res.checks if c.name == "row_accounting"][0].passed


def test_a_row_differing_only_in_volume_or_an_extra_column_is_a_conflict_not_a_duplicate(src, run, settings, db):
    rows = [list(r) + ["a"] for r in ROWS]
    rows.insert(3, list(rows[2]))
    rows[3][5] += 1  # volume differs
    rows.insert(6, list(rows[5]))
    rows[6][6] = "b"  # only the extra column differs
    res = do_ingest(run, write_delimited(src / "v.csv", HEADER + ["note"], rows))
    assert res.outcome == "accepted", res.message
    g = read_group(settings, db, res.dataset_ids[0])
    assert len(g["src_row"]) == 10 and sum(bool(f & 32) for f in g["quality_flags"]) == 4
    detail = [c for c in res.checks if c.name == "conflicting_observations"][0].detail
    assert "volume" in detail and "note" in detail


def test_unsorted_rows_are_warned_sorted_in_the_copy_and_keep_their_source_position(src, run, settings, db):
    rows = [list(r) for r in ROWS]
    rows[2], rows[5] = rows[5], rows[2]
    p = write_delimited(src / "unsorted.csv", HEADER, rows)
    before = sha256_file(p)
    res = do_ingest(run, p)
    assert res.outcome == "accepted", res.message
    assert sha256_file(p) == before  # source untouched
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["session_date"] == sorted(g["session_date"])  # documented rule: ascending
    assert g["src_row"] == [1, 2, 6, 4, 5, 3, 7, 8]  # original positions retained
    assert [bool(f & 8) for f in g["quality_flags"]] == [False, False, True, False, False, True, False, False]
    assert g["open"][2] == rows[5][1]  # data moved with its row
    chk = [c for c in res.checks if c.name == "source_order"][0]
    assert chk.severity == "warning" and not chk.passed
    notes = json.loads(db.one("SELECT transformations_json FROM ingest_attempts")[0])
    assert any(n["step"] == "sorted_by_time" and n["rows_moved"] == 2 for n in notes)
    assert db.one("SELECT row_count FROM datasets WHERE layer='cleaned'")[0] == 8  # nothing dropped


def test_unsorted_source_can_be_made_an_error_by_the_profile(src, run, db):
    rows = [list(r) for r in ROWS]
    rows[1], rows[2] = rows[2], rows[1]
    res = ingest_rows(src, run, rows, profile=make_profile(order={"on_unsorted": "error"}))
    assert_rejected_cleanly(db, res, "source_order")


def test_unsorted_and_conflicting_rows_are_sorted_and_both_kept_in_source_order(src, run, settings, db):
    rows = [list(r) for r in ROWS]
    rows[1], rows[5] = rows[5], rows[1]
    rows[6][0] = rows[0][0]
    res = ingest_rows(src, run, rows)
    assert res.outcome == "accepted", res.message
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["src_row"][:2] == [1, 7] and g["session_date"] == sorted(g["session_date"])


def test_intraday_sorting_uses_the_utc_instant(src, run, settings, db):
    times = intraday_utc(6)
    rows = [[t.isoformat().replace("+00:00", "Z"), 100 + i, 101 + i, 99 + i, 100 + i, 10] for i, t in enumerate(times)]
    rows[0], rows[3] = rows[3], rows[0]
    p = write_delimited(src / "intra.csv", HEADER, rows)
    prof = make_profile(instrument={"timeframe": "1m"}, datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, p, prof)
    assert res.outcome == "accepted", res.message
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["timestamp_utc"] == sorted(g["timestamp_utc"]) and g["src_row"][0] == 4


# ---- completeness and reporting ---------------------------------------------------------------------------
def test_every_source_row_appears_once_in_the_output(src, run, settings, db):
    res = do_ingest(run, write_delimited(src / "all.csv", HEADER, ROWS))
    g = read_group(settings, db, res.dataset_ids[0])
    assert sorted(g["src_row"]) == list(range(1, 9))
    assert [c for c in res.checks if c.name == "row_accounting"][0].passed
    a = db.one("SELECT rows_read, rows_accepted, rows_flagged FROM ingest_attempts")
    assert (a["rows_read"], a["rows_accepted"], a["rows_flagged"]) == (8, 8, 0)


def test_rejected_attempt_records_row_counts_and_a_full_report(src, run, db):
    rows = with_row(0, low=500)
    rows[2][3] = 500
    res = ingest_rows(src, run, rows)
    a = db.one("SELECT * FROM ingest_attempts WHERE attempt_id=?", (res.attempt_id,))
    assert (a["rows_read"], a["rows_flagged"], a["rows_accepted"]) == (8, 2, 6)
    assert a["issues_report_path"].endswith(f"issues_event{res.event_id}.csv")
    assert {r["source_row"] for r in issue_rows(res) if r["severity"] == "error"} == {"1", "3"}


def test_rejected_files_keep_the_raw_copy_and_leave_the_source_untouched(src, run, settings, db):
    p = write_delimited(src / "bad.csv", HEADER, with_row(0, low=500))
    before = sha256_file(p)
    res = do_ingest(run, p)
    assert sha256_file(p) == before
    raw = db.one("SELECT * FROM datasets WHERE layer='raw'")
    assert sha256_file(settings.data_path(raw["relative_path"])) == before
    assert res.outcome == "rejected"


def test_the_dataset_level_error_checks_are_all_stored_for_audit(src, run, db):
    res = ingest_rows(src, run, with_row(0, low=500))
    names = {r["check_name"] for r in db.query("SELECT check_name FROM quality_checks WHERE attempt_id=?", (res.attempt_id,))}
    assert {"low_le_open_close", "high_ge_open_close", "low_le_high", "prices_positive", "volume_non_negative",
            "no_missing_values", "conflicting_observations", "exact_duplicates_removed", "row_accounting",
            "not_empty"} <= names


# ---- warnings that must not reject ------------------------------------------------------------------------
def test_large_moves_gaps_and_ambiguous_dates_are_warnings_that_flag_rows(src, run, settings, db):
    rows = [list(r) for r in daily_rows(8)]
    rows[4][1:5] = [200, 201, 199, 200]  # +100% jump
    p = write_delimited(src / "w.csv", HEADER, rows)
    res = do_ingest(run, p)
    assert res.outcome == "accepted"
    large = [c for c in res.checks if c.name == "large_moves"][0]
    assert large.severity == "warning" and not large.passed
    assert read_group(settings, db, res.dataset_ids[0])["quality_flags"][4] & 4


def test_a_long_gap_in_dates_is_reported_as_a_warning(src, run, db):
    rows = daily_rows(4) + daily_rows(4, start=date(2026, 3, 2), seed=9)
    res = do_ingest(run, write_delimited(src / "gap.csv", HEADER, rows))
    assert res.outcome == "accepted"
    gap = [c for c in res.checks if c.name == "date_gaps"][0]
    assert not gap.passed and gap.severity == "warning"


def test_ddmmyy_all_days_12_or_less_is_flagged_row_by_row(src, run, settings, db):
    rows = [[f"{d:02d}-02-26"] + ohlc for d, ohlc in zip(range(1, 9), [r[1:] for r in ROWS])]
    prof = make_profile(datetime={"kind": "format", "format": "%d-%m-%y", "two_digit_year_pivot": 69})
    res = do_ingest(run, write_delimited(src / "dm.csv", HEADER, rows), prof)
    assert res.outcome == "accepted", res.message
    chk = [c for c in res.checks if c.name == "date_order_unverified"][0]
    assert chk.severity == "warning" and not chk.passed
    flags = read_group(settings, db, res.dataset_ids[0])["quality_flags"]
    assert sum(1 for f in flags if f & 2) == 7  # 02-02-26 reads the same either way; the other 7 fit both orders
    assert not flags[1] & 2  # the row dated 02-02-26 is not ambiguous


def test_intraday_partial_sessions_and_wrong_timeframe_are_warnings(src, run, db):
    times = intraday_utc(375 * 2 + 120)  # two full sessions and a partial third
    rows = [[t.isoformat().replace("+00:00", "Z"), 100, 101, 99, 100, 10] for t in times]
    p = write_delimited(src / "sess.csv", HEADER, rows)
    prof = make_profile(instrument={"timeframe": "1m"}, datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, p, prof)
    assert res.outcome == "accepted", res.message
    partial = [c for c in res.checks if c.name == "partial_session"][0]
    assert not partial.passed and "120/375" in partial.detail
    prof5 = make_profile(profile_id="five", instrument={"timeframe": "5m"},
                         datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res5 = do_ingest(run, p, prof5)
    spacing = [c for c in res5.checks if c.name == "timeframe_spacing"][0]
    assert not spacing.passed and "5m" in spacing.detail


def test_plausible_range_error_for_a_wrong_century_is_reported(src, run, db):
    rows = [list(r) for r in ROWS]
    rows[0][0] = "1970-01-01"
    res = ingest_rows(src, run, rows)
    assert_rejected_cleanly(db, res, "date_in_range")


def test_true_false_cells_in_a_price_column_are_not_numbers(src, run, db):
    from fixtures.builders import write_xlsx

    rows = [list(r) for r in ROWS]
    rows[2][4] = True
    res = do_ingest(run, write_xlsx(src / "bool.xlsx", HEADER, rows))
    assert_rejected_cleanly(db, res, "numeric_types")
    assert "no_missing_values" not in failed_names(res)
