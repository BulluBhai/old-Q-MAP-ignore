# Q-MAP PR #10: Windows and IDLE acceptance guide (W1 to W18), version 2

**08-Nov-26 | Program to test: PR #10, commit `33871b5` or later | Tracker:
`Q-MAP_DQ7-DQ10_Acceptance_Checklist_v2_08_Nov_26_151819.md` (same folder)**

**Written to `docs/standards/Q-MAP_User_Documentation_Standard.md`.**

This guide replaces `Q-MAP_Windows_IDLE_Acceptance_Guide_03_Nov_26_150000.md`, which is kept unchanged as a record.
It tests the PR #10 program **after PR #9 was added to it** (08-Nov-26).

**What you test, and what you do not:** you carry out W1 to W18 (sections 4 and 5). **W19 is not an owner check.**
It is the case of a folder that cannot be read, and the case of a scan that is both stopped and incomplete. Producing
an unreadable folder on purpose would mean changing Windows folder permissions, which you must not do. These cases are
covered by automated tests only (section 5, Part C). **Do not change any Windows permission or security setting for
this test.**

**Status: OUTSTANDING.** To be carried out by the Project Owner.

---

## 1. How this guide works

Every check is written the same way:

> - **Do:** one action. Do exactly this, nothing more.
> - **You should see:** what happens after the action.
> - **Save:** the evidence to keep, with its exact file name.
> - **If different:** what to do instead.

- Do the actions **in order, one at a time**. Look at the screen before the next action.
- **STOP** means:
  1. stop that check;
  2. do not try to repair anything;
  3. write what you saw in the tracker;
  4. continue where the STOP line says.
- You never need to read program code, type commands or understand technical messages. If a message appears, take a
  picture of it.
- Wording marked *(Windows wording; it may differ slightly)* comes from Windows, not from Q-MAP, and could not be
  checked against your computer.

**Evidence types** (the tracker uses the same short names). They work exactly as in round 2c:

| Type | What it is | How to make it |
|---|---|---|
| **PIC** | A screenshot | Section 3.4 |
| **TXT** | The words from a Q-MAP box, pasted into Notepad | Section 3.5 |
| **FILE** | A copy of a file Q-MAP made (CSV) | Section 3.6. Copy, never move |
| **WRITE** | No file; you write the answer in the tracker | - |

A text copy is preferred where it is enough, because it keeps the exact words. **If a text copy cannot be made, take
a picture instead and give it the same name ending in `.png`.**

---

## 2. Words used in this guide

| Word | Meaning here |
|---|---|
| **PR10_Test** | `D:\Q-MAP_V01\PR10_Test`, a **new** folder for this test only. Everything for this test goes in it |
| **Market_Files** | `D:\Q-MAP_V01\Market_Files`, your Q-MAP testing folder with 11 market files. In this test it is only **copied from**; Q-MAP never reads it directly |
| **Database Manager** | The Q-MAP window that loads and manages data, started from `database_manager.py` |
| **Analytical Workbench** | The Q-MAP window that runs analyses, started from `analytical_workbench.py` |
| **Screen buttons** | The buttons at the **top right** of a Q-MAP window. Database Manager: **Home**, **Sources**, **Data Management**, **Datasets and Storage**. Workbench: **Home**, **Run an analysis** |
| **Section** | A framed area with a bold title, for example **1. Input - folders Q-MAP reads market files from** |
| **Folder source** | A folder Q-MAP reads files from, listed in **Sources**, section 1 |
| **Scan** | Q-MAP reads the files of the selected folder source (button **SCAN SELECTED FOLDER NOW**) |
| **Dataset** | One prepared set of price bars (one instrument, one timeframe), with a number |
| **Reject / Restore** | Take a dataset out of use (it is kept, not deleted) / put it back. Both are recorded and reversible |
| **Live Log** | The black box at the bottom of each screen, listing what Q-MAP just did |
| **Run folder** | The folder one scan or analysis writes its reports into, for example `D:\Q-MAP_V01\PR10_Test\Q-MAP_OUTPUT\Data_Management\SCAN_20261108_101500` |

---

## 3. Before you begin

### 3.1 Why this test uses NEW folders

