"""Pure-logic tests (no window) for the GUI services layer, which wraps the Foundation."""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Application"))

from fixtures.builders import write_delimited
from qmap.data_engine.ingest import ingest_file
from qmap.core.runs import run_context
from qmap.storage.db import open_database
from qmap_gui import messages, services
from qmap_gui.services import GuiError

from gui.conftest import NET_HEADER, dd_mm_yy_rows


@pytest.fixture
def settings(world):
    """The Foundation's Settings with the real repository as the code folder (folders are in tmp)."""
    return services.build_core_settings(str(world.data), str(world.output), REPO, world.settings / "profiles")


def tree(path):
    return sorted(str(p.relative_to(path)) for p in path.rglob("*"))


# ---- folders ---------------------------------------------------------------------------------------------
def test_location_states(world):
    s = services.check_locations("", "", REPO)
    assert not s.overall_ok and s.data.message == "Not chosen yet."
    s = services.check_locations(str(world.data), str(world.output), REPO)
    assert s.overall_ok and s.data.ok and s.output.ok


def test_missing_folder_offers_to_create_it(world):
    s = services.check_locations(str(world.data / "later"), str(world.output), REPO)
    assert not s.data.ok and s.data.can_create and "Create folder" in s.data.message


def test_folder_inside_the_repository_is_refused(world):
    s = services.check_locations(str(REPO / "my_data"), str(world.output), REPO)
    assert not s.data.ok and "inside the code folder" in s.data.message and not s.data.can_create
    s = services.check_locations(str(world.data), str(REPO / "Application"), REPO)
    assert not s.output.ok and "inside the code folder" in s.output.message


def test_folder_that_contains_the_repository_is_refused(world):
    s = services.check_locations(str(REPO.parent), str(world.output), REPO)
    assert not s.data.ok and "code folder is inside" in s.data.message


def test_overlapping_folders_are_refused(world):
    nested = world.data / "out"
    nested.mkdir()
    s = services.check_locations(str(world.data), str(nested), REPO)
    assert not s.overall_ok and "overlap" in s.output.message
    s = services.check_locations(str(world.data), str(world.data), REPO)
    assert not s.overall_ok


def test_a_file_is_not_a_folder(world):
    s = services.check_locations(str(world.good), str(world.output), REPO)
    assert not s.data.ok and "file, not a folder" in s.data.message


def test_create_folder_applies_the_same_separation_rules(world):
    made = services.create_folder(str(world.data / "new" / "deeper"), "Q-MAP_DATA", REPO)
    assert made.is_dir()
    with pytest.raises(GuiError, match="inside the code folder"):
        services.create_folder(str(REPO / "newdata"), "Q-MAP_DATA", REPO)
    assert not (REPO / "newdata").exists()
    with pytest.raises(GuiError, match="overlap"):
        services.create_folder(str(world.data / "nested"), "Q-MAP_OUTPUT", REPO, other=str(world.data))
    assert not (world.data / "nested").exists()
    with pytest.raises(GuiError):
        services.create_folder("  ", "Q-MAP_DATA", REPO)


def test_core_settings_are_the_foundations_and_create_its_layout(settings, world):
    assert settings.data_root == world.data.resolve() and settings.code_root == REPO
    assert (world.data / "Raw_Data" / "_incoming").is_dir() and (world.output / "Logs").is_dir()
    assert str(world.settings / "profiles") in [str(p) for p in settings.profile_dirs]


def test_core_settings_refuse_unsafe_folders_in_plain_words(world):
    with pytest.raises(GuiError) as e:
        services.build_core_settings(str(REPO / "docs"), str(world.output), REPO)
    assert "E_CONFIG" not in str(e.value) and "inside the code folder" in str(e.value)


# ---- profiles ----------------------------------------------------------------------------------------------
def test_example_profiles_are_listed_and_described_in_plain_english(settings):
    infos = services.list_profiles(settings)
    ids = {i.profile.profile_id for i in infos if i.profile}
    assert {"example_csv_unix_seconds", "example_csv_iso_offset", "example_csv_dd_mm_yy", "example_text_headered_iso_date",
            "example_text_headerless_seven_columns", "example_parquet_naive_timestamp"} <= ids
    assert all(i.where == "example" and not i.problem for i in infos)
    for info in infos:
        rows = dict(services.describe_profile(info.profile))
        assert {"File type", "First row is a header", "Date / time", "Timeframe", "Volume", "Purpose"} <= set(rows)
        assert all(isinstance(v, str) and v for v in rows.values())


