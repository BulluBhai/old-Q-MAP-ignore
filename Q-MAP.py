"""Q-MAP launcher from the first graphical version, kept so existing shortcuts keep working.

It opens Q-MAP Database Manager (what this launcher always opened: Home and Data Management). Q-MAP now has two
applications with their own entry points next to this file:

  database_manager.py      prepare and manage market data
  analytical_workbench.py  research on prepared data

Open this file in Thonny or IDLE and press F5. Nothing here needs the command line.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "Application"))  # lets Q-MAP run straight from this folder, no installation step

APP_KEY = "database_manager"
TITLE = "Q-MAP"


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
