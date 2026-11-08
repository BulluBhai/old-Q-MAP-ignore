"""Reproducibility: processing versions, reuse, revalidation, supersession, audit trail, concurrency."""

import multiprocessing
import threading

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest, make_profile
from qmap import CLEANING_CODE_VERSION
from qmap.core.errors import IngestError
from qmap.core.runs import finish_run, start_run
from qmap.storage.parquet_io import read_canonical_metadata
from qmap.storage.recovery import verify_registry

ROWS = daily_rows(8)


def bad_rows():
    rows = [list(r) for r in ROWS]
    rows[2][3] = 500  # Low far above everything
    return rows


def attempts(db):
    return db.query("SELECT * FROM ingest_attempts ORDER BY attempt_id")


def cleaned(db):
    return db.query("SELECT * FROM datasets WHERE layer='cleaned' ORDER BY dataset_id")


@pytest.fixture
def good(src):
    return write_delimited(src / "good.csv", HEADER, ROWS)


@pytest.fixture
def bad(src):
    return write_delimited(src / "bad.csv", HEADER, bad_rows())


# ---- identical repeated derivation ---------------------------------------------------------------------
def test_identical_reprocessing_is_recognised_and_creates_no_new_dataset(run, db, good):
    first = do_ingest(run, good)
    second = do_ingest(run, good)
    assert (first.outcome, second.outcome) == ("accepted", "reused")
    assert second.dataset_ids == first.dataset_ids and len(cleaned(db)) == 1
    a = attempts(db)
    assert [x["outcome"] for x in a] == ["accepted", "reused"]
    assert a[1]["reused_of_attempt_id"] == a[0]["attempt_id"]
    assert len(db.query("SELECT * FROM ingest_events")) == 2  # both receipts retained


def test_same_content_under_another_name_is_reused_and_still_recorded(run, db, good, src):
    twin = src / "other_name.dat"
    twin.write_bytes(good.read_bytes())
    do_ingest(run, good)
    second = do_ingest(run, twin)
    assert second.outcome == "reused" and second.receipt_status == "reused_existing"
    assert len(db.query("SELECT * FROM datasets WHERE layer='raw'")) == 1 and len(cleaned(db)) == 1
    names = [e["original_filename"] for e in db.query("SELECT * FROM ingest_events ORDER BY event_id")]
    assert names == ["good.csv", "other_name.dat"]


# ---- rejected attempts: audit trail and revalidation -------------------------------------------------------
def test_failed_attempt_stays_in_the_audit_trail_and_retrying_unchanged_is_blocked(run, db, bad):
    assert do_ingest(run, bad).outcome == "rejected"
    again = do_ingest(run, bad)
    assert again.outcome == "blocked" and "force_reason" in again.message
    assert len(attempts(db)) == 1  # no new attempt, nothing lost
    assert attempts(db)[0]["outcome"] == "rejected"
    assert "blocked" in db.query("SELECT detail FROM ingest_events ORDER BY event_id")[1]["detail"].lower()


def test_forced_retry_needs_a_written_reason_and_links_to_the_failed_attempt(run, db, bad):
    first = do_ingest(run, bad)
    assert do_ingest(run, bad, force_reason="   ").outcome == "blocked"  # blank is not a reason
    forced = do_ingest(run, bad, force_reason="Vendor says the file is final; re-checking validation")
    assert forced.outcome == "rejected"
    a = attempts(db)
    assert len(a) == 2 and all(x["outcome"] == "rejected" for x in a)  # both stay
    assert a[1]["revalidation_of_attempt_id"] == first.attempt_id
    assert a[1]["force_reason"].startswith("Vendor says")


def test_a_corrected_profile_revalidates_without_force_and_keeps_the_history(run, db, src):
    # The file is fine, but the first profile mapped the wrong exchange timezone/format.
    p = write_delimited(src / "dm.csv", HEADER, [[r[0][8:10] + "-" + r[0][5:7] + "-" + r[0][2:4]] + r[1:] for r in ROWS])
    wrong = make_profile(datetime={"kind": "format", "format": "%m-%d-%y", "two_digit_year_pivot": 69})
    first = do_ingest(run, p, wrong)
    assert first.outcome == "rejected"  # day > 12 cannot be a month
    fixed = make_profile(profile_version=2, datetime={"kind": "format", "format": "%d-%m-%y", "two_digit_year_pivot": 69})
    second = do_ingest(run, p, fixed)
    assert second.outcome == "accepted", second.message
    a = attempts(db)
    assert [x["outcome"] for x in a] == ["rejected", "accepted"]
    assert a[1]["revalidation_of_attempt_id"] == a[0]["attempt_id"]
    assert (a[0]["profile_version"], a[1]["profile_version"]) == (1, 2)
    assert a[0]["processing_version"] != a[1]["processing_version"]
    assert len(db.query("SELECT * FROM datasets WHERE layer='raw'")) == 1  # raw is not duplicated


# ---- legitimate reprocessing under a new version ---------------------------------------------------------
def test_new_profile_version_creates_a_new_dataset_and_supersedes_the_old_one(run, db, settings, good):
    v1 = do_ingest(run, good, make_profile())
    v2 = do_ingest(run, good, make_profile(profile_version=2, source_label="v2"))
    assert (v1.outcome, v2.outcome) == ("accepted", "accepted")
    old, new = cleaned(db)
    assert old["status"] == "superseded" and old["superseded_by_dataset_id"] == new["dataset_id"]
    assert new["status"] == "active" and new["processing_version"] == f"test_profile@2+{CLEANING_CODE_VERSION}"
    assert old["sha256"] != new["sha256"] or old["relative_path"] != new["relative_path"]
    assert len(db.query("SELECT * FROM datasets WHERE layer='cleaned' AND status='active'")) == 1
    assert not verify_registry(settings, db).needs_attention  # both files still present and intact


