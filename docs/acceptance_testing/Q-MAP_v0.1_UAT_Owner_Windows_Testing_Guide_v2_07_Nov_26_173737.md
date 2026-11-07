# Q-MAP v0.1: Owner Windows Testing Guide (version 2)

**07-Nov-26 | Build `a202d43d78ed` | Tracker: `Q-MAP_v0.1_UAT_Owner_Test_Tracker_v2_07_Nov_26_173737.md`**

**Written to `docs/standards/Q-MAP_User_Documentation_Standard.md`.**

This guide is for the Project Owner. It is used for any further owner test of Q-MAP v0.1. Round 2c is complete
and was formally accepted by the Project Owner on 07-Nov-26; the test 21 pop-up calendar was accepted separately
(results review, sections 6 and 8).
The round-2c guide (`Q-MAP_v0.1_UAT_Round2c_Easy_Windows_Testing_Guide_07_Nov_26_063903.md`) is kept unchanged as the
record of what was used on 07-Nov-26.

The tests, their numbers (00-27) and their expected results are those of round 2c. Changes caused by Q-MAP's state after
round 2c are listed in section 7.

---

## 1. How this guide works

Every test is written the same way:

> - **Do:** one action. Do exactly this, nothing more.
> - **You should see:** what happens after the action.
> - **Save:** the evidence to keep, with its exact file name.
> - **If different:** what to do instead.

- Do the actions **in order, one at a time**. Look at the screen before the next action.
- **STOP** means:
  1. stop that test;
  2. do not try to repair anything;
  3. write what you saw in the tracker;
  4. continue where the STOP line says (another test, or the end of the session).
- You never need to read program code, type commands or understand technical messages. If a message appears, take a
  picture of it.

**Evidence types** (the tracker uses the same short names):

| Type | What it is | How to make it | Saved in |
|---|---|---|---|
| **TXT** | The words from a Q-MAP box, pasted into Notepad | Section 3.4 | Evidence folder (section 3.6) |
| **PIC** | A screenshot | Section 3.3 | Evidence folder |
| **FILE** | A copy of a file Q-MAP made (CSV or PDF) | Section 3.5. Copy, never move | Evidence folder |
| **WRITE** | No file; you write the answer in the tracker | - | Tracker |

A text copy is preferred where it is enough, because it keeps the exact words. A picture is asked for only where it
shows something a text copy cannot (a colour, a list row, a window, a screen location). **If a text copy cannot be made,
take a picture instead and give it the same name ending in `.png`.**

---

## 2. Words used in this guide

| Word | Meaning here |
|---|---|
| **Market_Files** | `D:\Q-MAP_V01\Market_Files`, the separate **Q-MAP testing folder**. It holds 11 market files copied for testing. Your private master data is **not** used in any test. |
| **Pattern_Files** | `D:\Q-MAP_V01\Pattern_Files`: six small sample files (`NSE_...csv`) made to test Q-MAP's warnings. |
| **Q-MAP_DATA** | `D:\Q-MAP_V01\Q-MAP_DATA`: Q-MAP's own copy of the data and its records. You never change anything in it. |
| **Q-MAP_OUTPUT** | `D:\Q-MAP_V01\Q-MAP_OUTPUT`: reports and results. You only open or copy files there. |
| **Database Manager** | The Q-MAP window that loads and manages data. Started from `database_manager.py`. |
| **Analytical Workbench** | The Q-MAP window that runs analyses. Started from `analytical_workbench.py`. |
| **Screen buttons** | The buttons at the **top right** of a Q-MAP window. Database Manager: **Home**, **Sources**, **Data Management**, **Datasets and Storage**. Workbench: **Home**, **Run an analysis**. |
| **Section** | A framed area with a bold title, for example **1. Input - folders Q-MAP reads market files from**. |
| **Folder source** | A folder Q-MAP reads files from, listed in **Sources**, section 1. |
| **Scan** | Q-MAP reads the files of the selected folder source (button **SCAN SELECTED FOLDER NOW**). |
| **Dataset** | One prepared set of price bars (one instrument, one timeframe), with a number, for example "dataset 18". |
| **Reject / Restore** | Take a dataset out of use (it is kept, not deleted) / put it back. Both are recorded. |
| **Live Log** | The black box at the bottom of each screen, listing what Q-MAP just did. |
| **Run ID** | The name of one scan or analysis, for example `SCAN_20261107_172216` or `DSUM_20261107_165125`. |
| **Alias registry** | Q-MAP's list of other names for an instrument ("RELIANCE EQ" means RELIANCE). |

---

## 3. Before you begin

### 3.1 Rules that protect your data

1. **Never delete, move, rename or edit** anything in `Q-MAP_DATA`, `Q-MAP_OUTPUT`, `Q-MAP_APP`, `Market_Files` or
   `Pattern_Files`.
