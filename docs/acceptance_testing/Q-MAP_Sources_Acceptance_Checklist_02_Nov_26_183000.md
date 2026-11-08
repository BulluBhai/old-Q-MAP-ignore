# Q-MAP Sources (automatic loading): owner acceptance checklist, Windows and IDLE

Prepared 02-Nov-26 for the branch `claude/happy-brahmagupta-su6tnr`. **Status: not yet performed by the Project Owner.**
Every result below is blank until you fill it in. Nothing here has been run on Windows or in IDLE by Claude; the
automated tests ran in a Linux container (see the PR).

**Before you start**
- Python 3.11 or newer on Windows; the branch checked out (or downloaded) into your `Q-MAP_APP` folder.
- A copy of a few real files in a folder of their own, for example `D:\Q-MAP\Q-MAP_TEST_FILES\scan_test\`. Use copies,
  not your only originals. Include: one daily CSV, one intraday CSV, one Excel file, and, if you have one, a file whose
  name says nothing about the instrument (for example `csv headers std.csv`).
- Write down each file's size and "Date modified" (File Explorer, Details view) before step 4. To be stricter, record
  its checksum: in Command Prompt, `certutil -hashfile "<file>" SHA256`.

Result: **P** = pass, **F** = fail (write what you saw), **NT** = not tested.

| # | Step | Expected outcome | Result | Notes |
|---|---|---|---|---|
| 1 | Open `Q-MAP_APP\database_manager.py` in IDLE and press **F5** | The Database Manager window opens. Home lists **Sources (automatic loading)** as READY | | |
| 2 | On Home, choose (or confirm) your `Q-MAP_DATA` and `Q-MAP_OUTPUT` folders | Both shown as usable | | |
| 3 | Press **Open** next to Sources. Set Market time zone `Asia/Kolkata`, Default exchange `NSE`. Press **Add folder...** and choose your test folder | The folder appears in section 1 and is selected. Trying to add your `Q-MAP_DATA` folder instead is refused with a message | | |
| 4 | Press **SCAN SELECTED FOLDER NOW** | Progress and Live Log move; the window stays responsive. Section 2 lists every file with a result. Files with a clear layout and a name like `NSE_NIFTY, 1D.csv` show **Imported** | | |
| 5 | Select an Imported file in section 2 | The text box explains how it was read (separator, header, columns, date layout, time zone, instrument, timeframe). Check that these match the file | | |
| 6 | Select a file shown as **Needs your answer** | The question is shown in plain words; only the matching answer boxes are switched on | | |
| 7 | Type the exchange and symbol (and anything else asked), press **Save answer**, then scan again | That file now shows **Imported**. Files you did not touch show change "unchanged" | | |
| 8 | Scan again without changing anything | Every file shows "unchanged"; **no new datasets** appear in Datasets and Storage | | |
| 9 | Open **Datasets and Storage** | One dataset per imported file, with the right instrument, timeframe, first and last dates and bar count. Select one: its original file name is listed | | |
| 10 | Compare one dataset with its file: open the file in Excel; check the number of data rows and the first and last close | Bars = data rows; the first and last close match | | |
| 11 | Put a copy of a file in the folder with one price changed (e.g. one close +1) and a new name, then scan | It is imported as another dataset; its detail says some bars **differ** from the existing dataset; in Datasets and Storage it shows "Passed with warnings". The earlier dataset is unchanged | | |
| 12 | Put a deliberately broken copy in the folder (e.g. type `abc` into one close, or make one low higher than the high), then scan | Shown as **Rejected** with the reason; it does **not** appear in Datasets and Storage | | |
| 13 | Close Database Manager. Open `Q-MAP_APP\analytical_workbench.py` and press **F5**; open Run an analysis | The imported datasets are listed; the rejected file is not | | |
| 14 | Select one daily dataset, Dataset Summary, start and end dates inside its range; run it | Completed, with a Run ID starting `DSUM_`. **Open Output Folder** shows a `Dataset_Summary_...csv` and a `Run_Metadata_...json` | | |
| 15 | Check the summary against the file: Bars, First bar, Last bar, First close, Last close | They match the rows of the file inside the chosen dates | | |
| 16 | Run Dataset Summary again with a start date after the data end (e.g. 01/01/30) | Refused with a plain explanation; **no** new run folder is created | | |
| 17 | Compare the size and Date modified (or checksum) of every file in your test folder with step "Before you start" | All identical: Q-MAP did not change any source file | | |
| 18 | In Sources, select the folder and press **Stop using selected folder** | The folder disappears from the list; the files in it and the datasets in Datasets and Storage remain | | |
| 19 | Close both applications with the window's X button | Both close at once, with no error window and no black ghost window | | |

**Optional (cloud folder).** Repeat steps 3-8 with a folder inside OneDrive or Google Drive on this computer. For an
"online only" file, Windows may download it when Q-MAP reads it; if it cannot be read (for example while offline),
the scan should report it as **Failed** with the advice to make it available offline, and nothing else should be
affected. This behaviour has not been tested with a real sync client.

**Record of the session**

| Item | Value |
|---|---|
| Date (dd-mmm-yy) | |
| Windows version | |
| Python version (IDLE: Help > About IDLE) | |
| Commit tested (from GitHub, the branch's latest commit) | |
| Files used (names only) | |
| Overall result | |

Please send the filled table (and a screenshot of any F result) back on the PR.

## Addendum 02-Nov-26: re-test after the PR #9 findings fix (branch `claude/friendly-babbage-8xyrgo`)

Only what this change affects, and only what Claude could not check on Windows. Use **copies** of your eight files in a
new test folder and a **new** pair of `Q-MAP_DATA` / `Q-MAP_OUTPUT` folders (so the earlier 4h RIVERUSD dataset is not
in the way). Market time zone `Asia/Kolkata`, default exchange `NSE`, "File name is the symbol" **off**.
Status: **not yet performed by the Project Owner.** Details and expected figures: `Q-MAP_PR9_Acceptance_Findings_02_Nov_26_210000.md`.

| # | Step | Expected outcome | Result | Notes |
|---|---|---|---|---|
| A1 | Add the folder and scan | `NSE_BANKNIFTY, 15.csv` Imported. 5PAISA, AKZOINDIA, ICICIBANK, OLAELEC, UJJIVAN, VERANDA: Needs your answer (symbol). RIVERUSD: Needs your answer (exchange or venue), **not** NSE | | |
| A2 | Select ICICIBANK.txt | Exchange box shows `NSE`, Symbol box `ICICIBANK`, already filled in. Press Save answer only | | |
| A3 | Do A2 for 5PAISA, VERANDA, AKZOINDIA, OLAELEC, UJJIVAN; for RIVERUSD type a venue (e.g. `CRYPTO`); scan again | Imported: ICICIBANK (1D), 5PAISA (30m), VERANDA (1m), RIVERUSD (**3h** if DQ-7 is approved; otherwise Rejected "180 minutes apart ... does not relabel"). Rejected: AKZOINDIA (repeated timestamps, low above open), OLAELEC (repeated timestamps), UJJIVAN (repeated timestamps; no longer "column 2 is not a number") | | |
| A4 | Scan again without changes | Every file "unchanged"; no new datasets | | |
| A5 | Workbench: Dataset Summary for ICICIBANK; use the Start date **Calendar...**, `<<` back to January 1998 and pick 02; End date: type `02-Nov-26` | Run completes; Bars 7,166; first close 7.86; last close 1,387.40 | | |
| A6 | In the calendar, `>>` from 1998 to 2026, then `<` / `>` | Year changes by one per click, month kept; month buttons still work | | |
| A7 | Press **Open Output Folder** under the completion message | File Explorer opens directly at that run's `DSUM_...` folder (CSV and JSON inside) | | |
| A8 | Rename that run folder in Explorer, press the button again | A message says the folder no longer exists; no error window | | |
