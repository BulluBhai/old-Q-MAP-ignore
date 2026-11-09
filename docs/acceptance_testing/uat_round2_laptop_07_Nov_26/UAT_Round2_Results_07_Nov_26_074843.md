# Q-MAP v0.1: UAT round 2 results (engine level)

Prepared 07-Nov-26 07:48 for Sandeep (Q-MAP owner). **The acceptance decision is the owner's.**

**Build:** `qmap 0.1.0rc1 / c2 build 21d31f0fe259` (source fingerprint `21d31f0fe2598904...`), loaded from
`D:\Q-MAP_V01\Q-MAP_APP`. This was confirmed before any test, and the same value is in every report made in this round.

**Method:** the same method as round 1. The same tkinter-free service functions the screens call were run on the real
Q-MAP_DATA and Q-MAP_OUTPUT, with no windows. A driver script ran from a scratch folder with bytecode writing off. In
step 8 the driver passes `ss.dataset_warnings(...)` into `file_details`, exactly as `sources.py` now does (lines 288
and 323). Console output of each step is in `08_Engine_Logs\`.

**Nothing changed outside the test:** all 334 program files in Q-MAP_APP have the same SHA-256 before and after, and
the `__pycache__` count stayed at 68. All 11 Market_Files copies are byte-identical to the round-1 baseline taken before
Q-MAP first ran. Your originals were not touched. Nothing was rejected in Datasets and Storage (step 13 is yours). The only
state changes are the ones step 14 asks for (VERANDA and 5PAISA rejected, then restored) and the new run folders.

## Results

| Step | Check | Result | What the engine showed |
|---|---|---|---|
| 8 | W2 | PASS (engine-tested) | OLAELEC.xlsx: "Detected timeframe: 1 minute", "Status: Accepted by default", "Quality warnings recorded for dataset 11:", "WARNING: Some dates/times have more than one different value" (183 timestamps, 366 observations). Also "WARNING: Rows were not in date order" |
| 9 | W14 | PASS (engine-tested) | RANDOMGAPS: only "WARNING: Some days have fewer bars than usual", no bar-interval warning |
| 9 | W15 | PASS (engine-tested) | EVERYOTHER: "WARNING: Part of the file may have another bar interval", source rows 1126-1163, "cannot show whether". Timeframe still 5 minutes. It also shows "Long gaps between dates" and "Some days have fewer bars than usual" |
| 9 | W16 | PASS (engine-tested) | GENUINE3M (rows 2251-2375, 3-minute steps) and DAILY0000 (rows 2251-2285, "outside the times of the intraday bars"): "WARNING: Part of the file has another bar interval" |
| 9 | W17 | PASS (engine-tested) | DAILY0915: "...may have another bar interval", "a time the intraday bars also use" |
| 10 | W18 | PASS WITH OBSERVATION (engine-tested) | SPARSE: "Some days have fewer bars than usual" and no bar-interval warning, **but also "WARNING: Long gaps between dates" (2025-04-04 -> 2025-04-14)**. The checklist says "only". Workbench Dataset Summary on NSE:EVERYOTHER: readiness READY with "Validated with warnings: ... interval_change_uncertain ...", completed (DSUM_20261107_021605) |
| 11 | A4 | PASS WITH OBSERVATION (engine-tested) | Summary "10 unchanged (imported earlier), 1 unchanged (rejected earlier)", with no stand-alone "imported". 19 datasets before and after. The scan report gives every file "Unchanged (imported earlier)" or "Unchanged (rejected earlier)". **On the Sources list, though, 5PAISA, VERANDA and UJJIVAN show "Available again (restored by you)" instead of "Unchanged (imported earlier)"**, because they were restored in round 1 (W7 and W10). The restored label stays after later scans (R2-O2) |
| 12 | W5 identity | PASS (engine-tested) | RELIANCE_EQ.csv is shown as NSE:RELIANCE (alias), dataset 18. `Instrument_Aliases.csv` has the row `RELIANCE,RELIANCE EQ` |
| 12 | W5 comparison (for your step-13 decision) | REPORTED, nothing rejected | See the comparison table below. The two datasets hold identical data; only the instrument name differs |
| 14 | W6 / W7 wording | PASS WITH OBSERVATION (engine-tested) | Reject: both "Rejected by you" ("Status: Rejected by you (reversible: Restore)") and both gone from the Workbench list. Restore: both "Available again (restored by you)" ("...; nothing was imported again") and offered again. **The Workbench still offers NSE:RELIANCE_EQ as well as NSE:RELIANCE**, as expected while step 13 is not done |
| 17 | Build in PDF | PASS (engine-tested) | MAAF_20261107_021752: the PDF's first line has "Q-MAP build: qmap 0.1.0rc1 / c2 build 21d31f0fe259". The workbook Data_Quality has "Code build: ... 21d31f0fe259". The Top-5 is the same as round 1 (SMA-243, 244, 245, 242, 246) |
| 18 | A5 values | PASS WITH OBSERVATION (engine-tested) | DSUM_20261107_021832: Bars 7166, first close 7.86, last close 1387.4 (02-Jan-98 to 02-Nov-26). The dates were typed, so the Calendar widget is untested (screen) |

### W5: the two RELIANCE datasets compared (step 13 input)

| Item | dataset 13 | dataset 18 | Same? |
|---|---|---|---|
| Instrument | NSE:RELIANCE_EQ | NSE:RELIANCE | different (the alias correction) |
| Original file(s) | RELIANCE_EQ.csv (original-file dataset 12) | RELIANCE_EQ.csv (original-file dataset 12) | same |
| Bars / From / To | 7746 / 07-Nov-94 / 30-Dec-25 | 7746 / 07-Nov-94 / 30-Dec-25 | same |
| Processing / settings fingerprint | auto_1b06649ffe7f@1+c2 / vs2:7d8e2f3b9e747e4c | same | same |
| Validation warnings | date_gaps 1997-10-01 -> 1997-10-09 | same | same |
| Storage / state | Permanent / Active | Permanent / Active | same |
| Data, all 8 columns, all 7,746 rows | | | identical (compared value by value) |
| Stored file SHA-256 | 20a64ec8... | 0060375a... | different. Each stored copy carries its own instrument and run, while the data inside are identical |
| Created by | SCAN_20261106_173630 (W1) | SCAN_20261106_173739 (W5) | — |

Dataset 13 (NSE:RELIANCE_EQ) has the lower number, as step 13 expects. Nothing in the checklist's comparison differs, so
by the checklist's rule step 13 may go ahead. Whether to reject is your decision.

## Observations (round 2)

| # | Step | What happened | Exact text |
|---|---|---|---|
| R2-O1 | 10 (W18) | SPARSE shows a second warning besides "fewer bars" | `WARNING: Long gaps between dates` / `2025-04-04 -> 2025-04-14` |
| R2-O2 | 11 (A4), 21 (V14) | Files restored in round 1 (5PAISA, VERANDA, UJJIVAN) keep "Available again (restored by you)" in the Sources list after later scans, so not every file reads "Unchanged (imported earlier)" as steps 11 and 21 expect. The scan report itself says "Unchanged (imported earlier)" | `5PAISA_30min.csv \| Available again (restored by you)` |
| R2-O3 | 14 | The Workbench offers both RELIANCE datasets until step 13 is done | `NSE:RELIANCE Daily`, `NSE:RELIANCE_EQ Daily` |
| R2-O4 | all | Run IDs still use UTC time while file names use local time (round-1 O6, not changed) | run `MAAF_20261107_021752`, file `..._07_Nov_26_074752` |

Round-1 observations O1 (warnings not in the Sources detail), O3 (Restore wording) and O4 ("1 imported" in an unchanged
scan) are resolved in this build, as far as the engine shows.

## Screen steps the owner still has to do

From the round-2 checklist:
- **Prepare:** step 4 (W11 before picture of your real folder, with the address bar), step 5 (IDLE first line).
- **Start:** steps 6 and 7 (V1/V2, V3).
- **Sources pictures:** steps 8 to 12 (W2, W14-W18, A4, W5). Engine results above say what you should see.
- **Your decision:** step 13 (reject NSE:RELIANCE_EQ or not).
- **W6/W7 pictures:** step 14.
- **W8:** step 15 (window responsiveness).
- **Workbench:** step 16 (V6), step 17 (Build_check_pdf picture), step 18 (Calendar), step 19 (A7).
- **Close and restart:** steps 20 and 21 (W12, V14).
- **Originals:** steps 22 and 23 (W11 parts 1 and 2).
