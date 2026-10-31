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
