# Q-MAP v0.1: Owner Test Tracker (version 2)

**07-Nov-26 | Build `a202d43d78ed` | Guide: `Q-MAP_v0.1_UAT_Owner_Windows_Testing_Guide_v2_07_Nov_26_173737.md`**

**Written to `docs/standards/Q-MAP_User_Documentation_Standard.md`.**

The tracker has two parts:
- **Part A (sections 1-6): the form for the next owner test.** Its numbers, names, expected results and file names are
  the same as in the guide.
- **Part B (section 7): the record of round 2c (07-Nov-26).** It keeps the Project Owner's results and notes as written,
  next to the review of the evidence.

---

# Part A: form for the next owner test

## 1. Session details

| Item | Fill in |
|---|---|
| Date testing started (dd-mmm-yy) | |
| Date testing finished (dd-mmm-yy) | |
| What was tested (all tests, or which ones) | |
| Windows version (Start → Settings → System → About) | |
| Python version: first IDLE line (test 00b) | |
| Program in place (test 00a) | |
| Build line in the PDF (test 23), copied exactly | |
| Evidence folder | `D:\Q-MAP_V01\Q-MAP_Test_Evidence_v2` |
| Test folder names used, if not `W8_Retest` / `W11_Retest` | |

## 2. Status words (one per test)

| Status | When to use it |
|---|---|
| **PASS** | Everything under "Expected" appeared. |
| **PASS WITH OBSERVATION** | It worked, but something was different, unclear or slow. Write what. |
| **FAIL** | Something under "Expected" did not happen, or an error appeared. |
| **NOT TESTED** | Not done (a STOP, too fast, or not part of this session). Write why. |
| **NOT SURE** | You cannot tell. Write what you saw. This is acceptable. |

## 3. Tests

Evidence: **TXT** text copy · **PIC** picture · **FILE** copy of a Q-MAP file · **WRITE** in this tracker.
All files go in the evidence folder.

