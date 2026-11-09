# Q-MAP v0.1: UAT round 2c, review of the Project Owner's Windows test results

**Build `a202d43d78ed`. Documents only: no program, data, registry or research output was changed for this review.**

| Version | Date | Change |
|---|---|---|
| 1 | 07-Nov-26 | First review of the round-2c owner tests |
| 2 | 07-Nov-26 | Consolidated review, changed as follows: |
| | | - Every test is reconciled as completed / result / evidence / sufficiency / decision. |
| | | - The four evidence gaps (tests 00, 10, 17, 26) are assessed one by one. |
| | | - `Market_Files` is recorded as the separate Q-MAP testing folder, and the repeat requests for tests 00, 26 and 27 are withdrawn. |
| | | - The accidental folder scan is recorded only as the Project Owner asked (no investigation, no cleanup). |
| | | - The Stop scan counter is classed as a minor future improvement (OW-45). |
| | | - The test 21 calendar check is added as a separate acceptance item. |
| 3 | 07-Nov-26 | The Project Owner confirmed that the test 21 pop-up calendar was checked and works correctly. The calendar is accepted; section 6 no longer lists it as pending or as a decision. |
| 4 | 07-Nov-26 | The Project Owner formally accepted the round-2c Windows UAT results recorded in PR #16. Recorded in sections 2 and 8 (and D6-27, OW-34). Results, evidence assessment and limitations unchanged. |

## 1. What was reviewed

| Item | Detail |
|---|---|
| Project Owner's tracker | `Q-MAP_v0.1_UAT_Round2c_Test_Tracker_07_Nov_26_063903.docx` (27,138 bytes), SHA-256 `a3fba6af4ccc69f68945565d650f8c2393d76b33e7e63130449ee28f26eb28a6` |
| Evidence ZIP | `Q-MAP_Test_Evidence.zip` (3,386,322 bytes, 48 files: 32 pictures, 14 text copies of screen boxes or the Live Log, 1 CSV), SHA-256 `8a27ad65e8c3824262d9310c4c8cbd1db8cdbd20322fc1dfa0280bc4a80ce6ea` |
| Testing | 07-Nov-26, evening; Project Owner's laptop (Windows 11 Pro 10.0.26300, Python 3.12.10); program in `D:\Q-MAP_V01\Q-MAP_APP` |
| Method | Each tracker row compared with its pictures and text copies, with the run IDs, dataset numbers and counts in the Live Log copies, and with the round-2c expected results. Wording and behaviour that the evidence left open were checked in the program code (read only). |

The tracker and the evidence ZIP are **not** stored in the repository (public). Their checksums above identify them.
Original evidence file names are used unchanged in this review.

**Terms used below:**
- **Market_Files** (`D:\Q-MAP_V01\Market_Files`) is the separate **Q-MAP testing folder**. The Project Owner copied a
  small selection of files into it from a private master database.
- The private master database is **not** part of Q-MAP testing. It is not requested, inspected or referred to by any
  test, and nothing in this review makes a claim about it.

## 2. Result in one paragraph

- **All tests were completed** (tests 01-27 and the preparation records 00a, 00 and 00b), and **no test failed**.
- The Project Owner reported PASS for every test. The evidence supports every reported result. For some tests the
  evidence has a documentation limitation (a picture that does not show everything); none of these limitations leaves an
  important result unverified.
- **No repeat test is needed.**
- The **test 21 pop-up calendar** was checked by the Project Owner and works correctly; it is **accepted** (section 6).
- **Windows owner acceptance: ACCEPTED.** On 07-Nov-26 the Project Owner stated: "I formally accept the Round 2c Windows
  UAT results recorded in PR #16." (section 8).
- The Stop scan counter display is recorded as a minor future improvement (OW-45).

## 3. Reconciliation of all tests

**Sufficiency:**
- **Yes:** the evidence alone supports the result.
- **Yes, with limitation:** the result is supported, and the limitation is about documentation (what a picture shows),
  not about whether the function worked.

