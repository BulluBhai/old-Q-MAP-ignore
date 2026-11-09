# Q-MAP PR #21 retest tracker (W08 and W14-W18 only)

Guide: `Q-MAP_PR21_Windows_Retest_Guide_09_Nov_26_112803.md` (same folder). Evidence folder:
`D:\Q-MAP_V01\PR10_Test\Evidence_PR21`.

## 1. Test details

| Item | Value |
|---|---|
| Date (dd-mmm-yy) | |
| Python version (IDLE first line) | |
| Commit tested (7 characters) | |

## 2. Results

Result: PASS, FAIL or NOT SURE. Under "Notes", write anything different from the guide.

| Check | What | Evidence | Result | Notes |
|---|---|---|---|---|
| W08R | Include sub-folders ticked but not saved: question shown; **No** scans with the saved setting (3 sub-folders not scanned); **Yes** saves and scans 33 files; box stays ticked; scan report line 1 shows `Sub-folders`, `included` | PIC `W08R_a_Not_Saved_Question.png`; PIC `W08R_b_Scan_With_Saved.png`; PIC `W08R_c_Scan_With_Subfolders.png`; FILE `Scan_Report_...csv` | | |
| W14R | RANDOMGAPS: fewer bars than usual; no bar-interval line | TXT `W14R_RandomGaps.txt` | | |
| W15R | EVERYOTHER: may have another bar interval; cannot show whether | TXT `W15R_EveryOther.txt` | | |
| W16aR | GENUINE3M: has another bar interval; 3 minute(s) | TXT `W16aR_Genuine3M.txt` | | |
| W16bR | DAILY0000: has another bar interval; outside the times of the intraday bars | TXT `W16bR_Daily0000.txt` | | |
| W17R | DAILY0915: may have another bar interval; a time the intraday bars also use | TXT `W17R_Daily0915.txt` | | |
| W18R | SPARSE: fewer bars than usual; no bar-interval line | TXT `W18R_Sparse.txt` | | |