Your round 2c folders (`D:\Q-MAP_V01\Q-MAP_DATA`, `Q-MAP_OUTPUT`, `Q-MAP_APP`) were made by a **later** Q-MAP
program. If the PR #10 program scanned them, it could read some files differently and mark earlier datasets as
replaced. To keep your accepted round 2c records exactly as they are, **this test uses only new folders inside
`PR10_Test`**.

Q-MAP remembers the last two folders chosen, for every copy of the program. So when the PR #10 program first opens,
it will show your round 2c folders. Section 4.2 changes them to the new folders **before anything else**, and
section 6 changes them back at the end.

### 3.2 Rules that protect your data

1. **Never delete, move, rename or edit** anything in `D:\Q-MAP_V01\Q-MAP_DATA`, `Q-MAP_OUTPUT`, `Q-MAP_APP` or
   `Market_Files`.
2. **Your private master data is never used.** Do not point Q-MAP at it and do not copy files from it.
3. Add only the folders this guide names, and only from inside `D:\Q-MAP_V01\PR10_Test`.
4. If Windows offers to **Replace** files, click **Skip these files** or **Cancel**, never **Replace**. *(Windows
   wording; it may differ slightly.)*
5. If Excel or Notepad asks **Save changes?**, click **Don't Save**.
6. Do not click these Q-MAP buttons; they are not part of the tests: **Delete Temporary dataset...**, **Move to
   Temporary**, **Make Permanent**, **DERIVE SELECTED TIMEFRAMES**, **Save answer / correction**, **LOAD FILES INTO
   Q-MAP**.
7. The checks that change Q-MAP's records are W5 (alias name), W6/W7 (reject and restore) and W10 (reject and
   restore). All of them are reversible and only affect the new test folders.
8. **Never change Windows folder permissions or security settings** (the **Security** tab of a folder's
   **Properties**). No check in this guide needs it.
9. If anything unexpected happens: take a picture, write it down, and **do not repair it**.

### 3.3 What you need

- Your laptop with IDLE (Python 3.12), as in round 2c. **Do not install or update anything.**
- About 80 minutes. You may stop after any check; close Q-MAP with the **X** at the top right of each window.
- Notepad, and Excel to look at CSV files.

### 3.4 How to take a picture (PIC)

1. Press **Windows key + Shift + S** together. The screen turns grey.
2. Drag a box around what the **Save** line names.
3. Click the small pop-up at the bottom right. The Snipping Tool opens.
4. Press **Ctrl+S**, open `D:\Q-MAP_V01\PR10_Test\Evidence`, type the exact file name and click **Save**.
5. Close the Snipping Tool.

*(Windows wording in steps 3-4; it may differ slightly.)*

### 3.5 How to make a text copy (TXT)

1. Click once inside the Q-MAP box named in the step.
2. Press **Ctrl+A**. If not all the text turns blue, drag with the mouse from the first to the last line instead.
3. Press **Ctrl+C**.
4. Start **Notepad** (Start menu → type `Notepad`) and press **Ctrl+V**.
5. Press **Ctrl+S**, open `D:\Q-MAP_V01\PR10_Test\Evidence`, type the exact file name (ending `.txt`) and click
   **Save**. Close Notepad.

### 3.6 How to copy a file Q-MAP made (FILE)

1. In File Explorer, click the file **once**.
2. Press **Ctrl+C**.
3. Open `D:\Q-MAP_V01\PR10_Test\Evidence` and press **Ctrl+V**.

The file stays where it was. Never use **Ctrl+X** (cut), and never drag files out of `Q-MAP_OUTPUT`.

---

## 4. Preparation (about 20 minutes, once)

### 4.1 Make the test folders and get the program

1. **Do:** press **Windows key + E**, click **This PC**, double-click **D:**, then double-click **Q-MAP_V01**.
2. **Do:** right-click an empty area → **New** → **Folder**, type `PR10_Test` and press **Enter**. Double-click it.
3. **Do:** inside `PR10_Test`, make these new, empty folders the same way: `Q-MAP_APP`, `Q-MAP_DATA`, `Q-MAP_OUTPUT`,
   `Evidence`, `W_Market`, `W_Pattern`, `W_Stop`.
