"""Reproduce an earlier analysis run from its Run ID (beta T7, 09-Nov-26).

`reproduce_run` reads what the earlier run recorded (Run_Metadata: analysis and version, the parameters exactly as
entered, every input dataset with its checksum, the code build) and runs the same analysis again as a NEW run (new Run
ID, new folder; the earlier run is never touched). Before anything runs it checks:

  * the analysis still exists with the same version (a changed method cannot reproduce an old result);
  * every input dataset still exists and its stored file still has the RECORDED checksum (otherwise the data differ,
    and the request is refused with the dataset named);
  * the code build: a different build does not stop the run, but is stated in the report, so a difference in the
    results can be traced to it.
  * the record itself (09-Nov-26 closure): exactly one readable Run_Metadata holding a JSON object with every field
    reproduction uses, of the right kind (run_id, raw_parameters = exactly this analysis's parameters as text,
    a non-empty input_datasets list with dataset numbers and SHA-256 checksums, outputs as plain file names); the run
    folder and the dataset files inside the Q-MAP folders; the earlier result tables present and unchanged since the
    run closed. Expected problems (damaged or incomplete record, unreadable or moved files) are refusals with the
    reason; nothing is run or written. Programming defects are not caught here and stay visible.

After the new run has calculated, its RESULT TABLES (AnalysisSpec.result_tables) are compared byte for byte, by
SHA-256, with the earlier run's, as recorded in the registry when that run was closed. The outcome is written to
`Reproducibility_Report_<stamp>.csv` in the new run folder and under "reproduction" in its Run_Metadata.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..core.build import current_build
from ..core.config import Settings, UnsafeDataPath
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


_SHA256 = re.compile(r"[0-9a-f]{64}")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _plain_name(name) -> bool:
    return isinstance(name, str) and name not in ("", ".", "..") and not any(c in name for c in "/\\:")


def _read_metadata(run_id: str, folder: Path) -> dict:
    """The earlier run's Run_Metadata as a dict, or a ReproduceError saying plainly what is wrong with it."""
    metas = sorted(folder.glob("Run_Metadata_*.json"))
    if not metas:
        raise ReproduceError(f"Run {run_id} has no Run_Metadata file in {folder}; it is not an analysis run, or its "
                             "folder was moved.")
    if len(metas) > 1:
        raise ReproduceError(f"Run {run_id} has {len(metas)} Run_Metadata files in {folder}; a run has exactly one, so "
                             "Q-MAP cannot tell which is the record.")
    try:
        text = metas[0].read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ReproduceError(f"The Run_Metadata file of run {run_id} cannot be read ({exc}).") from None
    if not text.strip():
        raise ReproduceError(f"The Run_Metadata file of run {run_id} is empty.")
    try:
        meta = json.loads(text)
    except ValueError as exc:  # json.JSONDecodeError
        raise ReproduceError(f"The Run_Metadata file of run {run_id} is damaged (not valid JSON: {exc}).") from None
    if not isinstance(meta, dict):
        raise ReproduceError(f"The Run_Metadata file of run {run_id} does not hold a run record.")
    return meta


