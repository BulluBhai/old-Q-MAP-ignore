# Q-MAP PR #10: acceptance tracker W1 to W18, version 2

**08-Nov-26 | Guide: `Q-MAP_Windows_IDLE_Acceptance_Guide_v2_08_Nov_26_151819.md` (same folder)**

**Written to `docs/standards/Q-MAP_User_Documentation_Standard.md`.**

This tracker replaces `Q-MAP_DQ7-DQ10_Acceptance_Checklist_03_Nov_26_120000.md`, which is kept unchanged as a record.
Check numbers, evidence file names and the order are the same as in the guide. Every evidence file goes into
`D:\Q-MAP_V01\PR10_Test\Evidence`.

**W19 is not an owner check** (guide section 5, Part C): it is covered by automated tests only, and its row below is
already filled in. Do not perform it, and do not change any Windows permission or security setting.

How to fill it in:
- **Result:** `PASS`, `FAIL` or `NOT SURE`; `NT` if not tested (say why in Notes).
- **Notes:** only if something differs. Ready-to-copy wording is given where useful; replace `...` with what you saw.

## 1. Session

| Item | Your entry |
|---|---|
| Date (dd-mmm-yy) | |
| Windows version (Start → Settings → System → About) | |
| Python version (the IDLE window's first line) | |
| Commit tested (guide section 4.1, step 8) | |
| Folders used (guide section 4.2) | `D:\Q-MAP_V01\PR10_Test\Q-MAP_DATA` and `...\Q-MAP_OUTPUT` (change if different) |

## 2. Checks

| # | Check | Evidence (exact file names) | Result | Notes |
|---|---|---|---|---|
| W00 | New folders chosen; files copied (guide 4.2, 4.3) | PIC `W00_Folders.png`; PIC `W00_Market_Before.png` | | |
| W1 | First scan of `W_Market`: no question; results as in the guide | PIC `W01_Scan_Result.png` (and `W01_Question.png` only if a question appeared) | | e.g. `FILE ... shows ... instead of ...` |
| W2 | OLAELEC details | TXT `W02_OLAELEC.txt` | | |
| W3 | Exceptions box | TXT `W03_Exceptions.txt` | | |
| W4 | Scan reports | FILE `Scan_Report_....csv`; FILE `Identification_Exceptions_....csv` | | |
| W5 | Alias registry: RELIANCE_EQ becomes NSE:RELIANCE | PIC `W05_Reliance.png` | | |
| W6 | Reject two files; Workbench does not offer them | PIC `W06_Rejected.png`; PIC `W06_Workbench.png` | | |
| W7 | Restore them; Workbench offers them again | PIC `W07_Workbench.png` | | |
| W8 | Stop a scan | PIC `W08_Stopped.png` | | `finished before Stop` if it was too quick (not a failure) |
| W9 | Dataset Summary of OLAELEC: READY with notes; Conflicting timestamps = 183 | PIC `W09_Readiness.png`; FILE `Dataset_Summary_....csv` | | value seen: `...` |
| W10 | Reject and Restore in Datasets and Storage | PIC `W10_Rejected.png`; PIC `W10_Restored.png` | | |
| W11 | Files in `W_Market` unchanged | PIC `W11_Market_After.png` (compare with `W00_Market_Before.png`) | | file that differs: `...` |
| W13 | Scan of `W_Pattern`: six Imported | PIC `W13_Pattern_Scan.png` | | |
| W14 | RANDOMGAPS: no interval warning | TXT `W14_RandomGaps.txt` | | |
| W15 | EVERYOTHER: "may have another bar interval" | TXT `W15_EveryOther.txt` | | |
| W16 | GENUINE3M and DAILY0000: "has another bar interval" | TXT `W16a_Genuine3M.txt`; TXT `W16b_Daily0000.txt` | | |
| W17 | DAILY0915: "may have another bar interval" | TXT `W17_Daily0915.txt` | | |
| W18 | SPARSE; scan report; Workbench note | TXT `W18_Sparse.txt`; FILE `Scan_Report_....csv`; TXT `W18_Workbench.txt` | | |
| W19 | Unreadable folder; scan both stopped and incomplete | None (no owner evidence) | **AUTOMATED ONLY - not performed by the owner** | Covered by automated tests (guide section 5, Part C); passed in GitHub runs 42469090550 and 42469094096 for commit `a3801f3`. Not seen on the owner's computer |
| W12 | Both windows close cleanly | WRITE | | `closed cleanly`, or what you saw |
| End | Round 2c folders put back (guide section 6) | WRITE | | `done` |

The two FILE copies named `Scan_Report_....csv` (W4, W18) have different times in their names, so they do not
replace each other. If Windows offers to replace one, click **Skip these files** (guide section 3.2).

## 3. Overall

| Item | Your entry |
|---|---|
| Overall result (all PASS / some FAIL / some NOT SURE) | |
| Evidence ZIP name (guide section 7) | |
| Anything else you noticed | |
