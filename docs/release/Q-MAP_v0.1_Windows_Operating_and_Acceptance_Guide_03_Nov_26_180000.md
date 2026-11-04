# Q-MAP v0.1 — Windows Owner Acceptance Testing Manual

| | |
|---|---|
| For | The Q-MAP Project Owner (Windows, Python 3.11, IDLE). No programming, no command line, no reading of code or logs |
| Release candidate | Pull request #12: https://github.com/BulluBhai/Q-MAP/pull/12 (branch `claude/epic-darwin-33o518`) |
| Code under test | commit `919c697` (`919c697f4bc83778b82ca8d08855215bf6de0b5c`), version `0.1.0rc1`, **build fingerprint `3fa925abf95b`** |
| Revised | 04-Nov-26 (second revision), after the independent audit of `3f4faea`: new build, new REQUIRED check **W19** (a changed file with the same size and date is detected), notes on multi-instrument files. Earlier versions are kept in Git history |
| Status | **OUTSTANDING** — Q-MAP v0.1 is not ready for controlled analytical use until you complete this manual and accept the result |

Later commits on the pull request that change no program file (only tests, test files or documents) do not change the code you test. You can always check
that you have the right code: every Q-MAP report shows the **build fingerprint**, and it must be `3fa925abf95b`
(check V13).

---

## 1. Purpose of the testing and what acceptance means

Q-MAP has been built and tested automatically by its developers on Linux and on a Windows computer at GitHub. That
proves a great deal, but not everything. Only you can show that:

- it installs and starts on **your** Windows computer from IDLE;
- it reads **your** market files correctly;
- the windows, messages and reports make sense to the person who will use them;
- your original files are left untouched.

**Acceptance** means: you have worked through every REQUIRED check below, recorded the result, and you are satisfied
that Q-MAP v0.1 can be used for controlled analytical research within its stated limits. You record your decision
("ACCEPTED" or "NOT ACCEPTED") in section 16. Acceptance is not approval to merge; merging into `main` remains a
separate decision of yours.

**Controlled analytical use** means: research by you, on data you have checked, knowing the limitations listed in
`docs/release/Q-MAP_v0.1_Known_Limitations_and_Release_Boundaries_03_Nov_26_180000.md`. It does not mean
production use, trading signals or automated decisions.

## 2. What Q-MAP v0.1 includes and what is outside its scope

**Included**

- **Database Manager** — prepares data:
  - *Sources*: you name folders where your market files are kept; Q-MAP finds the files, works out their layout,
    checks them and loads its own copies. It asks you only when something is genuinely unclear.
  - *Datasets and Storage*: the list of prepared data, with Permanent/Temporary storage, reversible "reject", and
    weekly/monthly data built from daily data.
- **Analytical Workbench** — research on prepared data:
  - *MA Affinity (QLOPB)*: your existing QLOPB moving-average research, with its calculations unchanged, now reading
    Q-MAP's prepared data.
  - *Dataset Summary*: a description of a dataset (bars, dates, gaps, returns) to check data before research.
- **Run records**: every analysis gets its own Run ID, its own folder and a record of exactly which data and which
  build of the program produced it.

**Outside v0.1 (by your decisions)**: MIQP Market Intelligence; DQ-11 (asset category and venue), DQ-12 (ignoring
technical export columns), DQ-14 (full-file finding changing the timeframe); OW-33 Option C and any reprocessing;
Opportunity Scanner, backtesting, portfolio and risk. These appear as COMING SOON or not at all.

**Data prepared before 04-Nov-26 (only relevant after acceptance, for your real Q-MAP folders).** On 04-Nov-26 a fault
was corrected in how Q-MAP recognises a file that mixes daily, weekly, monthly, quarterly or yearly sections. Q-MAP does
**not** re-process data you prepared earlier (you have not authorised that). Instead it checks the record kept with
each earlier dataset and tells you in plain words: in Datasets and Storage and in Sources, a line "Timeframe: ..." or
"Earlier classification: ..." says whether the earlier result is the same under the corrected rule, or whether the
corrected rule would call the file MIXED. In the second case MA Affinity refuses that dataset (as for any MIXED data)
and Dataset Summary shows a NOTE. Nothing about the dataset itself is changed. The acceptance test in this manual uses
new, empty folders, so you will not see these notes during the test.

## 3. What you are testing, and what automated testing already covers

Each check is marked:

- **REQUIRED** — only you can do it (your computer, your files, what you see on screen). All REQUIRED checks must be
  done for acceptance.
- **OPTIONAL** — the same behaviour is already proved by automated tests that run on a Windows computer at GitHub for
  every change. Do them only if you want to see the behaviour yourself.

