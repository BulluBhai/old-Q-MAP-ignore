# Q-MAP PR #21: Windows retest guide (W08 and W14-W18 only)

**09-Nov-26 | Program to test: PR #21, branch `claude/laughing-lamport-tqy0vr`, commit `181b4ba` or later |
Tracker: `Q-MAP_PR21_Retest_Tracker_09_Nov_26_112803.md` (same folder)**

**Written to `docs/standards/Q-MAP_User_Documentation_Standard.md`.**

This guide rechecks only the two checks that did not give the expected result in your run of 09-Nov-26. Do not
repeat any other check.

| Check | What it rechecks | Your earlier result |
|---|---|---|
| W08R | **Include sub-folders** ticked but not saved, both choices of the new question, and the scan report | No files found; the box went back to unticked |
| W14R-W18R | The whole-file warnings in the file details of the six pattern files | Expected warnings missing |

It reuses your `D:\Q-MAP_V01\PR10_Test` folders and the test data already in them. **Nothing in your round 2c
folders is used or changed.** About 25 minutes.

**Status: OUTSTANDING.** To be carried out by the Project Owner.

**Not part of this retest: where Add folder... opens.** As you approved, it first opens at the folder the program runs
from (the folder holding `database_manager.py`), then at the folder you chose last, also after a restart. This is
covered by automated tests (`test_add_folder_opens_at_the_application_folder_then_at_the_last_folder_also_after_restart`).
You may notice it while testing; nothing needs to be recorded. The remembered folder is kept in
`%APPDATA%\Q-MAP\gui_settings.json`, which every Q-MAP copy on this computer shares: after this test, your round 2c
copy will also open its folder window at the last folder chosen. No data is affected.

---

## 1. Rules that protect your data

1. Use only the folders under `D:\Q-MAP_V01\PR10_Test`. They are test folders.
2. Original market files are only read. Q-MAP never changes, moves or deletes them.
3. Never change Windows folder permissions or security settings.
4. If anything unexpected happens: take a picture, write it down in the tracker, and **do not repair it**.

Pictures (PIC), text copies (TXT) and file copies (FILE) are made exactly as in guide v2, sections 3.4 to 3.6
(`Q-MAP_Windows_IDLE_Acceptance_Guide_v2_08_Nov_26_151819.md`). Save everything in
`D:\Q-MAP_V01\PR10_Test\Evidence_PR21` (made in step 2.2).

---

## 2. Preparation (about 10 minutes)

### 2.1 Get the corrected program

1. **Do:** in your web browser open `https://github.com/BulluBhai/Q-MAP/tree/claude/laughing-lamport-tqy0vr`, click
   the green **Code** button, then **Download ZIP**. *(GitHub wording; it may differ slightly.)*
2. **Do:** open your **Downloads** folder, right-click the new ZIP → **Extract All...** → **Extract**.
3. **Do:** in File Explorer open `D:\Q-MAP_V01\PR10_Test`. Right-click an empty area → **New** → **Folder**, type
   `Q-MAP_APP_PR21` and press **Enter**.
4. **Do:** open the extracted folder until you see `database_manager.py`. Press **Ctrl+A**, **Ctrl+C**, open
   `D:\Q-MAP_V01\PR10_Test\Q-MAP_APP_PR21` and press **Ctrl+V**.
5. **You should see** in `Q-MAP_APP_PR21`: `database_manager.py`, `analytical_workbench.py` and the folders
   `Application` and `docs`.
6. **Do:** on `https://github.com/BulluBhai/Q-MAP/pull/21` click the **Commits** tab. Write the 7-character code on
   the last line in the tracker, section 1 (**Commit tested**). It should be `181b4ba` or later.

**If different:** if Windows asks **Replace or Skip Files**, click **Cancel**: you are in the wrong folder. Go back to
step 3. The new folder must be empty before step 4.

### 2.2 Make the evidence folder

1. **Do:** in `D:\Q-MAP_V01\PR10_Test` make a new folder `Evidence_PR21` (as in step 2.1.3).

### 2.3 Start Q-MAP with the PR10_Test folders

