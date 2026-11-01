"""The Tk start-up retry used by the window-test fixtures retries only Tk's own start-up error, visibly."""

import pytest

tkinter = pytest.importorskip("tkinter")

from gui import conftest  # noqa: E402

INIT_TCL = ("Can't find a usable init.tcl in the following directories: \n    {C:/Python/tcl/tcl8.6}\n\n"
            "couldn't read file \"C:/Python/tcl/tcl8.6/init.tcl\": No error")
TK_TCL = ("Can't find a usable tk.tcl in the following directories: \n    C:/Python/tcl/tk8.6\n\n"
          "couldn't read file \"C:/Python/tcl/tk8.6/ttk/combobox.tcl\": no such file or directory")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda s: None)


def failing_then_ok(*messages):
    calls = []

    def make():
        calls.append(1)
        if len(calls) <= len(messages):
            raise tkinter.TclError(messages[len(calls) - 1])
        return "window"

    make.calls = calls
    return make


@pytest.mark.parametrize("first", [INIT_TCL, TK_TCL])
def test_a_transient_startup_failure_is_retried_and_reported(first):
    make = failing_then_ok(first)
    with pytest.warns(RuntimeWarning, match="Tk start-up failed"):
        assert conftest.create_with_tk_startup_retry(make) == "window"
    assert len(make.calls) == 2


def test_two_failures_in_a_row_are_still_retried():
    make = failing_then_ok(INIT_TCL, TK_TCL)
    with pytest.warns(RuntimeWarning):
        assert conftest.create_with_tk_startup_retry(make) == "window"
    assert len(make.calls) == 3


def test_a_start_up_that_keeps_failing_is_raised_after_the_last_attempt():
    make = failing_then_ok(*([INIT_TCL] * 10))
    with pytest.warns(RuntimeWarning):
        with pytest.raises(tkinter.TclError, match="init.tcl"):
            conftest.create_with_tk_startup_retry(make)
    assert len(make.calls) == conftest.TK_STARTUP_ATTEMPTS


def test_any_other_error_is_raised_immediately_and_not_retried():
    make = failing_then_ok("no display name and no $DISPLAY environment variable")
    with pytest.raises(tkinter.TclError, match="no display"):
        conftest.create_with_tk_startup_retry(make)
    assert len(make.calls) == 1

    def boom():
        raise ValueError("a real bug in the application")

    with pytest.raises(ValueError):
        conftest.create_with_tk_startup_retry(boom)


def test_a_normal_start_is_not_delayed_or_warned(recwarn):
    make = failing_then_ok()
    assert conftest.create_with_tk_startup_retry(make) == "window"
    assert len(make.calls) == 1 and not recwarn.list
