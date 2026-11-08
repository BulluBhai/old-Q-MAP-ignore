"""Configuration and path management.

Settings come from a TOML file (read with the standard library) plus environment
variables. No path is ever hard-coded. The code folder, Q-MAP_DATA and Q-MAP_OUTPUT
must be separate, non-overlapping locations.
"""

from __future__ import annotations

import math
import os
import tempfile
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .errors import ConfigError

ENV_CONFIG = "QMAP_CONFIG"
ENV_DATA_ROOT = "QMAP_DATA_ROOT"
ENV_OUTPUT_ROOT = "QMAP_OUTPUT_ROOT"

DEFAULT_REQUIREMENT_SETS = {
    "price_only": {"require_volume": False},
    "price_volume": {"require_volume": True},
}

DATA_SUBFOLDERS = (
    "Raw_Data/_incoming",
    "Raw_Data/_quarantine",
    "Cleaned_Data/_incoming",
    "Timeframe_Data",
    "Reference_Files",
    "Feature_Store",
    "Research_Repository",
    "Metadata",
)
OUTPUT_SUBFOLDERS = ("Logs",)


def _default_code_root() -> Path:
    # Application/qmap/core/config.py -> repository root
    return Path(__file__).resolve().parents[3]


def _parse_date(value, name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    raise ConfigError(
        f"'{name}' must be a date such as 01-Jan-1990 or 1990-01-01, got {value!r}.",
        action="Correct the value in your local configuration file.",
    )


@dataclass(frozen=True)
class Settings:
    data_root: Path
    output_root: Path
    code_root: Path
    profile_dirs: tuple[Path, ...] = ()
    log_level: str = "INFO"
    stale_minutes: int = 60
    max_file_size_mb: int = 1024
    plausible_min_date: date = date(1990, 1, 1)
    plausible_max_days_ahead: int = 1
    max_daily_move_pct: float = 25.0
    max_gap_days: int = 7
    min_rows: int = 1
    requirement_sets: dict = field(default_factory=lambda: {k: dict(v) for k, v in DEFAULT_REQUIREMENT_SETS.items()})

    # ---- derived locations -------------------------------------------------
    @property
    def db_path(self) -> Path:
        return self.data_root / "Metadata" / "qmap_metadata.sqlite"

    @property
    def raw_dir(self) -> Path:
        return self.data_root / "Raw_Data"

    @property
    def raw_incoming_dir(self) -> Path:
        return self.raw_dir / "_incoming"

    @property
    def raw_quarantine_dir(self) -> Path:
        """Corrupt stored raw copies are moved here (never deleted) when explicitly restored."""
        return self.raw_dir / "_quarantine"

    @property
    def cleaned_dir(self) -> Path:
        return self.data_root / "Cleaned_Data"

    @property
    def cleaned_incoming_dir(self) -> Path:
        return self.cleaned_dir / "_incoming"

    @property
    def logs_dir(self) -> Path:
        return self.output_root / "Logs"

    def data_path(self, relative_path: str) -> Path:
        """Absolute path of a registry path (stored relative to the data root, using '/').

        Refuses anything that could point outside Q-MAP_DATA (absolute paths, drive letters, '..', empty parts).
        """
        parts = relative_path.split("/") if isinstance(relative_path, str) else []
        if (not parts or any(p in ("", ".", "..") or "\\" in p or ":" in p for p in parts)):
            raise ValueError(f"not a valid registry path inside Q-MAP_DATA: {relative_path!r}")
        return self.data_root.joinpath(*parts)

    def to_relative(self, absolute: Path) -> str:
        return absolute.resolve().relative_to(self.data_root).as_posix()


def _resolve_folder(value, where: str, relative_to: Path | None) -> Path:
    p = Path(str(value)).expanduser()
    if not p.is_absolute():
        if relative_to is None:
            raise ConfigError(f"{where} must be a full path (for example C:/Q-MAP_DATA), got {value!r}.",
                              action="Use the complete folder path, including the drive letter on Windows.")
        p = relative_to / p
    return p.resolve()


def _number(section: dict, key: str, default, kind, *, minimum):
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (kind is int and isinstance(value, float)
                                                                            and not value.is_integer()):
        raise ConfigError(f"'{key}' must be a {'whole ' if kind is int else ''}number, got {value!r}.",
                          action="Correct the value in your local configuration file (no quotes around numbers).")
    if not math.isfinite(value):  # TOML allows nan, inf and -inf; none is a usable limit (nan disables comparisons)
        raise ConfigError(f"'{key}' must be a finite number, got {value!r}.",
                          action=f"Replace it with an ordinary number in your local configuration file "
                                 f"(the default is {default}); nan, inf and -inf are not allowed.")
    value = kind(value)
    if value < minimum:
        raise ConfigError(f"'{key}' must be {minimum} or more, got {value!r}.",
                          action="Correct the value in your local configuration file.")
    return value


def _check_writable(folder: Path, label: str) -> None:
    try:
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".qmap_write_test_", delete=True):
            pass
    except OSError as exc:
        raise ConfigError(
            f"{label} folder is not writable: {folder} ({exc}).",
            action="Choose a folder you can write to.",
        ) from exc


