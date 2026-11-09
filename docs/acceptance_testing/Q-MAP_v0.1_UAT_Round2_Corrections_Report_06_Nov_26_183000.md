# Q-MAP v0.1: UAT round 2 — corrections after the first test round (06-Nov-26)

Prepared 06-Nov-26 by Claude (developer) for Sandeep (owner) and for ChatGPT's independent review. **Windows UAT is
not complete. Controlled analytical use is not approved.** Passing automated tests are not owner acceptance.

## 1. Records

| Record | Where | Status |
|---|---|---|
| First-round results (06-Nov-26 23:13 IST) | `docs/acceptance_testing/uat_round1_06_Nov_26/UAT_Results_06_Nov_26_231303.md` (copied unchanged; SHA-256 `15af1dba0f057954a165d158ba046ea50feb43f172fc2ecfd576449f8e2d727a`, identical to the file the owner supplied) | Preserved |
| First-round evidence ZIP | Owner's PC: `D:\Q-MAP_V01\Evidence\Q-MAP_UAT_Evidence_06_Nov_26_231303.zip` (9,645,365 bytes, SHA-256 `9aa8a37ac47f48033bf8946e41790369a3cd0b3d61713af0b974753c24088731`). Not copied into the repository (screenshots, workbooks, PDFs) | Preserved; not changed |
| Owner's Q-MAP_DATA, registry and market files | Owner's PC only | Not touched: this round never connected to the owner's PC |
| Round-2 automated evidence | `docs/acceptance_testing/uat_round2_06_Nov_26/` and `Q-MAP_UAT_Round2_Evidence_06_Nov_26_183000.zip` (supplied to the owner) | New |

**Builds.** First round: build `3fa925abf95b` (code `919c697`). Round 2: **code commit `56a72f4`, build fingerprint
`21d31f0fe259`** (program files changed: display only). The first-round fingerprint is not reused.

## 2. Findings and what was done