def test_a_broken_profile_is_listed_with_its_problem_not_hidden(settings, world):
    mine = world.settings / "profiles"
    mine.mkdir(parents=True)
    (mine / "broken.toml").write_text('profile_id = "broken"\n')
    infos = services.list_profiles(settings)
    broken = next(i for i in infos if i.path.name == "broken.toml")
    assert broken.profile is None and "profile_version" in broken.problem and broken.where == "mine"
    assert "has a problem" in broken.label


def test_profile_needs_reflect_what_the_file_cannot_provide(settings):
    by_id = {i.profile.profile_id: i.profile for i in services.list_profiles(settings)}
    n = services.profile_needs(by_id["example_text_headered_iso_date"])
    assert (n.exchange, n.symbol, n.timeframe) == (True, True, False)
    n = services.profile_needs(by_id["example_csv_unix_seconds"])
    assert (n.exchange, n.symbol, n.timeframe) == (False, False, True)
    n = services.profile_needs(by_id["example_csv_dd_mm_yy"])
    assert (n.exchange, n.symbol, n.timeframe) == (False, False, False)


def test_request_problems_are_plain(settings):
    p = {i.profile.profile_id: i.profile for i in services.list_profiles(settings)}["example_text_headered_iso_date"]
    problems = services.request_problems(p, "", "", "")
    assert len(problems) == 2 and "exchange" in problems[0] and "symbol" in problems[1]
    assert services.request_problems(p, "NSE", "NIFTY", "") == []


def test_profile_text_validation_gives_plain_messages(settings):
    good = (REPO / "Configuration/source_profiles/example_csv_dd_mm_yy.toml").read_text()
    profile, msg = services.validate_profile_text(good, settings)
    assert profile and msg == "This profile is valid."
    profile, msg = services.validate_profile_text(good.replace('format = "%d-%m-%y"', 'format = "%d-%m-%y"\nbogus'), settings)
    assert profile is None and msg
    profile, msg = services.validate_profile_text(good.replace("two_digit_year_pivot = 69", ""), settings)
    assert profile is None and "two-digit year" in msg and "E_PROFILE" not in msg
    profile, msg = services.validate_profile_text(good.replace('requirement_set = "price_only"', 'requirement_set = "nope"'), settings)
    assert profile is None and "nope" in msg


def test_copy_example_creates_an_independent_profile_outside_the_repository(settings, world):
    example = REPO / "Configuration/source_profiles/example_csv_dd_mm_yy.toml"
    before = example.read_text()
    path = services.copy_example_as(example, "my_daily", world.settings / "profiles")
    text = path.read_text()
    assert path.parent == world.settings / "profiles" and 'profile_id      = "my_daily"' in text
    assert "profile_version = 1" in text and example.read_text() == before
    with pytest.raises(GuiError, match="already have"):
        services.copy_example_as(example, "my_daily", world.settings / "profiles")
    for bad in ("", "has space", "a/b", "a@b"):
        with pytest.raises(GuiError, match="letters, digits"):
            services.copy_example_as(example, bad, world.settings / "profiles")


def test_save_user_profile_validates_and_writes_atomically(world):
    text = (REPO / "Configuration/source_profiles/example_csv_dd_mm_yy.toml").read_text().replace("example_csv_dd_mm_yy", "saved_one")
    path = services.save_user_profile(text, world.settings / "profiles")
    assert path.name == "saved_one.toml" and not [p for p in path.parent.iterdir() if p.name.endswith(".tmp")]


def test_profile_version_conflict_is_caught_before_ingest(settings, world):
    example = REPO / "Configuration/source_profiles/example_csv_dd_mm_yy.toml"
    mine = services.copy_example_as(example, "used_profile", world.settings / "profiles")
    profile = services.load_profile_file(mine, settings).profile
    assert services.profile_version_conflict(settings, profile) is None  # no database yet
    db = open_database(settings.db_path)
    with run_context(settings, db, "FOUND", area="Ingestion") as run:
        assert ingest_file(run, world.good, profile).outcome == "accepted"
    db.close()
    assert services.profile_version_conflict(settings, profile) is None  # same content: fine
    edited = mine.read_text().replace("CSV, DD-MM-YY dates", "CSV, edited")
    p2, _ = services.validate_profile_text(edited, settings)
    assert p2 is not None
    msg = services.profile_version_conflict(settings, p2)
    assert msg and "profile_version" in msg


