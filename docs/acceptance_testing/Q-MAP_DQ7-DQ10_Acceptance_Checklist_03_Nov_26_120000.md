# Q-MAP data automation (DQ-7 to DQ-10): owner acceptance checklist, Windows and IDLE

Prepared 03-Nov-26 for the branch `claude/friendly-babbage-8xyrgo`. **Status: not yet performed by the Project Owner.**
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

**Record of the session**

| Item | Value |
|---|---|
| Date (dd-mmm-yy) | |
| Windows version / Python version | |
| Commit tested | |
| Overall result | |