def _validated(run_id: str, meta: dict, spec) -> None:
    """Every field reproduction relies on is present and of the right kind; otherwise refuse, naming the field."""
    def bad(field: str, why: str) -> ReproduceError:
        return ReproduceError(f"The Run_Metadata of run {run_id} is incomplete or damaged: '{field}' {why}.")

    if meta.get("run_id") != run_id:
        raise bad("run_id", f"does not name this run (it says {meta.get('run_id')!r})")
    raw = meta["raw_parameters"]
    if not isinstance(raw, dict):
        raise bad("raw_parameters", "is not a list of named values")
    keys = {p.key for p in spec.parameters}
    if set(raw) != keys:
        missing, extra = sorted(keys - set(raw)), sorted(set(raw) - keys)
        raise bad("raw_parameters", "does not hold exactly this analysis's parameters"
                  + (f" (missing: {', '.join(missing)})" if missing else "")
                  + (f" (unknown: {', '.join(extra)})" if extra else ""))
    for k, v in raw.items():
        if v is not None and not isinstance(v, str):
            raise bad(f"raw_parameters.{k}", "is not text as entered")
    datasets = meta.get("input_datasets")
    if not isinstance(datasets, list) or not datasets:
        raise bad("input_datasets", "is missing or empty")
    for n, d in enumerate(datasets, start=1):
        if not isinstance(d, dict):
            raise bad(f"input_datasets[{n}]", "is not a dataset record")
        if not isinstance(d.get("dataset_id"), int) or isinstance(d.get("dataset_id"), bool) or d["dataset_id"] < 1:
            raise bad(f"input_datasets[{n}].dataset_id", "is missing or not a dataset number")
        if not isinstance(d.get("sha256"), str) or not _SHA256.fullmatch(d["sha256"]):
            raise bad(f"input_datasets[{n}].sha256", "is missing or not a SHA-256 checksum")
        if d.get("instrument") is not None and not isinstance(d["instrument"], str):
            raise bad(f"input_datasets[{n}].instrument", "is not text")
    outputs = meta.get("outputs")
    if not isinstance(outputs, list) or not all(_plain_name(n) for n in outputs):
        raise bad("outputs", "is missing or names something other than plain file names")
    if "build" in meta and not isinstance(meta["build"], dict):
        raise bad("build", "is not a build record")


def load_earlier_run(settings: Settings, db: Database, run_id: str, analyses: dict) -> EarlierRun:
    """Everything a reproduction needs from the earlier run, checked before anything runs. Any expected problem with
    the record, the folders or the files is a ReproduceError (a plain refusal); nothing is written or changed here."""
    run_id = (run_id or "").strip()
    if not run_id:
        raise ReproduceError("No Run ID was given.")
    row = db.one("SELECT run_id, status, output_path FROM runs WHERE run_id = ?", (run_id,))
    if row is None:
        raise ReproduceError(f"There is no run '{run_id}' in this Q-MAP registry.")
    if row["status"] != "completed" or not row["output_path"]:
        raise ReproduceError(f"Run {run_id} did not complete, so it has no results to reproduce.")
    parts = str(row["output_path"]).split("/")
    folder = settings.output_root.joinpath(*parts)
    if ".." in parts or Path(row["output_path"]).is_absolute() or not _inside(folder, settings.output_root):
        raise ReproduceError(f"The recorded folder of run {run_id} ({row['output_path']}) is not inside the "
                             "Q-MAP_OUTPUT folder, so it is not used.")
    if not folder.is_dir():
        raise ReproduceError(f"The folder of run {run_id} ({folder}) is missing; it was moved or deleted.")
    meta = _read_metadata(run_id, folder)
    # checked before they are used: a damaged record can hold any JSON value here (a list or an object would make the
    # analysis lookup fail, and JSON true would compare equal to version 1)
    analysis_id, version = meta.get("analysis_id"), meta.get("analysis_version")
    if not isinstance(analysis_id, str) or not analysis_id.strip():
        raise ReproduceError(f"The Run_Metadata of run {run_id} is incomplete or damaged: 'analysis_id' is missing or "
                             "not an analysis name.")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ReproduceError(f"The Run_Metadata of run {run_id} is incomplete or damaged: 'analysis_version' is "
                             "missing or not a version number.")
    spec = analyses.get(analysis_id)
    if spec is None:
        raise ReproduceError(f"The analysis of run {run_id} ('{analysis_id}') is not available in this program.")
    if version != spec.version:
        raise ReproduceError(f"Run {run_id} used {spec.name} version {version}; this program has "
                             f"version {spec.version}. A changed method cannot reproduce the earlier result.")
    if "raw_parameters" not in meta:
        raise ReproduceError(f"Run {run_id} was made before runs recorded the parameters exactly as entered "
                             "(09-Nov-26), so it cannot be repeated exactly. Runs made from now on can.")
    _validated(run_id, meta, spec)
    for d in meta["input_datasets"]:
        info = db.one("SELECT dataset_id, relative_path FROM datasets WHERE dataset_id = ?", (d["dataset_id"],))
        if info is None:
            raise ReproduceError(f"Dataset {d['dataset_id']} used by run {run_id} is no longer in the registry.")
        try:
            path = settings.data_path(info["relative_path"])  # refuses paths that could lead outside Q-MAP_DATA
        except UnsafeDataPath as exc:
            raise ReproduceError(f"Dataset {d['dataset_id']}: {exc}.") from None
        if not path.is_file():
            raise ReproduceError(f"Dataset {d['dataset_id']} ({d.get('instrument')}): its stored file is missing.")
        try:
            current = sha256_file(path)
        except OSError as exc:
            raise ReproduceError(f"Dataset {d['dataset_id']} ({d.get('instrument')}): its stored file cannot be read "
                                 f"({exc.strerror or exc}).") from None
        if current != d["sha256"]:
            raise ReproduceError(f"Dataset {d['dataset_id']} ({d.get('instrument')}) is no longer the data run {run_id} "
                                 "used (its checksum differs from the one recorded), so the result cannot be "
                                 "reproduced with it.")
    recorded = {r["relative_path"].rsplit("/", 1)[-1]: r["sha256"] for r in
                db.query("SELECT relative_path, sha256 FROM run_outputs WHERE run_id = ?", (run_id,))}
    tables = {}
    for prefix in spec.result_tables:
        name = next((n for n in meta["outputs"] if n.startswith(prefix)), None)
        if name is None or name not in recorded:
            raise ReproduceError(f"Run {run_id} has no recorded result table '{prefix}...'.")
        if not isinstance(recorded[name], str) or not _SHA256.fullmatch(recorded[name]):
            raise ReproduceError(f"The registry record of run {run_id}'s result table {name} has no valid checksum.")
        # the earlier table itself must still be there, unchanged since the run closed: it is the reference
        try:
            on_disk = sha256_file(folder / name)
        except OSError as exc:
            raise ReproduceError(f"The result table {name} of run {run_id} cannot be read "
                                 f"({exc.strerror or exc}); it was moved, deleted or is not accessible.") from None
        if on_disk != recorded[name]:
            raise ReproduceError(f"The result table {name} of run {run_id} was changed after the run (its checksum no "
                                 "longer matches the registry), so it cannot serve as the reference.")
        tables[prefix] = (name, recorded[name])
    return EarlierRun(run_id, folder, meta, tables)