4. **Do:** in your web browser open `https://github.com/BulluBhai/Q-MAP/tree/claude/friendly-babbage-8xyrgo`, click the
   green **Code** button, then **Download ZIP**. *(GitHub wording; it may differ slightly.)*
5. **Do:** open your **Downloads** folder, right-click the ZIP → **Extract All...** → **Extract**.
6. **Do:** open the extracted folder until you see `database_manager.py`. Press **Ctrl+A**, **Ctrl+C**, then open
   `D:\Q-MAP_V01\PR10_Test\Q-MAP_APP` and press **Ctrl+V**.
7. **You should see** in `PR10_Test\Q-MAP_APP`: `database_manager.py`, `analytical_workbench.py` and folders such as
   `Application` and `docs`.
8. **Do:** on the GitHub page of PR #10 (`https://github.com/BulluBhai/Q-MAP/pull/10`) click the **Commits** tab and
   look at the last line. Write its 7-character code in the tracker, section 1 (**Commit tested**). It should be
   `33871b5` or a later one.

The folders now look like this:

```text
D:\Q-MAP_V01\PR10_Test\
    Q-MAP_APP\      (the PR #10 program)
    Q-MAP_DATA\     (empty; Q-MAP fills it)
    Q-MAP_OUTPUT\   (empty; Q-MAP fills it)
    Evidence\       (your pictures, text copies and file copies)
    W_Market\       (filled in 4.3)
    W_Pattern\      (filled in 4.3)
    W_Stop\         (filled in 4.3)
```

**If different:** if `database_manager.py` is not in `PR10_Test\Q-MAP_APP`, open the extracted folder one level
deeper and repeat step 6. If GitHub asks you to sign in, sign in as usual.

### 4.2 Start Q-MAP and choose the NEW folders (before anything else)

1. **Do:** Start menu → type `IDLE` → click **IDLE (Python 3.12 ...)**.
2. **Do:** in IDLE click **File** → **Open...** → open `D:\Q-MAP_V01\PR10_Test\Q-MAP_APP\database_manager.py`.
3. **Do:** press **F5**.
4. **You should see** the window **Q-MAP Database Manager - prepare and manage market data**, on its **Home** screen.
   The section **Your folders (remembered between sessions, shared by both Q-MAP applications)** probably shows your
   round 2c folders. That is expected (section 3.1). **Do not click any other screen button yet.**
5. **Do:** next to **Q-MAP_DATA folder**, click **Browse...**, go to `D:\Q-MAP_V01\PR10_Test`, click `Q-MAP_DATA`
   once, and click **Select Folder**. *(Windows wording; it may differ slightly.)*
6. **Do:** next to **Q-MAP_OUTPUT folder**, do the same with `D:\Q-MAP_V01\PR10_Test\Q-MAP_OUTPUT`.
7. **You should see** both boxes showing the `PR10_Test` folders, each with `OK - this folder can be used.`, and the
   line `Both folders are ready and remembered.`
8. **Save:** PIC `W00_Folders.png` of the **Your folders** section.

**If different:** if a box still shows `D:\Q-MAP_V01\Q-MAP_DATA` or `D:\Q-MAP_V01\Q-MAP_OUTPUT`, repeat step 5 or 6.
If a red message appears, take a picture and **STOP** (end the session; go to section 6).

### 4.3 Copy the test files

All copies are made with **Ctrl+C** and **Ctrl+V**. Never drag, never cut.

**W_Market (for W1-W12):**
1. **Do:** open `D:\Q-MAP_V01\Market_Files`, press **Ctrl+A**, **Ctrl+C**, open `PR10_Test\W_Market`, press **Ctrl+V**.
2. **You should see** 11 files in `W_Market`: `5PAISA_30min.csv`, `AKZOINDIA.parquet`, `CRYPTO_RIVERUSD, 180.csv`,
   `ICICIBANK.txt`, `ICICIBANK (1).txt`, `ICICIBANK - Copy.txt`, `NSE_BANKNIFTY, 15.csv`, `OLAELEC.xlsx`,
   `RELIANCE_EQ.csv`, `UJJIVAN.txt`, `VERANDA_1min.csv`.
3. **Save:** PIC `W00_Market_Before.png` of `W_Market` in **View** → **Details**, with the **Size** and **Date
   modified** columns visible (this is the "before" picture for W11).

