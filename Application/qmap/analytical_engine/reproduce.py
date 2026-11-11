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


def _safe_relative_path(name) -> bool:
    return (isinstance(name, str) and bool(name) and not name.startswith("/")
            and "\\\\" not in name and ":" not in name
            and all(part not in ("", ".", "..") for part in name.split("/")))


def _verify_registered_provenance(db: Database, run_id: str, folder: Path, run_row) -> tuple[dict, dict]:
    """Verify the metadata and manifest against the checksums already recorded when the run was closed.

    No registry migration is needed: finish_run records a SHA-256 for every run output, including Run_Metadata and
    run_manifest.json. Older records without those anchors are refused as unverifiable rather than rewritten.
    """
    output_path = str(run_row["output_path"]).strip("/")
    prefix = output_path + "/"
    rows = db.query(
        "SELECT relative_path, kind, sha256, size_bytes FROM run_outputs WHERE run_id = ? ORDER BY relative_path",
        (run_id,),
    )
    registered = {}
    for item in rows:
        stored_path = item["relative_path"]
        if not isinstance(stored_path, str) or not stored_path.startswith(prefix):
            raise ReproduceError(f"The output registry of run {run_id} contains a path outside its recorded run folder.")
        relative = stored_path[len(prefix):]
        if not _safe_relative_path(relative) or relative in registered:
            raise ReproduceError(f"The output registry of run {run_id} contains an invalid or duplicate file path.")
        registered[relative] = item

    metadata_files = sorted(folder.glob("Run_Metadata_*.json"))
    if not metadata_files:
        raise ReproduceError(f"Run {run_id} has no Run_Metadata file in {folder}; it is not an analysis run, or its "
                             "folder was moved.")
    if len(metadata_files) > 1:
        raise ReproduceError(f"Run {run_id} has {len(metadata_files)} Run_Metadata files in {folder}; a run has exactly one, so "
                             "Q-MAP cannot tell which is the record.")
    metadata_path = metadata_files[0]
    metadata_record = registered.get(metadata_path.name)
    if (metadata_record is None or metadata_record["kind"] != "json"
            or not isinstance(metadata_record["sha256"], str)
            or not _SHA256.fullmatch(metadata_record["sha256"])):
        raise ReproduceError(f"The registry has no valid SHA-256 checksum for the Run_Metadata file of run {run_id}.")
    try:
        metadata_hash = sha256_file(metadata_path)
    except OSError as exc:
        raise ReproduceError(f"The Run_Metadata file of run {run_id} cannot be read ({exc.strerror or exc}).") from None
    if metadata_hash != metadata_record["sha256"]:
        raise ReproduceError(f"The Run_Metadata file of run {run_id} does not match the SHA-256 checksum recorded "
                             "in the registry; it may have been changed after the run.")

    manifest_path = folder / "run_manifest.json"
    manifest_record = registered.get("run_manifest.json")
    if (manifest_record is None or not isinstance(manifest_record["sha256"], str)
            or not _SHA256.fullmatch(manifest_record["sha256"])):
        raise ReproduceError(f"The registry has no valid SHA-256 checksum for run {run_id}'s run_manifest.json.")
    try:
        manifest_hash = sha256_file(manifest_path)
    except OSError as exc:
        raise ReproduceError(f"The run manifest of run {run_id} cannot be read ({exc.strerror or exc}).") from None
    if manifest_hash != manifest_record["sha256"]:
        raise ReproduceError(f"The run manifest of run {run_id} does not match its SHA-256 checksum recorded in the "
                             "registry; the historical record cannot be trusted.")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ReproduceError(f"The run manifest of run {run_id} is damaged or cannot be read ({exc}).") from None
    if not isinstance(manifest, dict) or manifest.get("run_id") != run_id or manifest.get("status") != "completed":
        raise ReproduceError(f"The run manifest of run {run_id} is incomplete or inconsistent with the registry.")

    manifest_outputs = manifest.get("outputs")
    if not isinstance(manifest_outputs, list):
        raise ReproduceError(f"The run manifest of run {run_id} has no valid output records.")
    expected = {}
    for entry in manifest_outputs:
        if not isinstance(entry, dict):
            raise ReproduceError(f"The run manifest of run {run_id} contains an invalid output record.")
        relative = entry.get("relative_path")
        if (not _safe_relative_path(relative) or relative == "run_manifest.json"
                or relative in expected or not isinstance(entry.get("sha256"), str)
                or not _SHA256.fullmatch(entry["sha256"])
                or not isinstance(entry.get("size_bytes"), int) or isinstance(entry.get("size_bytes"), bool)
                or entry["size_bytes"] < 0 or not isinstance(entry.get("kind"), str)):
            raise ReproduceError(f"The run manifest of run {run_id} contains an incomplete or duplicate output record.")
        expected[relative] = entry

    registered_outputs = {name: item for name, item in registered.items() if name != "run_manifest.json"}
    if set(expected) != set(registered_outputs):
        raise ReproduceError(f"The output records in the registry of run {run_id} do not agree with its run manifest.")
    for relative, entry in expected.items():
        item = registered_outputs[relative]
        if (item["sha256"] != entry["sha256"] or item["kind"] != entry["kind"]
                or item["size_bytes"] != entry["size_bytes"]):
            raise ReproduceError(f"The output registry record for {relative} in run {run_id} does not agree with its "
                                 "run manifest.")
    return manifest, registered



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


