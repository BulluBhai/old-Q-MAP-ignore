# Q-MAP MA Affinity beta: Windows acceptance guide (A1 to A8)

**09-Nov-26 | Program to test: PR #23, exactly commit `2c81d3a67526f9319992d9e39d9a75fede5e3a18` | Tracker:
`Q-MAP_MA_Affinity_Beta_Acceptance_Tracker_09_Nov_26_125357.md` (same folder)**

**Test exactly this commit:** `2c81d3a67526f9319992d9e39d9a75fede5e3a18`. It holds the final program, the example file and the expected results. Step
2.1.5 downloads that commit, not the branch: the branch can move on, a commit never changes. (The pull request's last
commit after it only adds this commit number to this guide and its tracker; nothing in the program differs.)

**Written to `docs/standards/Q-MAP_User_Documentation_Standard.md`.**

**Automated tests are not this test.** The developer's automated tests (on Linux and on GitHub's Windows and Linux
computers) passed before this guide was issued; they are reported in the pull request. This guide is your own check, on
your laptop, which no automated test replaces. Nothing in it has been done by you yet.

This guide checks that the MA Affinity beta works on your laptop, from loading a file to reproducing a result. It
uses one **synthetic** file (made-up prices, no real company), `NSE_BETADEMO.csv`, so the expected results are known
exactly. About 45 minutes. You do not need Python knowledge, command lines or logs.

The research question MA Affinity answers: *for this instrument, which moving averages has price historically
interacted with most reliably, and do the leaders chosen on the earlier (in-sample) part of the history keep that
behaviour on the later (out-of-sample) part?*

**Status: OUTSTANDING.** To be carried out by the Project Owner.

---

## 1. Before you begin

### 1.1 Rules that protect your data

1. This test uses **new folders** under `D:\Q-MAP_V01\Beta_Test`. Your round 2c and PR10_Test folders are not used.
2. Q-MAP only reads the example file. It never changes, moves or deletes it.
3. Never change Windows folder permissions or security settings.
4. If anything unexpected happens: take a picture, write it in the tracker, and **do not repair it**.

### 1.2 What you need

- Your laptop with IDLE for Python 3.11 (3.12 also works). **Do not install or update anything.**
- Notepad, Excel and a PDF viewer.
- Evidence goes into `D:\Q-MAP_V01\Beta_Test\Evidence`. Two kinds are used:
  - **PIC** (a picture): press **Windows key + Shift + S**, drag a box around what the step names, click the pop-up
    at the bottom right, press **Ctrl+S**, open the `Evidence` folder, type the exact file name and click **Save**.
  - **FILE** (a copy of a file Q-MAP made): in File Explorer click the file once, press **Ctrl+C**, open the
    `Evidence` folder and press **Ctrl+V**. Never use **Ctrl+X** (cut).

  These are the same steps as sections **3.4 How to take a picture (PIC)** and **3.6 How to copy a file Q-MAP made
  (FILE)** of the PR #10 guide v2, file `Q-MAP_Windows_IDLE_Acceptance_Guide_v2_08_Nov_26_151819.md`. After step 2.1.7
  below you also have it at `D:\Q-MAP_V01\Beta_Test\Q-MAP_APP\docs\acceptance_testing\` (it opens in Notepad).

---

## 2. Preparation (about 10 minutes)

### 2.1 Make the folders and get the program

1. **Do:** press **Windows key + E**, click **This PC**, then double-click **D:**.
2. **Look:** is there a folder `Q-MAP_V01`?
   - **Yes:** double-click it.
   - **No:** right-click an empty area → **New** → **Folder**, type `Q-MAP_V01`, press **Enter**, then double-click
     it.
   - **If there is no D: drive:** **STOP** and ask for help (go to section 5). Do not use another drive on your own.
3. **Look:** inside `Q-MAP_V01`, is there already a folder `Beta_Test` (for example from an earlier attempt)?
   - **No:** right-click an empty area → **New** → **Folder**, type `Beta_Test` and press **Enter**.
   - **Yes:** do **not** open, change, delete or replace it. Make a new folder `Beta_Test_2` instead (or
     `Beta_Test_3` if that exists too). Write its name in the tracker, section 1. **Wherever this guide says
     `Beta_Test`, use that new name.**
4. **Do:** double-click your new folder. It must be empty. Inside it make these new folders: `Q-MAP_APP`,
   `Q-MAP_DATA`, `Q-MAP_OUTPUT`, `Beta_Files`, `Evidence`.
5. **Do:** in your browser open exactly this address (it downloads the ZIP of that one commit straight away):
   `https://github.com/BulluBhai/Q-MAP/archive/2c81d3a67526f9319992d9e39d9a75fede5e3a18.zip`