def test_changed_processing_code_version_is_a_new_processing_version(run, db, good, monkeypatch):
    import qmap.data_engine.ingest as ing

    do_ingest(run, good)
    monkeypatch.setattr(ing, "CLEANING_CODE_VERSION", "c99")
    res = do_ingest(run, good)
    assert res.outcome == "accepted"
    old, new = cleaned(db)
    assert new["processing_version"] == "test_profile@1+c99" and old["status"] == "superseded"


def test_profile_and_code_version_used_are_preserved_per_attempt(run, db, settings, good):
    do_ingest(run, good)
    a = attempts(db)[0]
    assert (a["profile_id"], a["profile_version"], a["processing_version"]) == ("test_profile", 1, f"test_profile@1+{CLEANING_CODE_VERSION}")
    snap = db.one("SELECT * FROM source_profiles WHERE profile_id='test_profile' AND profile_version=1")
    assert snap["content_text"] == make_profile().content_text and snap["content_sha256"] == make_profile().content_sha256
    path = settings.data_path(cleaned(db)[0]["relative_path"])
    meta = read_canonical_metadata(path)
    assert meta["cleaning_code_version"] == CLEANING_CODE_VERSION and meta["profile_version"] == 1
    assert meta["processing_version"] == f"test_profile@1+{CLEANING_CODE_VERSION}" and meta["run_id"] == run.run_id
    assert meta["source_raw_sha256"] == db.one("SELECT sha256 FROM datasets WHERE layer='raw'")[0]


def test_changing_a_profile_without_a_new_version_is_refused(run, db, good):
    do_ingest(run, good)
    with pytest.raises(IngestError) as e:
        do_ingest(run, good, make_profile(source_label="edited but same version"))
    assert e.value.code == "E_PROFILE_CHANGED"
    assert len(attempts(db)) == 1


def test_lineage_raw_to_cleaned_to_attempt_to_run(run, db, good):
    do_ingest(run, good)
    c = cleaned(db)[0]
    a = db.one("SELECT * FROM ingest_attempts WHERE attempt_id=?", (c["created_by_attempt_id"],))
    ev = db.one("SELECT * FROM ingest_events WHERE event_id=?", (a["event_id"],))
    assert c["parent_dataset_id"] == a["raw_dataset_id"] == ev["raw_dataset_id"]
    assert a["run_id"] == ev["run_id"] == run.run_id


def test_the_audit_trail_cannot_be_rewritten(run, db, bad):
    do_ingest(run, bad)
    import sqlite3

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        db.connection().execute("UPDATE ingest_attempts SET outcome='accepted'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        db.connection().execute("DELETE FROM quality_checks")


def test_rejected_attempt_then_new_content_is_a_fresh_raw_dataset(run, db, src):
    p = src / "same_name.csv"
    write_delimited(p, HEADER, bad_rows())
    assert do_ingest(run, p).outcome == "rejected"
    write_delimited(p, HEADER, ROWS)  # corrected file, same name
    assert do_ingest(run, p).outcome == "accepted"
    assert len(db.query("SELECT * FROM datasets WHERE layer='raw'")) == 2


# ---- concurrency -----------------------------------------------------------------------------------------
def test_concurrent_identical_ingests_create_one_dataset(settings, db, good):
    results, errors = [], []
    barrier = threading.Barrier(6)

    def go(i):
        try:
            r = start_run(settings, db, "FOUND", area="Ingestion", recover=False)
            barrier.wait()
            results.append(do_ingest(r, good, note=str(i)))
            finish_run(r)
        except Exception as exc:  # pragma: no cover
            errors.append(repr(exc))

    ts = [threading.Thread(target=go, args=(i,)) for i in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors, errors
    assert sorted(r.outcome for r in results).count("accepted") == 1
    assert {r.outcome for r in results} <= {"accepted", "reused"}
    assert len(db.query("SELECT * FROM datasets WHERE layer='raw'")) == 1 and len(cleaned(db)) == 1
    assert len(db.query("SELECT * FROM ingest_events")) == 6
    # no stray cleaned files from the losers
    files = [p for p in (settings.data_root / "Cleaned_Data").rglob("*") if p.is_file()]
    assert len([f for f in files if "_incoming" not in f.parts]) == 1 and not list(settings.cleaned_incoming_dir.iterdir())
    assert not verify_registry(settings, db).needs_attention


def _ingest_proc(args):
    data, out, code, path, idx = args
    from fixtures.profiles import do_ingest as di
    from qmap.core.config import load_settings
    from qmap.core.runs import finish_run as fr, start_run as sr
    from qmap.storage.db import Database

    s = load_settings(None, env={"QMAP_DATA_ROOT": data, "QMAP_OUTPUT_ROOT": out}, code_root=code)
    d = Database(s.db_path)
    r = sr(s, d, "FOUND", area="Ingestion", recover=False)
    res = di(r, path, note=str(idx))
    fr(r)
    return res.outcome


def test_concurrent_processes_ingesting_the_same_file(settings, db, roots, good):
    args = [(str(settings.data_root), str(settings.output_root), str(roots["code"]), str(good), i) for i in range(6)]
    with multiprocessing.get_context("spawn").Pool(3) as pool:
        outcomes = pool.map(_ingest_proc, args)
    assert outcomes.count("accepted") == 1 and set(outcomes) <= {"accepted", "reused"}
    assert len(cleaned(db)) == 1 and len(db.query("SELECT * FROM ingest_events")) == 6
    assert not verify_registry(settings, db).needs_attention
