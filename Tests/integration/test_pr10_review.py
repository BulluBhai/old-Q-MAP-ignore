"""PR #10 review (03-Nov-26): canonical display names, conflict counts at the points of use, reprocessing provenance.
All data are SYNTHETIC."""

from __future__ import annotations

import csv
import hashlib

import pytest

from fixtures.builders import HEADER, daily_rows, ohlcv, weekdays, write_delimited
from fixtures.profiles import do_ingest
from qmap.analytical_engine import DATASET_SUMMARY, run_analysis
from qmap.catalog import check_readiness, get_dataset, list_datasets, provenance
from qmap.core.runs import run_context
from qmap.data_engine import auto_interpret as A
from qmap.data_engine import discovery as D
from qmap.data_engine import ingest as ING
from qmap.data_engine.derive import derive_timeframe
from qmap.data_engine.instruments import record_display_name
from qmap.data_engine.instrument_names import registry_path


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    f.mkdir()
    return f


def scan(settings, db, src):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, src.source_id)


def daily(path, n=12, seed=1):
    return write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(n), ohlcv(n, seed))])


# ---- 2: canonical display name ----------------------------------------------------------------------------------
def test_the_canonical_display_name_is_kept_beside_the_machine_safe_symbol(settings, db, folder):
    path = registry_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Canonical name,Alias 1\nNIFTY 50,NIFTY\n", encoding="utf-8")
    daily(folder / "NIFTY (1).csv")
    src = D.add_folder_source(settings, db, folder)
    scan(settings, db, src)
    (ds,) = list_datasets(db)
    assert (ds.instrument, ds.instrument_name) == ("NSE:NIFTY_50", "NIFTY 50")
    inst = db.one("SELECT * FROM instruments WHERE symbol = 'NIFTY_50'")
    assert inst["name"] == "NIFTY 50"
    # an existing name is never overwritten silently; a provisional identity gets no display name
    assert record_display_name(db, inst["instrument_id"], "Nifty Fifty") is False
    assert db.one("SELECT name FROM instruments WHERE instrument_id = ?", (inst["instrument_id"],))["name"] == "NIFTY 50"
    daily(folder / "UNKNOWNCO.csv", seed=3)
    scan(settings, db, src)
    assert db.one("SELECT name FROM instruments WHERE symbol = 'UNKNOWNCO'")["name"] is None


# ---- 3: conflicts at the points of use, counts kept apart --------------------------------------------------------
def _conflicted(src, run):
    rows = [list(r) for r in daily_rows(8)]
    rows.insert(3, [rows[2][0], rows[2][1], rows[2][2] + 1, rows[2][3], rows[2][4] + 0.5, rows[2][5]])  # conflict
    rows.insert(4, [rows[2][0], rows[2][1], rows[2][2] + 2, rows[2][3], rows[2][4] + 0.7, rows[2][5]])  # 3rd obs.
    rows.append(list(rows[-1]))  # exact duplicate
    rows.append(list(rows[-1]))  # another exact duplicate
    res = do_ingest(run, write_delimited(src / "c.csv", HEADER, rows))
    assert res.outcome == "accepted", res.message
    return res.dataset_ids[0]


def test_summary_keeps_conflicting_timestamps_rows_and_removed_duplicates_apart(src, run, settings, db):
    ds = _conflicted(src, run)
    res = run_analysis(settings, db, DATASET_SUMMARY, [ds], {})
    assert res.ok
    row = next(csv.DictReader(open(res.outputs[0], encoding="utf-8")))
    assert row["Bars"] == "10"  # 8 dates + 2 extra observations of one date; the 2 identical copies are not stored
    assert (row["Conflicting timestamps"], row["Conflicting observation rows"]) == ("1", "3")
    assert row["Returns between conflicting observations"] == "2"
    assert row["Exact duplicate rows removed at load"] == "2"
    assert row["Derived bars built from conflicting observations"] == ""
    assert row["Conflict note"].startswith("Potentially misleading: 1 timestamp(s) hold 3 conflicting observations")
    assert row["Returns counted"] == "9"  # the method is unchanged: every stored row is a bar
    log = (res.run_dir / "run_log.txt").read_text(encoding="utf-8")
    assert f"WARNING dataset {ds}: Potentially misleading" in log
    import json
    meta = json.loads(res.metadata_path.read_text(encoding="utf-8"))
    assert "conflicting observations" in json.dumps(meta["readiness_warnings"]).lower()  # recorded with the run