**W_Pattern (for W13-W18):**
1. **Do:** open `PR10_Test\Q-MAP_APP\docs\acceptance_testing\dq7_pattern_files_03_Nov_26`, press **Ctrl+A**,
   **Ctrl+C**, open `PR10_Test\W_Pattern`, press **Ctrl+V**.
2. **You should see** six files: `NSE_DAILY0000.csv`, `NSE_DAILY0915.csv`, `NSE_EVERYOTHER.csv`, `NSE_GENUINE3M.csv`,
   `NSE_RANDOMGAPS.csv`, `NSE_SPARSE.csv`. These are synthetic (made-up) files, not market data.

**W_Stop (for W8; 33 files, so the scan takes long enough to stop it):**
1. **Do:** inside `PR10_Test\W_Stop`, make three folders: `Copy_1`, `Copy_2`, `Copy_3`.
2. **Do:** copy all 11 files of `Market_Files` into **each** of the three folders (Ctrl+A, Ctrl+C in `Market_Files`,
   then Ctrl+V once inside each `Copy_` folder).

```text
D:\Q-MAP_V01\PR10_Test\W_Stop\
    Copy_1\   (all 11 files)
    Copy_2\   (all 11 files again)
    Copy_3\   (all 11 files again)
```

That gives 33 files. Windows never asks to replace anything, because each copy goes into its own folder.

### 4.4 Adding a folder source (used in W1, W8 and W13)

1. **Do:** Database Manager → click **Sources** (top right).
2. **Do:** in section **1. Input - folders Q-MAP reads market files from**, leave **Market time zone:** and **Default
   exchange:** empty. Make sure **Identify the instrument from the file name (RELIANCE (1).csv -> RELIANCE)** is
   ticked. Untick **Include sub-folders**, unless the check says to tick it.
3. **Do:** click **Add folder...**.
4. **You should see** a window titled **Choose the folder with your market-data files**. **Do not click Select Folder
   yet.**
5. **Do:** click in the address bar at the top of that window, type `D:\Q-MAP_V01\PR10_Test` and press **Enter**.
6. **Do:** click **once** on the folder named in the check, then click **Select Folder**. *(Windows wording; it may
   differ slightly.)*
7. **You should see** a new Live Log line `Folder added: NAME (D:\Q-MAP_V01\PR10_Test\NAME)`, and the new folder
   line selected in section 1.

**If the path is wrong:**
1. **Do not scan.**
2. With that line selected, click **Stop using selected folder**. A question **Stop using this folder** appears; click
   **Yes**.
3. The Live Log shows `Folder no longer scanned (its history and data are kept).` Nothing is deleted.
4. Try steps 3-7 once more. If it goes wrong again, **STOP** that check and go to the next one.

### 4.5 Opening the Analytical Workbench (used in W6, W7, W9 and W18)

1. **Do:** in the **IDLE** window click **File** → **Open...** → open
   `D:\Q-MAP_V01\PR10_Test\Q-MAP_APP\analytical_workbench.py`, then press **F5**.
2. **You should see** the window **Q-MAP Analytical Workbench - research on prepared data**. Its **Home** screen shows
   the same two `PR10_Test` folders (they are shared).
3. **Do:** click **Run an analysis** (top right).

**If different:** if the Workbench shows other folders, **STOP**: close it with **X**, and go back to section 4.2.

---

## 5. The checks

Round 2c (accepted on 07-Nov-26) tested an earlier program. These checks repeat the relevant parts on the PR #10
program now that PR #9 has been added. The round 2c test with the same purpose is named after each heading.

**About the expected values for your own files** (W1, W2, W3 and W9, for example `183`): they come from the PR #10
tests of 03-Nov-26 with copies of your files. They could not be re-checked with your files after PR #9 was added.
If you see something different, that is exactly what this test is for: write what you see.

### Part A: your 11 market files (folder `W_Market`)

#### W1: first scan, no questions (PIC + FILE)

