"""The source-profile library follows the naming standard (requirement 6) without changing how files are read.

Standard: docs/standards/Q-MAP_Naming_and_Reference_Conventions.md, section C.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

import pytest

from qmap.data_engine.profiles import PROFILE_STATUSES, find_profile, load_profile, resolve_legacy_id

REPO = Path(__file__).resolve().parents[2]
LIBRARY = REPO / "Configuration" / "source_profiles"
EVIDENCE = REPO / "docs" / "sample_file_testing" / "evidence_01_Nov_26" / "profiles_used"
STANDARD_DOC = REPO / "docs" / "standards" / "Q-MAP_Naming_and_Reference_Conventions.md"

FORMATS = {"csv": "CSV", "txt": "TXT", "xlsx": "XLSX", "parquet": "Parquet"}
STRUCTURES = {"hdr": "Headered", "nohdr": "Headerless"}
DATETIMES = ("ddmmyy", "isodate", "isodt", "unixs", "xldate", "naivedt")
QUALIFIERS = ("dupvol", "idfromname")
ID_RULE = re.compile(rf"^({'|'.join(FORMATS)})_({'|'.join(STRUCTURES)})_({'|'.join(DATETIMES)})(_({'|'.join(QUALIFIERS)}))*$")
# every profile name shipped before the standard, with the profile that now carries it
OLD_LIBRARY = {"example_csv_dd_mm_yy": "csv_hdr_ddmmyy_idfromname", "example_csv_iso_offset": "csv_hdr_isodt_idfromname",
               "example_csv_unix_seconds": "csv_hdr_unixs_idfromname", "example_csv_noheaders_iso_offset": "csv_nohdr_isodt",
               "example_csv_noheaders_unix_seconds": "csv_nohdr_unixs", "example_parquet_naive_timestamp": "parquet_hdr_naivedt",
               "example_text_headered_iso_date": "txt_hdr_isodate",
               "example_text_headerless_seven_columns": "txt_nohdr_isodate_dupvol",
               "example_xlsx_headers_iso_offset": "xlsx_hdr_isodt", "example_xlsx_headers_native_date": "xlsx_hdr_xldate",
               "example_xlsx_noheaders_iso_offset": "xlsx_nohdr_isodt"}
READING = ("file", "instrument", "columns", "datetime", "volume", "requirement_set", "on_unsorted", "keep_unmapped")


def library():
    return {p.stem: load_profile(p) for p in sorted(LIBRARY.glob("*.toml"))}


def reading(profile, *, identity=True):
    d = {k: v for k, v in asdict(profile).items() if k in READING}
    if not identity:
        d.pop("instrument")
    return d


def test_ids_are_unique_follow_the_rule_and_match_the_file_name():
    lib = library()
    assert len(lib) == 14
    for stem, p in lib.items():
        assert p.profile_id == stem, stem
        assert ID_RULE.match(p.profile_id), p.profile_id
    assert len({p.profile_id for p in lib.values()}) == len(lib)


def test_display_names_say_what_the_profile_reads():
    for p in library().values():
        fmt, structure = p.profile_id.split("_")[:2]
        expected = "Parquet:" if fmt == "parquet" else f"{STRUCTURES[structure]} {FORMATS[fmt]}:"
        name = p.display_name.removeprefix("Example - ")
        assert name.startswith(expected), (p.profile_id, p.display_name)
        assert ("Net Volume" in p.display_name) == bool(p.volume.preserved_not_volume), p.profile_id
        assert (p.file.header is True) == (structure == "hdr"), p.profile_id
        timeframe_fixed = p.instrument.timeframe not in ("ingest", "filename_pattern")
        if timeframe_fixed:  # a fixed timeframe is stated in the name
            assert {"1D": "daily", "1m": "1-minute"}[p.instrument.timeframe] in p.display_name, p.profile_id


def test_standard_and_example_profiles_are_clearly_distinguished():
    lib = library()
    for p in lib.values():
        assert p.status in PROFILE_STATUSES and p.status in ("standard", "example"), p.profile_id
        if p.status == "example":
            assert p.display_name.startswith("Example - ") and p.description.startswith("EXAMPLE")
            assert p.profile_id.endswith("_idfromname")
            standard = lib[p.profile_id.removesuffix("_idfromname")]  # every example names its standard counterpart
            assert standard.status == "standard" and standard.profile_id in p.description
        else:
            assert "EXAMPLE" not in p.description and not p.display_name.startswith("Example")
            assert p.instrument.exchange_from == "ingest" and p.instrument.symbol_from == "ingest"  # never guessed


def test_examples_read_exactly_like_their_standard_profile_apart_from_identity():
    lib = library()
    for p in (x for x in lib.values() if x.status == "example"):
        assert reading(p, identity=False) == reading(lib[p.profile_id.removesuffix("_idfromname")], identity=False)
        assert p.instrument.exchange_from == "filename_pattern"


def test_standard_profiles_read_exactly_like_the_verified_sample_file_profiles():
    """The verified copies used for the owner's 11 sample files (PR #3) are the reference for how files are read."""
    lib = library()
    checked = 0
    for p in lib.values():
        for old in p.legacy_ids:
            evidence = EVIDENCE / f"{old}.toml"
            if evidence.is_file():
                assert reading(load_profile(evidence)) == reading(p), (p.profile_id, old)
                checked += 1
    assert checked == 11  # every one of the 11 verified layouts is covered


