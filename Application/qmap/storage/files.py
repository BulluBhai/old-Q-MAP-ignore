"""File-handling primitives: hashing, durable copy, atomic placement, read-only flag.

Temporary files are always created on the same volume as their destination so the final
rename/link is atomic. Two different placement operations exist on purpose:

* `atomic_write_bytes` (os.replace) may replace an existing file. It is used only for files the
  caller owns exclusively (for example a run's manifest).
* `place_without_overwrite` never replaces anything. It is used for every registered data file.
"""

from __future__ import annotations

import errno
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


def place_without_overwrite(tmp: Path, final: Path) -> None:
    """Move `tmp` to `final` atomically, failing with FileExistsError if `final` already exists.

    The existence check and the placement are ONE operating-system call, so another process can never slip
    a file in between (there is no "check, then replace" window):
    * Windows: os.rename (MoveFileExW without MOVEFILE_REPLACE_EXISTING) refuses an existing target.
    * macOS/Linux: os.link refuses an existing target; the temporary name is then removed. If the volume
      does not support hard links, an exclusive create (O_CREAT | O_EXCL) claims the name first and the
      file is then moved onto that claim, which no other Q-MAP writer can take.
    A crash between the two steps of the POSIX paths leaves `tmp` behind, which recovery removes.
    """
    if os.name == "nt":
        os.rename(tmp, final)
        return
    try:
        os.link(tmp, final)
    except FileExistsError:
        raise
    except OSError as exc:
        if exc.errno not in (errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.EMLINK, errno.ENOSYS):
            raise
        fd = os.open(final, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)  # raises FileExistsError if taken
        os.close(fd)
        os.replace(tmp, final)  # replaces only our own empty claim
        return
    os.unlink(tmp)


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
