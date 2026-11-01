"""The Tk start-up retry used by the window-test fixtures retries only a failure of Tk's own interpreter creation."""

import pytest

tkinter = pytest.importorskip("tkinter")

from gui import conftest  # noqa: E402

SYMPTOMS = [
    "Can't find a usable init.tcl in the following directories: \n    {C:/Python/tcl/tcl8.6}\n\n"
    "couldn't read file \"C:/Python/tcl/tcl8.6/init.tcl\": No error",
    "Can't find a usable tk.tcl in the following directories: \n    C:/Python/tcl/tk8.6\n\n"
    "couldn't read file \"C:/Python/tcl/tk8.6/ttk/combobox.tcl\": no such file or directory",
    "couldn't read file \"C:/Python/tcl/tcl8.6/auto.tcl\": no such file or directory",
    'invalid command name "tcl_findLibrary"',
]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda s: None)


def tk_whose_creation_fails(monkeypatch, *messages):
    """A real tkinter.Tk subclass whose interpreter creation (`_tkinter.create`) raises the given errors in turn,
    then succeeds with a stand-in. The traceback of each failure passes through tkinter's own Tk.__init__."""
    calls = []

    def create(*args, **kwargs):
        calls.append(1)
        if len(calls) <= len(messages):
            raise tkinter.TclError(messages[len(calls) - 1])
        raise _Started()

    monkeypatch.setattr(tkinter._tkinter, "create", create)

    def make():
        try:
            return tkinter.Tk()
        except _Started:
            return "window"

    make.calls = calls
    return make


class _Started(Exception):
    """Stands for 'the interpreter was created' without needing a display."""


@pytest.mark.parametrize("symptom", SYMPTOMS)
def test_each_known_symptom_of_a_failed_interpreter_start_is_retried_and_reported(monkeypatch, symptom):
    make = tk_whose_creation_fails(monkeypatch, symptom)
    with pytest.warns(RuntimeWarning, match="Tk start-up failed"):
        assert conftest.create_with_tk_startup_retry(make) == "window"
    assert len(make.calls) == 2


def test_an_unseen_message_from_a_failed_interpreter_start_is_retried_too(monkeypatch):
    make = tk_whose_creation_fails(monkeypatch, "some other way the Tcl library failed to load")
    with pytest.warns(RuntimeWarning):
        assert conftest.create_with_tk_startup_retry(make) == "window"


def test_repeated_failures_are_retried_then_raised_after_the_last_attempt(monkeypatch):
    make = tk_whose_creation_fails(monkeypatch, *([SYMPTOMS[0]] * 10))
    with pytest.warns(RuntimeWarning):
        with pytest.raises(tkinter.TclError, match="init.tcl"):
            conftest.create_with_tk_startup_retry(make)
    assert len(make.calls) == conftest.TK_STARTUP_ATTEMPTS


def test_a_missing_display_is_not_a_start_up_fault_and_is_not_retried(monkeypatch):
    for message in ("no display name and no $DISPLAY environment variable", "couldn't connect to display \":0\""):
        make = tk_whose_creation_fails(monkeypatch, message)
        with pytest.raises(tkinter.TclError):
            conftest.create_with_tk_startup_retry(make)
        assert len(make.calls) == 1


def test_an_error_that_is_not_from_the_interpreter_creation_is_never_retried():
    calls = []

    def a_tcl_error_from_application_code():
        calls.append(1)
        raise tkinter.TclError("couldn't read file \"x.tcl\": no such file or directory")  # same words, other phase

    with pytest.raises(tkinter.TclError):
        conftest.create_with_tk_startup_retry(a_tcl_error_from_application_code)
    assert len(calls) == 1

    def a_real_bug():
        calls.append(1)
        raise ValueError("a real bug in the application")

    with pytest.raises(ValueError):
        conftest.create_with_tk_startup_retry(a_real_bug)
    assert len(calls) == 2


def test_an_error_while_the_application_builds_its_window_is_never_retried(display):
    """Tk itself starts fine; the application's own set-up then raises a TclError: that is a bug to show, not retry."""
    calls = []

    class Broken(tkinter.Tk):
        def __init__(self):
            super().__init__()
            calls.append(1)
            self.destroy()
            raise tkinter.TclError("couldn't read file \"x.tcl\": no such file or directory")

    with pytest.raises(tkinter.TclError):
        conftest.create_with_tk_startup_retry(Broken)
    assert len(calls) == 1


def test_a_normal_start_is_not_delayed_or_warned(recwarn):
    assert conftest.create_with_tk_startup_retry(lambda: "window") == "window"
    assert not recwarn.list