def test_every_earlier_name_is_still_recognised_and_belongs_to_exactly_one_profile(settings):
    from dataclasses import replace

    settings = replace(settings, profile_dirs=(LIBRARY,))  # the real library (the fixture's code folder is empty)
    lib = library()
    owners = {}
    for p in lib.values():
        for old in p.legacy_ids:
            assert old not in owners and old not in lib, old
            owners[old] = p.profile_id
    for old, new in OLD_LIBRARY.items():
        assert owners[old] == new
        assert find_profile(settings, old).profile_id == new  # e.g. a command line using the old name keeps working
    assert resolve_legacy_id(settings, "no_such_profile") is None


def test_glossary_documents_every_token_used():
    text = STANDARD_DOC.read_text(encoding="utf-8")
    for token in (*FORMATS, *STRUCTURES, *DATETIMES, *QUALIFIERS):
        assert f"`{token}`" in text, token


@pytest.mark.parametrize("doc", ["README.md", "docs/user_guides/Database_Manager_User_Guide.md",
                                 "docs/user_guides/Analytical_Workbench_User_Guide.md", "Configuration/qmap.example.toml"])
def test_user_facing_documents_do_not_use_retired_names(doc):
    text = (REPO / doc).read_text(encoding="utf-8")
    for old in OLD_LIBRARY:
        assert old not in text, (doc, old)


def test_your_own_copy_is_labelled_as_yours(settings, tmp_path):
    from qmap_gui import services

    path = services.copy_example_as(LIBRARY / "csv_hdr_ddmmyy.toml", "my_daily", tmp_path)
    mine = load_profile(path)
    assert (mine.status, mine.legacy_ids) == ("custom", ())
    assert mine.display_name.startswith("My copy: Headered CSV")
    assert reading(mine) == reading(load_profile(LIBRARY / "csv_hdr_ddmmyy.toml"))  # reading rules unchanged


def test_reloading_under_the_new_name_keeps_the_old_dataset_and_records_a_new_processing_version(run, src, db):
    """Documented compatibility behaviour: the profile name is part of a dataset's processing version (decision D2-08).
    A file loaded earlier under an OLD name and loaded again under the NEW name is processed again: the new dataset
    becomes active, the earlier one is kept (superseded, never deleted) with its original name in its history.
    The data read are identical, because the reading rules are identical."""
    from datetime import date, timedelta

    from fixtures.builders import write_delimited
    from fixtures.profiles import do_ingest
    from qmap.storage.parquet_io import read_quant_columns

    days, d = [], date(2026, 1, 5)
    while len(days) < 10:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    rows = [[x.strftime("%d-%m-%y"), 100 + i, 101 + i, 99 + i, 100.5 + i, 1000 + i, -5] for i, x in enumerate(days)]
    f = write_delimited(src / "daily.csv", ["time", "open", "high", "low", "close", "Volume", "Net Volume"], rows)
    old = do_ingest(run, f, load_profile(EVIDENCE / "csv_headers_dd_mm_yy.toml"), exchange="NSE", symbol="X", timeframe="1D")
    new = do_ingest(run, f, load_profile(LIBRARY / "csv_hdr_ddmmyy.toml"), exchange="NSE", symbol="X", timeframe="1D")
    assert old.outcome == new.outcome == "accepted"
    rows_ = {r["dataset_id"]: r for r in db.query("SELECT * FROM datasets WHERE layer = 'cleaned'")}
    o, n = rows_[old.dataset_ids[0]], rows_[new.dataset_ids[0]]
    assert o["processing_version"].startswith("csv_headers_dd_mm_yy@1") and n["processing_version"].startswith("csv_hdr_ddmmyy@1")
    assert (o["status"], o["superseded_by_dataset_id"], n["status"]) == ("superseded", n["dataset_id"], "active")
    settings = run.settings
    assert read_quant_columns(settings.data_path(o["relative_path"])).equals(
        read_quant_columns(settings.data_path(n["relative_path"])))  # identical data
