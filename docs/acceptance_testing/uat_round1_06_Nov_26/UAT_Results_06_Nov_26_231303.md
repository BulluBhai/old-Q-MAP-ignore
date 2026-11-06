# Q-MAP v0.1: Windows acceptance testing results

Prepared 06-Nov-26 23:13 for Sandeep (Q-MAP owner). **The acceptance decision is the owner's, not the tester's.**

**How this test was run.** Computer use was not available, so on 06-Nov-26 the owner switched the test to engine level.
Every check marked *engine-tested* was run without the windows. Claude called the same tkinter-free service functions
the screens call (`qmap_gui.source_services`, `registry_services`, `workbench_services`). Those functions in turn
call Q-MAP's own scan, derive, reject/restore and analysis engines. The checks used the real `D:\Q-MAP_V01\Q-MAP_DATA` and
`Q-MAP_OUTPUT` folders and the copies in `D:\Q-MAP_V01`. The driver script ran from a scratch folder with Python
bytecode writing turned off. Nothing in Q-MAP_APP was changed: all 323 program files have the same SHA-256 before and after,
see `08_Engine_Logs\Checksum_comparison.txt`. The console output of each step is in `Evidence\08_Engine_Logs\`, in place of the
screenshots the manual asks for. The checks that need the screen are NOT TESTED and are listed at the end.

## Section 16: final acceptance record

| Item | Value |
|---|---|
| Date(s) of testing (dd-mmm-yy) | 06-Nov-26 |
| Windows version | Windows 11 Pro 10.0.26300 |
| Python version (first line in IDLE) | Python 3.12 (`C:\Users\sandeepb\Python312`). The exact first IDLE line is still to be filled in by the owner |
| Date the ZIP was downloaded | Not recorded (extracted by the owner before the test) |
| Build fingerprint seen in reports (must be `3fa925abf95b`) | `3fa925abf95b`. Seen in every MAAF workbook (Data_Quality), every PDF first page, every Run_Metadata JSON, and the driver's start-up line `qmap 0.1.0rc1 / c2 build 3fa925abf95b` |
| Overall decision | *(owner's decision: ACCEPTED / NOT ACCEPTED)* |
| Outstanding issues (refer to check numbers) | 7 screen checks NOT TESTED (V2, V3, A7, V6, W12, V14, W11). Observations O1 to O7 below, especially O1 (W2, W14-W18 wording not in the Sources file detail) and O2 (W5 duplicate dataset) |

Results: **10 PASS, 14 PASS WITH OBSERVATION, 0 FAIL, 7 NOT TESTED** (31 REQUIRED checks). Optional checks were not run.

| Check | Kind | Result | Notes |
|---|---|---|---|
| V1 | REQUIRED | PASS WITH OBSERVATION | Done by the owner on screen: `01_Start\V1_database_manager_open.png` shows the Home screen and no package message. The folders were already filled in and green before V2 (remembered from an earlier setting on this PC; Q-MAP_DATA was laid out at 23:01:37 on start-up) |
| V2 | REQUIRED | NOT TESTED | Screen step (Browse). The V1 screenshot already shows both folders "OK - this folder can be used" and Sources, Data Management, Datasets and Storage READY, but `V2_folders.png` is not taken |
| V3 | REQUIRED | NOT TESTED | Screen step. Engine side: both analyses (MA Affinity, Dataset Summary) are registered and run |
| W1 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. No question. 8 imported with the expected timeframes, ICICIBANK copies on dataset 7, AKZOINDIA rejected: `low_le_open_close`, source rows 34185/34189 = 08-Nov-25 11:01 and 11:05, low 3262.3 above open 2641.0. Observation: the file imported is `ICICIBANK (1).txt` (first alphabetically), and `ICICIBANK.txt` plus `ICICIBANK - Copy.txt` show "Already loaded". The manual implies the reverse. Log `W1_W3_scan_market_files.txt` |
| W2 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. Detail shows "Detected timeframe: 1 minute", "Validation: Consistent across 20 sampled block(s)", "Status: Accepted by default". **The conflicting-observations warning is not in the file detail** (see O1). It appears in the Exceptions box and in Datasets and Storage (183 timestamps, 366 observations) |
| W3 | REQUIRED | PASS | Engine-tested. Exactly the 5 groups expected: not in alias registry; conflicting observations (OLAELEC); crypto venue unknown (RIVERUSD); time zone assumed (AKZOINDIA, OLAELEC, UJJIVAN); not loaded: data errors (AKZOINDIA) |
| W4 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. The run folder has `Scan_Report_...csv` and `Identification_Exceptions_...csv`. The three ICICIBANK copies are on one row. Copied to `07_Run_Folders\W4_SCAN_20261106_173630`. Opening Explorer and Excel was not done (screen). See O6 on Run ID times |
| W5 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. `Instrument_Aliases.csv` has `RELIANCE,RELIANCE EQ`. After the scan, RELIANCE_EQ.csv is NSE:RELIANCE (alias), dataset 18. Observation O2: the earlier provisional dataset 13 NSE:RELIANCE_EQ stays Active, so the same data are listed and offered twice |
| W6 | REQUIRED | PASS | Engine-tested. Both show "Rejected by you". The Workbench list (the same function as Refresh) no longer offers 5PAISA or VERANDA |
| W7 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. Restored, and the Workbench offers both again. Observation O3: the Result column shows "Already loaded" (the last scan's result), not "Imported" as the manual says |
| W8 | REQUIRED | PASS WITH OBSERVATION | Engine-tested (Stop pressed by a timer after 2.5 s). The scan stopped after the current file: "STOPPED by you: 27 file(s) not processed", 5 processed, no error. The next scan processed all 32. Window responsiveness was not tested (screen) |
| A4 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. All 11 files "unchanged", 9 datasets before and after, none new. Observation O4: the summary says "1 imported" because RELIANCE_EQ's earlier result is carried over (Action = skipped) |
| W19 | REQUIRED | PASS | Engine-tested. Both versions are 2,717 bytes, modified 04-Nov-26 09:03:00.000, with different SHA-256. The second scan says "changed", imports dataset 22 and notes "1 bar(s) differ from dataset 20". Dataset 20 is kept. The third scan says "unchanged". The same date was confirmed |
| V5 | REQUIRED | PASS | Engine-tested. NSE:ICICIBANK Weekly (dataset 23, 1,506 bars) and Monthly (dataset 24, 347 bars), with lineage "from dataset 7". The daily dataset shows "Timeframe measured with the corrected DQ-7 comparison (04-Nov-26)". Market_Files is unchanged (SHA-256) |
| W10 | REQUIRED | PASS | Engine-tested on dataset 15 UJJIVAN: "Rejected by you", then "Active". The stored file is still present and nothing is moved |
| W9 | REQUIRED | PASS | Engine-tested. Readiness is READY with 2 NOTE lines. The CSV "Conflicting timestamps" = 183. Run DSUM_20261106_173936 |
| A5 | REQUIRED | PASS WITH OBSERVATION | Engine-tested with the dates typed (02-Jan-98 to 02-Nov-26): Bars 7166, first close 7.86, last close 1387.4. The Calendar widget was not tested (screen) |
| A7 | REQUIRED | NOT TESTED | Screen step (Open Output Folder). The engine recorded `DSUM_...` folders as the last completed run |
| V6 | REQUIRED | NOT TESTED | Screen step. Engine side: defaults SMA, MA start 10, MA end 250, forward windows 5,10,20,50, each with a one-line help. The description says "exploratory ... Directed IR and the weight scheme are pending owner review" |
| V7 | REQUIRED | PASS | Engine-tested, run MAAF_20261106_173950 in 30 s. All the listed files are present. Summary: "NSE:ICICIBANK Daily (dataset 7), Run MAAF_...", "Daily (Q-MAP registered dataset; not re-aggregated)", Top-5, WARNINGS, LIMITATIONS. Data_Quality: Run ID, "Code build: qmap 0.1.0rc1 / c2 build 3fa925abf95b", dataset SHA-256, source files, lineage. The PDF's first lines are as specified. Copied to `07_Run_Folders\V7_MAAF_20261106_173950` |
| V9 | REQUIRED | PASS | Engine-tested. Weekly (MA end 60, MAAF_20261106_174049) and Monthly (5/24, 3,6,12, MAAF_20261106_174056) both completed. "Bar size" says Weekly or Monthly "(Q-MAP registered dataset; not re-aggregated)". Build 3fa925abf95b |
| V13 | REQUIRED | PASS | Engine-tested (text search instead of Notepad). All six strings found: `3fa925abf95b`, `MAAF_`, `ICICIBANK`, `6cbadc7`, `as_loaded`, `corrected comparison`. `"git_commit": null` |
| W13 | REQUIRED | PASS | Engine-tested. 6 imported, no question. Each one "Detected timeframe: 5 minutes" and "Consistent across 15 sampled block(s)" |
| W14 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. RANDOMGAPS has no interval warning, only `partial_session` (fewer bars), and is not in either interval line of Exceptions. See O1 on wording |
| W15 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. EVERYOTHER: `interval_change_uncertain`, source rows 1126-1163, "cannot show whether". Listed under "A section may have another bar interval..." and still 5 minutes. See O1 |
| W16 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. GENUINE3M (rows 2251-2375, 3-minute steps) and DAILY0000 (rows 2251-2285, "outside the times of the intraday bars, like daily data"): `interval_change_detected`, both under the "has" line. See O1 |
| W17 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. DAILY0915 is under the "may" line, and the detail says "a time the intraday bars also use". See O1 |
| W18 | REQUIRED | PASS WITH OBSERVATION | Engine-tested. SPARSE has no interval warning, and `partial_session` lists the one-bar dates. Issue files: two `interval_change_uncertain` (events 58, 59), two `interval_change_detected` (57, 60), RANDOMGAPS has none, SPARSE has only date_gaps. Scan report: 6 imported. The Workbench readiness on EVERYOTHER says "Validated with warnings: ... interval_change_uncertain" and the summary ran (DSUM_20261106_174210). See O1 |
| W12 | REQUIRED | NOT TESTED | Screen step |
| V14 | REQUIRED | NOT TESTED | Screen step. Engine side: repeated scans of Market_Files report every file unchanged (A4) |
| W11 (parts 1 and 2) | REQUIRED | NOT TESTED | Needs your original files. Part 1: `W11_1_originals_before.png` seems to show `Market_Files`, not your originals' folder (it lists the ICICIBANK copies and RELIANCE_EQ, and the address bar is cut off), so a retake is needed. Part 2 is not done. Supporting evidence on the copies: every Market_Files copy is byte-identical (SHA-256) to the baseline taken before Q-MAP first started, and Q-MAP itself re-read them as "unchanged" in each rescan |
| V4, V8, V10, V11, A6, A8, V12 | OPTIONAL | NOT TESTED | Skipped by instruction |

## Problems and observations

No check FAILED. No error message, crash, frozen state or wrong build appeared in any engine run. "Screenshot" below means the engine log
that replaces it.

| # | Check(s) | What happened | Exact text | Evidence |
|---|---|---|---|---|
| O1 | W2, W14-W18 | The manual expects the warnings in the Sources file-detail pane, in plain words ("Part of the file **may** have another bar interval", "Some days have fewer bars than usual", the OLAELEC conflict warning). The Sources detail (`source_services.file_details`, which the screen shows unchanged) contains none of them. They appear only in the Exceptions box and in Datasets and Storage details, under technical codes. The plain-English titles exist in `qmap_gui/messages.py` but the Sources screen does not use that module. Classifications are all correct. This is a manual-versus-screen wording or location difference, to be confirmed on screen | Dataset text e.g. `interval_change_uncertain: The sampled timeframe is 5m, but the full file contains section(s) on a regular coarser grid; the timestamps cannot show whether...`; `partial_session: Sessions with fewer bars than the usual 65` | `W2_olaelec_akzoindia_detail.txt`, `W13_W17_pattern_files.txt`, `W14_W18_pattern_warnings_and_run_folder.txt` |
| O2 | W5 | After the alias is added, the same file is registered twice: NSE:RELIANCE (dataset 18) and the earlier provisional NSE:RELIANCE_EQ (dataset 13). Both stay Active and both are offered in the Workbench | Workbench list: `'NSE:RELIANCE Daily', 'NSE:RELIANCE_EQ Daily'` | `W5_alias_registry.txt`, `W6_W7_reject_restore.txt`, `A4_rescan.txt` |
| O3 | W7 | After Restore the Result column shows "Already loaded" (the last scan's result), not "Imported" | `5PAISA_30min.csv \| Already loaded` | `W6_W7_reject_restore.txt` |
| O4 | A4, W19 | A scan where nothing was processed still counts "1 imported" in its summary, because an earlier result is carried over (Action = skipped) | `summary: 1 rejected earlier (unchanged), 1 imported, 9 already loaded`; report row `RELIANCE_EQ.csv,unchanged,skipped,Imported` | `A4_rescan.txt` |
| O5 | W1 | Which copy of ICICIBANK counts as "Imported" depends on alphabetical order: `ICICIBANK (1).txt` was imported, and the original name `ICICIBANK.txt` shows "Already loaded" | `ICICIBANK (1).txt \| Imported`, `ICICIBANK.txt \| Already loaded` | `W1_W3_scan_market_files.txt` |
| O6 | all runs | The time in Run IDs is UTC, while the file names and report dates use local time (IST): run `SCAN_20261106_173630` wrote `Scan_Report_06_Nov_26_230651.csv`. The manual's example (`MAAF_20261104_101500`) suggests local time | as shown | any run folder in `07_Run_Folders` |
| O7 | V1 | The Q-MAP folders were already chosen before V2 (remembered setting). Q-MAP_APP has Python's own `__pycache__` files from 22:23 (before this session) and from the V1 start at 23:01. They are not program files, and none were written during the engine tests | — | `V1_database_manager_open.png`, `Checksum_comparison.txt` |

Research note (not a defect, reported by Q-MAP itself): the V7 daily Top-5 is SMA-242 to SMA-246. The workbook warns that these are near-duplicate neighbours.

## Screen checks the owner still needs to do

Save each picture in the folder named, then send the record back so the table above can be updated.

1. **W11 part 1 (before).** Open the folder with your real eight files (View → Details, with the address bar visible) and save `06_Originals\W11_1_originals_before.png` over the old one.
2. **V2.** Database Manager Home: Browse... to `D:\Q-MAP_V01\Q-MAP_DATA`, then to `D:\Q-MAP_V01\Q-MAP_OUTPUT`. Save `01_Start\V2_folders.png`.
3. **V3.** IDLE: open `analytical_workbench.py`, press F5. Save `01_Start\V3_workbench_home.png`.
4. **V6.** Workbench → Run an analysis → MA Affinity (QLOPB). Save part 3 as `04_Workbench\V6_settings.png`.
5. **O1 confirmation (W2, W15).** Sources → `Market_Files` line → click `OLAELEC.xlsx`. Save `02_Sources\W2_olaelec_detail.png`. Then the `Pattern_Files` line → click `NSE_EVERYOTHER.csv`. Save `05_Patterns\W15_everyother.png`. Note whether the conflict warning and the "may have another bar interval" words appear on the right.
6. **A5 and A7.** Workbench → Dataset Summary → NSE:ICICIBANK Daily → Start date Calendar... `<<` to January 1998, click 2 → End date `02-Nov-26` → RUN ANALYSIS. Save `04_Workbench\A5_summary_icicibank.png`. Then click Open Output Folder and save `04_Workbench\A7_output_folder.png`.
7. **W12.** Close both Q-MAP windows with X. Save the desktop as `06_Originals\W12_closed.png`.
8. **V14.** Start both again from IDLE (F5 each). In Sources select `Market_Files` → SCAN SELECTED FOLDER NOW. Save `06_Originals\V14_restart.png`. Expected: every file unchanged, and the Workbench "Last run folder" shows the latest run.
9. **W11 part 1 (after).** Your real folder again, with Details. Save `06_Originals\W11_2_originals_after.png`.
10. **W11 part 2.** Copy your **eight original** files (Ctrl+C / Ctrl+V) into `D:\Q-MAP_V01\W11_Check`. In Sources, Add folder... → `W11_Check` → SCAN. Save `06_Originals\W11_3_content_check.png`. Expected: 7 "Already loaded" and AKZOINDIA "Rejected earlier (unchanged)".

Also please note the first line of the IDLE window (Python version) for section 16.
