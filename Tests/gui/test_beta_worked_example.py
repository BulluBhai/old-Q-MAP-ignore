"""MA Affinity beta - the END-TO-END WORKED EXAMPLE (T10, 09-Nov-26), executed through the real windows.

It does exactly what the owner's acceptance guide asks, with the synthetic file NSE_BETADEMO.csv:
  1. Database Manager > Sources: add the folder, scan; the file is registered as NSE:BETADEMO 1 day (a dataset);
  2. Analytical Workbench: choose MA Affinity (QLOPB), select NSE:BETADEMO, type MA types `SMA,EMA`, check readiness
     (READY), RUN ANALYSIS;
  3. check the run: Run ID, the in-sample/out-of-sample split, the findings file, Run_Metadata (dataset identity and
     checksum, parameters as entered, code build, provenance);
  4. Reproduce the run from its Run ID: a NEW run whose result tables are identical; the first run is untouched.
The committed evidence in docs/acceptance_testing/beta_ma_affinity_09_Nov_26/Worked_Example_Output/ is this test's
own output; the test checks that a fresh run gives the same result tables and the same findings (apart from the Run
ID and the date in file names). Set QMAP_WRITE_BETA_EVIDENCE=1 to rewrite that folder from a fresh run."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
from datetime import datetime

from qmap.storage.files import sha256_file

from fixtures import beta_example as B
from gui.test_two_applications import _select

OUT = B.EVIDENCE / "Worked_Example_Output"


def _strip(text: str, run_ids) -> str:
    for r in run_ids:
        text = text.replace(r, "<RUN_ID>")
    return re.sub(r"\d{2}_[A-Z][a-z]{2}_\d{2}_\d{6}", "<STAMP>", text)


def test_the_worked_example_runs_end_to_end_and_matches_the_committed_evidence(gui, world, tmp_path):
    folder = tmp_path / "Beta_Example"
    B.write(folder)
    assert (folder / B.NAME).read_bytes() == (B.EVIDENCE / B.NAME).read_bytes()  # the committed file is the generator's
    source_sha = (folder / B.NAME).read_bytes()

    # 1. Database Manager: add the folder and scan
    dm = gui.start()
    gui.choose_folders(dm)
    dm.show("sources")
    sources = dm.screens["sources"]
    gui.dialogs.directories.append(str(folder))
    sources.add_button.invoke()
    sources.scan_button.invoke()
    gui.wait(lambda: not sources.running, timeout=120, app=dm)
    gui.pump(0.2, dm)
    (state,) = list(sources.file_rows.values())
    assert state.outcome == "imported" and state.dataset_ids, state.detail
    dataset_id = state.dataset_ids[0]

    # 2. Analytical Workbench: choose MA Affinity, select the dataset, enter the parameter, check, run
    wb = gui.start(app_key="analytical_workbench")
    gui.choose_folders(wb)
    wb.show("analysis")
    screen = wb.screens["analysis"]
    screen.analysis_combo.current(next(k for k, c in enumerate(screen.choices) if c.analysis_id == "ma_affinity"))
    screen.on_analysis_selected()
    screen.refresh()
    _select(screen, dataset_id)
    screen.param_vars["ma_types"].set(B.PARAMS["ma_types"])
    screen.check()
    assert screen.last_readiness.ready, screen.readiness_box.get()
    screen.start_run()
    gui.wait(lambda: not screen.running and screen.last_result is not None, timeout=300, app=wb)
    run = screen.last_result
    assert run.ok, run.message
    assert run.run_id.startswith("MAAF_") and screen.reproduce_var.get() == run.run_id

    # 3. what the run recorded
    meta = json.loads(run.metadata_path.read_text(encoding="utf-8"))
    d = meta["input_datasets"][0]
    assert d["instrument"] == B.INSTRUMENT and d["timeframe"] == "1D" and len(d["sha256"]) == 64 and d["lineage"]
    assert meta["raw_parameters"]["ma_types"] == "SMA,EMA" and meta["build"]["source_fingerprint"]
    details = meta["analysis_details"]
    assert details["bars_used"]["count"] == 1500
    assert details["split"]["is_bars"] == 1050 and details["split"]["oos_bars"] == 450  # 70 % in-sample
    parse = lambda t: datetime.strptime(t, "%d-%b-%y")  # noqa: E731
    assert parse(details["split"]["is_last"]) < parse(details["split"]["oos_first"])
    findings = next(run.run_dir.glob("MA_Affinity_Findings_*.txt")).read_text(encoding="utf-8")
    assert all(label in findings for label in details["frozen_top"])

    # 4. reproduce from the Run ID
    first_files = {p.name: p.read_bytes() for p in run.run_dir.iterdir() if p.is_file()}
    screen.reproduce_button.invoke()
    gui.wait(lambda: not screen.running and screen.last_result is not run, timeout=300, app=wb)
    again = screen.last_result
    assert again.ok and again.run_id != run.run_id and again.reproduction["identical"], again.message
    assert screen.final_label.cget("text").startswith(f"REPRODUCED: every result table is identical to run {run.run_id}")
    assert {p.name: p.read_bytes() for p in run.run_dir.iterdir() if p.is_file()} == first_files  # untouched
    assert (folder / B.NAME).read_bytes() == source_sha  # the source file was only read

    report = next(again.run_dir.glob("Reproducibility_Report_*.csv"))
    produced = {"Findings.txt": findings, "Run_Metadata.json": run.metadata_path.read_text(encoding="utf-8"),
                "Reproducibility_Report.csv": report.read_text(encoding="utf-8"),
                "Run_Log.txt": (run.run_dir / "run_log.txt").read_text(encoding="utf-8")}
    tables = {"MA_Affinity_Candidates_.csv": next(run.run_dir.glob("MA_Affinity_Candidates_*.csv")).read_bytes()}
    interactions_sha = sha256_file(next(run.run_dir.glob("MA_Affinity_Interactions_*.csv")))  # 2.6 MB: hash only
    if os.environ.get("QMAP_WRITE_BETA_EVIDENCE") == "1":
        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir(parents=True)
        for name, text in produced.items():
            (OUT / name).write_text(text, encoding="utf-8", newline="")
        for name, data in tables.items():
            (OUT / name.replace("_.csv", ".csv")).write_bytes(data)
        return
    # the committed evidence is what this run produced: identical result tables, identical findings and frozen Top-N
    for name, data in tables.items():
        assert (OUT / name.replace("_.csv", ".csv")).read_bytes() == data, name
    committed_meta = json.loads((OUT / "Run_Metadata.json").read_text(encoding="utf-8"))
    assert committed_meta["analysis_details"] == {**details, "engine": committed_meta["analysis_details"]["engine"]}
    # the registered file's checksum changes with each registration (it records when it was made), so the dataset is
    # compared by what it holds: the same source file (checked above), rows and date range
    for k in ("instrument", "timeframe", "row_count", "date_from", "date_to"):
        assert committed_meta["input_datasets"][0][k] == d[k], k
    old_ids = [committed_meta["run_id"]]
    assert _strip((OUT / "Findings.txt").read_text(encoding="utf-8"), old_ids) == _strip(findings, [run.run_id])
    rows = list(csv.reader((OUT / "Reproducibility_Report.csv").open(encoding="utf-8")))
    assert rows[-1][-1].startswith("REPRODUCED")
    # the committed report records the interactions table's checksum; a fresh run gives the same table
    assert any(r[0].startswith("Result table MA_Affinity_Interactions_") and r[1].endswith(interactions_sha) for r in rows)
