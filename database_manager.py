"""Q-MAP Database Manager. Open this file in Thonny or IDLE and press F5.

Prepares and manages market data: load and check source files, see what has been prepared and where it is stored,
keep datasets Permanent or Temporary, and derive weekly, monthly, quarterly and yearly data from daily data.
Research is done in the separate Analytical Workbench (analytical_workbench.py), which uses the data prepared here.
Nothing here needs the command line.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "Application"))  # lets Q-MAP run straight from this folder, no installation step

APP_KEY = "database_manager"
TITLE = "Q-MAP Database Manager"


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