| No. | Check (checklist name) | Expected (short) | Evidence and exact file name | Status | Actual result / note |
|---|---|---|---|---|---|
| 00a | Program in place | Checklist file in `Q-MAP_APP\docs\acceptance_testing`; otherwise STOP | WRITE | | |
| 00 | Testing folder before (W11) | `D:\Q-MAP_V01\Market_Files`: 11 files with names, sizes, dates; address bar visible | PIC `00_Original_Files_Before.png` | | |
| 00b | Python version | First IDLE line written in section 1 | WRITE | | |
| 01 | Database Manager, folders (V1, V2) | Both "OK - this folder can be used."; "Both folders are ready and remembered."; READY for Sources (automatic loading), Data Management, Datasets and Storage | PIC `01a_Database_Manager_Folders.png`, PIC `01b_Database_Manager_Ready.png` | | |
| 02 | Workbench home (V3) | Folders OK; Dataset Summary and MA Research: MA Affinity (QLOPB) READY; Market Intelligence (MIQP) COMING SOON | PIC `02a_Workbench_Home.png`, PIC `02b_Workbench_MIQP.png` | | |
| 03 | OLAELEC (W2) | 1 minute; Accepted by default; "Quality warnings recorded for dataset 11:"; "Some dates/times have more than one different value" | TXT `03_OLAELEC_Details.txt` | | |
| 04 | RANDOMGAPS (W14) | Only "Some days have fewer bars than usual"; no "bar interval" | TXT `04_RandomGaps.txt` | | |
| 05 | EVERYOTHER (W15) | "may have another bar interval", rows 1126-1163, "cannot show whether"; 5 minutes | TXT `05_EveryOther.txt` | | |
| 06 | GENUINE3M (W16) | "has another bar interval"; 3 minute(s) | TXT `06_Genuine3M.txt` | | |
| 07 | DAILY0000 (W16) | "has another bar interval"; "outside the times of the intraday bars" | TXT `07_Daily0000.txt` | | |
| 08 | DAILY0915 (W17) | "may have another bar interval"; "a time the intraday bars also use" | TXT `08_Daily0915.txt` | | |
| 09 | SPARSE (W18) | "Long gaps between dates" 2025-04-04 -> 2025-04-14; "fewer bars"; no "bar interval" | TXT `09_Sparse_File_Details.txt` | | |
| 10 | Pattern scan report (W18) | Report of `SCAN_20261106_174124`: six pattern files Imported | PIC `10b_Pattern_Scan_Report.png` | | |
| 11 | Dataset with warnings (W18) | NSE:EVERYOTHER: "READY - every requirement is met."; "NOTE Validated with warnings" | TXT `11_Workbench_Warning.txt` | | |
| 12 | Repeat scan (A4) | "10 unchanged (imported earlier), 1 unchanged (rejected earlier)"; nothing imported | TXT `12_Repeat_Scan_Log.txt` | | |
| 13 | RELIANCE name (W5) | "Instrument: NSE:RELIANCE (alias)"; "Dataset(s): 18" | TXT `13_Reliance_After_Scan.txt` | | |
| 14 | Alias registry (W5) | `RELIANCE,RELIANCE EQ`; closed with Don't Save | PIC `14_Alias_Registry.png` | | |
| 15 | RELIANCE datasets (W5, look only) | 13: Bars 7746, 07-Nov-94 to 30-Dec-25, Original file(s) RELIANCE_EQ.csv, Rejected by you; 18: same, Active | PIC `15a_Reliance_EQ_Details.png`, PIC `15b_Reliance_Details.png` | | |
| 16 | RELIANCE decision (W5) | Already rejected on 07-Nov-26; nothing clicked | WRITE | | |
| 17 | Reject and restore VERANDA, 5PAISA (W6, W7) **(changes records; undone in the test)** | **Both** rows "Rejected by you", then **both** "Available again (restored by you)" | PIC `17a_Files_Rejected.png`, PIC `17b_Files_Restored.png` | | |
| 18 | Workbench after restore (W7) | VERANDA, 5PAISA, NSE:RELIANCE offered; NSE:RELIANCE_EQ not | PIC `18_Workbench_After_Restore.png` (`_part1`... if needed) | | |
| 19 | Stop scan (W8) | Window responds; "Stopped by you after N file(s); M file(s) not processed"; counter may show all done (OW-45). Too fast: NOT TESTED | PIC `19_Stop_Scan.png` | | |
| 20 | MA Affinity settings (V6) | MA types SMA; MA start 10; MA end 250; Forward windows 5,10,20,50; help lines | PIC `20_MA_Affinity_Settings.png` | | |
| 21 | Dataset Summary with the calendar (A5) | Calendar opens at January 1998; > < >> << change month/year; day 2 gives `02-Jan-98` and green "= 02-Jan-1998"; end date green "= 02-Nov-2026"; CSV 7166 bars, 02-Jan-98, 02-Nov-26, 7.86, 1387.4 | PIC `21c_Calendar_January_1998.png`, PIC `21a_Dates_Before_Run.png`, FILE `Dataset_Summary_..._.csv` (PIC `21b_ICICIBANK_Summary.png` optional) | | |
| 22 | Output folder (A7) | Address bar `...Research_Reports > DSUM_...`; CSV, run_log, run_manifest, Run_Metadata | PIC `22_Output_Folder.png` | | |
| 23 | Build in the PDF | "Q-MAP build: qmap 0.1.0rc1 / c2 build a202d43d78ed" | PIC `23_Build_Fingerprint_PDF.png`, FILE `QLOPB_MA_Affinity_Report_....pdf`; WRITE in section 1 | | |
| 24 | Close (W12) | Both windows close; no message; no empty window | WRITE (PIC `24_Closed_Desktop.png` only if something appears) | | |
| 25 | Restart and rescan (V14) | Last run folder = MA Affinity run of test 23; 10 unchanged (imported earlier), 1 unchanged (rejected earlier) | PIC `25a_Last_Run_Folder.png`, TXT `25_Restart_Rescan_Log.txt` | | |
| 26 | Testing folder after (W11) | Same 11 files, names, sizes, dates as test 00 | PIC `26_Original_Files_After.png` | | |
| 27 | Content check (W11) | 11 files: 10 "Already loaded", AKZOINDIA "Rejected earlier (unchanged)"; none Imported | TXT `27_Original_Content_Check.txt` | | |

## 4. Evidence checklist (tick when the file is in the evidence folder)

- [ ] TXT: 03, 04, 05, 06, 07, 08, 09, 11, 12, 13, 25, 27
- [ ] PIC: 00, 01a, 01b, 02a, 02b, 10b, 14, 15a, 15b, 17a, 17b, 18, 19, 20, 21c, 21a, 22, 23, 25a, 26
      (24 and 21b only if applicable)
- [ ] FILE: `Dataset_Summary_..._.csv` (test 21), `QLOPB_MA_Affinity_Report_....pdf` (test 23)

## 5. Ready-to-copy notes (change the numbers to what you see)

