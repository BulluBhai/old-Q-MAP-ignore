# Q-MAP v0.1: Easy Windows Testing Guide

**Round 2c | Owner-friendly version | 07-Nov-26 | Build `a202d43d78ed`**

This guide is a simpler way to carry out the owner checks of the round-2c checklist
(`Q-MAP_v0.1_UAT_Round2c_Owner_Screen_Checklist_07_Nov_26_050239.md`, kept unchanged in the same folder). It covers the same
checks. Where this guide and that checklist differ, the differences are listed at the end ("Differences from the round-2c
checklist"). Record your results in the **Round 2c Test Tracker**
(`Q-MAP_v0.1_UAT_Round2c_Test_Tracker_07_Nov_26_063903.md`).

## What this guide is for

You are checking, on your own Windows laptop, that:
- the Q-MAP windows open;
- the important screens show what they should;
- an analysis runs and its report names the tested build;
- your original market files are not changed.

**You do not need to write code, type commands, read error messages or fix problems.** You will use File Explorer and
IDLE. IDLE is the Python program already on your laptop: you open a named Q-MAP file and press **F5** to start it.

The automatic tests and the engine checks were already run on your laptop by Claude Code on 07-Nov-26 (report
`uat_round2c_laptop_07_Nov_26`, no FAIL). This guide covers only what has to be seen on the screen, plus your own
RELIANCE decision.

## Your role and the review process

1. **You:** follow this guide and give each test one result in the tracker.
2. **You:** save the pictures in one evidence folder.
3. **You:** send the evidence ZIP and the completed tracker to ChatGPT.
4. **ChatGPT:** reviews the results and lists anything that needs a closer look.
5. **Claude:** looks into any confirmed problem and fixes it on a separate GitHub branch, if needed.
6. **You:** make the final acceptance and merge decision. Finishing the tests does not approve a merge.

## Three kinds of test

The tracker shows which kind each test is:
- **Picture:** save the screenshot named in the step.
- **Write down:** no picture needed; write what you saw in the tracker (for example the Python version).
- **Picture if possible:** save a picture if you can; if not, write what happened.

## Before you begin

### What you need

- Your Windows laptop with Python and IDLE (the laptop has Python 3.12.10). **Do not install or change Python for this test.**
- About 60 minutes. You can stop between steps and continue later. If you stop, close Q-MAP with **X**.
- Your `D:\Q-MAP_V01` working area with `Q-MAP_DATA`, `Q-MAP_OUTPUT` and `Market_Files`.
- Notepad (part of Windows) for the two small file checks. Excel also works, but never save in Excel.

### Safety rules

- **Do not delete** any folder or file. Rename only where this guide says so.
- **Do not edit, move or rename** your original market files. You only look at them and copy them.
- **Do not change anything inside** `Q-MAP_DATA`, `Q-MAP_OUTPUT` or `Q-MAP_APP` yourself. Q-MAP writes there on its own;
  that is expected.
- If Excel or Notepad asks **"Save changes?"**, always click **Don't Save**.
- Do not run commands in a black command window.
- If a result is different from this guide: take a picture, write one sentence in the tracker, and **do not try to repair it**.
- If you are unsure, mark **NOT SURE** and carry on. ChatGPT will go through it with you.

### Two actions that change your real Q-MAP records

Most tests only look. Two tests make a **recorded, reversible** change in your real Q-MAP records:
- **Test 15-16 (RELIANCE):** your decision to reject the old duplicate `NSE:RELIANCE_EQ`. It can be undone with **Restore**.
- **Test 17-18 (VERANDA and 5PAISA):** you reject the two files and restore them straight away, in the same step.

Claude Code already tried both on a **copy** of your data on 07-Nov-26: everything matched and nothing else changed. On your
real data, the RELIANCE reject is **your decision**: if you prefer to wait, skip it and mark tests 15-16 **NOT TESTED
(decision deferred)**. Nothing is ever deleted.

Two test folders (`W8_Round2c` and `W11_Check_2c`) will be added to the Sources list. That is expected and harmless: they
contain only copies, Q-MAP recognises them as already loaded, and no new data is created. Leave them in the list.

## Part 1: Prepare

### Step 1. Check whether the new program is already in place

Claude Code already tested the new program in `D:\Q-MAP_V01\Q-MAP_APP` on 07-Nov-26, so this has probably been done already.

1. Open File Explorer and go to `D:\Q-MAP_V01`.
2. If you see **both** `Q-MAP_APP` **and** `Q-MAP_APP_round2`, open
   `Q-MAP_APP\docs\acceptance_testing`. If the file `Q-MAP_v0.1_UAT_Round2c_Owner_Screen_Checklist_07_Nov_26_050239.md`
   is there, **the new program is in place. Skip Step 2 and go to Step 3.** Write "already in place" in the tracker
   (test 00a).
3. Otherwise do Step 2.

### Step 2. Only if needed: keep the old program and download the new one

1. Rename `D:\Q-MAP_V01\Q-MAP_APP` to `Q-MAP_APP_round2`. Do not delete it. (If Windows says the folder is in use, close Q-MAP first.)
2. Open <https://github.com/BulluBhai/Q-MAP/tree/claude/epic-darwin-33o518>, click the green **Code** button,
   then **Download ZIP**.
3. In your Downloads folder, right-click the ZIP → **Extract All** → choose `D:\Q-MAP_V01` → **Extract**.
4. A folder named like `Q-MAP-claude-epic-darwin-33o518` appears in `D:\Q-MAP_V01`. Open it: you should see
   `database_manager.py` directly inside. (If you see another folder with the same name instead, that inner folder is the
   program.) Rename the folder that contains `database_manager.py` to `Q-MAP_APP` and make sure it sits directly in
   `D:\Q-MAP_V01`.
5. Do not touch `Q-MAP_DATA`, `Q-MAP_OUTPUT`, `Market_Files` or the other folders.

### Step 3. Make the evidence folder

In `D:\Q-MAP_V01`, create a new folder named `Q-MAP_Test_Evidence`. All pictures go directly into it (no sub-folders).
Use the file names given in each step.

### Step 4. Picture of your original market files, before testing (test 00)

1. Open the folder where your **real eight original** market files are kept (not a folder inside `D:\Q-MAP_V01`).
2. Click **View → Details** so that names, sizes and **Date modified** are visible.
3. Take a picture of the whole window **including the address bar** (it shows where the folder is).
   Save it as `00_Original_Files_Before.png`.

Do not copy, move or open the originals now.

## Part 2: Start Q-MAP

### Step 5. Open IDLE and write down the Python version (test 00b)

1. Start menu → type `IDLE` → open it.
2. Write the **first line** of the IDLE window in the tracker (for example `Python 3.12.10 ...`). No picture needed.

### Step 6. Start Database Manager (V1)

1. In IDLE: **File → Open** → `D:\Q-MAP_V01\Q-MAP_APP\database_manager.py`.
2. A window with program text opens. You do not need to read it. Press **F5**.
3. If Q-MAP offers to install missing packages, click **Yes**, wait, then follow its message (it may ask you to press F5 again).
   Record this in the tracker; it is not a failure.
4. The **Q-MAP Database Manager** window opens.

If an error appears or nothing opens: take a picture, mark FAIL, and stop. Tell ChatGPT.

### Step 7. Choose the two Q-MAP folders (V2, test 01)

On the Home screen:
1. Click **Browse...** next to Q-MAP_DATA and choose `D:\Q-MAP_V01\Q-MAP_DATA`.
2. Click **Browse...** next to Q-MAP_OUTPUT and choose `D:\Q-MAP_V01\Q-MAP_OUTPUT`.
3. Expected: both show a green **OK**, and the buttons show **READY**.

Picture → `01_Database_Manager_Folders.png`.

### Step 8. Start Analytical Workbench (V3, test 02)

1. In IDLE: **File → Open** → `D:\Q-MAP_V01\Q-MAP_APP\analytical_workbench.py` → **F5**.
2. Expected: the Workbench opens with the same two folders; **MA Affinity (QLOPB)** and **Dataset Summary** are available;
   **MIQP** shows **COMING SOON**.

Picture → `02_Workbench_Home.png`. Keep both windows open.

## Part 3: Data checks in Sources (Database Manager → Sources)

### Step 9. OLAELEC file (W2, test 03)

1. Click the **`Market_Files`** folder line, then the file **`OLAELEC.xlsx`**.
2. Expected on the right: **"Detected timeframe: 1 minute"**, **"Status: Accepted by default"**, a heading
   **"Quality warnings recorded for dataset ..."** and the line
   **"WARNING: Some dates/times have more than one different value"**.

Picture → `03_OLAELEC_Details.png`.

### Step 10. The five pattern example files (W14-W17, tests 04-08)

Click the **`Pattern_Files`** folder line, then each file in turn. Compare the words on the right:

| Test | File | Expected words on the right | Picture |
|---|---|---|---|
| 04 (W14) | `NSE_RANDOMGAPS.csv` | **only** "WARNING: Some days have fewer bars than usual"; **no** "bar interval" warning | `04_RandomGaps.png` |
| 05 (W15) | `NSE_EVERYOTHER.csv` | "WARNING: Part of the file **may** have another bar interval", with row numbers and the words "cannot show whether"; timeframe still **5 minutes** | `05_EveryOther.png` |
| 06 (W16) | `NSE_GENUINE3M.csv` | "WARNING: Part of the file **has** another bar interval" | `06_Genuine3M.png` |
| 07 (W16) | `NSE_DAILY0000.csv` | "WARNING: Part of the file **has** another bar interval" and the words "outside the times of the intraday bars" | `07_Daily0000.png` |
| 08 (W17) | `NSE_DAILY0915.csv` | "...**may** have another bar interval" and the words "a time the intraday bars also use" | `08_Daily0915.png` |

### Step 11. The sparse file, its scan report and the Workbench (W18, tests 09-11)

1. **Test 09.** Still in `Pattern_Files`, click **`NSE_SPARSE.csv`**. Expected: **both** "Some days have fewer bars than usual"
   **and** "Long gaps between dates" (shown as 2025-04-04 -> 2025-04-14, that is 04-Apr-25 to 14-Apr-25), and **no**
   "bar interval" warning. Picture → `09_Sparse_File_Details.png`.
2. **Test 10.** In File Explorer open `D:\Q-MAP_V01\Q-MAP_OUTPUT\Data_Management\SCAN_20261106_174124` (the scan of
   06-Nov-26 in which the six pattern files were first loaded). You should see a file starting with `Scan_Report_` and
   several files starting with `issues_event`.
   - Picture of the folder → `10a_Pattern_Scan_Folder.png`.
   - Right-click the `Scan_Report_...csv` file → **Open with → Notepad** (or Excel). The six pattern files are listed as
     **Imported**. Picture → `10b_Pattern_Scan_Report.png`. Close it; if asked to save, click **Don't Save**.
   - You do not need to open the `issues_event` files.
3. **Test 11.** In the Workbench run **Dataset Summary** on **NSE:EVERYOTHER**. Expected: the readiness box says
   **"Validated with warnings"** and the summary finishes. Picture → `11_Workbench_Warning.png`.

## Part 4: Repeat scan, RELIANCE and restore

### Step 12. Repeat the Market_Files scan (A4, test 12)

1. In Sources click the **`Market_Files`** folder line → **SCAN SELECTED FOLDER NOW**.
2. Expected when it finishes: **10 files "Unchanged (imported earlier)"**, including 5PAISA, VERANDA and UJJIVAN, and
   **AKZOINDIA "Unchanged (rejected earlier)"**. The summary reads "10 unchanged (imported earlier), 1 unchanged (rejected
   earlier)". No file is reported as newly imported.

