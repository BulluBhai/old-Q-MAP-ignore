# Q-MAP v0.1: Windows operating and acceptance guide

For the Project Owner (Windows, Python 3.11, IDLE; no programming, no command line, no reading of program code).
Prepared 03-Nov-26 for release candidate `0.1.0rc1` (pull request https://github.com/BulluBhai/Q-MAP/pull/12); revised
after the final release audit. **Status: OUTSTANDING. Q-MAP v0.1 is not ready for controlled analytical use until you
have completed this guide and accepted the result.**

This is the only document you need. It replaces, for v0.1, the PR #9 checklist and the PR #10 W-guide (their checks are
included below; nothing is lost). It is also your normal operating procedure afterwards (Parts 4, 5, 7 and 8).

**Two kinds of check.**
- **REQUIRED**: only you can do these, on your own Windows computer and with your real market files (installation,
  IDLE, File Explorer, your data, what the windows look like).
- **OPTIONAL**: the same behaviour is already proved by automated tests that run on a Windows computer at GitHub for
  every change (A6, A8 and V11 open the real windows; V4, V8 and V10 check the same results and messages without the
  window). Do them only if you want to see the behaviour yourself.
- **W13-W18 stay REQUIRED** (your decision D5-44, confirmed 04-Nov-26). The automated test
  `test_dq7_acceptance_pattern_files` checks the same six files on Windows for every change; that evidence
  **supplements but does not replace** your own check of what the Sources screen shows.

Record each result as **P** (pass), **F** (fail) or **NT** (not tested) in Part 9.

---

## Part 1. What you need (once)

1. Windows 10 or 11 and about 2 GB of free disk space.
2. **Python 3.11 or newer from python.org**, installed with "tcl/tk and IDLE" ticked (the default). To check: open
   IDLE; the first line shows the version, for example `Python 3.11.9`.
3. An internet connection the first time (Q-MAP offers to download the packages it needs).

## Part 2. Get the release candidate

1. Open https://github.com/BulluBhai/Q-MAP/pull/12. Click the branch name `claude/epic-darwin-33o518` near the top,
   then the green **Code** button, then **Download ZIP**.
2. Unzip it to a new folder with a short path, for example `D:\Q-MAP_V01\Q-MAP_APP` (not inside OneDrive).
3. On the PR page, open the **Commits** tab and write the top commit's code (7 characters) in Part 9.

## Part 3. Folders and test files (once)

Create these new, empty folders. **For acceptance, never use your real data folders.**

