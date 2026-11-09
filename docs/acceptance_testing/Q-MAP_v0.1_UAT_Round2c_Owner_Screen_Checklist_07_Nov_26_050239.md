# Q-MAP v0.1 — your remaining screen checks (UAT round 2c, build `a202d43d78ed`)

For Sandeep. Only clicking in Q-MAP and File Explorer; no code, no commands, no logs. About 45-60 minutes.
Save every picture with **Win+Shift+S** → drag around the window → click the pop-up → **Save**, using the exact name
and folder given. Your first-round folders and results stay as they are; nothing is deleted.

**Use this checklist.** It replaces the round-2 checklist of 06-Nov-26 and the round-2b checklist of 07-Nov-26 (both kept
unchanged in the same folder). Round 2c corrects two expectations: W18 (step 10) and V14 (step 21). The program is the
same as in round 2b. The program changed once more
on 07-Nov-26 (display only): after a later scan, a restored file shows that scan's result instead of "Available again".

**What changed since round 2, in plain words:**
- You need the **new download** (step 2): build **`a202d43d78ed`**.
- **Three checks are affected and must be done on the new build: A4 (step 11), W7 (step 14) and V14 (step 21).**
- W18 (step 10): SPARSE shows "Long gaps between dates" as well as "fewer bars"; that is correct. Step 10 now also
  includes the scan folder check from the full Windows manual.
- Claude's round-2 engine checks of the other steps (W2, W5 comparison, W14-W18, build check, A5 values) stay valid:
  this change touches only the restored-file wording. You still take the pictures listed below.

## A. Prepare (once)

1. **Keep the old program:** in File Explorer rename `D:\Q-MAP_V01\Q-MAP_APP` to `Q-MAP_APP_round2`. Do not delete it.
   To check the new download: its `docs\acceptance_testing` folder contains this checklist
   (`Q-MAP_v0.1_UAT_Round2c_Owner_Screen_Checklist_07_Nov_26_050239.md`).
