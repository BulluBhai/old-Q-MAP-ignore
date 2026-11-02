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

- **Last run folder** shows the folder of the latest **completed** run, exactly as recorded for that run. After a
  restart it is read from the Data Registry. A refused request or a failed run never replaces it.
- The path is shown in a read-only box, so you can select it and copy it (Ctrl+C).
- **Open Output Folder** opens that folder in File Explorer. It only opens it; nothing is moved, renamed or deleted.
  - The same button also appears under the completion message in **Progress / Status**, so you can open the
    results straight after a run.
  - Before any run has completed, the button is greyed out.
  - If the folder has since been moved or deleted, or Windows refuses to open it, a message explains what happened
    instead.

**3. Options.** The analysis's parameters. For Dataset Summary: an optional **Start date** and **End date**.

### Entering dates

Each date box accepts typing **and** has a **Calendar...** button.

- **Calendar:** click a day to fill in the box.
  - `<` and `>` change month; `<<` and `>>` change year (same month), so 1998 is a few clicks away; **Today** picks
    today; **Clear** empties the box.
  - Esc or **Close** closes the calendar without changing anything.
  - The calendar writes dates as `25-Feb-26`.
- **Typing:** day, then month, then year. All of these mean 25 February 2026:

  | You type | Format |
  |---|---|
  | `25/02/26` | day/month/year |
  | `25-02-26` | day-month-year |
  | `25-Feb-26` | day-month abbreviation-year (any letter case) |
  | `250226` | six digits = DDMMYY |

  Four-digit years (`25/02/2026`, `25-Feb-2026`) and ISO dates (`2026-02-25`) also work.
  A four-digit year must be from 0001 to 9999. There is no year 0000, so `01/01/0000` is refused as INVALID DATE
  INPUT. A date before 1969 or after 2068 is always shown with its four-digit year (for example `15-Jun-1950`).

  Six digits are always read as DDMMYY. A longer number, such as a Unix timestamp, is refused, never converted.
- **Two-digit years:** 00-68 mean 2000-2068, and 69-99 mean 1969-1999. So `26` is 2026 and `95` is 1995. This is the
  same rule Q-MAP's DD-MM-YY source profiles use.
- **Confirmation:** next to each box, Q-MAP shows what it understood (for example `= 25-Feb-2026`), or a red
  explanation.
- **Empty box:** an empty Start date means "from the first bar"; an empty End date means "to the last bar".

**Three different situations** are reported differently, before anything runs:

| You see | Meaning | What to do |
|---|---|---|
| **INVALID DATE INPUT** | A date can't be understood (for example `25.02.26`), doesn't exist (`31/02/26`), or the start is after the end. Nothing was checked or run. | Correct the date; the supported formats are listed |
| **NO DATA IN THIS PERIOD** | The dates are fine, but **none** of the selected datasets has a bar between them. The data's actual coverage is shown. | Choose a period inside the coverage, leave the dates empty, or load more data in Database Manager |
| **NOT READY** | Anything else that stops the run: wrong timeframe, too few bars (for example 1 bar where 2 are needed), a damaged file ... It is also shown when **some** selected datasets have bars in the period and others have none. Those datasets are named. | Follow the explanation. If some datasets have no bars, choose a period they all cover, or remove those datasets |
| **READY** | Valid dates, and enough bars in the period | Run |

A request that is refused in any of these ways creates **no** run, no run folder and no output files.

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
  | History | Enough bars in the chosen period (with "no bars at all" reported separately), and whether the data cover the whole period |

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
