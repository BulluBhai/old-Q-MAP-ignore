"""File-handling primitives: hashing, durable copy, atomic replace, read-only flag.

Everything here uses pathlib and os.replace, which behave the same on Windows,
macOS and Linux. Temporary files are always created on the same volume as their
destination so the final rename is atomic.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import uuid
from pathlib import Path

_CHUNK = 1024 * 1024


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fsync_path(path: str | Path) -> None:
    fd = os.open(path, os.O_RDWR if os.name == "nt" else os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def copy_durably(src: Path, dest_tmp: Path) -> None:
    """Copy src to dest_tmp (never touching src) and flush it to disk."""
    dest_tmp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest_tmp)
    fsync_path(dest_tmp)


def make_read_only(path: Path) -> None:
    mode = os.stat(path).st_mode
    os.chmod(path, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def is_read_only(path: Path) -> bool:
    return not (os.stat(path).st_mode & stat.S_IWUSR)


def unique_tmp_name(suffix: str = ".tmp") -> str:
    return f"{uuid.uuid4().hex}{suffix}"


def atomic_write_bytes(path: Path, data: bytes, tmp_dir: Path | None = None) -> None:
    """Write data to a temp file, flush, then atomically move it into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = (tmp_dir or path.parent) / f".{path.name}.{uuid.uuid4().hex}.tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def safe_remove(path: Path) -> bool:
    """Remove a file if present, clearing the read-only flag first (needed on Windows)."""
    try:
        if path.exists():
            os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR)
            path.unlink()
            return True
    except OSError:
        return False
    return False
