"""A folder scan never leaves the folder the user chose (PR #9 review, 08-Nov-26).

os.walk(followlinks=False) skips symbolic links to folders, but does not treat Windows junctions as links, so a junction
inside a source folder would have been followed and files outside the folder read. The scan now skips every entry whose
real location is not simply inside the folder. Junctions cannot be created on Linux; symbolic links, and a simulated
"redirected" folder (real location different from its listed path), exercise the same check.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.data_engine import discovery as D


def _daily(path):
    rows = ohlcv(10, 3)
    write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(len(rows)), rows)])


@pytest.fixture
def layout(tmp_path):
    inside, outside = tmp_path / "market_files", tmp_path / "elsewhere"
    (inside / "sub").mkdir(parents=True)
    outside.mkdir()
    _daily(inside / "NSE_AAA.csv")
    _daily(inside / "sub" / "NSE_BBB.csv")
    _daily(outside / "NSE_ZZZ.csv")
    return inside, outside


def _names(settings, src):
    files, _ = D.list_candidate_files(settings, src)
    return sorted(p.relative_to(src.location).as_posix() for p in files)


def _symlink(link: Path, target: Path, is_dir: bool):
    try:
        os.symlink(target, link, target_is_directory=is_dir)
    except (OSError, NotImplementedError) as exc:  # Windows without the symlink privilege
        pytest.skip(f"symbolic links cannot be created here: {exc}")


def test_plain_files_and_subfolders_are_still_found(settings, db, layout):
    inside, _ = layout
    src = D.add_folder_source(settings, db, inside, include_subfolders=True, default_exchange="NSE")
    assert _names(settings, src) == ["NSE_AAA.csv", "sub/NSE_BBB.csv"]


def test_a_linked_folder_pointing_outside_is_never_entered(settings, db, layout):
    inside, outside = layout
    _symlink(inside / "link_out", outside, True)
    src = D.add_folder_source(settings, db, inside, include_subfolders=True, default_exchange="NSE")
    assert _names(settings, src) == ["NSE_AAA.csv", "sub/NSE_BBB.csv"]


def test_a_linked_file_is_never_read_even_when_it_points_inside(settings, db, layout):
    inside, outside = layout
    _symlink(inside / "NSE_OUT.csv", outside / "NSE_ZZZ.csv", False)
    _symlink(inside / "NSE_COPY.csv", inside / "NSE_AAA.csv", False)
    src = D.add_folder_source(settings, db, inside, default_exchange="NSE")
    assert _names(settings, src) == ["NSE_AAA.csv"]


def test_a_folder_whose_real_location_is_elsewhere_is_skipped_like_a_junction(settings, db, layout, monkeypatch):
    """Simulates a Windows junction: not reported as a link, but its real location is outside the folder."""
    inside, outside = layout
    junction = inside / "junction"
    junction.mkdir()
    _daily(junction / "NSE_JJJ.csv")
    real_resolve = Path.resolve

    def fake_resolve(self, strict=False):
        if self == junction or junction in self.parents:
            return Path(real_resolve(outside, strict)) / self.relative_to(junction)
        return real_resolve(self, strict)

    monkeypatch.setattr(Path, "resolve", fake_resolve)
    src = D.add_folder_source(settings, db, inside, include_subfolders=True, default_exchange="NSE")
    assert _names(settings, src) == ["NSE_AAA.csv", "sub/NSE_BBB.csv"]


def test_an_entry_that_cannot_be_resolved_is_skipped(settings, db, layout, monkeypatch):
    inside, _ = layout
    real_resolve = Path.resolve

    def failing(self, strict=False):
        if self.name == "sub":
            raise OSError("reparse point cannot be read")
        return real_resolve(self, strict)

    monkeypatch.setattr(Path, "resolve", failing)
    src = D.get_source(db, D.add_folder_source(settings, db, inside, include_subfolders=True,
                                               default_exchange="NSE").source_id)
    assert _names(settings, src) == ["NSE_AAA.csv"]
