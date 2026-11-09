# Q-MAP MA Affinity beta acceptance tracker (A1 to A8)

Guide: `Q-MAP_MA_Affinity_Beta_Acceptance_Guide_09_Nov_26_125357.md` (same folder). Evidence folder:
`D:\Q-MAP_V01\Beta_Test\Evidence`.

## 1. Test details

| Item | Value |
|---|---|
| Date (dd-mmm-yy) | |
| Python version (IDLE first line) | |
| Commit tested (7 characters) | |
| Test folder used (`Beta_Test`, or the new name from step 2.1.3) | |

## 2. Results

Result: PASS, FAIL or NOT SURE. Under "Actual result", write what you saw if it differs from the expected outcome.

| Check | Expected outcome | Evidence | Actual result | Result |
|---|---|---|---|---|
| A1 | `Scan finished (1 imported)`; NSE:BETADEMO, Daily, accepted, no quality warnings | PIC `A1_Registered.png` | | |
| A2 | NSE:BETADEMO Daily, 1500 bars, 01-Jan-19 to 30-Sep-24; MA types `SMA,EMA`; `READY` | PIC `A2_Ready.png` | | |
| A3 | `Completed. Run MAAF_...`; Run ID filled in next to Reproduce Run ID | PIC `A3_Completed.png` | Run ID: | |
| A4 | Findings: 1500 bars, in-sample 1050 (01-Jan-19 to 09-Jan-23), out-of-sample 450 (10-Jan-23 to 30-Sep-24); Top-5 EMA-37, EMA-34, SMA-38, SMA-49, SMA-39; EMA-37 affinity 66.13, 63.64% over 44 | FILE `MA_Affinity_Findings_...txt` | | |
| A5 | PDF heading with dataset, Run ID, build and checksum; Excel Data_Quality starts with the research question and Run ID | FILE PDF; FILE `Run_Metadata_...json` | | |
| A6 | `REPRODUCED: every result table is identical to run ...`; report: 2 tables IDENTICAL; first run folder still there | PIC `A6_Reproduced.png`; FILE `Reproducibility_Report_...csv` | New Run ID: | |
| A7 | `Not reproduced: There is no run 'MAAF_TEST' in this Q-MAP registry.`; no new run | PIC `A7_Refused.png` | | |
| A8 | Your judgement: is the output understandable and useful? Anything missing? | WRITE | | (opinion) |
