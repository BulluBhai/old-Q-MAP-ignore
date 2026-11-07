# Q-MAP v0.1: Owner Test Tracker (version 2)

**07-Nov-26 | Build `a202d43d78ed` | Use with `Q-MAP_v0.1_UAT_Owner_Windows_Testing_Guide_v2_07_Nov_26_173737.md`**

The tracker has two parts:
- **Part A (sections 1-6): a blank form** for the next owner test. Test numbers, names, expected results and file names
  are the same as in the guide.
- **Part B (section 7): the record of round 2c** (07-Nov-26). The owner's results and notes are kept as written, next to
  the review status from `Q-MAP_v0.1_UAT_Round2c_Owner_Results_Review_07_Nov_26_173737.md`.

---

# Part A: blank form

## 1. Session details

| Item | Fill in |
|---|---|
| Date testing started (dd-mmm-yy) | |
| Date testing finished (dd-mmm-yy) | |
| Windows version (Start → Settings → System → About; e.g. Windows 11 Pro 10.0.26300) | |
| Python version: first line in IDLE (test 00b) | |
| Program in place (test 00a): situation and checklist file present? | |
| Build line in the PDF (test 23), copied exactly | |
| Evidence folder name | `Q-MAP_Test_Evidence_v2` |
| Originals folder path and number of files (test 00) | |
| Test folder names used (tests 19 and 27), if not `W8_Retest` / `W11_Retest` | |
| Number of files in the W8 folder (test 19) | |

## 2. Status words (choose one per test)

| Status | Use it when |
|---|---|
| **PASS** | Everything in "Expected" appeared. |
| **PASS WITH OBSERVATION** | It worked, but something was different, unclear or slow. Write what. |
| **FAIL** | Something in "Expected" did not happen, or an error appeared. |
| **NOT TESTED** | You did not do it (STOP, too fast, or chose not to). Write why. |
| **NOT SURE** | You cannot tell. Write what you saw. This is acceptable. |

## 3. Tests

Evidence types: **PIC** = picture (.png), **TXT** = text copy (.txt), **FILE** = file copy (.csv), **WRITE** = write in this tracker.