# ---- check (dry run) and preview: nothing is saved --------------------------------------------------------
def profile(settings, name="example_csv_dd_mm_yy"):
    return next(i.profile for i in services.list_profiles(settings) if i.profile and i.profile.profile_id == name)


def test_check_accepts_a_good_file_and_saves_nothing(settings, world):
    before = (tree(world.data), tree(world.output))
    report = services.check_file(world.good, profile(settings), settings)
    assert report.outcome == "would_be_accepted" and report.rows_read == 12 and not report.errors
    assert (tree(world.data), tree(world.output)) == before  # no registry, no raw copy, no run folder


def test_check_explains_problems_in_plain_english_with_rows(settings, world):
    report = services.check_file(world.bad, profile(settings), settings)
    assert report.outcome == "would_be_rejected"
    titles = {f.title for f in report.errors}
    assert "A price or volume is not a number" in titles and "Low price is higher than High" in titles
    text = "\n".join(f.text() for f in report.findings)
    assert "What to do:" in text and "source rows" in text and "[E_" not in text


def test_check_reports_unsupported_and_unreadable_files(settings, world):
    j = world.src / "x.json"
    j.write_text('{"a": 1}')
    r = services.check_file(j, profile(settings), settings)
    assert r.outcome == "unsupported" and "JSON" in r.errors[0].detail
    ragged = world.src / "ragged.csv"
    ragged.write_text("time,open,high,low,close,Volume,Net Volume\r\n01-01-26,1,2\r\n")
    r = services.check_file(ragged, profile(settings), settings)
    assert r.outcome == "unreadable" and r.errors and "[E_" not in r.errors[0].detail


def test_check_flags_an_extension_that_does_not_match(settings, world):
    odd = world.src / "NSE_NIFTY_1D1.parquet"
    odd.write_bytes(world.good.read_bytes())
    r = services.check_file(odd, profile(settings), settings)
    assert r.outcome == "would_be_accepted"
    assert any(f.check == "extension_matches_content" for f in r.warnings)


def test_preview_text_changes_nothing(settings, world):
    before = (tree(world.data), tree(world.output))
    text = services.make_preview(world.good, profile(settings), settings)
    assert "PREVIEW" in text and "WOULD BE ACCEPTED" in text
    assert (tree(world.data), tree(world.output)) == before


# ---- plain-English wording ---------------------------------------------------------------------------------
def test_every_check_the_foundation_produces_has_plain_wording(settings, world):
    names = set()
    db = open_database(settings.db_path)
    with run_context(settings, db, "FOUND", area="Ingestion") as run:
        for path in (world.good, world.bad):
            names |= {c.name for c in ingest_file(run, path, profile(settings)).checks}
        rows = dd_mm_yy_rows()
        rows[1] = rows[0]
        dup = write_delimited(world.src / "dup.csv", NET_HEADER, rows)
        names |= {c.name for c in ingest_file(run, dup, profile(settings)).checks}
    db.close()
    missing = sorted(n for n in names if n not in messages.CHECKS)
    assert not missing, f"checks without plain-English wording: {missing}"


def test_wording_never_shows_technical_codes():
    assert messages.readable("[E_COLUMN_MISSING] Column 'close' was not found. Action: Fix the column name.") == \
        "Column 'close' was not found.  What to do: Fix the column name."


def test_outcome_labels_are_plain():
    for key in ("accepted", "reused", "rejected", "blocked", "unsupported", "failed"):
        assert messages.OUTCOMES[key] and "_" not in messages.OUTCOMES[key]


# ---- opening folders ------------------------------------------------------------------------------------------
def test_opening_a_missing_path_is_reported_not_raised(tmp_path):
    ok, msg = services.open_in_file_manager(tmp_path / "nope")
    assert not ok and "does not exist" in msg


@pytest.mark.parametrize("platform,expect", [("linux", "xdg-open"), ("darwin", "open")])
def test_open_uses_the_platforms_file_manager(monkeypatch, tmp_path, platform, expect):
    calls = []
    monkeypatch.setattr(services.sys, "platform", platform)
    monkeypatch.setattr(services.subprocess, "Popen", lambda cmd, **k: calls.append(cmd))
    assert services.open_in_file_manager(tmp_path)[0] and calls == [[expect, str(tmp_path)]]


def test_open_on_windows_uses_startfile(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(services.sys, "platform", "win32")
    monkeypatch.setattr(services.os, "startfile", lambda p: calls.append(p), raising=False)
    assert services.open_in_file_manager(tmp_path)[0] and calls == [str(tmp_path)]
