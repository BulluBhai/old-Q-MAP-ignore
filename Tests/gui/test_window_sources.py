"""Real-window tests: Database Manager Sources screen (Blueprint v1.3 §8.5.8): add a folder, scan, answer a question,
scan again, and see the dataset in both applications. Source files must be unchanged afterwards."""

from __future__ import annotations

import hashlib

from fixtures.builders import HEADER, daily_rows, write_delimited


def _sha(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}


def _files(frame):
    return {s.relative_path: s for s in frame.file_rows.values()}


def ss_latest_answer(world, rel):
    from qmap.storage.db import open_database

    db = open_database(world.data / "Metadata" / "qmap_metadata.sqlite")
    try:
        return db.one("SELECT * FROM source_answers WHERE relative_path = ?", (rel,))
    finally:
        db.close()


def test_add_scan_answer_and_load_from_the_sources_screen(gui, world, tmp_path):
    market = tmp_path / "market_files"
    market.mkdir()
    write_delimited(market / "NSE_ABC.csv", HEADER, daily_rows(15))
    write_delimited(market / "prices.csv", HEADER, daily_rows(15, seed=4))
    before = _sha(market)

    app = gui.start()
    gui.choose_folders(app)
    app.screens["home"].module_rows["sources"]["button"].invoke()
    assert app.current == "sources"
    frame = app.screens["sources"]
    assert str(frame.scan_button.cget("state")) == "disabled"  # nothing to scan yet

    gui.dialogs.directories.append(str(market))
    frame.tz_var.set("Asia/Kolkata")
    frame.exch_var.set("NSE")
    frame.add_button.invoke()
    assert len(frame.source_rows) == 1 and frame.selected_source() is not None
    assert str(frame.scan_button.cget("state")) == "normal"

    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    files = _files(frame)
    assert files["NSE_ABC.csv"].outcome == "imported"
    assert files["prices.csv"].outcome == "needs_answer"
    assert "need attention" in frame.final_label.cget("text")

    item = next(i for i, s in frame.file_rows.items() if s.relative_path == "prices.csv")
    frame.files_tree.selection_set(item)
    frame.on_file_select()
    assert str(frame.ans_sym_entry.cget("state")) == "normal"
    assert str(frame.ans_date_box.cget("state")) == "disabled"  # only the boxes the question needs
    # PR #9 finding F-01: the folder's default exchange and the file name's symbol are filled in as a suggestion only
    assert (frame.ans_exch.get(), frame.ans_sym.get()) == ("NSE", "PRICES")
    assert ss_latest_answer(world, "prices.csv") is None  # nothing is recorded until Save answer
    frame.ans_exch.set("")
    frame.ans_sym.set("")
    frame.answer_button.invoke()
    assert gui.dialogs.messages[-1][0] == "warn"  # boxes emptied: asked for the missing answer, nothing saved
    frame.ans_exch.set("NSE")
    frame.ans_sym.set("PRC")
    frame.answer_button.invoke()
    assert "Answer recorded" in frame.final_label.cget("text")

    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    files = _files(frame)
    assert files["prices.csv"].outcome == "imported" and files["NSE_ABC.csv"].change == "unchanged"
    assert frame.last_report is not None and frame.last_report.is_file()
    assert _sha(market) == before  # the source folder was only read

    datasets = app.screens["datasets"]
    app.show("datasets")
    assert {datasets.tree.item(i, "values")[1] for i in datasets.tree.get_children()} == {"NSE:ABC", "NSE:PRC"}


def test_the_sources_screen_refuses_q_map_own_folders(gui, world):
    app = gui.start()
    gui.choose_folders(app)
    frame = app.screens["sources"]
    gui.dialogs.directories.append(str(world.data))
    frame.add_button.invoke()
    assert gui.dialogs.messages[-1][0] == "error" and not frame.source_rows


def test_stop_using_a_folder_keeps_its_files_and_data(gui, world, tmp_path):
    market = tmp_path / "m"
    market.mkdir()
    write_delimited(market / "NSE_ABC.csv", HEADER, daily_rows(10))
    app = gui.start()
    gui.choose_folders(app)
    frame = app.screens["sources"]
    gui.dialogs.directories.append(str(market))
    frame.add_button.invoke()
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    frame.remove_button.invoke()
    assert not frame.source_rows and (market / "NSE_ABC.csv").is_file()
    app.show("datasets")
    assert len(app.screens["datasets"].rows) == 1


def test_a_file_that_lacks_only_its_exchange_asks_only_for_the_exchange(gui, world, tmp_path):
    """Owner decision DQ-2 (02-Nov-26): the symbol column is the file's own information; only the exchange is asked."""
    market = tmp_path / "m"
    market.mkdir()
    rows = [[d[0], "INFY", *d[1:]] for d in daily_rows(10)]
    write_delimited(market / "prices.csv", ["date", "symbol", "open", "high", "low", "close", "volume"], rows)
    app = gui.start()
    gui.choose_folders(app)
    frame = app.screens["sources"]
    frame.exch_var.set("")
    gui.dialogs.directories.append(str(market))
    frame.add_button.invoke()
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    item = next(i for i, s in frame.file_rows.items() if s.relative_path == "prices.csv")
    frame.files_tree.selection_set(item)
    frame.on_file_select()
    assert str(frame.ans_exch_entry.cget("state")) == "normal"
    assert str(frame.ans_sym_entry.cget("state")) == "disabled"
    frame.ans_exch.set("NSE")
    frame.answer_button.invoke()
    assert "Answer recorded" in frame.final_label.cget("text")
    frame.scan_button.invoke()
    gui.wait(lambda: not frame.running)
    assert next(s for s in frame.file_rows.values() if s.relative_path == "prices.csv").outcome == "imported"