2. **Add only the folders this guide names** (tests 19 and 27), and only from inside `D:\Q-MAP_V01` (section 4.2).
3. **Your private master data is never used.** Do not point Q-MAP at it and do not copy files from it for these tests.
4. If Excel or Notepad asks **Save changes?** (or similar), click **Don't Save**.
5. If Windows offers to **Replace** files, click **Skip these files** or **Cancel**, never **Replace**. (Windows wording;
   it may differ slightly.)
6. Do not click these Q-MAP buttons; they are not part of the tests:
   - **Delete Temporary dataset...**, **Move to Temporary**, **Make Permanent**, **DERIVE SELECTED TIMEFRAMES**;
   - **Save answer / correction**, **Add selected names to alias registry**, **Save settings of selected folder**;
   - **LOAD FILES INTO Q-MAP**.
7. The **only** test that changes Q-MAP's records is test 17 (two files rejected and restored at once). Each such
   action is marked in **bold** where it happens.
8. If anything unexpected happens: take a picture, write it down, and **do not repair it**.

### 3.2 What you need

- Your laptop with IDLE (Python 3.12). **Do not install or update anything.**
- About 75 minutes for all tests. You may stop after any test;
  close Q-MAP with the **X** at the top right of each window.
- Notepad (part of Windows). Excel only to look at CSV files.

### 3.3 How to take a picture (PIC)

1. Press **Windows key + Shift + S** together. The screen turns grey.
2. Drag a box around what the **Save** line names. Scroll first if needed.
3. Click the small pop-up at the bottom right. The Snipping Tool opens.
4. Press **Ctrl+S**, open your evidence folder, type the exact file name and click **Save**.
5. Close the Snipping Tool.

If it does not fit on one screen, take two pictures and add `_part1` and `_part2` to the name.
(The Windows wording in steps 3-4 may differ slightly.)

### 3.4 How to make a text copy (TXT)

1. Click once inside the Q-MAP box named in the step.
2. Press **Ctrl+A**. If not all the text turns blue, drag with the mouse from the first to the last line instead.
3. Press **Ctrl+C**.
4. Start **Notepad** (Start menu → type `Notepad`) and press **Ctrl+V**.
5. Press **Ctrl+S**, open your evidence folder, type the exact file name (ending `.txt`) and click **Save**. Close Notepad.

### 3.5 How to copy a file Q-MAP made (FILE)

1. In File Explorer, click the file **once**.
2. Press **Ctrl+C**.
3. Open your evidence folder and press **Ctrl+V**.

The file stays where it was. Never use **Ctrl+X** (cut) and never drag files out of `Q-MAP_OUTPUT`.

### 3.6 The evidence folder and the tracker

1. Press **Windows key + E**. File Explorer opens.
2. In the left panel click **This PC**, double-click **D:**, then double-click **Q-MAP_V01**.
3. Right-click an empty area → **New** → **Folder**. Type `Q-MAP_Test_Evidence_v2` and press **Enter**.
   If that name already exists, use `Q-MAP_Test_Evidence_v2_2`.
4. Make a copy of the tracker for this session and write today's date at the top (tracker section 6).

You should now have an empty folder `D:\Q-MAP_V01\Q-MAP_Test_Evidence_v2`. Every evidence file goes directly into it.

---

## 4. Two skills used several times

### 4.1 Opening the two Q-MAP windows

**Database Manager**
1. Start menu → type `IDLE` → click **IDLE (Python 3.12 ...)**. The IDLE window opens.
2. In IDLE click **File** → **Open...** → go to `D:\Q-MAP_V01\Q-MAP_APP` → open `database_manager.py`.
   A second window with program text opens; you do not need to read it.
3. Press **F5**.
4. **You should see**, after a few seconds, the window **Q-MAP Database Manager - prepare and manage market data**.

**Analytical Workbench**
1. In the **IDLE** window (the first one) click **File** → **Open...** → open `D:\Q-MAP_V01\Q-MAP_APP\analytical_workbench.py`.
2. Press **F5**.
3. **You should see** the window **Q-MAP Analytical Workbench - research on prepared data**.

**If different:**
- If no window opens, or a message appears: take a picture and **STOP** (end the session; go to section 6).
- If a message offers to install packages: do not accept it, take a picture and **STOP** (end the session). The laptop
  already has everything, so this would mean something has changed. (The exact wording of that message was not checked.)

### 4.2 Adding a folder source safely (tests 19 and 27 only)

1. Database Manager → click **Sources** (top right).
2. In section **1. Input - folders Q-MAP reads market files from**, click **Add folder...**.
3. **You should see** a window titled **Choose the folder with your market-data files**. It opens in your user folder.
   **Do not click Select Folder yet.**
4. Click in the address bar at the top of that window, type `D:\Q-MAP_V01` and press **Enter**.
5. Click **once** on the folder named in the test. Its name appears in the **Folder:** box at the bottom.
6. Check that the **Folder:** box shows exactly that name, then click **Select Folder**.
   (Steps 4-6 use Windows wording; it may differ slightly.)
