"""Configuration and path management.

Settings come from a TOML file (read with the standard library) plus environment
variables. No path is ever hard-coded. The code folder, Q-MAP_DATA and Q-MAP_OUTPUT
must be separate, non-overlapping locations.
"""

from __future__ import annotations

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
    def cleaned_dir(self) -> Path:
        return self.data_root / "Cleaned_Data"

    @property
    def cleaned_incoming_dir(self) -> Path:
        return self.cleaned_dir / "_incoming"

    @property
    def logs_dir(self) -> Path:
        return self.output_root / "Logs"

    def data_path(self, relative_path: str) -> Path:
        """Absolute path of a registry path (stored relative to the data root, using '/')."""
        return self.data_root.joinpath(*relative_path.split("/"))

    def to_relative(self, absolute: Path) -> str:
        return absolute.resolve().relative_to(self.data_root).as_posix()


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

    paths = cfg.get("paths", {})
    data_raw = env.get(ENV_DATA_ROOT) or paths.get("data_root")
    out_raw = env.get(ENV_OUTPUT_ROOT) or paths.get("output_root")
    for label, value, key in (("Q-MAP_DATA", data_raw, "data_root"), ("Q-MAP_OUTPUT", out_raw, "output_root")):
        if not value or str(value).startswith("<"):
            raise ConfigError(f"{label} location is not set.",
                              action=f"Set [paths] {key} in your local configuration file "
                                     f"(or the environment variable {ENV_DATA_ROOT if key == 'data_root' else ENV_OUTPUT_ROOT}).")
    code = Path(code_root).resolve() if code_root else _default_code_root()
    data_root = Path(data_raw).expanduser().resolve()
    output_root = Path(out_raw).expanduser().resolve()
    validate_roots(data_root, output_root, code)

    val = cfg.get("validation", {})
    files = cfg.get("files", {})
    rec = cfg.get("recovery", {})
    profile_dirs = [code / "Configuration" / "source_profiles"]
    if files.get("profiles_dir"):
        profile_dirs.append(Path(files["profiles_dir"]).expanduser().resolve())

    req_sets = {k: dict(v) for k, v in DEFAULT_REQUIREMENT_SETS.items()}
    for name, body in cfg.get("requirement_sets", {}).items():
        req_sets[name] = {"require_volume": bool(body.get("require_volume", False))}

    settings = Settings(
        data_root=data_root,
        output_root=output_root,
        code_root=code,
        profile_dirs=tuple(profile_dirs),
        log_level=str(cfg.get("logging", {}).get("level", "INFO")).upper(),
        stale_minutes=int(rec.get("stale_minutes", 60)),
        max_file_size_mb=int(files.get("max_file_size_mb", 1024)),
        plausible_min_date=_parse_date(val.get("plausible_min_date", "01-Jan-1990"), "plausible_min_date"),
        plausible_max_days_ahead=int(val.get("plausible_max_days_ahead", 1)),
        max_daily_move_pct=float(val.get("max_daily_move_pct", 25.0)),
        max_gap_days=int(val.get("max_gap_days", 7)),
        min_rows=int(val.get("min_rows", 1)),
        requirement_sets=req_sets,
    )
    if create_layout:
        ensure_layout(settings)
    return settings
