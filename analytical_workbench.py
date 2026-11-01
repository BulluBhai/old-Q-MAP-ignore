"""Q-MAP Analytical Workbench. Open this file in Thonny or IDLE and press F5.

Runs analyses on data already prepared in Database Manager (database_manager.py). Every analysis checks that the
data it needs are ready before it starts, and every run is saved with a Run ID and a full record of its inputs.
The Workbench never imports source files. Nothing here needs the command line.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "Application"))  # lets Q-MAP run straight from this folder, no installation step

APP_KEY = "analytical_workbench"
TITLE = "Q-MAP Analytical Workbench"


def _show_problem(text: str, offer_install: list[str] | None = None) -> None:
    from qmap_gui.launch import show_problem

    show_problem(text, offer_install, title=TITLE)


def main() -> int:
    from qmap_gui.launch import launch

    return launch(APP_KEY, HERE, sys.argv[1:], lambda text, offer=None: _show_problem(text, offer),
                  prog=Path(__file__).name)


if __name__ == "__main__":
    code = main()
    if code:
        sys.exit(code)
