# Q-MAP — Windows/IDLE acceptance guide for PR #10 (W1 to W18), for a non-programmer

> **Superseded on 08-Nov-26** by `Q-MAP_Windows_IDLE_Acceptance_Guide_v2_08_Nov_26_151819.md` (same folder), written to
> the User Documentation Standard for the PR #10 program after PR #9 was added. Use the new guide. This file is kept
> unchanged below as the record of 03-Nov-26.


Prepared 03-Nov-26. **Status: OUTSTANDING — to be carried out by the Project Owner.** This guide explains how to carry
out the 18 checks in `Q-MAP_DQ7-DQ10_Acceptance_Checklist_03_Nov_26_120000.md` (same folder). You record results in that
checklist. No command line is needed at any point.

## Part A — Before you start (about 15 minutes, once)

### A1. Get the version to be tested

1. Open https://github.com/BulluBhai/Q-MAP/pull/10 in your browser.
2. Click the branch name `claude/friendly-babbage-8xyrgo` near the top, then the green **Code** button, then
   **Download ZIP**.
3. Unzip it to a NEW folder, for example `D:\Q-MAP_TEST_03_Nov_26\Q-MAP` (not inside your usual Q-MAP folder, not inside
   OneDrive).
4. Write down the latest commit shown on the PR page ("Commits" tab, top line) in the checklist's "Commit tested" box.
   At the time of writing it is the commit after `8e98440` that adds this guide.

### A2. Prepare three NEW empty folders (never your real ones)

| Folder | Example | Used for |
|---|---|---|
| Test data | `D:\Q-MAP_TEST_03_Nov_26\Q-MAP_DATA` | Q-MAP's registry and stored copies |
| Test output | `D:\Q-MAP_TEST_03_Nov_26\Q-MAP_OUTPUT` | run folders, reports |
| Evidence | `D:\Q-MAP_TEST_03_Nov_26\Evidence` | your screenshots and copies of reports |

### A3. Prepare the two test-file folders

**Folder 1 — your eight market-data files (COPIES only).**
1. Create `D:\Q-MAP_TEST_03_Nov_26\Market_Files`.
2. COPY (Ctrl+C, Ctrl+V — never drag/move) your eight files into it: `5PAISA_30min.csv`, `AKZOINDIA.parquet`,
   `CRYPTO_RIVERUSD, 180.csv`, `ICICIBANK.txt`, `NSE_BANKNIFTY, 15.csv`, `OLAELEC.xlsx`, `UJJIVAN.txt`,
   `VERANDA_1min.csv`.
3. Add the three extra files the checklist asks for: `ICICIBANK (1).txt` and `ICICIBANK - Copy.txt` (copies of
   ICICIBANK.txt, renamed) and `RELIANCE_EQ.csv` (a small daily file of another stock).

