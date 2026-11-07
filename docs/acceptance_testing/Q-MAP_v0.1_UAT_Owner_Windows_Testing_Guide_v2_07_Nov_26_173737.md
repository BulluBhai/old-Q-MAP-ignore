# Q-MAP v0.1: Owner Windows Testing Guide (version 2)

**07-Nov-26 | Build `a202d43d78ed` | Use with `Q-MAP_v0.1_UAT_Owner_Test_Tracker_v2_07_Nov_26_173737.md`**

This guide replaces, for any future owner test, the round-2c easy guide
(`Q-MAP_v0.1_UAT_Round2c_Easy_Windows_Testing_Guide_07_Nov_26_063903.md`, kept unchanged). It is rewritten from the
round-2c owner test of 07-Nov-26. Everything that was unclear then is now spelled out, and screen names are as Q-MAP
shows them. The tests, their numbers (00-27) and their expected results are the same as in round 2c, except where
Q-MAP's state has changed since then (listed in section 7, not hidden).

---

## 1. Before you read further: how this guide works

Each test has the same parts:

> **Do:** one action. Do exactly this, nothing more.
> **You should see:** what happens after the action.
> **Save:** what to keep as evidence and its exact file name.
> **If different:** what to do when it does not look like this.

- Do the actions **in order, one at a time**. After each action, look at the screen before you do the next one.
- When a line says **STOP**:
  - stop that test;
  - do not try to repair anything;
  - write what you saw in the tracker;
  - then go to the test named in the STOP line, or end the session if it says so.
- You never need to read program code, type commands or understand error messages. If a message appears, take a
  picture of it.

### Evidence types

| Type | What it means | How to make it |
|---|---|---|
| **PICTURE (.png)** | A screenshot | Section 3.3 |
| **TEXT COPY (.txt)** | The words from a Q-MAP box, pasted into Notepad | Section 3.4 |
| **FILE COPY (.csv / .pdf)** | A copy of a file Q-MAP made | Section 3.5. **Copy, never move.** |
| **WRITE DOWN** | No file; write the answer in the tracker | - |

Every file name in this guide is exact. Use it as written, including capital letters and the underscore `_`.

---

## 2. Words used in this guide

| Word | What it means here |
|---|---|
| **Q-MAP_DATA** | The folder where Q-MAP keeps its own copy of your data and its records. You never change anything in it. |
| **Q-MAP_OUTPUT** | The folder where Q-MAP writes reports and results. You only open files there to look, or copy them. |
| **Database Manager** | The Q-MAP window that loads and manages market data. Started from `database_manager.py`. |
| **Analytical Workbench** | The Q-MAP window that runs analyses. Started from `analytical_workbench.py`. |
| **Screen buttons** | The buttons at the **top right** of a Q-MAP window that switch screens. Database Manager: **Home**, **Sources**, **Data Management**, **Datasets and Storage**. Workbench: **Home**, **Run an analysis**. |
| **Section** | A framed area of a screen with a bold title, for example **"1. Input - folders Q-MAP reads market files from"**. |
| **Folder source** | A folder that Q-MAP reads market files from. Listed in Sources, section 1. |
| **Scan** | Q-MAP reads the files in the selected folder source. Button **SCAN SELECTED FOLDER NOW**. |
| **Dataset** | One prepared set of price bars (one instrument, one timeframe), with a number, for example "dataset 18". |
| **Reject / Restore** | Taking a dataset out of use (it is kept, not deleted) / putting it back. Both are recorded. |
| **Live Log** | The black box at the bottom of each screen. It lists what Q-MAP just did. |
| **Run ID** | The name of one scan or analysis, for example `SCAN_20261107_172216` or `DSUM_20261107_165125`. |
| **Alias registry** | Q-MAP's list of other names for an instrument (for example "RELIANCE EQ" means RELIANCE). |
| **Originals folder** | The folder where **you** keep your own master copies of the market files, **outside** `D:\Q-MAP_V01`. Q-MAP must never change them. |
| **Pattern files** | Six small sample files (`NSE_...csv`) made to test Q-MAP's warnings. |

---

## 3. Before you begin

### 3.1 Rules that protect your data

1. **Never delete, move, rename or edit** any file in `Q-MAP_DATA`, `Q-MAP_OUTPUT`, `Q-MAP_APP`, `Market_Files`,
   `Pattern_Files` or your originals folder. The only renames allowed are those in test 00a.
2. **Add only the folders this guide names** (in tests 19 and 27). Never add your Desktop, Documents, Downloads, OneDrive or
   any other folder. Section 4.2 shows how to choose the right one.
