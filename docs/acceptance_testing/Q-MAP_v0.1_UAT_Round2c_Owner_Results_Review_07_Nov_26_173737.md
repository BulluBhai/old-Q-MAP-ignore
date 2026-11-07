# Q-MAP v0.1: UAT round 2c, review of the owner's Windows test results

**Reviewed 07-Nov-26 by Claude (cloud session). Build `a202d43d78ed`. Documents only; no program, data or registry changed.**

## 1. What was reviewed

| Item | Detail |
|---|---|
| Owner tracker | `Q-MAP_v0.1_UAT_Round2c_Test_Tracker_07_Nov_26_063903.docx` (27,138 bytes), SHA-256 `a3fba6af4ccc69f68945565d650f8c2393d76b33e7e63130449ee28f26eb28a6` |
| Evidence ZIP | `Q-MAP_Test_Evidence.zip` (3,386,322 bytes, 48 files), SHA-256 `8a27ad65e8c3824262d9310c4c8cbd1db8cdbd20322fc1dfa0280bc4a80ce6ea`: 32 pictures, 14 text files (screen text and live-log copies), 1 CSV |
| Testing | 07-Nov-26, evening, owner's laptop (Windows 11 Pro 10.0.26300, Python 3.12.10) |
| Method | Every one of the 27 tracker entries was compared with its pictures and text files, then with the run IDs, dataset numbers and counts in the live logs, and with the expected results of the round-2c guide and checklist. Unclear points were checked against the code (`qmap/data_engine/discovery.py`, `qmap_gui/sources.py`, `qmap_gui/widgets.py`). |

**The two uploads are not added to the repository.** One live-log copy (`19_Stop_Scan.txt`) lists the names of personal
files from a folder on the owner's computer (see finding F1), and the repository is public. Their checksums are recorded
above for traceability. Whether to add the evidence, with that file removed or redacted, is for the owner to decide.

## 2. Overall result

- **No test failed.** The tracker has 30 rows: tests 01-27 plus 00, 00a and 00b.
  - 18 rows: **Verified**.
  - 8 rows: **Verified with observation** (01, 02, 05, 15, 19, 21, 25, 27).
  - 4 rows: **Partly evidenced**, meaning the result is likely but the pictures do not show everything asked (00, 10, 17, 26).
  - None: **Not verified**.
- **Two matters need the owner's decision before acceptance:**
  - **F1:** during the W8 test a personal folder ("My Desktop") was added and scanned by mistake.
  - **F2:** the W11 "originals" checks were not shown to have used the folder of real originals outside `D:\Q-MAP_V01`.
- **One small display defect was found (F3):** after Stop scan the counter shows all files as done. It is reported, not fixed.
- **Windows owner acceptance is not yet complete.** That decision stays with the owner, after ChatGPT's review.

Status key used below:
- **Verified:** the evidence supports the owner's PASS.
- **Verified with observation:** the evidence supports PASS, but something should be noted.
- **Partly evidenced:** the result is likely, but the evidence does not show everything the test asks for.
- **Not verified:** the evidence does not support the test as specified.

## 3. Test by test

