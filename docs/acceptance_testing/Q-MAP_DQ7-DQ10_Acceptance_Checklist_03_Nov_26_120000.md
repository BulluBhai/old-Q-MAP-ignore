# Q-MAP data automation (DQ-7 to DQ-10): owner acceptance checklist, Windows and IDLE

> **Superseded on 08-Nov-26** by `Q-MAP_DQ7-DQ10_Acceptance_Checklist_v2_08_Nov_26_151819.md` (same folder), the tracker
> of the new guide (W1-W19). Use the new tracker. This file is kept unchanged below as the record of 03-Nov-26.


Prepared 03-Nov-26 for the branch `claude/friendly-babbage-8xyrgo`; W13-W18 added the same day. **Status: OUTSTANDING — not yet performed by the Project Owner.**
Only what a Linux container cannot establish is listed; everything else is covered by the automated tests (see the
implementation report). Expected figures for your eight files are in
`Q-MAP_DQ7-DQ10_Implementation_Report_03_Nov_26_120000.md`, section 5.

**Before you start:** copies of your eight files (and, if you like, a few more) in a NEW test folder, and a NEW pair
of `Q-MAP_DATA` / `Q-MAP_OUTPUT` folders. Add three extra copies to the test folder: `ICICIBANK (1).txt` (identical
copy), `ICICIBANK - Copy.txt` (identical copy) and a `RELIANCE_EQ.csv` (a small daily file of another stock, renamed; not a copy of one of the eight files).

Result: **P** pass, **F** fail (write what you saw), **NT** not tested.

| # | Step | Expected outcome | Result | Notes |
|---|---|---|---|---|
| W1 | Database Manager (`database_manager.py`, F5) > Sources. Leave **Market time zone** and **Default exchange** empty; leave "Identify the instrument from the file name" ticked. **Add folder...**, then **SCAN SELECTED FOLDER NOW** | No question window at any point. Imported: 5PAISA (30 minutes), RIVERUSD (CRYPTO, 3 hours), ICICIBANK (Daily, its copies "Already loaded"), BANKNIFTY (15 minutes), OLAELEC (1 minute), UJJIVAN (5 minutes), VERANDA (1 minute), RELIANCE_EQ. Not loaded: AKZOINDIA (low above open on 08-Nov-25) | | |
| W2 | Select OLAELEC.xlsx | Detail shows "Detected timeframe: 1 minute", "Validation: Consistent across 20 sampled block(s) (620 of 69000 rows examined)", "Status: Accepted by default" and a warning about conflicting observations under Exceptions | | |
| W3 | Read the **Exceptions** box | One line per kind, e.g. "Instrument not in the alias registry (provisional)" listing several files once, "Conflicting observations inside the file" (OLAELEC), "Cryptocurrency: trading venue unknown" (RIVERUSD), "Time zone assumed" (AKZOINDIA, OLAELEC, UJJIVAN), "Not loaded: data errors" (AKZOINDIA) | | |
| W4 | Press **Open run folder** | Explorer opens the scan's folder with `Scan_Report_...csv` and `Identification_Exceptions_...csv`; open the latter in Excel: grouped rows, the copies of one name on one row | | |
| W5 | Select RELIANCE_EQ.csv, type `RELIANCE` as **Canonical name**, press **Add selected names to alias registry**; then **Open alias registry folder** and open `Instrument_Aliases.csv` in Excel; scan again | The CSV has a row `RELIANCE, RELIANCE EQ`; the next scan lists RELIANCE_EQ.csv as NSE:RELIANCE; it no longer appears under "not in the alias registry" | | |
| W6 | Ctrl+click two files (e.g. VERANDA and 5PAISA), type a reason, press **Reject selected** | Both show "Rejected by you"; Exceptions lists them. Close and open **Analytical Workbench**: neither is offered | | |
| W7 | Back in Sources, select them and press **Restore selected** | Both show "Imported" again; the Workbench offers them after a refresh | | |
| W8 | Put 30 or more file copies in the folder (any data files), press SCAN, then **Stop scan** while it runs | The window stays responsive; the scan stops after the current file; the message says how many files were not processed; the datasets of the files done are in Datasets and Storage; scanning again processes the rest | | |
| W9 | Workbench: Dataset Summary for OLAELEC | Readiness READY with two NOTEs (validation and "Unresolved conflicting observations"); the run completes; the CSV has "Conflicting timestamps" = 183 | | |
| W10 | Datasets and Storage: select a dataset, **Reject (reversible)**, then **Restore** | State column shows "Rejected by you", then "Active"; nothing is moved or deleted | | |
| W11 | Compare the size and Date modified of every file in your test folder with before | All identical: Q-MAP did not change any source file | | |
| W12 | Close both applications with the window's X button | Both close at once, with no error and no black window | | |

