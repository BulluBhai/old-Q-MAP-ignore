"""Data-root containment (review of 04-Nov-26, item B3).

A registry path is resolved (symbolic links and Windows junctions followed) and must stay inside the resolved
Q-MAP_DATA root. Deletion never follows, changes or removes a link, and recovery never reaches outside the data
root through one. Link tests run where the operating system lets the test create the link; junction tests run on
Windows (CI) only.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from qmap.core.config import UnsafeDataPath
from qmap.storage.files import is_link, safe_remove
from qmap.storage.recovery import _files_under, recover_incomplete, verify_registry


def _symlink(link: Path, target: Path, *, directory: bool):
    try:
        os.symlink(target, link, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:  # Windows without the privilege to create symbolic links
        pytest.skip(f"symbolic links cannot be created here: {exc}")


def _junction(link: Path, target: Path):
    if sys.platform != "win32":
        pytest.skip("Windows junctions exist only on Windows")
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


@pytest.fixture
def outside(tmp_path):
    d = tmp_path / "outside"
    d.mkdir()
    victim = d / "victim.csv"
    victim.write_text("not Q-MAP's file")
    os.chmod(victim, stat.S_IREAD)
    yield d
    os.chmod(victim, stat.S_IREAD | stat.S_IWRITE)


@pytest.mark.parametrize("bad", ["", "/abs", "a//b", "../x", "Raw_Data/../../x", "C:/x", "a\\b", "./a"])
def test_malformed_registry_paths_are_refused(settings, bad):
    with pytest.raises(UnsafeDataPath):
        settings.data_path(bad)
    assert issubclass(UnsafeDataPath, ValueError)  # existing callers that catch ValueError still do


def test_an_ordinary_path_inside_the_root_is_accepted(settings):
    p = settings.data_path("Raw_Data/ab/file.csv")
    assert p == settings.data_root / "Raw_Data" / "ab" / "file.csv"


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_a_folder_link_leading_outside_the_root_is_refused(settings, outside, kind):
    link = settings.data_root / "Raw_Data" / "escape"
    link.parent.mkdir(parents=True, exist_ok=True)
    (_symlink(link, outside, directory=True) if kind == "symlink" else _junction(link, outside))
    assert is_link(link)
    with pytest.raises(UnsafeDataPath, match="outside Q-MAP_DATA"):
        settings.data_path("Raw_Data/escape/victim.csv")


def test_a_file_link_leading_outside_the_root_is_refused(settings, outside):
    link = settings.data_root / "Raw_Data" / "victim.csv"
    link.parent.mkdir(parents=True, exist_ok=True)
    _symlink(link, outside / "victim.csv", directory=False)
    with pytest.raises(UnsafeDataPath):
        settings.data_path("Raw_Data/victim.csv")


def test_a_link_that_stays_inside_the_root_is_accepted(settings):
    real = settings.data_root / "Raw_Data" / "real"
    real.mkdir(parents=True, exist_ok=True)
    _symlink(settings.data_root / "Raw_Data" / "alias", real, directory=True)
    assert settings.data_path("Raw_Data/alias/x.csv") == settings.data_root / "Raw_Data" / "alias" / "x.csv"


def test_safe_remove_never_follows_or_removes_a_link(settings, outside):
    victim = outside / "victim.csv"
    link = settings.data_root / "Cleaned_Data" / "victim.csv"
    link.parent.mkdir(parents=True, exist_ok=True)
    _symlink(link, victim, directory=False)
    assert safe_remove(link) is False
    assert victim.read_text() == "not Q-MAP's file"
    assert not os.stat(victim).st_mode & stat.S_IWUSR  # its read-only flag was not cleared through the link
    assert is_link(link)  # left for the user to investigate


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_recovery_does_not_walk_or_delete_through_a_link(settings, db, outside, kind):
    # an "orphan" managed file reached through a link would otherwise be deleted by recovery
    (outside / "orphan.parquet").write_bytes(b"x")
    os.utime(outside / "orphan.parquet", (0, 0))  # old enough to look abandoned
    link = settings.cleaned_dir / "escape"
    link.parent.mkdir(parents=True, exist_ok=True)
    (_symlink(link, outside, directory=True) if kind == "symlink" else _junction(link, outside))
    assert list(_files_under(settings.cleaned_dir)) == []
    report = recover_incomplete(settings, db, stale_minutes=1)
    assert (outside / "orphan.parquet").exists() and (outside / "victim.csv").exists()
    assert not report.deleted_cleaned_orphans


def test_recovery_reports_a_registered_path_that_now_leads_outside_and_carries_on(settings, db, outside):
    from qmap.core.runs import run_context
    from qmap.storage.registry import receive_file

    src = outside.parent / "ABC.csv"
    src.write_text("time,open,high,low,close\n2026-01-05,1,2,0.5,1.5\n")
    with run_context(settings, db, "FOUND", area="Ingestion") as run:
        rec = receive_file(run, src)
    rel = db.one("SELECT relative_path FROM datasets WHERE dataset_id = ?", (rec.raw_dataset_id,))[0]
    stored = settings.data_path(rel)
    # replace the stored file's folder by a link to a folder outside Q-MAP_DATA holding a copy of the file
    moved = outside / "moved"
    moved.mkdir()
    for f in stored.parent.iterdir():
        os.chmod(f, stat.S_IREAD | stat.S_IWRITE)
        f.rename(moved / f.name)
    stored.parent.rmdir()
    _symlink(stored.parent, moved, directory=True)
    report = recover_incomplete(settings, db)  # must not raise
    assert any("outside Q-MAP_DATA" in p for p in report.problems)
    assert verify_registry(settings, db) is not None  # must not raise either
    assert (moved / stored.name).exists()
