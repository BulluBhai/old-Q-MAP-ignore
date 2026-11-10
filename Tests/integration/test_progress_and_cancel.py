"""Workbench progress and Cancel (10-Nov-26; from the MA Affinity V2 merge package, batch 3, adapted to V1 for PR A).

- A cancelled run is closed with status 'cancelled' (not 'failed'), writes no result tables, returns outcome
  'cancelled' and cannot be reproduced (only completed runs can); V1 stops on request, and so does a reproduction.
- Progress counts rise to exactly the total, for V1 (QLOPB's two phases shown as one count) plus one final step for the
  reports and run record, so the count reaches its total only when the run has really finished.
- The job sends at most one progress event per 0.2 s (plus the first and last), so the screen is never flooded.
"""

from __future__ import annotations

from datetime import date

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from fixtures.profiles import do_ingest
from qmap.analytical_engine import MA_AFFINITY, run_analysis
from qmap.analytical_engine.reproduce import reproduce_run
from qmap.core.errors import RunCancelled
from qmap.core.runs import run_context
from qmap_gui import workbench_services as ws

SMALL = {"ma_start": "5", "ma_end": "40", "min_interactions": "5", "fwd_windows": "3,5,10", "regime_ma": "20"}


@pytest.fixture
def dataset(run, src):
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(600, date(2021, 1, 4)), ohlcv(600, seed=7, base=300.0))]
    return do_ingest(run, write_delimited(src / "NSE_PROGRESS.csv", HEADER, rows)).dataset_ids[0]


def _status(db, run_id):
    return db.one("SELECT status, error_message FROM runs WHERE run_id = ?", (run_id,))


def test_run_context_records_a_cancelled_run_as_cancelled(settings, db):
    with pytest.raises(RunCancelled):
        with run_context(settings, db, "TEST", area="Research_Reports") as run:
            raise RunCancelled("Cancelled by the user.")
    row = _status(db, run.run_id)
    assert row["status"] == "cancelled" and row["error_message"] == "Cancelled by the user."


def test_cancel_stops_the_analysis_and_records_it(settings, db, dataset):
    calls = {"n": 0}

    def cancel():  # let a few steps run, then ask to stop
        calls["n"] += 1
        return calls["n"] > 5

    before = {r["run_id"] for r in db.query("SELECT run_id FROM runs")}
    res = run_analysis(settings, db, MA_AFFINITY, [dataset], SMALL, cancel=cancel)
    assert res.outcome == "cancelled" and not res.ok and res.run_id and res.run_id not in before
    assert _status(db, res.run_id)["status"] == "cancelled"
    assert not [p for p in res.run_dir.iterdir()  # no results and no Run_Metadata (only the run log and manifest)
                if p.suffix in (".csv", ".xlsx", ".pdf", ".png") or p.name.startswith("Run_Metadata")]
    n_runs = len(db.query("SELECT run_id FROM runs"))
    refused = reproduce_run(settings, db, res.run_id)  # a cancelled run is not a research result: not reproducible
    assert refused.outcome == "blocked" and not refused.run_id and len(db.query("SELECT run_id FROM runs")) == n_runs


def test_progress_counts_rise_to_the_total_only_at_the_end(settings, db, dataset):
    seen = []
    res = run_analysis(settings, db, MA_AFFINITY, [dataset], SMALL, progress=lambda d, t, m: seen.append((d, t, m)))
    assert res.ok, res.message
    totals = {t for _, t, _ in seen}
    assert len(totals) == 1
    total = totals.pop()
    dones = [d for d, _, _ in seen]
    assert dones == sorted(dones) and 0 <= dones[0] < total
    n = 36  # periods 5..40, SMA only
    assert total == n + 5 + 1  # in-sample, out-of-sample Top-5, then the reports and run record
    assert [d for d in dones if d == total] == [total]  # the total is reached once: after everything was written
    assert seen[-1] == (total, total, "Reports and run record written")
    assert any(m.startswith("In-sample") for _, _, m in seen) and any(m.startswith("Out-of-sample") for _, _, m in seen)