| No. | Purpose (checklist name) | Completed | Result reported | Evidence available (original file names) | Sufficient | Limitation / note |
|---|---|---|---|---|---|---|
| 00a | Tested program in place | Yes | PASS | Build line in the PDF (test 23) | Yes | The Step 1 situation was not written in the tracker; the PDF proves the tested build. |
| 00 | Testing folder before testing (W11) | Yes | PASS | `00_Original_Files_Before.png` | Yes, with limitation | See section 4 (no address bar). |
| 00b | Python version | Yes | Recorded | Tracker: `Python 3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025, ...) on win32` | Yes | |
| 01 | Database Manager opens, folders accepted (V1, V2) | Yes | PASS | `01_Database_Manager_Folders.png` | Yes, with limitation | Both folders "OK - this folder can be used." and "Both folders are ready and remembered."; the READY labels lower on the Home screen are not in the picture. |
| 02 | Workbench opens (V3) | Yes | PASS | `02_Workbench_Home.png` | Yes, with limitation | Folders OK; Dataset Summary and MA Research: MA Affinity (QLOPB) READY. The "Market Intelligence (MIQP)" line is further down and not in the picture. |
| 03 | OLAELEC warnings (W2) | Yes | PASS | `03_OLAELEC_Details.png`, `03_OLAELEC_Details.txt` | Yes | 1 minute; Accepted by default; "Quality warnings recorded for dataset 11"; "Some dates/times have more than one different value". |
| 04 | RANDOMGAPS (W14) | Yes | PASS | `04_RandomGaps.png`, `.txt` | Yes | Only "Some days have fewer bars than usual". |
| 05 | EVERYOTHER (W15) | Yes | PASS | `05_EveryOther.png`, `.txt` | Yes | "may have another bar interval", rows 1126-1163, "cannot show whether", 5 minutes. Also "Long gaps between dates" and "fewer bars", which are correct for this file. |
| 06 | GENUINE3M (W16) | Yes | PASS | `06_Genuine3M.png`, `.txt` | Yes | "has another bar interval", rows 2251-2375. |
| 07 | DAILY0000 (W16) | Yes | PASS | `07_Daily0000.png`, `.txt` | Yes | "outside the times of the intraday bars". |
| 08 | DAILY0915 (W17) | Yes | PASS | `08_Daily0915.png`, `.txt` | Yes | "a time the intraday bars also use". |
| 09 | SPARSE (W18) | Yes | PASS | `09_Sparse_File_Details.png`, `.txt` | Yes | "Long gaps between dates 2025-04-04 -> 2025-04-14" and "fewer bars"; no interval warning. |
| 10 | Scan report of the pattern files (W18) | Yes | PASS | `10b_Pattern_Scan_Report.png` | Yes, with limitation | See section 4 (`10a` not supplied). |
| 11 | Dataset with warnings usable (W18) | Yes | PASS | `11_Workbench_Warning.png`, `.txt` | Yes | "READY"; "NOTE Validated with warnings". The tracker notes for 11 and 12 name each other's text file; the files themselves are correct. |
| 12 | Repeat scan (A4) | Yes | PASS | `12_Repeat_Scan.png`, `.txt` | Yes | Run `SCAN_20261107_145104`: "10 unchanged (imported earlier), 1 unchanged (rejected earlier)"; nothing imported. |
| 13 | RELIANCE name (W5) | Yes | PASS | `13_Reliance_After_Scan.png`, `.txt` | Yes | "Instrument: NSE:RELIANCE (alias)", dataset 18. |
| 14 | Alias registry (W5) | Yes | PASS | `14_Alias_Registry.png` | Yes | Row RELIANCE / RELIANCE EQ. Later scans report the same settings, so the registry file was not changed. |
| 15 | RELIANCE comparison (W5) | Yes | PASS | `15a_Reliance_EQ_Details.png`, `.txt`, `15b_Reliance_Details.png`, plus `16` and `13` | Yes | Same bars (7746) and dates (07-Nov-94 to 30-Dec-25); 13 is the lower number; original file shown in `16` (dataset 13) and in `13_...txt` (dataset 18). The pictures come from the Workbench readiness box, not Datasets and Storage. |
| 16 | Reject the old RELIANCE_EQ duplicate (W5) | Yes | PASS | `16_Old_Reliance_Rejected.png` | Yes | Dataset 13 "Rejected by you", reason recorded; 18 Active (also shown in `18b`). **This decision is in effect.** |
| 17 | Reject and restore VERANDA and 5PAISA (W6, W7) | Yes | PASS | `17a_Files_Rejected.png`, `17b_Files_Restored.png` | Yes, with limitation | See section 4 (file rows not pictured). |
| 18 | Workbench after restore (W7) | Yes | PASS | `18a/18b/18c_Workbench_After_Restore_*.png` | Yes | NSE:RELIANCE (18) offered, RELIANCE_EQ (13) not; VERANDA and 5PAISA offered. |
| 19 | Stop scan (W8) | Yes | PASS | `19_Stop_Scan.png`, `19_Stop_Scan.txt` | Yes | Run `SCAN_20261107_161523`: "Stopped by you after 2 file(s); 8 file(s) not processed ... Work already done is kept"; no error. The folder held 10 files, not 30 or more (the paste method in the guide caused this; corrected in guide v2). The counter showed "10 / 10" (section 5). |
| 20 | MA Affinity settings (V6) | Yes | PASS | `20_MA_Affinity_Settings.png` | Yes | SMA, 10, 250, 5,10,20,50, help lines. |
| 21 | Dataset Summary of ICICIBANK (A5) | Yes | PASS | `21_ICICIBANK_Summary.png`, `Dataset_Summary_07_Nov_26_222125.csv` | Yes | Run `DSUM_20261107_165125`: 7166 bars, 02-Jan-98 to 02-Nov-26, first close 7.86, last close 1387.4. An earlier run (`DSUM_20261107_164410`) used a wrong start date, as the Project Owner reported; it was repeated correctly. Pop-up calendar checked by the Project Owner and accepted (section 6). |
| 22 | Output folder opens (A7) | Yes | PASS | `22_Output_Folder.png` | Yes | `Q-MAP_OUTPUT > Research_Reports > DSUM_20261107_165125`. |
| 23 | Build in the PDF report | Yes | PASS | `23_Build_Fingerprint_PDF.png`, `23_Build_Fingerprint_PDF_Live_log.txt` | Yes | "Q-MAP build: qmap 0.1.0rc1 / c2 build a202d43d78ed". Top-5 and 43,579 interactions identical to the laptop engine runs. |
| 24 | Clean close (W12) | Yes | PASS | `24_Closed_Desktop.png`; Project Owner's note | Yes | No message and no leftover window, as reported. |
| 25 | Restart and rescan (V14) | Yes | PASS | `25_Restart_Check.png`, `.txt`; Project Owner's note | Yes | Run `SCAN_20261107_172216`: 10 unchanged (imported earlier), 1 unchanged (rejected earlier); folders remembered and last run folder, as reported. |
| 26 | Testing folder after testing (W11) | Yes | PASS | `26_Original_Files_After.png` | Yes, with limitation | See section 4 (no address bar). |
| 27 | Content check of the testing files (W11) | Yes | PASS | `27_Original_Content_Check.png`, `.txt` | Yes | Run `SCAN_20261107_172713` on a copy of the 11 testing files: 10 "Already loaded", AKZOINDIA "Rejected earlier (unchanged)", each "stored copy verified, no new copy". The guide expected 8 files; the testing folder holds 11, so the count, not the result, differs. |

