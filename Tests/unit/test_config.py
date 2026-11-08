from pathlib import Path

import pytest

from qmap.core.config import load_settings
from qmap.core.errors import ConfigError


def _env(data, out):
    return {"QMAP_DATA_ROOT": str(data), "QMAP_OUTPUT_ROOT": str(out)}


def test_loads_from_environment_and_creates_layout(roots):
    s = load_settings(None, env=_env(roots["data"], roots["output"]), code_root=roots["code"])
    assert s.data_root == roots["data"].resolve()
    for sub in ("Raw_Data/_incoming", "Cleaned_Data/_incoming", "Metadata", "Feature_Store", "Research_Repository"):
        assert (roots["data"] / sub).is_dir()
    assert (roots["output"] / "Logs").is_dir()


def test_config_file_and_environment_precedence(roots, tmp_path):
    other = tmp_path / "other_data"
    other.mkdir()
    cfg = tmp_path / "qmap.local.toml"
    cfg.write_text(f'[paths]\ndata_root = "{other.as_posix()}"\noutput_root = "{roots["output"].as_posix()}"\n'
                   '[validation]\nmax_daily_move_pct = 12.5\nplausible_min_date = "01-Jan-1995"\n'
                   '[requirement_sets.price_volume_strict]\nrequire_volume = true\n')
    s = load_settings(cfg, env={}, code_root=roots["code"])
    assert s.data_root == other.resolve()
    assert s.max_daily_move_pct == 12.5
    assert s.plausible_min_date.year == 1995
    assert s.requirement_sets["price_volume_strict"]["require_volume"] is True
    # environment variable beats the file
    s2 = load_settings(cfg, env={"QMAP_DATA_ROOT": str(roots["data"])}, code_root=roots["code"])
    assert s2.data_root == roots["data"].resolve()


def test_missing_location_is_a_clear_error(roots):
    with pytest.raises(ConfigError, match="not set"):
        load_settings(None, env={}, code_root=roots["code"])
    with pytest.raises(ConfigError, match="not set"):
        load_settings(None, env={"QMAP_DATA_ROOT": "<set locally>", "QMAP_OUTPUT_ROOT": str(roots["output"])},
                      code_root=roots["code"])


def test_root_must_exist(roots, tmp_path):
    with pytest.raises(ConfigError, match="does not exist"):
        load_settings(None, env=_env(tmp_path / "nope", roots["output"]), code_root=roots["code"])


def test_roots_cannot_be_inside_code_folder(roots):
    inside = roots["code"] / "data"
    inside.mkdir()
    with pytest.raises(ConfigError, match="inside the code folder"):
        load_settings(None, env=_env(inside, roots["output"]), code_root=roots["code"])


def test_code_folder_cannot_be_inside_a_root(roots, tmp_path):
    big = tmp_path / "big"
    code = big / "code"
    code.mkdir(parents=True)
    with pytest.raises(ConfigError, match="inside the"):
        load_settings(None, env=_env(big, roots["output"]), code_root=code)


def test_data_and_output_must_not_overlap(roots):
    nested = roots["data"] / "out"
    nested.mkdir()
    with pytest.raises(ConfigError, match="overlap"):
        load_settings(None, env=_env(roots["data"], nested), code_root=roots["code"])
    with pytest.raises(ConfigError, match="overlap"):
        load_settings(None, env=_env(roots["data"], roots["data"]), code_root=roots["code"])


def test_bad_config_file(roots, tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("[paths\n")
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_settings(bad, env={}, code_root=roots["code"])
    with pytest.raises(ConfigError, match="not found"):
        load_settings(tmp_path / "missing.toml", env={}, code_root=roots["code"])


def test_registry_paths_are_relative_to_data_root(settings):
    p = settings.data_path("Raw_Data/ab/abc.txt")
    assert p == settings.data_root / "Raw_Data" / "ab" / "abc.txt"
    assert settings.to_relative(p) == "Raw_Data/ab/abc.txt"
    assert isinstance(settings.db_path, Path)


# ---- numeric settings: finite values only (independent review of PR #1, 08-Nov-26) ------------------------------
def _load_with(roots, tmp_path, validation_lines: str, name: str = "qmap.local.toml"):
    cfg = tmp_path / name
    cfg.write_text(f'[paths]\ndata_root = "{roots["data"].as_posix()}"\noutput_root = "{roots["output"].as_posix()}"\n'
                   f"[validation]\n{validation_lines}\n")
    return load_settings(cfg, env={}, code_root=roots["code"])


@pytest.mark.parametrize("literal", ["nan", "inf", "-inf", "+inf", "+nan", "-nan"])
def test_non_finite_max_daily_move_pct_is_rejected_when_the_toml_file_is_loaded(roots, tmp_path, literal):
    # nan would make every "move > limit" comparison False and silently switch off the large-move warning
    with pytest.raises(ConfigError, match="'max_daily_move_pct' must be a finite number") as info:
        _load_with(roots, tmp_path, f"max_daily_move_pct = {literal}")
    assert "nan, inf and -inf are not allowed" in info.value.action


@pytest.mark.parametrize("key", ["plausible_max_days_ahead", "max_gap_days", "min_rows"])
@pytest.mark.parametrize("literal", ["nan", "inf", "-inf"])
def test_non_finite_values_are_rejected_for_whole_number_settings_too(roots, tmp_path, key, literal):
    with pytest.raises(ConfigError, match=f"'{key}' must be a "):
        _load_with(roots, tmp_path, f"{key} = {literal}")


def test_valid_finite_values_load_exactly_as_before(roots, tmp_path):
    s = _load_with(roots, tmp_path, "max_daily_move_pct = 12.5\nmax_gap_days = 10\nmin_rows = 3\n"
                                    "plausible_max_days_ahead = 0")
    assert (s.max_daily_move_pct, s.max_gap_days, s.min_rows, s.plausible_max_days_ahead) == (12.5, 10, 3, 0)
    assert isinstance(s.max_daily_move_pct, float) and isinstance(s.max_gap_days, int)
    s_int = _load_with(roots, tmp_path, "max_daily_move_pct = 40", name="int_value.toml")  # an integer literal is fine
    assert s_int.max_daily_move_pct == 40.0 and isinstance(s_int.max_daily_move_pct, float)
    s_zero = _load_with(roots, tmp_path, "max_daily_move_pct = 0.0", name="zero.toml")  # the minimum itself is allowed
    assert s_zero.max_daily_move_pct == 0.0
    s_default = load_settings(None, env=_env(roots["data"], roots["output"]), code_root=roots["code"])
    assert (s_default.max_daily_move_pct, s_default.max_gap_days, s_default.min_rows) == (25.0, 7, 1)


@pytest.mark.parametrize("line, message", [
    ("max_daily_move_pct = -0.5", "'max_daily_move_pct' must be 0 or more"),
    ("min_rows = 0", "'min_rows' must be 1 or more"),
    ("max_gap_days = 2.5", "'max_gap_days' must be a whole number"),
    ('max_daily_move_pct = "25"', "'max_daily_move_pct' must be a number"),
    ("max_daily_move_pct = true", "'max_daily_move_pct' must be a number"),
])
def test_existing_minimum_and_type_checks_are_unchanged(roots, tmp_path, line, message):
    with pytest.raises(ConfigError, match=message):
        _load_with(roots, tmp_path, line)
