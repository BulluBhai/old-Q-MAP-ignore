# Q-MAP PR #21 retest tracker (R1 to R4)

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
| R1 | Add folder opens at `Q-MAP_APP_PR21` first, then at `W_Pattern`, also after a restart | PIC `R1a_First_Open.png`; PIC `R1b_Second_Open.png` | | Preferred first folder, if different (decision D-4): |
| R2 | Include sub-folders ticked but not saved: question shown; **No** scans with the saved setting; **Yes** saves and scans 33 files; box stays ticked | PIC `R2a_Not_Saved_Question.png`; PIC `R2b_Scan_With_Saved.png`; PIC `R2c_Scan_With_Subfolders.png` | | |
| R3 | Whole-file warnings in the details of the six pattern files | TXT `R3_RandomGaps.txt`, `R3_EveryOther.txt`, `R3_Genuine3M.txt`, `R3_Daily0000.txt`, `R3_Daily0915.txt`, `R3_Sparse.txt` | | |
| R4 | Scan report first line: `Sub-folders`, `included`, `Skip patterns`, `none` | FILE `Scan_Report_...csv` | | |
