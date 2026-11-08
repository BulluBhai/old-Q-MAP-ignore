"""Acceptance W13-W18 (03-Nov-26): the six SYNTHETIC pattern files the owner scans on Windows/IDLE are scanned here
through the same Sources path, so the checklist's expected results are verified evidence, not assumptions.
Files: docs/acceptance_testing/dq7_pattern_files_03_Nov_26/ (5-minute data, Asia/Kolkata offsets in the timestamps)."""

from __future__ import annotations

import shutil
from pathlib import Path

from qmap.catalog import get_dataset
from qmap.core.runs import run_context
from qmap.data_engine import discovery as D
from qmap_gui import source_services as ss

FILES = Path(__file__).resolve().parents[2] / "docs" / "acceptance_testing" / "dq7_pattern_files_03_Nov_26"

# file -> (warning expected on the dataset or None, exception-group kind expected or None)
EXPECTED = {
    "NSE_RANDOMGAPS.csv": (None, None),
    "NSE_EVERYOTHER.csv": ("interval_change_uncertain", "interval_uncertain"),
    "NSE_GENUINE3M.csv": ("interval_change_detected", "interval_change"),
    "NSE_SPARSE.csv": (None, None),
    "NSE_DAILY0000.csv": ("interval_change_detected", "interval_change"),
    "NSE_DAILY0915.csv": ("interval_change_uncertain", "interval_uncertain"),
}


def test_the_pattern_files_give_the_checklist_results(settings, db, tmp_path):
    folder = tmp_path / "patterns"
    folder.mkdir()
    for name in EXPECTED:
        shutil.copy2(FILES / name, folder / name)
    src = D.add_folder_source(settings, db, folder)
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        res = D.scan_source(run, src.source_id)
    assert res.counts == {"imported": 6}, res.counts
    groups = {g["kind"]: g["files"] for g in ss.exception_groups(settings, src.source_id)}
    for name, (warning, kind) in EXPECTED.items():
        sym = name[4:-4]
        infos = [get_dataset(db, d) for d in _datasets_for(db, sym)]
        assert len(infos) == 1 and infos[0].timeframe == "5m", (name, infos)
        warns = infos[0].warnings
        for w in ("interval_change_detected", "interval_change_uncertain"):
            assert any(x.startswith(w) for x in warns) == (w == warning), (name, warns)
        for k in ("interval_change", "interval_uncertain"):
            assert (name in groups.get(k, [])) == (k == kind), (name, groups)
    assert any(x.startswith("partial_session") for x in get_dataset(db, _datasets_for(db, "SPARSE")[0]).warnings)
    # the per-file problem reports in the run folder carry the findings (checklist W18)
    texts = [p.read_text(encoding="utf-8", errors="ignore") for p in tmp_path.rglob("issues_event*.csv")]
    assert sum("interval_change_uncertain" in t for t in texts) == 2
    assert sum("interval_change_detected" in t for t in texts) == 2


def _datasets_for(db, symbol):
    return [r[0] for r in db.connection().execute(
        "SELECT d.dataset_id FROM datasets d JOIN instruments i ON i.instrument_id = d.instrument_id "
        "WHERE i.symbol = ? AND d.layer = 'cleaned' AND d.status = 'active'", (symbol,))]
