# Q-MAP v0.1: Round 2c Test Tracker

**Owner's results sheet | 07-Nov-26 | Build `a202d43d78ed` | Use with
`Q-MAP_v0.1_UAT_Round2c_Easy_Windows_Testing_Guide_07_Nov_26_063903.md`**

Make a copy of this file (or print it) and fill in the copy. Write dates as dd-mmm-yy (for example 08-Nov-26).

## Test session details

| Item | Fill in |
|---|---|
| Date testing started | |
| Date testing finished | |
| Windows version (if known; Claude Code saw Windows 11 Pro 10.0.26300) | |
| Python version: first line in IDLE (test 00b) | |
| New program: "already in place" (Step 1) or download date (Step 2) (test 00a) | |
| Build shown in the PDF (test 23) | |
| Evidence folder name | `Q-MAP_Test_Evidence` |
| Test folder names used (Steps 16 and 23), if not `W8_Round2c` / `W11_Check_2c` | |

## How to use this tracker

Give each test one result:
- **PASS:** the expected result appeared.
- **PASS WITH OBSERVATION:** it worked, but something was unusual or confusing.
- **FAIL:** it did not work as expected.
- **NOT TESTED:** you could not do it, or chose not to. Say why.
- **NOT SURE:** you are unsure; leave it for review.

**Evidence** column: **Picture** = save the named screenshot; **Write down** = no picture, write what you saw;
**Picture if possible** = picture if you can, otherwise write what happened.

Tests marked **(real record)** make a recorded, reversible change in your real Q-MAP records (see the guide).

## Test checklist

