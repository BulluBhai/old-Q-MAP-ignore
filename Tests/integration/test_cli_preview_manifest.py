"""Command line, dry-run preview and run manifests with ingestion."""

import json

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import make_profile, profile_text
from qmap.cli import main
from qmap.core.runs import finish_run, run_context, start_run
from qmap.data_engine.ingest import ingest_file
from qmap.data_engine.preview import preview_file
from qmap.storage.files import sha256_file

ROWS = daily_rows(8)


@pytest.fixture
def config_file(roots, tmp_path):
    cfg = tmp_path / "qmap.local.toml"
    cfg.write_text(f'[paths]\ndata_root = "{roots["data"].as_posix()}"\noutput_root = "{roots["output"].as_posix()}"\n')
    return cfg


@pytest.fixture
def profile_file(tmp_path):
    p = tmp_path / "cli_profile.toml"
    p.write_text(profile_text(profile_id="cli_profile"))
    return p


def files_under(root):
    return sorted(p for p in root.rglob("*") if p.is_file())


# ---- preview: registers nothing and writes nothing -------------------------------------------------------
def test_preview_changes_nothing_on_disk(src, settings, roots):
    p = write_delimited(src / "pv.csv", HEADER, ROWS)
    before = (files_under(roots["data"]), files_under(roots["output"]))
    text = preview_file(p, make_profile(), settings)
    after = (files_under(roots["data"]), files_under(roots["output"]))
    assert before == after
    assert "WOULD BE ACCEPTED" in text and "Rows: 8" in text and "Detected format: delimited_text" in text
    assert "ISO dates" in text and "Suggested delimiter" in text and "looks like a header" in text


def test_preview_explains_why_a_file_would_be_rejected(src, settings):
    rows = [list(r) for r in ROWS]
    rows[1][3] = 999
    text = preview_file(write_delimited(src / "bad.csv", HEADER, rows), make_profile(), settings)
    assert "WOULD BE REJECTED" in text and "low_le_open_close" in text


def test_preview_without_a_profile_gives_suggestions_not_decisions(src):
    rows = [[int(1738381500 + 86400 * i)] + r[1:] for i, r in enumerate(ROWS)]
    text = preview_file(write_delimited(src / "u.csv", HEADER + ["Net Volume"], [r + [1] for r in rows]))
    assert "Unix seconds" in text and "suggestions only" in text and "Volume-like columns" in text


def test_preview_reports_unsupported_files(src):
    p = src / "x.json"
    p.write_text("{}")
    assert "JSON" in preview_file(p)


# ---- command line ----------------------------------------------------------------------------------------
def test_cli_ingest_preview_recover_verify(src, config_file, profile_file, roots, capsys):
    p = write_delimited(src / "cli.csv", HEADER, ROWS)
    assert main(["--config", str(config_file), "preview", "--profile", str(profile_file), str(p)]) == 0
    assert "WOULD BE ACCEPTED" in capsys.readouterr().out
    assert main(["--config", str(config_file), "ingest", "--profile", str(profile_file), "--note", "n1", str(p)]) == 0
    out = capsys.readouterr().out
    assert "ACCEPTED" in out and "Run FOUND_" in out
    assert main(["--config", str(config_file), "ingest", "--profile", str(profile_file), str(p)]) == 0
    assert "REUSED" in capsys.readouterr().out
    assert main(["--config", str(config_file), "recover"]) == 0
    assert main(["--config", str(config_file), "verify"]) == 0
    assert "verify:" in capsys.readouterr().out


def test_cli_exit_code_and_report_for_a_rejected_file(src, config_file, profile_file, capsys):
    rows = [list(r) for r in ROWS]
    rows[0][3] = 999
    p = write_delimited(src / "badcli.csv", HEADER, rows)
    assert main(["--config", str(config_file), "ingest", "--profile", str(profile_file), str(p)]) == 1
    out = capsys.readouterr().out
    assert "REJECTED" in out and "issues report" in out


def test_cli_reports_configuration_problems_clearly(src, tmp_path, profile_file, capsys):
    bad = tmp_path / "nothing.toml"
    assert main(["--config", str(bad), "verify"]) == 2
    assert "Configuration file not found" in capsys.readouterr().err


def test_cli_reports_an_unknown_profile(src, config_file, capsys):
    assert main(["--config", str(config_file), "ingest", "--profile", "no_such_profile", str(src / "x.csv")]) == 2
    assert "was not found" in capsys.readouterr().err


def test_cli_unsupported_file_is_a_failure_exit(src, config_file, profile_file, capsys):
    p = src / "z.json"
    p.write_text("{}")
    assert main(["--config", str(config_file), "ingest", "--profile", str(profile_file), str(p)]) == 1
    assert "UNSUPPORTED" in capsys.readouterr().out


# ---- manifests -------------------------------------------------------------------------------------------
def test_manifest_lists_inputs_outputs_and_the_issue_report(src, settings, db):
    good = write_delimited(src / "g.csv", HEADER, ROWS)
    rows = [list(r) for r in ROWS]
    rows[2][3] = 999
    bad = write_delimited(src / "b.csv", HEADER, rows)
    with run_context(settings, db, "FOUND", area="Ingestion", params={"files": 2}) as run:
        ingest_file(run, good, make_profile())
        b = ingest_file(run, bad, make_profile(profile_id="other"))
    m = json.loads((run.dir / "run_manifest.json").read_text())
    assert m["status"] == "completed" and m["parameters"] == {"files": 2}
    assert {i["dataset_id"] for i in m["input_datasets"]} == {r["dataset_id"] for r in db.query(
        "SELECT dataset_id FROM datasets WHERE layer='raw'")}
    out = {o["relative_path"]: o for o in m["outputs"]}
    report = f"issues_event{b.event_id}.csv"
    assert report in out and out[report]["sha256"] == sha256_file(run.dir / report)
    assert "run_log.txt" in out
    log = (run.dir / "run_log.txt").read_text()
    assert run.run_id in log and "Ingest REJECTED" in log and "Ingest accepted" in log
    rel = run.relative_dir
    stored = {r["relative_path"] for r in db.query("SELECT relative_path FROM run_outputs WHERE run_id=?", (run.run_id,))}
    assert f"{rel}/{report}" in stored and f"{rel}/run_manifest.json" in stored


def test_receipts_and_attempts_are_tied_to_their_run(src, settings, db):
    p = write_delimited(src / "r.csv", HEADER, ROWS)
    r1 = start_run(settings, db, "FOUND", area="Ingestion")
    ingest_file(r1, p, make_profile())
    finish_run(r1)
    r2 = start_run(settings, db, "FOUND", area="Ingestion")
    ingest_file(r2, p, make_profile())
    finish_run(r2)
    ev = db.query("SELECT run_id FROM ingest_events ORDER BY event_id")
    assert [e["run_id"] for e in ev] == [r1.run_id, r2.run_id]
    assert [a["run_id"] for a in db.query("SELECT run_id FROM ingest_attempts ORDER BY attempt_id")] == [r1.run_id, r2.run_id]