| # | Finding (first round) | Classification | What was done | Tests |
|---|---|---|---|---|
| O1 | W2, W14-W18: quality warnings not shown in the Sources file detail | **Defect, corrected** (display only) | The Sources detail lists, under "Quality warnings recorded for dataset N", each warning recorded for the file's dataset, with its plain-English title and the recorded detail. One shared wording function (`messages.describe_warning`) now serves Sources and Datasets and Storage, so the two screens describe a warning the same way. Nothing is recalculated; severity, validation status and readiness are unchanged. Works for unchanged, skipped files | `test_uat_round1_corrections.py`: 4 wording cases, unknown wording, W2 conflict, W14-W18 pattern files, skipped file; `test_window_sources.py::test_the_detail_pane_shows_recorded_quality_warnings_and_a_rescan_shows_unchanged` (real window) |
| O3 | W7: after Restore the row said "Already loaded"/"Imported" | **Defect, corrected** (display only) | Restore only re-offers data; the row now says "Available again (restored by you)" and the detail "...; nothing was imported again". The Restore operation itself is unchanged | `test_a_restored_dataset_is_described_as_available_again_not_imported`; `test_window_sources.py::test_reject_and_restore_selected_files_in_bulk` (expectation updated to the approved wording) |
| O4 | A4: a skipped file kept its earlier "Imported"; the summary counted it again | **Defect, corrected** (display only) | A file skipped because it is unchanged is shown, reported (Scan_Report Result column) and counted as "Unchanged (imported earlier)" / "Unchanged (rejected earlier)" / "Unchanged (still needs your answer)". The scan summary counts only this scan. The stored observation (used by the skip logic) is unchanged | `test_scan_results_describe_only_what_this_scan_did` (first import; unchanged second scan with zero imports; no inflation; new and changed files still counted); `test_folder_discovery.py` (two expectations updated; stored outcome now also asserted) |
| O2 | W5: NSE:RELIANCE_EQ and NSE:RELIANCE both active | **Expected behaviour** (owner decision 06-Nov-26: keep the design) | A correction creates a new dataset and never changes the old one (D5-30); a changed identity is a different instrument, so the old dataset is not superseded. Verified on the first-round evidence: dataset 13 NSE:RELIANCE_EQ (provisional, W1 scan) and dataset 18 NSE:RELIANCE (after the alias) come from the same unchanged `RELIANCE_EQ.csv`, Daily, 7,746 bars, 07-Nov-94 to 30-Dec-25 (`W1_W3_scan_market_files.txt`, `A4_rescan.txt`). Dataset checksums are not in the first-round logs: the owner checks identity on screen before rejecting. **Manual W5 gains a one-time, reversible reject step** for the old dataset. Rejection deletes nothing (dataset, stored file, source file kept), keeps earlier runs and their records, removes it from the Workbench list, and Restore undoes it. Not done on the owner's data | `test_w5_duplicate_is_removed_from_analyses_by_reversible_rejection` (isolated data: identity match, Workbench list, file kept, earlier run kept, restore) |
| O5 | W1: which ICICIBANK copy is "Imported" | **Expected behaviour; documentation clarified** | Identical content is stored once; files are read in alphabetical order (`ICICIBANK (1).txt` first, as the space sorts before the dot); the others are "Already loaded" with the same dataset (7 in round 1); Datasets and Storage → "Original file(s)" lists all names. Manual W1 explains this | existing `test_the_same_content_under_two_names_is_loaded_once` |
| O6 | Run ID time differs from file-name time | **Expected behaviour; documentation clarified** | Verified in code: `core/runs.py` builds `<MODULE>_<YYYYMMDD>_<HHMMSS>` from `datetime.now(timezone.utc)` (decision D2-02 records "(UTC)"); output file names use `datetime.now()` (the computer's local time). Manual section 10 explains it with the first-round example `SCAN_20261106_173630` (17:36:30 UTC) and `Scan_Report_06_Nov_26_230651.csv` (23:06:51 IST) | — |
| O7 | Remembered folders; Python `__pycache__` files | **Normal; no action** | Python creates `__pycache__` itself; it is not a program file and not part of the build fingerprint | — |

No dataset identity, registry history, processing/cleaning/rules version, fingerprint scheme, timeframe or
validation rule, QLOPB calculation or methodology was changed.

## 3. Python version

| Item | Evidence |
|---|---|
| Release requirement | `pyproject.toml`: `requires-python = ">=3.11"`; README and manual: "Python 3.11 or newer". Not changed |
| CI | Now Python 3.11 **and** 3.12, Windows (GUI tests required) and Ubuntu (`.github/workflows/tests.yml`) |
| Local, Linux | Python 3.11.15 and 3.12.13 on commit `56a72f4`: see section 4 and `uat_round2_06_Nov_26/Local_pytest_py311.txt`, `Local_pytest_py312.txt` (python -VV, executable, pytest 9.2.0, dependency versions, command, totals, skip reasons) |
| Earlier 3.12 run | 1,340 passed, 2 skipped, 0 failed on `2f7f99b` (build `3fa925abf95b`), Python 3.12.13; superseded by the run on `56a72f4` |
| Owner's PC (first round) | **Evidenced:** the first-round report names the interpreter used for the engine tests as `C:\Users\sandeepb\Python312` (Python 3.12), on Windows 11 Pro 10.0.26300. **Not evidenced:** the exact version line and which interpreter IDLE starts. The owner records the first line of the IDLE window in V1/section 16 |
| Extra 3.11 testing on the owner's PC | Not required: 3.11 stays tested in CI; 3.12 is now tested too |

## 4. Test results (round 2)

| Where | Python | Commit | Passed | Skipped | Failed | Skips |
|---|---|---|---|---|---|---|
| Local Linux (Ubuntu 24.04.5, Xvfb, GUI required) | 3.11.15 | `56a72f4` | 1,352 | 2 | 0 | 2 Windows-junction tests (Windows only); 213 GUI passed |
| Local Linux (same) | 3.12.13 | `56a72f4` | 1,352 | 2 | 0 | same |
| GitHub CI Windows (GUI required) | 3.11 | `56a72f4` | 1,353 | 1 | 0 | hard-link fallback test (macOS/Linux only); GUI 213 passed, 0 skipped |
| GitHub CI Windows (GUI required) | 3.12 | `56a72f4` | 1,353 | 1 | 0 | same |
| GitHub CI Ubuntu (no display) | 3.11 | `56a72f4` | 1,246 | 108 | 0 | 106 window tests (no display) and 2 Windows-junction tests |
| GitHub CI Ubuntu (no display) | 3.12 | `56a72f4` | 1,246 | 108 | 0 | same |

**4a. GitHub CI on `56a72f4`:** run #110 (`42268067492`, pull_request), totals read from each job's log; run #109
(push) also succeeded. https://github.com/BulluBhai/Q-MAP/actions/runs/42268067492. The Windows window tests ran (213
passed, none skipped). GitHub's results are independent of the local totals; neither is owner acceptance.

