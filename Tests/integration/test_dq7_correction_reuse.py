"""Processing identity and reuse after the DQ-7 correction of 04-Nov-26 (owner instruction, 04-Nov-26).

The correction (1291d63) is deliberately NOT a new processing version, cleaning-code version or fingerprint scheme:
that would reprocess and supersede every dataset (not authorised). This test establishes, end to end and
deterministically, what happens instead:

1. a mixed daily/weekly file loaded with the ORIGINAL comparison (emulated exactly: the old unit check, and inference
   records without the new marker) is registered 1D;
2. after the correction, a scan of the identical, unchanged file in the same folder SKIPS it: the old result is kept,
   no attempt and no dataset are created, nothing is superseded - and the old result is NOT presented as corrected:
   the dataset, the Sources details, the readiness check and Run_Metadata say it was classified earlier and that the
   corrected comparison would give MIXED (judged read-only from the blocks recorded at the time);
3. the identical content arriving as a new file (another folder) and a genuinely new file are classified by the
   corrected comparison (MIXED, marked as corrected); the earlier dataset stays unchanged and active;
4. a uniform file loaded earlier is recognised as "same result" and is not flagged.
"""

from __future__ import annotations

import json
import shutil
from datetime import date

import pytest

from fixtures.builders import HEADER, ohlcv, write_delimited
from qmap.analytical_engine import DATASET_SUMMARY, MA_AFFINITY, check_analysis, run_analysis
from qmap.catalog import get_dataset, list_datasets
from qmap.core.runs import run_context
from qmap.core.timeframes import CORRECTED, EARLIER_CHANGED, EARLIER_SAME, INFERENCE_LOGIC
from qmap.data_engine import discovery as D
from qmap.data_engine import timeframe_infer as T
from qmap_gui import source_services as ss
from qmap_gui.registry_services import details
from test_dq7_calendar_units import MIXED_CASES, UNIFORM_CASES, month_ends, weekdays


@pytest.fixture
def original_logic(monkeypatch):
    """The comparison and the inference record exactly as before 1291d63 / this change."""
    old_as_dict = T.Inference.as_dict

    def as_dict_without_marker(self):
        d = old_as_dict(self)
        d.pop("logic", None)
        return d

    monkeypatch.setattr(T, "_measuring_unit", lambda label: "minute" if T._is_minutes(label) else "calendar")
    monkeypatch.setattr(T.Inference, "as_dict", as_dict_without_marker)
    return monkeypatch


def _write(path, keys, seed=1):
    write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(keys, ohlcv(len(keys), seed=seed))])
    return path


def _scan(settings, db, src):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, src.source_id)


def _count(db, table):
    return db.one(f"SELECT COUNT(*) AS n FROM {table}")["n"]


