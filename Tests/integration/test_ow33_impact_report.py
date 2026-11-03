"""OW-33 step 1 (D5-49): the read-only impact report for Option C (sparse-only alignment). SYNTHETIC data.

Option C is NOT applied anywhere: sampling (timeframe_infer) is unchanged; the report only evaluates what Option C
would do, on the exact blocks the recorded sampling used, and the registry and files must not change."""

from __future__ import annotations

import hashlib
import random
from datetime import date

from fixtures.builders import HEADER, ohlcv, write_delimited
from fixtures.profiles import do_ingest, make_profile
from integration.test_dq7_full_file_classification import at, sess, weekdays
from qmap.data_engine import ow33_impact as O
from qmap.data_engine import timeframe_infer as T


def _load(src, run, keys, name):
    rows = [[k.isoformat()] + r for k, r in zip(keys, ohlcv(len(keys)))]
    prof = make_profile(profile_id=name, instrument={"timeframe": "infer"},
                        datetime={"kind": "iso", "exchange_timezone": "Asia/Kolkata"})
    res = do_ingest(run, write_delimited(src / f"{name}.csv", HEADER, rows), prof)
    assert res.outcome == "accepted", res.message
    return res


def sparse_keys():  # 5-minute data + 170 one-bar dates at varying times; a sampled block lands in them (seeded)
    rnd = random.Random(170)
    return sess(5, date(2023, 1, 2), 200) + [at(d, 9 + rnd.randrange(6), 15 + 5 * rnd.randrange(9))
                                            for d in weekdays(date(2023, 9, 4), 170)]


def regular_keys():  # 1-minute data with 20 days of every other bar: a sampled block lands there (MIXED today)
    return sess(1, date(2024, 1, 1), 150) + sess(1, date(2024, 6, 3), 20)[::2] + sess(1, date(2024, 7, 1), 150)


def daily_keys():  # 1-minute data with 400 daily bars at 00:00 (one time of day): MIXED today
    return sess(1, date(2022, 1, 3), 20) + [at(d, 0, 0) for d in weekdays(date(2022, 6, 6), 400)]


def test_option_c_changes_only_sparse_one_bar_blocks():
    t, o = O.evaluate_option_c(sparse_keys(), "Asia/Kolkata")
    assert (t.status, t.patterns) == ("mixed", {"5m": 14, "1D": 1})
    assert (o.status, o.timeframe, len(o.excluded_blocks)) == ("consistent", "5m", 1)
    for keys in (regular_keys(), daily_keys()):  # regular multiples and fixed-time daily bars stay MIXED
        t, o = O.evaluate_option_c(keys, "Asia/Kolkata")
        assert t.status == "mixed" and (o.status, o.excluded_blocks) == ("mixed", []), (t.patterns, o)


def test_option_c_never_touches_a_file_without_a_minute_block():
    """A daily file stamped at varying times (e.g. last-trade time) has no minute block: nothing is excluded."""
    rnd = random.Random(1)
    keys = [at(d, 9 + rnd.randrange(6), rnd.randrange(60)) for d in weekdays(date(2022, 1, 3), 300)]
    t, o = O.evaluate_option_c(keys, "Asia/Kolkata")
    assert o.excluded_blocks == [] and o.status == t.status


def test_the_report_lists_mixed_datasets_reproduces_the_seed_and_changes_nothing(settings, db, src, run):
    _load(src, run, sparse_keys(), "sparse")
    _load(src, run, regular_keys(), "regular")
    _load(src, run, sess(5, date(2024, 1, 1), 30), "plain")  # consistent 5m: not in the report
    before = hashlib.sha256(settings.db_path.read_bytes()).hexdigest()
    conn = O.open_read_only(settings.db_path)
    try:
        rows = O.impact_rows(conn, settings.data_path)
    finally:
        conn.close()
    assert hashlib.sha256(settings.db_path.read_bytes()).hexdigest() == before  # read-only
    by = {r["source_file"]: r for r in rows}
    assert set(by) == {"sparse.csv", "regular.csv"}, by.keys()
    s, r = by["sparse.csv"], by["regular.csv"]
    assert s["instrument"] == "NSE:TEST" and s["dataset_id"] and s["blocks"]
    assert s["seed_reproduced"] == r["seed_reproduced"] == "yes"
    assert (s["current_classification"], s["proposed_classification_option_c"], s["would_change"]) == ("MIXED", "5m", "yes")
    assert "one-bar dates at varying times" in s["reason"] and "superseded" in s["processing_and_lineage"]
    assert (r["proposed_classification_option_c"], r["would_change"]) == ("MIXED", "no")
    assert O.summary(rows) == {"mixed_datasets": 2, "would_change": 1, "unchanged": 1, "not_evaluable": 0}


def test_a_dataset_whose_sampling_cannot_be_reproduced_is_not_evaluable(settings, db, src, run):
    _load(src, run, sparse_keys(), "sparse")
    # simulate a stored file that is missing: the report must say so, not guess
    path = next(settings.data_root.rglob("*.parquet"))
    path.rename(path.with_suffix(".moved"))
    conn = O.open_read_only(settings.db_path)
    try:
        rows = O.impact_rows(conn, settings.data_path)
    finally:
        conn.close()
    assert rows and all(x["would_change"] == "unknown" and x["proposed_classification_option_c"] == "not evaluable"
                        for x in rows), rows


def test_the_report_files_are_written_with_a_stamp(tmp_path):
    row = {k: "" for k in O.REPORT_COLUMNS} | {"would_change": "yes"}
    csv_path, txt = O.write_report([row], tmp_path / "OW33_Impact", "03_Nov_26_120000")
    assert csv_path.name == "OW33_Impact_Report_03_Nov_26_120000.csv" and csv_path.is_file()
    assert "Would change classification:    1" in txt.read_text(encoding="utf-8")


def test_sampling_itself_is_unchanged():
    t = T.infer_interval(sparse_keys(), zone="Asia/Kolkata")
    assert t.status == "mixed"  # Option C is not applied to the real sampling
