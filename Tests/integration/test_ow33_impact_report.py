"""OW-33 step 1 (D5-49) and its review corrections: the READ-ONLY impact report for Option C (sparse-only alignment).
SYNTHETIC data only.

Option C is NOT applied anywhere: production sampling (timeframe_infer) is unchanged; the report evaluates what
Option C would do on the exact blocks of the recorded sampling. A dataset is evaluated only when the inference input
(the whole file's timestamps in file order, shared by every dataset of the attempt) is rebuilt exactly and the recorded
evidence is reproduced; otherwise it is NOT EVALUABLE. Tampering tests work on COPIES of the registry and of stored
files; the real registry and every stored dataset are verified byte-identical afterwards.
"""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import sqlite3
from datetime import date, timezone

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from fixtures.builders import HEADER, ohlcv, write_delimited
from fixtures.profiles import do_ingest, make_profile
from integration.test_dq7_full_file_classification import at, sess, weekdays
from qmap.data_engine import ow33_impact as O
from qmap.data_engine import timeframe_infer as T

UTC = timezone.utc


# ---- synthetic files -------------------------------------------------------------------------------------------------
def sparse_keys():  # 5-minute data + 170 one-bar dates at varying times; a sampled block lands in them (seeded)
    rnd = random.Random(170)
    return sess(5, date(2023, 1, 2), 200) + [at(d, 9 + rnd.randrange(6), 15 + 5 * rnd.randrange(9))
                                            for d in weekdays(date(2023, 9, 4), 170)]


def regular_keys():  # 1-minute data with 20 days of every other bar: a sampled block lands there (MIXED today)
    return sess(1, date(2024, 1, 1), 150) + sess(1, date(2024, 6, 3), 20)[::2] + sess(1, date(2024, 7, 1), 150)


def daily_varying_keys():  # one bar per date at varying times, no intraday part at all
    rnd = random.Random(1)
    return [at(d, 9 + rnd.randrange(6), rnd.randrange(60)) for d in weekdays(date(2022, 1, 3), 300)]


def multi_rows():
    """Two instruments interleaved per timestamp (AAA, BBB), with an exact duplicate AAA row every 500 timestamps,
    5-minute bars then 120 one-bar dates at varying times. Returns (file rows, file-order keys in UTC)."""
    rnd = random.Random(120)
    ts = sess(5, date(2023, 1, 2), 100) + [at(d, 9 + rnd.randrange(6), 15 + 5 * rnd.randrange(9))
                                          for d in weekdays(date(2023, 6, 5), 120)]
    vals = ohlcv(2 * len(ts), seed=4)
    rows, keys = [], []
    for i, k in enumerate(ts):
        a = [k.isoformat(), "AAA"] + vals[2 * i]
        rows += [a, [k.isoformat(), "BBB"] + vals[2 * i + 1]]
        keys += [k, k]
        if i % 500 == 7:
            rows.append(list(a))  # identical in every column: an exact duplicate
            keys.append(k)
    return rows, [k.astimezone(UTC) for k in keys]


def _load(src, run, keys, name):
    rows = [[k.isoformat()] + r for k, r in zip(keys, ohlcv(len(keys)))]
    prof = make_profile(profile_id=name, instrument={"timeframe": "infer"},
                        datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, write_delimited(src / f"{name}.csv", HEADER, rows), prof)
    assert res.outcome == "accepted", res.message
    return res


def _load_multi(src, run):
    rows, keys = multi_rows()
    header = ["time", "Symbol", "open", "high", "low", "close", "Volume"]
    prof = make_profile(profile_id="multi", instrument={"timeframe": "infer", "symbol_from": "column",
                                                         "symbol_column": "Symbol", "symbol": None},
                        datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, write_delimited(src / "multi.csv", header, rows), prof)
    assert res.outcome == "accepted", res.message
    return res, keys