Picture → `12_Repeat_Scan.png`.

### Step 13. RELIANCE name and alias registry (W5, tests 13-14)

1. **Test 13.** In `Market_Files` click **`RELIANCE_EQ.csv`**: it is shown as **NSE:RELIANCE**. Picture → `13_Reliance_After_Scan.png`.
2. **Test 14.** Click **Open alias registry folder**. Right-click `Instrument_Aliases.csv` → **Open with → Notepad** (or
   Excel). Find the row `RELIANCE,RELIANCE EQ`. Picture → `14_Alias_Registry.png`. Close it; if asked to save, click
   **Don't Save** (this file is part of your Q-MAP records).

### Step 14. RELIANCE duplicate: compare first, then decide (W5, tests 15-16)

1. **Test 15: compare (only looks).** Open **Datasets and Storage**. Find the two **Daily** lines **NSE:RELIANCE_EQ** and
   **NSE:RELIANCE**. Click each one and check:
   - both show the same "Original file(s)": `RELIANCE_EQ.csv`;
   - both have the same number of bars (Claude Code saw **7,746**);
   - both have the same From and To dates (Claude Code saw **07-Nov-94 to 30-Dec-25**; the screen may show another date layout);
   - NSE:RELIANCE_EQ has the **lower** dataset number (Claude Code saw **13**, and **18** for NSE:RELIANCE).

   Pictures → `15a_Reliance_EQ_Details.png` (NSE:RELIANCE_EQ selected) and `15b_Reliance_Details.png` (NSE:RELIANCE selected).

   **If anything differs, stop here. Reject nothing.** Mark test 15 FAIL or NOT SURE, write what differs, and mark test 16
   NOT TESTED.