def test_a_reproduction_reports_progress_and_can_be_cancelled(settings, db, dataset):
    first = run_analysis(settings, db, MA_AFFINITY, [dataset], SMALL)
    seen = []
    again = reproduce_run(settings, db, first.run_id, progress=lambda d, t, m: seen.append((d, t)))
    assert again.ok and again.reproduction["identical"] and seen[-1][0] == seen[-1][1]
    stopped = reproduce_run(settings, db, first.run_id, cancel=lambda: True)
    assert stopped.outcome == "cancelled" and _status(db, stopped.run_id)["status"] == "cancelled"
    assert _status(db, first.run_id)["status"] == "completed"  # the earlier run is untouched


def test_the_job_throttles_progress_events(monkeypatch):
    clock = {"t": 0.0}
    monkeypatch.setattr(ws.time, "monotonic", lambda: clock["t"])
    events = []
    tick = ws._Ticker(events.append)
    for i in range(1001):
        clock["t"] = i * 0.001  # 1000 steps in one second
        tick(i, 1000, f"step {i}")
    dones = [e["done"] for e in events]
    assert dones[0] == 0 and dones[-1] == 1000 and len(events) <= 8
    job = ws.AnalysisJob(None, "ma_affinity", [], {})
    assert not job.cancel_event.is_set()
    job.cancel()
    assert job.cancel_event.is_set()


# ---- MA Affinity V2 (merge package patch 0003, V2 part) ------------------------------------------------------------
def test_v2_cancel_stops_the_run_and_records_it(settings, db, dataset):
    from qmap.analytical_engine import MA_AFFINITY_V2

    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return calls["n"] > 60  # inside the chance test

    res = run_analysis(settings, db, MA_AFFINITY_V2, [dataset], {**SMALL, "chance_shuffles": "50"}, cancel=cancel)
    assert res.outcome == "cancelled" and _status(db, res.run_id)["status"] == "cancelled"
    assert not [p for p in res.run_dir.iterdir() if p.suffix in (".csv", ".xlsx", ".pdf", ".png")]


def test_v2_progress_counts_every_shuffle_and_ends_at_the_total(settings, db, dataset):
    from qmap.analytical_engine import MA_AFFINITY_V2

    seen = []
    res = run_analysis(settings, db, MA_AFFINITY_V2, [dataset], {**SMALL, "chance_shuffles": "7"},
                       progress=lambda d, t, m: seen.append((d, t, m)))
    assert res.ok, res.message
    (total,) = {t for _, t, _ in seen}
    n = 36
    assert total == n + 7 * n + 5 + 1  # in-sample, 7 full re-scans, out-of-sample Top-5, reports and record
    dones = [d for d, _, _ in seen]
    assert dones == sorted(dones) and [d for d in dones if d == total] == [total]
    assert any(m.startswith("Chance test: shuffle 7 of 7") for _, _, m in seen)


def test_progress_completion_follows_successful_run_finalisation(settings, db, dataset, monkeypatch):
    import qmap.core.runs as runs
    actual_finish = runs.finish_run
    events = []
    state = {"finished": False}

    def observed_finish(run, status="completed", error=None):
        path = actual_finish(run, status, error)
        state["finished"] = run.finished
        return path

    monkeypatch.setattr(runs, "finish_run", observed_finish)

    def progress(done, total, message):
        if done == total:
            events.append((message, state["finished"]))

    result = run_analysis(settings, db, MA_AFFINITY, [dataset], SMALL, progress=progress)
    assert result.ok, result.message
    assert events == [("Reports and run record written", True)]
    assert _status(db, result.run_id)["status"] == "completed"


def test_finalisation_failure_never_emits_success_completion(settings, db, dataset, monkeypatch):
    import qmap.core.runs as runs
    actual_finalise = runs._finish

    def fail_finalise(run, status, error):
        if status == "completed":
            raise OSError("simulated output-hashing/finalisation failure")
        return actual_finalise(run, status, error)

    # Exercise the real finish_run wrapper, including its liveness-lock release in finally.
    monkeypatch.setattr(runs, "_finish", fail_finalise)
    events = []
    result = run_analysis(settings, db, MA_AFFINITY, [dataset], SMALL,
                          progress=lambda done, total, message: events.append((done, total, message)))
    assert result.outcome == "failed"
    assert not any(done == total for done, total, _ in events)