| No. | Check | Owner | Review | Evidence and reasoning |
|---|---|---|---|---|
| 00a | New program in place | PASS | Verified | The build in the PDF (test 23) is `a202d43d78ed`, which proves the program in use. The tracker does not record which Step 1 situation applied. |
| 00 | Originals before (W11) | PASS | Partly evidenced | 11 files with sizes and dates are visible, but **no address bar**, so the folder is not identified. See F2. |
| 00b | Python version | recorded | Verified | `Python 3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025, ...) on win32`. |
| 01 | V1, V2 folders | PASS | Verified with observation | Both folders show "OK - this folder can be used" and "Both folders are ready and remembered". The READY labels of the Database Manager modules are below the picture's edge. |
| 02 | V3 Workbench home | PASS | Verified with observation | Folders OK; Dataset Summary and MA Research: MA Affinity (QLOPB) READY. "Market Intelligence (MIQP) COMING SOON" is further down the screen and not in the picture. |
| 03 | W2 OLAELEC | PASS | Verified | Text file: 1 minute; Accepted by default; "Quality warnings recorded for dataset 11"; "Some dates/times have more than one different value" (183 timestamps). Also shows "Rows were not in date order" (expected for this file). |
| 04 | W14 RANDOMGAPS | PASS | Verified | Only "Some days have fewer bars than usual"; no bar-interval warning. |
| 05 | W15 EVERYOTHER | PASS | Verified with observation | "Part of the file may have another bar interval", rows 1126-1163, "cannot show whether", 5 minutes. **Also** "Long gaps between dates" and "Some days have fewer bars than usual". These are correct for this file, but the guide did not mention them. |
| 06 | W16 GENUINE3M | PASS | Verified | "Part of the file has another bar interval", rows 2251-2375, 3-minute steps. |
| 07 | W16 DAILY0000 | PASS | Verified | "has another bar interval"; "outside the times of the intraday bars". |
| 08 | W17 DAILY0915 | PASS | Verified | "may have another bar interval"; "a time the intraday bars also use". |
| 09 | W18 SPARSE | PASS | Verified | "Long gaps between dates 2025-04-04 -> 2025-04-14" and "fewer bars"; no bar-interval warning. |
| 10 | W18 scan folder and report | PASS | Partly evidenced | `10b`: the Scan_Report lists all six pattern files as Imported (source Pattern_Files). **`10a_Pattern_Scan_Folder.png` is missing**, so the scan folder itself is not shown. |
| 11 | W18 Workbench warning | PASS | Verified | Readiness: "READY", "NOTE Validated with warnings ... interval_change_uncertain", 3413 bars. The tracker's note names the wrong text file (11 and 12 are swapped in the notes; the files themselves are correct). |
| 12 | A4 repeat scan | PASS | Verified | Run `SCAN_20261107_145104`: "10 unchanged (imported earlier), 1 unchanged (rejected earlier)"; all 11 files listed; nothing imported. |
| 13 | W5 RELIANCE name | PASS | Verified | "Instrument: NSE:RELIANCE (alias)", dataset 18. |
| 14 | W5 alias registry | PASS | Verified | The Excel picture shows `RELIANCE` / `RELIANCE EQ`. It was opened in Excel, not Notepad. The later scans (tests 25 and 27) show "same validation settings", so the registry was not changed by Excel. |
| 15 | W5 comparison | PASS | Verified with observation | Bars 7746 and 07-Nov-94 to 30-Dec-25 are the same for datasets 13 and 18, and 13 is the lower number. The pictures come from the **Workbench readiness box**, not from Datasets and Storage as the guide asked, so "Original file(s)" is not shown there. It is shown for dataset 13 in picture 16, and dataset 18 is linked to `RELIANCE_EQ.csv` in text file 13. Together this supports the comparison. |
| 16 | W5 reject (real record) | PASS | Verified | Datasets and Storage: dataset 13 "State: Rejected by you", reason `duplicate after alias correction (W5)`, message "Rejected 1 dataset(s) ... Restore undoes it". The Workbench list (18b) offers dataset 18 NSE:RELIANCE Daily and not 13; 18 datasets are offered (19 before). **This real-record decision is now in effect.** |
| 17 | W6/W7 reject and restore | PASS | Partly evidenced | The live log shows "Rejected 2 dataset(s) [2, 17]" then "Restored 2 dataset(s) [2, 17]" (5PAISA = 2, VERANDA = 17), and the status messages agree. The pictures do **not** show the two file rows with "Rejected by you" / "Available again (restored by you)", which was the check the guide asked for. |
| 18 | W7 Workbench after restore | PASS | Verified | 18a-c: the full list is visible; NSE:RELIANCE (18) offered, RELIANCE_EQ (13) not offered; VERANDA and 5PAISA offered. |
| 19 | W8 stop scan | PASS | Verified with observation, see **F1** and **F3** | Run `SCAN_20261107_161523` on `W8_Round2c`: "Stopped by you after 2 file(s); 8 file(s) not processed ... Work already done is kept"; no error. Window responsiveness is not shown, and the folder held 10 files, not 30 or more. Before this, the first scan of `W8_Round2c` found no supported files, and a personal folder was added and scanned (F1). |
| 20 | V6 MA Affinity settings | PASS | Verified | SMA, MA start 10, MA end 250, forward windows 5,10,20,50, a help line under each. |
| 21 | A5 Dataset Summary | PASS | Verified with observation, see **F4** | First run `DSUM_20261107_164410` (wrong start date, as the owner reported). Second run `DSUM_20261107_165125`: CSV Bars 7166, First bar 02-Jan-98, Last bar 02-Nov-26, First close 7.86, Last close 1387.4. **All expected values match.** The date boxes before the run are not pictured; the CSV and the PDF data line (test 23) confirm the period. |
| 22 | A7 output folder | PASS | Verified | Explorer opened `Q-MAP_OUTPUT\Research_Reports\DSUM_20261107_165125` with the CSV, run log, manifest and metadata. |
| 23 | Build in PDF | PASS | Verified | PDF header: "Q-MAP build: qmap 0.1.0rc1 / c2 build a202d43d78ed", source fingerprint `a202d43d78ed...9bea2`, run `MAAF_20261107_170332`. The live log shows 7166 bars, Top-5 SMA-243/244/245/242/246 and 43,579 interactions, **identical to the laptop engine runs** (reproducibility confirmed again). The tracker's "Build shown in the PDF" field was left empty. |
| 24 | W12 close | PASS | Verified | Desktop picture; the owner reports no error and no leftover window. |
| 25 | V14 restart and rescan | PASS | Verified with observation | Run `SCAN_20261107_172216`: 10 "Unchanged (imported earlier)" (VERANDA and 5PAISA included, no longer "Available again"); AKZOINDIA "Unchanged (rejected earlier)". "Folders remembered" and "Last run folder" are stated by the owner but not pictured. |
| 26 | W11 originals after | PASS | Partly evidenced, see **F2** | Same 11 names, sizes and dates as picture 00. No address bar. The owner's note says "Compared the original Market_Files folder" and "I had 11 files". |
| 27 | W11 content check | PASS | Verified with observation, see **F2** | Run `SCAN_20261107_172713` on `W11_Check_2c`: **11 files**, 10 "Already loaded" and AKZOINDIA "Rejected earlier (unchanged)"; every stored copy verified ("stored copy verified, no new copy"). Expected was 8 files (7 + AKZOINDIA). The tracker note says "eight original market files". |