2. **Test 16: your decision (changes your real records, reversible).** Only if everything matched and you decide to go ahead:
   select **NSE:RELIANCE_EQ only**, type `duplicate after alias correction (W5)` in **Reason (recorded)**, click
   **Reject (reversible)**.
   Expected: NSE:RELIANCE_EQ shows **"Rejected by you"**; NSE:RELIANCE stays **Active**. Picture → `16_Old_Reliance_Rejected.png`.
   - **To undo later** (only if ChatGPT or Claude asks): select NSE:RELIANCE_EQ in Datasets and Storage and click **Restore**.
   - **If you prefer to wait:** do not reject; mark test 16 **NOT TESTED (decision deferred)**.

### Step 15. Reject and restore two files (W6/W7, tests 17-18)

1. Back in **Sources**, click the `Market_Files` folder line. Hold **Ctrl** and click `VERANDA_1min.csv` and `5PAISA_30min.csv`.
2. Type any short reason (for example `UAT 2c test`) in **Reason (recorded)** and click **Reject selected**. Both show
   **"Rejected by you"**. Picture → `17a_Files_Rejected.png`.
3. Keep both selected and click **Restore selected**. Both show **"Available again (restored by you)"**. This label stays
   until the next scan (Step 21). Picture → `17b_Files_Restored.png`.
