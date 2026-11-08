"""PR #9 corrections combined with PR #10 features (integration of 08-Nov-26). Synthetic data only.

- A scan that the user STOPS (PR #10) and that is also INCOMPLETE (PR #9) reports both, is recorded as failed, and
  marks nothing as missing.
- The command-line `scan` (PR #10) never reports an incomplete scan as success: it says so and returns 1.
- The scan job (Sources screen) carries both flags to the window.
"""

from __future__ import annotations

import json
import os

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.cli import main as cli_main
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap_gui import source_services as ss


def daily(path, n=12, seed=1):
    rows = ohlcv(n, seed)
    return write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(len(rows)), rows)])


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    (f / "sub").mkdir(parents=True)
    return f


@pytest.fixture
def deny(monkeypatch):
    real = os.scandir
    denied: set = set()

    def fake(path="."):
        if os.path.normcase(os.path.abspath(os.fspath(path))) in denied:
            raise PermissionError(13, "Permission denied", os.fspath(path))
        return real(path)

    monkeypatch.setattr(os, "scandir", fake)
    return lambda p: denied.add(os.path.normcase(os.path.abspath(os.fspath(p))))


def scan(settings, db, src, **kw):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, src.source_id, **kw)


def test_a_stopped_scan_that_is_also_incomplete_reports_both(settings, db, folder, deny):
    for i in range(3):
        daily(folder / f"NSE_S{i}.csv", seed=i)
    daily(folder / "sub" / "NSE_LOW.csv", seed=9)
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE",
                              include_subfolders=True)
    first = scan(settings, db, src)
    assert first.complete and not first.stopped
    deny(folder / "sub")
    calls = {"n": 0}

    def stop_after_one():
        calls["n"] += 1
        return calls["n"] > 1

    res = scan(settings, db, src, should_stop=stop_after_one)
    assert res.stopped and not res.complete
    text = res.summary()
    assert text.startswith("INCOMPLETE SCAN") and "STOPPED by you" in text
    row = db.one("SELECT * FROM source_scans WHERE scan_id = ?", (res.scan_id,))
    assert row["status"] == "failed" and row["detail"].startswith("Incomplete:")
    summary = json.loads(row["summary_json"])
    assert summary["stopped"] is True and summary["complete"] is False and summary["not_processed"]
    assert "missing" not in res.counts  # nothing is reported missing when the scan stopped or a folder was unreadable
    assert all(s.outcome != "missing" for s in D.file_states(db, src.source_id))


def test_the_scan_job_carries_stopped_and_incomplete_to_the_window(settings, db, folder, deny):
    daily(folder / "NSE_S0.csv")
    src = D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE",
                              include_subfolders=True)
    deny(folder / "sub")
    job = ss.ScanJob(settings, src.source_id)
    job.cancel()  # Stop pressed before the first file
    out = job.run()
    assert out.error is None and out.stopped and out.incomplete and "sub" in out.incomplete


def _config(tmp_path, roots):
    cfg = tmp_path / "qmap.local.toml"
    cfg.write_text(f'[paths]\ndata_root = "{roots["data"].as_posix()}"\noutput_root = "{roots["output"].as_posix()}"\n')
    return cfg


def test_command_line_scan_returns_1_and_says_so_when_incomplete(settings, roots, folder, tmp_path, capsys, deny):
    daily(folder / "NSE_TOP.csv")
    cfg = _config(tmp_path, roots)
    assert cli_main(["--config", str(cfg), "scan", "--folder", str(folder)]) == 0  # complete: success, as before
    capsys.readouterr()
    deny(folder)  # the source folder itself cannot be listed
    assert cli_main(["--config", str(cfg), "scan", "--folder", str(folder)]) == 1
    out = capsys.readouterr().out
    assert "Summary: INCOMPLETE SCAN" in out and "Scan INCOMPLETE:" in out