def _reconcile_metadata_with_registry(run_id: str, meta: dict, spec, run_row, manifest: dict,
                                      db: Database, registered_outputs: dict) -> None:
    """Cross-check every reproduction input against the run row, run_inputs, datasets and frozen manifest."""
    try:
        run_parameters = json.loads(run_row["params_json"])
    except (TypeError, ValueError) as exc:
        raise ReproduceError(f"The registry parameters for run {run_id} are not valid JSON ({exc}).") from None
    if not isinstance(run_parameters, dict):
        raise ReproduceError(f"The registry parameters for run {run_id} are not a valid run record.")
    if manifest.get("parameters") != run_parameters:
        raise ReproduceError(f"The registry parameters for run {run_id} do not match its run manifest.")
    if (run_parameters.get("analysis_id") != meta.get("analysis_id")
            or run_parameters.get("analysis_version") != meta.get("analysis_version")):
        raise ReproduceError(f"The Run_Metadata analysis identity for run {run_id} does not match the registry.")
    if meta.get("parameters") != run_parameters.get("parameters"):
        raise ReproduceError(f"The Run_Metadata parameters for run {run_id} do not match the registry.")

    # Re-parse the exact text entered by the user. This prevents a changed raw_parameters field from silently
    # reproducing a different effective set of parameters, even when the normalized parameters field is untouched.
    from datetime import date
    from .base import _parse_param
    raw = meta.get("raw_parameters")
    if not isinstance(raw, dict):
        raise ReproduceError(f"The Run_Metadata raw parameters for run {run_id} are inconsistent.")
    effective = {}
    for parameter in spec.parameters:
        value, problem = _parse_param(parameter, raw.get(parameter.key))
        if problem:
            raise ReproduceError(f"The Run_Metadata raw parameter '{parameter.key}' for run {run_id} is invalid: "
                                 f"{problem}")
        effective[parameter.key] = value
    if spec.check_params is not None:
        effective, problems = spec.check_params(dict(effective))
        if problems:
            raise ReproduceError(f"The Run_Metadata parameters for run {run_id} do not reproduce their recorded "
                                 f"values: {' '.join(problems)}")
    effective = {key: (value.isoformat() if isinstance(value, date) else value)
                 for key, value in effective.items()}
    if effective != meta.get("parameters"):
        raise ReproduceError(f"The Run_Metadata raw parameters for run {run_id} do not match its recorded parameters.")

    datasets = meta.get("input_datasets")
    ids = [item["dataset_id"] for item in datasets]
    if len(ids) != len(set(ids)):
        raise ReproduceError(f"The Run_Metadata of run {run_id} contains duplicate dataset references.")
    if run_parameters.get("dataset_ids") != ids:
        raise ReproduceError(f"The Run_Metadata dataset references for run {run_id} do not match the registry.")
    registered_inputs = [item["dataset_id"] for item in db.query(
        "SELECT dataset_id FROM run_inputs WHERE run_id = ? ORDER BY dataset_id", (run_id,))]
    if sorted(ids) != registered_inputs:
        raise ReproduceError(f"The Run_Metadata dataset references for run {run_id} do not match run_inputs in the registry.")

    manifest_inputs = manifest.get("input_datasets")
    if not isinstance(manifest_inputs, list):
        raise ReproduceError(f"The run manifest of run {run_id} has no valid input dataset records.")
    manifest_by_id = {}
    for item in manifest_inputs:
        if not isinstance(item, dict) or not isinstance(item.get("dataset_id"), int):
            raise ReproduceError(f"The run manifest of run {run_id} contains an invalid input dataset record.")
        if item["dataset_id"] in manifest_by_id:
            raise ReproduceError(f"The run manifest of run {run_id} contains duplicate input dataset records.")
        manifest_by_id[item["dataset_id"]] = item.get("sha256")
    if set(manifest_by_id) != set(ids):
        raise ReproduceError(f"The run manifest dataset references for run {run_id} do not match Run_Metadata.")

    for item in datasets:
        dataset_id = item["dataset_id"]
        current = db.one("SELECT dataset_id, sha256 FROM datasets WHERE dataset_id = ?", (dataset_id,))
        if current is None or current["sha256"] != item["sha256"]:
            raise ReproduceError(f"Dataset {dataset_id} used by run {run_id} does not match its registry record.")
        if manifest_by_id.get(dataset_id) != item["sha256"]:
            raise ReproduceError(f"Dataset {dataset_id} in the run manifest of run {run_id} does not match Run_Metadata.")

    output_names = meta.get("outputs")
    if not isinstance(output_names, list) or len(output_names) != len(set(output_names)):
        raise ReproduceError(f"The Run_Metadata output records for run {run_id} are invalid or duplicated.")
    available_names = {name.rsplit("/", 1)[-1] for name in registered_outputs}
    if any(name not in available_names for name in output_names):
        raise ReproduceError(f"The Run_Metadata output records for run {run_id} do not match the registry.")



def load_earlier_run(settings: Settings, db: Database, run_id: str, analyses: dict) -> EarlierRun:
    """Everything a reproduction needs from the earlier run, checked before anything runs. Any expected problem with
    the record, the folders or the files is a ReproduceError (a plain refusal); nothing is written or changed here."""
    run_id = (run_id or "").strip()
    if not run_id:
        raise ReproduceError("No Run ID was given.")
    row = db.one("SELECT run_id, status, output_path, params_json, module_code FROM runs WHERE run_id = ?", (run_id,))
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
    manifest, registered_outputs = _verify_registered_provenance(db, run_id, folder, row)
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
    _reconcile_metadata_with_registry(run_id, meta, spec, row, manifest, db, registered_outputs)
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