2. **Download the new program:** https://github.com/BulluBhai/Q-MAP/tree/claude/epic-darwin-33o518 → green **Code**
   → **Download ZIP**. (If you already downloaded on 07-Nov-26 before this checklist, download again.) Extract it to `D:\Q-MAP_V01\` and rename the
   extracted folder to `Q-MAP_APP`. Keep `Q-MAP_DATA`, `Q-MAP_OUTPUT`, `Market_Files` and the other folders as they are.
3. Create the folder `D:\Q-MAP_V01\Evidence_Round2b` with sub-folders `01_Start`, `02_Sources`, `03_Datasets`,
   `04_Workbench`, `05_Patterns`, `06_Originals`.
4. **W11 "before" picture of your originals.** Open the folder where your **real** eight market files are kept (not
   anything in `D:\Q-MAP_V01`). **View → Details**. Picture the whole window **with the address bar** →
   `06_Originals\W11_1_originals_before.png`.

## B. Start Q-MAP (V1, V2, V3)

5. Start **IDLE**. Write down the **first line** of the IDLE window (for example `Python 3.12.7 ...`).
6. **V1/V2.** IDLE → File → Open → `D:\Q-MAP_V01\Q-MAP_APP\database_manager.py` → press **F5**. On the Home screen click
   **Browse...** next to Q-MAP_DATA and choose `D:\Q-MAP_V01\Q-MAP_DATA`; then **Browse...** next to Q-MAP_OUTPUT and
   choose `D:\Q-MAP_V01\Q-MAP_OUTPUT`. Both show a green "OK" and the buttons show READY.
   Picture → `01_Start\V2_folders.png`.
7. **V3.** IDLE → File → Open → `analytical_workbench.py` → **F5**. The Workbench opens with the same two folders,
   MA Affinity (QLOPB) and Dataset Summary available, MIQP "COMING SOON". Picture → `01_Start\V3_workbench_home.png`.

## C. Sources screen (Database Manager → Sources)

8. **W2.** Click the `Market_Files` folder line, then the file `OLAELEC.xlsx`. On the right you should see
   "Detected timeframe: 1 minute", "Status: Accepted by default", a heading **"Quality warnings recorded for dataset
   ..."** and the line **"WARNING: Some dates/times have more than one different value"**.
   Picture → `02_Sources\W2_olaelec_detail.png`.
9. **W14-W17.** Click the `Pattern_Files` folder line, then each file in turn:
   - `NSE_RANDOMGAPS.csv`: only **"WARNING: Some days have fewer bars than usual"**; no "bar interval" warning →
     `05_Patterns\W14_randomgaps.png`
   - `NSE_EVERYOTHER.csv`: **"WARNING: Part of the file may have another bar interval"** with row numbers and the words
     "cannot show whether"; timeframe still 5 minutes → `05_Patterns\W15_everyother.png`
   - `NSE_GENUINE3M.csv` and `NSE_DAILY0000.csv`: **"WARNING: Part of the file has another bar interval"** (DAILY0000
     also says "outside the times of the intraday bars") → `05_Patterns\W16_genuine3m.png`, `W16_daily0000.png`
   - `NSE_DAILY0915.csv`: **"...may have another bar interval"** and "a time the intraday bars also use" →
     `05_Patterns\W17_daily0915.png`
10. **W18.** Still in `Pattern_Files`: click `NSE_SPARSE.csv`. On the right you should see **both** warnings
    **"Some days have fewer bars than usual"** and **"Long gaps between dates"** (2025-04-04 -> 2025-04-14), and **no**
    "bar interval" warning. Picture → `05_Patterns\W18_sparse.png`.
    **Scan folder of the pattern files.** In File Explorer open `D:\Q-MAP_V01\Q-MAP_OUTPUT\Data_Management\` and then
    the folder **`SCAN_20261106_174124`** (the scan in which the six pattern files were first loaded on 06-Nov-26).
    You should see a file starting with `Scan_Report_` and several files starting with `issues_event`. Double-click the
    `Scan_Report_...csv` file (it opens in Excel): the six pattern files are listed as **Imported**. Close Excel without
    saving. Picture of the folder and of the Excel sheet → `05_Patterns\W18_run_folder.png`. (You do not need to open
    the `issues_event` files: their content was checked by Claude in round 1.)
    **Workbench.** Run **Dataset Summary** on **NSE:EVERYOTHER**: the readiness box says "Validated with warnings" and
    the summary completes → `05_Patterns\W18_workbench.png`.
11. **A4 (repeat on the new build).** Click the `Market_Files` folder line → **SCAN SELECTED FOLDER NOW**. When it
    finishes: **10 files "Unchanged (imported earlier)"**, including 5PAISA, VERANDA and UJJIVAN, which you restored
    earlier, and **AKZOINDIA "Unchanged (rejected earlier)"**. The summary reads "10 unchanged (imported earlier),
    1 unchanged (rejected earlier)" and has **no "imported"**.
    Picture → `02_Sources\A4_rescan.png`.
12. **W5.** Click `RELIANCE_EQ.csv`: it is shown as **NSE:RELIANCE**. Click **Open alias registry folder**, open
    `Instrument_Aliases.csv` in Excel: a row `RELIANCE, RELIANCE EQ`; close Excel.
    Pictures → `02_Sources\W5_after_scan.png`, `W5_alias_csv.png`.
13. **W5, one-time reject of the old duplicate.** Open **Datasets and Storage**. Find the two Daily lines
    **NSE:RELIANCE_EQ** and **NSE:RELIANCE**. Click each: both must show the same "Original file(s)" (`RELIANCE_EQ.csv`),
    the same number of bars and the same From/To dates; NSE:RELIANCE_EQ has the lower dataset number. **If anything
    differs, stop and write it down; reject nothing.** Otherwise select **NSE:RELIANCE_EQ** only, type
    `duplicate after alias correction (W5)` in **Reason (recorded)**, click **Reject (reversible)**. It shows
    "Rejected by you"; NSE:RELIANCE stays Active. Picture → `03_Datasets\W5_old_rejected.png`.
14. **W6 then W7.** Back in Sources, `Market_Files`: hold **Ctrl** and click `VERANDA_1min.csv` and `5PAISA_30min.csv`,
    type any reason, **Reject selected** → both "Rejected by you" (`02_Sources\W6_rejected.png`). Then keep them
    selected → **Restore selected** → both show **"Available again (restored by you)"** (**W7, repeat on the new build**; this label stays until the next
    scan, see step 21). In the Workbench click
    **Refresh**: they are offered again, and only **NSE:RELIANCE** (not RELIANCE_EQ) is offered.
    Pictures → `02_Sources\W7_restored.png`, `04_Workbench\W7_workbench.png`.
15. **W8 (window stays usable).** In File Explorer make `D:\Q-MAP_V01\W8_Round2` and copy 30 or more data files into it
    (Ctrl+C / Ctrl+V of your market-file **copies**; press Ctrl+V several times). In Sources: **Add folder...** →
    `W8_Round2` → **SCAN SELECTED FOLDER NOW**, and within 2-3 seconds click **Stop scan**. While it stops, scroll the
    file list: the window must respond. Picture → `02_Sources\W8_stopped.png`. If the scan finishes before you can
    stop it, write "scan too fast to stop" (the stop itself was already proved in round 1).

## D. Workbench (Analytical Workbench)

16. **V6.** **Run an analysis** → **MA Affinity (QLOPB)**. Section 3 shows the settings with their defaults (SMA, MA
    start 10, MA end 250, windows 5,10,20,50) and a one-line help each. Picture → `04_Workbench\V6_settings.png`.
17. **Build check.** Choose **NSE:ICICIBANK Daily** → **RUN ANALYSIS** (about 30 seconds). Then **Open Output Folder**,
    open the PDF report: the first lines say **"Q-MAP build: qmap 0.1.0rc1 / c2 build a202d43d78ed"**.
    Picture → `04_Workbench\Build_check_pdf.png`.
18. **A5.** **Dataset Summary** → **NSE:ICICIBANK Daily** → Start date: **Calendar...** → use `<<` to reach January 1998
    → click **2** → End date type `02-Nov-26` → **RUN ANALYSIS**. Expected: 7,166 bars, first close 7.86, last close
    1387.4. Picture → `04_Workbench\A5_summary_icicibank.png`.
19. **A7.** Click **Open Output Folder**: the folder of the run you just made opens. Picture →
    `04_Workbench\A7_output_folder.png`.

## E. Close, restart, originals (at the very end)

20. **W12.** Close both Q-MAP windows with **X**. No error, no window left behind. Picture of the desktop →
    `06_Originals\W12_closed.png`.
21. **V14.** Start both again from IDLE (F5 each). Folders are remembered; in the Workbench "Last run folder" shows your
    latest run; in Sources select `Market_Files` → **SCAN SELECTED FOLDER NOW** (**V14, repeat on the new build**).
    `Market_Files` holds 11 files. Expected: **10 files "Unchanged (imported earlier)"** (5PAISA, RIVERUSD, BANKNIFTY,
    OLAELEC, UJJIVAN, VERANDA, the three ICICIBANK files and RELIANCE_EQ; VERANDA and 5PAISA too, although you
    restored them in step 14) and **AKZOINDIA "Unchanged (rejected earlier)"**. AKZOINDIA is never imported. Picture → `06_Originals\V14_restart.png`.
22. **W11 part 1 (after).** Your real originals folder again, **View → Details**, with the address bar →
    `06_Originals\W11_2_originals_after.png`. Size and Date modified must match the "before" picture.
23. **W11 part 2.** Copy your **eight original** files (Ctrl+C / Ctrl+V) into `D:\Q-MAP_V01\W11_Check`. In Sources:
    **Add folder...** → `W11_Check` → **SCAN SELECTED FOLDER NOW**. Expected: seven **"Already loaded"** and AKZOINDIA
    **"Rejected earlier (unchanged)"** (same content as what Q-MAP read before). Picture →
    `06_Originals\W11_3_content_check.png`.

## F. Send back

Zip `Evidence_Round2b` (right-click → Send to → Compressed folder) and send it with the IDLE first line (step 5) and any
step that did not look as described.

## First-round results that stay valid (no need to repeat)

V7, V9, V13 (judged on the generated files), and the engine-tested results of W1, W3, W4, W6, W9, W10, W13, W19 and V5.
These were tested without the screen. **You decide** whether that evidence is enough for you or whether you want to
see them on screen too; if you want to, the steps are in the Windows manual under the same check names.