1. **Do:** add `W_Market` as a folder source (section 4.4).
2. **Do:** in section **3. Options - scan, review and correct**, click **SCAN SELECTED FOLDER NOW**.
3. **You should see** the scan finish without any question window. Under **Progress / Status** the message starts
   with `Scan finished`. In section **2. Output - files found in the selected folder**, the **Result** column shows:
   - **Imported** for `5PAISA_30min.csv` (30 minutes), `CRYPTO_RIVERUSD, 180.csv` (3 hours, instrument CRYPTO:RIVERUSD),
     `ICICIBANK.txt` (Daily), `NSE_BANKNIFTY, 15.csv` (15 minutes), `OLAELEC.xlsx` (1 minute), `UJJIVAN.txt`
     (5 minutes), `VERANDA_1min.csv` (1 minute) and `RELIANCE_EQ.csv`;
   - **Already loaded** for `ICICIBANK (1).txt` and `ICICIBANK - Copy.txt` (same content as `ICICIBANK.txt`);
   - **Rejected** for `AKZOINDIA.parquet` (a data error: the low is above the open on 08-Nov-25).
4. **Save:** PIC `W01_Scan_Result.png` of section 2.

**If different:** write what you saw in the tracker and continue with W2. If a question window appears, take a picture
`W01_Question.png`, click **Cancel** or close it, and continue.

#### W2: OLAELEC details (TXT) (round 2c test 03)

1. **Do:** in section 2, click the line `OLAELEC.xlsx` once.
2. **You should see** in the box below the list: `Detected timeframe: 1 minute`, a line starting `Validation:
   Consistent across 20 sampled block(s)`, and `Status: Accepted by default`. (OLAELEC's conflicting observations are
   listed in the Exceptions box; that is W3.)
3. **Save:** TXT `W02_OLAELEC.txt` of that box.

**If different:** save the TXT anyway and write what differs.

#### W3: Exceptions box (TXT)

1. **Do:** find the box headed **Exceptions found (grouped; routine files are accepted automatically and not listed):**
   in section 2.
2. **You should see** a first line `... kind(s) of exception, ... file mention(s). Routine files are not listed.` and
   then one line per kind, each followed by the file names. Among them: `Instrument not in the alias registry
   (provisional)`, `Conflicting observations inside the file (kept, not resolved)` (OLAELEC),
   `Cryptocurrency: trading venue unknown` (RIVERUSD), `Time zone assumed Asia/Kolkata`, `Not loaded: data errors`
   (AKZOINDIA).
3. **Save:** TXT `W03_Exceptions.txt` of that box.

#### W4: the scan's reports (FILE x 2)

1. **Do:** in section 2, click **Open run folder**.
2. **You should see** File Explorer open at `D:\Q-MAP_V01\PR10_Test\Q-MAP_OUTPUT\Data_Management\SCAN_...` with
   `Scan_Report_....csv` and `Identification_Exceptions_....csv`.
3. **Save:** FILE copies of both CSV files. Do not rename them.
4. **Do:** open the `Identification_Exceptions_....csv` copy in Excel. **You should see** grouped rows; the three
   ICICIBANK files are on one row. Close Excel with **Don't Save**.

#### W5: alias registry (PIC) (round 2c tests 13-16)

This check changes Q-MAP's alias list in the new `PR10_Test` folders only.

1. **Do:** in section 2, click `RELIANCE_EQ.csv` once.
2. **Do:** in section 3, type `RELIANCE` in the **Canonical name:** box.
3. **Do:** click **Add selected names to alias registry**.
4. **You should see** under **Progress / Status**: `Alias registry updated (a backup was kept). The next scan
   identifies these files again.`
5. **Do:** click **SCAN SELECTED FOLDER NOW**.
6. **You should see** that the **Instrument** column of `RELIANCE_EQ.csv` begins with `NSE:RELIANCE`.
7. **Save:** PIC `W05_Reliance.png` of the `RELIANCE_EQ.csv` line.

#### W6: reject two files (PIC x 2) (round 2c test 17)

Reversible: W7 undoes it.

1. **Do:** in section 2, click `VERANDA_1min.csv`, then hold **Ctrl** and click `5PAISA_30min.csv`. Both lines are
   highlighted.
2. **Do:** in **Reason (recorded):** type `W6 test`.
3. **Do:** click **Reject selected**.
4. **You should see** at once, with no question window: `Rejected 2 dataset(s). They are kept unchanged and no longer
   offered to analyses; Restore undoes it.` Both lines now show **Rejected by you** in the **Result** column.
   Nothing else needs to be clicked.