def test_workbench_readiness_and_derivation_show_the_conflict(src, run, settings, db):
    from qmap_gui import workbench_services as ws

    ds = _conflicted(src, run)
    res = ws.check(settings, DATASET_SUMMARY.analysis_id, [ds], {})
    assert res.ready and any(i.name == "conflicts" for r in res.reports for i in r.items)
    text = "".join(t for t, _ in ws.readiness_parts(res))
    assert "Unresolved conflicting observations" in text
    out = derive_timeframe(run, ds, "1W")
    assert out.ok and any("conflicting observations" in w for w in out.assessment.warnings)
    summ = run_analysis(settings, db, DATASET_SUMMARY, [out.dataset_id], {})
    row = next(csv.DictReader(open(summ.outputs[0], encoding="utf-8")))
    assert row["Derived bars built from conflicting observations"] == "1" and row["Conflicting timestamps"] == ""
    assert "derived bar(s) were built from daily data with conflicting observations" in row["Conflict note"]
    assert check_readiness(settings, db, out.dataset_id, DATASET_SUMMARY.requirement).ready


# ---- 4: reprocessing after this update keeps provenance ------------------------------------------------------------
def test_reprocessing_after_the_update_keeps_every_record_and_links_correctly(settings, db, folder, monkeypatch):
    files = [daily(folder / "NSE_AAA.csv"), daily(folder / "NSE_BBB.csv", seed=2)]
    before = {p.name: sha(p) for p in files}
    src = D.add_folder_source(settings, db, folder)
    # the registry as the previous code left it: cleaning code c1, rules v5
    monkeypatch.setattr(ING, "CLEANING_CODE_VERSION", "c1")
    monkeypatch.setattr(A, "RULES_VERSION", 5)
    scan(settings, db, src)
    old = {d.instrument: d for d in list_datasets(db)}
    aaa = old["NSE:AAA"]
    with run_context(settings, db, "DBM", area="Data_Management") as run:
        weekly = derive_timeframe(run, aaa.dataset_id, "1W")
    summary = run_analysis(settings, db, DATASET_SUMMARY, [aaa.dataset_id], {})
    raws_before = db.query("SELECT dataset_id, sha256, relative_path FROM datasets WHERE layer = 'raw' ORDER BY 1")
    monkeypatch.undo()

    scan(settings, db, src)  # the first scan after the update
    # raw source files and stored originals: unchanged, not duplicated
    assert {p.name: sha(p) for p in files} == before
    assert db.query("SELECT dataset_id, sha256, relative_path FROM datasets WHERE layer = 'raw' ORDER BY 1") == raws_before
    for r in raws_before:
        assert sha(settings.data_path(r["relative_path"])) == r["sha256"]
    new = {d.instrument: d for d in list_datasets(db, include_superseded=False) if d.layer == "cleaned"}
    for inst, o in old.items():
        o_now, n = get_dataset(db, o.dataset_id), new[inst]
        assert o_now.status == "superseded" and settings.data_path(o_now.relative_path).is_file()  # old kept
        assert db.one("SELECT superseded_by_dataset_id FROM datasets WHERE dataset_id = ?", (o.dataset_id,))[0] == \
            n.dataset_id
        assert n.parent_dataset_id == o.parent_dataset_id  # the same original file
        assert n.processing_version.endswith("+c2") and o.processing_version.endswith("+c1")
        ev = db.one("SELECT e.original_filename FROM datasets d JOIN ingest_attempts a ON a.attempt_id = "
                    "d.created_by_attempt_id JOIN ingest_events e USING (event_id) WHERE d.dataset_id = ?",
                    (n.dataset_id,))[0]
        assert ev == inst.split(":")[1].join(["NSE_", ".csv"])
        assert provenance(db, n.dataset_id) and provenance(db, o.dataset_id)
    # the derived dataset keeps its valid lineage to the (now superseded) daily dataset it was built from
    w = get_dataset(db, weekly.dataset_id)
    assert w.parent_dataset_id == aaa.dataset_id and w.status == "active"
    assert db.one("SELECT source_dataset_id FROM dataset_derivations WHERE dataset_id = ?", (w.dataset_id,))[0] == \
        aaa.dataset_id
    # the earlier run and its outputs stay traceable to the dataset it used
    assert db.one("SELECT dataset_id FROM run_inputs WHERE run_id = ?", (summary.run_id,))[0] == aaa.dataset_id
    assert all(p.is_file() for p in summary.outputs)
    # a second unchanged scan creates nothing
    n_before = db.one("SELECT COUNT(*) FROM datasets")[0]
    res = scan(settings, db, src)
    assert db.one("SELECT COUNT(*) FROM datasets")[0] == n_before
    assert {f[1:3] for f in res.files} == {("unchanged", "skipped")}