| Folder | Example | What to put in it |
|---|---|---|
| Q-MAP_DATA | `D:\Q-MAP_V01\Q-MAP_DATA` | nothing (Q-MAP fills it) |
| Q-MAP_OUTPUT | `D:\Q-MAP_V01\Q-MAP_OUTPUT` | nothing (one folder per run appears here) |
| Market_Files | `D:\Q-MAP_V01\Market_Files` | **COPIES** (Ctrl+C, Ctrl+V; never drag) of your eight files `5PAISA_30min.csv`, `AKZOINDIA.parquet`, `CRYPTO_RIVERUSD, 180.csv`, `ICICIBANK.txt`, `NSE_BANKNIFTY, 15.csv`, `OLAELEC.xlsx`, `UJJIVAN.txt`, `VERANDA_1min.csv`; plus `ICICIBANK (1).txt` and `ICICIBANK - Copy.txt` (two more copies of ICICIBANK.txt, renamed) and `RELIANCE_EQ.csv` (a small daily file of another stock) |
| Pattern_Files | `D:\Q-MAP_V01\Pattern_Files` | the six files from `Q-MAP_APP\docs\acceptance_testing\dq7_pattern_files_03_Nov_26\` |
| V01_Files | `D:\Q-MAP_V01\V01_Files` | `NSE_CONFLICTDAILY.csv` from `Q-MAP_APP\docs\acceptance_testing\v01_files_03_Nov_26\` (synthetic) |
| Evidence | `D:\Q-MAP_V01\Evidence` | your screenshots |

**Before you start:** open the folder where your REAL eight files are kept, choose **View → Details** (Size and Date
modified visible), press **Win+Shift+S**, capture the window and save it as `Evidence\W00_originals_before.png`. Do the
same for `Market_Files`.

**Evidence for every check:** Win+Shift+S → capture → save as `Evidence\<check>_<short name>.png`. If a step says
"Open run folder", copy that folder into `Evidence`.

## Part 4. Start Q-MAP

| # | Kind | Do | Success looks like |
|---|---|---|---|
| **V1** | REQUIRED | Open **IDLE** → **File → Open** → `D:\Q-MAP_V01\Q-MAP_APP\database_manager.py` → press **F5** | The **Q-MAP Database Manager** window opens, or a message lists missing packages and offers to install them: click **Yes**, wait a few minutes, press **F5** again, and the window opens. No red text in the IDLE window |
| **V2** | REQUIRED | On the **Home** screen choose `Q-MAP_DATA` and `Q-MAP_OUTPUT` | Both accepted (green). Sources, Data Management and Datasets and Storage are listed as available |
| **V3** | REQUIRED | Open `analytical_workbench.py` the same way (IDLE → File → Open → F5) | The **Q-MAP Analytical Workbench** opens with the same folders. Under **Available now**: "MA Research: MA Affinity (QLOPB)" and "Dataset Summary". Market Intelligence (MIQP) shows COMING SOON |

Both windows may stay open together.

## Part 5. Normal operation

### 5.1 Load your files (Database Manager → Sources)

| # | Kind | Do | Success looks like |
|---|---|---|---|
| **W1** | REQUIRED | Leave **Market time zone** and **Default exchange** empty; keep "Identify the instrument from the file name" ticked. **Add folder...** → `Market_Files` → **SCAN SELECTED FOLDER NOW** | No question window. Imported: 5PAISA (30 minutes), RIVERUSD (CRYPTO, 3 hours), ICICIBANK (Daily; its two copies "Already loaded"), BANKNIFTY (15 minutes), OLAELEC (1 minute), UJJIVAN (5 minutes), VERANDA (1 minute), RELIANCE_EQ. Not loaded: AKZOINDIA (low above open on 08-Nov-25) |
| **W2** | REQUIRED | Click `OLAELEC.xlsx` | "Detected timeframe: 1 minute", "Validation: Consistent across 20 sampled block(s)", "Status: Accepted by default", and a conflicting-observations warning |
| **W3** | REQUIRED | Read the **Exceptions** box | One line per kind: instruments not in the alias registry; conflicting observations (OLAELEC); cryptocurrency venue unknown (RIVERUSD); time zone assumed (AKZOINDIA, OLAELEC, UJJIVAN); not loaded: data errors (AKZOINDIA) |
| **W4** | REQUIRED | **Open run folder** | File Explorer opens the scan folder with `Scan_Report_...csv` and `Identification_Exceptions_...csv`; in Excel the copies of one name are on one row |
| **W5** | REQUIRED | Select `RELIANCE_EQ.csv`, type `RELIANCE` as **Canonical name**, **Add selected names to alias registry**; **Open alias registry folder**, open `Instrument_Aliases.csv` in Excel; scan again | The CSV has a row `RELIANCE, RELIANCE EQ`; after the scan RELIANCE_EQ.csv is listed as NSE:RELIANCE |
| **W6** | REQUIRED | Ctrl+click VERANDA and 5PAISA, type a reason, **Reject selected**; in the Workbench press **Refresh** | Both "Rejected by you"; the Workbench does not offer them |
| **W7** | REQUIRED | Select them, **Restore selected**; Workbench **Refresh** | Both "Imported" again; the Workbench offers them |
| **W8** | REQUIRED | Put 30 or more file copies in a new folder, add and scan it, press **Stop scan** while it runs | The window stays responsive; it stops after the current file and says how many were not processed |
| **A4** | REQUIRED | Scan `Market_Files` again without changing anything | Every file "unchanged"; no new datasets |
| **V4** | OPTIONAL | **Add folder...** → `V01_Files` → **SCAN SELECTED FOLDER NOW** | `NSE_CONFLICTDAILY.csv` imported as NSE:CONFLICTDAILY, Daily, 301 bars, with a conflicting-observations warning (29-Jul-24 has two different rows). Needed for V8 |
| **W13** | REQUIRED | Add `Pattern_Files`, scan | 6 imported, no question; each "Detected timeframe: 5 minutes", "Consistent across 15 sampled block(s)" |
| **W14** | REQUIRED | Click `NSE_RANDOMGAPS.csv` (about 10 % of bars missing at random) | No interval warning of either kind; only "Some days have fewer bars than usual". Not listed under either interval line in the Exceptions box |
| **W15** | REQUIRED | Click `NSE_EVERYOTHER.csv` (one day with every other bar missing) | Warning "Part of the file **may** have another bar interval" with the source rows and the words "cannot show whether"; Exceptions line "A section may have another bar interval or regularly missing bars (full-file check)" lists the file; timeframe still 5 minutes |
| **W16** | REQUIRED | Click `NSE_GENUINE3M.csv` (one day of 3-minute bars), then `NSE_DAILY0000.csv` (35 one-bar dates at 00:00) | Warning "Part of the file **has** another bar interval" with the source rows (3-minute steps; for DAILY0000 "outside the times of the intraday bars, like daily data"); Exceptions line "A section of the file has another bar interval (found by the full-file check)" lists both |
| **W17** | REQUIRED | Click `NSE_DAILY0915.csv` (35 one-bar dates at 09:15) | Listed under the "**may** have another bar interval" line, not the "has" line; the detail says "a time the intraday bars also use" |
| **W18** | REQUIRED | Click `NSE_SPARSE.csv` (35 dates with one bar each at varying times); then **Open run folder**; then in the Workbench run Dataset Summary on NSE:EVERYOTHER | SPARSE: no interval warning; "Some days have fewer bars than usual" lists the one-bar dates. Run folder: the `issues_event...csv` files of the W15-W17 files contain the interval finding with source rows (two `interval_change_uncertain`, two `interval_change_detected`); W14 and W18 have none; `Scan_Report_...csv` lists all six as imported. Workbench: readiness "Validated with warnings: ... interval_change_uncertain ..." and the summary runs |

### 5.2 Your datasets (Database Manager → Datasets and Storage)

| # | Kind | Do | Success looks like |
|---|---|---|---|
| **V5** | REQUIRED | Select the daily **NSE:ICICIBANK** dataset; under "Derive from daily data" tick **Weekly** and **Monthly** → **DERIVE SELECTED TIMEFRAMES** | Two new datasets, NSE:ICICIBANK Weekly and Monthly, linked to the daily one |
| **W10** | REQUIRED | Select a dataset → **Reject (reversible)** → **Restore** | "Rejected by you", then "Active"; nothing moved or deleted |

### 5.3 Analyses (Analytical Workbench → Run an analysis)

| # | Kind | Do | Success looks like |
|---|---|---|---|
| **W9** | REQUIRED | Dataset Summary on OLAELEC → **RUN ANALYSIS** | READY with notes; the result CSV has "Conflicting timestamps" = 183 |
| **A5** | REQUIRED | Dataset Summary on ICICIBANK; Start date: **Calendar...**, `<<` back to January 1998, pick 02; End date: type `02-Nov-26`; run | Completes; Bars 7,166; first close 7.86; last close 1,387.40 |
| **A7** | REQUIRED | **Open Output Folder** under the completion message | File Explorer opens that run's `DSUM_...` folder |
| **V6** | REQUIRED | Choose **MA Affinity (QLOPB)** and look at section 3 | Boxes already filled with QLOPB's defaults (MA types SMA, MA start 10, MA end 250, Forward windows 5,10,20,50 ...); the description says results are exploratory and Directed IR and the weights are pending your review |
| **V7** | REQUIRED | Select **NSE:ICICIBANK Daily** → **Check readiness (nothing is saved)** → **RUN ANALYSIS**; then **Open Output Folder** | READY (notes possible); a Run ID starting `MAAF_`. The folder holds `QLOPB_MA_Affinity_....xlsx`, `QLOPB_MA_Affinity_Report_....pdf`, PNG charts, `MA_Affinity_Candidates_....csv`, `MA_Affinity_Interactions_....csv`, `run_log.txt`, `Run_Metadata_....json`. In the Excel **Summary** sheet: "Instrument / file" names the dataset and the Run ID; "Bar size" says "Daily (Q-MAP registered dataset; not re-aggregated)"; a Top-5 list; the limitations. The **Data_Quality** sheet lists the Run ID, code build, dataset checksum and source file. The PDF's first lines show the dataset, the Run ID, "Q-MAP build: qmap 0.1.0rc1 ...", the source fingerprint and the dataset checksum; Q-MAP's notes appear under Warnings as "Q-MAP data: ..." |
| **V9** | REQUIRED | **NSE:ICICIBANK Weekly**, MA end `60` → RUN ANALYSIS; then **Monthly** with MA start `5`, MA end `24`, Forward windows `3,6,12` | Both finish; "Bar size" says Weekly / Monthly (Q-MAP registered dataset) |
| **V8** | OPTIONAL | **NSE:CONFLICTDAILY** → RUN ANALYSIS | **Not started**; the readiness box says FAIL "1 timestamp(s) in the chosen period hold conflicting observations ... (29-Jul-24) ... MA Affinity needs exactly one bar per time". With End date `26-07-24` and MA end `60` it runs |
| **V10** | OPTIONAL | VERANDA (1-minute) with MA Affinity → Check readiness | FAIL "Timeframe 1 minute is not supported here (needs: Daily, Weekly, Monthly)." |
| **V11** | OPTIONAL | ICICIBANK Daily, type `nan` in **Wt: fwd return** → RUN ANALYSIS | "Not started: the parameters are not valid"; the box explains the weights. Put `25` back |
| **A6** | OPTIONAL | In the calendar, `>>` from 1998 to 2026, then `<` / `>` | Year changes by one per click, month kept |
| **A8** | OPTIONAL | Rename the A7 run folder in Explorer, press Open Output Folder again | A message says the folder no longer exists; no error window |
| **V12** | OPTIONAL | If you still use the separate QLOPB program: run it on your original `ICICIBANK.txt` with default settings and compare its Excel Top-5 and scores with V7 | Same Top-5 and scores. If QLOPB reads or cleans the file differently, note what it says |

### 5.4 The record of a run

| # | Kind | Do | Success looks like |
|---|---|---|---|
| **V13** | REQUIRED | In the V7 run folder, right-click `Run_Metadata_....json` → **Open with → Notepad** | It contains `"build"` with `"version": "0.1.0rc1"` and a long `"source_fingerprint"` (`"git_commit": null` is normal for a ZIP download); `"method_source"` names QLOPB commit 6cbadc7; `"input_datasets"` names NSE:ICICIBANK with its checksum; `"qlopb_settings"` shows `"timeframe": "as_loaded"` |

## Part 6. If something goes wrong

- Q-MAP explains problems in its own windows (NOT READY, INVALID PARAMETERS, a message). Follow the explanation.
  Nothing in this guide can change your original files.
- If **red text** appears in the IDLE window, or a window freezes for more than a few minutes: take a screenshot,
  close Q-MAP with the window's **X**, note the time, write F in Part 9 and continue with the next check if you can.
  You never need to read or fix the red text; send the screenshot.
- If the package installation in V1 fails (no internet, company firewall): screenshot the message and send it.

## Part 7. Close and restart

| # | Kind | Do | Success looks like |
|---|---|---|---|
| **W12** | REQUIRED | Close both windows with their **X** | Both close at once; no error; no black window left behind |
| **V14** | REQUIRED | Open both programs again (IDLE → F5) | Folders remembered; every dataset still listed; the Workbench's **Last run folder** shows the latest completed run; a new scan of `Market_Files` reports every file "unchanged" |
| **W11** | REQUIRED | Take the "after" pictures of your real files and of `Market_Files` | Every Size and Date modified identical to the "before" pictures |

## Part 8. Afterwards: everyday use

Database Manager → Sources (add your real market-data folders once; scan when files change) → Datasets and Storage
(derive weekly/monthly when needed) → Analytical Workbench (choose the analysis, select one dataset, Check readiness,
RUN ANALYSIS) → Open Output Folder. Read the known-limitations document before using results for research decisions.
For weekly/monthly research with a start date, start on the first trading day of a week or month.

## Part 9. Record of the session

| Item | Value |
|---|---|
| Date (dd-mmm-yy) | |
| Windows version | |
| Python version (IDLE first line) | |
| Commit tested | |
| Overall result | ACCEPTED / NOT ACCEPTED |

| Check | Kind | Result (P/F/NT) | Notes |
|---|---|---|---|
| V1 | REQUIRED | | |
| V2 | REQUIRED | | |
| V3 | REQUIRED | | |
| W1 | REQUIRED | | |
| W2 | REQUIRED | | |
| W3 | REQUIRED | | |
| W4 | REQUIRED | | |
| W5 | REQUIRED | | |
| W6 | REQUIRED | | |
| W7 | REQUIRED | | |
| W8 | REQUIRED | | |
| A4 | REQUIRED | | |
| V5 | REQUIRED | | |
| W10 | REQUIRED | | |
| W9 | REQUIRED | | |
| A5 | REQUIRED | | |
| A7 | REQUIRED | | |
| V6 | REQUIRED | | |
| V7 | REQUIRED | | |
| V9 | REQUIRED | | |
| V13 | REQUIRED | | |
| W12 | REQUIRED | | |
| V14 | REQUIRED | | |
| W11 | REQUIRED | | |
| W13 | REQUIRED | | |
| W14 | REQUIRED | | |
| W15 | REQUIRED | | |
| W16 | REQUIRED | | |
| W17 | REQUIRED | | |
| W18 | REQUIRED | | |
| V4, V8 | optional | | |
| V10, V11 | optional | | |
| A6, A8 | optional | | |
| V12 | optional | | |

Send this table and the zipped `Evidence` folder (right-click → Send to → Compressed (zipped) folder) for review.
Merging into `main` stays your decision afterwards.