5. **Save:** PIC `W06_Rejected.png` of section 2.
6. **Do:** open the Analytical Workbench (section 4.5).
7. **You should see** neither VERANDA nor 5PAISA in the dataset list of section **1. Input - analysis and prepared
   datasets**.
8. **Save:** PIC `W06_Workbench.png` of that list.

#### W7: restore them (PIC) (round 2c tests 17-18)

1. **Do:** in Database Manager → **Sources**, select the same two lines (click, Ctrl+click).
2. **Do:** click **Restore selected**.
3. **You should see** `Restored 2 dataset(s). They are offered to analyses again.`, and both lines back to
   **Imported**.
4. **Do:** in the Workbench, click **Refresh** in section 1.
5. **You should see** VERANDA and 5PAISA listed again.
6. **Save:** PIC `W07_Workbench.png` of the list.

#### W8: Stop a scan (PIC) (round 2c test 19)

1. **Do:** tick **Include sub-folders** in section 1, then add `W_Stop` as a folder source (section 4.4).
2. **Do:** click **SCAN SELECTED FOLDER NOW**. Watch **Files done:** under **Progress / Status**. As soon as it starts
   counting (for example `2 / 33`), click **Stop scan**.
3. **You should see** the window stay usable, the stage line `Stopping after the current file...`, and then a message
   starting `Stopped by you after ... file(s); ... file(s) not processed (listed in the scan report). Work already
   done is kept.`
4. **Save:** PIC `W08_Stopped.png` of **Progress / Status**.
5. **Do:** untick **Include sub-folders** again.

**If different:** if the scan finishes before you can click **Stop scan**, write `finished before Stop` in the tracker;
this is not a failure.

#### W9: Dataset Summary of OLAELEC (PIC + FILE)

Use **Dataset Summary**. (In this program it is the only analysis.)

1. **Do:** in the Workbench, section **1. Input - analysis and prepared datasets**, check that **Analysis:** shows
   `Dataset Summary`.
2. **Do:** click once on the line whose **Instrument** is `NSE:OLAELEC`.
3. **Do:** in section **3. Options - parameters**, click **Check readiness (nothing is saved)**.
4. **You should see** in **Readiness of the selected data:** `READY - every requirement is met. Read the warnings
   below.` and two `NOTE` lines (validation warnings, and unresolved conflicting observations).
5. **Save:** PIC `W09_Readiness.png` of that box.
6. **Do:** click **RUN ANALYSIS**.
7. **You should see** under **Progress / Status** a message starting `Completed. Run DSUM_...`.
8. **Do:** click **Open Output Folder**. File Explorer opens
   `D:\Q-MAP_V01\PR10_Test\Q-MAP_OUTPUT\Research_Reports\DSUM_...`.
9. **Save:** FILE copy of `Dataset_Summary_....csv`.
10. **Do:** open the copy in Excel. **You should see** the column **Conflicting timestamps** with the value **183**.
    Close Excel with **Don't Save**.

#### W10: reject and restore in Datasets and Storage (PIC x 2)

Reversible: step 5 undoes it.

1. **Do:** Database Manager → click **Datasets and Storage** (top right).
2. **Do:** click the `NSE:VERANDA` line once.
3. **Do:** click **Reject (reversible)**.
4. **You should see** at once, with no question window: `Rejected 1 dataset(s). They are kept unchanged and no longer
   offered to analyses; Restore undoes it.` The **State** column shows **Rejected by you**.
5. **Save:** PIC `W10_Rejected.png`.
6. **Do:** with the line still selected, click **Restore**.
7. **You should see** `Restored 1 dataset(s). They are offered to analyses again.` and **State** back to **Active**.
8. **Save:** PIC `W10_Restored.png`.

#### W11: source files unchanged (PIC) (round 2c tests 26-27)

1. **Do:** open `PR10_Test\W_Market` in **View** → **Details**.
2. **Save:** PIC `W11_Market_After.png`.
3. **Check:** every **Size** and **Date modified** is identical to `W00_Market_Before.png`.

**If different:** write which file differs. Do not open or change the file.

### Part B: the six pattern files (folder `W_Pattern`)

