# Q-MAP Analytical Workbench: user guide

Open `Q-MAP_APP/analytical_workbench.py` in Thonny or IDLE and press **F5**.

The Workbench runs analyses on data **already prepared in Database Manager**. It never imports or interprets source
files. When data are missing, it tells you what to prepare in Database Manager.

## Home

- **Your folders**: the same remembered folders as Database Manager. If neither application has been opened before,
  the Workbench prepares the standard folders next to the program folder in the same way (see the Database Manager
  guide, **Home**).
- **Available now**: analyses that genuinely work: **MA Research: MA Affinity (QLOPB)** and **Dataset Summary**.
  The MA Research card covers both MA Affinity analyses in the **Analysis:** list: **MA Affinity (QLOPB)** (V1) and
  **MA Affinity V2 (chance-tested)** (added 10-Nov-26, see below).
- **Planned application windows** and **Planned research modules**: everything else is marked **COMING SOON**, with
  the reason. That includes Market Intelligence (MIQP), which is outside Q-MAP v0.1. Stage Analysis (Weinstein) is
  listed as planned; it needs approved rules first.

## Run an analysis

**1. Input.** Choose the analysis; its description and result type are shown. Select one or more prepared datasets.
Deleted datasets and datasets you **rejected** (Database Manager, reversible) are never offered; superseded ones only
if you tick "Show superseded".

What the readiness box tells you about data prepared automatically (03-Nov-26):
- **Conflicting observations** (NOTE): some time stamps have more than one different value. Dataset Summary still
  runs; calculations that go bar by bar (such as returns) treat each stored row as a bar, and it counts them in its
  "Conflicting timestamps" column. **MA Affinity refuses** such a dataset (it needs one bar per time; see below).
- **MIXED intervals**: the dataset does not have one bar interval. Dataset Summary runs with a NOTE (its per-bar figures
  mix intervals); an analysis that needs one interval refuses it with the reason.
- Any timeframe can appear (for example 75 minutes or 2 hours); it is the interval measured in the data.

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

**3. Options.** The analysis's parameters. For Dataset Summary: an optional **Start date** and **End date**. For MA
Affinity, see the next section.

## MA Affinity (QLOPB)

QLOPB's **MA Affinity Scanner V2**, brought into Q-MAP with its calculations unchanged (Project Owner approval
03-Nov-26). It describes how price behaved around moving averages in the past. It is **not** a trading signal.

**Research question.** For this instrument, which moving averages (type and period) has price historically
interacted with most reliably? Here "interacted" means price came within the proximity zone, then moved in the
expected direction over the following bars. Do the leaders chosen on the earlier (in-sample) part of the history keep
that behaviour on the later (out-of-sample) part? The ranking uses the in-sample part only; the out-of-sample part
never changes a rank.

- **Data:** one registered **daily, weekly or monthly** dataset per run. Weekly and monthly datasets are the ones made
  in Database Manager (Datasets and Storage, Derive). The Workbench never builds weekly or monthly bars itself, and
  never uses another timeframe instead. Intraday and quarterly datasets are not offered in v0.1.
