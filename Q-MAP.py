"""Q-MAP launcher. Open this file in Thonny or IDLE and press F5.

It checks that this Python can run Q-MAP, explains in plain words anything that is missing, and then opens the
Q-MAP window. Nothing here needs the command line.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "Application"))  # lets Q-MAP run straight from this folder, no installation step


def _show_problem(text: str, offer_install: list[str] | None = None) -> None:
    """Show a plain-English message in a small window (falls back to printing if no window is possible)."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        print("\nQ-MAP cannot start yet:\n\n" + text)
        return
    root = tk.Tk()
    root.withdraw()
    try:
        if offer_install:
            from qmap_gui.environment import install_packages

            if messagebox.askyesno("Q-MAP cannot start yet",
                                   text + "\n\nInstall the missing packages now? (needs an internet connection)"):
                ok, output = install_packages(offer_install)
                messagebox.showinfo("Q-MAP", ("Installed. Press F5 again to start Q-MAP." if ok else
                                              "The installation did not work:\n\n" + output[-1500:]))
        else:
            messagebox.showerror("Q-MAP cannot start yet", text)
    finally:
        root.destroy()


def main() -> int:
    from qmap_gui.environment import describe_environment, missing_packages, python_problem, tkinter_problem

    problems = describe_environment()
    if problems:
        only_packages = not python_problem() and not tkinter_problem()
        _show_problem("\n\n".join(problems), missing_packages() if only_packages else None)
        return 1
    from qmap_gui.app import main as run_app

    return run_app(HERE, sys.argv[1:])


if __name__ == "__main__":
    code = main()
    if code:
        sys.exit(code)
