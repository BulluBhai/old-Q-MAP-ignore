"""The owner's V1 beta acceptance package (09-Nov-26) is consistent and FROZEN: the guide and the tracker name the same
exact 40-character commit, the same checks A1-A8 and the same evidence files; and, where the git history is available,
the evidence folder is unchanged since that commit and the guide and tracker are unchanged since they recorded it.

The owner tested that exact commit on Windows (A1-A7 passed, 10-Nov-26), so it is the V1 baseline. Later program changes
do not touch this package: V1 parity is proved by the worked example reproducing its result tables
(Tests/gui/test_beta_worked_example.py), and a release candidate gets its own package naming its own commit."""

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


# the commit that recorded 2c81d3a in the guide and tracker (their text is frozen from here on)
FROZEN_DOCS_COMMIT = "2feb4538744b112126ac69c80e3ffd0594b4abe1"


def _git():
    git = shutil.which("git")
    if git is None or not (REPO / ".git").exists():
        pytest.skip("no git checkout")
    return git


def _has(git, sha):
    return not subprocess.run([git, "-C", str(REPO), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True).returncode


def test_the_v1_evidence_is_unchanged_since_the_owner_tested_commit():
    sha = _shas(GUIDE.read_text(encoding="utf-8")).pop()
    git = _git()
    if not _has(git, sha):
        pytest.skip(f"commit {sha[:12]} is not in this (shallow) clone; checked where the history is available")
    done = subprocess.run([git, "-C", str(REPO), "diff", "--name-only", sha, "--",
                           "docs/acceptance_testing/beta_ma_affinity_09_Nov_26"], capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout.split() == [], f"V1 evidence changed after {sha[:12]}: {done.stdout}"


def test_the_v1_guide_and_tracker_are_unchanged():
    git = _git()
    if not _has(git, FROZEN_DOCS_COMMIT):
        pytest.skip(f"commit {FROZEN_DOCS_COMMIT[:12]} is not in this (shallow) clone")
    done = subprocess.run([git, "-C", str(REPO), "diff", "--name-only", FROZEN_DOCS_COMMIT, "--",
                           str(GUIDE.relative_to(REPO)), str(TRACKER.relative_to(REPO))], capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout.split() == [], done.stdout