3. If Excel or Notepad asks **"Save changes?"**, click **Don't Save**.
4. Never click **Delete Temporary dataset...**, **Move to Temporary**, **Make Permanent**, **DERIVE SELECTED TIMEFRAMES**,
   **Save answer / correction**, **Add selected names to alias registry**, or **LOAD FILES INTO Q-MAP**. They are not
   part of these tests.
5. The **only** actions that change your Q-MAP records are in test 17 (reject and restore two files at once). Test 16 is
   a look-only check now (section 7).
6. If anything unexpected happens: take a picture, write it down, and **do not repair it**. Ask ChatGPT or Claude.

### 3.2 What you need

- Your laptop, with IDLE (Python 3.12) already installed. **Do not install or update anything.**
- About 75 minutes. You may stop after any test. Close Q-MAP with the **X** button at the top right if you stop.
- Notepad (part of Windows). Excel is only for looking at CSV files.

### 3.3 How to take a picture

1. Press the **Windows key + Shift + S** together. The screen turns grey.
2. Drag a box around the area named in the **Save** line. Include everything the Save line asks for (scroll first if needed).
3. A small pop-up appears at the bottom right. Click it. The **Snipping Tool** opens with your picture.
4. Press **Ctrl+S**. A Save window opens.
5. Go to your evidence folder (section 3.6), type the exact file name, and click **Save**.
6. Close the Snipping Tool.

If the area does not fit on one screen, take two pictures and add `_part1`, `_part2` to the name
(for example `18_Workbench_After_Restore_part1.png`).

### 3.4 How to make a text copy (where the guide asks for one)

1. Click once inside the Q-MAP box named in the step (for example the details box, or the Live Log).
2. Press **Ctrl+A** to select all its text. If not everything turns blue, drag with the mouse from the first to the last
   line instead.
3. Press **Ctrl+C**.
4. Open **Notepad** (Start menu → type `Notepad`). Press **Ctrl+V**.
5. Press **Ctrl+S**, go to your evidence folder, type the exact file name (ending in `.txt`), click **Save**. Close Notepad.

### 3.5 How to copy a file Q-MAP made

1. In File Explorer, click the file **once**.
2. Press **Ctrl+C**.
3. Open your evidence folder and press **Ctrl+V**.

The original stays where it was. Never use Cut (Ctrl+X) and never drag files out of `Q-MAP_OUTPUT`.

### 3.6 Make the evidence folder

1. Open **File Explorer** (Windows key + E).
2. In the left panel, click **This PC**, then double-click **D:**, then double-click **Q-MAP_V01**.
3. Right-click an empty space → **New** → **Folder**. Type `Q-MAP_Test_Evidence_v2` and press **Enter**.
   If that name already exists, use `Q-MAP_Test_Evidence_v2_2`.
4. Make a copy of the tracker for this session (section 6 of the tracker says how). Write the date at the top.

---

## 4. Two skills you need several times

### 4.1 Opening the two Q-MAP windows

**Database Manager**
1. Start menu → type `IDLE` → click **IDLE (Python 3.12 ...)**. The IDLE window opens.
2. In IDLE click **File** → **Open...**. Go to `D:\Q-MAP_V01\Q-MAP_APP` and open `database_manager.py`.
   A second window with program text opens. You do not need to read it.
3. Press **F5**. After a few seconds the window **Q-MAP Database Manager - prepare and manage market data** opens.

**Analytical Workbench**
1. In the **IDLE** window (the first one), click **File** → **Open...** → `D:\Q-MAP_V01\Q-MAP_APP\analytical_workbench.py`.
2. Press **F5**. The window **Q-MAP Analytical Workbench - research on prepared data** opens.

**If different:** if an error message appears or no window opens, take a picture and **STOP** (end the session; tell ChatGPT).
If Q-MAP offers to install missing packages, click **No**, take a picture and **STOP**: the laptop already has them, so
this would mean something has changed.

### 4.2 Adding a folder source safely (tests 19 and 27 only)

1. Database Manager → click **Sources** (top right).
2. In section **"1. Input - folders Q-MAP reads market files from"**, click **Add folder...**.
3. **You should see:** a window **"Choose the folder with your market-data files"**. It usually opens in your user folder.
   **Do not click Select Folder yet.**
4. Click in the **address bar** at the top of that window, type `D:\Q-MAP_V01` and press **Enter**.
5. Click **once** on the folder named in the test (for example `W8_Retest`). Its name appears in the **Folder:** box at the bottom.
6. Check that the **Folder:** box shows exactly the name from the test. Then click **Select Folder**.
7. **You should see** a new line in the Live Log: `Folder added: W8_Retest (D:\Q-MAP_V01\W8_Retest)`, and the new
   folder line selected in section 1.
