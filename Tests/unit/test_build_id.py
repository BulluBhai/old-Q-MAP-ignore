"""Build identification (owner instruction 03-Nov-26): different code builds must be distinguishable in every run record,
even when the version label is unchanged."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from qmap import __version__
from qmap.core import build as B
from qmap.core.runs import finish_run, start_run


def _tree(root):
    (root / "Application" / "pkg").mkdir(parents=True)
    (root / "Application" / "pkg" / "calc.py").write_text("X = 1\n", encoding="utf-8")
    (root / "database_manager.py").write_text("print('dm')\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='q'\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("text\n", encoding="utf-8")
    return root


def test_same_version_different_code_gives_a_different_build(tmp_path):
    root = _tree(tmp_path / "a")
    before = B.build_info(root)
    (root / "Application" / "pkg" / "calc.py").write_text("X = 2\n", encoding="utf-8")
    after = B.build_info(root)
    assert before["version"] == after["version"] == __version__
    assert before["source_fingerprint"] != after["source_fingerprint"]
    assert B.build_label(before) != B.build_label(after)


def test_new_program_file_changes_the_build_but_documents_do_not(tmp_path):
    root = _tree(tmp_path / "a")
    fp = B.source_fingerprint(root)
    (root / "docs" / "guide.md").write_text("changed\n", encoding="utf-8")
    assert B.source_fingerprint(root) == fp
    (root / "Application" / "pkg" / "extra.py").write_text("", encoding="utf-8")
    assert B.source_fingerprint(root) != fp


def test_windows_and_unix_line_endings_give_the_same_build(tmp_path):
    a, b = _tree(tmp_path / "a"), _tree(tmp_path / "b")
    (b / "Application" / "pkg" / "calc.py").write_bytes(b"X = 1\r\n")
    assert B.source_fingerprint(a) == B.source_fingerprint(b)


def test_without_git_the_fingerprint_alone_identifies_the_build(tmp_path):
    root = _tree(tmp_path / "a")
    info = B.build_info(root)
    assert info["git_commit"] is None and info["git_modified"] is None
    assert B.build_label(info) == f"qmap {__version__} / {info['cleaning_code_version']} build {info['source_fingerprint'][:12]}"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed on this computer")
def test_git_commit_and_modified_marker(tmp_path):
    root = _tree(tmp_path / "a")

    def git(*args):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    git("init", "-q")
    git("add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x")
    clean = B.build_info(root)
    assert len(clean["git_commit"]) == 40 and clean["git_modified"] is False
    assert B.build_label(clean).endswith(f"git {clean['git_commit'][:12]}")
    (root / "docs" / "guide.md").write_text("doc edit\n", encoding="utf-8")
    assert B.build_info(root)["git_modified"] is False  # documents are not program files
    (root / "Application" / "pkg" / "calc.py").write_text("X = 3\n", encoding="utf-8")
    edited = B.build_info(root)
    assert edited["git_modified"] is True and edited["git_commit"] == clean["git_commit"]
    assert B.build_label(edited).endswith("+modified")
    assert edited["source_fingerprint"] != clean["source_fingerprint"]


def test_every_run_record_carries_the_build(settings, db):
    run = start_run(settings, db, "FOUND", area="Ingestion", module_name="Foundation", params={})
    finish_run(run, "completed")
    row = db.one("SELECT code_version FROM runs WHERE run_id = ?", (run.run_id,))
    current = B.current_build()
    assert row["code_version"] == B.build_label(current) and current["source_fingerprint"][:12] in row["code_version"]
    manifest = json.loads(next(run.dir.glob("*manifest*.json")).read_text(encoding="utf-8"))
    assert manifest["build"]["source_fingerprint"] == current["source_fingerprint"]