In every case the detected timeframe stays **5 minutes**. These warnings are reports only; they never change data.

#### W13: scan the pattern files (PIC)

1. **Do:** add `W_Pattern` as a folder source (section 4.4), then click **SCAN SELECTED FOLDER NOW**.
2. **You should see** six lines **Imported** and no question.
3. **Save:** PIC `W13_Pattern_Scan.png` of section 2.

#### W14-W17: the warnings of five files (TXT each) (round 2c tests 04-08)

For each file in the table:

1. **Do:** click the file's line once.
2. **Save:** TXT of the box below the list, with the file name in the table.
3. **Check:** the box contains the words in the "Must contain" column, and not those in the "Must not contain" column.

| Check | File | Must contain | Must not contain | Save as |
|---|---|---|---|---|
| W14 | `NSE_RANDOMGAPS.csv` | `WARNING: Some days have fewer bars than usual` | any line containing `bar interval` | `W14_RandomGaps.txt` |
| W15 | `NSE_EVERYOTHER.csv` | `WARNING: Part of the file may have another bar interval`; `cannot show whether`; `Detected timeframe: 5 minutes` | - | `W15_EveryOther.txt` |
| W16a | `NSE_GENUINE3M.csv` | `WARNING: Part of the file has another bar interval`; `3 minute(s)` | - | `W16a_Genuine3M.txt` |
| W16b | `NSE_DAILY0000.csv` | `WARNING: Part of the file has another bar interval`; `outside the times of the intraday bars` | - | `W16b_Daily0000.txt` |
| W17 | `NSE_DAILY0915.csv` | `WARNING: Part of the file may have another bar interval`; `a time the intraday bars also use` | - | `W17_Daily0915.txt` |

Known and expected: for the two DAILY files, "Some days have fewer bars than usual" is **not** shown.

#### W18: SPARSE file, its report, and the Workbench (TXT + FILE + TXT) (round 2c tests 09-11)

1. **Do:** click `NSE_SPARSE.csv` once.
2. **You should see** `Some days have fewer bars than usual` and **no** line containing `bar interval`.
3. **Save:** TXT `W18_Sparse.txt`.
4. **Do:** click **Open run folder**, and copy `Scan_Report_....csv` (FILE). Open the copy in Excel: **you should see**
   all six files with **Imported**. Close Excel with **Don't Save**.
5. **Do:** in the Workbench, click **Refresh**, click the `NSE:EVERYOTHER` line, then **Check readiness (nothing is
   saved)**.
6. **You should see** a `NOTE` line containing `Validated with warnings` and `interval_change_uncertain`.
7. **Save:** TXT `W18_Workbench.txt` of the readiness box.

### Part C: W19, a folder that cannot be read (AUTOMATED ONLY, NOT AN OWNER ACTION)

**Do not perform W19. Do not change Windows permissions.** In the tracker, W19 is already marked
`AUTOMATED ONLY - not performed by the owner`; leave it as it is.

**Why it is not a manual check.** When a folder inside a source cannot be read (for example because Windows denies
access), Q-MAP must not say "Scan finished". It processes the files it can read, shows a red message starting
`Scan INCOMPLETE:`, and never reports the files in that folder as missing. The only way to produce such a folder on
purpose is to change Windows permissions. That could leave the folder, or other folders, inaccessible, so it is not
part of owner testing. Q-MAP has no button that makes a folder unreadable, and no other safe method was found.

**What covers it instead** (automated tests, run by the developer and by GitHub on Windows and Ubuntu; technical
note, nothing for you to do):