## 4. Findings

**F1: a personal folder was added and scanned during the W8 test (matter for the owner; data protection).**
- **What happened:** the live log shows "Folder added: My Desktop (C:\Users\...\OneDrive - ...\My Desktop)" and run
  `SCAN_20261107_155640`: 27 files "Ignored (not a data file type)" and 9 "Rejected". Both test folders were then
  removed with **Stop using selected folder**, and `W8_Round2c` was added again.
- **What Q-MAP kept:** files rejected at the interpretation stage are **not copied** into Q-MAP_DATA. In
  `discovery.py`, a rejected interpretation is recorded and returned before `ingest_file`. The log has no "Receipt" lines
  for that scan, which confirms it. Q-MAP did record, permanently, for each of those files:
  - its name, size and checksum;
  - the rejection message, which for some files names sheet or column headings;
  - this record is in the Q-MAP_DATA registry and in the scan report folder
    `Q-MAP_OUTPUT\Data_Management\SCAN_20261107_155640`.
- **The source:** it stays listed with its history ("Folder no longer scanned (its history and data are kept)").
- **Not a program fault.** The folder picker opens in the user's home folder (`Path.home()`), and any folder can be chosen.
- **Owner decision needed:** accept these records as they are, or ask for a controlled, reviewed removal. That would be
  a registry change and needs separate approval. **Do not delete anything by hand.**
- **Guide change:** precise folder-picker steps, a path check in the Live Log before scanning, and a stop rule for a
  wrong folder.

**F2: the W11 checks did not clearly use the folder of real originals.**
- **Expected:** the eight original files kept **outside** `D:\Q-MAP_V01`, pictured with the address bar.
- **Recorded:**
  - 11 files, matching `Market_Files` exactly (including `ICICIBANK - Copy` and `ICICIBANK (1)`);
  - no address bar in either picture;
  - the owner's note "Compared the original Market_Files folder".