| Situation | Note |
|---|---|
| As expected | `PASS - as expected.` |
| Extra correct warning (test 05) | `PASS WITH OBSERVATION - also shows "Long gaps between dates" and "fewer bars".` |
| Scan result (tests 12, 25) | `PASS - 10 unchanged (imported earlier), 1 unchanged (rejected earlier); run SCAN_2026..._......` |
| Stop scan worked (test 19) | `PASS - stopped after N file(s), M not processed; window responded; counter showed all done (OW-45).` |
| Stop too slow (test 19) | `NOT TESTED - scan finished too quickly to stop (one try).` |
| Wrong folder added (tests 19, 27) | `Wrong folder added (path ...), not scanned, stopped using it.` |
| Calendar worked (test 21) | `PASS - calendar opened at January 1998; > < >> << changed month/year; day 2 filled 02-Jan-98 (green = 02-Jan-1998).` |
| Calendar did not work (test 21) | `FAIL (calendar) - the calendar did ... (describe); start date typed instead; nothing was run with a wrong date.` |
| Wrong date run (test 21) | `First run DSUM_... used a wrong start date; repeated as DSUM_... with the correct dates.` |
| Picture in parts | `Picture split into _part1 and _part2.` |
| STOP followed | `STOP at "...": I saw "...". Nothing changed by me.` |

## 6. Notes, summary and next step

Make a copy of this file (or print it) for each session and keep this one blank.

| Test | What I noticed |
|---|---|
| | |
| | |

| Question | Answer |
|---|---|
| All planned tests done? | Yes / No / Partly |
| Any FAIL? (which) | |
| Any NOT TESTED or NOT SURE? (which, why) | |
| Anything confusing? | |
| Evidence ZIP and tracker sent to ChatGPT? | Yes / No |
| Project Owner's acceptance decision | **Leave empty until the evidence has been reviewed.** |

**Next step:** send the ZIP of the evidence folder and this tracker to ChatGPT, then **wait** for the review (guide,
section 6). Do not repeat a test that failed or was not sure; Claude looks into it after the review.

---

# Part B: record of round 2c (07-Nov-26)

## 7. Round 2c results and evidence review

**Sources:**
- the Project Owner's completed tracker `Q-MAP_v0.1_UAT_Round2c_Test_Tracker_07_Nov_26_063903.docx`
  (SHA-256 `a3fba6af4ccc69f68945565d650f8c2393d76b33e7e63130449ee28f26eb28a6`);
- the evidence ZIP `Q-MAP_Test_Evidence.zip` (SHA-256 `8a27ad65e8c3824262d9310c4c8cbd1db8cdbd20322fc1dfa0280bc4a80ce6ea`).

Neither is stored in the repository. Review: `Q-MAP_v0.1_UAT_Round2c_Owner_Results_Review_07_Nov_26_173737.md` (version 2).

**Session details as recorded:**
- started 07 Nov 26;
- Windows 11 Pro 10.0.26300;
- `Python 3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)] on win32`;
- evidence folder `Q-MAP_Test_Evidence`.

**How to read the table:**
- **Result** and **Project Owner's note** are copied from the tracker; notes are shortened only where they list file names.
- File names are the round-2c originals. In round 2c, test 15 was "compare" and test 16 "reject".
- **Sufficient:** "Yes" means the evidence alone supports the result; "Yes, with limitation" means the result is
  supported but a picture does not show everything.

