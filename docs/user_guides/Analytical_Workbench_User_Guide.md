# Q-MAP Analytical Workbench: user guide

Open `Q-MAP_APP/analytical_workbench.py` in Thonny or IDLE and press **F5**.

The Workbench runs analyses on data **already prepared in Database Manager**. It never imports or interprets source
files. When data are missing, it tells you what to prepare in Database Manager.

## Home

- **Your folders**: the same remembered folders as Database Manager.
- **Available now**: analyses that genuinely work (currently **Dataset Summary**).
- **Planned application windows** and **Planned research modules**: everything else is marked **COMING SOON**, with
  the reason. That includes Market Intelligence (MIQP) and MA Research (QLOPB): their code is not in the repository
  yet. Stage Analysis (Weinstein) is listed as planned; it needs approved rules first.

## Run an analysis

**1. Input.** Choose the analysis; its description and result type are shown. Select one or more prepared datasets.
Deleted datasets are never offered; superseded ones only if you tick "Show superseded".

**2. Output.** Each run gets its own folder, named by its **Run ID** (for example `DSUM_20261101_154719`), in
`Q-MAP_OUTPUT/Research_Reports`. An earlier run is never overwritten.

**3. Options.** The analysis's parameters. For Dataset Summary: optional start and end dates such as `01-Jan-24`.

- **Check readiness** saves nothing. For every selected dataset it shows each requirement as OK, NOTE (a warning) or
  FAIL:

  | Requirement | What is checked |
  |---|---|
  | Registered | It is a standardised or derived dataset in the registry, not an original file |
  | Current | Active, not superseded |
  | File | Present, readable, and its checksum matches the registry |
  | Data structure | A schema version this Q-MAP understands, with the required columns |
  | Timeframe | Supported by this analysis |
  | Volume | Present, if the analysis needs it |
  | Validation | Status and warnings |
  | Storage | A Temporary dataset is noted, because you may delete it later |
  | History | Enough bars in the chosen period, and whether the data cover the whole period |

- **RUN ANALYSIS** checks again and runs only if everything required is met. Otherwise it explains what is missing and
  creates no run.

The existence of a dataset does not make it ready. For example, an analysis that needs intraday data will not run on
daily data, and a period with no data is refused.

**Progress / Status** and **Live Log** show what is happening. The final line names the Run ID and the saved files.

## What each run saves

| File | Content |
|---|---|
| `Dataset_Summary_<dd_mmm_yy_hhmmss>.csv` | The results; dates in dd-mmm-yy |
| `Run_Metadata_<dd_mmm_yy_hhmmss>.json` | Run ID, analysis and version, code versions, parameters, readiness warnings, and every input dataset with its checksum, processing version, settings fingerprint, storage class, validation warnings and lineage back to the original file |
| `run_manifest.json`, `run_log.txt` | The standard Q-MAP run record: outputs with checksums, inputs, status |

The run and its input datasets are also recorded in the Data Registry (`runs`, `run_inputs`). This lets Database
Manager warn you before you delete a dataset that a run used.

## Dataset Summary (version 1)

A **utility**: it describes data and checks the research path end to end. It makes no market judgement and defines no
signal.

For each dataset, within the chosen period:

- bars, first and last bar, calendar days covered, longest gap between bars;
- first and last close, and the change between them (%);
- bar-to-bar close returns: count, mean, standard deviation (sample, n-1), smallest and largest, in %;
- bars with quality flags, bars with volume, average volume.

Each return uses only consecutive bars of the same dataset.
