"""MA Affinity V2 release candidate - the END-TO-END WORKED EXAMPLE (10-Nov-26), executed through the real windows.

The same steps as the V1 worked example (test_beta_worked_example.py), with MA Affinity V2 (chance-tested) and its
default options: register the synthetic NSE_BETADEMO.csv in Database Manager; in the Workbench choose
**MA Affinity V2 (chance-tested)**, select NSE:BETADEMO, MA types `SMA,EMA`, check readiness, RUN ANALYSIS; check the
run record (analysis identity, chance-test settings and seed, library versions, warm-up); reproduce it from its Run ID
(a NEW run with identical result tables; the first run untouched).

The committed evidence in B.RELEASE_EVIDENCE/Worked_Example_Output_V2 is this test's own output and must come from a
clean checkout of exactly the program code under test. QMAP_WRITE_BETA_EVIDENCE=1 (re)writes it."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil

from qmap.storage.files import sha256_file

from fixtures import beta_example as B
from gui.test_two_applications import _select

OUT = B.RELEASE_EVIDENCE / "Worked_Example_Output_V2"
TABLES = ("MA_Affinity_V2_Candidates_", "MA_Affinity_V2_Chance_Shuffles_")


def _strip(text: str, run_ids) -> str:
    for r in run_ids:
        text = text.replace(r, "<RUN_ID>")
    return re.sub(r"\d{2}_[A-Z][a-z]{2}_\d{2}_\d{6}", "<STAMP>", text)


def test_the_v2_worked_example_runs_end_to_end_and_matches_the_committed_evidence(gui, world, tmp_path):
    folder = tmp_path / "Beta_Example"
    B.write(folder)
    source = (folder / B.NAME).read_bytes()

    dm = gui.start()
    gui.choose_folders(dm)
    dm.show("sources")
    sources = dm.screens["sources"]
    gui.dialogs.directories.append(str(folder))
    sources.add_button.invoke()
    sources.scan_button.invoke()
    gui.wait(lambda: not sources.running, timeout=120, app=dm)
    (state,) = list(sources.file_rows.values())
    dataset_id = state.dataset_ids[0]

    wb = gui.start(app_key="analytical_workbench")
    gui.choose_folders(wb)
    wb.show("analysis")
    screen = wb.screens["analysis"]
    names = [c.name for c in screen.choices]
    assert "MA Affinity (QLOPB)" in names and "MA Affinity V2 (chance-tested)" in names  # V1 stays available
    screen.analysis_combo.current(next(k for k, c in enumerate(screen.choices) if c.analysis_id == "ma_affinity_v2"))
    screen.on_analysis_selected()
    screen.refresh()
    _select(screen, dataset_id)
    screen.param_vars["ma_types"].set(B.PARAMS["ma_types"])
    screen.check()
    assert screen.last_readiness.ready, screen.readiness_box.get()
    screen.start_run()
    gui.wait(lambda: not screen.running and screen.last_result is not None, timeout=600, app=wb)
    run = screen.last_result
    assert run.ok, run.message
    assert run.run_id.startswith("MAA2_") and screen.stage_var.get() == "Finished"
    assert float(screen.progress.cget("value")) == float(screen.progress.cget("maximum"))  # full bar at the end

    meta = json.loads(run.metadata_path.read_text(encoding="utf-8"))
    assert meta["analysis_id"] == "ma_affinity_v2" and meta["analysis_version"] == 1
    assert meta["parameters"]["v2_settings"]["chance_shuffles"] == 200 and meta["parameters"]["v2_settings"]["chance_seed"] == 1
    assert meta["build"]["libraries"]["python"] and meta["build"]["libraries"]["numpy"]
    details = meta["analysis_details"]
    assert details["bars_used"]["count"] == 1500 and details["ma_warmup"]["bars_before_start"] == 0
    assert details["chance_test"]["shuffles"] == 200 and details["chance_test"]["block_bars"] == 15
    findings = next(run.run_dir.glob("MA_Affinity_V2_Findings_*.txt")).read_text(encoding="utf-8")
    assert "EXECUTIVE INTERPRETATION" in findings and "VERDICT: " + details["chance_test"]["verdict"] in findings

    first_files = {p.name: p.read_bytes() for p in run.run_dir.iterdir() if p.is_file()}
    screen.reproduce_button.invoke()
    gui.wait(lambda: not screen.running and screen.last_result is not run, timeout=600, app=wb)
    again = screen.last_result
    assert again.ok and again.run_id.startswith("MAA2_") and again.reproduction["identical"], again.message
    assert {p.name: p.read_bytes() for p in run.run_dir.iterdir() if p.is_file()} == first_files
    assert (folder / B.NAME).read_bytes() == source

    report = next(again.run_dir.glob("Reproducibility_Report_*.csv"))
    produced = {"Findings.txt": findings, "Run_Metadata.json": run.metadata_path.read_text(encoding="utf-8"),
                "Reproducibility_Report.csv": report.read_text(encoding="utf-8"),
                "Run_Log.txt": (run.run_dir / "run_log.txt").read_text(encoding="utf-8")}
    tables = {p + ".csv": next(run.run_dir.glob(p + "*.csv")).read_bytes() for p in TABLES}
    interactions_sha = sha256_file(next(run.run_dir.glob("MA_Affinity_V2_Interactions_*.csv")))
    if os.environ.get("QMAP_WRITE_BETA_EVIDENCE") == "1":
        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir(parents=True)
        for name, text in produced.items():
            (OUT / name).write_text(text, encoding="utf-8", newline="")
        for name, data in tables.items():
            (OUT / name.replace("_.csv", ".csv")).write_bytes(data)
        return
    B.check_evidence_provenance(json.loads((OUT / "Run_Metadata.json").read_text(encoding="utf-8")))
    for name, data in tables.items():
        assert (OUT / name.replace("_.csv", ".csv")).read_bytes() == data, name
    committed = json.loads((OUT / "Run_Metadata.json").read_text(encoding="utf-8"))
    assert committed["analysis_details"] == {**details, "engine": committed["analysis_details"]["engine"]}
    assert _strip((OUT / "Findings.txt").read_text(encoding="utf-8"), [committed["run_id"]]) == \
        _strip(findings, [run.run_id])
    rows = list(csv.reader((OUT / "Reproducibility_Report.csv").open(encoding="utf-8")))
    assert rows[-1][-1].startswith("REPRODUCED")
    assert any(r[0].startswith("Result table MA_Affinity_V2_Interactions_") and r[1].endswith(interactions_sha)
               for r in rows)