| No. | Check (name in the checklist) | Expected (short) | Evidence: type and exact file name | Status | Actual result / note |
|---|---|---|---|---|---|
| 00a | Program in place | Checklist file present in `Q-MAP_APP\docs\acceptance_testing`; otherwise STOP | WRITE | | |
| 00 | Originals before (W11) | Full path in the address bar; names, sizes, dates; item count | PIC `00_Originals_Before.png` | | |
| 00b | Python version | First IDLE line written in section 1 | WRITE | | |
| 01 | Database Manager, folders (V1, V2) | Both folders "OK - this folder can be used."; "Both folders are ready and remembered."; READY for Sources (automatic loading), Data Management, Datasets and Storage | PIC `01a_Database_Manager_Folders.png`, PIC `01b_Database_Manager_Ready.png` | | |
| 02 | Workbench home (V3) | Same folders OK; Dataset Summary and MA Research: MA Affinity (QLOPB) READY; Market Intelligence (MIQP) COMING SOON | PIC `02a_Workbench_Home.png`, PIC `02b_Workbench_MIQP.png` | | |
| 03 | OLAELEC (W2) | 1 minute; Accepted by default; "Quality warnings recorded for dataset 11"; "Some dates/times have more than one different value" | PIC `03_OLAELEC_Details.png`, TXT `03_OLAELEC_Details.txt` | | |
| 04 | RANDOMGAPS (W14) | Only "Some days have fewer bars than usual"; no "bar interval" | PIC `04_RandomGaps.png`, TXT `04_RandomGaps.txt` | | |
| 05 | EVERYOTHER (W15) | "may have another bar interval", rows 1126-1163, "cannot show whether"; 5 minutes | PIC `05_EveryOther.png`, TXT `05_EveryOther.txt` | | |
| 06 | GENUINE3M (W16) | "has another bar interval", 3 minute(s) | PIC `06_Genuine3M.png`, TXT `06_Genuine3M.txt` | | |
| 07 | DAILY0000 (W16) | "has another bar interval"; "outside the times of the intraday bars" | PIC `07_Daily0000.png`, TXT `07_Daily0000.txt` | | |
| 08 | DAILY0915 (W17) | "may have another bar interval"; "a time the intraday bars also use" | PIC `08_Daily0915.png`, TXT `08_Daily0915.txt` | | |
| 09 | SPARSE (W18) | "Long gaps between dates" 2025-04-04 -> 2025-04-14 and "fewer bars"; no "bar interval" | PIC `09_Sparse_File_Details.png`, TXT `09_Sparse_File_Details.txt` | | |
| 10 | Pattern scan folder and report (W18) | Folder `SCAN_20261106_174124` with `Scan_Report_...` and `issues_event...`; six pattern files Imported | PIC `10a_Pattern_Scan_Folder.png`, PIC `10b_Pattern_Scan_Report.png` | | |
| 11 | Dataset with warnings (W18) | NSE:EVERYOTHER: "READY - every requirement is met."; "NOTE Validated with warnings" | PIC `11_Workbench_Warning.png`, TXT `11_Workbench_Warning.txt` | | |
| 12 | Repeat scan (A4) | "10 unchanged (imported earlier), 1 unchanged (rejected earlier)"; nothing imported | PIC `12a_Repeat_Scan_Message.png`, PIC `12b_Repeat_Scan_Files.png`, TXT `12_Repeat_Scan_Log.txt` | | |
| 13 | RELIANCE name (W5) | "Instrument: NSE:RELIANCE (alias)"; Dataset(s): 18 | PIC `13_Reliance_After_Scan.png`, TXT `13_Reliance_After_Scan.txt` | | |
| 14 | Alias registry (W5) | `RELIANCE,RELIANCE EQ`; closed with Don't Save | PIC `14_Alias_Registry.png` | | |
| 15 | RELIANCE datasets (W5, look only) | 13: Bars 7746, 07-Nov-94 to 30-Dec-25, Original file(s) RELIANCE_EQ.csv, **Rejected by you**; 18: same bars, dates and file, **Active** | PIC `15a_Reliance_EQ_Details.png`, PIC `15b_Reliance_Details.png` | | |
| 16 | RELIANCE decision (W5) | Already rejected on 07-Nov-26; no click | WRITE | | |
| 17 | Reject and restore VERANDA, 5PAISA (W6, W7) | **Both** rows "Rejected by you", then **both** "Available again (restored by you)"; messages "Rejected 2 dataset(s)..." / "Restored 2 dataset(s)..." | PIC `17a_Files_Rejected.png`, PIC `17b_Files_Restored.png` | | |
| 18 | Workbench after restore (W7) | VERANDA, 5PAISA and NSE:RELIANCE offered; NSE:RELIANCE_EQ not offered | PIC `18_Workbench_After_Restore.png` (or `_part1`...) | | |
| 19 | Stop scan (W8) | Window responds; "Stopped by you after N file(s); M file(s) not processed"; counter may wrongly show all done (F3). Too fast: NOT TESTED | PIC `19_Stop_Scan.png`, TXT `19_Stop_Scan_Log.txt` (only if no personal file names) | | |
| 20 | MA Affinity settings (V6) | SMA; 10; 250; 5,10,20,50; help lines | PIC `20_MA_Affinity_Settings.png` | | |
| 21 | ICICIBANK Dataset Summary (A5) | Before run: green "= 02-Jan-1998", "= 02-Nov-2026"; CSV: 7166 bars, 02-Jan-98, 02-Nov-26, first close 7.86, last close 1387.4 | PIC `21a_Dates_Before_Run.png`, PIC `21b_ICICIBANK_Summary.png`, FILE `Dataset_Summary_..._.csv` | | |
| 22 | Output folder (A7) | Address bar `...Research_Reports > DSUM_...`; CSV, run_log, run_manifest, Run_Metadata | PIC `22_Output_Folder.png` | | |
| 23 | Build in PDF | "Q-MAP build: qmap 0.1.0rc1 / c2 build a202d43d78ed" | PIC `23_Build_Fingerprint_PDF.png`; WRITE in section 1 | | |
| 24 | Close (W12) | Both windows close; no message; no empty window | PIC `24_Closed_Desktop.png` | | |
| 25 | Restart and rescan (V14) | Last run folder = MA Affinity run of test 23; 10 unchanged (imported earlier), 1 unchanged (rejected earlier); VERANDA, 5PAISA not "Available again" | PIC `25a_Last_Run_Folder.png`, PIC `25b_Restart_Rescan.png`, TXT `25_Restart_Rescan_Log.txt` | | |
| 26 | Originals after (W11) | Same path, count, names, sizes, dates as test 00 | PIC `26_Originals_After.png` | | |
| 27 | Originals content check (W11) | Every file except AKZOINDIA "Already loaded"; AKZOINDIA "Rejected earlier (unchanged)"; total = count of test 00; none Imported | PIC `27_Originals_Content_Check.png`, TXT `27_Originals_Content_Check_Log.txt` | | |