8. **Check before scanning:** the path in brackets must start with `D:\Q-MAP_V01\` and end with the folder name from the test.

**If different (wrong folder added):**
1. **Do not scan.**
2. Keep that line selected in section 1 and click **Stop using selected folder** → **Yes**. The Live Log shows
   "Folder no longer scanned (its history and data are kept)". Nothing is deleted.
3. Write in the tracker: `Wrong folder added by mistake (path ...), not scanned, stopped using it.`
4. Try steps 2-8 **once** more. If it goes wrong again, **STOP** that test.

**Never scan a folder whose path is not the one in the test.** (In round 2c a personal folder was added and scanned by
mistake. Q-MAP did not copy those files, but it recorded their names. See the review, finding F1.)

---

## 5. The tests

### Part A: Prepare

#### Test 00a: Is the tested program in place? (WRITE DOWN)

You only **look** in this test. Do not rename anything unless the table says so.

**Do:** open File Explorer at `D:\Q-MAP_V01` (section 3.6, steps 1-2). Note which of `Q-MAP_APP` and `Q-MAP_APP_round2` you see.
**Do:** if `Q-MAP_APP` exists, double-click it → `docs` → `acceptance_testing`. Look for the file
`Q-MAP_v0.1_UAT_Round2c_Owner_Screen_Checklist_07_Nov_26_050239.md` ("the checklist file").

| You see | Checklist file in `Q-MAP_APP\docs\acceptance_testing`? | Then |
|---|---|---|
| `Q-MAP_APP` (with or without `Q-MAP_APP_round2`) | **Yes** | In place. Tracker: `In place (checklist file present)`. Go to test 00. |
| `Q-MAP_APP` and `Q-MAP_APP_round2` | **No** | **STOP** (end the session; ask for help). |
| `Q-MAP_APP` only | **No** | `Q-MAP_APP` is an old program. **STOP** and ask for help before downloading. Claude will give you the download steps for the exact build to test. |
| No `Q-MAP_APP` | - | **STOP** (end the session; ask for help). |

The round-2c tests on 07-Nov-26 used the program in place, so the first row is expected. The build is confirmed in test 23.

#### Test 00: Originals folder, before (PICTURE)

**Do:** in File Explorer open **your originals folder** (section 2: outside `D:\Q-MAP_V01`).
- If you do not keep a separate originals folder (your master copies are `D:\Q-MAP_V01\Market_Files`), open
  `D:\Q-MAP_V01\Market_Files` and write in the tracker: `No separate originals folder; Market_Files is my master copy.`

**Do:** click **View** → **Details**.
**Do:** click once in the **address bar** at the top. It changes to show the full path, for example `D:\My Data\Market files`.
**You should see:** the full path, and every file with **Name**, **Date modified**, **Size**. Count the files.
**Save:** PICTURE `00_Originals_Before.png` of the **whole** File Explorer window, including the address bar with the full
path and the item count at the bottom left (for example "11 items").
**Tracker:** write the folder path and the number of files. Example note: `Folder D:\...\..., 11 files.`
**Do not** open, copy or move the originals now.

#### Test 00b: Python version (WRITE DOWN)

**Do:** start IDLE (section 4.1, step 1).
**You should see:** the first line, for example `Python 3.12.10 (tags/v3.12.10:...) [MSC v.1943 64 bit (AMD64)] on win32`.
**Tracker:** copy that line.

### Part B: Start Q-MAP

#### Test 01: Database Manager and folders (V1, V2) (PICTURE)

**Do:** open Database Manager (section 4.1).
**You should see:** the **Home** screen, with section **"Your folders (remembered between sessions, shared by both Q-MAP applications)"**.
**Do:** check the **Q-MAP_DATA folder** box. It should read `D:\Q-MAP_V01\Q-MAP_DATA`. If it does not, click **Browse...**
next to it, go to `D:\Q-MAP_V01`, click **Q-MAP_DATA** once and click **Select Folder**.
**Do:** the same for the **Q-MAP_OUTPUT folder** box (`D:\Q-MAP_V01\Q-MAP_OUTPUT`).
**You should see:** under each box, in green, **"OK - this folder can be used."**, then **"Both folders are ready and remembered."**
**Do:** scroll down the Home screen.
**You should see:** **READY** (green) next to **Sources (automatic loading)**, **Data Management** and **Datasets and Storage**.
**Save:** PICTURE `01a_Database_Manager_Folders.png` (folders and the green lines) and `01b_Database_Manager_Ready.png` (the READY labels).
**If different:** a red message under a folder box → picture, **STOP** (end the session).

#### Test 02: Workbench home (V3) (PICTURE)

**Do:** open the Analytical Workbench (section 4.1).
**You should see:** the same two folders with green "OK" lines; **Dataset Summary** and **MA Research: MA Affinity (QLOPB)** marked **READY**.
**Do:** scroll down until you see **Market Intelligence (MIQP)**.
**You should see:** **COMING SOON** next to it.
**Save:** PICTURE `02a_Workbench_Home.png` (folders and the two READY lines) and `02b_Workbench_MIQP.png` (the MIQP line).
Keep both Q-MAP windows open from now on. Switch between them with the taskbar.

### Part C: Warnings shown for files (Database Manager → Sources)

How to look at one file (used in tests 03-09 and 13):
1. Database Manager → click **Sources** (top right).
2. In section **1**, click the folder line named in the test (column **Name**: `Market_Files` or `Pattern_Files`).
3. In section **"2. Output - files found in the selected folder"**, click the file named in the test (column **File**).
4. The box **under** the file list shows that file's details. Scroll inside that box if needed.

#### Test 03: OLAELEC (W2) (PICTURE + TEXT COPY)

**Do:** look at `OLAELEC.xlsx` in `Market_Files` (steps 1-4 above).
**You should see in the details box:**
- `Detected timeframe: 1 minute`
- `Status: Accepted by default`
- `Quality warnings recorded for dataset 11:`
- `WARNING: Some dates/times have more than one different value`

Other warnings may also appear (for example "Rows were not in date order"). That is normal for this file.

**Save:** PICTURE `03_OLAELEC_Details.png` and TEXT COPY of the details box `03_OLAELEC_Details.txt`.

#### Tests 04-08: the five pattern files (W14-W17) (PICTURE + TEXT COPY each)

**Do:** click the `Pattern_Files` folder line, then each file in turn.

| Test | File | Must be in the details box | Must **not** be there | Save |
|---|---|---|---|---|
| 04 (W14) | `NSE_RANDOMGAPS.csv` | `WARNING: Some days have fewer bars than usual` | any line with "bar interval" | `04_RandomGaps.png`, `04_RandomGaps.txt` |
| 05 (W15) | `NSE_EVERYOTHER.csv` | `WARNING: Part of the file may have another bar interval`, `source rows 1126-1163`, `cannot show whether`; `Detected timeframe: 5 minutes` | - (it also shows "Long gaps between dates" and "fewer bars"; that is normal) | `05_EveryOther.png`, `05_EveryOther.txt` |
| 06 (W16) | `NSE_GENUINE3M.csv` | `WARNING: Part of the file has another bar interval`, `3 minute(s)` | - | `06_Genuine3M.png`, `06_Genuine3M.txt` |
| 07 (W16) | `NSE_DAILY0000.csv` | `WARNING: Part of the file has another bar interval`, `outside the times of the intraday bars` | - | `07_Daily0000.png`, `07_Daily0000.txt` |
| 08 (W17) | `NSE_DAILY0915.csv` | `WARNING: Part of the file may have another bar interval`, `a time the intraday bars also use` | - | `08_Daily0915.png`, `08_Daily0915.txt` |

Note the difference: **"has"** = certain; **"may have"** = Q-MAP cannot be sure.

#### Test 09: SPARSE (W18) (PICTURE + TEXT COPY)

**Do:** click `NSE_SPARSE.csv` in `Pattern_Files`.
**You should see:** `WARNING: Long gaps between dates` with `2025-04-04 -> 2025-04-14` (04-Apr-25 to 14-Apr-25), and
`WARNING: Some days have fewer bars than usual`, and **no** line with "bar interval".
**Save:** `09_Sparse_File_Details.png`, `09_Sparse_File_Details.txt`.

#### Test 10: the scan report of the pattern files (W18) (PICTURE x 2)

**Do:** in File Explorer go to `D:\Q-MAP_V01\Q-MAP_OUTPUT\Data_Management\SCAN_20261106_174124`.
**You should see:** a file starting with `Scan_Report_` and several files starting with `issues_event`.
**Save:** PICTURE `10a_Pattern_Scan_Folder.png` of the File Explorer window **with the address bar**.
**Do:** right-click the `Scan_Report_...csv` file → **Open with** → **Notepad** (or Excel).
**You should see:** `Pattern_Files` at the top and six lines `NSE_DAILY0000.csv`, `NSE_DAILY0915.csv`, `NSE_EVERYOTHER.csv`,
`NSE_GENUINE3M.csv`, `NSE_RANDOMGAPS.csv`, `NSE_SPARSE.csv`, each with `Imported`.
**Save:** PICTURE `10b_Pattern_Scan_Report.png`. Close it; if asked to save, click **Don't Save**.

#### Test 11: a dataset with warnings is still usable (W18) (PICTURE + TEXT COPY)

**Do:** Workbench → click **Run an analysis** (top right).
**Do:** in section **"1. Input - analysis and prepared datasets"**, open the **Analysis:** list and choose **Dataset Summary**.
**Do:** in the dataset list, click the line **NSE:EVERYOTHER** (5 minutes, dataset 30).
**Do:** click **Check readiness (nothing is saved)**.
**You should see** in the box **"Readiness of the selected data"**: `READY - every requirement is met.` and a line starting
`NOTE Validated with warnings`.
**Save:** `11_Workbench_Warning.png`, and a TEXT COPY of the readiness box `11_Workbench_Warning.txt`.
You do not need to run the summary.

### Part D: Repeat scan, RELIANCE, reject and restore

#### Test 12: repeat scan of Market_Files (A4) (PICTURE + TEXT COPY)

**Do:** Database Manager → **Sources** → click the `Market_Files` folder line in section 1.
**Do:** click **SCAN SELECTED FOLDER NOW** (section **"3. Options - scan, review and correct"**). Wait until **Stage:** shows **Finished**.
**You should see:**
- under **Progress / Status**, the green message `Scan finished (10 unchanged (imported earlier), 1 unchanged (rejected earlier)). Run SCAN_...`;
- in the file list, 10 files with **Result** `Unchanged (imported earlier)` (5PAISA, RIVERUSD, BANKNIFTY, OLAELEC, UJJIVAN,
  VERANDA, three ICICIBANK files, RELIANCE_EQ) and `AKZOINDIA.parquet` with `Unchanged (rejected earlier)`.

The Detail of `RELIANCE_EQ.csv` reads "...Imported. 1 dataset(s) created". That repeats its earlier result; it is not a new import.
**Save:** PICTURE `12a_Repeat_Scan_Message.png` (Progress / Status) and `12b_Repeat_Scan_Files.png` (the file list,
scrolled so all 11 Result values are visible), and a TEXT COPY of the Live Log `12_Repeat_Scan_Log.txt`.
**Tracker note example:** `PASS - 10 unchanged (imported earlier), 1 unchanged (rejected earlier); run SCAN_2026...`.
**If different:** any file says `Imported` or `Rejected` (without "Unchanged") → picture, mark **FAIL**, continue with test 13.

#### Test 13: RELIANCE name (W5) (PICTURE + TEXT COPY)

**Do:** click `RELIANCE_EQ.csv` in the `Market_Files` file list.
**You should see:** `Instrument: NSE:RELIANCE (alias)` and `Dataset(s): 18`.
**Save:** `13_Reliance_After_Scan.png`, `13_Reliance_After_Scan.txt`.

#### Test 14: alias registry (W5) (PICTURE)

**Do:** click **Open alias registry folder** (section 3). A File Explorer window opens.
**Do:** right-click `Instrument_Aliases.csv` → **Open with** → **Notepad**.
**You should see:** a line `RELIANCE,RELIANCE EQ` (Notepad), or RELIANCE in column A and RELIANCE EQ in column B (Excel).
**Save:** `14_Alias_Registry.png`. Close it; if asked to save, click **Don't Save**. This file is part of your Q-MAP records.

#### Test 15: the two RELIANCE datasets (W5) (PICTURE x 2, look only)

**Do:** Database Manager → click **Datasets and Storage** (top right).
**Do:** in the dataset list, click the line **13 NSE:RELIANCE_EQ Daily**.
**You should see** in the box at the top: `Bars: 7746   From 07-Nov-94 to 30-Dec-25`, `Original file(s): RELIANCE_EQ.csv`
and `State: Rejected by you`.
**Save:** `15a_Reliance_EQ_Details.png`. The picture must show the lines Bars, Original file(s) and State.
**Do:** click the line **18 NSE:RELIANCE Daily**.
**You should see:** `Bars: 7746   From 07-Nov-94 to 30-Dec-25`, `Original file(s): RELIANCE_EQ.csv`, State **Active**.
**Save:** `15b_Reliance_Details.png`.
**If different:** dataset 13 is **not** "Rejected by you", or dataset 18 is not Active → picture, write down, **STOP** this
part (go to test 19). Do not click Reject or Restore.

#### Test 16: the RELIANCE duplicate decision (W5) (WRITE DOWN)

The decision was taken on 07-Nov-26 (dataset 13 rejected, reason `duplicate after alias correction (W5)`).
**Do not click Reject or Restore.** If test 15 matched, write: `Already rejected on 07-Nov-26; confirmed in test 15.`

#### Test 17: reject and restore two files (W6, W7) (changes your Q-MAP records; restored at once) (PICTURE x 2)

**Do:** Database Manager → **Sources** → click the `Market_Files` folder line.
**Do:** in the file list click `VERANDA_1min.csv`. Then hold **Ctrl** and click `5PAISA_30min.csv`. Both lines are now blue.
**Do:** click in the **Reason (recorded):** box (section 3) and type `UAT retest W6`.
**Do:** click **Reject selected**.
**You should see:** under Progress / Status, `Rejected 2 dataset(s). They are kept unchanged and no longer offered to
analyses; Restore undoes it.` In the file list, **both** rows show Result **Rejected by you**.
**Save:** PICTURE `17a_Files_Rejected.png`. Scroll so that **the two file rows and the message** are both visible (two
pictures `_part1` / `_part2` if needed).
**If different:** if either row does not show "Rejected by you", take the picture and go straight to the Restore action below.
**Do:** keep both rows selected (if not, select them again as above). Click **Restore selected**.
**You should see:** `Restored 2 dataset(s). They are offered to analyses again.` **Both** rows show **Available again (restored by you)**.
**Save:** PICTURE `17b_Files_Restored.png` (the two rows and the message).
**If different:** if either row does not show "Available again (restored by you)", **STOP**:
- do not click anything else for these files;
- mark test 17 **FAIL** and test 18 **NOT TESTED**;
- write which file shows what;
- go to test 19.

Nothing is lost: the datasets are kept and can be restored with help.

#### Test 18: Workbench list after restore (W7) (PICTURE)

**Do:** Workbench → **Run an analysis** → click **Refresh** (section 1).
**You should see:** VERANDA and 5PAISA in the list; **NSE:RELIANCE** (dataset 18) in the list; **NSE:RELIANCE_EQ** (dataset 13) **not** in the list.
**Save:** `18_Workbench_After_Restore.png` (use `_part1`, `_part2`, `_part3` if the list needs scrolling).

### Part E: The window stays usable during a scan

#### Test 19: Stop scan (W8) (PICTURE + TEXT COPY)

**Prepare the folder (File Explorer only):**
1. In `D:\Q-MAP_V01`, right-click empty space → **New** → **Folder** → type `W8_Retest` → **Enter**.
   If that name exists, use `W8_Retest_2` (write the name in the tracker).
2. Open `D:\Q-MAP_V01\Market_Files`. Press **Ctrl+A** (all files turn blue), then **Ctrl+C**.
3. Open the new `W8_Retest` folder. Press **Ctrl+V**. Wait until copying ends. Press **Ctrl+V** again, and then a third
   time. Windows adds "- Copy" to the names.
4. **Check:** the bottom-left corner of File Explorer shows the number of items. It should be **30 or more**.
   Write the number in the tracker.

**Scan and stop:**
1. Add the folder `W8_Retest` exactly as in section 4.2 (check the path in the Live Log).
2. With the `W8_Retest` line selected in section 1, click **SCAN SELECTED FOLDER NOW**.
3. **Immediately** click **Stop scan** (next to it). Then scroll the file list up and down with the mouse wheel.

**You should see:**
- the window responds while you scroll;
- under Progress / Status, the message `Stopped by you after N file(s); M file(s) not processed (listed in the scan
  report). Work already done is kept.`;
- the Live Log shows `STOPPED by you`.

**Known display fault (review finding F3):** the counter **Files done:** may show all files (for example `33 / 33`) and
the bar may be full, even though the scan stopped. Trust the red message, not the counter.

**Save:** PICTURE `19_Stop_Scan.png` (Progress / Status with the message) and a TEXT COPY of the Live Log `19_Stop_Scan_Log.txt`.
**Before saving the text copy, check that it contains no names of personal files.** If it does, do not save it; write
"log not saved: contained other file names".

**If the scan finishes before you can click Stop scan:**
- **One try only.** Do not repeat it, add more files or add another folder.
- Mark **NOT TESTED** with the note `scan finished too quickly to stop`. This is not a failure.
- Go to test 20.

**If the window freezes or an error appears:** picture, mark **FAIL**, go to test 20 if Q-MAP still works.

### Part F: Analyses

#### Test 20: MA Affinity settings (V6) (PICTURE)

**Do:** Workbench → **Run an analysis** → **Analysis:** list → **MA Affinity (QLOPB)**.
**You should see** in section **"3. Options - parameters"**:
- **MA types:** `SMA`
- **MA start:** `10`
- **MA end:** `250`
- **Forward windows:** `5,10,20,50`
- a grey help line under each.

**Save:** `20_MA_Affinity_Settings.png`.

#### Test 21: Dataset Summary of ICICIBANK, with the calendar (A5) (PICTURE x 3 + FILE COPY)

**Do:** in the **Analysis:** list choose **Dataset Summary**.
**Do:** in the dataset list click **7 NSE:ICICIBANK Daily** (Bars 7166). Only this one line must be selected
(the counter shows `[1 selected of ...]`).
**What this test checks:** that the **Calendar...** button works (A5 is "Dates and the calendar"), and that Dataset
Summary gives the expected figures for the right dates. Choosing a date in the calendar only fills the date box; it
never starts an analysis. Nothing runs until you click **RUN ANALYSIS** yourself.

**Part 1: the calendar (sets the start date)**

**Do:** click in the **Start date:** box (section 3) and type `01-Jan-98`.
**You should see:** next to the box, in **green**, `= 01-Jan-1998`. (Typing first makes the calendar open at January
1998. With an empty box it opens at today's month, which is far from 1998.)
**Do:** click the **Calendar...** button next to the **Start date:** box.
**You should see:** a small window called **Choose a date**, with **January 1998** at the top and the day **1** shown
pressed in. At the top are four buttons: **<<** and **>>** move one year back or forward, **<** and **>** move one
month back or forward. At the bottom are **Today**, **Clear** and **Close**.
**Save:** PICTURE `21c_Calendar_January_1998.png` showing the small window.
**Do:** click **>** once. **You should see:** **February 1998**.
**Do:** click **<** once. **You should see:** **January 1998** again.
**Do:** click **>>** once. **You should see:** **January 1999**.
**Do:** click **<<** once. **You should see:** **January 1998** again.
**Do:** click the day **2**.
**You should see:** the small window closes by itself; the **Start date:** box now shows `02-Jan-98` and, in **green**,
`= 02-Jan-1998`. The calendar has set the correct start date for this test.
**Do not click** **Today** or **Clear** in the small window: **Today** would put today's date in the box and **Clear**
would empty it. If you clicked one by mistake, nothing has run: click in the **Start date:** box, delete its text
(Backspace) and type `02-Jan-98`.

**Part 2: the end date**

**Do:** click in the **End date:** box and type `02-Nov-26`.
**You should see:** in green, `= 02-Nov-2026`.
**Save:** PICTURE `21a_Dates_Before_Run.png` showing both boxes and both green lines.

**If different (calendar):** the small window does not open, does not show **January 1998**, or a button or a day
does nothing. Click **Close** (or the X of the small window) if it is open. Nothing has run. Then:
1. Click in the **Start date:** box, delete its text (Backspace) and type `02-Jan-98`.
2. Check the green `= 02-Jan-1998`.
3. Continue with Part 2, and record in the tracker what the calendar did (see the ready-to-copy note).
**If different (dates):** a red line, or a green line with another date: click in that box, delete its text, type the
date again and check again. If it is still not right, mark **NOT SURE** and go to test 22 **without** clicking
**RUN ANALYSIS**.
**Stop and check before running:** click **RUN ANALYSIS** only when the two green lines say exactly `= 02-Jan-1998`
and `= 02-Nov-2026`.

**Part 3: the summary**

**Do:** click **RUN ANALYSIS**. Wait until the Live Log shows `... completed: 1 output file(s).`
**Do:** click **Open Output Folder**. A File Explorer window opens on the run's folder `DSUM_...`.
**Do:** copy the file `Dataset_Summary_....csv` into your evidence folder (section 3.5). Then open the **copy** in Excel or Notepad.
**You should see:** Bars `7166`, First bar `02-Jan-98`, Last bar `02-Nov-26`, First close `7.86`, Last close `1387.4`.
**Save:** PICTURE `21b_ICICIBANK_Summary.png`; the FILE COPY stays as `Dataset_Summary_dd_Mmm_yy_hhmmss.csv`.
**If you ran with a wrong date:** do not delete that run. Write its Run ID (from the Live Log) in the tracker, for example
`First run DSUM_... used a wrong start date; repeated as DSUM_...`, and run again with the right dates.

#### Test 22: output folder (A7) (PICTURE)

**You should see** (the window from test 21) the address bar ending in `Q-MAP_OUTPUT > Research_Reports > DSUM_...`, with
the CSV, `run_log`, `run_manifest` and `Run_Metadata_...` files.
**Save:** `22_Output_Folder.png` with the address bar.

#### Test 23: build in the PDF report (PICTURE + WRITE DOWN)

**Do:** Workbench → **Run an analysis** → **Analysis:** list → **MA Affinity (QLOPB)**.
**Do:** click **7 NSE:ICICIBANK Daily** only. Leave **Start date** and **End date** empty and all other settings as they are.
**Do:** click **RUN ANALYSIS**. Wait (about 30 seconds) until the Live Log shows `... completed: 9 output file(s).`
**Do:** click **Open Output Folder** → double-click the `.pdf` file.
**You should see:** under the title "QLOPB - MA Affinity research report", the line containing
`Q-MAP build: qmap 0.1.0rc1 / c2 build a202d43d78ed`.
**Save:** PICTURE `23_Build_Fingerprint_PDF.png`. **Write down** the build text in the tracker's session details.
Close the PDF reader.

### Part G: Close, restart, originals (at the end)

#### Test 24: close (W12) (PICTURE)

**Do:** click the **X** (top right) of the Workbench window, then of the Database Manager window.
**You should see:** both close; no message; no empty window left.
**Save:** `24_Closed_Desktop.png` (the desktop).

#### Test 25: restart and rescan (V14) (PICTURE x 2 + TEXT COPY)

**Do:** open both windows again (section 4.1).
**Do:** Workbench → **Run an analysis**.
**You should see:** in section **"2. Output - where results are saved"**, **Last run folder:** shows the MA Affinity run of test 23 (`MAAF_...`).
**Save:** `25a_Last_Run_Folder.png`.
**Do:** Database Manager → **Sources** → `Market_Files` line → **SCAN SELECTED FOLDER NOW**.
**You should see:** `10 unchanged (imported earlier), 1 unchanged (rejected earlier)`; VERANDA and 5PAISA now show
`Unchanged (imported earlier)` (no longer "Available again").
**Save:** `25b_Restart_Rescan.png` and a TEXT COPY of the Live Log `25_Restart_Rescan_Log.txt`.

#### Test 26: originals folder, after (PICTURE)

**Do:** open the same folder as in test 00, **View → Details**, click in the address bar.
**You should see:** the same path, the same number of files, and the same names, sizes and dates as `00_Originals_Before.png`.
**Save:** `26_Originals_After.png` (whole window with address bar and item count).
**If different:** picture, mark **FAIL**, write which file differs. Do not change anything.

#### Test 27: content check of the originals (W11) (PICTURE + TEXT COPY)

1. In `D:\Q-MAP_V01` make a new folder `W11_Retest` (or `W11_Retest_2` if it exists).
2. Open your originals folder (test 00). **Ctrl+A**, **Ctrl+C**. Open `W11_Retest`, **Ctrl+V** once. This copies; nothing is moved.
3. Add the folder `W11_Retest` as in section 4.2 and click **SCAN SELECTED FOLDER NOW**.

**You should see:** every file **except** AKZOINDIA with Result `Already loaded`, and `AKZOINDIA.parquet` with
`Rejected earlier (unchanged)`. The total equals the file count from test 00. **No file** shows `Imported`.
**Save:** `27_Originals_Content_Check.png` and a TEXT COPY of the Live Log `27_Originals_Content_Check_Log.txt`.
**If different:** any file `Imported` or `changed` → picture, mark **FAIL**, write the file name, **STOP**.

Close both Q-MAP windows with **X**.

---

## 6. Finishing

1. In the tracker, give **every** test a status: PASS, PASS WITH OBSERVATION, FAIL, NOT TESTED or NOT SURE.
2. Fill in **Session details**, **Notes** and **Final summary** in the tracker. Leave "Owner's acceptance decision" empty.
3. Check the evidence folder against the tracker's file list (tracker section 4).
4. Right-click the evidence folder → **Send to** → **Compressed (zipped) folder**.
5. Send the ZIP and the tracker for review.

**Completing the tests is not acceptance and not approval to merge.** The evidence is reviewed first; the decision is yours.

---

## 7. What changed since round 2c, and why

**Expectations changed because Q-MAP's state changed (not because the rules changed):**
- **Test 15 and 16:** NSE:RELIANCE_EQ (dataset 13) was rejected by the owner on 07-Nov-26. It is now expected to show
  **Rejected by you**, and no reject action is taken. (Round 2c: compare, then reject.)
- **Tests 19 and 27:** new folder names `W8_Retest` and `W11_Retest`, because `W8_Round2c` and `W11_Check_2c` are already
  folder sources.
- **Test 27:** the expected count is "every file except AKZOINDIA" instead of a fixed "seven". In round 2c the folder used
  held 11 files, not the 8 the guide assumed (review finding F2). The owner should confirm which folder holds the originals.

**Clarity changes from the round-2c experience:**
- Screens, sections and buttons are named as Q-MAP shows them; terms are explained (section 2); one action per line.
- Safe folder adding with a path check before scanning, and what to do after a wrong folder (section 4.2; finding F1).
- Test 21: type the dates instead of using the calendar; picture the green confirmations before running; what to do
  after a run with a wrong date (finding F4).
- Each picture now states what it must show:
  - the address bar for originals and folders;
  - the two file rows in test 17;
  - the Datasets and Storage details in test 15;
  - the MIQP line in test 02;
  - Last run folder in test 25.
- Text copies and file copies are named, and how to make them is explained.
- The display fault after Stop scan is explained (finding F3).
- No package installs during testing: an install prompt is a STOP.
- The draft's download route is replaced by a STOP. The round-2c owner tests used the program in place, and any new build
  needs its own download instructions from Claude.

The detailed reasons are in `Q-MAP_v0.1_UAT_Round2c_Owner_Results_Review_07_Nov_26_173737.md`.