| Case | Automated tests (file :: test) | Where it ran |
|---|---|---|
| A sub-folder cannot be read: scan INCOMPLETE, readable files processed, nothing reported missing; the next scan is complete once the folder is readable | `Tests/integration/test_scan_integrity.py` :: `test_an_unreadable_subfolder_makes_the_scan_incomplete_and_never_missing`, `test_the_folder_becomes_readable_again_and_the_next_scan_is_complete`, `test_an_unreadable_source_folder_marks_nothing_missing`, `test_an_entry_whose_location_cannot_be_read_is_reported_not_silently_dropped` | Windows and Ubuntu CI; the unreadable folder is simulated by the test |
| The same with a **real** permission-denied folder | `test_scan_integrity.py` :: `test_a_real_permission_denied_folder_makes_the_scan_incomplete`, `test_a_real_permission_denied_child_folder_counts_only_when_included` (with and without sub-folders) | Ubuntu CI only (needs a non-root Linux user); skipped on Windows |
| With **Include sub-folders** off, a locked child folder does not make the scan incomplete | `test_scan_integrity.py` :: `test_an_unreadable_child_folder_counts_only_when_sub_folders_are_included` (both settings), `test_links_inside_a_folder_that_is_not_scanned_are_not_listed` | Windows and Ubuntu CI |
| The red `Scan INCOMPLETE:` message in the real Sources window | `Tests/gui/test_window_sources_incomplete.py` :: `test_an_unreadable_subfolder_is_shown_as_an_incomplete_scan` | Windows CI (real window); skipped on Ubuntu (no screen) |
| A scan both **stopped** and **incomplete**: both messages shown; recorded as failed; nothing reported missing | `Tests/integration/test_pr9_pr10_integration.py` :: `test_a_stopped_scan_that_is_also_incomplete_reports_both`, `test_the_scan_job_carries_stopped_and_incomplete_to_the_window`; `Tests/gui/test_window_sources_stopped_incomplete.py` :: `test_stopped_and_incomplete_are_both_shown` | Integration tests: Windows and Ubuntu CI. Window test: Windows CI only |
| Windows junctions (links) are never followed | `test_scan_integrity.py` :: `test_a_real_windows_junction_is_never_followed` | Windows CI only (a real junction) |

All of these passed in the GitHub runs for PR #10's commit `a3801f3`: push run `42469090550` and pull-request run
`42469094096`. Windows: 1180 passed, 4 skipped (the Linux-only tests). Ubuntu: 1080 passed, 104 skipped (window tests
and the Windows-only test). The application code is unchanged since then. The runs for the newest commit are shown on
the PR #10 page (**Checks** tab).

**What this does not show.** These are automated tests. They do **not** mean that you have seen the red
`Scan INCOMPLETE:` message, or the stopped-and-incomplete message, on your own computer. The stopped-and-incomplete
case is automated only, because it also needs an unreadable folder.

### Part D: close (WRITE) (round 2c test 24)

#### W12: close both windows

1. **Do:** close the Workbench with the **X** at its top right, then the Database Manager the same way.
2. **You should see** both close at once, with no error and no black window left behind.
3. **WRITE** in the tracker: `closed cleanly` or what you saw.

---

## 6. At the end: put your round 2c folders back (always do this)

This makes Q-MAP open your round 2c folders again next time.

1. **Do:** open the Database Manager from `D:\Q-MAP_V01\Q-MAP_APP\database_manager.py` (your round 2c program, **not**
   the one in `PR10_Test`), as in round 2c.
2. **Do:** on **Home**, next to **Q-MAP_DATA folder** click **Browse...** and choose `D:\Q-MAP_V01\Q-MAP_DATA`; next to
   **Q-MAP_OUTPUT folder** choose `D:\Q-MAP_V01\Q-MAP_OUTPUT`.
3. **You should see** `Both folders are ready and remembered.` Close the window with **X**.

Keep the whole `PR10_Test` folder until the review is finished. Do not delete it.

---

## 7. What to do next

1. Fill in the tracker's section 1 (date as dd-mmm-yy, Windows and Python versions, commit tested).
2. Right-click `D:\Q-MAP_V01\PR10_Test\Evidence` → **Send to** → **Compressed (zipped) folder**. *(Windows wording; it
   may differ slightly.)* Rename the ZIP to `PR10_Evidence_<dd_Mmm_yy>.zip`, for example `PR10_Evidence_09_Nov_26.zip`.
3. Send the tracker and the ZIP for review (to ChatGPT, as for round 2c).
4. Then:
   - **If every check is PASS:** wait for the review. Merging PR #10 stays your decision afterwards.
   - **If any check is FAIL or NOT SURE:** do not repeat it and do not try to fix anything. Send the files and wait.
   - **If you stopped early (a STOP line):** send what you have, and say at which check you stopped.
   - **If Q-MAP opened the wrong folders:** stop and ask for help before using Q-MAP again.