| No. | Check | Completed | Result | Project Owner's note (as written, shortened) | Evidence (round-2c file names) | Sufficient | Note |
|---|---|---|---|---|---|---|---|
| 00a | Program in place | Yes | PASS | - | build line of test 23 | Yes | |
| 00 | Testing folder before | Yes | PASS | - | `00_Original_Files_Before.png` | Yes, with limitation | No address bar; folder identified by the note on test 26 and the file list |
| 00b | Python version | Yes | recorded | - | tracker | Yes | |
| 01 | V1, V2 | Yes | PASS | - | `01_Database_Manager_Folders.png` | Yes, with limitation | READY labels outside the picture |
| 02 | V3 | Yes | PASS | - | `02_Workbench_Home.png` | Yes, with limitation | MIQP line outside the picture |
| 03 | W2 | Yes | PASS | "Additional evidence saved: 03_OLAELEC_Details.txt - full text copied from the Q-MAP file-details screen" | `03_...png`, `.txt` | Yes | |
| 04 | W14 | Yes | PASS | text copy saved | `04_...png`, `.txt` | Yes | |
| 05 | W15 | Yes | PASS | text copy saved | `05_...png`, `.txt` | Yes | Extra correct warnings |
| 06 | W16 | Yes | PASS | text copy saved | `06_...png`, `.txt` | Yes | |
| 07 | W16 | Yes | PASS | text copy saved | `07_...png`, `.txt` | Yes | |
| 08 | W17 | Yes | PASS | - | `08_...png`, `.txt` | Yes | |
| 09 | W18 | Yes | PASS | - | `09_...png`, `.txt` | Yes | |
| 10 | W18 report | Yes | PASS | - | `10b_Pattern_Scan_Report.png` | Yes, with limitation | `10a` not supplied; the report shows the result |
| 11 | W18 Workbench | Yes | PASS | names `12_Repeat_Scan.txt` (notes 11/12 swapped) | `11_...png`, `.txt` | Yes | |
| 12 | A4 | Yes | PASS | names `11_Workbench_Warning.txt` (notes 11/12 swapped) | `12_...png`, `.txt` | Yes | Run SCAN_20261107_145104 |
| 13 | W5 name | Yes | PASS | text copy saved | `13_...png`, `.txt` | Yes | |
| 14 | W5 alias | Yes | PASS | - | `14_Alias_Registry.png` | Yes | |
| 15 | W5 compare | Yes | PASS | "15_Reliance_EQ_Details.txt covering both Reliance_EQ & Reliance" | `15a`, `15b`, `.txt`, with `16` and `13` | Yes | |
| 16 | W5 reject | Yes | PASS | "Dataset 13 (NSE:RELIANCE_EQ) rejected successfully. Dataset 18 (NSE:RELIANCE) retained." | `16_Old_Reliance_Rejected.png` | Yes | Decision in effect |
| 17 | W6/W7 | Yes | PASS | - | `17a`, `17b` | Yes, with limitation | Messages and logged datasets [2, 17] prove reject and restore; the rows are not pictured |
| 18 | W7 Workbench | Yes | PASS | "Dataset list was longer than one screen, so three screenshots were captured ... VERANDA and 5PAISA were available again ... NSE:RELIANCE was available; rejected dataset NSE:RELIANCE_EQ was not offered." | `18a`, `18b`, `18c` | Yes | |
| 19 | W8 | Yes | PASS | "Additional evidence saved: 19_Stop_Scan.txt" | `19_...png`, `.txt` | Yes | Stopped after 2 of 10; counter "10 / 10" (OW-45) |
| 20 | V6 | Yes | PASS | - | `20_MA_Affinity_Settings.png` | Yes | |
| 21 | A5 | Yes | PASS | "Dataset Summary completed successfully for NSE:ICICIBANK Daily. All expected results matched: Bars 7,166; First bar 02-Jan-1998; Last bar 02-Nov-2026; First close 7.86; Last close 1,387.4" | `21_ICICIBANK_Summary.png`, `Dataset_Summary_07_Nov_26_222125.csv` | Yes | Earlier run with a wrong start date repeated correctly. Pop-up calendar checked by the Project Owner and **accepted** |
| 22 | A7 | Yes | PASS | - | `22_Output_Folder.png` | Yes | |
| 23 | Build in PDF | Yes | PASS | "Additional Evidence (text of live log) saved" | `23_...png`, `23_..._Live_log.txt` | Yes | `a202d43d78ed` |
| 24 | W12 | Yes | PASS | "Both ... windows closed normally using the X buttons. No error messages, frozen windows or empty windows appeared." | `24_Closed_Desktop.png` | Yes | |
| 25 | V14 | Yes | PASS | "Q-MAP_DATA and Q-MAP_OUTPUT folders were remembered. Last Run Folder showed the latest MA Affinity analysis. ... 10 files showed Unchanged (imported earlier). AKZOINDIA showed Unchanged (rejected earlier). VERANDA and 5PAISA were no longer shown as Available again." | `25_...png`, `.txt` | Yes | |
| 26 | W11 after | Yes | PASS | "Observation - I had 11 files. Compared the original Market_Files folder ... filenames, sizes, Date modified unchanged." | `26_Original_Files_After.png` | Yes, with limitation | No address bar; same 11 files as test 00 |
| 27 | W11 content | Yes | PASS | "Copied the eight original market files into W11_Check_2c ... Seven files showed Already loaded. AKZOINDIA showed Rejected earlier. No files were newly imported." | `27_...png`, `.txt` | Yes | The log shows the 11 testing files: 10 Already loaded, AKZOINDIA Rejected earlier (unchanged) |

**Totals:**
- 30 rows: tests 01-27 plus 00a, 00 and 00b. All completed; all results supported; 0 FAIL; 0 pending.
- Sufficiency: 24 rows "Yes"; 6 rows "Yes, with limitation" (00, 01, 02, 10, 17, 26).
- No repeat test recommended.

**Windows owner acceptance: ACCEPTED** by the Project Owner on 07-Nov-26 ("I formally accept the Round 2c Windows UAT
results recorded in PR #16."). Controlled analytical use is a separate decision, not yet taken.

**Accepted:** the test 21 pop-up calendar (checked by the Project Owner; no further test).

**Recorded, no action:** Stop scan counter (OW-45, minor future improvement).
