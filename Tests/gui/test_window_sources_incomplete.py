"""Real-window test: an incomplete folder scan is shown as INCOMPLETE on the Sources screen, never as finished
(independent review of PR #9 at 9c2e420, 08-Nov-26). Synthetic data only."""

from __future__ import annotations

import os

from fixtures.builders import HEADER, daily_rows, write_delimited


def test_an_unreadable_subfolder_is_shown_as_an_incomplete_scan(gui, tmp_path, monkeypatch):
    market = tmp_path / "market_files"
    (market / "sub").mkdir(parents=True)
    write_delimited(market / "NSE_ABC.csv", HEADER, daily_rows(15))
    write_delimited(market / "sub" / "NSE_DEF.csv", HEADER, daily_rows(15, seed=3))
    real = os.scandir
    denied = os.path.normcase(os.path.abspath(market / "sub"))

    def fake(path="."):
        if os.path.normcase(os.path.abspath(os.fspath(path))) == denied:
            raise PermissionError(13, "Permission denied", os.fspath(path))
        return real(path)

    app = gui.start()
    gui.choose_folders(app)
    app.show("sources")
    frame = app.screens["sources"]
    gui.dialogs.directories.append(str(market))
    frame.tz_var.set("Asia/Kolkata")
    frame.exch_var.set("NSE")
    frame.sub_var.set(True)
    frame.add_button.invoke()

    monkeypatch.setattr(os, "scandir", fake)
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    text = frame.final_label.cget("text")
    assert text.startswith("Scan INCOMPLETE:") and "sub" in text and "Scan finished" not in text
    assert frame.counts_var.get().startswith("INCOMPLETE SCAN")
    assert {s.relative_path for s in frame.file_rows.values()} == {"NSE_ABC.csv"}  # the readable file was processed

    monkeypatch.setattr(os, "scandir", real)
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    assert frame.final_label.cget("text").startswith("Scan finished")
    assert {s.relative_path for s in frame.file_rows.values()} == {"NSE_ABC.csv", "sub/NSE_DEF.csv"}