4. **Test 18.** In the Workbench click **Refresh**. Expected: VERANDA and 5PAISA are offered again, and **only NSE:RELIANCE**
   (not NSE:RELIANCE_EQ) is offered. If you skipped the RELIANCE reject in Step 14, both RELIANCE lines are offered; that is
   expected then, so write "RELIANCE reject deferred". Picture → `18_Workbench_After_Restore.png`.

## Part 5: The window stays usable during a scan

### Step 16. Stop a scan (W8, test 19)

1. In File Explorer create `D:\Q-MAP_V01\W8_Round2c`. (If that name already exists, use `W8_Round2c_2` and write the name in the tracker.)
2. Open `D:\Q-MAP_V01\Market_Files`, select all files (**Ctrl+A**), **Ctrl+C**. Go to `W8_Round2c` and press **Ctrl+V**
   three times (Windows adds "- Copy" to the names), so the folder holds 30 or more files. This copies; nothing is moved.
3. In Sources: **Add folder...** → choose `W8_Round2c` → **SCAN SELECTED FOLDER NOW**, and within 2-3 seconds click **Stop scan**.
4. While it stops, scroll the file list. Expected: the window responds and the scan stops without an error.

Picture → `19_Stop_Scan.png`. If the scan finishes before you can stop it, write **NOT TESTED: scan too fast to stop**.
This is not a failure (stopping was already proved in round 1).

## Part 6: Workbench, analysis and report

### Step 17. MA Affinity settings (V6, test 20)

In the Workbench: **Run an analysis** → **MA Affinity (QLOPB)**. Expected in section 3: SMA, MA start 10, MA end 250,
windows 5,10,20,50, each with a one-line help. Picture → `20_MA_Affinity_Settings.png`.

### Step 18. Dataset Summary of ICICIBANK (A5, test 21)

1. **Dataset Summary** → choose **NSE:ICICIBANK Daily**.
2. Start date: click **Calendar...**, use `<<` to reach **January 1998**, click **2** (02-Jan-98).
3. End date: type `02-Nov-26`.
4. Click **RUN ANALYSIS**.
5. Expected: **7166 bars**, first close **7.86**, last close **1387.4**.

Picture → `21_ICICIBANK_Summary.png`.

### Step 19. Output folder (A7, test 22)

Click **Open Output Folder**. Expected: File Explorer opens the folder of the run you just made. Picture → `22_Output_Folder.png`.

### Step 20. Build in the PDF report (build check, test 23)

1. **Run an analysis** → **MA Affinity (QLOPB)** → **NSE:ICICIBANK Daily**, default settings → **RUN ANALYSIS** (about 30 seconds).
2. **Open Output Folder** → open the PDF report.
3. Expected near the top of page 1: **"Q-MAP build: qmap 0.1.0rc1 / c2 build a202d43d78ed"**.
   If it is different or missing, write exactly what it says. Do not guess.

Picture → `23_Build_Fingerprint_PDF.png`. Close the PDF reader.

## Part 7: Close, restart, originals (at the very end)

### Step 21. Close Q-MAP (W12, test 24)

Close both Q-MAP windows with **X**. Expected: no error, no empty window left behind. Picture of the desktop → `24_Closed_Desktop.png`.

### Step 22. Restart and scan again (V14, test 25)

