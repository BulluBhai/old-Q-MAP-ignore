"""Batch 4 (10-Nov-26): every run records the Python and library versions its results depend on, and a reproduction
states whether they differ (a library upgrade can change the last digits of a result table)."""

from __future__ import annotations

import csv
import json
import platform
from datetime import date

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from fixtures.profiles import do_ingest
from qmap.analytical_engine import MA_AFFINITY_V2, run_analysis
from qmap.analytical_engine import reproduce as R
from qmap.core import build as B

SMALL = {"ma_start": "5", "ma_end": "30", "min_interactions": "5", "fwd_windows": "3,5", "regime_ma": "20",
         "chance_shuffles": "3"}


def test_library_versions_are_part_of_the_build_but_not_of_the_fingerprint(tmp_path):
    libs = B.library_versions()
    assert libs["python"] == platform.python_version()
    assert set(B.LIBRARIES) <= set(libs) and libs["numpy"] and libs["pandas"]
    (tmp_path / "Application").mkdir()
    (tmp_path / "Application" / "x.py").write_text("x = 1\n")
    info = B.build_info(tmp_path)
    assert info["libraries"] == libs and info["source_fingerprint"] == B.source_fingerprint(tmp_path)


def test_runs_record_libraries_and_a_reproduction_compares_them(settings, db, run, src, monkeypatch):
    rows = [[d.isoformat()] + r for d, r in zip(weekdays(400, date(2021, 1, 4)), ohlcv(400, seed=2, base=200.0))]
    ds = do_ingest(run, write_delimited(src / "NSE_LIBS.csv", HEADER, rows)).dataset_ids[0]
    first = run_analysis(settings, db, MA_AFFINITY_V2, [ds], SMALL)
    meta = json.loads(first.metadata_path.read_text(encoding="utf-8"))
    assert meta["build"]["libraries"] == B.current_build()["libraries"]
    same = R.reproduce_run(settings, db, first.run_id)
    assert same.reproduction["same_libraries"] is True and same.reproduction["identical"]
    rows = list(csv.reader(next(same.run_dir.glob("Reproducibility_Report_*.csv")).open(encoding="utf-8")))
    assert rows[2][0] == "Python and library versions" and rows[2][-1] == "same"
    # a different numpy version is reported (results may still be identical)
    changed = {**B.current_build(), "libraries": {**B.current_build()["libraries"], "numpy": "0.0.0"}}
    monkeypatch.setattr(R, "current_build", lambda: changed)
    other = R.reproduce_run(settings, db, first.run_id)
    assert other.reproduction["same_libraries"] is False
    rows = list(csv.reader(next(other.run_dir.glob("Reproducibility_Report_*.csv")).open(encoding="utf-8")))
    assert rows[2][-1] == "DIFFERENT" and "numpy 0.0.0" in rows[2][2]