- **What is proved:** the 11 files in the folder used are unchanged, and Q-MAP holds exactly their content. Every file
  was "Already loaded" or "Rejected earlier (unchanged)", with "stored copy verified".
- **What is not proved:** that a separate folder of original files outside `D:\Q-MAP_V01` is unchanged.
- **Owner decision needed (any one):**
  - confirm that `D:\Q-MAP_V01\Market_Files` is where you keep your originals (then W11 is verified, with 11 files);
  - or repeat tests 00, 26 and 27 on the real originals folder with the revised guide;
  - or record W11 as "verified for Market_Files only".
- **Guide change:** define "originals folder", require the address bar, and set the expected result by file count
  rather than a fixed "seven".

**F3: after Stop scan the progress counter shows every file as done (display defect, low).**
- **Seen:** picture 19 shows "Files done: 10 / 10" and a full green bar, while the message correctly says "Stopped by
  you after 2 file(s); 8 file(s) not processed".
- **Cause:** `discovery.py` calls `progress(len(files), len(files), "")` after the loop, even when the scan was stopped.
- **Effect:** display only. No data is affected, and the message, log and scan report are correct.
- **Not fixed** (this is a documents-only change). The owner decides whether to log it as a correction item.

**F4: the start date was entered wrongly the first time (test 21).**
- **What happened:** the owner reported different results in the first run. The live log shows two Dataset Summary runs
  on dataset 7 (`DSUM_20261107_164410`, then `DSUM_20261107_165125`). Only the second one is in the evidence, and it
  matches every expected value.
- **Likely cause:** the guide asked for the calendar. The calendar opens at the current month, so reaching January 1998
  takes about 28 clicks on `<<` (one year each) and then `<` for the months. That is easy to get wrong.
- **What the program did:** it showed the chosen date in green next to the box ("= dd-Mmm-yyyy"). There is no evidence
  of a program fault.
- **Remains in Q-MAP_OUTPUT:** the first run's folder, which is harmless and should not be deleted.
- **Guide change:** type `02-Jan-98` and `02-Nov-26` instead, read the two green confirmations, picture them before
  running, and record any repeated run with its run ID.

**F5: evidence gaps (not failures).**
- `10a` is missing.
- Test 17 pictures do not show the two file rows.
- Test 15 pictures come from the Workbench instead of Datasets and Storage.
- No address bars in 00 and 26.
- The MIQP line and "Last run folder" are not pictured.
- The tracker fields "Date testing finished", "Build shown in the PDF", the Notes table and the Final summary were left
  empty.
- The text-file notes for tests 11 and 12 are swapped.

The revised guide states exactly what each picture must show.

**F6: wording that may confuse (observation).**
- For `RELIANCE_EQ.csv` the scan list reads "Unchanged (imported earlier) ... Unchanged since 2026-11-07: Imported.
  1 dataset(s) created".
- This repeats the result of its last processing (the alias correction). It is correct, but it can look like a new import.
- No change is proposed now; it is recorded for the owner.

## 5. State of the owner's Q-MAP after round 2c (relevant to any re-test)

- **RELIANCE:** NSE:RELIANCE_EQ (dataset 13) is **Rejected by you**; NSE:RELIANCE (dataset 18) is Active; 18 datasets are offered.
- **Sources:** `W8_Round2c` and `W11_Check_2c` are folder sources. "My Desktop" is no longer scanned, but its history is kept (F1).
- **Q-MAP_OUTPUT:** the two Dataset Summary runs (`DSUM_20261107_164410` with the wrong date, and `DSUM_20261107_165125`)
  and the MA Affinity run `MAAF_20261107_170332` are kept.

The revised guide's expectations take this state into account. These changes are listed, not hidden: see section 7 of
the guide.

## 6. Recommendation

- The round-2c owner tests support the build's behaviour on Windows. **No functional failure was found.**
- Before deciding on Windows owner acceptance, the owner should:
  1. decide F1 (accept the "My Desktop" records, or request a reviewed removal);
  2. decide F2 (confirm `Market_Files` as the originals, or repeat tests 00, 26 and 27);
  3. decide whether F3 becomes a correction item;
  4. optionally re-take the pictures listed in F5 (tests 10a, 17, 15, 25) with the revised guide.
- **Controlled analytical use is not approved by this review.**
