# Q-MAP v0.1: Windows operating and acceptance guide

For the Project Owner (Windows, Python 3.11, IDLE; no programming or command line needed).
Prepared 03-Nov-26 for release candidate `0.1.0rc1`. **Status: OUTSTANDING. Q-MAP v0.1 is not ready for controlled
analytical use until you have completed this guide and accepted the result.**

This one guide replaces, for v0.1, the separate PR #9 and PR #10 instructions. It contains:
- how to install, start, use, close and restart Q-MAP (Parts 1-7, also your normal operating procedure later);
- every acceptance check, each with "what success looks like": **W1-W18** (the PR #10 checks, unchanged, detailed in
  `docs/acceptance_testing/Q-MAP_Windows_IDLE_Acceptance_Guide_03_Nov_26_150000.md` and
  `Q-MAP_DQ7-DQ10_Acceptance_Checklist_03_Nov_26_120000.md`), **A4-A8** (the still-relevant PR #9 re-test steps) and the
  new **V1-V14** checks for v0.1. A1-A3 of PR #9 are replaced by W1 (files are now read without questions).

Record each result as **P** (pass), **F** (fail) or **NT** (not tested) in the table in Part 9.

---

## Part 1. What you need (once)

1. **Windows 10 or 11** and about 2 GB of free disk space.
2. **Python 3.11 or newer from python.org**, installed with **"tcl/tk and IDLE"** ticked (the default).
   To check: open **IDLE**; the first line of the window shows the version, for example `Python 3.11.9`.
3. An internet connection the first time (Q-MAP offers to download the Python packages it needs).

## Part 2. Get the release candidate

1. Open the release-candidate pull request on GitHub (link sent with this guide), click the branch name
   `claude/epic-darwin-33o518`, then **Code → Download ZIP**.
2. Unzip it to a new folder, for example `D:\Q-MAP_V01\Q-MAP_APP`. Keep the folder path short, and **not** inside
   OneDrive.
3. Write down the commit shown at the top of the PR's **Commits** tab in the "Commit tested" box (Part 9).

## Part 3. Folders (once)

Create these new, empty folders. **For acceptance, never use your real data folders.**

| Folder | Example | Holds |
|---|---|---|
| Q-MAP_DATA | `D:\Q-MAP_V01\Q-MAP_DATA` | Q-MAP's registry and its own copies of your data |
| Q-MAP_OUTPUT | `D:\Q-MAP_V01\Q-MAP_OUTPUT` | one folder per run: reports, logs, run records |
| Market_Files | `D:\Q-MAP_V01\Market_Files` | **copies** of your eight market files + the three extra files of W-checks (A3 of the W-guide) |
| Pattern_Files | `D:\Q-MAP_V01\Pattern_Files` | the six files from `Q-MAP_APP\docs\acceptance_testing\dq7_pattern_files_03_Nov_26\` |
| V01_Files | `D:\Q-MAP_V01\V01_Files` | `NSE_CONFLICTDAILY.csv` from `Q-MAP_APP\docs\acceptance_testing\v01_files_03_Nov_26\` (synthetic) |
| Evidence | `D:\Q-MAP_V01\Evidence` | your screenshots and copied run folders |

The three Q-MAP folders (code, data, output) must be separate and not inside each other; Q-MAP checks this.
Before you start, take the "before" picture of your original files (A4 of the W-guide: Explorer **View → Details**,
**Win+Shift+S**, save as `Evidence\W00_originals_before.png`).

## Part 4. Start Q-MAP

| # | Do | Success looks like |
|---|---|---|
| **V1** | Open **IDLE** → **File → Open** → `D:\Q-MAP_V01\Q-MAP_APP\database_manager.py` → press **F5** | Either the **Q-MAP Database Manager** window opens, or a message lists missing packages (pandas, scipy, matplotlib, reportlab, pyarrow ...) and offers to install them. Click **Yes**, wait (a few minutes), then press **F5** again: the window opens. No red text in the IDLE window |
| **V2** | On the **Home** screen choose `Q-MAP_DATA` and `Q-MAP_OUTPUT` (Part 3) | Both folders accepted (green). The Home screen lists Sources, Data Management, Datasets and Storage as available |
| **V3** | Open `analytical_workbench.py` the same way (IDLE → File → Open → F5) | The **Q-MAP Analytical Workbench** opens with the same folders already chosen. Under **Available now**: **MA Research: MA Affinity (QLOPB)** and **Dataset Summary**. Market Intelligence (MIQP) is COMING SOON |

Both windows may stay open at the same time.

## Part 5. Normal operation

### 5.1 Load data (Database Manager → Sources)

Do **W1 to W8** with `Market_Files`, then **W13 to W18** with `Pattern_Files`, exactly as in the W-guide (Part C). Then:

| # | Do | Success looks like |
|---|---|---|
| **A4** | Press **SCAN SELECTED FOLDER NOW** again for `Market_Files` without changing anything | Every file "unchanged"; no new datasets |
| **V4** | **Add folder...** → `V01_Files` → **SCAN SELECTED FOLDER NOW** | `NSE_CONFLICTDAILY.csv` imported as **NSE:CONFLICTDAILY, Daily, 301 bars**, with a conflicting-observations warning (one date, 29-Jul-24, has two different rows) |

### 5.2 Weekly and monthly data (Database Manager → Datasets and Storage)

| # | Do | Success looks like |
|---|---|---|
| **V5** | Select the daily **NSE:ICICIBANK** dataset; under "Derive from daily data" tick **Weekly** and **Monthly** → **DERIVE SELECTED TIMEFRAMES** | Two new datasets: NSE:ICICIBANK Weekly and Monthly, linked to the daily one. Nothing in Market_Files changes |
| **W10** | Reject (reversible) and Restore a dataset, as in the W-guide | "Rejected by you", then "Active" |

### 5.3 Analyses (Analytical Workbench → Run an analysis)

| # | Do | Success looks like |
|---|---|---|
| **W9** | Dataset Summary on OLAELEC (W-guide) | READY with notes; "Conflicting timestamps" = 183 |
| **A5-A8** | Dataset Summary on ICICIBANK with the calendar, Open Output Folder, renamed folder (PR #9 checklist A5-A8) | As in that checklist (A5: Bars 7,166; first close 7.86; last close 1,387.40) |
| **V6** | Choose **MA Research: MA Affinity (QLOPB)**. Look at section 3 (Options) | The boxes are already filled with QLOPB's defaults (MA types SMA, MA start 10, MA end 250, Forward windows 5,10,20,50 ...). The description says the results are exploratory and that Directed IR and the weights are pending your review |
| **V7** | Select **NSE:ICICIBANK Daily** → **Check readiness (nothing is saved)** → **RUN ANALYSIS** | READY (notes possible). The run finishes; Progress shows a Run ID starting `MAAF_`. **Open Output Folder** shows `QLOPB_MA_Affinity_....xlsx`, `QLOPB_MA_Affinity_Report_....pdf`, PNG charts, `MA_Affinity_Candidates_....csv`, `MA_Affinity_Interactions_....csv`, `run_log.txt`, `Run_Metadata_....json`. The Excel and PDF open and show a Top-5 list and the limitations |
| **V8** | Select **NSE:CONFLICTDAILY** → **RUN ANALYSIS** | **Not started**. The readiness box says FAIL: "1 timestamp(s) in the chosen period hold conflicting observations ... (29-Jul-24) ... MA Affinity needs exactly one bar per time". Then type End date `26-07-24` and MA end `60` → **RUN ANALYSIS**: it runs (the conflict is outside the period). Dataset Summary on the same dataset still runs (with a note) |
| **V9** | Select **NSE:ICICIBANK Weekly** → MA end `60` → **RUN ANALYSIS**; then **Monthly** with MA start `5`, MA end `24`, Forward windows `3,6,12` | Both runs finish. In the run log there is no line "Aggregated" (Q-MAP's own weekly/monthly data were used) |
| **V10** | Select a **1-minute or 5-minute** dataset (for example VERANDA) with MA Affinity → **Check readiness (nothing is saved)** | FAIL "Timeframe 1 minute is not supported here (needs: Daily, Weekly, Monthly).". Nothing runs |
| **V11** | ICICIBANK Daily, type `nan` in **Wt: fwd return** → **RUN ANALYSIS** | "Not started: the parameters are not valid"; the box lists "Affinity weights must be finite numbers ...". Put `25` back |
| **V12** (optional) | If you still have the separate QLOPB program: run it on your original `ICICIBANK.txt` with default settings and compare its Excel Top-5 and scores with V7 | Same Top-5 and the same scores (Q-MAP uses the same calculations). If QLOPB refuses or cleans the file differently, note what it says |

### 5.4 The record of each run (code build)

| # | Do | Success looks like |
|---|---|---|
| **V13** | In the V7 run folder, right-click `Run_Metadata_....json` → **Open with → Notepad** | It contains `"build"` with `"version": "0.1.0rc1"` and a long `"source_fingerprint"`; `"git_commit": null` (a ZIP download has no git history; the fingerprint identifies the build); `"method_source"` names QLOPB commit 6cbadc7; `"input_datasets"` names NSE:ICICIBANK with its checksum; `"qlopb_settings"` lists every setting with `"timeframe": "as_loaded"` |

## Part 6. If something goes wrong

- Q-MAP explains problems in its own windows (NOT READY, INVALID PARAMETERS, a message box). Read the explanation;
  it says what to do. Nothing you do in this guide can change your original files.
- If **red text** appears in the IDLE window, or a window freezes for more than a few minutes: take a screenshot
  (Win+Shift+S), close Q-MAP with the window's **X**, note the time, copy the latest run folder into `Evidence\`,
  write F in Part 9 and continue with the next check if you can. You never need to read or fix the red text.
- If the package installation in V1 fails (no internet, or a company firewall): screenshot the message and send it.

## Part 7. Close and restart

| # | Do | Success looks like |
|---|---|---|
| **W12** | Close both windows with their **X** | Both close at once; no error; no black window left behind |
| **V14** | Open `database_manager.py` and `analytical_workbench.py` again (F5) | Both open with your folders remembered; every dataset is still listed; the Workbench's **Last run folder** shows the latest completed run; a new Sources scan of `Market_Files` reports every file "unchanged" |
| **W11** | Take the "after" picture of your original files and of `Market_Files` (W-guide) | Every Size and Date modified identical to the "before" picture |

## Part 8. Afterwards: everyday use

The same steps with your **real** folders: Database Manager → Sources (add your market-data folders once, then scan
when files change) → Datasets and Storage (derive weekly/monthly when needed) → Analytical Workbench (choose the
analysis, select the dataset, Check readiness, Run) → Open Output Folder. Read the known-limitations document before
using results for research decisions.

## Part 9. Record of the session

| Item | Value |
|---|---|
| Date (dd-mmm-yy) | |
| Windows version | |
| Python version (IDLE first line) | |
| Commit tested | |
| Overall result | ACCEPTED / NOT ACCEPTED |

| Check | Result (P/F/NT) | Notes |
|---|---|---|
| V1 | | |
| V2 | | |
| V3 | | |
| W1 | | |
| W2 | | |
| W3 | | |
| W4 | | |
| W5 | | |
| W6 | | |
| W7 | | |
| W8 | | |
| W9 | | |
| W10 | | |
| W11 | | |
| W12 | | |
| W13 | | |
| W14 | | |
| W15 | | |
| W16 | | |
| W17 | | |
| W18 | | |
| A4 | | |
| A5 | | |
| A6 | | |
| A7 | | |
| A8 | | |
| V4 | | |
| V5 | | |
| V6 | | |
| V7 | | |
| V8 | | |
| V9 | | |
| V10 | | |
| V11 | | |
| V12 (optional) | | |
| V13 | | |
| V14 | | |

Send this table and the zipped `Evidence` folder for review. Merging into `main` stays your decision afterwards.