| No. | Step | Checklist name | Test | Expected result (short) | Evidence | File name(s) | Your result | What happened |
|---:|---:|---|---|---|---|---|---|---|
| 00a | 1-2 | Download | New program in place | Round-2c checklist file present in `Q-MAP_APP`; old program kept as `Q-MAP_APP_round2` | Write down | - | | |
| 00 | 4 | W11 (before) | Originals before | Names, sizes, Date modified and address bar visible | Picture | `00_Original_Files_Before.png` | | |
| 00b | 5 | - | Python version | First line of IDLE written in the session details | Write down | - | | |
| 01 | 6-7 | V1, V2 | Database Manager and folders | Window opens; both folders green OK; buttons READY | Picture | `01_Database_Manager_Folders.png` | | |
| 02 | 8 | V3 | Workbench home | Same folders; MA Affinity (QLOPB) and Dataset Summary available; MIQP COMING SOON | Picture | `02_Workbench_Home.png` | | |
| 03 | 9 | W2 | OLAELEC details | 1 minute; Accepted by default; "Quality warnings recorded for dataset ..."; "Some dates/times have more than one different value" | Picture | `03_OLAELEC_Details.png` | | |
| 04 | 10 | W14 | RANDOMGAPS | Only "Some days have fewer bars than usual"; no bar-interval warning | Picture | `04_RandomGaps.png` | | |
| 05 | 10 | W15 | EVERYOTHER | "may have another bar interval", row numbers, "cannot show whether"; still 5 minutes | Picture | `05_EveryOther.png` | | |
| 06 | 10 | W16 | GENUINE3M | "has another bar interval" | Picture | `06_Genuine3M.png` | | |
| 07 | 10 | W16 | DAILY0000 | "has another bar interval"; "outside the times of the intraday bars" | Picture | `07_Daily0000.png` | | |
| 08 | 10 | W17 | DAILY0915 | "may have another bar interval"; "a time the intraday bars also use" | Picture | `08_Daily0915.png` | | |
| 09 | 11 | W18 | SPARSE details | "fewer bars" **and** "Long gaps between dates" (2025-04-04 -> 2025-04-14, i.e. 04-Apr-25 to 14-Apr-25); no bar-interval warning | Picture | `09_Sparse_File_Details.png` | | |
| 10 | 11 | W18 | Pattern scan folder and report | `SCAN_20261106_174124` has `Scan_Report_...` and `issues_event...` files; the report lists all six pattern files as Imported | Picture (2) | `10a_Pattern_Scan_Folder.png`, `10b_Pattern_Scan_Report.png` | | |
| 11 | 11 | W18 | Workbench warning | Dataset Summary on NSE:EVERYOTHER: "Validated with warnings"; summary completes | Picture | `11_Workbench_Warning.png` | | |
| 12 | 12 | A4 | Repeat scan | 10 "Unchanged (imported earlier)" incl. 5PAISA, VERANDA, UJJIVAN; AKZOINDIA "Unchanged (rejected earlier)"; nothing newly imported | Picture | `12_Repeat_Scan.png` | | |
| 13 | 13 | W5 | RELIANCE name | `RELIANCE_EQ.csv` shown as NSE:RELIANCE | Picture | `13_Reliance_After_Scan.png` | | |
| 14 | 13 | W5 | Alias registry | Row `RELIANCE,RELIANCE EQ`; closed with Don't Save | Picture | `14_Alias_Registry.png` | | |
| 15 | 14 | W5 | RELIANCE comparison (looks only) | Same original file `RELIANCE_EQ.csv`, same bars (7,746), same From/To (07-Nov-94 to 30-Dec-25); RELIANCE_EQ has the lower number (13 vs 18) | Picture (2) | `15a_Reliance_EQ_Details.png`, `15b_Reliance_Details.png` | | |
| 16 | 14 | W5 | Old duplicate rejected **(real record, your decision)** | Only NSE:RELIANCE_EQ "Rejected by you"; NSE:RELIANCE Active. If deferred: NOT TESTED (decision deferred) | Picture | `16_Old_Reliance_Rejected.png` | | |
| 17 | 15 | W6, W7 | Reject then restore VERANDA and 5PAISA **(real record, restored at once)** | "Rejected by you", then "Available again (restored by you)" | Picture (2) | `17a_Files_Rejected.png`, `17b_Files_Restored.png` | | |
| 18 | 15 | W7 | Workbench after restore | VERANDA and 5PAISA offered; only NSE:RELIANCE offered (both RELIANCE lines if test 16 was deferred) | Picture | `18_Workbench_After_Restore.png` | | |
| 19 | 16 | W8 | Stop scan | Window responds; scan stops without error. If too fast: NOT TESTED: scan too fast to stop | Picture if possible | `19_Stop_Scan.png` | | |
| 20 | 17 | V6 | MA Affinity settings | SMA; MA 10-250; windows 5,10,20,50; one-line help each | Picture | `20_MA_Affinity_Settings.png` | | |
| 21 | 18 | A5 | ICICIBANK Dataset Summary | 02-Jan-98 to 02-Nov-26: 7166 bars; first close 7.86; last close 1387.4 | Picture | `21_ICICIBANK_Summary.png` | | |
| 22 | 19 | A7 | Open output folder | Folder of the run just made opens | Picture | `22_Output_Folder.png` | | |
| 23 | 20 | Build check | PDF build line | "Q-MAP build: qmap 0.1.0rc1 / c2 build a202d43d78ed" | Picture | `23_Build_Fingerprint_PDF.png` | | |
| 24 | 21 | W12 | Close Q-MAP | Both windows close; no error; no empty window | Picture | `24_Closed_Desktop.png` | | |
| 25 | 22 | V14 | Restart and rescan | Folders remembered; Last run folder = latest run; 10 "Unchanged (imported earlier)" (VERANDA, 5PAISA no longer "Available again"); AKZOINDIA "Unchanged (rejected earlier)" | Picture | `25_Restart_Check.png` | | |
| 26 | 23 | W11 part 1 | Originals after | Same names, sizes and Date modified as picture 00 | Picture | `26_Original_Files_After.png` | | |
| 27 | 23 | W11 part 2 | Originals content check | Seven "Already loaded"; AKZOINDIA "Rejected earlier (unchanged)" | Picture | `27_Original_Content_Check.png` | | |

## Notes / issues to discuss

| Test number | What I noticed (in your own words) |
|---|---|
| | |
| | |
| | |

## Final summary

| Question | Your answer |
|---|---|
| Did you complete all tests? | Yes / No / Partly |
| Any FAIL results? | Yes / No |
| Any NOT TESTED results? (which, and why) | |
| Any NOT SURE results? | Yes / No |
| RELIANCE_EQ reject (test 16) | Done / Deferred / Stopped (difference found) |
| Anything confusing or inconvenient? | |
| Evidence ZIP sent to ChatGPT? | Yes / No |
| Owner's acceptance decision | Leave blank until the evidence review: ACCEPT / NOT ACCEPT / PENDING |

## What to send for review

- [ ] ZIP of the `Q-MAP_Test_Evidence` folder (31 pictures if every test was done; fewer if some were NOT TESTED)
- [ ] This completed tracker
- [ ] The IDLE first line (Python version)
- [ ] Short notes about problems or confusing steps

**Reminder:** completing this tracker does not accept the release or approve a GitHub merge. The evidence is reviewed
first; the final decision stays with the Project Owner.