## 4. Evidence checklist (tick when the file is in the evidence folder)

- [ ] PIC: 00, 01a, 01b, 02a, 02b, 03-09, 10a, 10b, 11, 12a, 12b, 13, 14, 15a, 15b, 17a, 17b, 18, 19, 20, 21a, 21b, 22, 23, 24, 25a, 25b, 26, 27
- [ ] TXT: 03-09, 11, 12, 13, 19 (if allowed), 25, 27
- [ ] FILE: `Dataset_Summary_..._.csv` (test 21)

## 5. Ready-to-copy notes (edit the numbers you actually see)

| Situation | Note to copy |
|---|---|
| Test passed exactly | `PASS - as expected.` |
| Extra warning, correct for the file (test 05) | `PASS WITH OBSERVATION - also shows "Long gaps between dates" and "fewer bars".` |
| Scan result (tests 12, 25) | `PASS - 10 unchanged (imported earlier), 1 unchanged (rejected earlier); run SCAN_2026..._......` |
| Stop scan worked (test 19) | `PASS - stopped after N file(s), M not processed; window responded; counter showed all done (F3).` |
| Stop too slow (test 19) | `NOT TESTED - scan finished too quickly to stop (one try).` |
| Wrong folder added (tests 19, 27) | `Wrong folder added by mistake (path ...), not scanned, stopped using it.` |
| Wrong date run (test 21) | `First run DSUM_... used a wrong start date; repeated as DSUM_... with the correct dates.` |
| Picture could not show everything | `Picture split into _part1 and _part2.` |
| No separate originals folder (test 00) | `No separate originals folder; Market_Files is my master copy.` |
| You stopped as told | `STOP at step "...": I saw "...". Nothing changed by me.` |

## 6. Notes and final summary

| Test | What I noticed |
|---|---|
| | |
| | |

| Question | Answer |
|---|---|
| All tests done? | Yes / No / Partly |
| Any FAIL? (which) | |
| Any NOT TESTED or NOT SURE? (which, why) | |
| Anything confusing? | |
| Evidence ZIP sent? | Yes / No |
| Owner's acceptance decision | **Leave empty until the evidence has been reviewed.** |

How to use this form: copy this file (or print it), fill in the copy, and keep the original blank.

---

# Part B: record of round 2c (07-Nov-26)

## 7. Round 2c results: owner's tracker and review

**Source:** the owner's completed tracker `Q-MAP_v0.1_UAT_Round2c_Test_Tracker_07_Nov_26_063903.docx` (SHA-256
`a3fba6af...eb28a6`) and the evidence ZIP (SHA-256 `8a27ad65...0ce6ea`).

**Session details as recorded by the owner:**
- started 07 Nov 26;
- Windows 11 Pro 10.0.26300;
- `Python 3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)] on win32`;
- evidence folder `Q-MAP_Test_Evidence`.

Left empty: finished date, test 00a situation, build line, test folder names, Notes and Final summary.

The **Owner** columns are copied from the owner's tracker. Notes are shortened only where they repeat evidence file names.
The **Review** column is from the results review. In the round-2c numbering, test 15 was "compare" and test 16 "reject".

