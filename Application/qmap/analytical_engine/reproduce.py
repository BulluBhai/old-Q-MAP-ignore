"""Reproduce an earlier analysis run from its Run ID (beta T7, 09-Nov-26).

`reproduce_run` reads what the earlier run recorded (Run_Metadata: analysis and version, the parameters exactly as
entered, every input dataset with its checksum, the code build) and runs the same analysis again as a NEW run (new Run
ID, new folder; the earlier run is never touched). Before anything runs it checks:

  * the analysis still exists with the same version (a changed method cannot reproduce an old result);
  * every input dataset still exists and its stored file still has the RECORDED checksum (otherwise the data differ,
    and the request is refused with the dataset named);
  * the code build: a different build does not stop the run, but is stated in the report, so a difference in the
    results can be traced to it.

After the new run has calculated, its RESULT TABLES (AnalysisSpec.result_tables) are compared byte for byte, by
SHA-256, with the earlier run's, as recorded in the registry when that run was closed. The outcome is written to
`Reproducibility_Report_<stamp>.csv` in the new run folder and under "reproduction" in its Run_Metadata.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from ..core.build import current_build
from ..core.config import Settings
from ..storage.db import Database
from ..storage.files import sha256_file


class ReproduceError(Exception):
    """The earlier run cannot be reproduced; the message says why in plain English."""


@dataclass
class EarlierRun:
    run_id: str
    folder: Path
    metadata: dict
    tables: dict  # result-table prefix -> (file name, sha256 recorded when the earlier run was closed)


def load_earlier_run(settings: Settings, db: Database, run_id: str, analyses: dict) -> EarlierRun:
    run_id = (run_id or "").strip()
    row = db.one("SELECT run_id, status, output_path FROM runs WHERE run_id = ?", (run_id,))
    if row is None:
        raise ReproduceError(f"There is no run '{run_id}' in this Q-MAP registry.")
    if row["status"] != "completed" or not row["output_path"]:
        raise ReproduceError(f"Run {run_id} did not complete, so it has no results to reproduce.")
    folder = settings.output_root.joinpath(*row["output_path"].split("/"))
    metas = sorted(folder.glob("Run_Metadata_*.json")) if folder.is_dir() else []
    if not metas:
        raise ReproduceError(f"Run {run_id} has no Run_Metadata file in {folder}; it is not an analysis run, or its "
                             "folder was moved.")
    meta = json.loads(metas[-1].read_text(encoding="utf-8"))
    spec = analyses.get(meta.get("analysis_id"))
    if spec is None:
        raise ReproduceError(f"The analysis of run {run_id} ('{meta.get('analysis_id')}') is not available in this "
                             "program.")
    if meta.get("analysis_version") != spec.version:
        raise ReproduceError(f"Run {run_id} used {spec.name} version {meta.get('analysis_version')}; this program has "
                             f"version {spec.version}. A changed method cannot reproduce the earlier result.")
    if "raw_parameters" not in meta:
        raise ReproduceError(f"Run {run_id} was made before runs recorded the parameters exactly as entered "
                             "(09-Nov-26), so it cannot be repeated exactly. Runs made from now on can.")
    for d in meta.get("input_datasets", []):
        info = db.one("SELECT dataset_id, relative_path FROM datasets WHERE dataset_id = ?", (d["dataset_id"],))
        if info is None:
            raise ReproduceError(f"Dataset {d['dataset_id']} used by run {run_id} is no longer in the registry.")
        path = settings.data_path(info["relative_path"])
        if not path.is_file():
            raise ReproduceError(f"The stored file of dataset {d['dataset_id']} ({d.get('instrument')}) is missing.")
        if sha256_file(path) != d["sha256"]:
            raise ReproduceError(f"Dataset {d['dataset_id']} ({d.get('instrument')}) is no longer the data run {run_id} "
                                 "used (its checksum differs from the one recorded), so the result cannot be "
                                 "reproduced with it.")
    recorded = {r["relative_path"].rsplit("/", 1)[-1]: r["sha256"] for r in
                db.query("SELECT relative_path, sha256 FROM run_outputs WHERE run_id = ?", (run_id,))}
    tables = {}
    for prefix in spec.result_tables:
        name = next((n for n in meta.get("outputs", []) if n.startswith(prefix)), None)
        if name is None or name not in recorded:
            raise ReproduceError(f"Run {run_id} has no recorded result table '{prefix}...'.")
        tables[prefix] = (name, recorded[name])
    return EarlierRun(run_id, folder, meta, tables)


def reproduce_run(settings: Settings, db: Database, run_id: str, *, log=None):
    """Run the earlier run again as a new run and compare. Returns the AnalysisRunResult of the new run; its
    `reproduction` (also in Run_Metadata) says whether every result table is identical."""
    from . import ANALYSES
    from .base import AnalysisRunResult, run_analysis

    try:
        earlier = load_earlier_run(settings, db, run_id, ANALYSES)
    except ReproduceError as exc:
        return AnalysisRunResult("blocked", f"Not reproduced: {exc}")
    meta = earlier.metadata
    spec = ANALYSES[meta["analysis_id"]]
    say = log or (lambda _m: None)
    say(f"Reproducing run {earlier.run_id} ({spec.name}) with its recorded datasets and parameters...")
    raw = {k: v for k, v in meta["raw_parameters"].items() if v is not None}
    ids = [d["dataset_id"] for d in meta["input_datasets"]]
    return run_analysis(settings, db, spec, ids, raw, log=log, reproduce_of={"earlier": earlier})


def compare_and_report(ctx, spec, reproduce_of: dict, outputs: list[Path]) -> tuple[Path, dict]:
    """Called by run_analysis after the new run has calculated: compare, write the report, return (path, summary)."""
    earlier: EarlierRun = reproduce_of["earlier"]
    meta = earlier.metadata
    rows = []
    build_now, build_then = current_build(), meta.get("build") or {}
    same_build = build_now.get("source_fingerprint") == build_then.get("source_fingerprint")
    rows.append(("Code build", build_then.get("source_fingerprint", "(not recorded)"),
                 build_now.get("source_fingerprint"), "same" if same_build else "DIFFERENT"))
    for d in meta["input_datasets"]:
        rows.append((f"Dataset {d['dataset_id']} ({d.get('instrument')}) checksum", d["sha256"], d["sha256"],
                     "same (checked before the run)"))
    rows.append(("Parameters", json.dumps(meta["raw_parameters"], sort_keys=True),
                 json.dumps(meta["raw_parameters"], sort_keys=True), "same (taken from the earlier run)"))
    identical = True
    for prefix, (name, sha_then) in earlier.tables.items():
        new = next((p for p in outputs if p.name.startswith(prefix)), None)
        sha_now = sha256_file(new) if new is not None else "(not produced)"
        same = sha_now == sha_then
        identical &= same
        rows.append((f"Result table {prefix}...", f"{name} sha256 {sha_then}",
                     f"{new.name if new else '-'} sha256 {sha_now}", "IDENTICAL" if same else "DIFFERENT"))
    verdict = ("REPRODUCED: every result table is identical to run " + earlier.run_id if identical else
               "NOT REPRODUCED: at least one result table differs from run " + earlier.run_id +
               ("" if same_build else " (the code build is different, see the first row)"))
    path = ctx.output(f"Reproducibility_Report_{ctx.stamp}.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("Item", f"Earlier run {earlier.run_id}", f"This run {ctx.run_id}", "Result"))
        w.writerows(rows)
        w.writerow(("Verdict", "", "", verdict))
    ctx.log(verdict)
    return path, {"of_run_id": earlier.run_id, "identical": identical, "same_build": same_build, "verdict": verdict}
