# Q-MAP MA Affinity V2 release candidate: focused Windows acceptance guide (R1 to R10)

**10-Nov-26 | Program to test: exactly commit `fbbedd4c46adad11a4079f8e1b39437e23184362` | Tracker:
`Q-MAP_MA_Affinity_V2_RC_Acceptance_Tracker_10_Nov_26_113344.md` (same folder)**

**Test exactly this commit.** It holds the program, the example file and the expected results. Step 2.1.4 downloads
that commit, not a branch: a branch can move on, a commit never changes. (The pull request's last commit after it only
adds this guide and its tracker; nothing in the program differs.)

**Written to `docs/standards/Q-MAP_User_Documentation_Standard.md`.**

**What this test covers, and what it does not.** You already accepted the V1 beta on 10-Nov-26 (A1 to A7). This guide
checks **only what is new or changed**: the folders prepared automatically, the progress bar, Cancel, closing during a
run, MA Affinity V2 and its new report, and that V1 and your earlier data are untouched. It does not repeat the V1
checks. About 30 minutes. You do not need Python knowledge, command lines or logs.

**Automated CI and Project Owner acceptance are separate.** The automated test matrix runs the software suite on
standard GitHub Windows and Ubuntu runners. It does not test your own laptop, your installed Python/IDLE setup, local
folder permissions, screen layout or the manual workflow below. Passing CI is not Project Owner acceptance and does
not complete any of R1-R10. You must perform these checks on Windows and record what you actually observe in the
tracker. Nothing in this guide has been accepted by you yet. See the current automated checks on
[PR #26](https://github.com/BulluBhai/Q-MAP/pull/26).

**Status: OUTSTANDING.** To be carried out by the Project Owner.

---

## 1. Before you begin

### 1.1 Rules that protect your data

1. This test uses a **new folder** `D:\Q-MAP_V01\RC_Test`. Your `Beta_Test` folder from 10-Nov-26 and your round 2c
   folders are only **looked at** in R9, never changed.
2. Q-MAP only reads the example file. It never changes, moves or deletes it.
3. Step R1 changes **which folders Q-MAP remembers** (a setting, not data). Section 4 says how to switch back.
4. If anything unexpected happens: take a picture, write it in the tracker, and **do not repair it**.

### 1.2 What you need

- Your laptop with IDLE for Python 3.11 or 3.12. **Do not install or update anything.**
- Notepad, Excel and a PDF viewer.
- Evidence goes into `D:\Q-MAP_V01\RC_Test\Evidence`. Two kinds are used:
  - **PIC** (a picture): press **Windows key + Shift + S**, drag a box around what the step names, click the pop-up at
    the bottom right, press **Ctrl+S**, open the `Evidence` folder, type the exact file name and click **Save**.
  - **FILE** (a copy of a file Q-MAP made): in File Explorer click the file once, press **Ctrl+C**, open the `Evidence`
    folder and press **Ctrl+V**. Never use **Ctrl+X** (cut).

---

## 2. Preparation (about 5 minutes)

### 2.1 Make the folders and get the program

1. **Do:** press **Windows key + E**, click **This PC**, double-click **D:**, then double-click `Q-MAP_V01`.
2. **Look:** is there already a folder `RC_Test`?
   - **No:** right-click an empty area → **New** → **Folder**, type `RC_Test` and press **Enter**.
   - **Yes:** do **not** open, change or delete it. Make `RC_Test_2` instead and write its name in the tracker,
     section 1. **Wherever this guide says `RC_Test`, use that name.**
3. **Do:** double-click `RC_Test`. Inside it make **only these three** new folders: `Q-MAP_APP`, `Beta_Files`,
   `Evidence`. Do **not** make `Q-MAP_DATA` or `Q-MAP_OUTPUT`: Q-MAP makes them itself in R1.
4. **Do:** in your browser open exactly this address (it downloads the ZIP of that one commit straight away):
   `https://github.com/BulluBhai/Q-MAP/archive/fbbedd4c46adad11a4079f8e1b39437e23184362.zip`
5. **Do:** in **Downloads**, right-click the ZIP → **Extract All...** → **Extract**.
6. **Do:** open the extracted folder (its name is `Q-MAP-fbbedd4c46adad11a4079f8e1b39437e23184362`) until you see
   `database_manager.py`. Press **Ctrl+A**, **Ctrl+C**, open `D:\Q-MAP_V01\RC_Test\Q-MAP_APP` and press **Ctrl+V**.
7. **Do:** in `Q-MAP_APP`, open `docs` → `acceptance_testing` → `rc_ma_affinity_v2`. Click `NSE_BETADEMO.csv` once,
   press **Ctrl+C**, open `D:\Q-MAP_V01\RC_Test\Beta_Files` and press **Ctrl+V**.
8. **Check:** the name of the extracted folder ends with `fbbedd4c46adad11a4079f8e1b39437e23184362`. If it does not,
   you downloaded something else: **STOP** and ask for help (section 5).

**You should see** in `RC_Test`: `Beta_Files` (one file, `NSE_BETADEMO.csv`), `Evidence` (empty) and `Q-MAP_APP`.

**If different:** if Windows asks **Replace or Skip Files**, click **Cancel**: you are in a folder that is not empty.
Go back to step 2 and make a new folder.

---

## 3. The checks

### R1: the folders are prepared next to the program (PIC)

1. **Do:** Start menu → type `IDLE` → open the IDLE you normally use. Write its first line (it starts with
   `Python 3.`) in the tracker, section 1.
2. **Do:** in IDLE click **File** → **Open...** → open `D:\Q-MAP_V01\RC_Test\Q-MAP_APP\database_manager.py`. Press
   **F5**.
3. **You should see** the window **Q-MAP Database Manager - prepare and manage market data** on **Home**, with a line
   under the two folder boxes. It is **one** of these two:
   - **Case A (most likely, because Q-MAP remembers your 10-Nov-26 folders):** `You are using the folders you chose
     earlier (remembered). The standard folders for this copy of Q-MAP would be D:\Q-MAP_V01\RC_Test\Q-MAP_DATA and
     D:\Q-MAP_V01\RC_Test\Q-MAP_OUTPUT. ...` The two boxes still show your `Beta_Test` folders. Q-MAP has **not**
     switched on its own. Go to step 4.
   - **Case B:** `Folders prepared automatically next to the Q-MAP program folder: created Q-MAP_DATA and
     Q-MAP_OUTPUT.` in green, and the boxes show the `RC_Test` folders. Skip to step 7.
4. **Do (case A only):** click **Use standard folders** (to the right of the line `Both folders are ready and
   remembered.`).
5. **You should see** a window **Use standard folders** listing `Q-MAP_DATA: D:\Q-MAP_V01\RC_Test\Q-MAP_DATA` and
   `Q-MAP_OUTPUT: D:\Q-MAP_V01\RC_Test\Q-MAP_OUTPUT`, and saying your current folders stay exactly as they are.
6. **Do:** click **Yes**.
7. **You should see** the two boxes showing `D:\Q-MAP_V01\RC_Test\Q-MAP_DATA` and `D:\Q-MAP_V01\RC_Test\Q-MAP_OUTPUT`,
   the line `Both folders are ready and remembered.` in green, and a green line starting `Now using the standard
   folders` (case A) or `Folders prepared automatically` (case B).
8. **Save:** PIC `R1_Folders.png` of the folder area on **Home**.
9. **Check:** in File Explorer, `D:\Q-MAP_V01\RC_Test` now also holds `Q-MAP_DATA` and `Q-MAP_OUTPUT`.

**PASS** if step 3 matches one of the two cases and steps 7 and 9 are as described. **If different:** if a red line
`The standard folders could not be prepared automatically: ...` appears, take the picture, write the red text in the
tracker and **STOP**.

### R2: a finished scan shows a full bar (PIC)

1. **Do:** click **Sources** (top right). Leave every setting in section 1 as it is.
2. **Do:** click **Add folder...**, go to `D:\Q-MAP_V01\RC_Test`, click `Beta_Files` once and click **Select Folder**.
3. **Do:** click **SCAN SELECTED FOLDER NOW** (section 3).
4. **You should see** under **Progress / Status**: **Stage:** `Finished`, the green bar **full from left to right**,
   and a line starting `Scan finished (1 imported)`.
5. **Save:** PIC `R2_Scan_Finished.png` of **Progress / Status**.
6. **Do:** close the Database Manager with **X**.

**PASS** if step 4 is as described.

### R3: V1 is still available and unchanged (PIC + FILE)

1. **Do:** in IDLE open `D:\Q-MAP_V01\RC_Test\Q-MAP_APP\analytical_workbench.py` and press **F5**. Click
   **Run an analysis** (top right).
2. **Do:** click the **Analysis:** list. **You should see** both **MA Affinity (QLOPB)** and **MA Affinity V2
   (chance-tested)** (and **Dataset Summary**). Choose **MA Affinity (QLOPB)**.
3. **Do:** click the line **NSE:BETADEMO** in the dataset list. In **3. Options - parameters**, in **MA types**,
   delete what is there and type `SMA,EMA`. Leave every other box as it is.
4. **Do:** click **RUN ANALYSIS**. Wait (about half a minute).
5. **You should see** under **Progress / Status**: **Stage:** `Finished`; **Progress:** `488 of 488 steps (100.0%)`;
   the bar **full**; a line starting `Completed. Run MAAF_`.
6. **Save:** PIC `R3_V1_Completed.png` of **Progress / Status**.
7. **Do:** click **Open Output Folder**, open the file starting `MA_Affinity_Findings_` (Notepad).
8. **You should see** under **Frozen Top-5**, in this order: `1. EMA-37`, `2. EMA-34`, `3. SMA-38`, `4. SMA-49`,
   `5. SMA-39`, and line 1 starting `1. EMA-37: affinity 66.13; in-sample 63.64% success over 44 outcome(s)`. These are
   the same results you accepted on 10-Nov-26.
9. **Save:** FILE copy of that `MA_Affinity_Findings_...txt` into `Evidence`.

**PASS** if steps 2, 5 and 8 are as described.

### R4: run MA Affinity V2 and watch the progress (PIC x3)

1. **Do:** in **Analysis:** choose **MA Affinity V2 (chance-tested)**. Click the line **NSE:BETADEMO** again.
2. **Do:** in **MA types** type `SMA,EMA`. Leave every other box as it is. The new boxes at the end of the list show
   **Chance shuffles** `200`, **Chance block bars** `15`, **Chance seed** `1`, **Strength rule** `relative`,
   **Group %** `10`, **Zone mode** `percent`, **ATR period** `14`, **ATR multiple** `1`, **MA warm-up** `earlier`.
3. **Do:** click **Check readiness (nothing is saved)**.
4. **You should see** a first line starting `READY - every requirement is met.` and a line `OK   Chance test: 200
   shuffles of 69 blocks of 15 bars (seed 1); 482 candidates are re-scanned on each shuffle.`
5. **Save:** PIC `R4_V2_Ready.png` of sections 1 and 3 and the readiness box.
6. **Do:** click **RUN ANALYSIS**. While it runs (about one to two minutes):
   - **Stage:** shows `Chance test: shuffle ... of 200`;
   - **Progress:** shows `... of 96,888 steps (...%)` and the bar grows from left to right;
   - **ETA:** shows a time left after the first few seconds.
7. **Save:** PIC `R4_V2_Running.png` of **Progress / Status** while it runs.
8. **You should see** at the end: **Stage:** `Finished`; **Progress:** `96,888 of 96,888 steps (100.0%)`; the bar
   **full**; a line starting `Completed. Run MAA2_`. Write the Run ID (`MAA2_` and the date and time) in the tracker.
9. **Save:** PIC `R4_V2_Completed.png` of **Progress / Status**.

**PASS** if steps 4, 6 and 8 are as described.

### R5: the V2 report is understandable (FILE)

1. **Do:** click **Open Output Folder**. Open the file starting `MA_Affinity_V2_Findings_` (Notepad).
2. **You should see** first `EXECUTIVE INTERPRETATION`, with eight headings `1. Question investigated` to `8. What to
   investigate next`, then `DETAILED FINDINGS`.
3. **You should see** these numbers (they are the expected results; only the Run ID differs):
   - heading 3: `EMA-37 with an affinity score of 66.13 out of 100` and `63.64% of 44 usable outcome(s)`;
   - heading 5: `Verdict: NOT DISTINGUISHABLE FROM CHANCE`, `averaged 72.59`, `the real best score was 66.13 (chance
     p-value 0.8657)`;
   - heading 6: `51.36%` and `12.27 percentage points above that baseline`.
   The verdict is the expected answer for this synthetic file: its prices are made up, so luck explains the ranking.
4. **Do:** open the PDF starting `MA_Affinity_V2_Report_`. **You should see** on page 1 the heading **Executive
   interpretation** with the same eight answers.
5. **Save:** FILE copies of the `MA_Affinity_V2_Findings_...txt`, the `MA_Affinity_V2_Report_...pdf` and the
   `Run_Metadata_...json` (the full record; you do not need to read it) into `Evidence`.

**PASS** if steps 2, 3 and 4 are as described.

### R6: reproduce the V2 run (PIC + FILE)

1. **Do:** check that **Reproduce Run ID:** (section 2) shows your V2 Run ID from R4. Click **Reproduce run (runs it
   again and compares)**. Wait one to two minutes.
2. **You should see**: **Stage:** `Finished`, the bar full, and a line starting `REPRODUCED: every result table is
   identical to run <your Run ID>. New run MAA2_...`.
3. **Save:** PIC `R6_Reproduced.png` of **Progress / Status**.
4. **Do:** click **Open Output Folder** (the NEW run's folder). Copy `Reproducibility_Report_...csv` to `Evidence`
   (FILE) and open the copy in Excel.
5. **You should see** a row `Python and library versions` ending `same`, three rows starting `Result table` ending
   `IDENTICAL`, and a last row `Verdict` with `REPRODUCED: ...`. Close Excel with **Don't Save**.

**PASS** if steps 2 and 5 are as described.

### R7: Cancel stops a run safely (PIC x2)

1. **Do:** in **MA types** type `SMA,EMA,WMA,HMA,RMA` (a long run). Click **RUN ANALYSIS**.
2. **Do:** wait until **Stage:** shows `Chance test: shuffle ...`. Click **Cancel** once (next to **RUN ANALYSIS**).
3. **You should see** **Cancel** greyed out and **Stage:** `Cancelling - the run stops after its current step...`,
   then within a few seconds: **Stage:** `Cancelled`; **Progress:** `Cancelled at ... of ... steps (not complete)`; the
   bar **not** full; an amber line starting `Cancelled. Run MAA2_... stopped before it finished and is recorded as
   cancelled`.
4. **Save:** PIC `R7_Cancelled.png` of **Progress / Status**. Write the cancelled Run ID (next to **Run ID:**) in the
   tracker.
5. **Do:** click in **Reproduce Run ID:**, delete its content, type the cancelled Run ID and click **Reproduce run (runs
   it again and compares)**.
6. **You should see** a line `Not reproduced: Run MAA2_... did not complete, so it has no results to reproduce.`
7. **Save:** PIC `R7_Not_Reproducible.png` of **Progress / Status**.

**PASS** if steps 3 and 6 are as described. Nothing is lost by cancelling: your data and earlier runs are untouched.

### R8: closing the window during a run (PIC)

1. **Do:** with `SMA,EMA,WMA,HMA,RMA` still in **MA types**, click **RUN ANALYSIS**. Wait until **Stage:** shows
   `Chance test: shuffle ...`.
2. **Do:** close the Workbench window with **X** (top right).
3. **You should see** the window close, and within about a minute the IDLE Shell window shows its prompt `>>>` again
   (IDLE is no longer busy).
4. **Save:** PIC `R8_Closed.png` of the IDLE Shell window.

**PASS** if step 3 is as described. **If different:** if after two minutes IDLE still shows no `>>>`, take the picture,
write it in the tracker, then close IDLE.

### R9: your earlier data are untouched (PIC)

1. **Do:** in File Explorer open `D:\Q-MAP_V01\Beta_Test\Q-MAP_OUTPUT\Research_Reports` (the folder of your 10-Nov-26
   test; if you used another name then, open that one).
2. **You should see** your run folders from 10-Nov-26 (names starting `MAAF_20261110_`), still there.
3. **Save:** PIC `R9_Earlier_Runs.png` of that folder.
4. **Check:** `D:\Q-MAP_V01\RC_Test\Q-MAP_OUTPUT\Research_Reports` holds the runs of this test (one `MAAF_`, the
   `MAA2_` runs) and the earlier `Beta_Test` folder holds none of them.

**PASS** if steps 2 and 4 are as described.

### R10: your judgement of the new report (WRITE)

1. **Do:** read the executive interpretation (R5) once more.
2. **Write** in the tracker, row R10: is it understandable for a finance reader, is anything missing or unclear, and
   is the detailed part still what you need? This is your opinion, not a pass/fail check.

---

## 4. At the end

1. **Do:** close IDLE.
2. Q-MAP now remembers the `RC_Test` folders. To use your `Beta_Test` (or round 2c) data again later, open
   `database_manager.py`, and on **Home** use **Browse...** next to each folder to choose those folders. Nothing in
   any folder was moved or deleted.

## 5. What to do next

1. Fill in the tracker (section 1 and rows R1 to R10).
2. Right-click `D:\Q-MAP_V01\RC_Test\Evidence` → **Send to** → **Compressed (zipped) folder**. Rename the ZIP to
   `RC_Evidence_<dd_Mmm_yy>.zip`.
3. Send the tracker and the ZIP for review.
4. Then:
   - **If every check is PASS:** wait for the review. Accepting the release candidate, the open method decisions and
     merging stay your decisions.
   - **If any check is FAIL or NOT SURE:** do not repeat it and do not try to fix anything. Write what you saw (the
     exact words on the screen are enough), send the files and wait.
   - **If you stopped early (a STOP line):** send what you have and say where you stopped.

You never need to read code or logs: the pictures, the copied files and the words you write are enough.
