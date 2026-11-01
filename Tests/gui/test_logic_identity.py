"""Window logic (no tkinter) for exchange/symbol identity: early, plain-English problems; where the profile takes the
identity from; and making a copy of a file-name profile that asks for exchange and symbol. Synthetic data only."""

from pathlib import Path

from gui.conftest import NET_HEADER, REPO, dd_mm_yy_rows
from fixtures.builders import write_delimited
from qmap.data_engine.profiles import load_profile
from qmap_gui import services

EXAMPLES = REPO / "Configuration" / "source_profiles"


def ex(name):
    return load_profile(EXAMPLES / f"{name}.toml")


def test_invalid_typed_codes_are_reported_before_anything_runs():
    p = ex("example_text_headered_iso_date")
    problems = services.request_problems(p, "NSE 1", "NIFTY 50", "")
    assert any("'NSE 1' is not valid" in x for x in problems) and any("'NIFTY 50' is not valid" in x for x in problems)
    assert services.request_problems(p, "nse", "nifty", "") == []  # lower case is normalised by the Foundation


def test_a_file_name_that_does_not_fit_the_profile_pattern_is_noted_before_anything_runs():
    p = ex("example_csv_dd_mm_yy")
    notes = services.file_name_notes(p, [Path("D:/x/NSE_NIFTY, 1(1).csv"), Path("D:/x/NSE_NIFTY_1D.csv")])
    assert len(notes) == 1 and "'NSE_NIFTY, 1(1).csv' does not fit" in notes[0] and "Copy so it asks me" in notes[0]
    assert services.file_name_notes(p, [Path("D:/x/NSE_NIFTY_1D.csv")]) == []
    assert services.request_problems(p, "", "", "") == []  # a note, not a block: other files can still go ahead


def test_the_note_says_where_the_profile_takes_the_identity_from():
    note = services.identity_note(ex("example_csv_dd_mm_yy"))
    assert "Exchange: read from the file name (pattern ^(?P<exchange>" in note and "Timeframe: fixed in the profile (1D)" in note
    assert "Copy so it asks me for exchange and symbol" in note
    note = services.identity_note(ex("example_parquet_naive_timestamp"))
    assert "Exchange: typed by you below" in note and "Copy so it asks me" not in note


def test_a_copy_that_asks_for_exchange_and_symbol_changes_only_that(tmp_path):
    src = EXAMPLES / "example_csv_iso_offset.toml"
    before = src.read_bytes()
    path = services.copy_profile_asking_for_identity(src, "my_iso_csv", tmp_path)
    new, old = load_profile(path), load_profile(src)
    assert src.read_bytes() == before and path.parent == tmp_path  # the example is never edited
    assert (new.profile_id, new.profile_version) == ("my_iso_csv", 1)
    assert (new.instrument.exchange_from, new.instrument.symbol_from) == ("ingest", "ingest")
    assert not services.reads_identity_from_filename(new) and services.reads_identity_from_filename(old)
    for attr in ("file", "columns", "datetime", "volume", "requirement_set"):
        assert getattr(new, attr) == getattr(old, attr)
    assert new.instrument.timeframe == old.instrument.timeframe


def test_the_copy_loads_a_file_whose_name_the_original_cannot_read(tmp_path, world):
    settings = services.build_core_settings(str(world.data), str(world.output), REPO, world.settings)
    f = write_delimited(world.src / "csv headers std.csv", NET_HEADER, dd_mm_yy_rows())
    original = ex("example_csv_dd_mm_yy")
    assert services.check_file(f, original, settings).outcome == "would_be_rejected"
    copy = load_profile(services.copy_profile_asking_for_identity(EXAMPLES / "example_csv_dd_mm_yy.toml", "mine", tmp_path))
    report = services.check_file(f, copy, settings, {"exchange": "NSE", "symbol": "NIFTY"})
    assert report.outcome == "would_be_accepted", [x.text() for x in report.errors]


def test_a_copy_name_that_is_taken_or_invalid_is_refused(tmp_path):
    src = EXAMPLES / "example_csv_iso_offset.toml"
    services.copy_profile_asking_for_identity(src, "taken", tmp_path)
    for name in ("taken", "has space"):
        try:
            services.copy_profile_asking_for_identity(src, name, tmp_path)
        except services.GuiError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"{name!r} should be refused")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["taken.toml"]  # no stray temporary file