| Already covered automatically (for every change, on Windows and Linux) | Still needs you |
|---|---|
| The automated test suite. On GitHub's Windows computer: 1,341 passed, 1 skipped, 0 failed, including 212 tests that open the real Q-MAP windows. On GitHub's Ubuntu (Linux) computer: 1,235 passed, 107 skipped, 0 failed (run #100, build `3fa925abf95b`). The counts differ because the Linux computer has no screen, so the 105 window tests are skipped there; two tests run only on Windows, and one runs only on Linux/macOS | Installing and starting from IDLE on your PC |
| The six synthetic pattern files of W13-W18 give the expected classifications (`test_dq7_acceptance_pattern_files`) | **W13-W18 remain REQUIRED** (your decision D5-44): the automated test supplements, but does not replace, your own check of what the screen shows |
| The DQ-7 correction of 04-Nov-26 (daily/weekly/monthly sections no longer counted as one timeframe); a changed file with the same size and date is detected (`test_the_w19_acceptance_files_behave_as_the_manual_says`) | Your real files: W1-W12; the same-size change check W19 on your PC |
| MA Affinity gives the same results as standalone QLOPB on sample data; reports carry Run ID, build and checksum | MA Affinity on your real data and reading the reports: V6-V9, V13 |
| Calendar buttons, missing-folder message, refusal messages (A6, A8, V4, V8, V10, V11) | Optional for you |

## 4. Computer and software requirements

1. Windows 10 or 11, about 2 GB of free disk space, and about 3 hours (it can be split over several sittings; Q-MAP
   remembers everything between sittings).
2. **Python 3.11 or newer from python.org**, with "tcl/tk and IDLE" ticked when it was installed (this is the
   default). To check: open IDLE from the Start menu; the first line of the IDLE window shows the version, for
   example `Python 3.11.9`.
3. An internet connection the first time, because Q-MAP may need to download a few standard Python packages.
4. Excel (or any program that opens `.xlsx`), a PDF reader, and Notepad.

## 5. Download the exact release candidate

1. Open https://github.com/BulluBhai/Q-MAP/pull/12 in your browser (sign in to GitHub if asked).
2. Near the top, click the blue branch name **`claude/epic-darwin-33o518`**.
3. Click the green **Code** button, then **Download ZIP**. A file such as `Q-MAP-claude-epic-darwin-33o518.zip` is
   saved in your Downloads folder.
4. In File Explorer, right-click the ZIP → **Extract All...** → choose `D:\Q-MAP_V01\` → **Extract**. Rename the
   extracted folder to `Q-MAP_APP`, so that you have `D:\Q-MAP_V01\Q-MAP_APP\database_manager.py`.
   (Use `C:\` instead of `D:\` if you have no D drive. Keep the path short, and **not** inside OneDrive.)
5. Write the date of download in section 16. The code you test is identified later by its build fingerprint
   `3fa925abf95b` (check V13).

## 6. Prepare the folders and test files

**Golden rule: never give Q-MAP your original market files during this test.** Q-MAP only reads files, but the test
must prove that; so it works on copies, and you check the originals at the end (W11).

**How to copy safely in File Explorer:** select the files, press **Ctrl+C** (copy), open the target folder, press
**Ctrl+V** (paste). Never drag files with the mouse (dragging can *move* them instead of copying).

Create these folders inside `D:\Q-MAP_V01\` (in File Explorer: right-click → **New → Folder**):

| Folder | What goes in it |
|---|---|
| `Q-MAP_DATA` | nothing — Q-MAP fills it (its registry and its own copies of the data) |
| `Q-MAP_OUTPUT` | nothing — every run gets its own folder here |
| `Market_Files` | **copies** of your eight files `5PAISA_30min.csv`, `AKZOINDIA.parquet`, `CRYPTO_RIVERUSD, 180.csv`, `ICICIBANK.txt`, `NSE_BANKNIFTY, 15.csv`, `OLAELEC.xlsx`, `UJJIVAN.txt`, `VERANDA_1min.csv`; plus two more copies of ICICIBANK.txt renamed `ICICIBANK (1).txt` and `ICICIBANK - Copy.txt` (right-click → Rename); plus `RELIANCE_EQ.csv`, a small daily file of another stock |
| `Pattern_Files` | the six files from `D:\Q-MAP_V01\Q-MAP_APP\docs\acceptance_testing\dq7_pattern_files_03_Nov_26\` |
| `V01_Files` | `NSE_CONFLICTDAILY.csv` from `D:\Q-MAP_V01\Q-MAP_APP\docs\acceptance_testing\v01_files_03_Nov_26\` (synthetic) |
| `W8_Many_Files` | 30 or more data files for the Stop test (W8 explains how) |
| `W11_Check` | empty for now; used at the very end (W11) |
| `W19_Scan` | empty for now; used by W19 (Q-MAP's own synthetic test file is copied in there) |
| `Evidence` | your screenshots, with the sub-folders listed in section 13 |

**Before you start — the "before" picture of your originals (part of W11):** open the folder where your real eight
files are kept, choose **View → Details** so the **Size** and **Date modified** columns show, press **Win+Shift+S**,
drag around the window, click the small notification, and **Save** the picture as
`Evidence\06_Originals\W11_1_originals_before.png`.

## 7. Launch Q-MAP through IDLE

### V1 — Database Manager starts (REQUIRED)

- **Checks / why:** Q-MAP starts on your computer without the command line; if packages are missing it installs them
  itself.
- **Prepare:** section 5 done.
- **Steps:**
  1. Start **IDLE** (Start menu → IDLE (Python 3.11)).
  2. **File → Open...** → `D:\Q-MAP_V01\Q-MAP_APP\database_manager.py` → **Open**. A window with the program text
     appears; you do not need to read it.
  3. Press **F5** (or **Run → Run Module**).
  4. If a message "Q-MAP cannot start yet" lists missing packages (for example pandas, scipy, matplotlib,
     reportlab, pyarrow) and asks "Install the missing packages now?", click **Yes** and wait — this can take a few
     minutes with no visible progress. When "Installed. Press F5 again to start Q-MAP." appears, click **OK** and
     press **F5** again in the same IDLE window.
- **Pass:** the **Q-MAP Database Manager** window opens with a Home screen.
- **Fail / unexpected:** red text in IDLE; the message says the installation did not work; nothing opens after two
  minutes.
- **Evidence:** `Evidence\01_Start\V1_database_manager_open.png` (and a picture of any message).
- **If different:** screenshot, close the window, record FAIL, and report (section 15). Do not try to install
  anything by other means.

### V2 — Choose the two folders (REQUIRED)

- **Checks / why:** Q-MAP keeps program, data and results apart, and remembers your choice.
- **Steps:** on the Home screen, next to **Q-MAP_DATA folder** click **Browse...** and choose `D:\Q-MAP_V01\Q-MAP_DATA`;
  next to **Q-MAP_OUTPUT folder** choose `D:\Q-MAP_V01\Q-MAP_OUTPUT`.
- **Pass:** both shown as accepted (green text); Sources, Data Management and Datasets and Storage are listed as READY.
- **Fail:** red text you cannot resolve by choosing the folders named above.
- **Evidence:** `Evidence\01_Start\V2_folders.png`.

### V3 — Analytical Workbench starts (REQUIRED)

- **Steps:** in IDLE: **File → Open...** → `D:\Q-MAP_V01\Q-MAP_APP\analytical_workbench.py` → **F5**. Both windows may
  stay open together.
- **Pass:** the **Q-MAP Analytical Workbench** opens with the same two folders already chosen. Under "Available now":
  **MA Research: MA Affinity (QLOPB)** and **Dataset Summary**. Market Intelligence (MIQP) is shown as COMING SOON.
- **Evidence:** `Evidence\01_Start\V3_workbench_home.png`.

## 8. Database Manager: Sources (loading your files)

Open **Sources** from the Home screen of Database Manager. For every Sources check, the file list in the middle shows
one line per file; clicking a line shows its details on the right; the **Exceptions** box lists anything unusual,
grouped by kind.

### W1 — Your files load without questions (REQUIRED)

- **Checks / why:** Q-MAP reads ordinary files by itself (automation-first, Blueprint §8.5.11 A) and refuses bad data.
- **Steps:**
  1. Leave **Market time zone** and **Default exchange** empty; keep "Identify the instrument from the file name"
     ticked.
  2. **Add folder...** → `D:\Q-MAP_V01\Market_Files` → **Select Folder**.
  3. Click **SCAN SELECTED FOLDER NOW** and wait until the status says the scan has finished.
- **Pass:** no question window at any point. Imported: 5PAISA (30 minutes), RIVERUSD (CRYPTO, 3 hours), ICICIBANK
  (Daily; its two copies shown as "Already loaded"), BANKNIFTY (15 minutes), OLAELEC (1 minute), UJJIVAN (5 minutes),
  VERANDA (1 minute), RELIANCE_EQ. Not loaded: AKZOINDIA (a data error: low above open on 08-Nov-25).
- **Fail:** a question appears; a file not loaded that should be; AKZOINDIA loaded.
- **Evidence:** `Evidence\02_Sources\W1_scan_result.png` (scroll if needed; two pictures are fine).

### W2 — The detected timeframe is explained (REQUIRED)

- **Checks / why:** the bar size is measured from the data, not taken from a file name.
- **Steps:** click the line `OLAELEC.xlsx`.
- **Pass:** "Detected timeframe: 1 minute", "Validation: Consistent across 20 sampled block(s)", "Status: Accepted by
  default", and a warning about conflicting observations (the same minute with different prices).
- **Evidence:** `Evidence\02_Sources\W2_olaelec_detail.png`.

### W3 — Exceptions are grouped (REQUIRED)

- **Steps:** read the **Exceptions** box.
- **Pass:** one line per kind: instruments not yet in the alias registry; conflicting observations (OLAELEC);
  cryptocurrency venue unknown (RIVERUSD); time zone assumed (AKZOINDIA, OLAELEC, UJJIVAN); not loaded: data errors
  (AKZOINDIA).
- **Evidence:** `Evidence\02_Sources\W3_exceptions.png`.

### W4 — The scan report (REQUIRED)

- **Steps:** click **Open run folder**.
- **Pass:** File Explorer opens a folder containing `Scan_Report_...csv` and `Identification_Exceptions_...csv`. Open
  the second in Excel: copies of one name are on one row.
- **Evidence:** `Evidence\02_Sources\W4_run_folder.png`; also copy that whole run folder into
  `Evidence\07_Run_Folders\`.

### W5 — Alias registry (REQUIRED)

- **Checks / why:** you can teach Q-MAP that "RELIANCE EQ" is RELIANCE, without editing any program.
- **Steps:** click `RELIANCE_EQ.csv`; type `RELIANCE` in **Canonical name**; click **Add selected names to alias
  registry**; click **Open alias registry folder** and open `Instrument_Aliases.csv` in Excel (close Excel afterwards);
  click **SCAN SELECTED FOLDER NOW** again.
- **Pass:** the CSV has a row `RELIANCE, RELIANCE EQ`; after the scan RELIANCE_EQ.csv is listed as NSE:RELIANCE.
- **Evidence:** `Evidence\02_Sources\W5_alias_csv.png`, `W5_after_scan.png`.

### W6 — Reject files (REQUIRED)

- **Steps:** hold **Ctrl** and click VERANDA and 5PAISA; type a reason (any words); click **Reject selected**. In the
  Workbench, open **Run an analysis** and click **Refresh**.
- **Pass:** both show "Rejected by you"; the Workbench does not offer them.
- **Evidence:** `Evidence\02_Sources\W6_rejected.png`, `W6_workbench.png`.

### W7 — Restore them (REQUIRED)

- **Steps:** select the same two lines; click **Restore selected**; in the Workbench click **Refresh**.
- **Pass:** both show "Imported" again; the Workbench offers them.
- **Evidence:** `Evidence\02_Sources\W7_restored.png`.

### W8 — Stopping a scan (REQUIRED)

- **Checks / why:** a long scan can be stopped safely; the window stays usable; nothing is half-done.
- **Prepare (File Explorer):** put **30 or more** data files in `D:\Q-MAP_V01\W8_Many_Files`. Best: copies of other
  market files you have (not the eight above), because files Q-MAP has not seen before take longer to read. If you
  have fewer, copy the ones you have, then press **Ctrl+V** several more times in the same folder: Windows adds
  "- Copy", "- Copy (2)" ... until there are 30 or more.
- **Steps:**
  1. In Sources: **Add folder...** → `W8_Many_Files`.
  2. Click **SCAN SELECTED FOLDER NOW**, and within 2-3 seconds click **Stop scan**.
- **Pass:** the window stays responsive (you can scroll); the scan stops after the file it is working on; a message
  says how many files were not processed. Pressing **SCAN SELECTED FOLDER NOW** again processes the rest.
- **Fail:** the window freezes; an error appears; files are reported as loaded that were not.
- **If the scan finishes before you can click Stop:** this is not a Q-MAP fault. Make a second folder with more and
  larger files and try once more. If it is still too fast, record **NOT TESTED** with the note "scan too fast to
  stop" (an automated Windows test, `test_stop_scan_stops_safely_after_the_current_file`, covers this behaviour).
- **Evidence:** `Evidence\02_Sources\W8_stopped.png`.

### A4 — A repeated scan changes nothing (REQUIRED)

- **Steps:** select the `Market_Files` folder line; click **SCAN SELECTED FOLDER NOW** without changing anything.
- **Pass:** every file "unchanged"; no new datasets in Datasets and Storage.
- **Evidence:** `Evidence\02_Sources\A4_rescan.png`.

### W19 — A changed file with the same size and date is detected (REQUIRED)

- **Checks / why:** Q-MAP decides whether a file is unchanged by its **content** (its SHA-256 checksum), not only by
  its size and "Date modified". Before 04-Nov-26 a file whose contents changed while its size and date stayed the same
  could be skipped (review finding A1).
- **The two test files** (synthetic, made by Q-MAP's developer):
  `D:\Q-MAP_V01\Q-MAP_APP\docs\acceptance_testing\w19_same_size_files_04_Nov_26\version_A\NSE_SAMESIZE.csv` and
  `...\version_B\NSE_SAMESIZE.csv`. They have the same name and the same size (2,717 bytes), and they differ in one
  digit (the last volume value: 65194 in A, 65197 in B). They came out of the same ZIP, so their "Date modified" is
  the same, and copying in File Explorer keeps that date.
- **Steps:**
  1. In File Explorer, copy (Ctrl+C / Ctrl+V) `version_A\NSE_SAMESIZE.csv` into `D:\Q-MAP_V01\W19_Scan`.
  2. In Sources: **Add folder...** → `W19_Scan` → **SCAN SELECTED FOLDER NOW**. Expected: `NSE_SAMESIZE.csv` Imported.
  3. In File Explorer, open `W19_Scan` with **View → Details**, take a screenshot showing **Size** and **Date
     modified**, then copy `version_B\NSE_SAMESIZE.csv` into `W19_Scan` and choose **Replace the file in the
     destination**. Take a second screenshot: the size and date look the same as before.
  4. Back in Sources, with the `W19_Scan` line selected, click **SCAN SELECTED FOLDER NOW** again.
- **Pass:** the file is reported as **changed** and processed, not "unchanged" or "skipped". It is Imported as a
  new version, and Datasets and Storage shows a second NSE:SAMESIZE dataset. A note that it overlaps the first version and differs on one date is expected. The first version is kept unchanged. A third scan without any change reports
  it as unchanged.
- **Fail:** the second scan says "unchanged"/"skipped" for `NSE_SAMESIZE.csv`.
- **Note:** if your two screenshots show different dates (for example because the files were not taken from the same
  ZIP), the check still tests that the change is found, but not the same-date case. Write that in Remarks.
- **Evidence:** `Evidence\02_Sources\W19_before.png`, `W19_after_copy.png`, `W19_changed.png`.

### V4 — A file with a conflicting date (OPTIONAL, needed for V8)

- **Steps:** **Add folder...** → `V01_Files` → **SCAN SELECTED FOLDER NOW**.
- **Pass:** `NSE_CONFLICTDAILY.csv` imported as NSE:CONFLICTDAILY, Daily, 301 bars, with a conflicting-observations
  warning: 29-Jul-24 appears twice with different prices. Q-MAP keeps both rows and does not choose between them.
- **Evidence:** `Evidence\02_Sources\V4_conflictdaily.png`.

## 9. Datasets and Storage

### V5 — Weekly and monthly data from daily data (REQUIRED)

- **Checks / why:** weekly and monthly research uses data Q-MAP builds once, in one documented way (first open,
  highest high, lowest low, last close; each bar dated by its last trading day, so no future information is used).
- **Steps:** Home → **Datasets and Storage**; click the **NSE:ICICIBANK Daily** line; under "Derive from daily data"
  tick **Weekly** and **Monthly**; click **DERIVE SELECTED TIMEFRAMES**.
- **Pass:** two new lines, NSE:ICICIBANK Weekly and Monthly, linked to the daily dataset (details show where they came
  from). Nothing in `Market_Files` changes. Clicking the daily line shows, in its details, "Timeframe: measured with the
  corrected DQ-7 comparison (04-Nov-26)" — everything in this test is prepared with the corrected code.
- **Evidence:** `Evidence\03_Datasets\V5_derived.png`.

### W10 — Reversible reject (REQUIRED)

- **Steps:** click any dataset line → **Reject (reversible)** → then **Restore**.
- **Pass:** "Rejected by you", then "Active"; nothing is moved or deleted.
- **Evidence:** `Evidence\03_Datasets\W10_reject_restore.png`.

## 10. Analytical Workbench and MA Affinity

In the Workbench click **Run an analysis**. The screen has three numbered parts: **1. Input** (choose the analysis
and the dataset), **2. Output** (where results go), **3. Options** (settings). **Check readiness (nothing is saved)**
tests whether the chosen data are suitable; **RUN ANALYSIS** runs it; **Open Output Folder** opens the results.

**Two terms you will see:**
- **Run ID** — the name of one run, such as `MAAF_20261104_101500` (MA Affinity, date, time). Every run gets a new one
  and its own folder; an earlier run is never overwritten.
- **Build fingerprint** — a 12-character code (here `3fa925abf95b`) that identifies exactly which version of the
  program produced a result. If the program changes, the code changes. It lets anyone later tell which program
  produced a report.

### W9 — Dataset Summary on a file with conflicts (REQUIRED)

- **Steps:** Analysis: **Dataset Summary**; click the **NSE:OLAELEC** line; **RUN ANALYSIS**; **Open Output Folder**;
  open the CSV in Excel.
- **Pass:** before the run the readiness box says READY with notes; the CSV column "Conflicting timestamps" shows 183.
- **Evidence:** `Evidence\04_Workbench\W9_summary.png`.

### A5 — Dates and the calendar (REQUIRED)

- **Steps:** Dataset Summary; click **NSE:ICICIBANK Daily**; next to Start date click **Calendar...**, click `<<` until
  January 1998, click **2**; in End date type `02-Nov-26`; **RUN ANALYSIS**.
- **Pass:** completes; the CSV shows Bars 7,166, first close 7.86, last close 1,387.40.
- **Evidence:** `Evidence\04_Workbench\A5_summary_icicibank.png`.

### A7 — Open the results (REQUIRED)

- **Steps:** click **Open Output Folder** under the completion message.
- **Pass:** File Explorer opens that run's `DSUM_...` folder.
- **Evidence:** `Evidence\04_Workbench\A7_output_folder.png`.

### V6 — MA Affinity settings are shown (REQUIRED)

- **Steps:** Analysis: **MA Affinity (QLOPB)**; look at part 3.
- **Pass:** the boxes are already filled with QLOPB's usual settings (MA types SMA, MA start 10, MA end 250, Forward
  windows 5,10,20,50 ...), each with a one-line explanation; the description says the results are exploratory and that
  Directed IR and the weights are pending your review.
- **Evidence:** `Evidence\04_Workbench\V6_settings.png`.

### V7 — MA Affinity on your daily data, and where to find the results (REQUIRED)

- **Checks / why:** the main research function works on your real data and its results can be traced back to their
  data and program.
- **Steps:**
  1. Click the **NSE:ICICIBANK Daily** line (one dataset per run).
  2. Click **Check readiness (nothing is saved)**. Read the box: READY (green), possibly with NOTE lines.
  3. Click **RUN ANALYSIS**. Wait until the status shows completed (usually under a minute for about 7,000 daily bars) and a Run ID
     starting `MAAF_`.
  4. Click **Open Output Folder**.
- **Pass — the folder contains:**
  `QLOPB_MA_Affinity_<date>.xlsx` (the workbook), `QLOPB_MA_Affinity_Report_<date>.pdf` (the report),
  several `chart_...png` pictures, `MA_Affinity_Candidates_<date>.csv` and `MA_Affinity_Interactions_<date>.csv` (the
  full tables, for checking), `run_log.txt` and `Run_Metadata_<date>.json` (the run record).
- **Pass — in the workbook:** sheet **Summary**: the line "Instrument / file" names NSE:ICICIBANK, the dataset number
  and the Run ID; "Bar size" says "Daily (Q-MAP registered dataset; not re-aggregated)"; a Top-5 list; WARNINGS and
  LIMITATIONS. Sheet **Data_Quality**: "Run ID", "Code build: qmap 0.1.0rc1 / c2 build 3fa925abf95b", "Dataset
  checksum (SHA-256)", source file and lineage.
- **Pass — in the PDF:** the first lines under the title show the dataset, the Run ID, "Q-MAP build: qmap 0.1.0rc1 /
  c2 build 3fa925abf95b", the source fingerprint and the dataset checksum. Q-MAP's own notes, if any, appear under
  **Warnings** starting with "Q-MAP data:".
- **Fail:** not started without a clear reason; files missing; the build is not `3fa925abf95b`.
- **Evidence:** `Evidence\04_Workbench\V7_completed.png`, `V7_folder.png`, `V7_excel_summary.png`,
  `V7_excel_data_quality.png`, `V7_pdf_first_page.png`; copy the run folder into `Evidence\07_Run_Folders\`.

### V9 — MA Affinity on weekly and monthly data (REQUIRED)

- **Steps:** click **NSE:ICICIBANK Weekly**; set **MA end** to `60`; **RUN ANALYSIS**. Then click **NSE:ICICIBANK
  Monthly**; set **MA start** `5`, **MA end** `24`, **Forward windows** `3,6,12`; **RUN ANALYSIS**.
- **Pass:** both finish; in each workbook "Bar size" says Weekly or Monthly "(Q-MAP registered dataset; not
  re-aggregated)" — Q-MAP's own weekly/monthly data were used.
- **Evidence:** `Evidence\04_Workbench\V9_weekly.png`, `V9_monthly.png`.

### V13 — The run record (REQUIRED)

- **Checks / why:** each result can be traced to its data and to the exact program build.
- **Steps:** in the V7 run folder, right-click `Run_Metadata_<date>.json` → **Open with → Notepad**. Use **Ctrl+F**
  (Find) to look for each of these, one at a time: `3fa925abf95b`, `MAAF_`, `ICICIBANK`, `6cbadc7`, `as_loaded`,
  `corrected comparison`.
- **Pass:** each is found. (Meaning: the build; the Run ID; the dataset; the QLOPB version the method comes from;
  "the data were used as registered, not re-aggregated"; "its timeframe was classified with the corrected DQ-7
  comparison".) `"git_commit": null` is normal for a ZIP download.
- **Evidence:** `Evidence\04_Workbench\V13_metadata.png`.

### OPTIONAL Workbench checks (already proved automatically)

| Ref | Steps | Pass |
|---|---|---|
| **V8** | MA Affinity; **NSE:CONFLICTDAILY**; RUN ANALYSIS. Then End date `26-07-24`, MA end `60`, RUN ANALYSIS | First: "Not started"; the readiness box names 29-Jul-24 and says MA Affinity needs exactly one bar per time. Second: it runs (the conflict is outside the period) |
| **V10** | MA Affinity; a 1-minute dataset such as VERANDA; Check readiness | FAIL "Timeframe 1 minute is not supported here (needs: Daily, Weekly, Monthly)." |
| **V11** | MA Affinity; ICICIBANK Daily; type `nan` in **Wt: fwd return**; RUN ANALYSIS | "Not started: the parameters are not valid"; then type `25` back |
| **A6** | In a date calendar, `>>` from 1998 to 2026, then `<` / `>` | year changes one per click; month kept |
| **A8** | Rename the A7 run folder in Explorer; click Open Output Folder | a message says the folder no longer exists; no error window |
| **V12** | Only if you still use the separate QLOPB program: run it on your original-file copy of ICICIBANK.txt with default settings; compare its Top-5 and scores with V7 | the same Top-5 and scores. Note: QLOPB's own loader handles repeated timestamps differently (it keeps the first and lists the others as rejected); if QLOPB reports repeated timestamps, a difference is expected |

## 11. W13-W18: timeframe-pattern files (REQUIRED)

**Why these matter.** Q-MAP decides a file's bar size (5 minutes, daily ...) by looking at the times in the file. A
file with gaps must not be mistaken for a different bar size, and a file that really changes bar size must not be
treated as uniform, because MA Affinity and other research assume one bar size. These six small files are made up
(not market data); each contains 5-minute bars with one deliberate pattern:

| File | Pattern | What it represents | Correct result |
|---|---|---|---|
| `NSE_RANDOMGAPS.csv` | about 10 % of bars missing at random | ordinary missing data | still 5 minutes, no interval warning |
| `NSE_EVERYOTHER.csv` | one day with every other bar missing | regularly missing bars — looks like 10-minute bars but may just be gaps | 5 minutes, warning "**may** have another bar interval" (Q-MAP cannot tell, so it says so) |
| `NSE_GENUINE3M.csv` | one day of 3-minute bars | a genuine change of bar size | 5 minutes, warning "**has** another bar interval" |
| `NSE_DAILY0000.csv` | 35 days with one bar at 00:00 | daily-style rows inside intraday data | warning "**has** another bar interval" |
| `NSE_DAILY0915.csv` | 35 days with one bar at 09:15 | one bar per day at a normal intraday time — could be daily rows or a sparse instrument | warning "**may** have another bar interval" |
| `NSE_SPARSE.csv` | 35 days with one bar each at varying times | a thinly traded instrument (sparse observations) | no interval warning; "Some days have fewer bars than usual" |

### W13 — Load the six files (REQUIRED)

- **Steps:** Sources → **Add folder...** → `Pattern_Files` → **SCAN SELECTED FOLDER NOW**.
- **Pass:** 6 imported, no question; each file "Detected timeframe: 5 minutes", "Consistent across 15 sampled
  block(s)".
- **Evidence:** `Evidence\05_Patterns\W13_scan.png`.

### W14 — Random gaps are only gaps (REQUIRED)

- **Steps:** click `NSE_RANDOMGAPS.csv`.
- **Pass:** no interval warning of either kind; only "Some days have fewer bars than usual"; not listed under either
  interval line in the Exceptions box.
- **Evidence:** `Evidence\05_Patterns\W14_randomgaps.png`.

### W15 — Regular gaps are flagged as uncertain (REQUIRED)

- **Steps:** click `NSE_EVERYOTHER.csv`.
- **Pass:** warning "Part of the file **may** have another bar interval", with source row numbers and the words
  "cannot show whether"; the Exceptions line "A section may have another bar interval or regularly missing bars
  (full-file check)" lists the file; timeframe still 5 minutes.
- **Evidence:** `Evidence\05_Patterns\W15_everyother.png`.

### W16 — Genuine changes are flagged as detected (REQUIRED)

- **Steps:** click `NSE_GENUINE3M.csv`, then `NSE_DAILY0000.csv`.
- **Pass:** each shows "Part of the file **has** another bar interval" with source rows (3-minute steps; for DAILY0000
  "outside the times of the intraday bars, like daily data"); the Exceptions line "A section of the file has another
  bar interval (found by the full-file check)" lists both.
- **Evidence:** `Evidence\05_Patterns\W16_genuine3m.png`, `W16_daily0000.png`.

### W17 — One bar a day at an intraday time is uncertain (REQUIRED)

- **Steps:** click `NSE_DAILY0915.csv`.
- **Pass:** listed under the "**may** have another bar interval" line (not the "has" line); the detail says "a time
  the intraday bars also use".
- **Evidence:** `Evidence\05_Patterns\W17_daily0915.png`.

### W18 — Sparse instrument, reports and Workbench (REQUIRED)

- **Steps:** click `NSE_SPARSE.csv`; then **Open run folder**; then in the Workbench run **Dataset Summary** on
  **NSE:EVERYOTHER**.
- **Pass:** SPARSE: no interval warning; "Some days have fewer bars than usual" lists the one-bar dates. Run folder:
  the `issues_event...csv` files of the W15-W17 files mention the interval finding with source rows (two say
  `interval_change_uncertain`, two say `interval_change_detected`); RANDOMGAPS and SPARSE have none;
  `Scan_Report_...csv` lists all six as imported. Workbench: the readiness box says "Validated with warnings: ...
  interval_change_uncertain ..." and the summary runs.
- **Evidence:** `Evidence\05_Patterns\W18_sparse.png`, `W18_run_folder.png`, `W18_workbench.png`.

## 12. Closing and restarting Q-MAP

### W12 — Clean closing (REQUIRED)

- **Steps:** close both Q-MAP windows with the **X** in their top-right corner.
- **Pass:** both close at once; no error message; no empty black window left behind.
- **Evidence:** `Evidence\06_Originals\W12_closed.png` (a picture of the desktop after closing).

### V14 — Restart (REQUIRED)

- **Steps:** open `database_manager.py` and `analytical_workbench.py` again from IDLE (F5 each); in Sources, select
  `Market_Files` and scan again.
- **Pass:** folders remembered; every dataset still listed; the Workbench's "Last run folder" shows your latest
  completed run; the scan reports every file "unchanged".
- **Evidence:** `Evidence\06_Originals\V14_restart.png`.

### W11 — Your original files were not changed (REQUIRED, at the very end)

- **Checks / why:** Q-MAP must never alter source files (Blueprint §8.5.11 G). File size and "Date modified" are a
  useful quick look but **are not proof** that the contents are identical. Part 2 lets Q-MAP itself compare the
  contents byte for byte, using a SHA-256 fingerprint of each file.
- **Part 1 — quick look:** open your real files' folder (View → Details) and take
  `Evidence\06_Originals\W11_2_originals_after.png`. Compare with `W11_1_originals_before.png`: same files, sizes and
  dates.
- **Part 2 — content check:**
  1. In File Explorer, **copy** (Ctrl+C / Ctrl+V) your **eight original files** from their real folder into the empty
     `D:\Q-MAP_V01\W11_Check` folder. Copy only these eight (not the ICICIBANK copies and not RELIANCE_EQ).
  2. In Sources: leave **Market time zone** and **Default exchange** empty, keep "Identify the instrument from the
     file name" ticked; **Add folder...** → `W11_Check` → **SCAN SELECTED FOLDER NOW**.
- **Pass:** seven files show **"Already loaded"** and AKZOINDIA shows **"Rejected earlier (unchanged)"**. Meaning:
  Q-MAP calculated each file's fingerprint and found exactly the contents it read from your copies at the start
  (W1). So your originals now hold the same bytes as when you began, and Q-MAP never received the originals themselves
  until this read-only final check.
- **Fail / unexpected:** any of the eight shows **"Imported"** (especially with "bar(s) differ"), or anything else:
  the contents are not the same. Do not try to explain it; record it and report.
- **Evidence:** `Evidence\06_Originals\W11_3_content_check.png`.

## 13. Capturing and organising evidence

**Screenshot:** press **Win+Shift+S**, drag around the window, click the notification that appears, click the
**Save** icon, and save it with the name given in the check. If a check needs more than one picture, add `_2`, `_3`.

**Name:** `<Check>_<short description>.png`, for example `W15_everyother.png`, `V7_pdf_first_page.png`.

**Folders inside `D:\Q-MAP_V01\Evidence`:**

```text
Evidence\
    01_Start\          V1-V3
    02_Sources\        W1-W8, A4, W19, V4
    03_Datasets\       V5, W10
    04_Workbench\      W9, A5, A7, V6-V13
    05_Patterns\       W13-W18
    06_Originals\      W11, W12, V14
    07_Run_Folders\    copies of the run folders named in W4 and V7 (and of any run that behaved unexpectedly)
    Acceptance_Record.docx or .xlsx (your copy of section 16, filled in)
```

At the end: right-click `Evidence` → **Send to → Compressed (zipped) folder**, and send the ZIP with your record.

## 14. Recording results

For every check write one of:

- **PASS** — what you saw matches "Pass".
- **FAIL** — it clearly does not match, or an error appeared.
- **NOT TESTED** — you could not do it (say why: no time, file not available, scan too fast to stop ...).
- **PASS WITH OBSERVATION** — it matches, but you noticed something worth mentioning (a confusing message, a slow
  step, odd wording). Describe it.

Write what you saw in your own words in the Notes column; exact wording on screen helps. You do not need to decide
whether something is serious — that is the reviewers' job.

## 15. Troubleshooting: when a result differs from what is expected

1. **Do not try to repair anything.** Do not change files in Q-MAP_DATA or in the program folder, do not reinstall,
   do not edit settings files.
2. Take a screenshot of exactly what you see (and of any message).
3. If a step mentions a run folder, copy it into `Evidence\07_Run_Folders\`.
4. Write FAIL (or PASS WITH OBSERVATION) and a short description in section 16.
5. If **red text** appears in the IDLE window, or a window does not respond for more than a few minutes: screenshot,
   close Q-MAP with the window's **X**, note the time, and continue with the next check if the program starts again
   (F5). You never need to read or fix the red text.
6. If the package installation (V1) fails: screenshot the message; this usually means no internet or a company
   firewall.
7. Send the record and the Evidence ZIP for review (ChatGPT reviews; Claude corrects). A FAIL does not end the test:
   carry on with the other checks if you can.

Nothing in this manual can change your original files: Q-MAP only reads, and the test works on copies.

## 16. Final acceptance record

| Item | Value |
|---|---|
| Date(s) of testing (dd-mmm-yy) | |
| Windows version | |
| Python version (first line in IDLE) | |
| Date the ZIP was downloaded | |
| Build fingerprint seen in reports (must be `3fa925abf95b`) | |
| Overall decision | ACCEPTED / NOT ACCEPTED |
| Outstanding issues (refer to check numbers) | |

| Check | Kind | Result (PASS / FAIL / NOT TESTED / PASS WITH OBSERVATION) | Notes |
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
| W13 | REQUIRED | | |
| W14 | REQUIRED | | |
| W15 | REQUIRED | | |
| W16 | REQUIRED | | |
| W17 | REQUIRED | | |
| W18 | REQUIRED | | |
| W19 | REQUIRED | | |
| W12 | REQUIRED | | |
| V14 | REQUIRED | | |
| W11 (parts 1 and 2) | REQUIRED | | |
| V4 | OPTIONAL | | |
| V8 | OPTIONAL | | |
| V10 | OPTIONAL | | |
| V11 | OPTIONAL | | |
| A6 | OPTIONAL | | |
| A8 | OPTIONAL | | |
| V12 | OPTIONAL | | |

**Acceptance rule:** ACCEPTED when every REQUIRED check is PASS or PASS WITH OBSERVATION, or any exception has been
reviewed and you have agreed it does not stop controlled analytical use. Merging into `main` stays a separate decision.
