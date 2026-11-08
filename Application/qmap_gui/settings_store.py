"""Remembered GUI choices (the two data/output folders and a few conveniences), stored OUTSIDE the code repository."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path

SETTINGS_FILE = "gui_settings.json"
ENV_SETTINGS_DIR = "QMAP_GUI_SETTINGS_DIR"


class StoreError(Exception):
    """Plain-English problem with where settings would be stored."""


def default_settings_dir(env=None, platform: str | None = None) -> Path:
    env = os.environ if env is None else env
    platform = platform or sys.platform
    if env.get(ENV_SETTINGS_DIR):
        return Path(env[ENV_SETTINGS_DIR]).expanduser()
    if platform.startswith("win"):
        base = env.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Q-MAP"
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Q-MAP"
    return Path(env.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "q-map"


@dataclass
class GuiSettings:
    data_root: str = ""
    output_root: str = ""
    last_input_dir: str = ""
    last_profile: str = ""
    source_label: str = ""


class GuiSettingsStore:
    """Reads and writes gui_settings.json. Refuses to live inside the code repository."""

    def __init__(self, directory: str | Path, code_root: str | Path):
        self.directory = Path(directory).expanduser().resolve()
        code = Path(code_root).resolve()
        if self.directory == code or code in self.directory.parents:
            raise StoreError(f"Q-MAP's remembered settings cannot be kept inside the code folder ({self.directory}). "
                             "Choose a settings folder outside the Q-MAP code repository.")
        self.path = self.directory / SETTINGS_FILE
        self.profiles_dir = self.directory / "profiles"
        self.load_warning: str | None = None

    def load(self) -> GuiSettings:
        self.load_warning = None
        if not self.path.is_file():
            return GuiSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            names = {f.name for f in fields(GuiSettings)}
            return GuiSettings(**{k: str(v) for k, v in raw.items() if k in names})
        except (OSError, ValueError, TypeError) as exc:
            self.load_warning = (f"Your remembered settings file could not be read ({exc}); starting with empty "
                                 "choices. Nothing else is affected.")
            return GuiSettings()

    def save(self, settings: GuiSettings) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.directory, prefix=".gui_settings_", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(settings), fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except OSError as exc:
            raise StoreError(f"Your choices could not be remembered because the settings file could not be written "
                             f"({self.path}): {exc}") from exc
