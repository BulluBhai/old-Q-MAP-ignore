"""Shared start-up for the entry points (database_manager.py, analytical_workbench.py and the older Q-MAP.py).

It checks that this Python can run Q-MAP, explains in plain words anything that is missing (offering to install
missing packages), and then opens the requested application. Nothing third-party is imported before the check.
"""

from __future__ import annotations

from pathlib import Path


def show_problem(text: str, offer_install: list[str] | None = None, title: str = "Q-MAP") -> None:
    """Show a plain-English message in a small window (falls back to printing if no window is possible)."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        print(f"\n{title} cannot start yet:\n\n" + text)
        return
    root = tk.Tk()
    root.withdraw()
    try:
        if offer_install:
            from .environment import install_packages

            if messagebox.askyesno(f"{title} cannot start yet",
                                   text + "\n\nInstall the missing packages now? (needs an internet connection)"):
                ok, output = install_packages(offer_install)
                messagebox.showinfo(title, ("Installed. Press F5 again to start Q-MAP." if ok else
                                            "The installation did not work:\n\n" + output[-1500:]))
        else:
            messagebox.showerror(f"{title} cannot start yet", text)
    finally:
        root.destroy()


def launch(app_key: str, code_root: str | Path, argv: list[str], problem, prog: str) -> int:
    """`problem(text, offer_install)` shows a start-up problem. Returns the program's exit code."""
    from . import environment

    problems = environment.describe_environment()
    if problems:
        only_packages = not environment.python_problem() and not environment.tkinter_problem()
        problem("\n\n".join(problems), environment.missing_packages() if only_packages else None)
        return 1
    from .app import main as run_app

    return run_app(code_root, argv, app_key=app_key, prog=prog)
