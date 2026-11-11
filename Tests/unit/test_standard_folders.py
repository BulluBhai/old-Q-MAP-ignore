"""Automatic preparation of the standard folders (10-Nov-26 usability requirement 1).

Q-MAP_DATA and Q-MAP_OUTPUT belong side by side in the folder that holds the Q-MAP program folder. Preparing them
creates a missing folder (empty) and uses an existing one exactly as it is: nothing is deleted, moved, renamed, merged
or overwritten, and a problem is reported in plain English with nothing changed."""

from __future__ import annotations

from qmap_gui.services import prepare_standard_folders, standard_folders


def _tree(root):
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None) for p in sorted(root.rglob("*"))}


def test_missing_folders_are_created_next_to_the_program_folder(tmp_path):
    code = tmp_path / "Q-MAP_APP"
    code.mkdir()
    res = prepare_standard_folders(tmp_path, code)
    assert res.ok and res.created == ["Q-MAP_DATA", "Q-MAP_OUTPUT"] and res.existing == []
    assert res.data == tmp_path / "Q-MAP_DATA" and res.output == tmp_path / "Q-MAP_OUTPUT"
    assert res.data.is_dir() and res.output.is_dir() and not any(res.data.iterdir()) and not any(res.output.iterdir())
    assert "created Q-MAP_DATA and Q-MAP_OUTPUT" in res.describe()


def test_existing_folders_and_their_contents_are_used_as_they_are(tmp_path):
    code = tmp_path / "Q-MAP_APP"
    code.mkdir()
    (tmp_path / "Q-MAP_DATA" / "Metadata").mkdir(parents=True)
    (tmp_path / "Q-MAP_DATA" / "Metadata" / "qmap_metadata.sqlite").write_bytes(b"registry")
    (tmp_path / "Q-MAP_OUTPUT" / "Research_Reports" / "MAAF_1").mkdir(parents=True)
    (tmp_path / "Q-MAP_OUTPUT" / "Research_Reports" / "MAAF_1" / "results.csv").write_text("a,b\n1,2\n")
    before = _tree(tmp_path)
    res = prepare_standard_folders(tmp_path, code)
    assert res.ok and res.created == [] and res.existing == ["Q-MAP_DATA", "Q-MAP_OUTPUT"]
    assert _tree(tmp_path) == before  # nothing changed, added or removed
    assert "already there" in res.describe()


def test_one_missing_folder_is_created_and_the_other_kept(tmp_path):
    code = tmp_path / "Q-MAP_APP"
    code.mkdir()
    (tmp_path / "Q-MAP_DATA").mkdir()
    (tmp_path / "Q-MAP_DATA" / "keep.txt").write_text("mine")
    res = prepare_standard_folders(tmp_path, code)
    assert res.ok and res.created == ["Q-MAP_OUTPUT"] and res.existing == ["Q-MAP_DATA"]
    assert (tmp_path / "Q-MAP_DATA" / "keep.txt").read_text() == "mine"


def test_a_file_in_the_way_is_reported_and_nothing_is_changed(tmp_path):
    code = tmp_path / "Q-MAP_APP"
    code.mkdir()
    (tmp_path / "Q-MAP_OUTPUT").write_text("not a folder")
    before = _tree(tmp_path)
    res = prepare_standard_folders(tmp_path, code)
    assert not res.ok and "is a file, not a folder" in res.problem and "Nothing was changed" in res.problem
    assert _tree(tmp_path) == before  # Q-MAP_DATA was not created either: all or nothing


def test_folders_that_would_be_inside_the_program_folder_are_refused(tmp_path):
    res = prepare_standard_folders(tmp_path, tmp_path)  # program folder = the parent itself
    assert not res.ok and "inside the code folder" in res.problem
    assert not (tmp_path / "Q-MAP_DATA").exists() and not (tmp_path / "Q-MAP_OUTPUT").exists()


def test_a_folder_that_cannot_be_created_is_explained(tmp_path, monkeypatch):
    from pathlib import Path

    code = tmp_path / "Q-MAP_APP"
    code.mkdir()
    real = Path.mkdir

    def refuse(self, *a, **k):
        if self.name == "Q-MAP_OUTPUT":
            raise PermissionError("Access is denied")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "mkdir", refuse)
    res = prepare_standard_folders(tmp_path, code)
    assert not res.ok and "could not create the folder" in res.problem and "Access is denied" in res.problem
    assert "safely removed" in res.problem
    assert not (tmp_path / "Q-MAP_DATA").exists() and not (tmp_path / "Q-MAP_OUTPUT").exists()


def test_the_standard_paths(tmp_path):
    assert standard_folders(tmp_path) == (tmp_path.resolve() / "Q-MAP_DATA", tmp_path.resolve() / "Q-MAP_OUTPUT")



def test_failed_rollback_leaves_nonempty_new_folder_and_reports_partial_result(tmp_path, monkeypatch):
    from pathlib import Path

    code = tmp_path / "Q-MAP_APP"
    code.mkdir()
    data = tmp_path / "Q-MAP_DATA"
    real = Path.mkdir

    def fail_second_folder(self, *a, **k):
        if self.name == "Q-MAP_OUTPUT":
            # Simulate another process/user placing a file in the new folder before rollback.
            (data / "keep.txt").write_text("keep this file")
            raise PermissionError("Access is denied")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "mkdir", fail_second_folder)
    res = prepare_standard_folders(tmp_path, code)

    assert not res.ok
    assert "could not be safely removed" in res.problem and "left in place" in res.problem
    assert res.created == ["Q-MAP_DATA"]
    assert (data / "keep.txt").read_text() == "keep this file"
    assert not (tmp_path / "Q-MAP_OUTPUT").exists()



def test_failure_never_removes_or_changes_preexisting_user_folder(tmp_path, monkeypatch):
    from pathlib import Path

    code = tmp_path / "Q-MAP_APP"
    code.mkdir()
    data = tmp_path / "Q-MAP_DATA"
    data.mkdir()
    original = data / "keep.txt"
    original.write_text("existing user data")
    real = Path.mkdir

    def fail_output(self, *a, **k):
        if self.name == "Q-MAP_OUTPUT":
            raise PermissionError("Access is denied")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "mkdir", fail_output)
    res = prepare_standard_folders(tmp_path, code)

    assert not res.ok and "safely removed" in res.problem
    assert res.existing == ["Q-MAP_DATA"] and res.created == []
    assert original.read_text() == "existing user data"
    assert data.is_dir() and not (tmp_path / "Q-MAP_OUTPUT").exists()
