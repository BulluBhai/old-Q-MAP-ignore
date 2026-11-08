"""Real-window test: when a scan is both STOPPED by the user (PR #10) and INCOMPLETE (PR #9), the Sources screen
says both, in the error colour (integration of 08-Nov-26)."""

from __future__ import annotations

from qmap_gui import source_services as ss


def test_stopped_and_incomplete_are_both_shown(gui):
    from qmap_gui.widgets import ERROR_COLOR, WARN_COLOR  # needs tkinter: imported only when the GUI test runs

    app = gui.start()
    gui.choose_folders(app)
    app.show("sources")
    frame = app.screens["sources"]
    frame._finish(ss.ScanSummary(run_id="R", summary="INCOMPLETE SCAN: 1 imported, STOPPED by you", stopped=True,
                                 not_processed=["NSE_B.csv"], counts={"imported": 1},
                                 incomplete="1 folder(s) could not be read, so their files were not checked (sub: x)."))
    text = frame.final_label.cget("text")
    assert text.startswith("Stopped by you") and "Scan INCOMPLETE: 1 folder(s) could not be read" in text
    assert str(frame.final_label.cget("fg")) == ERROR_COLOR
    frame._finish(ss.ScanSummary(run_id="R", summary="1 imported, STOPPED by you", stopped=True,
                                 not_processed=["NSE_B.csv"], counts={"imported": 1}))
    assert "INCOMPLETE" not in frame.final_label.cget("text")
    assert str(frame.final_label.cget("fg")) == WARN_COLOR  # a plain stop keeps PR #10's warning colour
