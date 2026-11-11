"""The owner's acceptance package is consistent (beta closure, 09-Nov-26): the guide and the tracker name the same
exact 40-character commit, the same checks A1-A8 and the same evidence files; and, where the git history is available,
that commit holds exactly the program, example data and expected results being tested (only the guide and tracker may
differ after it, because they record its number)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs" / "acceptance_testing"
GUIDE = DOCS / "Q-MAP_MA_Affinity_Beta_Acceptance_Guide_09_Nov_26_125357.md"
TRACKER = DOCS / "Q-MAP_MA_Affinity_Beta_Acceptance_Tracker_09_Nov_26_125357.md"


def _shas(text):
    return set(re.findall(r"\b[0-9a-f]{40}\b", text))


def test_guide_and_tracker_name_one_exact_commit_and_the_same_checks_and_evidence():
    guide, tracker = GUIDE.read_text(encoding="utf-8"), TRACKER.read_text(encoding="utf-8")
    assert len(_shas(guide)) == 1 and _shas(guide) == _shas(tracker)
    sha = _shas(guide).pop()
    assert f"https://github.com/BulluBhai/Q-MAP/archive/{sha}.zip" in guide and "/tree/claude/" not in guide
    checks = [f"A{i}" for i in range(1, 9)]
    assert re.findall(r"^### (A\d):", guide, re.M) == checks
    assert re.findall(r"^\| (A\d) \|", tracker, re.M) == checks
    for name in re.findall(r"`(A\d_[A-Za-z_]+\.png)`", tracker):
        assert name in guide, name


def test_the_named_commit_holds_exactly_the_program_and_expected_results_under_test():
    sha = _shas(GUIDE.read_text(encoding="utf-8")).pop()
    git = shutil.which("git")
    if git is None or not (REPO / ".git").exists():
        pytest.skip("no git checkout")
    if subprocess.run([git, "-C", str(REPO), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True).returncode:
        pytest.skip(f"commit {sha[:12]} is not in this (shallow) clone; checked where the history is available")
    paths = ["Application", "*.py", "pyproject.toml", "Tests", ".gitattributes", "docs/acceptance_testing/beta_ma_affinity_09_Nov_26"]
    done = subprocess.run([git, "-C", str(REPO), "diff", "--name-only", sha, "--", *paths], capture_output=True, text=True)
    changed = [p for p in done.stdout.splitlines() if p != "Tests/beta/test_acceptance_package.py"]
    assert done.returncode == 0 and changed == [], f"changed after {sha[:12]}: {changed}"