**MA Affinity unchanged.** The same synthetic daily file run through folder scan + Workbench MA Affinity (default
settings) on the previous build (`efb4bd9`) and on `56a72f4` gives byte-identical candidate and interaction tables
(`uat_round2_06_Nov_26/MA_Affinity_output_unchanged.txt`).

**Regressions on the old code.** The 10 new O1/O3/O4 tests fail on the previous code and pass on `56a72f4`; the W5
test passes on both (W5 needs no code change).

## 5. Acceptance status by check (after round 2)

"Engine-tested" = tested by Claude without the screen in round 1 (build `3fa925abf95b`). The round-2 change is display
only, so engine results stay valid evidence of behaviour, **but a check whose requirement is what the screen shows is
not PASS until the owner has seen it.**

| Check | Status | Owner action |
|---|---|---|
| V1 | PASS WITH OBSERVATION (owner, round 1) | Record the IDLE first line |
| W2, W14, W15, W16, W17, W18 | Finding O1 **corrected**; **screen re-test required** (new build) | Checklist |
| W5 | Behaviour as designed; **screen re-test with the new reject step required** | Checklist |
| W7, A4 | Findings O3/O4 **corrected**; **screen re-test required** | Checklist |
| V2, V3, V6, A7, W12, V14, W11 | **NOT TESTED** (screen / originals) | Checklist |
| W8 | Engine PASS (Stop logic); **screen part (window responsive) NOT TESTED** | Checklist |
| A5 | Engine PASS (values); **screen part (Calendar) NOT TESTED** | Checklist |
| V7, V9, V13 | **PASS** (round 1): judged on the generated files and run record, not on a screen; build was `3fa925abf95b` | Optional repeat; the build fingerprint in new reports will read `21d31f0fe259` |
| W1, W3, W4, W6, W9, W10, W13, W19, V5 | Engine-tested PASS / PASS WITH OBSERVATION (round 1); **screen not seen by the owner** | **Owner decision:** accept the engine evidence for these, or see them on screen (the checklist lists them as optional) |
| Optional checks | Not run | — |

**Owner acceptance still required for:** every check above that is not PASS, the acceptance of engine-tested
evidence (W1, W3, W4, W6, W9, W10, W13, W19, V5), and the overall decision in section 16 of the manual.

## 6. Readiness

- **Ready for the remaining Windows UAT (owner screen checks):** yes, subject to ChatGPT's independent review of this
  round.
- **Ready for controlled analytical use:** **no.** That needs the owner's completed acceptance, the pending owner
  decisions (D3-15, D6-18, D6-19, D6-20, D6-21, OW-41), OW-35's independent verification and the owner's merge
  approval. None of these is given or implied here.
