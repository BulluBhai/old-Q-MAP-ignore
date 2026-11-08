"""Reading the profile drop-down's selection must work with Tk 8.6 and Tk 9 on every supported Python (3.11+).

Python 3.11 + Tk 9: ttk.Combobox.current() raised TclError ("expected integer but got") when nothing was chosen,
which broke choosing the data folders and every profile action in the Data Management window."""

import pytest

pytest.importorskip("tkinter")

from qmap_gui.widgets import combobox_index  # noqa: E402


class _StubTk:
    def __init__(self, answer):
        self.answer = answer

    def call(self, *args):
        assert args == (".combo", "current")
        return self.answer

    @staticmethod
    def getint(value):
        return int(value)


class _StubCombo:
    _w = ".combo"

    def __init__(self, answer):
        self.tk = _StubTk(answer)


@pytest.mark.parametrize("answer, expected", [("", -1), (-1, -1), ("-1", -1), (0, 0), ("2", 2), (3, 3)])
def test_no_selection_is_minus_one_and_a_selection_is_its_index_whatever_tk_answers(answer, expected):
    assert combobox_index(_StubCombo(answer)) == expected


def test_a_real_combobox_with_and_without_a_selection(display):
    import tkinter
    from tkinter import ttk

    from gui.conftest import create_with_tk_startup_retry

    root = create_with_tk_startup_retry(tkinter.Tk)
    try:
        combo = ttk.Combobox(root, values=["a", "b", "c"])
        assert combobox_index(combo) == -1
        combo.current(1)
        assert combobox_index(combo) == 1 == combo.current()  # same answer as tkinter's own, when there is one
        combo.set("")
        assert combobox_index(combo) == -1
    finally:
        root.destroy()
