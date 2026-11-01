"""Validation settings are part of the processing identity (Project Owner decision, D2-32).

A previous result may be reused only if raw content, processing version, relevant ingest request AND the
configuration fingerprint (validation settings that can change acceptance, dataset content or quality_flags)
all match.
"""

import dataclasses
import json
from datetime import date

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest, read_group
from qmap.core.config import load_settings
from qmap.core.runs import finish_run, start_run
from qmap.data_engine import canonical as C
from qmap.data_engine.ingest import FINGERPRINT_KEYS, _validation_settings, config_fingerprint
from qmap.storage.parquet_io import read_canonical_metadata
from qmap.storage.recovery import verify_registry

ROWS = daily_rows(8)  # close-to-close moves are below 1%


@pytest.fixture
def good(src):
    return write_delimited(src / "good.csv", HEADER, ROWS)


def ingest_with(settings, db, path, **kw):
    run = start_run(settings, db, "FOUND", area="Ingestion")
    try:
        return do_ingest(run, path, **kw)
    finally:
        finish_run(run)


def cleaned(db):
    return db.query("SELECT * FROM datasets WHERE layer='cleaned' ORDER BY dataset_id")


def attempts(db):
    return db.query("SELECT * FROM ingest_attempts ORDER BY attempt_id")


# ---- unchanged settings: reuse is preserved ------------------------------------------------------------------
def test_unchanged_settings_reuse_the_earlier_result(settings, db, good):
    first = ingest_with(settings, db, good, today=date(2026, 3, 1))
    second = ingest_with(settings, db, good, today=date(2026, 6, 1))  # another day: not part of the identity
    assert (first.outcome, second.outcome) == ("accepted", "reused")
    assert second.dataset_ids == first.dataset_ids and len(cleaned(db)) == 1
    fp = config_fingerprint(_validation_settings(settings, do_profile(), date(2026, 3, 1)))
    assert {a["config_fingerprint"] for a in attempts(db)} == {fp}
    assert cleaned(db)[0]["config_fingerprint"] == fp
    assert fp in second.message


def test_a_report_only_setting_does_not_prevent_reuse_but_is_reported(settings, db, good):
    first = ingest_with(settings, db, good)
    second = ingest_with(dataclasses.replace(settings, max_gap_days=1), db, good)
    assert (first.outcome, second.outcome) == ("accepted", "reused")
    assert "report-only settings differ" in second.message and "max_gap_days" in second.message


# ---- changed settings: never silently reused ----------------------------------------------------------------
def test_a_setting_that_changes_quality_flags_produces_a_new_dataset(settings, db, good):
    first = ingest_with(settings, db, good)
    tight = dataclasses.replace(settings, max_daily_move_pct=0.1)  # now most bars are "large moves"
    second = ingest_with(tight, db, good)
    assert (first.outcome, second.outcome) == ("accepted", "accepted")
    old, new = cleaned(db)
    assert old["config_fingerprint"] != new["config_fingerprint"]
    assert old["processing_version"] == new["processing_version"]  # the version text is unchanged
    assert old["status"] == "superseded" and old["superseded_by_dataset_id"] == new["dataset_id"]
    flags_old = read_group(settings, db, old["dataset_id"])["quality_flags"]
    flags_new = read_group(settings, db, new["dataset_id"])["quality_flags"]
    assert not any(f & C.FLAG_LARGE_MOVE for f in flags_old) and any(f & C.FLAG_LARGE_MOVE for f in flags_new)
    meta = read_canonical_metadata(settings.data_path(new["relative_path"]))
    assert meta["config_fingerprint"] == new["config_fingerprint"] and meta["validation_settings"]["max_daily_move_pct"] == 0.1
    assert not verify_registry(settings, db).needs_attention


def test_returning_to_earlier_settings_reuses_their_result_and_says_it_is_superseded(settings, db, good):
    first = ingest_with(settings, db, good)
    ingest_with(dataclasses.replace(settings, max_daily_move_pct=0.1), db, good)
    again = ingest_with(settings, db, good)
    assert again.outcome == "reused" and again.dataset_ids == first.dataset_ids
    assert "SUPERSEDED" in again.message and len(cleaned(db)) == 2


@pytest.mark.parametrize("change", [
    {"min_rows": 50},  # acceptance
    {"plausible_min_date": date(2026, 1, 7)},  # acceptance (earlier rows now out of range)
    {"plausible_max_days_ahead": 0},
    {"requirement_sets": {"price_only": {"require_volume": True}, "price_volume": {"require_volume": True}}},
])
def test_a_setting_that_can_change_acceptance_is_never_reused(settings, db, good, change):
    first = ingest_with(settings, db, good)
    second = ingest_with(dataclasses.replace(settings, **change), db, good)
    assert first.outcome == "accepted" and second.outcome in ("accepted", "rejected")  # processed, not reused
    assert [a["outcome"] for a in attempts(db)] == ["accepted", second.outcome]
    assert attempts(db)[0]["config_fingerprint"] != attempts(db)[1]["config_fingerprint"]


