import pytest

from fixtures.profiles import make_profile, profile_text
from qmap.core.errors import IngestError, ProfileError
from qmap.data_engine.profiles import (check_profile_against_settings, find_profile, load_profile,
                                       parse_profile, processing_version, register_profile_snapshot)


def test_default_profile_parses():
    p = make_profile()
    assert p.profile_id == "test_profile" and p.profile_version == 1 and p.volume.rule == "use_column"
    assert p.columns["date"].name == "time" and p.file.header is True


def test_header_must_be_stated():
    with pytest.raises(ProfileError, match="header"):
        parse_profile(profile_text(file={"header": None}).replace("[file]\n", "[file]\n"))


@pytest.mark.parametrize("override,message", [
    ({"profile_id": "bad id"}, "profile_id"),
    ({"profile_id": "a@b"}, "profile_id"),
    ({"profile_id": "a+b"}, "profile_id"),
    ({"profile_version": 0}, "profile_version"),
    ({"profile_version": "1"}, "profile_version"),
    ({"instrument": {"timeframe": "2D"}}, "timeframe"),
    ({"instrument": {"timeframe": None}}, "timeframe"),
    ({"instrument": {"exchange_from": "fixed", "exchange": None}}, "exchange"),
    ({"instrument": {"symbol_from": "column"}}, "symbol_column"),
    ({"instrument": {"symbol_from": "filename_pattern"}}, "filename_pattern"),
    ({"instrument": {"symbol_from": "guess"}}, "symbol_from"),
    ({"datetime": {"kind": "magic"}}, "kind"),
    ({"datetime": {"kind": "format"}}, "format"),
    ({"datetime": {"kind": "format", "format": "%d-%m-%y"}}, "two_digit_year_pivot"),
    ({"datetime": {"kind": "iso", "format": "%Y"}}, "only used with kind"),
    ({"datetime": {"kind": "native"}}, "precision"),
    ({"datetime": {"kind": "iso", "timezone": "Mars/Phobos"}}, "time zone"),
    ({"datetime": {"kind": "iso", "two_digit_year_pivot": 150}}, "two_digit_year_pivot"),
    ({"volume": {"rule": "magic"}}, "rule"),
    ({"volume": {"rule": "use_column", "column": None}}, "column"),
    ({"volume": {"rule": "sum_columns", "columns": ["a", "b"]}}, "justification"),
    ({"volume": {"rule": "sum_columns", "columns": ["a"], "justification": "x"}}, "at least two"),
    ({"volume": {"requirement_set": None}}, "requirement_set"),
    ({"volume": {"rule": "none", "verify_identical": ["a"]}}, "verify_identical"),
    ({"order": {"on_unsorted": "ignore"}}, "on_unsorted"),
    ({"file": {"expected_format": "docx"}}, "expected_format"),
    ({"file": {"delimiter": ";;"}}, "delimiter"),
    ({"columns": {"date": {"name": "time"}, "open": {"name": "o"}, "high": {"name": "h"}, "low": {"name": "l"}}},
     "close"),
    ({"columns": {"date": {"name": "t", "position": 0}, "open": {"name": "o"}, "high": {"name": "h"},
                  "low": {"name": "l"}, "close": {"name": "c"}}}, "exactly one"),
    ({"columns": {"date": {"name": "t"}, "open": {"name": "o"}, "high": {"name": "h"}, "low": {"name": "l"},
                  "close": {"name": "c"}, "volume": {"name": "v"}}}, "unknown canonical"),
])
def test_invalid_profiles_are_rejected_with_a_clear_message(override, message):
    with pytest.raises(ProfileError, match=message):
        make_profile(**override)


def test_sum_columns_with_justification_is_valid():
    p = make_profile(volume={"rule": "sum_columns", "columns": ["BuyVol", "SellVol"],
                             "justification": "Vendor documentation: total = buy + sell", "column": None})
    assert p.volume.rule == "sum_columns" and len(p.volume.columns) == 2


def test_time_column_requires_time_format_and_vice_versa():
    cols = {"date": {"name": "d"}, "time": {"name": "t"}, "open": {"name": "o"}, "high": {"name": "h"},
            "low": {"name": "l"}, "close": {"name": "c"}}
    with pytest.raises(ProfileError, match="time_format"):
        make_profile(columns=cols)
    assert make_profile(columns=cols, datetime={"kind": "iso", "time_format": "%H:%M"}).datetime.time_format == "%H:%M"
    with pytest.raises(ProfileError, match="no \\[columns\\] time column"):
        make_profile(datetime={"kind": "iso", "time_format": "%H:%M"})


def test_invalid_toml_and_missing_file(tmp_path):
    with pytest.raises(ProfileError, match="not valid TOML"):
        parse_profile("profile_id = ")
    with pytest.raises(ProfileError, match="not found"):
        load_profile(tmp_path / "nope.toml")


def test_requirement_set_must_exist(settings):
    p = make_profile(volume={"requirement_set": "does_not_exist"})
    with pytest.raises(ProfileError, match="does_not_exist"):
        check_profile_against_settings(p, settings)
    check_profile_against_settings(make_profile(), settings)


def test_processing_version_format():
    assert processing_version(make_profile(), "c1") == "test_profile@1+c1"


def test_find_profile_by_id_and_by_path(settings, tmp_path):
    folder = settings.profile_dirs[0]
    folder.mkdir(parents=True)
    (folder / "test_profile.toml").write_text(profile_text())
    assert find_profile(settings, "test_profile").profile_id == "test_profile"
    other = tmp_path / "x.toml"
    other.write_text(profile_text(profile_id="other"))
    assert find_profile(settings, str(other)).profile_id == "other"
    with pytest.raises(ProfileError, match="was not found"):
        find_profile(settings, "missing")


def test_profile_snapshot_is_stored_and_a_changed_profile_needs_a_new_version(db):
    p1 = make_profile()
    register_profile_snapshot(db, p1)
    register_profile_snapshot(db, p1)  # idempotent
    row = db.one("SELECT * FROM source_profiles WHERE profile_id='test_profile'")
    assert row["content_sha256"] == p1.content_sha256 and "profile_id" in row["content_text"]
    changed = make_profile(instrument={"symbol": "OTHER"})
    with pytest.raises(IngestError) as e:
        register_profile_snapshot(db, changed)
    assert e.value.code == "E_PROFILE_CHANGED"
    register_profile_snapshot(db, make_profile(profile_version=2, instrument={"symbol": "OTHER"}))
    assert len(db.query("SELECT * FROM source_profiles")) == 2