def _is_inside(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def validate_roots(data_root: Path, output_root: Path, code_root: Path) -> None:
    for label, root in (("Q-MAP_DATA", data_root), ("Q-MAP_OUTPUT", output_root)):
        if not root.is_dir():
            raise ConfigError(
                f"{label} folder does not exist: {root}.",
                action="Create the folder first (Q-MAP never creates a root folder, so a typing mistake cannot go unnoticed).",
            )
        _check_writable(root, label)
        if _is_inside(root, code_root):
            raise ConfigError(
                f"{label} folder is inside the code folder: {root}.",
                action="Choose a location outside the Q-MAP code repository.",
            )
        if _is_inside(code_root, root):
            raise ConfigError(
                f"The code folder is inside the {label} folder: {root}.",
                action="Choose a location that does not contain the code repository.",
            )
    if _is_inside(data_root, output_root) or _is_inside(output_root, data_root):
        raise ConfigError(
            "Q-MAP_DATA and Q-MAP_OUTPUT overlap.",
            action="Choose two separate folders that are not inside each other.",
        )


def ensure_layout(settings: Settings) -> None:
    """Create the standard sub-folders under the two roots (idempotent)."""
    for sub in DATA_SUBFOLDERS:
        (settings.data_root / sub).mkdir(parents=True, exist_ok=True)
    for sub in OUTPUT_SUBFOLDERS:
        (settings.output_root / sub).mkdir(parents=True, exist_ok=True)


def load_settings(config_path: str | os.PathLike | None = None, *, env=None,
                  code_root: str | os.PathLike | None = None, create_layout: bool = True) -> Settings:
    """Build and validate Settings. Precedence: environment variables, local file, defaults."""
    env = os.environ if env is None else env
    cfg: dict = {}
    path = config_path or env.get(ENV_CONFIG)
    if path:
        path = Path(path)
        if not path.is_file():
            raise ConfigError(f"Configuration file not found: {path}.",
                              action="Check the path, or copy Configuration/qmap.example.toml and fill it in.")
        try:
            with open(path, "rb") as fh:
                cfg = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Configuration file is not valid TOML: {exc}.", action="Fix the syntax error.") from exc

    # A relative folder in the configuration file means "relative to that file", never to the folder Q-MAP
    # happens to be started from (IDLE, a shortcut or a terminal can each start in a different folder).
    cfg_dir = Path(path).resolve().parent if path else None
    paths = cfg.get("paths", {})
    resolved = {}
    for label, key, env_name in (("Q-MAP_DATA", "data_root", ENV_DATA_ROOT), ("Q-MAP_OUTPUT", "output_root", ENV_OUTPUT_ROOT)):
        from_env = env.get(env_name)
        value = from_env or paths.get(key)
        if not value or str(value).startswith("<"):
            raise ConfigError(f"{label} location is not set.",
                              action=f"Set [paths] {key} in your local configuration file (or the environment variable {env_name}).")
        resolved[key] = _resolve_folder(value, f"the environment variable {env_name}" if from_env else f"[paths] {key}",
                                        None if from_env else cfg_dir)
    code = Path(code_root).resolve() if code_root else _default_code_root()
    data_root, output_root = resolved["data_root"], resolved["output_root"]
    validate_roots(data_root, output_root, code)

    val = cfg.get("validation", {})
    files = cfg.get("files", {})
    rec = cfg.get("recovery", {})
    profile_dirs = [code / "Configuration" / "source_profiles"]
    if files.get("profiles_dir"):
        profile_dirs.append(_resolve_folder(files["profiles_dir"], "[files] profiles_dir", cfg_dir))

    req_sets = {k: dict(v) for k, v in DEFAULT_REQUIREMENT_SETS.items()}
    for name, body in cfg.get("requirement_sets", {}).items():
        req_sets[name] = {"require_volume": bool(body.get("require_volume", False))}

    settings = Settings(
        data_root=data_root,
        output_root=output_root,
        code_root=code,
        profile_dirs=tuple(profile_dirs),
        log_level=str(cfg.get("logging", {}).get("level", "INFO")).upper(),
        stale_minutes=_number(rec, "stale_minutes", 60, int, minimum=1),
        max_file_size_mb=_number(files, "max_file_size_mb", 1024, int, minimum=1),
        plausible_min_date=_parse_date(val.get("plausible_min_date", "01-Jan-1990"), "plausible_min_date"),
        plausible_max_days_ahead=_number(val, "plausible_max_days_ahead", 1, int, minimum=0),
        max_daily_move_pct=_number(val, "max_daily_move_pct", 25.0, float, minimum=0),
        max_gap_days=_number(val, "max_gap_days", 7, int, minimum=1),
        min_rows=_number(val, "min_rows", 1, int, minimum=1),
        requirement_sets=req_sets,
    )
    if create_layout:
        ensure_layout(settings)
    return settings