def test_cancelled_run_never_emits_success_completion(settings, db, dataset):
    events = []
    result = run_analysis(settings, db, MA_AFFINITY, [dataset], SMALL, cancel=lambda: True,
                          progress=lambda done, total, message: events.append((done, total, message)))
    assert result.outcome == "cancelled"
    assert not any(done == total for done, total, _ in events)


def test_v2_no_ranked_candidate_skips_chance_test_in_production_outputs(settings, db, dataset):
    import csv
    import json
    import math
    import openpyxl
    from qmap.analytical_engine import MA_AFFINITY_V2

    # Force the real engine's candidate-ranking phase to reject every MA candidate.
    params = {**SMALL, "min_interactions": "9999", "chance_shuffles": "7"}
    res = run_analysis(settings, db, MA_AFFINITY_V2, [dataset], params)
    assert res.ok, res.message

    metadata = json.loads(res.metadata_path.read_text(encoding="utf-8"))
    chance = metadata["analysis_details"]["chance_test"]
    assert chance["status"] == "no_candidate"
    assert chance["test_run"] is False
    assert chance["verdict"] == "NO RANKED CANDIDATE - CHANCE TEST SKIPPED"
    assert chance["requested_shuffles"] == 7
    assert chance["attempted_shuffles"] == 0
    assert chance["valid_shuffles"] == 0
    assert chance["invalid_shuffles"] == 0
    assert chance["unattempted_shuffles"] == 7
    assert math.isnan(chance["p_value"]) if isinstance(chance["p_value"], float) else chance["p_value"] is None

    findings = next(res.run_dir.glob("MA_Affinity_V2_Findings_*.txt")).read_text(encoding="utf-8")
    assert "Chance test was NOT RUN" in findings
    assert "7 shuffles were requested, but zero were attempted" in findings
    assert "VERDICT: NO RANKED CANDIDATE" in findings

    with next(res.run_dir.glob("MA_Affinity_V2_Candidates_*.csv")).open(encoding="utf-8", newline="") as handle:
        candidate_rows = list(csv.DictReader(handle))
    assert candidate_rows
    assert all(row["chance_status"] == "no_candidate" for row in candidate_rows)
    assert all(row["chance_verdict"] == "NO RANKED CANDIDATE - CHANCE TEST SKIPPED" for row in candidate_rows)
    assert all(row["chance_test_run"] in ("False", "false", "0") for row in candidate_rows)
    assert all(row["chance_p"] in ("", "nan", "NaN") for row in candidate_rows)

    with next(res.run_dir.glob("MA_Affinity_V2_Chance_Shuffles_*.csv")).open(encoding="utf-8", newline="") as handle:
        shuffle_rows = list(csv.DictReader(handle))
    assert len(shuffle_rows) == 1
    assert shuffle_rows[0]["status"] == "no_candidate"
    assert shuffle_rows[0]["test_run"] in ("False", "false", "0")
    assert shuffle_rows[0]["requested_shuffles"] == "7"
    assert shuffle_rows[0]["attempted_shuffles"] == "0"
    assert shuffle_rows[0]["valid_shuffles"] == "0"
    assert shuffle_rows[0]["invalid_shuffles"] == "0"
    assert shuffle_rows[0]["unattempted_shuffles"] == "7"

    workbook = openpyxl.load_workbook(next(res.run_dir.glob("MA_Affinity_V2_*.xlsx")), read_only=True)
    summary = list(workbook["Summary"].values)
    summary_text = " ".join(str(cell) for row in summary for cell in row if cell is not None)
    assert "no_candidate" in summary_text and "0 / 0 / 0 / 0 / 7" in summary_text
    chance_tab = list(workbook["Chance_Test"].values)
    chance_text = " ".join(str(cell) for row in chance_tab for cell in row if cell is not None)
    assert "no_candidate" in chance_text and "7" in chance_text and "not run" in chance_text.lower()

    # The PDF must not claim that the requested shuffles actually ran.
    from pypdf import PdfReader
    pdf = PdfReader(str(next(res.run_dir.glob("MA_Affinity_V2_Report_*.pdf"))))
    pdf_text = " ".join(page.extract_text() or "" for page in pdf.pages)
    assert "no_candidate" in pdf_text
    assert "7/0/0/0/7" in pdf_text
    assert "no chance-test shuffles were run" in pdf_text