**Totals:**
- 30 rows: tests 01-27 plus 00a, 00 and 00b.
- Completed: 30. Results supported: 30. Failed: 0. Pending: 0.
- Sufficiency: "Yes" for 24 rows; "Yes, with limitation" for 6 rows (00, 01, 02, 10, 17, 26).

## 4. The four evidence gaps

**Test 00 and test 26: testing folder before and after (W11, part 1)**
- **Available:** two pictures with the same 11 files, in the same order, with the same names, Date modified and Size.
  The Project Owner's note on test 26 identifies the folder as `Market_Files`. The 11 names are exactly the 11 files
  that every scan of `Market_Files` lists (tests 12 and 25).
- **Missing:** the address bar, so the folder path is not in the pictures.
- **Effect:** none on an important result. The folder is identified by the Project Owner's note and by the matching
  file list. The pictures show no change in name, size or date. Test 27 proves independently that the content is unchanged.
- **Classification:** documentation limitation (picture framing), not a verification gap.
- **Resolution:** accept as is. Guide v2 asks for the address bar in future runs. **No repeat.**

**Test 10: scan report of the pattern files (W18)**
- **Available:** `10b_Pattern_Scan_Report.png`. It shows the Scan_Report contents: source `Pattern_Files`, folder
  `D:\Q-MAP_V01\Pattern_Files`, and all six pattern files with Result "Imported", "1 dataset(s) created".
- **Missing:** `10a_Pattern_Scan_Folder.png`, the picture of the scan folder `SCAN_20261106_174124` in File Explorer.
- **Effect:** none. The result that matters (all six files imported) is in `10b`, and tests 04-09 and 11 confirm each
  file's warnings. The folder picture only showed where the report was found.
- **Classification:** documentation limitation.
- **Resolution:** accept as is. Guide v2 no longer requires the folder picture. **No repeat.**

**Test 17: reject and restore VERANDA and 5PAISA (W6, W7)**
- **Available:**
  - `17a` and `17b` show the messages "Rejected 2 dataset(s). They are kept unchanged and no longer offered to analyses;
    Restore undoes it." and "Restored 2 dataset(s). They are offered to analyses again.";
  - the Live Log in both pictures shows "Rejected 2 dataset(s) [2, 17]" then "Restored 2 dataset(s) [2, 17]"
    (dataset 2 = 5PAISA, 17 = VERANDA, as listed in `12_Repeat_Scan.txt`);
  - test 18 shows both offered again in the Workbench;
  - test 25 shows both back to "Unchanged (imported earlier)" after the next scan.