7. **You should see** a new Live Log line `Folder added: NAME (D:\Q-MAP_V01\NAME)`, and the new folder line selected in section 1.
8. **Check before scanning:** the path in brackets starts with `D:\Q-MAP_V01\` and ends with the folder name from the test.

**If the path is wrong:**
1. **Do not scan.**
2. With that line selected, click **Stop using selected folder**. A question **Stop using this folder** appears; click **Yes**.
3. The Live Log shows `Folder no longer scanned (its history and data are kept).` Nothing is deleted.
4. Write in the tracker: `Wrong folder added (path ...), not scanned, stopped using it.`
5. Try steps 2-8 **once** more. If it goes wrong again, **STOP** that test and go to the next one.

---

## 5. The tests

### Part A: Prepare

#### Test 00a: is the tested program in place? (WRITE)

In this test you only **look**.

1. **Do:** open File Explorer at `D:\Q-MAP_V01` (section 3.6, steps 1-2).
2. **Do:** double-click `Q-MAP_APP` → `docs` → `acceptance_testing`.
3. **You should see** the file `Q-MAP_v0.1_UAT_Round2c_Owner_Screen_Checklist_07_Nov_26_050239.md`.

| You see | Then |
|---|---|
| The file is there | Tracker: `In place (checklist file present)`. Go to test 00. |
| The file is not there, or there is no `Q-MAP_APP` | **STOP**. Do not rename, download or move anything. End the session and ask for help (section 6). |

The build is confirmed again in test 23.

#### Test 00: testing folder before testing (W11 part 1) (PIC)

1. **Do:** in File Explorer open `D:\Q-MAP_V01\Market_Files`.
2. **Do:** click **View** → **Details**.
3. **Do:** click once in the address bar at the top. It shows the full path `D:\Q-MAP_V01\Market_Files`.
4. **You should see** 11 files with **Name**, **Date modified** and **Size**, and "11 items" at the bottom left.
5. **Save:** PIC `00_Original_Files_Before.png` of the whole File Explorer window: the address bar, the file list and
   the item count. This proves the starting state; test 26 is compared with it.

Do not open, copy or move these files now.

#### Test 00b: Python version (WRITE)

1. **Do:** start IDLE (section 4.1, step 1).
2. **You should see** a first line such as `Python 3.12.10 (tags/v3.12.10:...) [MSC v.1943 64 bit (AMD64)] on win32`.
3. **Tracker:** copy that line into the session details.

### Part B: Start Q-MAP

#### Test 01: Database Manager and folders (V1, V2) (PIC x 2)

1. **Do:** open Database Manager (section 4.1).
2. **You should see** the **Home** screen with the section **Your folders (remembered between sessions, shared by both Q-MAP applications)**.
3. **Check:** the **Q-MAP_DATA folder** box reads `D:\Q-MAP_V01\Q-MAP_DATA` and the **Q-MAP_OUTPUT folder** box reads
   `D:\Q-MAP_V01\Q-MAP_OUTPUT`.
   - **If a box is different:** click **Browse...** next to it, go to `D:\Q-MAP_V01`, click the folder once, then click
     **Select Folder**.
4. **You should see**, under each box in green, `OK - this folder can be used.`, and then `Both folders are ready and remembered.`
5. **Save:** PIC `01a_Database_Manager_Folders.png` (both boxes and the green lines).
6. **Do:** scroll down the Home screen.
7. **You should see** **READY** (green) next to **Sources (automatic loading)**, **Data Management** and **Datasets and Storage**.
8. **Save:** PIC `01b_Database_Manager_Ready.png`.

**If different:** a red message under a folder box: picture, **STOP** (end the session).

#### Test 02: Analytical Workbench home (V3) (PIC x 2)

1. **Do:** open the Analytical Workbench (section 4.1).
2. **You should see** the same two folders with green `OK - this folder can be used.`, and **READY** next to
   **Dataset Summary** and **MA Research: MA Affinity (QLOPB)**.
3. **Save:** PIC `02a_Workbench_Home.png`.
4. **Do:** scroll down to **Market Intelligence (MIQP)**.
5. **You should see** **COMING SOON** next to it.
6. **Save:** PIC `02b_Workbench_MIQP.png`.

Keep both Q-MAP windows open from now on. Switch between them with the Windows taskbar.

### Part C: Warnings shown for files (Database Manager → Sources)

**How to show one file's details** (tests 03-09 and 13):
1. Database Manager → click **Sources** (top right).
2. In section **1. Input - folders Q-MAP reads market files from**, click the folder line named in the test (column
   **Name**: `Market_Files` or `Pattern_Files`).
3. In section **2. Output - files found in the selected folder**, click the file named in the test (column **File**).
4. The box **under** the file list shows that file's details.

The details box is read only; nothing is changed by looking. For each of tests 03-09 the evidence is the **text copy of
that details box** (TXT). No picture is needed.

#### Test 03: OLAELEC (W2) (TXT)

1. **Do:** show the details of `OLAELEC.xlsx` in `Market_Files`.
2. **You should see:**
   - `Detected timeframe: 1 minute`
   - `Status: Accepted by default`
   - `Quality warnings recorded for dataset 11:`
   - `WARNING: Some dates/times have more than one different value`

   Other warnings, such as "Rows were not in date order", are normal for this file.
3. **Save:** TXT `03_OLAELEC_Details.txt`.

#### Tests 04-08: the five pattern files (W14-W17) (TXT each)

**Do:** click the `Pattern_Files` folder line, then each file in turn.

| Test | File | Must be in the details box | Must **not** be in it | Save |
|---|---|---|---|---|
| 04 (W14) | `NSE_RANDOMGAPS.csv` | `WARNING: Some days have fewer bars than usual` | any line containing "bar interval" | `04_RandomGaps.txt` |
| 05 (W15) | `NSE_EVERYOTHER.csv` | `WARNING: Part of the file may have another bar interval`; `source rows 1126-1163`; `cannot show whether`; `Detected timeframe: 5 minutes` | - (it also shows "Long gaps between dates" and "fewer bars"; that is normal) | `05_EveryOther.txt` |
| 06 (W16) | `NSE_GENUINE3M.csv` | `WARNING: Part of the file has another bar interval`; `3 minute(s)` | - | `06_Genuine3M.txt` |
| 07 (W16) | `NSE_DAILY0000.csv` | `WARNING: Part of the file has another bar interval`; `outside the times of the intraday bars` | - | `07_Daily0000.txt` |
| 08 (W17) | `NSE_DAILY0915.csv` | `WARNING: Part of the file may have another bar interval`; `a time the intraday bars also use` | - | `08_Daily0915.txt` |

"**has**" means Q-MAP is certain; "**may have**" means it cannot be sure.

#### Test 09: SPARSE (W18) (TXT)

1. **Do:** show the details of `NSE_SPARSE.csv` in `Pattern_Files`.
2. **You should see** `WARNING: Long gaps between dates` with `2025-04-04 -> 2025-04-14` (04-Apr-25 to 14-Apr-25),
   `WARNING: Some days have fewer bars than usual`, and **no** line containing "bar interval".
3. **Save:** TXT `09_Sparse_File_Details.txt`.

#### Test 10: scan report of the pattern files (W18) (PIC)

1. **Do:** in File Explorer open `D:\Q-MAP_V01\Q-MAP_OUTPUT\Data_Management\SCAN_20261106_174124`.
2. **You should see** a file whose name starts with `Scan_Report_`, and several files starting with `issues_event`.
3. **Do:** right-click the `Scan_Report_...csv` file → **Open with** → **Notepad** (or Excel).
4. **You should see** `Pattern_Files` near the top, and the six files `NSE_DAILY0000.csv`, `NSE_DAILY0915.csv`,
   `NSE_EVERYOTHER.csv`, `NSE_GENUINE3M.csv`, `NSE_RANDOMGAPS.csv` and `NSE_SPARSE.csv`, each with `Imported`.
5. **Save:** PIC `10b_Pattern_Scan_Report.png`.
6. **Do:** close Notepad or Excel. If asked to save, click **Don't Save**.

(`10a_Pattern_Scan_Folder.png` from round 2c is no longer needed: the report itself shows the result.)

#### Test 11: a dataset with warnings is still usable (W18) (TXT)

1. **Do:** Workbench → click **Run an analysis** (top right).
2. **Do:** in section **1. Input - analysis and prepared datasets**, open the **Analysis:** list and choose **Dataset Summary**.
3. **Do:** in the dataset list click the line **30 NSE:EVERYOTHER 5 minutes**.
4. **Do:** click **Check readiness (nothing is saved)**.
5. **You should see**, in the box **Readiness of the selected data**, `READY - every requirement is met.` and a line
   starting `NOTE Validated with warnings`.
6. **Save:** TXT of that box `11_Workbench_Warning.txt`.

Do not click **RUN ANALYSIS** here.

### Part D: Repeat scan, RELIANCE, reject and restore

#### Test 12: repeat scan of Market_Files (A4) (TXT)

1. **Do:** Database Manager → **Sources** → click the `Market_Files` folder line in section 1.
2. **Do:** in section **3. Options - scan, review and correct**, click **SCAN SELECTED FOLDER NOW**.
3. **Wait** until **Stage:** under **Progress / Status** shows **Finished** (a few seconds).
4. **You should see**, in green, `Scan finished (10 unchanged (imported earlier), 1 unchanged (rejected earlier)). Run SCAN_...`.
   In the Live Log there is one line per file: 10 start with `Unchanged (imported earlier)` (5PAISA, RIVERUSD, BANKNIFTY,
   OLAELEC, UJJIVAN, VERANDA, three ICICIBANK files, RELIANCE_EQ) and `AKZOINDIA.parquet` starts with
   `Unchanged (rejected earlier)`.
   For `RELIANCE_EQ.csv` the line ends "...Imported. 1 dataset(s) created". That repeats its earlier result; it is not a new import.
5. **Save:** TXT of the Live Log `12_Repeat_Scan_Log.txt`.

**If different:** a file shows `Imported` or `Rejected` without the word "Unchanged": take a picture, mark **FAIL**,
continue with test 13.

This scan only reads; it changes no data.

#### Test 13: RELIANCE name (W5) (TXT)

1. **Do:** show the details of `RELIANCE_EQ.csv` in `Market_Files`.
2. **You should see** `Instrument: NSE:RELIANCE (alias)` and `Dataset(s): 18`.
3. **Save:** TXT `13_Reliance_After_Scan.txt`.

#### Test 14: alias registry (W5) (PIC)

1. **Do:** in section 3 click **Open alias registry folder**. A File Explorer window opens.
2. **Do:** right-click `Instrument_Aliases.csv` → **Open with** → **Notepad**.
3. **You should see** the line `RELIANCE,RELIANCE EQ`.
4. **Save:** PIC `14_Alias_Registry.png`.
5. **Do:** close Notepad. If asked to save, click **Don't Save**. This file is part of Q-MAP's records.

#### Test 15: the two RELIANCE datasets (W5) (PIC x 2; look only)

1. **Do:** Database Manager → click **Datasets and Storage** (top right).
2. **Do:** in the dataset list (section **1. Input - prepared datasets in the Data Registry**) click the line **13 NSE:RELIANCE_EQ Daily**.
3. **You should see**, in the box **Details of the selected dataset:** under the list: `Bars: 7746   From 07-Nov-94 to 30-Dec-25`, `State: Rejected by you`
   and `Original file(s): RELIANCE_EQ.csv (preserved unchanged)`.
4. **Save:** PIC `15a_Reliance_EQ_Details.png` (the lines Bars, State and Original file(s)).
5. **Do:** click the line **18 NSE:RELIANCE Daily**.
6. **You should see** the same Bars, dates and Original file(s), and in the list the **State** column **Active**.
7. **Save:** PIC `15b_Reliance_Details.png`.

**If different:** dataset 13 is not "Rejected by you", or dataset 18 is not Active: picture, write it down, do **not**
click **Reject (reversible)** or **Restore**, and go to test 17.

#### Test 16: the RELIANCE duplicate decision (W5) (WRITE)

This decision was taken on 07-Nov-26 (dataset 13 rejected, reason `duplicate after alias correction (W5)`). **Do not
click anything.** If test 15 matched, write: `Already rejected on 07-Nov-26; confirmed in test 15.`

#### Test 17: reject and restore two files (W6, W7) (PIC x 2)

**This test changes Q-MAP's records, and the change is undone in the same test.** Reject takes the two datasets out of
use; **Restore selected** puts them back. Nothing is deleted. Both actions complete at once; no confirmation question appears.

1. **Do:** Database Manager → **Sources** → click the `Market_Files` folder line.
2. **Do:** in the file list click `VERANDA_1min.csv`, then hold **Ctrl** and click `5PAISA_30min.csv`. Both lines are highlighted.
3. **Do:** click in the **Reason (recorded):** box (section 3) and type `UAT retest W6`.
4. **Do:** click **Reject selected**.
5. **You should see**:
   - under Progress / Status, `Rejected 2 dataset(s). They are kept unchanged and no longer offered to analyses; Restore undoes it.`;
   - in the file list, **both** rows with Result **Rejected by you**.
6. **Save:** PIC `17a_Files_Rejected.png` showing the **two rows** and the message (use `_part1` / `_part2` if needed).
7. **Do:** keep both rows selected (if not, select them again as in step 2) and click **Restore selected**.
8. **You should see**:
   - `Restored 2 dataset(s). They are offered to analyses again.`;
   - **both** rows with **Available again (restored by you)**.
9. **Save:** PIC `17b_Files_Restored.png` showing the two rows and the message.

**If different:**
- If after step 4 a row does not show "Rejected by you": take the picture and continue with step 7.
- If after step 7 a row does not show "Available again (restored by you)": **STOP**.
  - Do not click anything else for these files.
  - Mark test 17 **FAIL** and test 18 **NOT TESTED**, and write which file shows what.
  - Go to test 19. Nothing is lost; the datasets can be restored with help.

#### Test 18: Workbench list after restore (W7) (PIC)

1. **Do:** Workbench → **Run an analysis** → click **Refresh** (section 1).
2. **You should see** VERANDA, 5PAISA and **NSE:RELIANCE** (dataset 18) in the list, and **NSE:RELIANCE_EQ** (dataset 13) **not** in it.
3. **Save:** PIC `18_Workbench_After_Restore.png` (`_part1`, `_part2`, ... if the list needs scrolling).

### Part E: The window stays usable during a scan

#### Test 19: Stop scan (W8) (PIC)

**Prepare the test folder** (File Explorer only; this copies, nothing is moved):

```text
D:\Q-MAP_V01\W8_Retest\
    Copy_1\   (all 11 files from Market_Files)
    Copy_2\   (all 11 files again)
    Copy_3\   (all 11 files again)