def _fingerprint(settings) -> dict:
    """Every stored file (datasets and stored originals) byte by byte, and the registry's complete content.
    The registry's own files (main file, -wal, -shm journal) are excluded from the byte scan: on Windows the journal
    files are locked while the registry is open. Its content is covered instead by a logical dump through a read-only
    connection (which sees committed WAL content) plus the main file's bytes."""
    db_names = settings.db_path.name
    files = {p.relative_to(settings.data_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(settings.data_root.rglob("*")) if p.is_file() and not p.name.startswith(db_names)}
    conn = O.open_read_only(settings.db_path)
    try:
        files["<registry content>"] = hashlib.sha256("\n".join(conn.iterdump()).encode("utf-8")).hexdigest()
    finally:
        conn.close()
    files["<registry file>"] = hashlib.sha256(settings.db_path.read_bytes()).hexdigest()
    assert any(k.endswith(".parquet") for k in files)  # the scan really covers the stored datasets
    return files


def _report(db_path, data_path):
    conn = O.open_read_only(db_path)
    try:
        return O.impact_rows(conn, data_path)
    finally:
        conn.close()


def _datasets(rows):
    return [r for r in rows if r["row_type"] == "dataset"]


def _copy_registry(settings, tmp_path, sql: list[tuple]):
    """A COPY of the registry with the given changes (immutability triggers dropped in the copy only)."""
    copy = tmp_path / "registry_copy.sqlite"
    src = sqlite3.connect(settings.db_path)
    dst = sqlite3.connect(copy)
    src.backup(dst)
    src.close()
    for (name,) in dst.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'").fetchall():
        dst.execute(f'DROP TRIGGER "{name}"')
    for stmt, params in sql:
        dst.execute(stmt, params)
    dst.commit()
    dst.close()
    return copy


@pytest.fixture
def registry(settings, db, src, run):
    """sparse (would change), regular (stays MIXED), multi-instrument (would change, shared inference), plain 5m."""
    _load(src, run, sparse_keys(), "sparse")
    _load(src, run, regular_keys(), "regular")
    multi, multi_keys = _load_multi(src, run)
    _load(src, run, sess(5, date(2024, 1, 1), 30), "plain")
    return {"multi_keys": multi_keys}


def _attempt_of(db, source_file):
    return db.connection().execute(
        "SELECT a.attempt_id, a.datetime_rules_json, a.transformations_json FROM ingest_attempts a JOIN ingest_events e "
        "USING (event_id) WHERE e.original_filename = ? AND a.outcome = 'accepted'", (source_file,)).fetchone()


# ---- Option C on blocks ----------------------------------------------------------------------------------------------
def test_sparse_blocks_are_excluded_only_under_option_c():
    t, o = O.evaluate_option_c(sparse_keys(), "Asia/Kolkata")
    assert T.infer_interval(sparse_keys(), zone="Asia/Kolkata").status == "mixed"  # production sampling unchanged
    assert (t.status, t.patterns) == ("mixed", {"5m": 14, "1D": 1})
    assert (o.status, o.timeframe, o.dominant, len(o.excluded)) == ("consistent", "5m", "5m", 1)
    ex = next(b for b in o.blocks if b["role"] == "excluded")
    assert ex["interval"] == "1D" and "one bar per date at varying times" in ex["sparse"]
    assert all(b["agrees_under_c"] for b in o.blocks if b["role"] == "used")


def test_regular_multiple_blocks_remain_mixed():
    t, o = O.evaluate_option_c(regular_keys(), "Asia/Kolkata")
    assert t.status == "mixed" and (o.status, o.excluded) == ("mixed", [])
    reg = next(b for b in o.blocks if b["interval"] == "2m")
    assert reg["role"] == "used" and reg["agrees_under_c"] is False and "never excluded" in reg["sparse"]


def test_fixed_time_daily_blocks_remain_mixed():
    keys = sess(1, date(2022, 1, 3), 20) + [at(d, 0, 0) for d in weekdays(date(2022, 6, 6), 400)]
    t, o = O.evaluate_option_c(keys, "Asia/Kolkata")
    assert t.status == "mixed" and (o.status, o.excluded) == ("mixed", [])
    assert any("one time of day" in b["sparse"] for b in o.blocks if b["interval"] == "1D")


def test_a_varying_time_daily_series_without_a_minute_block_is_not_affected():
    t, o = O.evaluate_option_c(daily_varying_keys(), "Asia/Kolkata")
    assert o.excluded == [] and (o.status, o.timeframe) == (t.status, t.timeframe)
    assert all("no minute block" in b["sparse"] for b in o.blocks if b["interval"])


# ---- exact reconstruction ----------------------------------------------------------------------------------------------
def test_each_dataset_of_a_multi_instrument_attempt_gets_the_exact_file_order_input(settings, db, registry):
    keys = registry["multi_keys"]
    att = _attempt_of(db, "multi.csv")
    ids = [r[0] for r in db.connection().execute(
        "SELECT dataset_id FROM datasets WHERE created_by_attempt_id = ? AND layer = 'cleaned'", (att["attempt_id"],))]
    assert len(ids) == 2  # AAA and BBB
    removed = json.loads(att["transformations_json"])
    assert any(s.get("step") == "exact_duplicates_removed" and s["count"] >= 1 for s in removed if isinstance(s, dict))
    conn = O.open_read_only(settings.db_path)
    try:
        for ds in ids:
            rec = O.reconstruct_input(conn, settings.data_path, ds)
            assert rec.keys == keys, rec.reason  # interleaved, duplicates included: exactly the file's sequence
            assert rec.siblings == ids and rec.removed_rows >= 1 and rec.stored_rows + rec.removed_rows == len(keys)
    finally:
        conn.close()
    # combining each group's stored rows one after the other (not file order) would NOT reproduce the recorded
    # inference: the exact file order matters, which is why membership is proven by src_row
    record = json.loads(att["datetime_rules_json"])["timeframe_inference"]
    aaa = [k for k, r in zip(keys, multi_rows()[0]) if r[1] == "AAA"]
    bbb = [k for k, r in zip(keys, multi_rows()[0]) if r[1] == "BBB"]
    per_group = aaa + bbb
    assert per_group != keys and len(per_group) == len(keys)
    assert O.compare_with_record(T.infer_interval(per_group, zone="Asia/Kolkata"), record, "MIXED")


def test_the_report_verifies_reconstruction_and_changes_nothing(settings, db, registry):
    before = _fingerprint(settings)
    rows = _report(settings.db_path, settings.data_path)
    assert _fingerprint(settings) == before  # registry and every stored file byte-identical
    ds = {r["source_file"] + ":" + r["instrument"]: r for r in _datasets(rows)}
    assert set(ds) == {"sparse.csv:NSE:TEST", "regular.csv:NSE:TEST", "multi.csv:NSE:AAA", "multi.csv:NSE:BBB"}
    assert all(r["reproduction"].startswith("verified") for r in ds.values()), ds
    s, r = ds["sparse.csv:NSE:TEST"], ds["regular.csv:NSE:TEST"]
    assert (s["proposed_classification_option_c"], s["would_change"]) == ("5m", "yes")
    assert (r["proposed_classification_option_c"], r["would_change"]) == ("MIXED", "no")
    for k in ("multi.csv:NSE:AAA", "multi.csv:NSE:BBB"):
        m = ds[k]
        assert (m["proposed_classification_option_c"], m["would_change"]) == ("5m", "yes")
        assert "shares one inference with dataset" in m["processing_and_lineage"] and int(m["removed_duplicates"]) >= 1
    blocks = [b for b in rows if b["row_type"] == "block" and b["dataset_id"] == s["dataset_id"]]
    assert len(blocks) == 15 and [b["option_c_role"] for b in blocks].count("excluded") == 1
    assert O.summary(rows) == {"mixed_datasets": 4, "would_change": 3, "unchanged": 1, "not_evaluable": 0}


# ---- NOT EVALUABLE cases (copies only) -----------------------------------------------------------------------------
def test_an_incorrect_source_row_reconstruction_is_not_evaluable(settings, db, registry, tmp_path):
    before = _fingerprint(settings)
    rel = db.connection().execute("SELECT relative_path FROM datasets d JOIN instruments i USING (instrument_id) "
                                  "WHERE i.symbol = 'BBB' AND d.layer = 'cleaned'").fetchone()[0]
    tab = pq.read_table(str(settings.data_path(rel)))
    rows = tab.column("src_row").to_pylist()
    rows[10] = rows[11]  # one row placed twice: an incorrect membership
    bad = tmp_path / "tampered.parquet"
    pq.write_table(tab.set_column(tab.schema.get_field_index("src_row"), "src_row", pa.array(rows, pa.int64())), bad)
    data_path = lambda r: bad if r == rel else settings.data_path(r)  # noqa: E731
    ds = {x["instrument"] + x["source_file"]: x for x in _datasets(_report(settings.db_path, data_path))}
    for k in ("NSE:AAAmulti.csv", "NSE:BBBmulti.csv"):  # both share the inference: both not evaluable
        assert ds[k]["reproduction"].startswith("NOT EVALUABLE") and "more than once" in ds[k]["reproduction"]
        assert ds[k]["proposed_classification_option_c"] == "NOT EVALUABLE" and ds[k]["would_change"] == "unknown"
    assert ds["NSE:TESTsparse.csv"]["reproduction"].startswith("verified")
    assert _fingerprint(settings) == before


def test_an_incomplete_source_row_set_is_not_evaluable(settings, db, registry, tmp_path):
    rel = db.connection().execute("SELECT relative_path FROM datasets d JOIN ingest_attempts a ON "
                                  "a.attempt_id = d.created_by_attempt_id JOIN ingest_events e USING (event_id) "
                                  "WHERE e.original_filename = 'sparse.csv' AND d.layer = 'cleaned'").fetchone()[0]
    copy_dir = tmp_path / "copy"
    copy_dir.mkdir()
    shutil.copy2(settings.data_path(rel), copy_dir / "x.parquet")
    tab = pq.read_table(str(copy_dir / "x.parquet"))
    pq.write_table(tab.slice(0, tab.num_rows - 1), copy_dir / "short.parquet")  # one stored row missing
    data_path = lambda r: copy_dir / "short.parquet" if r == rel else settings.data_path(r)  # noqa: E731
    ds = next(x for x in _datasets(_report(settings.db_path, data_path)) if x["source_file"] == "sparse.csv")
    assert ds["reproduction"].startswith("NOT EVALUABLE") and "stored rows, the registry says" in ds["reproduction"]


def test_matching_seed_but_mismatching_block_evidence_is_not_evaluable(settings, db, registry, tmp_path):
    att = _attempt_of(db, "regular.csv")
    rules = json.loads(att["datetime_rules_json"])
    rules["timeframe_inference"]["blocks"][2]["steps"] += 1  # seed, status and everything else unchanged
    copy = _copy_registry(settings, tmp_path, [("UPDATE ingest_attempts SET datetime_rules_json = ? WHERE "
                                                "attempt_id = ?", (json.dumps(rules), att["attempt_id"]))])
    ds = next(x for x in _datasets(_report(copy, settings.data_path)) if x["source_file"] == "regular.csv")
    assert ds["recorded_seed"] == rules["timeframe_inference"]["seed"]
    assert ds["reproduction"].startswith("NOT EVALUABLE: recorded inference not reproduced")
    assert "block 3" in ds["reproduction"] and "steps" in ds["reproduction"]
    assert ds["would_change"] == "unknown" and ds["proposed_classification_option_c"] == "NOT EVALUABLE"


@pytest.mark.parametrize("change", ["missing", "incomplete"])
def test_missing_or_incomplete_duplicate_lineage_is_not_evaluable(settings, db, registry, tmp_path, change):
    att = _attempt_of(db, "multi.csv")
    steps = json.loads(att["transformations_json"])
    if change == "missing":
        steps = [s for s in steps if not (isinstance(s, dict) and s.get("step") == "exact_duplicates_removed")]
    else:
        for s in steps:
            if isinstance(s, dict) and s.get("step") == "exact_duplicates_removed":
                s["removed_source_row_and_kept_source_row"] = s["removed_source_row_and_kept_source_row"][:-1]
    copy = _copy_registry(settings, tmp_path, [("UPDATE ingest_attempts SET transformations_json = ? WHERE "
                                                "attempt_id = ?", (json.dumps(steps), att["attempt_id"]))])
    ds = [x for x in _datasets(_report(copy, settings.data_path)) if x["source_file"] == "multi.csv"]
    assert len(ds) == 2 and all(x["reproduction"].startswith("NOT EVALUABLE") for x in ds)
    want = "cannot be placed" if change == "missing" else "duplicate-removal record is incomplete"
    assert all(want in x["reproduction"] for x in ds), [x["reproduction"] for x in ds]


def test_a_missing_stored_file_is_not_evaluable(settings, db, registry, tmp_path):
    data_path = lambda r: tmp_path / "nowhere.parquet"  # noqa: E731
    assert all(x["reproduction"].startswith("NOT EVALUABLE") and "missing" in x["reproduction"]
               for x in _datasets(_report(settings.db_path, data_path)))


# ---- report files ---------------------------------------------------------------------------------------------------
def test_the_report_files_are_written_with_a_stamp(settings, db, registry, tmp_path):
    rows = _report(settings.db_path, settings.data_path)
    csv_path, txt = O.write_report(rows, tmp_path / "OW33_Impact", "03_Nov_26_120000")
    assert csv_path.name == "OW33_Impact_Report_03_Nov_26_120000.csv"
    assert txt.name == "OW33_Impact_Summary_03_Nov_26_120000.txt"
    assert sorted(p.name for p in (tmp_path / "OW33_Impact").iterdir()) == sorted([csv_path.name, txt.name])
    text = txt.read_text(encoding="utf-8")
    assert "Would change classification:    3" in text and "NOT EVALUABLE (see reason):     0" in text
