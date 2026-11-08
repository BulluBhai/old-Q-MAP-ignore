"""Scan integrity (independent review of PR #9 at 9c2e420, 08-Nov-26).

1. A file whose CONTENTS changed is detected even when its size and modification time are unchanged (the checksum
   is computed on every scan; size and time are never trusted on their own).
2. A folder that cannot be read never produces an apparently complete scan: the scan is recorded as failed and
   INCOMPLETE, the folder is reported, and files last seen inside it are recorded as unreadable, not as missing.

Synthetic data only.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.catalog import get_dataset
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    (f / "sub").mkdir(parents=True)
    return f


@pytest.fixture
def source(settings, db, folder):
    return D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE",
                               include_subfolders=True)


def scan(settings, db, source):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, source.source_id)


def daily(path, n=20, seed=1):
    rows = ohlcv(n, seed)
    return write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(len(rows)), rows)])


def outcome(result, rel):
    return next(f for f in result.files if f[0] == rel)


def scan_row(db, scan_id):
    return db.one("SELECT * FROM source_scans WHERE scan_id = ?", (scan_id,))


# ---- 1. changed contents with the same size and modification time -------------------------------------------------

def _same_size_edit(path):
    """Change one digit of one price, keep the size, and restore the original access and modification times."""
    st = os.stat(path)
    data = path.read_bytes()
    lines = data.split(b"\n")
    cells = lines[3].split(b",")
    close = cells[4].rstrip(b"\r")
    pos = max(i for i, c in enumerate(close) if chr(c).isdigit())
    new_digit = b"1" if close[pos:pos + 1] != b"1" else b"2"
    cells[4] = cells[4][:pos] + new_digit + cells[4][pos + 1:]
    lines[3] = b",".join(cells)
    new = b"\n".join(lines)
    assert len(new) == len(data) and new != data
    path.write_bytes(new)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    after = os.stat(path)
    assert (after.st_size, after.st_mtime_ns) == (st.st_size, st.st_mtime_ns)


def test_changed_contents_with_the_same_size_and_time_are_detected(settings, db, source, folder):
    f = folder / "NSE_ABC.csv"
    daily(f)
    first = scan(settings, db, source)
    assert outcome(first, "NSE_ABC.csv")[3] == "imported"
    old_ids = D.file_states(db, source.source_id)[0].dataset_ids
    old_row = dict(db.one("SELECT * FROM datasets WHERE dataset_id = ?", (old_ids[0],)))

    _same_size_edit(f)
    second = scan(settings, db, source)
    rel, change, action, result, detail = outcome(second, "NSE_ABC.csv")
    assert (change, action, result) == ("changed", "processed", "imported"), detail
    new_ids = D.file_states(db, source.source_id)[0].dataset_ids
    assert new_ids and new_ids != old_ids
    # the earlier dataset is untouched (DQ-1: report only) and the difference is reported on the new one
    assert dict(db.one("SELECT * FROM datasets WHERE dataset_id = ?", (old_ids[0],))) == old_row
    assert any("differ" in w for w in get_dataset(db, new_ids[0]).warnings)


def test_an_unchanged_file_is_still_skipped_after_its_checksum_is_checked(settings, db, source, folder):
    daily(folder / "NSE_ABC.csv")
    scan(settings, db, source)
    again = scan(settings, db, source)
    assert outcome(again, "NSE_ABC.csv")[1:3] == ("unchanged", "skipped")
    obs = D.file_history(db, source.source_id, "NSE_ABC.csv")
    assert obs[-1]["sha256"] == obs[0]["sha256"]


# ---- 2. folders that cannot be read ---------------------------------------------------------------------------------

@pytest.fixture
def deny(monkeypatch):
    """Make os.scandir (used by os.walk) fail for the given folders, as an access-denied folder would."""
    real = os.scandir
    denied: set = set()

    def fake(path="."):
        if os.path.normcase(os.path.abspath(os.fspath(path))) in denied:
            raise PermissionError(13, "Permission denied", os.fspath(path))
        return real(path)

    monkeypatch.setattr(os, "scandir", fake)
    return lambda p: denied.add(os.path.normcase(os.path.abspath(os.fspath(p))))


def test_an_unreadable_subfolder_makes_the_scan_incomplete_and_never_missing(settings, db, source, folder, deny):
    daily(folder / "NSE_TOP.csv")
    daily(folder / "sub" / "NSE_LOW.csv", seed=2)
    first = scan(settings, db, source)
    assert first.complete and scan_row(db, first.scan_id)["status"] == "completed"
    datasets_before = db.query("SELECT dataset_id, status FROM datasets ORDER BY dataset_id")

    deny(folder / "sub")
    daily(folder / "NSE_NEW.csv", seed=3)
    second = scan(settings, db, source)
    assert not second.complete
    assert second.unreadable_folders and second.unreadable_folders[0][0] == "sub"
    assert second.summary().startswith("INCOMPLETE SCAN")
    row = scan_row(db, second.scan_id)
    assert row["status"] == "failed" and row["detail"].startswith("Incomplete:")
    summary = json.loads(row["summary_json"])
    assert summary["complete"] is False and summary["unreadable_folders"][0][0] == "sub"
    # readable files are still processed
    assert outcome(second, "NSE_NEW.csv")[3] == "imported"
    assert outcome(second, "NSE_TOP.csv")[1] == "unchanged"
    # the file inside the unreadable folder is NOT reported as missing, and its data are unchanged
    rel, change, action, result, detail = outcome(second, "sub/NSE_LOW.csv")
    assert (change, result) == ("unreadable", "failed") and "could not be read" in detail
    assert "missing" not in second.counts
    after = {r["dataset_id"]: r["status"] for r in db.query("SELECT dataset_id, status FROM datasets")}
    assert all(after[r["dataset_id"]] == r["status"] for r in datasets_before)
    # the report says so
    with open(second.report_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0][4:6] == ["Scan", "INCOMPLETE: " + second.incomplete_text()]
    assert any(r[0] == "sub" and r[3] == "Could not be read" for r in rows)


def test_the_folder_becomes_readable_again_and_the_next_scan_is_complete(settings, db, source, folder, monkeypatch):
    daily(folder / "sub" / "NSE_LOW.csv", seed=2)
    scan(settings, db, source)
    n_datasets = db.one("SELECT COUNT(*) AS n FROM datasets")["n"]
    real = os.scandir
    target = os.path.normcase(os.path.abspath(folder / "sub"))

    def fake(path="."):
        if os.path.normcase(os.path.abspath(os.fspath(path))) == target:
            raise PermissionError(13, "Permission denied", os.fspath(path))
        return real(path)

    monkeypatch.setattr(os, "scandir", fake)
    assert not scan(settings, db, source).complete
    monkeypatch.setattr(os, "scandir", real)
    fixed = scan(settings, db, source)
    assert fixed.complete and scan_row(db, fixed.scan_id)["status"] == "completed"
    assert outcome(fixed, "sub/NSE_LOW.csv")[3] in ("reused", "imported")
    assert db.one("SELECT COUNT(*) AS n FROM datasets")["n"] == n_datasets  # same content: reused, not duplicated


def test_an_unreadable_source_folder_marks_nothing_missing(settings, db, source, folder, deny):
    daily(folder / "NSE_TOP.csv")
    scan(settings, db, source)
    deny(folder)
    res = scan(settings, db, source)
    assert not res.complete and res.unreadable_folders[0][0] == "."
    assert outcome(res, "NSE_TOP.csv")[1:4] == ("unreadable", "none", "failed")
    assert "missing" not in res.counts
    assert scan_row(db, res.scan_id)["status"] == "failed"


def test_an_entry_whose_location_cannot_be_read_is_reported_not_silently_dropped(settings, db, folder, monkeypatch):
    from pathlib import Path
    daily(folder / "sub" / "NSE_LOW.csv")
    src = D.add_folder_source(settings, db, folder, default_exchange="NSE", include_subfolders=True)
    real_resolve = Path.resolve

    def failing(self, strict=False):
        if self.name == "sub":
            raise OSError(5, "I/O error")
        return real_resolve(self, strict)

    monkeypatch.setattr(Path, "resolve", failing)
    unreadable: list = []
    files, _ = D.list_candidate_files(settings, src, unreadable=unreadable)
    assert files == [] and unreadable == [("sub", "its location cannot be read (I/O error)")]


@pytest.mark.skipif(sys.platform == "win32" or not hasattr(os, "geteuid") or os.geteuid() == 0,
                    reason="needs POSIX permissions and a non-root user (the Linux CI runner)")
def test_a_real_permission_denied_folder_makes_the_scan_incomplete(settings, db, source, folder):
    daily(folder / "sub" / "NSE_LOW.csv")
    scan(settings, db, source)
    os.chmod(folder / "sub", 0)
    try:
        res = scan(settings, db, source)
    finally:
        os.chmod(folder / "sub", 0o755)
    assert not res.complete and res.unreadable_folders[0][0] == "sub"
    assert outcome(res, "sub/NSE_LOW.csv")[1] == "unreadable"


# ---- real Windows junction (Windows CI) ------------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions exist only on Windows")
def test_a_real_windows_junction_is_never_followed(settings, db, folder, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    daily(outside / "NSE_OUT.csv")
    daily(folder / "NSE_IN.csv")
    junction = folder / "junction"
    made = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True, text=True)
    if made.returncode != 0:
        pytest.skip(f"mklink /J failed here: {made.stdout} {made.stderr}")
    assert (junction / "NSE_OUT.csv").is_file()  # the junction really points outside
    assert not junction.is_symlink()  # and Python does not report it as a link
    src = D.add_folder_source(settings, db, folder, default_exchange="NSE", include_subfolders=True)
    links: list = []
    files, _ = D.list_candidate_files(settings, src, links=links)
    assert [p.name for p in files] == ["NSE_IN.csv"]
    assert links and links[0][0] == "junction/"
    res = scan(settings, db, src)
    assert res.complete and [f[0] for f in res.files] == ["NSE_IN.csv"]
    assert res.links_skipped[0][0] == "junction/"
