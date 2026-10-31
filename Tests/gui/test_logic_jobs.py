"""Pure-logic tests (no window) for the background ingest job."""

import logging
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Application"))

from fixtures.builders import write_delimited
from qmap.core.errors import IngestError
from qmap_gui import jobs, services
from qmap_gui.jobs import IngestJob

from gui.conftest import NET_HEADER, dd_mm_yy_rows


@pytest.fixture
def settings(world):
    return services.build_core_settings(str(world.data), str(world.output), REPO, world.settings / "profiles")


@pytest.fixture
def profile(settings):
    return next(i.profile for i in services.list_profiles(settings) if i.profile and i.profile.profile_id == "example_csv_dd_mm_yy")


def run_job(settings, files, profile, **kw):
    events = []
    job = IngestJob(settings, files, profile, emit=events.append, **kw)
    return job, job.run(), events


def types(events):
    return [e["type"] for e in events]


def test_full_run_reports_every_file_in_plain_terms(settings, world, profile):
    unsupported = world.src / "notes.json"
    unsupported.write_text("{}")
    job, summary, events = run_job(settings, [world.good, world.bad, unsupported], profile)
    assert summary.error is None and summary.run_id and summary.run_dir.is_dir()
    assert [o.outcome for o in summary.outcomes] == ["accepted", "rejected", "unsupported"]
    assert [o.label for o in summary.outcomes] == ["Accepted", "Rejected - see problems", "File type not supported"]
    assert summary.counts() == {"accepted": 1, "rejected": 1, "unsupported": 1}
    assert summary.rows_total == 24  # rows read from the two readable files
    good, bad, _ = summary.outcomes
    assert good.datasets and good.rows_read == 12 and good.ok
    assert not bad.ok and bad.issues_report and bad.issues_report.is_file() and bad.rows_flagged == 2
    assert "Problems:" in bad.message and any(f.severity == "error" for f in bad.findings)


def test_event_sequence_and_content(settings, world, profile):
    job, summary, events = run_job(settings, [world.good, world.bad], profile)
    t = types(events)
    assert t[0] == "stage" and t.count("run_started") == 1 and t.count("file_start") == 2 and t.count("file_done") == 2
    assert t[-1] == "done" and events[-1]["summary"] is summary
    assert t.index("run_started") < t.index("file_start") < t.index("file_done")
    started = next(e for e in events if e["type"] == "run_started")
    assert Path(started["run_dir"]).is_dir() and started["run_id"].startswith("FOUND_")
    logs = [e["text"] for e in events if e["type"] == "log"]
    assert any("Receipt" in line for line in logs) and any("REJECTED" in line for line in logs)


def test_results_are_saved_outside_the_repository(settings, world, profile):
    _, summary, _ = run_job(settings, [world.good, world.bad], profile)
    assert world.output.resolve() in summary.run_dir.parents
    assert REPO not in summary.run_dir.parents
    assert (summary.run_dir / "run_manifest.json").is_file()


def test_loading_the_same_file_again_says_so(settings, world, profile):
    run_job(settings, [world.good], profile)
    _, summary, _ = run_job(settings, [world.good], profile)
    assert summary.outcomes[0].outcome == "reused" and summary.outcomes[0].label == "Already loaded (nothing new)"
    assert summary.outcomes[0].ok


def test_retrying_an_unchanged_rejected_file_is_blocked_and_explained(settings, world, profile):
    run_job(settings, [world.bad], profile)
    _, summary, _ = run_job(settings, [world.bad], profile)
    out = summary.outcomes[0]
    assert out.outcome == "blocked" and "retry" in out.message.lower()


def test_log_handler_is_removed_after_the_run(settings, world, profile):
    logger = logging.getLogger("qmap")
    before = list(logger.handlers)
    run_job(settings, [world.good], profile)
    assert list(logger.handlers) == before


def test_cancel_stops_after_the_current_file(settings, world, profile):
    files = [write_delimited(world.src / f"NSE_FILE{i}_1D.csv", NET_HEADER, dd_mm_yy_rows(8, i)) for i in range(1, 6)]
    events = []
    job = IngestJob(settings, files, profile, emit=events.append)
    original = job.emit

    def watcher(event):
        original(event)
        if event["type"] == "file_done" and event["index"] == 2:
            job.cancel()

    job.emit = watcher
    summary = job.run()
    assert summary.cancelled and len(summary.outcomes) == 2
    assert any("Cancelled by you" in e.get("text", "") for e in events)
    assert types(events)[-1] == "done"


def test_one_unexpected_error_does_not_stop_the_other_files(settings, world, profile, monkeypatch):
    real = jobs.ingest_file
    calls = {"n": 0}

    def flaky(run, path, prof, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("disk exploded")
        return real(run, path, prof, **kw)

    monkeypatch.setattr(jobs, "ingest_file", flaky)
    _, summary, _ = run_job(settings, [world.bad, world.good], profile)
    assert [o.outcome for o in summary.outcomes] == ["failed", "accepted"]
    assert "disk exploded" in summary.outcomes[0].message and "Unexpected problem" in summary.outcomes[0].message


def test_foundation_errors_are_shown_without_codes(settings, world, profile, monkeypatch):
    def refuse(*a, **k):
        raise IngestError("The profile changed.", code="E_PROFILE_CHANGED", action="Raise profile_version.")

    monkeypatch.setattr(jobs, "ingest_file", refuse)
    _, summary, _ = run_job(settings, [world.good], profile)
    msg = summary.outcomes[0].message
    assert "E_PROFILE_CHANGED" not in msg and "Raise profile_version" in msg


def test_setup_failure_is_reported_in_the_summary(settings, world, profile, monkeypatch):
    def broken(*a, **k):
        raise IngestError("The registry file cannot be opened.", code="E_X", action="Check the folder.")

    monkeypatch.setattr(jobs, "open_database", broken)
    _, summary, events = run_job(settings, [world.good], profile)
    assert summary.error == "The registry file cannot be opened. Check the folder." and not summary.outcomes
    assert types(events)[-1] == "done"


def test_the_job_talks_only_through_the_emit_callback_from_a_worker_thread(settings, world, profile):
    seen_threads, events = set(), []

    def emit(event):
        seen_threads.add(threading.current_thread().name)
        events.append(event)

    job = IngestJob(settings, [world.good], profile, emit=emit)
    t = threading.Thread(target=job.run, name="qmap-worker")
    t.start()
    t.join(30)
    assert not t.is_alive() and seen_threads == {"qmap-worker"} and types(events)[-1] == "done"


def test_request_values_reach_the_foundation(settings, world):
    p = next(i.profile for i in services.list_profiles(settings) if i.profile and i.profile.profile_id == "example_text_headered_iso_date")
    f = write_delimited(world.src / "odd_name.txt", ["date", "open", "high", "low", "close", "Volume"],
                        [[r[0], *r[1:6]] for r in __import__("fixtures.builders", fromlist=["daily_rows"]).daily_rows(8)])
    _, summary, _ = run_job(settings, [f], p)
    assert summary.outcomes[0].outcome == "rejected"  # exchange/symbol not supplied: never guessed
    _, summary, _ = run_job(settings, [f], p, exchange="nse", symbol="demo", source_label="vendor", note="n")
    assert summary.outcomes[0].outcome == "accepted"