### Interval patterns (added 03-Nov-26 after the second and third reviews; W13-W18)

These use six **synthetic** 5-minute files in the repository folder
`docs/acceptance_testing/dq7_pattern_files_03_Nov_26/` (not market data; your eight files do not contain these
patterns). Copy the six files into a NEW, separate test folder and add it in Sources. The same files are scanned by
the automated test `Tests/integration/test_dq7_acceptance_pattern_files.py`, which confirms the outcomes below on
Linux; this checklist confirms what you see on Windows/IDLE. In every case the detected timeframe stays **5 minutes**
(the full-file check never changes it).

| # | Step | Expected outcome | Result | Notes |
|---|---|---|---|---|
| W13 | Sources: add the pattern folder, **SCAN SELECTED FOLDER NOW** | 6 imported, no question; every file shows "Detected timeframe: 5 minutes" and "Validation: Consistent across 15 sampled block(s)" | | |
| W14 | **Random missing bars**: select `NSE_RANDOMGAPS.csv` (about 10 % of bars missing at random) | No interval warning of either kind; only "Some days have fewer bars than usual". Not listed under either interval exception line | | |
| W15 | **Regular missing-bar pattern (uncertain)**: select `NSE_EVERYOTHER.csv` (one day with every other bar missing, i.e. a 10-minute grid) | Warning "Part of the file may have another bar interval" with the source rows and the words "cannot show whether"; Exceptions line "A section may have another bar interval or regularly missing bars (full-file check)" lists the file; timeframe still 5 minutes | | |
| W16 | **Genuine interval change (detected)**: select `NSE_GENUINE3M.csv` (one day of 3-minute bars) and `NSE_DAILY0000.csv` (35 one-bar dates at 00:00) | Warning "Part of the file has another bar interval" with the source rows (3 minute steps; "outside the times of the intraday bars, like daily data"); Exceptions line "A section of the file has another bar interval (found by the full-file check)" lists both | | |
| W17 | **Daily-like bars at an intraday time (uncertain)**: select `NSE_DAILY0915.csv` (35 one-bar dates at 09:15) | Listed under the "may have another bar interval" line, not the "has another bar interval" line; the detail says "a time the intraday bars also use" | | |
| W18 | **Sparse instrument**: select `NSE_SPARSE.csv` (35 consecutive dates with one bar each at varying times) | No interval warning of either kind; "Some days have fewer bars than usual" lists the one-bar dates. Then **Open run folder**: the per-file problem reports `issues_event<n>.csv` of the W15-W17 files contain the interval finding with its source rows (two `interval_change_uncertain`, two `interval_change_detected`); W14 and W18 have none; `Scan_Report_...csv` lists all six files as imported. Workbench: Dataset Summary on `NSE_EVERYOTHER` shows readiness "Validated with warnings: ... interval_change_uncertain ..." and runs | | |

Known limitation seen in W16/W17: in the two `DAILY` files the one-bar dates outnumber the intraday dates, so
"Some days have fewer bars than usual" is not shown for them (that check compares with the most common number of
bars per date). The interval warnings are shown.

**Record of the session**

| Item | Value |
|---|---|
| Date (dd-mmm-yy) | |
| Windows version / Python version | |
| Commit tested | |
| Overall result | |