**Folder 2 — the six synthetic pattern files (made for this test; NOT market data).**
1. Create `D:\Q-MAP_TEST_03_Nov_26\Pattern_Files`.
2. From the unzipped code folder, copy the six files in `docs\acceptance_testing\dq7_pattern_files_03_Nov_26\`:

| File | What it contains (5-minute bars, synthetic prices) | Used in |
|---|---|---|
| `NSE_RANDOMGAPS.csv` | about 10 % of bars missing at random | W14 |
| `NSE_EVERYOTHER.csv` | one day with every other bar missing (a regular 10-minute pattern) | W15 |
| `NSE_GENUINE3M.csv` | one day of 3-minute bars | W16 |
| `NSE_DAILY0000.csv` | 35 days with a single bar at 00:00 | W16 |
| `NSE_DAILY0915.csv` | 35 days with a single bar at 09:15 | W17 |
| `NSE_SPARSE.csv` | 35 days with a single bar each, at different times of day | W18 |

### A4. Record your original files BEFORE the test (for W11)

In the folder where your REAL eight files are kept: **View → Details**, make sure the **Size** and **Date modified**
columns are visible, press **Win+Shift+S**, capture the window, and save the picture as
`Evidence\W00_originals_before.png`. Do the same for `Market_Files`.

### A5. How to keep evidence (every step)

- **Screenshot:** Win+Shift+S → drag around the window → click the notification → **Save** as
  `Evidence\W<number>_<short name>.png` (for example `W15_everyother_warning.png`).
- **Reports:** when a step says "Open run folder", copy that whole run folder into `Evidence\`.
- **Result:** write P (pass), F (fail) or NT (not tested) in the checklist's Result column, and in Notes what you saw
  if it differs.
- At the end, right-click the `Evidence` folder → **Send to → Compressed (zipped) folder**; keep the ZIP.

### A6. If a result differs from what is expected

1. Do not repeat or "fix" anything first. Take a screenshot of exactly what you see.
2. Copy the run folder (Sources → **Open run folder**) into `Evidence\`.
3. Write F and a one-line description in the checklist; continue with the next step if the program still works.
4. If a window shows an error, screenshot it, close Q-MAP with the window's **X**, and note the time.
5. Send the checklist and the Evidence ZIP for review. Nothing in this test can damage your real files: everything
   works on copies in new folders.

## Part B — Start Q-MAP

1. Open **IDLE**. **File → Open** → the unzipped folder → `database_manager.py`. Press **F5**.
2. On the **Home** screen choose the Test data folder (A2) as Q-MAP_DATA and the Test output folder as Q-MAP_OUTPUT.
   Never choose your real folders for this test.
3. The **Analytical Workbench** is opened the same way with `analytical_workbench.py` (needed in W6, W7, W9, W18).

## Part C — The checks

Each line: where → what to do → what you should see. The full wording of the expected results is in the checklist.

### Your eight market-data files (W1-W12; folder `Market_Files`)

| # | Screen | Do | You should see |
|---|---|---|---|
| W1 | Database Manager → **Sources** | Leave Market time zone and Default exchange empty; keep "Identify the instrument from the file name" ticked. **Add folder...** → `Market_Files` → **SCAN SELECTED FOLDER NOW** | No question window. The files are imported with the timeframes listed in the checklist (including RELIANCE_EQ); AKZOINDIA "not loaded" (data error on 08-Nov-25) |
| W2 | Sources, file list | Click `OLAELEC.xlsx` | "Detected timeframe: 1 minute", "Consistent across 20 sampled block(s)", "Accepted by default", a conflicting-observations warning |
| W3 | Sources, **Exceptions** box | Read it | One line per kind of exception (see checklist) |
| W4 | Sources | **Open run folder** | Explorer opens the scan folder with `Scan_Report_...csv` and `Identification_Exceptions_...csv` |
| W5 | Sources | Select `RELIANCE_EQ.csv`, type `RELIANCE` as Canonical name, **Add selected names to alias registry**, scan again | It is then listed as NSE:RELIANCE |
| W6 | Sources, then Workbench | Ctrl+click two files, type a reason, **Reject selected**; open the Workbench | Both "Rejected by you"; the Workbench does not offer them |
| W7 | Sources, then Workbench | Select them, **Restore selected**; Refresh the Workbench | Both offered again |
| W8 | Sources | Put 30+ file copies in a folder, scan, press **Stop scan** while running | Window responsive; stops after the current file; message says how many were not processed |
| W9 | Workbench → Dataset Summary on OLAELEC | Run it | READY with notes; the CSV shows "Conflicting timestamps" = 183 |
| W10 | Database Manager → **Datasets and Storage** | Select a dataset → **Reject (reversible)** → **Restore** | "Rejected by you", then "Active"; nothing moved or deleted |
| W11 | Explorer | Repeat A4 for your REAL folder and for `Market_Files`; save as `W11_originals_after.png` | Every Size and Date modified identical to `W00_originals_before.png` |
| W12 | Both programs | Close each with the window's **X** | Both close at once, no error, no black window |

### The six synthetic pattern files (W13-W18; folder `Pattern_Files`)

In every case the detected timeframe stays **5 minutes**. These warnings are reports only; they never change data.

| # | Screen | Do | You should see |
|---|---|---|---|
| W13 | Sources | **Add folder...** → `Pattern_Files` → **SCAN SELECTED FOLDER NOW** | 6 imported; no question; each file "Detected timeframe: 5 minutes", "Consistent across 15 sampled block(s)" |
| W14 | Sources | Click `NSE_RANDOMGAPS.csv` | **No** interval warning; only "Some days have fewer bars than usual". (Random missing bars are not another interval) |
| W15 | Sources | Click `NSE_EVERYOTHER.csv` | Warning "Part of the file **may** have another bar interval" with source rows and the words "cannot show whether"; listed under the Exceptions line "A section may have another bar interval or regularly missing bars" |
| W16 | Sources | Click `NSE_GENUINE3M.csv`, then `NSE_DAILY0000.csv` | Warning "Part of the file **has** another bar interval" with source rows (3-minute steps; for DAILY0000 "outside the times of the intraday bars, like daily data"); both under the Exceptions line "A section of the file has another bar interval" |
| W17 | Sources | Click `NSE_DAILY0915.csv` | Under the "**may** have another bar interval" line (not "has"); the detail says "a time the intraday bars also use" |
| W18 | Sources, Explorer, Workbench | Click `NSE_SPARSE.csv`; then **Open run folder**; then Workbench → Dataset Summary on NSE:EVERYOTHER | SPARSE: no interval warning, "Some days have fewer bars than usual" lists the one-bar days. Run folder: the `issues_event...csv` files of W15-W17 contain the interval finding with source rows; RANDOMGAPS and SPARSE have none. Workbench: "Validated with warnings: ... interval_change_uncertain ..." and the summary runs |

Known, expected: for the two DAILY files "Some days have fewer bars than usual" is not shown (their one-bar days
outnumber the full days); the interval warning is shown.

## Part D — Finish

1. Fill in the checklist's "Record of the session" (date as dd-mmm-yy, Windows and Python versions, commit tested,
   overall result).
2. Zip the Evidence folder (A5).
3. Send the checklist and the ZIP for review. Merging stays your decision after the review.

## About your eight original files

- In the Claude sessions of 02/03-Nov-26 the eight files were used only as copies; this session never had them.
- Q-MAP reads source files and stores its own copy; it never writes to a source file. This is covered by automated
  tests (raw-file integrity and "source files never change" tests, run locally and in CI on Windows and Ubuntu).
- Your own confirmation is W11 (sizes and dates before and after, compared with A4). Only you can confirm the real
  files on your computer.