6. **Do:** in **Downloads**, right-click the ZIP → **Extract All...** → **Extract**.
7. **Do:** open the extracted folder (its name is `Q-MAP-2c81d3a67526f9319992d9e39d9a75fede5e3a18`) until you see `database_manager.py`. Press **Ctrl+A**, **Ctrl+C**, open
   `D:\Q-MAP_V01\Beta_Test\Q-MAP_APP` and press **Ctrl+V**.
8. **Do:** in `Q-MAP_APP`, open `docs` → `acceptance_testing` → `beta_ma_affinity_09_Nov_26`. Click
   `NSE_BETADEMO.csv` once, press **Ctrl+C**, open `D:\Q-MAP_V01\Beta_Test\Beta_Files` and press **Ctrl+V**.
9. **Check:** the name of the extracted folder ends with `2c81d3a67526f9319992d9e39d9a75fede5e3a18`. If it does not, you downloaded something else:
   **STOP** and ask for help (go to section 5). The tracker already shows this commit in section 1.

**You should see** `Beta_Files` holding exactly one file, `NSE_BETADEMO.csv`.

**If different:** if Windows asks **Replace or Skip Files** at any point, click **Cancel**: you are in a folder that is
not empty. Go back to step 3 and make a new folder. Nothing is ever overwritten in this test.

### 2.2 Start the Database Manager with the new folders

1. **Do:** Start menu → type `IDLE` → open the IDLE you normally use. Write its first line (it starts with
   `Python 3.`) in the tracker, section 1.
2. **Do:** in IDLE click **File** → **Open...** → open `D:\Q-MAP_V01\Beta_Test\Q-MAP_APP\database_manager.py`.
   Press **F5**.
3. **You should see** the window **Q-MAP Database Manager - prepare and manage market data** on **Home**.
4. **Do:** next to **Q-MAP_DATA folder** click **Browse...** and choose `D:\Q-MAP_V01\Beta_Test\Q-MAP_DATA`. Next to
   **Q-MAP_OUTPUT folder** click **Browse...** and choose `D:\Q-MAP_V01\Beta_Test\Q-MAP_OUTPUT`.
5. **You should see** `Both folders are ready and remembered.`

**If different:** if a window **Q-MAP Database Manager cannot start yet** appears, click **No** if it offers to
install anything, take a picture `A0_Start_Problem.png` and **STOP** (go to section 5).

---

## 3. The checks

### A1: register the example file (PIC)

1. **Do:** click **Sources** (top right). In section **1. Input - folders Q-MAP reads market files from**, leave
   **Market time zone:** and **Default exchange:** as they are and **Include sub-folders** unticked.
2. **Do:** click **Add folder...**, go to `D:\Q-MAP_V01\Beta_Test`, click `Beta_Files` once and click
   **Select Folder**.
3. **Do:** in section **3. Options - scan, review and correct**, click **SCAN SELECTED FOLDER NOW**.
4. **You should see** under **Progress / Status** a line starting `Scan finished (1 imported)`.
5. **Do:** in section 2, click the line `NSE_BETADEMO.csv`.
6. **You should see** in the box below it:
   - `Detected timeframe: Daily`;
   - `Status: Accepted by default`;
   - `Instrument: NSE:BETADEMO (file name)`;
   - a line `Quality warnings recorded for dataset 2: none`.
