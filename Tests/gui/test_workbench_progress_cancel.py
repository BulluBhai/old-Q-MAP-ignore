"""Real-window tests (10-Nov-26): the Workbench shows 'done of total' steps and an ETA while an analysis runs, Cancel
stops it (recorded as cancelled), closing the window asks a running analysis to stop, and the progress bar's end state
always agrees with the outcome: full only for a completed run (the 10-Nov-26 acceptance finding: a successful run left
the bar almost empty), never full for a cancelled, failed or blocked one."""

from __future__ import annotations

from types import SimpleNamespace

from gui.test_two_applications import _select
from gui.test_workbench_ma_affinity import _prepare_long


def _v1_screen(gui, world):
    ds = _prepare_long(world)
    app = gui.start(app_key="analytical_workbench")
    gui.choose_folders(app)
    app.show("analysis")
    screen = app.screens["analysis"]
    screen.analysis_combo.current(next(k for k, c in enumerate(screen.choices) if c.analysis_id == "ma_affinity"))
    screen.on_analysis_selected()
    screen.refresh()
    _select(screen, ds)
    screen.param_vars["ma_types"].set("SMA,EMA,WMA,HMA,RMA")  # long enough to watch and cancel
    return app, screen


def _full(screen) -> bool:
    return (str(screen.progress.cget("mode")) == "determinate"
            and float(screen.progress.cget("value")) == float(screen.progress.cget("maximum")) > 0)


def test_progress_count_and_cancel(gui, world):
    app, screen = _v1_screen(gui, world)
    assert str(screen.cancel_button.cget("state")) == "disabled"
    screen.start_run()
    assert screen.running and app.active_job is screen.job
    gui.wait(lambda: " of " in screen.count_var.get(), timeout=120, app=app)
    assert str(screen.progress.cget("mode")) == "determinate" and screen.count_var.get().endswith("%)")
    assert str(screen.cancel_button.cget("state")) == "normal"
    screen.cancel_button.invoke()
    assert str(screen.cancel_button.cget("state")) == "disabled"
    gui.wait(lambda: not screen.running, timeout=120, app=app)
    res = screen.last_result
    assert res.outcome == "cancelled", res.message
    assert screen.stage_var.get() == "Cancelled" and screen.final_label.cget("text").startswith("Cancelled.")
    assert not _full(screen) and "not complete" in screen.count_var.get()
    assert app.active_job is None and screen.job is None and screen.eta_var.get() == "-"
    assert str(screen.run_button.cget("state")) == "normal"


def test_a_completed_run_and_its_reproduction_end_with_a_full_bar(gui, world):
    app, screen = _v1_screen(gui, world)
    screen.param_vars["ma_types"].set("SMA")
    screen.start_run()
    gui.wait(lambda: not screen.running, timeout=300, app=app)
    assert screen.last_result.ok, screen.last_result.message
    assert _full(screen) and screen.stage_var.get() == "Finished" and "(100.0%)" in screen.count_var.get()
    first = screen.last_result
    screen.reproduce_button.invoke()
    gui.wait(lambda: not screen.running and screen.last_result is not first, timeout=300, app=app)
    assert screen.last_result.ok and screen.last_result.reproduction["identical"]
    assert _full(screen) and screen.stage_var.get() == "Finished"


def test_end_states_agree_with_the_outcome(gui, world):
    app, screen = _v1_screen(gui, world)
    res = lambda outcome: SimpleNamespace(outcome=outcome, ok=outcome == "completed", message=f"{outcome}.",  # noqa: E731
                                          run_id=None, run_dir=None, outputs=[], readiness=None, reproduction=None,
                                          metadata_path=SimpleNamespace(name="Run_Metadata.json"))
    for outcome, stage in (("failed", "Failed"), ("blocked", "Not started"), ("cancelled", "Cancelled")):
        screen._begin(SimpleNamespace(cancel_event=SimpleNamespace(is_set=lambda: False), cancel=lambda: None))
        screen._on_tick({"done": 3, "total": 10, "text": "In-sample SMA-12"})
        screen._finish(res(outcome))
        assert screen.stage_var.get() == stage and not _full(screen), outcome
    # an analysis that reports no count at all still ends with a full bar when it completes
    screen._begin(SimpleNamespace(cancel_event=SimpleNamespace(is_set=lambda: False), cancel=lambda: None))
    screen._finish(res("completed"))
    assert _full(screen) and screen.stage_var.get() == "Finished" and screen.count_var.get() == "Complete"


def test_the_eta_appears_once_a_rate_is_known(gui, world, monkeypatch):
    from qmap_gui import analysis

    app, screen = _v1_screen(gui, world)
    clock = {"t": 100.0}
    monkeypatch.setattr(analysis.time, "monotonic", lambda: clock["t"])
    screen._begin(SimpleNamespace(cancel_event=SimpleNamespace(is_set=lambda: False), cancel=lambda: None))
    screen._on_tick({"done": 0, "total": 100, "text": "x"})
    clock["t"] += 1
    screen._on_tick({"done": 10, "total": 100, "text": "x"})
    assert screen.eta_var.get() == "-"  # under 3 s: no estimate yet rather than an unreliable one
    clock["t"] += 3
    screen._on_tick({"done": 40, "total": 100, "text": "x"})
    assert screen.eta_var.get() not in ("-", "0 s")
    screen._finish(SimpleNamespace(outcome="cancelled", ok=False, message="Cancelled.", run_id=None, run_dir=None))


def test_closing_the_window_asks_a_running_analysis_to_stop(gui, world):
    app, screen = _v1_screen(gui, world)
    screen.start_run()
    gui.wait(lambda: " of " in screen.count_var.get(), timeout=120, app=app)
    job = screen.job
    app._on_closing()
    assert job.cancel_event.is_set()
    for t in list(app.tasks.threads):
        t.join(120)
    assert not any(t.is_alive() for t in app.tasks.threads)


def test_v2_shows_its_options_counts_progress_and_can_be_cancelled(gui, world):
    app, screen = _v1_screen(gui, world)
    screen.analysis_combo.current(next(k for k, c in enumerate(screen.choices) if c.analysis_id == "ma_affinity_v2"))
    screen.on_analysis_selected()
    for key, default in (("chance_shuffles", "200"), ("chance_block", "15"), ("chance_seed", "1"),
                         ("strength_rule", "relative"), ("group_pct", "10"), ("zone_mode", "percent"),
                         ("ma_warmup", "earlier")):
        assert screen.param_vars[key].get() == default, key
    screen.refresh()
    screen.param_vars["ma_types"].set("SMA,EMA,WMA,HMA,RMA")
    screen.param_vars["chance_shuffles"].set("2000")  # long enough to watch and cancel
    _select(screen, next(iter(screen.rows.values())))
    screen.start_run()
    gui.wait(lambda: "Chance test: shuffle" in screen.stage_var.get(), timeout=180, app=app)
    assert " of " in screen.count_var.get() and not _full(screen)
    screen.cancel_button.invoke()
    gui.wait(lambda: not screen.running, timeout=120, app=app)
    assert screen.last_result.outcome == "cancelled" and screen.stage_var.get() == "Cancelled" and not _full(screen)