def test_unchanged_file_keeps_its_earlier_result_and_is_disclosed_new_files_use_the_correction(
        settings, db, tmp_path, original_logic):
    mixed, _ = MIXED_CASES["daily then weekly"]
    uniform, _ = UNIFORM_CASES["daily with weekends, random holidays and a holiday week"]
    a = tmp_path / "A"
    a.mkdir()
    _write(a / "NSE_DAYWEEK.csv", mixed)
    _write(a / "NSE_UNIFORM.csv", uniform, seed=2)
    src_a = D.add_folder_source(settings, db, a)

    # 1. original logic
    _scan(settings, db, src_a)
    old = {d.instrument: d for d in list_datasets(db)}
    assert old["NSE:DAYWEEK"].timeframe == "1D"  # the defect: a daily+weekly file registered as one timeframe
    assert old["NSE:UNIFORM"].timeframe == "1D"
    before = {k: (d.dataset_id, d.sha256, d.status, d.processing_version) for k, d in old.items()}
    attempts, datasets = _count(db, "ingest_attempts"), _count(db, "datasets")

    # 2. corrected code, identical unchanged files, same folder
    original_logic.undo()
    res = _scan(settings, db, src_a)
    assert {f[0]: (f[1], f[2]) for f in res.files} == {"NSE_DAYWEEK.csv": ("unchanged", "skipped"),
                                                       "NSE_UNIFORM.csv": ("unchanged", "skipped")}
    assert (_count(db, "ingest_attempts"), _count(db, "datasets")) == (attempts, datasets)  # nothing processed again
    now = {d.instrument: d for d in list_datasets(db)}
    assert {k: (d.dataset_id, d.sha256, d.status, d.processing_version) for k, d in now.items()} == before
    assert now["NSE:DAYWEEK"].timeframe == "1D"  # classification kept, not changed

    # ... and disclosed, not presented as corrected
    dw, un = now["NSE:DAYWEEK"], now["NSE:UNIFORM"]
    assert (dw.timeframe_logic, un.timeframe_logic) == (EARLIER_CHANGED, EARLIER_SAME)
    assert "would classify this file as MIXED" in dw.timeframe_logic_note and "daily, weekly" in dw.timeframe_logic_note
    text = "".join(t for t, _tag in details(settings, dw.dataset_id))
    assert "would classify this file as MIXED" in text
    state = next(s for s in ss.files(settings, src_a.source_id) if s.relative_path == "NSE_DAYWEEK.csv")
    assert "Earlier classification" in "".join(t for t, _ in ss.file_details(state))
    ma = check_analysis(settings, db, MA_AFFINITY, [dw.dataset_id], {})
    assert not ma.ready and any(f.name == "timeframe_logic" for r in ma.reports for f in r.failures)
    ma_uniform = check_analysis(settings, db, MA_AFFINITY, [un.dataset_id], {"ma_end": "40"})
    assert not any(i.name == "timeframe_logic" for r in ma_uniform.reports for i in r.items)  # not flagged
    summary = run_analysis(settings, db, DATASET_SUMMARY, [dw.dataset_id], {})
    assert summary.outcome == "completed"  # Dataset Summary allows mixed data, with the NOTE
    assert any("would classify this file as MIXED" in w for w in summary.readiness.warnings)
    meta = json.loads(summary.metadata_path.read_text(encoding="utf-8"))
    assert "would give MIXED" in meta["input_datasets"][0]["timeframe_classified_by"]

    # 3a. identical content as a new file (another folder): the corrected comparison runs; the old dataset is kept
    b = tmp_path / "B"
    b.mkdir()
    shutil.copy2(a / "NSE_DAYWEEK.csv", b / "NSE_DAYWEEK.csv")
    _scan(settings, db, D.add_folder_source(settings, db, b))
    new = [d for d in list_datasets(db) if d.instrument == "NSE:DAYWEEK" and d.dataset_id != dw.dataset_id]
    assert [(d.timeframe, d.timeframe_logic, d.status) for d in new] == [("MIXED", CORRECTED, "active")]
    record = json.loads(db.one("SELECT datetime_rules_json FROM ingest_attempts WHERE attempt_id = (SELECT "
                               "created_by_attempt_id FROM datasets WHERE dataset_id = ?)", (new[0].dataset_id,))
                        ["datetime_rules_json"])["timeframe_inference"]
    assert record["logic"] == INFERENCE_LOGIC and record["status"] == "mixed"
    kept = get_dataset(db, dw.dataset_id)
    assert (kept.timeframe, kept.status, kept.sha256) == ("1D", "active", before["NSE:DAYWEEK"][1])  # not superseded

    # 3b. a genuinely new file
    c = tmp_path / "C"
    c.mkdir()
    daily = weekdays(date(2005, 1, 3), 400)
    _write(c / "NSE_NEWMIX.csv", daily + month_ends(date(2007, 1, 1), 120), seed=5)  # daily then monthly, all past
    _write(c / "NSE_NEWDAILY.csv", uniform, seed=6)
    _scan(settings, db, D.add_folder_source(settings, db, c))
    fresh = {d.instrument: d for d in list_datasets(db) if d.instrument in ("NSE:NEWMIX", "NSE:NEWDAILY")}
    assert fresh["NSE:NEWMIX"].timeframe == "MIXED"
    assert (fresh["NSE:NEWDAILY"].timeframe, fresh["NSE:NEWDAILY"].timeframe_logic) == ("1D", CORRECTED)
    assert "corrected DQ-7 comparison" in "".join(t for t, _ in details(settings, fresh["NSE:NEWDAILY"].dataset_id))


def test_derived_weekly_data_inherit_the_earlier_classification_note(settings, db, tmp_path, original_logic, run):
    from qmap.data_engine.derive import derive_timeframe

    a = tmp_path / "A"
    a.mkdir()
    _write(a / "NSE_DAYWEEK.csv", MIXED_CASES["daily then weekly"][0])
    _scan(settings, db, D.add_folder_source(settings, db, a))
    original_logic.undo()
    (daily,) = list_datasets(db)
    derive_timeframe(run, daily.dataset_id, "1W")
    weekly = next(d for d in list_datasets(db) if d.timeframe == "1W")
    assert weekly.timeframe_logic == EARLIER_CHANGED  # built from a daily dataset that the correction would call MIXED
    chk = check_analysis(settings, db, MA_AFFINITY, [weekly.dataset_id], {"ma_end": "20"})
    assert any(f.name == "timeframe_logic" for r in chk.reports for f in r.failures)


def test_a_change_of_the_folder_inputs_reinterprets_with_the_correction_and_keeps_the_earlier_dataset(
        settings, db, tmp_path, original_logic):
    """E.g. the alias-registry edit of acceptance check W5: the scan reads the file again."""
    from qmap.data_engine.instrument_names import registry_path

    a = tmp_path / "A"
    a.mkdir()
    _write(a / "NSE_DAYWEEK.csv", MIXED_CASES["daily then weekly"][0])
    src = D.add_folder_source(settings, db, a)
    _scan(settings, db, src)
    original_logic.undo()
    reg = registry_path(settings)
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text((reg.read_text(encoding="utf-8") if reg.exists() else "canonical,alias1\n") + "RELIANCE,RELIANCE EQ\n",
                   encoding="utf-8")
    res = _scan(settings, db, src)
    assert [(f[1], f[2]) for f in res.files] == [("unchanged", "processed")]
    got = sorted((d.timeframe, d.status, d.timeframe_logic) for d in list_datasets(db))
    assert got == [("1D", "active", EARLIER_CHANGED), ("MIXED", "active", CORRECTED)]