- **Options** (shown with QLOPB's defaults; change only what you need): MA types (SMA, EMA, WMA, HMA, RMA), MA start and
  end, proximity %, cooldown bars, forward windows (the first is the primary window), minimum interactions, IS split %,
  regime MA, Top-N, the four affinity weights (divided by their sum), OOS scope, minimum OOS outcomes, and an optional
  start and end date. Wrong values are listed under **INVALID PARAMETERS** and nothing runs. Weights must be finite
  numbers, not negative, and not all 0 (safeguard S-2).
- **The dataset is refused (NOT READY), with the reason and the dates, when:**
  - it holds **conflicting observations** in the chosen period (the same time with different values, which Q-MAP has
    not resolved), or weekly/monthly bars built from such days. Load a corrected source file, or choose a period that
    leaves those dates out;
  - its timeframe is **MIXED**;
  - it is too short for the chosen MA range and forward windows (QLOPB's own rule), or prices are not usable.
- **It still runs, with a NOTE, when:** another dataset overlaps it with different values (that is about the other
  dataset), the interval finding was uncertain, or there are gaps or incomplete first/last periods. Exact duplicate rows
  were already removed when the data were loaded and never stop the analysis.
- **Results** (in the run folder): `QLOPB_MA_Affinity_<date>.xlsx` (all tables and the limitations),
  `QLOPB_MA_Affinity_Report_<date>.pdf`, PNG charts, `MA_Affinity_Candidates_<date>.csv` and
  `MA_Affinity_Interactions_<date>.csv` (for independent checking), `MA_Affinity_Findings_<date>.txt` (the research
  question and the frozen Top-N in plain sentences, with how to read them), the run log and `Run_Metadata_<date>.json`.
  The metadata holds the input dataset and its checksum, every setting exactly as you typed it, the bars used, the
  in-sample/out-of-sample dates, the code build and the QLOPB source commit.
- **Reproduce a run** (section **2. Output - where results are saved**): after a run, its Run ID is filled in next to
  **Reproduce Run ID:**. You can also type any earlier Run ID there. Click **Reproduce run (runs it again and
  compares)**.
  - What happens: Q-MAP runs the same analysis again as a NEW run, with the same data and settings. The earlier run is
    never changed. It then compares the result tables.
  - When it works: the result line says `REPRODUCED: every result table is identical to run ...`, and the new run
    folder holds `Reproducibility_Report_<date>.csv`.
  - When it is refused (no new run is made): the data have changed since the earlier run (checksum differs), the
    analysis version has changed, or the run is older than 09-Nov-26.
  - A different program build is stated in the report.
- **Accuracy evidence:** the calculations are checked automatically against a separate, independently written
  calculation of the same method, on every candidate and every interaction. Further tests prove that later bars
  can never change in-sample results (no look-ahead).
- **Read with care:** rankings describe the past; many candidates are tested, so some look good by chance (p-values
  are not corrected); Directed IR and the weight scheme are **pending owner review**; small out-of-sample samples are
  weak evidence. These limitations are printed in every report.

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

**Progress, ETA and Cancel** (added 10-Nov-26). While an MA Affinity analysis or a reproduction runs:

- **Progress:** shows `<done> of <total> steps (<percent>%)` and the bar fills from left to right. One step is one
  moving-average candidate scored once (in-sample, then out-of-sample). The last step is writing the reports and the
  run record, so the bar is full only when everything is saved.
- **ETA:** the estimated time left. It appears after the first few seconds (before that it shows `-`, rather than an
  unreliable guess). It is an estimate from the speed so far.
- **Stage:** what is being done now, for example `In-sample EMA-37`.
- Dataset Summary does not report steps: while it runs, its bar moves back and forth.
- **When a run ends**, **Stage:**, the bar and the coloured result line always agree:

  | Outcome | Stage: | Bar | Result line |
  |---|---|---|---|
  | Completed | `Finished` | full | green, starts with `Completed. Run ...` (or `REPRODUCED ...` for a reproduction) |
  | Cancelled by you | `Cancelled` | stays where it stopped; **Progress:** says `Cancelled at ... (not complete)` | amber, starts with `Cancelled.` |
  | Failed | `Failed` | stays where it stopped | red, starts with `The analysis failed` |
  | Refused (not ready) | `Not started` | empty | amber, says why nothing was run |

- **Cancel** (in **3. Options - parameters**, next to **RUN ANALYSIS**) stops a run safely:
  1. Click **Cancel** once. The button greys out and **Stage:** shows `Cancelling - the run stops after its current
     step...`.
  2. Wait a moment (normally a second or two). **Stage:** then shows `Cancelled` and the result line starts with
     `Cancelled. Run <Run ID> stopped before it finished and is recorded as cancelled`.
  3. Nothing is lost: your data and earlier runs are not touched. The cancelled run's folder holds only its log, no
     results, and it is never offered as a result or for **Reproduce**. Run again whenever you like.
  4. If the run was already writing its reports when you clicked, it finishes normally and says `Completed`.
- **Closing the window during a run** also asks the run to stop, so Thonny or IDLE does not keep working in the
  background. The run is then recorded as cancelled.

## MA Affinity V2 (chance-tested)

Added 10-Nov-26 as a **beta release candidate**. It runs the same calculations as **MA Affinity (QLOPB)** and adds a
test of whether the best result is better than luck, plus the other additions below. Its defaults are **provisional**:
they are documented choices, not final owner-approved methodology (see
`docs/release/Q-MAP_MA_Affinity_V2_Method_Review_and_Decisions_10_Nov_26_112718.md`).

**V1 or V2: which to choose**

| Choose | When |
|---|---|
| **MA Affinity V2 (chance-tested)** | New research: it tells you whether the ranking stands out from chance |
| **MA Affinity (QLOPB)** (V1) | To repeat or compare with runs made before 10-Nov-26. V1 is unchanged and stays available |
| Not **Dataset Summary** | It only describes the data; it does not rank moving averages |

V1 runs have Run IDs starting `MAAF_`; V2 runs start `MAA2_`. The two never share a Run ID, a folder or a result table.

**What V2 adds**

| Addition | What it means for you |
|---|---|
| **Executive interpretation** | The first part of the findings file, of the Excel **Summary** sheet and of the PDF: eight short plain-English answers (question, data, findings, what the numbers mean, chance, baseline, limitations, what next). Every number in it comes from the run's calculated results. The detailed tables follow it, unchanged |
| **Chance test** | The in-sample prices are cut into blocks of 15 bars, the blocks are put in a random order, and the whole scan is run again on that shuffled history, 200 times. Shuffling keeps each bar's shape and the stock's overall move but destroys any real link with a moving average. The real #1 score is compared with the 200 best scores that luck alone produced |
| **Verdict** | `STANDS OUT FROM CHANCE` when the chance p-value is 0.05 or less, otherwise `NOT DISTINGUISHABLE FROM CHANCE` (treat the ranking as unproven). Standing out is evidence for this instrument and period under the shuffle model's assumptions, **not** proof of a profitable or lasting edge. With 200 shuffles the smallest possible p-value is 0.0050 |
| **Chance p (adjusted)** | Each Top-N finding gets its own chance p-value. It allows for the many periods tested, so use it instead of the older "p-value (uncorrected)" |
| **Baseline %** and **Edge** | What price did anyway over the same bars (for example, it rose after 54% of all days). Edge = success rate minus baseline, in percentage points. Reported only: the score itself still compares with 50%, as in V1 |
| **Fairer strength** | Long MAs produce fewer interactions; V2 compares a candidate's count with nearby periods, so a long MA is not marked down just for being long |
| **Distinct findings** | Neighbouring periods (for example EMA-34 to EMA-41) are nearly the same line; V2 groups them so each Top-N place is a different finding. The group's members and the full ranking are kept |
| **MA warm-up** | With a **Start date**, the moving averages are also calculated from the dataset's earlier bars, so a long MA does not restart at the Start date. Interactions, outcomes and the in-sample/out-of-sample split still use only the chosen period |

**How to run it**

1. Open the Analytical Workbench (`analytical_workbench.py`, **F5**).
2. In **1. Input - analysis and prepared datasets**, choose **MA Affinity V2 (chance-tested)** in **Analysis:**.
3. Select one **daily, weekly or monthly** dataset in the list.
4. In **3. Options - parameters**, change only what you need. The V1 options keep their V1 meaning and defaults. The
   V2 options are at the end of the list:

   | On screen | Default | Meaning |
   |---|---|---|
   | **Chance shuffles** | `200` | How many shuffled histories are tested. `0` = no chance test (the report then says so). For a finer p-value, use for example `1000` (about five times longer) |
   | **Chance block bars** | `15` | Bars per block when shuffling |
   | **Chance seed** | `1` | Fixes the random order, so the same settings always give the same result |
   | **Strength rule** | `relative` | `relative` (V2) or `v1` (the old rule, for comparison) |
   | **Group %** | `10` | Periods of one MA type within this % of a leader form one finding. `0` = no grouping |
   | **Zone mode** | `percent` | `percent` uses **Proximity %** (as V1). `atr` uses **ATR multiple** x the average true range |
   | **ATR period** | `14` | Only used when **Zone mode** is `atr` |
   | **ATR multiple** | `1` | Only used when **Zone mode** is `atr` |
   | **MA warm-up** | `earlier` | `earlier` = use the bars before the **Start date** to calculate the MAs; `none` = start the MAs at the Start date (as V1). It matters only when a Start date is entered |

   With **Strength rule** `v1`, **Group %** `0` and **MA warm-up** `none` (or no Start date), V2 gives every V1
   number exactly, plus the chance test and the baselines.
5. Click **Check readiness (nothing is saved)**. Expect `READY - every requirement is met.` and, for the chance test,
   an `OK` line such as `Chance test: 200 shuffles of 69 blocks of 15 bars (seed 1); ...`.
   - If it says `INVALID PARAMETERS`, correct the option named in red.
   - If a `FAIL` line ends with `too few to shuffle meaningfully (at least 5 are needed)`, use a smaller **Chance
     block bars** or more data.
   - With a **Start date**, a line `MA warm-up: ... bar(s) before the Start date ... are used to calculate the moving
     averages` confirms the warm-up. A `NOTE` line `MA warm-up: only ... bar(s) exist before the Start date` means long
     MAs still start inside the period; the run is allowed.
6. Click **RUN ANALYSIS**. Watch **Progress:** and **ETA:**. The chance test is most of the work: about 1 to 2
   minutes for SMA and EMA on 1,500 daily bars (measured on a Linux test computer; your PC may differ), longer with all
   five MA types. **Cancel** stops it safely (see "Progress, ETA and Cancel" above).
7. When it finishes, **Stage:** shows `Finished`, the bar is full and the result line starts with
   `Completed. Run MAA2_...`.

**Where the results are.** In the run folder (`Q-MAP_OUTPUT\Research_Reports\MAA2_<date>_<time>\`):

| File | What to look at |
|---|---|
| `MA_Affinity_V2_Findings_<date>.txt` | Start here: **EXECUTIVE INTERPRETATION**, then **DETAILED FINDINGS** with the **VERDICT** line and each Top-N finding |
| `MA_Affinity_V2_Report_<date>.pdf` | Page 1: the executive interpretation. Then the chance test, data and warnings, and the Top-N table |
| `MA_Affinity_V2_<date>.xlsx` | **Summary** (executive interpretation, then the verdict), **Top_N** (with group members), **Rankings** (every candidate), **Chance_Test** (all luck-only scores), **Interactions**, **Settings** |
| `chance_test_distribution_<date>.png` | The luck-only #1 scores as bars, and the real #1 score as a red line |
| `MA_Affinity_V2_Candidates_`, `_Interactions_`, `_Chance_Shuffles_<date>.csv` | Full tables; these three are compared when a run is reproduced |
| `Run_Metadata_<date>.json` | Everything needed to repeat the run: analysis and version, every option including the seed, the chance-test summary, the warm-up, the program build and the Python and library versions |

**How to read the verdict**

- `NOT DISTINGUISHABLE FROM CHANCE`: shuffled prices often scored as high. The Top-N may be luck; do not rely on it.
  This is the expected result on the synthetic worked-example file `NSE_BETADEMO.csv`: the real #1 (EMA-37) scored
  66.13 while luck averaged 72.59 (chance p-value 0.8657, checked 10-Nov-26).
- `STANDS OUT FROM CHANCE`: the best score is higher than nearly all luck-only scores. This is evidence for this one
  instrument and period only; confirm it on other instruments and later periods before relying on it.
- `CHANCE TEST NOT RUN`: **Chance shuffles** was `0`.

**Reproduce** works as for V1 (section **2. Output - where results are saved**, **Reproduce run (runs it again and
compares)**). The Reproducibility report also has a row **Python and library versions**: `DIFFERENT` there explains
small last-digit differences after a software update.

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
