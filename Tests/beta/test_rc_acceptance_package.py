"""The MA Affinity V2 release candidate's acceptance package (10-Nov-26) is consistent: the guide and the tracker name
the same exact 40-character commit, the same checks R1-R10 and the same evidence files; and, where the git history is
available, that commit holds exactly the program, the example data and the expected results being tested (only the
guide and the tracker may differ after it, because they record its number).

The V1 beta package (09-Nov-26) is separate and frozen (test_acceptance_package.py)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs" / "acceptance_testing"
CHECKS = [f"R{i}" for i in range(1, 11)]


def _one(pattern):
    found = sorted(DOCS.glob(pattern))
    assert len(found) == 1, (pattern, found)
    return found[0]


def _shas(text):
    return set(re.findall(r"\b[0-9a-f]{40}\b", text))


def _package():
    guide = _one("Q-MAP_MA_Affinity_V2_RC_Acceptance_Guide_*.md")
    tracker = _one("Q-MAP_MA_Affinity_V2_RC_Acceptance_Tracker_*.md")
    return guide, tracker, guide.read_text(encoding="utf-8"), tracker.read_text(encoding="utf-8")


def test_guide_and_tracker_name_one_exact_commit_and_the_same_checks_and_evidence():
    guide_path, tracker_path, guide, tracker = _package()
    assert guide_path.name.replace("Guide", "Tracker") == tracker_path.name and tracker_path.name in guide
    assert len(_shas(guide)) == 1 and _shas(guide) == _shas(tracker)
    sha = _shas(guide).pop()
    assert f"https://github.com/BulluBhai/Q-MAP/archive/{sha}.zip" in guide and "/tree/claude/" not in guide
    assert re.findall(r"^### (R\d+):", guide, re.M) == CHECKS
    assert re.findall(r"^\| (R\d+) \|", tracker, re.M) == CHECKS
    names = re.findall(r"`(R\d+_[A-Za-z0-9_]+\.png)`", tracker)
    assert names and all(n in guide for n in names)
    assert all(n in tracker for n in re.findall(r"`(R\d+_[A-Za-z0-9_]+\.png)`", guide))


def test_the_named_commit_holds_exactly_the_program_and_expected_results_under_test():
    sha = _shas(_package()[2]).pop()
    git = shutil.which("git")
    if git is None or not (REPO / ".git").exists():
        pytest.skip("no git checkout")
    if subprocess.run([git, "-C", str(REPO), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True).returncode:
        pytest.skip(f"commit {sha[:12]} is not in this (shallow) clone; checked where the history is available")
    paths = ["Application", "*.py", "pyproject.toml", "Tests", ".gitattributes", "docs/acceptance_testing/rc_ma_affinity_v2",
             "docs/acceptance_testing/beta_ma_affinity_09_Nov_26"]
    done = subprocess.run([git, "-C", str(REPO), "diff", "--name-only", sha, "--", *paths], capture_output=True, text=True)
    changed = [p for p in done.stdout.splitlines() if p != "Tests/beta/test_rc_acceptance_package.py"]
    assert done.returncode == 0 and changed == [], f"changed after {sha[:12]}: {changed}"