def reproduce_run(settings: Settings, db: Database, run_id: str, *, log=None, progress=None, cancel=None):
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
    return run_analysis(settings, db, spec, ids, raw, log=log, reproduce_of={"earlier": earlier}, progress=progress,
                        cancel=cancel)


def compare_and_report(ctx, spec, reproduce_of: dict, outputs: list[Path]) -> tuple[Path, dict]:
    """Called by run_analysis after the new run has calculated: compare, write the report, return (path, summary)."""
    earlier: EarlierRun = reproduce_of["earlier"]
    meta = earlier.metadata
    rows = []
    build_now, build_then = current_build(), meta.get("build") or {}
    same_build = build_now.get("source_fingerprint") == build_then.get("source_fingerprint")
    rows.append(("Code build", build_then.get("source_fingerprint", "(not recorded)"),
                 build_now.get("source_fingerprint"), "same" if same_build else "DIFFERENT"))
    libs_then, libs_now = build_then.get("libraries"), build_now.get("libraries")
    same_libs = libs_then == libs_now if libs_then is not None else None

    def _libs(d):
        return "(not recorded - run made before 10-Nov-26)" if d is None else ", ".join(
            f"{k} {v}" for k, v in sorted(d.items()))
    rows.append(("Python and library versions", _libs(libs_then), _libs(libs_now),
                 "not recorded" if same_libs is None else "same" if same_libs else "DIFFERENT"))
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
               ("" if same_build else " (the code build is different, see the first row)") +
               (" (Python or library versions differ, see the second row)" if same_libs is False else ""))
    path = ctx.output(f"Reproducibility_Report_{ctx.stamp}.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("Item", f"Earlier run {earlier.run_id}", f"This run {ctx.run_id}", "Result"))
        w.writerows(rows)
        w.writerow(("Verdict", "", "", verdict))
    ctx.log(verdict)
    return path, {"of_run_id": earlier.run_id, "identical": identical, "same_build": same_build,
                  "same_libraries": same_libs, "verdict": verdict}
