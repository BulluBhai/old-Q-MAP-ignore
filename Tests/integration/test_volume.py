"""Volume: absent, single, duplicated, split, ambiguous. Nothing added, discarded or equated without a rule."""

import json

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest, failed_names, make_profile, read_group

ROWS = daily_rows(8)
NO_VOL_HEADER = ["time", "open", "high", "low", "close"]
NO_VOL_ROWS = [r[:5] for r in ROWS]
NONE_RULE = {"rule": "none", "column": None}


def accepted(res):
    assert res.outcome == "accepted", res.message
    return res


def attempt(db, res):
    return db.one("SELECT * FROM ingest_attempts WHERE attempt_id=?", (res.attempt_id,))


def dataset(db, res):
    return db.one("SELECT * FROM datasets WHERE dataset_id=?", (res.dataset_ids[0],))


# ---- absent -----------------------------------------------------------------------------------------
def test_missing_volume_does_not_invalidate_price_data(src, run, settings, db):
    p = write_delimited(src / "novol.csv", NO_VOL_HEADER, NO_VOL_ROWS)
    res = accepted(do_ingest(run, p, make_profile(volume=NONE_RULE)))
    assert dataset(db, res)["volume_status"] == "absent"
    g = read_group(settings, db, res.dataset_ids[0])
    assert all(v is None for v in g["volume"])  # empty (null), never zero
    assert all(f == 0 for f in g["quality_flags"])  # no per-row noise when the whole field is absent
    chk = {c.name: c for c in res.checks}
    assert chk["volume_required"].passed and chk["volume_required"].severity == "info"
    assert "volume_non_negative" not in chk and "zero_volume_bars" not in chk  # not applicable without volume
    prov = json.loads(attempt(db, res)["field_provenance_json"])
    assert prov["volume"]["status"] == "absent"


def test_absent_volume_is_rejected_only_when_the_requirement_set_needs_it(src, run, db):
    p = write_delimited(src / "novol2.csv", NO_VOL_HEADER, NO_VOL_ROWS)
    res = do_ingest(run, p, make_profile(volume={"rule": "none", "column": None, "requirement_set": "price_volume"}))
    assert res.outcome == "rejected" and "volume_required" in failed_names(res)


# ---- single column ------------------------------------------------------------------------------------
def test_single_volume_column_is_mapped_and_preserved(src, run, settings, db):
    p = write_delimited(src / "vol.csv", HEADER, ROWS)
    res = accepted(do_ingest(run, p))
    assert dataset(db, res)["volume_status"] == "mapped"
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["volume"][0] == ROWS[0][5] and g["x_volume"][0] == str(ROWS[0][5])  # original field preserved


def test_blank_volume_cells_are_flagged_and_only_fail_when_volume_is_required(src, run, settings, db):
    rows = [list(r) for r in ROWS]
    rows[2][5] = ""
    rows[4][5] = "  "
    p = write_delimited(src / "gaps.csv", HEADER, rows)
    res = accepted(do_ingest(run, p))
    g = read_group(settings, db, res.dataset_ids[0])
    assert [bool(f & 1) for f in g["quality_flags"]] == [False, False, True, False, True, False, False, False]
    assert g["volume"][2] is None
    res2 = do_ingest(run, p, make_profile(profile_id="strict", volume={"requirement_set": "price_volume"}))
    assert res2.outcome == "rejected" and "volume_required" in failed_names(res2)
    assert [c for c in res2.checks if c.name == "volume_required"][0].rows_failed == 2


def test_zero_volume_is_valid_and_reported_as_info(src, run, db):
    rows = [list(r) for r in ROWS]
    rows[1][5] = 0
    res = accepted(do_ingest(run, write_delimited(src / "zero.csv", HEADER, rows)))
    chk = [c for c in res.checks if c.name == "zero_volume_bars"][0]
    assert chk.severity == "info" and chk.rows_failed == 1


@pytest.mark.parametrize("bad,check", [("-5", "volume_non_negative"), ("abc", "numeric_types"),
                                       ("inf", "numeric_types"), ("N/A", "numeric_types")])
def test_invalid_volume_values_are_rejected(bad, check, src, run, db):
    rows = [list(r) for r in ROWS]
    rows[3][5] = bad
    res = do_ingest(run, write_delimited(src / "badvol.csv", HEADER, rows))
    assert res.outcome == "rejected" and check in failed_names(res)


def test_constant_volume_is_a_warning_not_an_error(src, run, db):
    rows = [list(r[:5]) + [38948210] for r in ROWS]
    res = accepted(do_ingest(run, write_delimited(src / "const.csv", HEADER, rows)))
    chk = [c for c in res.checks if c.name == "constant_volume"][0]
    assert chk.severity == "warning" and not chk.passed and "placeholder" in chk.detail


# ---- duplicated columns ---------------------------------------------------------------------------------
DUP_HEADER = ["time", "open", "high", "low", "close", "Volume", "Volume"]


def dup_rows(differ=False):
    return [list(r) + [r[5] + (1 if differ and i == 2 else 0)] for i, r in enumerate(ROWS)]


def test_ambiguous_duplicate_name_is_an_error_not_a_guess(src, run, db):
    p = write_delimited(src / "dup.csv", DUP_HEADER, dup_rows())
    res = do_ingest(run, p)  # column = "Volume" matches two columns
    assert res.outcome == "rejected" and "E_COLUMN_AMBIGUOUS" in res.message and "Volume#1" in res.message