```

1. In `D:\Q-MAP_V01`, make a new folder `W8_Retest`. If that name exists, use `W8_Retest_2` and write the name in the tracker.
2. Open `W8_Retest` and make three folders in it: `Copy_1`, `Copy_2`, `Copy_3`.
3. Open `D:\Q-MAP_V01\Market_Files`, press **Ctrl+A**, then **Ctrl+C**.
4. Open `Copy_1` and press **Ctrl+V**. Wait until the copy ends.
5. Repeat step 4 for `Copy_2` and `Copy_3`. Because each copy goes into its own empty folder, Windows never asks to
   replace files. (If it does ask, click **Skip these files**.)

You now have 33 files in three sub-folders. Separate folders are needed because pasting the same files into one folder
makes Windows ask to replace them, and no extra copies are made. That is what happened in round 2c.

**Scan and stop:**
1. Database Manager → **Sources**. In section 1, tick **Include sub-folders**. (This applies only to the folder added
   next. Do not click **Save settings of selected folder**.)
2. Add the folder `W8_Retest` as in section 4.2, and check the path in the Live Log.
3. With the `W8_Retest` line selected, click **SCAN SELECTED FOLDER NOW**.
4. **Immediately** click **Stop scan** (next to it).
5. Scroll the file list up and down with the mouse wheel.

**You should see:**
- the window responds while you scroll;
- under Progress / Status, the message `Stopped by you after N file(s); M file(s) not processed (listed in the scan
  report). Work already done is kept.`

**Known display fault (minor, to be corrected later, OW-45):** the counter **Files done:** may show all files as done
(for example `33 / 33`) and the bar may be full. The message is correct; the counter is not.

**Save:** PIC `19_Stop_Scan.png` (Progress / Status with the message).

**If the scan finishes before you can click Stop scan:** one try only. Do not repeat it and do not add more files or
folders. Mark **NOT TESTED**: `scan finished too quickly to stop`. This is not a failure. Go to test 20.

**If the window freezes or an error appears:** picture, mark **FAIL**, and go to test 20 if Q-MAP still works.

### Part F: Analyses (Analytical Workbench)

Two different analyses are used. **Dataset Summary** gives counts and first/last values (tests 11, 21, 22).
**MA Affinity (QLOPB)** is the moving-average research (tests 20, 23). Choose the one named in each test.

#### Test 20: MA Affinity settings (V6) (PIC)

1. **Do:** Workbench → **Run an analysis** → **Analysis:** list → **MA Affinity (QLOPB)**.
2. **You should see**, in section **3. Options - parameters**:
   - **MA types:** `SMA`
   - **MA start:** `10`
   - **MA end:** `250`
   - **Forward windows:** `5,10,20,50`
   - a grey help line under each.
3. **Save:** PIC `20_MA_Affinity_Settings.png`.

Do not change any value.

#### Test 21: Dataset Summary of ICICIBANK, with the calendar (A5) (PIC x 2 + FILE; PIC 21b optional)

**What this test checks:**
- that the **Calendar...** button works;
- that **Dataset Summary** (not MA Affinity) gives the expected figures for the right dates.

Choosing a date in the calendar only fills the date box; it never starts an analysis. Nothing runs until you click
**RUN ANALYSIS**.

**Status:** round-2c test 21 was completed on 07-Nov-26 (PASS), and the Project Owner has checked and accepted the
pop-up calendar. This procedure is for a future owner test only; it is not a request to repeat test 21.

**Before you start:**
1. **Do:** Workbench → **Run an analysis** → **Analysis:** list → **Dataset Summary**.
2. **Do:** in the dataset list click **7 NSE:ICICIBANK Daily** (Bars 7166). Only this line must be selected; the counter
   shows `[1 selected of ...]`.

**Part 1: the calendar (sets the start date)**

1. **Do:** click in the **Start date:** box (section **3. Options - parameters**) and type `01-Jan-98`.
2. **You should see**, next to the box in **green**, `= 01-Jan-1998`. Typing first makes the calendar open at
   January 1998; with an empty box it opens at today's month.
3. **Do:** click **Calendar...** next to the **Start date:** box.
4. **You should see** a small window **Choose a date** with **January 1998** at the top and day **1** shown pressed in.
   At the top: **<<** and **>>** (one year back or forward), **<** and **>** (one month). At the bottom: **Today**,
   **Clear** and **Close**.
5. **Save:** PIC `21c_Calendar_January_1998.png` showing the small window.
6. **Do:** click **>** once. **You should see** **February 1998**.
7. **Do:** click **<** once. **You should see** **January 1998**.
8. **Do:** click **>>** once. **You should see** **January 1999**.
9. **Do:** click **<<** once. **You should see** **January 1998**.
10. **Do:** click the day **2**.
11. **You should see** the small window close by itself. The **Start date:** box shows `02-Jan-98` and, in green,
    `= 02-Jan-1998`.

Do not click **Today** or **Clear**: **Today** puts today's date in the box and **Clear** empties it. If you clicked one
by mistake, nothing has run: click in the **Start date:** box, delete its text (Backspace) and type `02-Jan-98`.

**Part 2: the end date**

1. **Do:** click in the **End date:** box and type `02-Nov-26`.
2. **You should see**, in green, `= 02-Nov-2026`.
3. **Save:** PIC `21a_Dates_Before_Run.png` showing both boxes and both green lines.

**If different (calendar):** the small window does not open, is not at **January 1998**, or a button or a day does
nothing:
1. Click **Close** (or the X of the small window) if it is open. Nothing has run.
2. Click in the **Start date:** box, delete its text and type `02-Jan-98`.
3. Check the green `= 02-Jan-1998`.
4. Write in the tracker what the calendar did (ready-to-copy note in the tracker), then continue with Part 2.

**If different (dates):** a red line, or a green line with another date: click in that box, delete its text, type the
date again and check. If it is still wrong, mark **NOT SURE** and go to test 22 **without** clicking **RUN ANALYSIS**.

**Part 3: the summary**

Click **RUN ANALYSIS** only when the two green lines say exactly `= 02-Jan-1998` and `= 02-Nov-2026`.
1. **Do:** click **RUN ANALYSIS**.
2. **Wait** until the Live Log shows `... completed: 1 output file(s).`
3. **Do:** click **Open Output Folder**. A File Explorer window opens on the run's folder `DSUM_...`.
4. **Do:** copy the file `Dataset_Summary_....csv` into your evidence folder (section 3.5), then open the **copy** in
   Excel or Notepad.
5. **You should see** Bars `7166`, First bar `02-Jan-98`, Last bar `02-Nov-26`, First close `7.86`, Last close `1387.4`.
6. **Save:** FILE `Dataset_Summary_dd_Mmm_yy_hhmmss.csv` (keep the name Q-MAP gave it). The CSV is the evidence of the
   figures. PIC `21b_ICICIBANK_Summary.png` is optional.

**If you ran with a wrong date:** do not delete that run. Write its Run ID (from the Live Log) in the tracker, then run
again with the right dates.

#### Test 22: output folder (A7) (PIC)

1. **You should see**, in the File Explorer window from test 21, the address bar ending
   `Q-MAP_OUTPUT > Research_Reports > DSUM_...`, with the CSV, `run_log`, `run_manifest` and `Run_Metadata_...` files.
2. **Save:** PIC `22_Output_Folder.png` with the address bar.

#### Test 23: build in the PDF report (PIC + FILE + WRITE)

1. **Do:** Workbench → **Run an analysis** → **Analysis:** list → **MA Affinity (QLOPB)** (not Dataset Summary).
2. **Do:** click **7 NSE:ICICIBANK Daily** only. Leave **Start date:** and **End date:** empty and every other value unchanged.
3. **Do:** click **RUN ANALYSIS**.
4. **Wait** about 30 seconds, until the Live Log shows `... completed: 9 output file(s).`
5. **Do:** click **Open Output Folder** and double-click the file `QLOPB_MA_Affinity_Report_....pdf`.
6. **You should see**, under the title "QLOPB - MA Affinity research report", the text
   `Q-MAP build: qmap 0.1.0rc1 / c2 build a202d43d78ed`.
7. **Save:**
   - PIC `23_Build_Fingerprint_PDF.png`, which makes the build line easy to see;
   - FILE: a copy of the PDF (section 3.5), which holds the full report and the build line.
8. **Tracker:** copy the build text into the session details.
9. **Do:** close the PDF reader.

### Part G: Close, restart, testing folder (at the end)

#### Test 24: close (W12) (WRITE)

1. **Do:** click the **X** (top right) of the Workbench window, then of the Database Manager window.
2. **You should see** both windows close, with no message and no empty window left behind.
3. **Tracker:** write `Both closed, no message.`

A picture is needed **only** if a message or an empty window appears: PIC `24_Closed_Desktop.png`.

#### Test 25: restart and rescan (V14) (PIC + TXT)

1. **Do:** open both windows again (section 4.1).
2. **Do:** Workbench → **Run an analysis**.
3. **You should see**, in section **2. Output - where results are saved**, **Last run folder:** showing the MA
   Affinity run of test 23 (`MAAF_...`).
4. **Save:** PIC `25a_Last_Run_Folder.png`.
5. **Do:** Database Manager → **Sources** → click the `Market_Files` line → **SCAN SELECTED FOLDER NOW**, and wait for **Finished**.
6. **You should see** `10 unchanged (imported earlier), 1 unchanged (rejected earlier)`. VERANDA and 5PAISA now show
   `Unchanged (imported earlier)`, no longer "Available again".
7. **Save:** TXT of the Live Log `25_Restart_Rescan_Log.txt`.

#### Test 26: testing folder after testing (W11 part 1) (PIC)

1. **Do:** open `D:\Q-MAP_V01\Market_Files` → **View** → **Details** → click in the address bar.
2. **You should see** the same 11 files with the same names, sizes and Date modified as in `00_Original_Files_Before.png`.
3. **Save:** PIC `26_Original_Files_After.png` (address bar, file list, item count).

**If different:** picture, mark **FAIL**, write which file differs. Do not change anything.

#### Test 27: content check of the testing files (W11 part 2) (TXT)

1. In `D:\Q-MAP_V01`, make a new folder `W11_Retest` (or `W11_Retest_2` if it exists).
2. Open `D:\Q-MAP_V01\Market_Files`, press **Ctrl+A**, then **Ctrl+C**. Open `W11_Retest` and press **Ctrl+V** once.
3. Database Manager → **Sources**. Make sure **Include sub-folders** is **not** ticked.
4. Add the folder `W11_Retest` as in section 4.2.
5. Click **SCAN SELECTED FOLDER NOW** and wait for **Finished**.
6. **You should see** 11 files: 10 with `Already loaded` and `AKZOINDIA.parquet` with `Rejected earlier (unchanged)`.
   **No** file shows `Imported`. This shows that Q-MAP holds exactly the same content as the testing files.
7. **Save:** TXT of the Live Log `27_Original_Content_Check.txt`.
8. **Do:** close both Q-MAP windows with **X**.

**If different:** a file shows `Imported` or `changed`: picture, mark **FAIL**, write the file name, **STOP** (go to section 6).

---

## 6. What to do next

**After the last test you did:**
1. In the tracker, give **every** test you did a status: PASS, PASS WITH OBSERVATION, FAIL, NOT TESTED or NOT SURE.
2. Fill in the session details and the notes. Leave "Project Owner's acceptance decision" empty.
3. Check the evidence folder against the tracker's file list (tracker section 4).
4. Right-click the evidence folder → **Send to** → **Compressed (zipped) folder**.
5. Send the ZIP and the tracker to ChatGPT for review.

**Then:**

| Situation | What to do |
|---|---|
| Every test PASS | Send the files and **wait** for the review. Do not merge anything. |
| Any FAIL, NOT SURE or STOP | Do **not** repeat the test. Send the files and **wait**. Claude looks into it after the review. |
| Q-MAP shows a message you do not understand, or will not start | **Stop** testing, take a picture, and **ask for help**. Do not reinstall or change anything. |
| You were interrupted | Close Q-MAP with **X**. **Continue** later from the next test; earlier results stay valid. |

Completing the tests is not acceptance and not approval to merge. The evidence is reviewed first; the decision is the
Project Owner's.

---

## 7. What changed since round 2c, and why

**Changed because Q-MAP's state changed** (the expected rules are the same as in round 2c):
- **Tests 15 and 16** are look-only. NSE:RELIANCE_EQ (dataset 13) was rejected on 07-Nov-26.
- **Tests 19 and 27** use new folder names (`W8_Retest`, `W11_Retest`), because `W8_Round2c` and `W11_Check_2c` are
  already folder sources.
- **Tests 00, 26 and 27** name the testing folder `D:\Q-MAP_V01\Market_Files` and its 11 files. In round 2c they used
  this folder too. The private master data is not part of any test.

**Changed for clarity, from the round-2c experience:**
- Screens, sections, buttons and messages are named as Q-MAP shows them; words are explained in section 2.
- Every action is one step, with what to see and what to do if different.
- Test 19 uses three sub-folders and **Include sub-folders**. In round 2c, pasting into one folder produced only 10 files.
- Test 21 checks the calendar (`01-Jan-98`, then the calendar, then day 2), and the analysis runs only after both green
  lines are right. Its new picture is `21c_Calendar_January_1998.png`.
- Evidence is asked for only where it proves something:
  - text copies for words: tests 03-09, 11, 12, 13, 25 and 27;
  - pictures where a picture shows more: folders, rows, windows and the PDF line;
  - CSV and PDF copies of the results.
- Pictures dropped:
  - `10a` (the report shows the result);
  - `12a`/`12b` and `25b` (the Live Log text copy shows the same);
  - `24` (only if something goes wrong);
  - `21b` is optional (the CSV is the evidence).
- The Stop scan counter fault is explained (OW-45).
- An offer to install packages, a missing checklist file, or a wrong folder path leads to a clear STOP.
- Section 6 says what to do next and when to wait, continue, stop or ask for help.

**Not checked on a Windows screen in this session:** the wording of Windows' own dialogs (folder picker, Snipping
Tool, replace-files question, File Explorer item count) and of the package-install message. They are marked in the text.
Every Q-MAP label, path, message and value above was checked against the program code and the round-2c evidence.

Details: `Q-MAP_v0.1_UAT_Round2c_Owner_Results_Review_07_Nov_26_173737.md`.
