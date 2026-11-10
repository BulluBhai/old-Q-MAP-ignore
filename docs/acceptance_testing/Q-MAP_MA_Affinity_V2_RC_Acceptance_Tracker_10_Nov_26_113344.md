# Q-MAP MA Affinity V2 release candidate acceptance tracker (R1 to R10)

Guide: `Q-MAP_MA_Affinity_V2_RC_Acceptance_Guide_10_Nov_26_113344.md` (same folder). Program: commit
`429c50c32143e35088b3a0a500b8e20a4285b083`. To be filled in by the Project Owner; nothing below has been tested by the
owner yet. Evidence folder: `D:\Q-MAP_V01\RC_Test\Evidence`.

## 1. Test details

| Item | Value |
|---|---|
| Date (dd-mmm-yy) | |
| Python version (IDLE first line) | |
| Commit to test (filled in; must match the downloaded folder name) | `429c50c32143e35088b3a0a500b8e20a4285b083` |
| Downloaded folder name ends with that commit (yes / no) | |
| Test folder used (`RC_Test`, or the new name from step 2.1.2) | |
| R1 case seen (A = remembered folders kept, B = prepared automatically) | |

## 2. Results

Result: PASS, FAIL or NOT SURE. Under "Actual result", write what you saw if it differs from the expected outcome.

| Check | Expected outcome | Evidence | Actual result | Result |
|---|---|---|---|---|
| R1 | Case A: earlier folders kept and standard folders named; **Use standard folders** → **Yes**; or case B: prepared automatically. Then the `RC_Test` folders, `Both folders are ready and remembered.`; `Q-MAP_DATA` and `Q-MAP_OUTPUT` exist in `RC_Test` | PIC `R1_Folders.png` | | |
| R2 | Stage `Finished`, bar full, `Scan finished (1 imported)` | PIC `R2_Scan_Finished.png` | | |
| R3 | Both MA Affinity analyses listed; V1: `488 of 488 steps (100.0%)`, bar full, `Completed. Run MAAF_...`; Top-5 EMA-37, EMA-34, SMA-38, SMA-49, SMA-39; EMA-37 66.13, 63.64% over 44 | PIC `R3_V1_Completed.png`; FILE `MA_Affinity_Findings_...txt` | | |
| R4 | `READY`; `OK   Chance test: 200 shuffles of 69 blocks of 15 bars (seed 1); ...`; while running: shuffle count, step count, ETA; at the end `96,888 of 96,888 steps (100.0%)`, bar full, `Completed. Run MAA2_...` | PIC `R4_V2_Ready.png`; PIC `R4_V2_Running.png`; PIC `R4_V2_Completed.png` | V2 Run ID: | |
| R5 | Findings start with `EXECUTIVE INTERPRETATION` (8 headings); EMA-37 66.13, 63.64% of 44; `NOT DISTINGUISHABLE FROM CHANCE`, 72.59, 66.13, p 0.8657; baseline 51.36%, 12.27 points; PDF page 1 **Executive interpretation** | FILE findings; FILE PDF; FILE `Run_Metadata_...json` | | |
| R6 | `REPRODUCED: every result table is identical to run ...`; report: `Python and library versions` same, 3 tables IDENTICAL | PIC `R6_Reproduced.png`; FILE `Reproducibility_Report_...csv` | New Run ID: | |
| R7 | `Cancelling - ...`, then Stage `Cancelled`, `Cancelled at ... (not complete)`, bar not full, `Cancelled. Run MAA2_... recorded as cancelled`; reproducing it: `Not reproduced: Run ... did not complete, ...` | PIC `R7_Cancelled.png`; PIC `R7_Not_Reproducible.png` | Cancelled Run ID: | |
| R8 | Window closes; IDLE shows `>>>` again within about a minute | PIC `R8_Closed.png` | | |
| R9 | 10-Nov-26 run folders still in `Beta_Test`; this test's runs only in `RC_Test` | PIC `R9_Earlier_Runs.png` | | |
| R10 | Your judgement: is the executive interpretation understandable and useful? Anything missing? | WRITE | | (opinion) |