7. **Save:** PIC `A1_Registered.png` of section 2 with that box.

**PASS** if steps 4 and 6 are as described.

### A2: open MA Affinity in the Workbench and check readiness (PIC)

1. **Do:** close the Database Manager with **X**. In IDLE open
   `D:\Q-MAP_V01\Beta_Test\Q-MAP_APP\analytical_workbench.py` and press **F5**.
2. **You should see** the window **Q-MAP Analytical Workbench - research on prepared data**, with the Beta_Test
   folders on **Home** (they are remembered).
3. **Do:** click **Run an analysis** (top right).
4. **Do:** in section **1. Input - analysis and prepared datasets**, next to **Analysis:** choose
   **MA Affinity (QLOPB)**. Do **not** use **Dataset Summary** (a data check, not research).
5. **Do:** in the dataset list, click the line **NSE:BETADEMO**.
6. **You should see** in that line: **Timeframe** `Daily`, **Bars** `1500`, **From** `01-Jan-19`, **To** `30-Sep-24`.
7. **Do:** in section **3. Options - parameters**, click in the box **MA types**, delete what is there and type
   `SMA,EMA`. Leave every other box as it is.
8. **Do:** click **Check readiness (nothing is saved)**.
9. **You should see** in **Readiness of the selected data:** a first line starting `READY - every requirement is
   met.`
10. **Save:** PIC `A2_Ready.png` of sections 1 and 3.

**PASS** if steps 6 and 9 are as described. **If different:** if it says `NOT READY`, take the picture, write the
first red line in the tracker, and **STOP**.

### A3: run the analysis (PIC)

1. **Do:** click **RUN ANALYSIS**. Wait (about half a minute). **Live Log** shows the progress.
2. **You should see** under **Progress / Status** a line starting `Completed. Run MAAF_`. The Run ID is the part
   `MAAF_` followed by the date and time, for example `MAAF_20261110_101500`.
3. **Do:** write the Run ID in the tracker, row A3.
4. **You should see** the same Run ID filled in next to **Reproduce Run ID:** in section **2. Output - where results
   are saved**.
5. **Save:** PIC `A3_Completed.png` of **Progress / Status** and section 2.

**PASS** if steps 2 and 4 are as described.

### A4: the research findings (FILE)

1. **Do:** click **Open Output Folder** (section 2). File Explorer opens the run folder
   `D:\Q-MAP_V01\Beta_Test\Q-MAP_OUTPUT\Research_Reports\<Run ID>`.
2. **Do:** double-click the file whose name starts with `MA_Affinity_Findings_` (it opens in Notepad).
3. **You should see**:
   - under **Data**: `1500 bars from 01-Jan-19 to 30-Sep-24. Ranking used the in-sample part only: 1050 bars
     (01-Jan-19 to 09-Jan-23). The out-of-sample check used the remaining 450 bars (10-Jan-23 to 30-Sep-24).`
   - under **Frozen Top-5**, in this order: `1. EMA-37`, `2. EMA-34`, `3. SMA-38`, `4. SMA-49`, `5. SMA-39`;
   - line 1 reading `1. EMA-37: affinity 66.13; in-sample 63.64% success over 44 outcome(s)`.
4. **Save:** FILE copy of the `MA_Affinity_Findings_...txt` file into `Evidence`.

**PASS** if step 3 is as described. These numbers are the expected results recorded by the automated worked example
(`Worked_Example_Output\Findings.txt` in the same docs folder). Only the Run ID and the dates in file names differ.

### A5: the report and the record (FILE)