| No. | Check | Owner status | Owner's note (as written, shortened) | Review status | Review remark |
|---|---|---|---|---|---|
| 00a | Program in place | PASS | - | Verified | Build confirmed by test 23. |
| 00 | Originals before | PASS | - | Partly evidenced | 11 files; no address bar (F2). |
| 00b | Python version | Python 3.12.10 ... on win32 | - | Verified | |
| 01 | V1, V2 | PASS | - | Verified with observation | READY labels not in the picture. |
| 02 | V3 | PASS | - | Verified with observation | MIQP line not in the picture. |
| 03 | W2 OLAELEC | PASS | "Additional evidence saved: 03_OLAELEC_Details.txt - full text copied from the Q-MAP file-details screen" | Verified | |
| 04 | W14 | PASS | text copy saved | Verified | |
| 05 | W15 | PASS | text copy saved | Verified with observation | Also shows long gaps and fewer bars (correct). |
| 06 | W16 GENUINE3M | PASS | text copy saved | Verified | |
| 07 | W16 DAILY0000 | PASS | text copy saved | Verified | |
| 08 | W17 | PASS | - | Verified | |
| 09 | W18 SPARSE | PASS | - | Verified | |
| 10 | W18 scan report | PASS | - | Partly evidenced | `10a` missing; `10b` correct. |
| 11 | W18 Workbench | PASS | names `12_Repeat_Scan.txt` (notes 11/12 swapped) | Verified | |
| 12 | A4 | PASS | names `11_Workbench_Warning.txt` (notes 11/12 swapped) | Verified | Run SCAN_20261107_145104. |
| 13 | W5 name | PASS | text copy saved | Verified | |
| 14 | W5 alias | PASS | - | Verified | Opened in Excel; registry unchanged (later scans). |
| 15 | W5 compare | PASS | "15_Reliance_EQ_Details.txt covering both Reliance_EQ & Reliance" | Verified with observation | From the Workbench, not Datasets and Storage. |
| 16 | W5 reject | PASS | "Dataset 13 (NSE:RELIANCE_EQ) rejected successfully. Dataset 18 (NSE:RELIANCE) retained." | Verified | Real-record decision in effect. |
| 17 | W6/W7 | PASS | - | Partly evidenced | Log [2, 17] rejected and restored; rows not pictured. |
| 18 | W7 Workbench | PASS | "Dataset list was longer than one screen, so three screenshots were captured ... VERANDA and 5PAISA were available again ... NSE:RELIANCE was available; rejected dataset NSE:RELIANCE_EQ was not offered." | Verified | |
| 19 | W8 | PASS | "Additional evidence saved: 19_Stop_Scan.txt" | Verified with observation | Stopped after 2 of 10; personal folder scanned earlier (F1); counter fault (F3). |
| 20 | V6 | PASS | - | Verified | |
| 21 | A5 | PASS | "Dataset Summary completed successfully for NSE:ICICIBANK Daily. All expected results matched: Bars 7,166; First bar 02-Jan-1998; Last bar 02-Nov-2026; First close 7.86; Last close 1,387.4" | Verified with observation | First run DSUM_20261107_164410 wrong start date (F4); second run DSUM_20261107_165125 matches. |
| 22 | A7 | PASS | - | Verified | |
| 23 | Build in PDF | PASS | "Additional Evidence (text of live log) saved" | Verified | `a202d43d78ed`; Top-5 and 43,579 interactions as in the laptop runs. |
| 24 | W12 | PASS | "Both ... windows closed normally using the X buttons. No error messages, frozen windows or empty windows appeared." | Verified | |
| 25 | V14 | PASS | "Q-MAP_DATA and Q-MAP_OUTPUT folders were remembered. Last Run Folder showed the latest MA Affinity analysis. ... 10 files showed Unchanged (imported earlier). AKZOINDIA showed Unchanged (rejected earlier). VERANDA and 5PAISA were no longer shown as Available again." | Verified with observation | Folders and last run not pictured. |
| 26 | W11 after | PASS | "Observation - I had 11 files. Compared the original Market_Files folder ... filenames, sizes, Date modified unchanged." | Partly evidenced | Folder not identified (F2). |
| 27 | W11 content | PASS | "Copied the eight original market files into W11_Check_2c ... Seven files showed Already loaded. AKZOINDIA showed Rejected earlier. No files were newly imported." | Verified with observation | Log shows 11 files: 10 Already loaded, AKZOINDIA Rejected earlier (unchanged) (F2). |

**Open points for the owner:**
- F1: the personal folder scanned in error;
- F2: which folder holds the originals;
- F3: the stop-scan counter;
- acceptance decision: pending.
