"""Which build of Q-MAP produced a run (owner instruction 03-Nov-26: two different builds must never look the same).

A version label alone is not enough: two copies of the code can carry the same `__version__`. Every run therefore
records a BUILD made of:

  version              `qmap.__version__` (the release label)
  source_fingerprint   SHA-256 over every program file of this copy (Application/**/*.py, the top-level entry-point
                       .py files and pyproject.toml), by relative path. Windows (CRLF) and Unix (LF) line endings are
                       hashed the same, so one commit gives one fingerprint on every computer. Always present.
  git_commit           the checked-out commit, when the code folder is a git checkout and git is installed; else None
  git_modified         True when tracked or new program files differ from that commit; None without git
  libraries            Python and the installed versions of the numerical and report libraries the results depend
                       on (numpy, pandas, scipy, pyarrow, openpyxl, matplotlib, reportlab); not part of the
                       fingerprint, but a reproduction states whether they differ (a library upgrade can change the
                       last digits of a result)

`build_label()` is the short text stored in the run record, e.g.
  "qmap 0.1.0rc1 / c2 build 3f9a1c0d2b7e git 9d677fb1c2a4" or "... git 9d677fb1c2a4+modified" or, for a downloaded
  copy without git, "qmap 0.1.0rc1 / c2 build 3f9a1c0d2b7e".
Computing it never stops a run: a git problem just means git_commit is None.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from .. import CLEANING_CODE_VERSION, __version__

CODE_ROOT = Path(__file__).resolve().parents[3]  # .../Q-MAP_APP (Application/qmap/core/build.py)
PROGRAM_GLOBS = ("Application/**/*.py", "*.py", "pyproject.toml")


def program_files(root: Path = CODE_ROOT) -> list[Path]:
    files = set()
    for pattern in PROGRAM_GLOBS:
        files.update(p for p in root.glob(pattern) if p.is_file() and "__pycache__" not in p.parts)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def source_fingerprint(root: Path = CODE_ROOT) -> str:
    total = hashlib.sha256()
    for p in program_files(root):
        content = p.read_bytes().replace(b"\r\n", b"\n")
        total.update(p.relative_to(root).as_posix().encode("utf-8") + b"\0")
        total.update(hashlib.sha256(content).digest())
    return total.hexdigest()


def _git(root: Path, *args: str) -> str | None:
    exe = shutil.which("git")
    if exe is None or not (root / ".git").exists():
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console window flashing up from IDLE on Windows
    try:
        done = subprocess.run([exe, "-C", str(root), *args], capture_output=True, text=True, timeout=10,
                              creationflags=flags, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def git_state(root: Path = CODE_ROOT) -> tuple[str | None, bool | None]:
    commit = _git(root, "rev-parse", "HEAD")
    if not commit:
        return None, None
    status = _git(root, "status", "--porcelain", "--untracked-files=normal", "--", "Application", "*.py",
                  "pyproject.toml")
    if status is None:
        return commit, None
    changed = [line for line in status.splitlines() if line.strip() and "__pycache__" not in line]
    return commit, bool(changed)


LIBRARIES = ("numpy", "pandas", "scipy", "pyarrow", "openpyxl", "matplotlib", "reportlab")


def library_versions() -> dict:
    """{"python": "3.12.3", "numpy": "2.1.0", ...}; a library that is not installed is recorded as None."""
    from importlib import metadata

    out = {"python": platform.python_version()}
    for name in LIBRARIES:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def build_info(root: Path = CODE_ROOT) -> dict:
    commit, modified = git_state(root)
    return {"version": __version__, "cleaning_code_version": CLEANING_CODE_VERSION,
            "source_fingerprint": source_fingerprint(root), "git_commit": commit, "git_modified": modified,
            "libraries": library_versions()}


@lru_cache(maxsize=1)
def current_build() -> dict:
    """The build of the code running now (computed once per program start)."""
    return build_info()


def build_label(info: dict | None = None) -> str:
    b = info or current_build()
    text = f"qmap {b['version']} / {b['cleaning_code_version']} build {b['source_fingerprint'][:12]}"
    if b.get("git_commit"):
        text += f" git {b['git_commit'][:12]}" + ("+modified" if b.get("git_modified") else "")
    return text