1. **Do:** Start menu → type `IDLE` → click the IDLE you used on 09-Nov-26.
2. **You should see** the IDLE window. Write its whole first line (it starts with `Python 3.`) in the tracker,
   section 1 (**Python version**).
3. **Do:** in IDLE click **File** → **Open...** → open `D:\Q-MAP_V01\PR10_Test\Q-MAP_APP_PR21\database_manager.py`.
4. **Do:** press **F5**.
5. **You should see** the window **Q-MAP Database Manager - prepare and manage market data** on its **Home** screen.
6. **Look at** the section **Your folders (remembered between sessions, shared by both Q-MAP applications)**:
   - **If** both boxes show `D:\Q-MAP_V01\PR10_Test\Q-MAP_DATA` and `D:\Q-MAP_V01\PR10_Test\Q-MAP_OUTPUT`: go on to
     section 3.
   - **If** they show your round 2c folders (`D:\Q-MAP_V01\Q-MAP_DATA`, `D:\Q-MAP_V01\Q-MAP_OUTPUT`): next to
     **Q-MAP_DATA folder** click **Browse...** and choose `D:\Q-MAP_V01\PR10_Test\Q-MAP_DATA`. Then next to
     **Q-MAP_OUTPUT folder** click **Browse...** and choose `D:\Q-MAP_V01\PR10_Test\Q-MAP_OUTPUT`.
7. **You should see** `Both folders are ready and remembered.`

**If different:** if a window titled **Q-MAP Database Manager cannot start yet** appears, click **No** if it offers
to install anything. Take a picture `W00R_Start_Problem.png` and **STOP** (go to section 5).

---

## 3. The checks

In every check, **Sources** means: on the Database Manager window, click **Sources** (top right).

### W08R: Include sub-folders ticked but not saved (PIC + FILE)

This scan reads the 33 files in `W_Stop` (three sub-folders). It adds data to the **test** registry only. It does not
change the files.

1. **Do:** click **Sources**. In section 1, click the line **W_Stop** in the folder list.
2. **You should see** in that line, under **Sub-folders**, the word `no`, and the box **Include sub-folders** not
   ticked.
3. **Do:** tick **Include sub-folders**. **Do not** click **Save settings of selected folder**.
4. **Do:** in section **3. Options - scan, review and correct**, click **SCAN SELECTED FOLDER NOW**.
5. **You should see** a window **Folder settings not saved** with the line
   `Include sub-folders: on screen on, saved off`.
6. **Save:** PIC `W08R_a_Not_Saved_Question.png` of that window.
7. **Do:** click **No**.
8. **You should see**:
   - the box **Include sub-folders** unticked again (the screen shows the setting the scan used);
   - under **Progress / Status** a line starting `Scan finished (no supported files found (3 sub-folder(s) not
     scanned: Include sub-folders is off for this folder))`.
9. **Save:** PIC `W08R_b_Scan_With_Saved.png` of section 1 and **Progress / Status**.
10. **Do:** tick **Include sub-folders** again. Click **SCAN SELECTED FOLDER NOW**.
11. **You should see** the same window **Folder settings not saved**. Click **Yes**.
12. **You should see**:
    - **Files done:** counting up to `33 / 33`;
    - the box **Include sub-folders** still ticked when the scan has finished;
    - in the folder list, `yes` under **Sub-folders** for **W_Stop**;
    - section 2 listing files such as `Copy_1/...`, `Copy_2/...` and `Copy_3/...`;
    - in **Live Log**, the line `Folder settings saved before the scan: Include sub-folders on`.
13. **Save:** PIC `W08R_c_Scan_With_Subfolders.png` of section 1, section 2 and **Progress / Status**.
14. **Do:** look at **Last scan report:** in section 2, then click **Open run folder**.
15. **You should see** a File Explorer window with a file whose name starts with `Scan_Report_`.
16. **Do:** copy that file to `Evidence_PR21` (FILE, guide v2 section 3.6). Open the copy in Excel.
17. **You should see** on the first line, after `Scan` and `complete`, the cells `Sub-folders`, `included`,
    `Skip patterns` and `none`. Close Excel with **Don't Save**.