1. In IDLE open `database_manager.py` → **F5**; open `analytical_workbench.py` → **F5**.
2. Expected: both folders are remembered; in the Workbench **"Last run folder"** shows your latest run (the MA Affinity run of Step 20).
3. In Sources click the **`Market_Files`** folder line → **SCAN SELECTED FOLDER NOW**.
4. Expected: **10 files "Unchanged (imported earlier)"**: 5PAISA, RIVERUSD, BANKNIFTY, OLAELEC, UJJIVAN, VERANDA, the three
   ICICIBANK files and RELIANCE_EQ. VERANDA and 5PAISA no longer say "Available again". **AKZOINDIA "Unchanged (rejected
   earlier)"**. AKZOINDIA is never imported.

Picture → `25_Restart_Check.png`.

### Step 23. Your originals after testing (W11, tests 26-27)

1. **Test 26, quick look.** Open your real originals folder again → **View → Details**, with the address bar. Compare names,
   sizes and Date modified with `00_Original_Files_Before.png`: they must be the same. Picture → `26_Original_Files_After.png`.
2. **Test 27, content check.**
   - In File Explorer create a new, empty folder `D:\Q-MAP_V01\W11_Check_2c`. (If that name already exists, use
     `W11_Check_2c_2` and write the name in the tracker.)
   - **Copy** (Ctrl+C, then Ctrl+V) your eight original files into it. Do not move them.
   - In Sources: **Add folder...** → `W11_Check_2c` → **SCAN SELECTED FOLDER NOW**.
   - Expected: **seven "Already loaded"** and **AKZOINDIA "Rejected earlier (unchanged)"**. This shows that Q-MAP still has
     exactly the same content as your originals.
   - If any file says imported or changed, write it down and stop.

   Picture → `27_Original_Content_Check.png`. Then close both Q-MAP windows with **X**.

## How to take and save a picture

1. Press **Windows key + Shift + S**.
2. Drag around the Q-MAP window or the File Explorer window.
3. Click the pop-up that appears at the bottom right; the Snipping Tool opens.
4. Click the **Save** icon (or press Ctrl+S).
5. Save it in `D:\Q-MAP_V01\Q-MAP_Test_Evidence` with the name from this guide.

If you cannot use the suggested name, use any clear name and write it in the tracker.

## How to record each result

- **PASS:** what you saw matches the expected result.
- **PASS WITH OBSERVATION:** it worked, but something was confusing, slow or unusual. Write what.
- **FAIL:** it clearly did not work as expected, or an error appeared.
- **NOT TESTED:** you could not do it, or chose not to. Write why.
- **NOT SURE:** you are not sure whether it passed. That is fine; ChatGPT will review it with you.

You do not need to decide how serious anything is.

## If something goes wrong

1. Stop that test.
2. Take a picture of what you see, including any message.
3. Mark it **FAIL** or **NOT SURE** and write one sentence.
4. If Q-MAP still works normally, continue with the next test. Steps 21-23 should still be done at the end if possible.
5. Do not change files, settings or code, and do not reinstall anything.
6. If Q-MAP freezes for several minutes, take a picture and close it with **X** if possible.

A problem found during testing is useful evidence, not a mistake by you.

## When you have finished

1. Check that every test in the tracker has a result (NOT TESTED is allowed).
2. Right-click `Q-MAP_Test_Evidence` → **Send to → Compressed (zipped) folder**.
3. Send ChatGPT: the ZIP, the completed tracker, the IDLE first line, and a short note about anything confusing or unexpected.

**Completing the tests does not accept the release or approve the merge of PR #12.** The evidence is reviewed first; the
final decision is yours.

## Checks not repeated in this round

These were tested earlier without the screen and stay valid: V7, V9, V13 (judged on the generated files), and the
engine-tested W1, W3, W4, W6, W9, W10, W13, W19 and V5. **You decide** whether that evidence is enough or whether you
want to see them on screen too; the steps are in the Windows manual under the same names.

## Differences from the round-2c checklist

The checks and expected results are the same as in the round-2c checklist. Only the way of working differs:
- One evidence folder `Q-MAP_Test_Evidence` with numbered file names, instead of `Evidence_Round2b` with sub-folders.
  The tracker lists the checklist name (V1, W2, ...) for every test.
- Step 1 lets you skip the download when the new program is already in place (it was, for Claude Code's tests on 07-Nov-26).
- New test folder names `W8_Round2c` and `W11_Check_2c`, so that folders from earlier rounds are not reused.
- Notepad is suggested for the two CSV checks, and "Don't Save" is stated, so that no file is changed by accident.
- The RELIANCE reject may be deferred (NOT TESTED) if you prefer; the undo (Restore) is described.
- Order: the Dataset Summary and output-folder checks (Steps 18-19) come before the MA Affinity build check (Step 20).
  The result is the same.