1. **Do:** in the same run folder, open the PDF whose name starts with `QLOPB_MA_Affinity_Report_`.
2. **You should see** on page 1 a heading line naming `NSE:BETADEMO Daily (dataset 2)`, your Run ID,
   `Q-MAP build:` and `Dataset checksum (SHA-256):`, and the sections **Data and sample sizes** and the
   limitations.
3. **Do:** open the Excel file `QLOPB_MA_Affinity_...xlsx` and click its sheet **Data_Quality**.
4. **You should see** in column B, from row 1: `Research question:`, the question, `Q-MAP run and data record`, and
   `Run ID:` followed by your Run ID. Close Excel with **Don't Save**.
5. **Save:** FILE copies of the PDF and of the `Run_Metadata_...json` file (the full record; you do not need to read
   it) into `Evidence`.

**PASS** if steps 2 and 4 are as described.

### A6: reproduce the run from its Run ID (PIC + FILE)

1. **Do:** in the Workbench, check that **Reproduce Run ID:** shows your Run ID from A3.
2. **Do:** click **Reproduce run (runs it again and compares)**. Wait about half a minute.
3. **You should see** under **Progress / Status** a line starting
   `REPRODUCED: every result table is identical to run <your Run ID>. New run MAAF_...`.
4. **Save:** PIC `A6_Reproduced.png` of **Progress / Status**.
5. **Do:** click **Open Output Folder**. This opens the NEW run's folder (a different Run ID). Copy the file
   `Reproducibility_Report_...csv` to `Evidence` (FILE) and open the copy in Excel.
6. **You should see** two lines starting `Result table` that end with `IDENTICAL`, and a last line `Verdict` with
   `REPRODUCED: ...`. Close Excel with **Don't Save**.
7. **Check:** in File Explorer, open `D:\Q-MAP_V01\Beta_Test\Q-MAP_OUTPUT\Research_Reports`. **You should see** two
   run folders: the first one (from A3) is still there, unchanged.

**PASS** if steps 3, 6 and 7 are as described.

### A7: a run that cannot be reproduced is refused (PIC)

1. **Do:** click in **Reproduce Run ID:**, delete its content and type `MAAF_TEST`. Click **Reproduce run (runs it
   again and compares)**.
2. **You should see** a line starting `Not reproduced: There is no run 'MAAF_TEST' in this Q-MAP registry.` No new
   run folder appears.
3. **Save:** PIC `A7_Refused.png` of **Progress / Status**.

**PASS** if step 2 is as described.

### A8: your research judgement (WRITE)

1. **Do:** read the findings file (A4) once more, including **How to read this**.
2. **Write** in the tracker, row A8: is the output understandable and useful for your research, and is anything
   missing? This is your opinion, not a pass/fail check.

---

## 4. At the end

1. **Do:** close the Workbench with **X**.
2. **Do:** if you will use your round 2c program next, start `D:\Q-MAP_V01\Q-MAP_APP\database_manager.py` and choose
   `D:\Q-MAP_V01\Q-MAP_DATA` and `D:\Q-MAP_V01\Q-MAP_OUTPUT` on **Home** (Q-MAP remembers one pair of folders for
   all its copies).

## 5. What to do next

1. Fill in the tracker (section 1 and rows A1 to A8).
2. Right-click `D:\Q-MAP_V01\Beta_Test\Evidence` → **Send to** → **Compressed (zipped) folder**. Rename the ZIP to
   `Beta_Evidence_<dd_Mmm_yy>.zip`.
3. Send the tracker and the ZIP for review (to ChatGPT).
4. Then:
   - **If every check is PASS:** wait for the review. Accepting the beta and merging stay your decisions.
   - **If any check is FAIL or NOT SURE:** do not repeat it and do not try to fix anything. Write what you saw in
     the tracker (the exact words on the screen are enough), send the files and wait.
   - **If you stopped early (a STOP line):** send what you have and say where you stopped.

You never need to read code or logs: the pictures, the copied files and the words you write are enough to diagnose a
problem.