**PASS** if steps 5, 8, 11, 12 and 17 are as described. **If different:** write what you saw. If the **Folder settings
not saved** window does not appear at step 5, write that, click **Stop scan** if a scan is running, and continue
with W14R-W18R.

### W14R-W18R: whole-file warnings in the file details (TXT)

No new scan is needed: the six pattern files were scanned on 09-Nov-26, and their checks are already recorded.

1. **Do:** click **Sources**. In section 1, click the line **W_Pattern**.
2. **Do:** in section **2. Output - files found in the selected folder**, click `NSE_RANDOMGAPS.csv`.
3. **You should see**, in the details box below the file list, a line starting `Quality warnings recorded for
   dataset` (followed by the dataset number and a colon), and under it the lines in the table below.
4. **Save:** TXT of the details box, as `W14R_RandomGaps.txt`.
5. **Do:** repeat steps 2 to 4 for each file in the table, using its TXT name.

| Check | File | You should see | You should NOT see | TXT |
|---|---|---|---|---|
| W14R | `NSE_RANDOMGAPS.csv` | `WARNING: Some days have fewer bars than usual` | any line containing `bar interval` | `W14R_RandomGaps.txt` |
| W15R | `NSE_EVERYOTHER.csv` | `WARNING: Part of the file may have another bar interval`; the words `cannot show whether`; `Detected timeframe: 5 minutes` | `has another bar interval` | `W15R_EveryOther.txt` |
| W16aR | `NSE_GENUINE3M.csv` | `WARNING: Part of the file has another bar interval`; `3 minute(s)` | `may have another bar interval` | `W16aR_Genuine3M.txt` |
| W16bR | `NSE_DAILY0000.csv` | `WARNING: Part of the file has another bar interval`; `outside the times of the intraday bars` | `fewer bars than usual` | `W16bR_Daily0000.txt` |
| W17R | `NSE_DAILY0915.csv` | `WARNING: Part of the file may have another bar interval`; `a time the intraday bars also use` | `fewer bars than usual` | `W17R_Daily0915.txt` |
| W18R | `NSE_SPARSE.csv` | `WARNING: Some days have fewer bars than usual` | any line containing `bar interval` | `W18R_Sparse.txt` |

Also expected, and not a failure:

- `NSE_EVERYOTHER.csv` and `NSE_SPARSE.csv` also show `WARNING: Long gaps between dates`.
- `NSE_EVERYOTHER.csv` also shows `WARNING: Some days have fewer bars than usual`.
- The line `Validation: Consistent across 15 sampled block(s)` still appears. It describes the sampled timeframe
  check only; the whole-file warnings follow it.

**PASS** if every file shows its "You should see" text and none of its "You should NOT see" text.

---

## 4. At the end

1. **Do:** in **Sources**, click **W_Stop**, untick **Include sub-folders**, and click **Save settings of selected
   folder**. This puts W_Stop back as it was. It can be undone by ticking the box and saving again.
2. **Do:** close the Database Manager with **X**.
3. **Do:** if you will use your round 2c program next, start `D:\Q-MAP_V01\Q-MAP_APP\database_manager.py` and choose
   `D:\Q-MAP_V01\Q-MAP_DATA` and `D:\Q-MAP_V01\Q-MAP_OUTPUT` on **Home** (as in guide v2, section 6).

---

## 5. What to do next

1. Fill in the tracker's section 1 (date as dd-mmm-yy, Python version, commit tested) and the W08R and W14R-W18R rows.
2. Right-click `D:\Q-MAP_V01\PR10_Test\Evidence_PR21` → **Send to** → **Compressed (zipped) folder**. Rename the ZIP to
   `PR21_Evidence_<dd_Mmm_yy>.zip`, for example `PR21_Evidence_10_Nov_26.zip`.
3. Send the tracker and the ZIP for review (to ChatGPT).
4. Then:
   - **If every check is PASS:** wait for the review. Merging PR #21 stays your decision afterwards.
   - **If any check is FAIL or NOT SURE:** do not repeat it and do not try to fix anything. Send the files and wait.
   - **If you stopped early (a STOP line):** send what you have, and say where you stopped.