def test_a_rejection_blocks_only_an_unchanged_retry(settings, db, good):
    strict = dataclasses.replace(settings, min_rows=50)
    first = ingest_with(strict, db, good)
    blocked = ingest_with(strict, db, good)
    relaxed = ingest_with(settings, db, good)  # different settings: a new identity, no force_reason needed
    assert (first.outcome, blocked.outcome, relaxed.outcome) == ("rejected", "blocked", "accepted")
    assert relaxed.attempt_id and attempts(db)[-1]["revalidation_of_attempt_id"] == first.attempt_id
    assert attempts(db)[-1]["force_reason"] is None


# ---- the fingerprint itself ------------------------------------------------------------------------------
def test_fingerprint_is_stable_and_covers_exactly_the_identity_settings(settings):
    p = do_profile()
    base = _validation_settings(settings, p, date(2026, 1, 1))
    assert config_fingerprint(base) == config_fingerprint(dict(reversed(list(base.items()))))
    assert config_fingerprint(base) == config_fingerprint({**base, "today": "2030-12-31", "max_gap_days": 99})
    for key in FINGERPRINT_KEYS:
        changed = {**base, key: "something else"}
        assert config_fingerprint(changed) != config_fingerprint(base), key
    assert config_fingerprint(base).startswith("vs1:")


def test_fingerprint_is_the_same_when_settings_are_reloaded_from_a_file(roots, tmp_path):
    cfg = tmp_path / "q.toml"
    cfg.write_text(f'[paths]\ndata_root = "{roots["data"].as_posix()}"\noutput_root = "{roots["output"].as_posix()}"\n'
                   '[validation]\nmax_daily_move_pct = 25\nplausible_min_date = "01-Jan-1990"\n', encoding="utf-8")
    from_file = load_settings(cfg, env={}, code_root=roots["code"])
    defaults = load_settings(None, env={"QMAP_DATA_ROOT": str(roots["data"]), "QMAP_OUTPUT_ROOT": str(roots["output"])},
                             code_root=roots["code"])
    d = date(2026, 1, 1)
    assert config_fingerprint(_validation_settings(from_file, do_profile(), d)) == \
        config_fingerprint(_validation_settings(defaults, do_profile(), d))  # 25 and 25.0 are the same setting


# ---- backward compatibility with results recorded before the fingerprint existed ---------------------------
def _make_legacy(db, attempt_id, *, keep_settings_json):
    """Rewrite rows as earlier code wrote them (protective triggers lifted only inside this test helper)."""
    conn = db.connection()
    triggers = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name IN "
                            "('trg_attempts_no_update', 'trg_datasets_identity')").fetchall()
    for t in triggers:
        conn.execute(f"DROP TRIGGER {t['name']}")
    conn.execute("UPDATE ingest_attempts SET config_fingerprint = NULL"
                 + ("" if keep_settings_json else ", validation_settings_json = NULL") + " WHERE attempt_id = ?",
                 (attempt_id,))
    conn.execute("UPDATE datasets SET config_fingerprint = NULL WHERE created_by_attempt_id = ?", (attempt_id,))
    for t in triggers:
        conn.execute(t["sql"])


def test_result_from_migration_2_era_is_reused_when_its_recorded_settings_match(settings, db, good):
    first = ingest_with(settings, db, good)
    _make_legacy(db, first.attempt_id, keep_settings_json=True)
    same = ingest_with(settings, db, good)
    assert same.outcome == "reused" and same.dataset_ids == first.dataset_ids
    changed = ingest_with(dataclasses.replace(settings, min_rows=2), db, good)
    assert changed.outcome == "accepted" and len(cleaned(db)) == 2  # different settings: reprocessed


def test_result_without_recorded_settings_is_never_reused_and_reprocessing_does_not_collide(settings, db, good):
    first = ingest_with(settings, db, good)
    _make_legacy(db, first.attempt_id, keep_settings_json=False)
    second = ingest_with(settings, db, good)
    assert second.outcome == "accepted"  # unknown settings are treated as incompatible
    old, new = cleaned(db)
    assert old["config_fingerprint"] is None and new["config_fingerprint"]
    assert old["status"] == "superseded" and new["status"] == "active"
    third = ingest_with(settings, db, good)
    assert third.outcome == "reused" and third.dataset_ids == second.dataset_ids
    assert json.loads(attempts(db)[-1]["validation_settings_json"])["min_rows"] == 1


def test_fingerprint_is_part_of_the_protected_dataset_identity(settings, db, good):
    import sqlite3

    first = ingest_with(settings, db, good)
    with pytest.raises(sqlite3.IntegrityError):
        db.connection().execute("UPDATE datasets SET config_fingerprint = 'vs1:forged' WHERE dataset_id = ?",
                                (first.dataset_ids[0],))


def do_profile():
    from fixtures.profiles import make_profile

    return make_profile()
