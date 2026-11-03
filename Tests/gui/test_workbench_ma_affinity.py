"""Real-window tests: MA Affinity (QLOPB) in the Analytical Workbench."""

from __future__ import annotations

import pytest

from datetime import date, datetime

from fixtures.builders import daily_rows, write_delimited
from gui.conftest import NET_HEADER
from gui.test_two_applications import REPO, _prepare, _select


def _prepare_long(world, n=700):
    from qmap.core.runs import run_context
    from qmap.data_engine.ingest import ingest_file
    from qmap.storage.db import open_database
    from qmap_gui.services import build_core_settings, list_profiles

    rows = [[datetime.fromisoformat(r[0]).strftime("%d-%m-%y")] + r[1:] + [r[5] // 3]
            for r in daily_rows(n, seed=4, start=date(2023, 1, 2))]  # all in the past (future dates are rejected)
    path = write_delimited(world.src / "NSE_LONGMA_1D.csv", NET_HEADER, rows)
    settings = build_core_settings(str(world.data), str(world.output), REPO)
    profile = next(p.profile for p in list_profiles(settings) if p.profile and p.profile.profile_id == "csv_hdr_ddmmyy_idfromname")
    db = open_database(settings.db_path)
    try:
        with run_context(settings, db, "FOUND", area="Ingestion") as run:
            res = ingest_file(run, path, profile)
        assert res.outcome == "accepted", res.message
        return res.dataset_ids[0]
    finally:
        db.close()


@pytest.fixture
def ma(gui, world):
    ids = {"short": _prepare(world), "long": _prepare_long(world)}
    app = gui.start(app_key="analytical_workbench")
    gui.choose_folders(app)
    app.show("analysis")
    screen = app.screens["analysis"]
    i = next(k for k, c in enumerate(screen.choices) if c.analysis_id == "ma_affinity")
    screen.analysis_combo.current(i)
    screen.on_analysis_selected()
    gui.pump(0.2)
    return screen, ids


def test_ma_affinity_is_offered_with_its_defaults_shown(ma):
    screen, _ = ma
    assert screen.choice.name == "MA Affinity (QLOPB)"
    assert screen.param_vars["ma_start"].get() == "10" and screen.param_vars["ma_end"].get() == "250"
    assert screen.param_vars["fwd_windows"].get() == "5,10,20,50" and screen.param_vars["ma_types"].get() == "SMA"
    assert screen.param_vars["date_from"].get() == ""
    assert "pending owner review" in screen.about.cget("text")


def test_a_too_short_dataset_is_explained_and_not_started(ma, gui):
    screen, ids = ma
    _select(screen, ids["short"])
    screen.start_run()
    gui.pump(0.3)
    assert not screen.running and screen.final_label.cget("text").startswith("Not started")
    assert screen.last_readiness is not None and not screen.last_readiness.ready
    assert any(f.name == "ma_affinity_history" for r in screen.last_readiness.reports for f in r.failures)


def test_invalid_weights_are_reported_as_parameters(ma, gui):
    screen, ids = ma
    _select(screen, ids["long"])
    screen.param_vars["w_forward"].set("nan")
    screen.start_run()
    gui.pump(0.3)
    assert screen.final_label.cget("text") == "Not started: the parameters are not valid (see the readiness box)."
    assert any("finite" in p for p in screen.last_readiness.parameter_problems)


def test_a_run_completes_and_writes_the_reports(ma, gui):
    screen, ids = ma
    _select(screen, ids["long"])
    screen.param_vars["ma_end"].set("60")
    screen.start_run()
    gui.wait(lambda: not screen.running and screen.last_result is not None, timeout=180)
    res = screen.last_result
    assert res.ok, res.message
    names = {p.name for p in res.outputs}
    assert any(n.endswith(".xlsx") for n in names) and any(n.endswith(".pdf") for n in names)
    assert res.run_id.startswith("MAAF_")