def test_identical_duplicates_are_accepted_only_when_verified(src, run, settings, db):
    p = write_delimited(src / "dup2.csv", DUP_HEADER, dup_rows())
    prof = make_profile(volume={"column": "Volume#1", "verify_identical": ["Volume#2"]})
    res = accepted(do_ingest(run, p, prof))
    prov = json.loads(attempt(db, res)["volume_rule_json"])
    assert prov["verified_identical_to"] == [{"position": 6, "name": "Volume", "rows_differing": 0}]
    g = read_group(settings, db, res.dataset_ids[0])
    assert "x_volume" in g and "x_volume_2" in g  # both original fields preserved
    assert g["volume"][0] == ROWS[0][5]  # counted once - not doubled


def test_differing_duplicates_are_never_merged_or_equated(src, run, db):
    p = write_delimited(src / "dup3.csv", DUP_HEADER, dup_rows(differ=True))
    prof = make_profile(volume={"column": "Volume#1", "verify_identical": ["Volume#2"]})
    res = do_ingest(run, p, prof)
    assert res.outcome == "rejected" and "volume_mapping_resolved" in failed_names(res)
    assert "not merged automatically" in open(res.issues_report).read()


def test_duplicate_by_position(src, run, settings, db):
    p = write_delimited(src / "dup4.csv", DUP_HEADER, dup_rows())
    res = accepted(do_ingest(run, p, make_profile(volume={"column": {"position": 6}})))
    assert read_group(settings, db, res.dataset_ids[0])["volume"][1] == ROWS[1][5]


# ---- split volume --------------------------------------------------------------------------------------
SPLIT_HEADER = ["time", "open", "high", "low", "close", "BuyVolume", "SellVolume"]


def split_rows():
    return [r[:5] + [r[5] // 2, r[5] - r[5] // 2] for r in ROWS]


def test_split_volume_is_summed_only_with_a_justification_and_recorded(src, run, settings, db):
    p = write_delimited(src / "split.csv", SPLIT_HEADER, split_rows())
    prof = make_profile(volume={"rule": "sum_columns", "column": None, "columns": ["BuyVolume", "SellVolume"],
                                "justification": "Vendor documentation: total volume = buy + sell"})
    res = accepted(do_ingest(run, p, prof))
    assert dataset(db, res)["volume_status"] == "derived_sum"
    assert read_group(settings, db, res.dataset_ids[0])["volume"][0] == ROWS[0][5]
    prov = json.loads(attempt(db, res)["volume_rule_json"])
    assert prov["justification"].startswith("Vendor documentation") and len(prov["source_columns"]) == 2
    g = read_group(settings, db, res.dataset_ids[0])
    assert "x_buyvolume" in g and "x_sellvolume" in g


def test_sum_with_a_missing_part_is_missing_not_a_partial_sum(src, run, settings, db):
    rows = split_rows()
    rows[2][6] = ""
    p = write_delimited(src / "split2.csv", SPLIT_HEADER, rows)
    prof = make_profile(volume={"rule": "sum_columns", "column": None, "columns": ["BuyVolume", "SellVolume"],
                                "justification": "x"})
    res = accepted(do_ingest(run, p, prof))
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["volume"][2] is None and g["quality_flags"][2] & 1


# ---- Net Volume style extra volume-like column -----------------------------------------------------------
NET_HEADER = HEADER + ["Net Volume"]


def net_rows():
    return [list(r) + [(-1) ** i * (r[5] // 3)] for i, r in enumerate(ROWS)]


def test_net_volume_is_never_added_to_or_used_as_volume(src, run, settings, db):
    p = write_delimited(src / "net.csv", NET_HEADER, net_rows())
    res = accepted(do_ingest(run, p, make_profile(volume={"preserved_not_volume": ["Net Volume"]})))
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["volume"][0] == ROWS[0][5] and g["x_net_volume"][0] == str(net_rows()[0][6])
    assert [c for c in res.checks if c.name == "volume_columns_ignored"][0].passed  # acknowledged in the profile


def test_unacknowledged_volume_like_column_raises_a_warning(src, run, db):
    p = write_delimited(src / "net2.csv", NET_HEADER, net_rows())
    res = accepted(do_ingest(run, p))
    chk = [c for c in res.checks if c.name == "volume_columns_ignored"][0]
    assert chk.severity == "warning" and not chk.passed and "Net Volume" in chk.detail


def test_rule_none_with_a_volume_column_present_warns_and_preserves_it(src, run, settings, db):
    p = write_delimited(src / "none_but.csv", HEADER, ROWS)
    res = accepted(do_ingest(run, p, make_profile(volume=NONE_RULE)))
    assert dataset(db, res)["volume_status"] == "absent"
    g = read_group(settings, db, res.dataset_ids[0])
    assert all(v is None for v in g["volume"]) and g["x_volume"][0] == str(ROWS[0][5])
    assert not [c for c in res.checks if c.name == "volume_columns_ignored"][0].passed


def test_missing_volume_column_named_in_the_profile_is_an_error(src, run, db):
    p = write_delimited(src / "nov3.csv", NO_VOL_HEADER, NO_VOL_ROWS)
    res = do_ingest(run, p)  # profile expects a Volume column
    assert res.outcome == "rejected" and "volume_mapping_resolved" in failed_names(res)


def test_non_volume_columns_are_never_treated_as_volume(src, run, settings, db):
    header = HEADER[:5] + ["Turnover"]
    p = write_delimited(src / "turn.csv", header, [r[:5] + [123] for r in ROWS])
    res = accepted(do_ingest(run, p, make_profile(volume=NONE_RULE)))
    assert all(v is None for v in read_group(settings, db, res.dataset_ids[0])["volume"])
