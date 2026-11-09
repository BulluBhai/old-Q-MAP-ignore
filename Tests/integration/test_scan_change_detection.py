"""Folder-scan change detection (review of 04-Nov-26, items A1 and A2).

A1 (D5-08): the current SHA-256 is always part of the unchanged-file test. A file whose contents change while its
size stays the same and its modification time is restored must be detected and processed again, and a file that
changes during the scan must never be registered with an interpretation made from its earlier contents.

A2: every setting that can change how a file is interpreted or validated is part of the inputs fingerprint
(timeframe_sampling, the resolved requirement set of the automatic profiles, the file-size limit, the cleaning-code
version), so changing one makes the next scan re-evaluate the file. Under the current (default) settings the
fingerprint is unchanged, so nothing is re-evaluated in bulk.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from datetime import date

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.core.runs import run_context
from qmap.data_engine import auto_interpret as A
from qmap.data_engine import discovery as D
from qmap.data_engine.instrument_names import registry_path


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    f.mkdir()
    return f


@pytest.fixture
def source(settings, db, folder):
    return D.add_folder_source(settings, db, folder, market_timezone="Asia/Kolkata", default_exchange="NSE")


def scan(settings, db, source, **kw):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, source.source_id, **kw)


def daily(path, n=30, seed=1, start=date(2026, 1, 5)):
    rows = ohlcv(n, seed)
    return write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(len(rows), start), rows)])


def outcome_of(result, rel):
    return next(f for f in result.files if f[0] == rel)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_size_edit(path) -> bytes:
    """Change one digit of the last volume value: same size, still valid data, different contents."""
    data = path.read_bytes()
    body = data.rstrip(b"\r\n")
    i = len(body) - 1
    while not body[i:i + 1].isdigit():
        i -= 1
    old = body[i:i + 1]
    new = b"7" if old != b"7" else b"3"
    changed = data[:i] + new + data[i + 1:]
    assert len(changed) == len(data) and changed != data
    return changed


def raw_shas(db):
    return {r["sha256"] for r in db.query("SELECT sha256 FROM datasets WHERE layer = 'raw'")}


# ---- A1 -------------------------------------------------------------------------------------------------------------

def test_a_same_contents_same_size_and_time_is_unchanged(settings, db, source, folder):
    p = daily(folder / "NSE_ABC.csv")
    scan(settings, db, source)
    r = scan(settings, db, source)
    assert outcome_of(r, "NSE_ABC.csv")[1:3] == ("unchanged", "skipped")
    obs = D.file_history(db, source.source_id, "NSE_ABC.csv")[-1]
    assert obs["sha256"] == sha(p)  # the checksum recorded for the skip is the one calculated now


def test_b_changed_contents_with_same_size_and_restored_time_are_detected(settings, db, source, folder):
    p = daily(folder / "NSE_ABC.csv")
    scan(settings, db, source)
    before = p.stat()
    first_sha = sha(p)
    p.write_bytes(same_size_edit(p))
    os.utime(p, ns=(before.st_atime_ns, before.st_mtime_ns))  # as a sync or copy tool may do
    after = p.stat()
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    r = scan(settings, db, source)
    change, action, outcome = outcome_of(r, "NSE_ABC.csv")[1:4]
    assert (change, action) == ("changed", "processed")
    assert outcome == "imported"
    assert raw_shas(db) == {first_sha, sha(p)}  # the new contents are registered under their own checksum
    obs = D.file_history(db, source.source_id, "NSE_ABC.csv")[-1]
    assert obs["sha256"] == sha(p) and obs["change"] == "changed"


def test_c_a_file_changed_during_the_scan_is_not_registered_under_the_earlier_checksum(settings, db, source, folder,
                                                                                       monkeypatch):
    p = daily(folder / "NSE_ABC.csv")
    examined = sha(p)
    changed = same_size_edit(p)
    real = A.interpret_file

    def interpret_then_change(path, *a, **k):  # the file is rewritten after Q-MAP examined it, before loading
        out = real(path, *a, **k)
        if path.read_bytes() != changed:
            path.write_bytes(changed)
        return out

    monkeypatch.setattr(A, "interpret_file", interpret_then_change)
    r = scan(settings, db, source)
    outcome, detail = outcome_of(r, "NSE_ABC.csv")[3:5]
    assert outcome == "failed" and "changed after it was examined" in detail
    assert db.one("SELECT COUNT(*) FROM datasets")[0] == 0  # nothing registered at all
    event = db.one("SELECT * FROM ingest_events ORDER BY event_id DESC LIMIT 1")
    assert event["status"] == "failed" and event["raw_dataset_id"] is None and event["sha256"] == sha(p) != examined
    # the next scan (file now stable) processes the new contents normally
    monkeypatch.setattr(A, "interpret_file", real)
    r = scan(settings, db, source)
    assert outcome_of(r, "NSE_ABC.csv")[3] == "imported" and raw_shas(db) == {sha(p)}


def test_source_files_are_never_modified_by_scanning(settings, db, source, folder):
    p = daily(folder / "NSE_ABC.csv")
    original = p.read_bytes()
    st = p.stat()
    for _ in range(2):
        scan(settings, db, source)
    assert p.read_bytes() == original and p.stat().st_mtime_ns == st.st_mtime_ns


# ---- A2 -------------------------------------------------------------------------------------------------------------

def _legacy_fingerprint(src, answer_row, settings):
    """The fingerprint formula before review item A2 (kept here to prove nothing is re-evaluated in bulk)."""
    reg = registry_path(settings)
    aliases = hashlib.sha256(reg.read_bytes()).hexdigest()[:16] if reg.is_file() else None
    payload = {"rules": A.RULES_VERSION, "tz": src.market_timezone, "exch": src.default_exchange, "aliases": aliases,
               "sym_from_name": src.symbol_from_filename, "answer": answer_row["answer_id"] if answer_row else None,
               "validation": [str(settings.plausible_min_date), settings.plausible_max_days_ahead,
                              settings.max_daily_move_pct, settings.min_rows, settings.max_gap_days]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def test_default_settings_keep_the_existing_fingerprint(settings, source):
    assert D._fingerprint_extensions(settings) == {}
    assert D._inputs_fingerprint(source, None, settings) == _legacy_fingerprint(source, None, settings)
    # values written out explicitly but equal to the defaults are resolved first: still no change
    explicit = dataclasses.replace(settings, timeframe_sampling={"initial_rows": 20, "blocks_daily": 5})
    assert D._inputs_fingerprint(source, None, explicit) == _legacy_fingerprint(source, None, settings)


@pytest.mark.parametrize("change", [
    {"timeframe_sampling": {"initial_rows": 25}},
    {"timeframe_sampling": {"consistency_share": 0.95}},
    {"requirement_sets": {"price_only": {"require_volume": True}, "price_volume": {"require_volume": True}}},
    {"max_file_size_mb": 1},
], ids=["sampling_rows", "sampling_share", "require_volume", "max_file_size"])
def test_changing_an_interpretation_setting_changes_the_fingerprint(settings, source, change):
    changed = dataclasses.replace(settings, **change)
    assert D._inputs_fingerprint(source, None, changed) != D._inputs_fingerprint(source, None, settings)


def test_a_cleaning_code_version_change_changes_the_fingerprint(settings, source, monkeypatch):
    import qmap

    before = D._inputs_fingerprint(source, None, settings)
    monkeypatch.setattr(qmap, "CLEANING_CODE_VERSION", "c3")
    assert D._inputs_fingerprint(source, None, settings) != before


@pytest.mark.parametrize("change", [
    {"timeframe_sampling": {"blocks_daily": 6}},
    {"requirement_sets": {"price_only": {"require_volume": True}, "price_volume": {"require_volume": True}}},
], ids=["timeframe_sampling", "require_volume"])
def test_the_next_scan_re_evaluates_an_unchanged_file_after_a_setting_change(settings, db, source, folder, change):
    daily(folder / "NSE_ABC.csv")
    scan(settings, db, source)
    assert outcome_of(scan(settings, db, source), "NSE_ABC.csv")[2] == "skipped"  # current settings: no re-evaluation
    changed = dataclasses.replace(settings, **change)
    r = scan(changed, db, source)
    change_kind, action = outcome_of(r, "NSE_ABC.csv")[1:3]
    assert (change_kind, action) == ("unchanged", "processed")
    # and with the changed settings kept, the following scan skips again
    assert outcome_of(scan(changed, db, source), "NSE_ABC.csv")[2] == "skipped"


def test_the_w19_acceptance_files_behave_as_the_manual_says(settings, db, source, folder):
    """Windows manual W19: version B replaces version A with the same size and the same modification time."""
    from pathlib import Path

    base = Path(__file__).resolve().parents[2] / "docs" / "acceptance_testing" / "w19_same_size_files_04_Nov_26"
    a, b = (base / v / "NSE_SAMESIZE.csv" for v in ("version_A", "version_B"))
    assert a.stat().st_size == b.stat().st_size and a.read_bytes() != b.read_bytes()
    target = folder / "NSE_SAMESIZE.csv"
    target.write_bytes(a.read_bytes())
    stamp = target.stat()
    assert outcome_of(scan(settings, db, source), "NSE_SAMESIZE.csv")[3] == "imported"
    target.write_bytes(b.read_bytes())  # as File Explorer's copy-and-replace: content changes, the date is kept
    os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    r = scan(settings, db, source)
    assert outcome_of(r, "NSE_SAMESIZE.csv")[1:4] == ("changed", "processed", "imported")
    assert len([d for d in db.query("SELECT 1 FROM datasets WHERE layer = 'cleaned'")]) == 2