- **Missing:** the file list rows themselves, with "Rejected by you" and "Available again (restored by you)".
- **Effect:** the function (reject, then restore, of exactly those two datasets) is proved by the messages, the logged
  dataset numbers and tests 18 and 25. Only the row wording is not pictured. That wording was tested on the program in
  automated tests and in the round-2c laptop engine checks (W6/W7 PASS).
- **Classification:** documentation limitation.
- **Resolution:** accept as is. Guide v2 asks for the rows in future runs. **No repeat.**

**Repeat recommendation:** none. No important function or result is left unverified, so **no repeat of any test is
recommended**. The earlier requests to repeat tests 00, 26 and 27 are **withdrawn**: those tests concern the Q-MAP
testing folder, which the evidence covers, and not the private master database.

## 5. Stop scan counter (minor future improvement)

- **Seen in test 19:** after **Stop scan**, the Progress / Status area showed "Files done: 10 / 10" and a full green
  bar. The message under it correctly said "Stopped by you after 2 file(s); 8 file(s) not processed (listed in the scan
  report). Work already done is kept.", and the Live Log and scan report agree with the message.
- **Effect:** display only. No data, result or record is affected.
- **Classification:** minor future display correction, agreed by the Project Owner. Recorded as **OW-45** in
  `docs/Outstanding_Work_Register.md`.
- **No program change** in this work, and **no further application testing** for this item.

## 6. The pop-up calendar in test 21 (A5): accepted

- **What changed:** after the round-2c tests were completed, test 21 in guide v2 was changed to use the **Calendar...**
  button. The Start date is typed as `01-Jan-98`, then the calendar is opened; it must open at January 1998. The four
  arrows are checked: `<<` and `>>` move one year, `<` and `>` one month. Clicking day **2** fills `02-Jan-98` and shows
  the green "= 02-Jan-1998". Then the End date `02-Nov-26` is entered. **RUN ANALYSIS** is clicked only when both green
  lines are right. New picture: `21c_Calendar_January_1998.png`; `21a` and `21b` are unchanged.
- **Checked against the program (read only):**
  - the calendar opens at the month of the date already in the box, or at today's month if the box is empty;
  - `<<` `>>` shift 12 months and `<` `>` one month;
  - clicking a day fills the box and closes the calendar;
  - the green confirmation is shown in the form `= dd-Mmm-yyyy`;
  - the window is titled "Choose a date", with **Today**, **Clear** and **Close**;
  - choosing a date never starts an analysis.
- **Status: checked and accepted.** The Project Owner has confirmed that the pop-up calendar was checked and works
  correctly. The calendar is accepted, and nothing needs changing. Round-2c test 21 (completed with typed dates) stays
  PASS.
- **No further calendar test and no repeat of test 21 is needed.** The calendar procedure stays in guide v2 for any
  future owner test.

## 7. Other records (no action requested)

- **Accidental folder scan:** during test 19 a folder outside `D:\Q-MAP_V01` was added and scanned by mistake. The Project
  Owner has asked that this be ignored. It is not investigated further and nothing is cleaned up.
- **Wording observation:** for `RELIANCE_EQ.csv` the scan list reads "Unchanged (imported earlier) ... Imported. 1
  dataset(s) created". This repeats the result of its last processing, so it is correct but can look like a new import.
  Noted only.
- **State after round 2c:**
  - dataset 13 (NSE:RELIANCE_EQ) is "Rejected by you"; 18 datasets are offered;
  - `W8_Round2c` and `W11_Check_2c` are folder sources;
  - the runs `DSUM_20261107_164410`, `DSUM_20261107_165125` and `MAAF_20261107_170332` are kept in `Q-MAP_OUTPUT`.
  - Guide v2 takes this into account.

## 8. Owner acceptance

**Windows owner acceptance of round 2c: ACCEPTED by the Project Owner, 07-Nov-26.**

> "I formally accept the Round 2c Windows UAT results recorded in PR #16."

- The acceptance covers the results, evidence assessment and limitations recorded in this review (sections 3-5). They are
  unchanged.
- The test 21 pop-up calendar was accepted separately (section 6).
- No repeat test and no further screenshot is requested.
- Recorded as decision D6-27 (`docs/decision_log.md`). OW-34 is resolved (`docs/Outstanding_Work_Register.md`).

**What this acceptance does not decide:**
- **controlled analytical use** of Q-MAP v0.1, which is a separate approval and has not been given;
- the merge of any PR;
- the other open owner decisions (D3-15, D6-18, D6-19, D6-20, D6-21, OW-41) and the independent review OW-35.
