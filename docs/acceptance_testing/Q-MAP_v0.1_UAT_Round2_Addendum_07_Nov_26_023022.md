# Q-MAP v0.1: UAT round 2 addendum — engine results and the R2-O2 correction (07-Nov-26)

Prepared 07-Nov-26 by Claude (developer) for Sandeep (owner) and ChatGPT's independent review. **Windows UAT is not
complete. Controlled analytical use is not approved.** Automated tests are not owner acceptance.

## 1. Records (all kept unchanged)

| Record | Where | SHA-256 |
|---|---|---|
| Round-2 corrections report (06-Nov-26) | `Q-MAP_v0.1_UAT_Round2_Corrections_Report_06_Nov_26_183000.md` | `ff6ff88bb00b1374b503f61ee09e395b94aa19a66fc75cff97354d1c95b80315` (unchanged since `d529c1b`) |
| Round-2 evidence ZIP (06-Nov-26) | `Q-MAP_UAT_Round2_Evidence_06_Nov_26_183000.zip` | `7f83a0a69c650e91e20f348ccedf7a86ab386e71660fc78c2b4068646de09113` (unchanged) |
| Round-2 checklist (06-Nov-26) | `Q-MAP_v0.1_UAT_Round2_Owner_Screen_Checklist_06_Nov_26_183000.md` | `570aa9fc6df9bd3ee8e1e1bde2a8503a6b96a2740ad8205d27682f2e330aea43` (unchanged; replaced for use by the 2b checklist) |
| Round-2 engine results from the owner's PC (07-Nov-26 07:48 IST, build `21d31f0fe259`) | `uat_round2_laptop_07_Nov_26/UAT_Round2_Results_07_Nov_26_074843.md` (copied unchanged) | `175ae498eec14db0e847553e413dedc412641efb9a6bd0069fc6751818a3876b` |
| Round-2 engine evidence ZIP from the owner's PC | Owner's PC `D:\Q-MAP_V01\Evidence_Round2\Q-MAP_UAT_Round2_Evidence_07_Nov_26_074843.zip` (9,387,897 bytes; not in the repository) | `156a69b1862b351a6d6a577b8bd81e7c6effe99259b3d8cb60b2459382ecb3f8` |

## 2. Round-2 engine results (owner's PC, build `21d31f0fe259`)

11 engine-tested checks: 7 PASS, 4 PASS WITH OBSERVATION, 0 FAIL. Round-1 findings O1, O3 and O4 resolved at engine
level. W5: datasets 13 (NSE:RELIANCE_EQ) and 18 (NSE:RELIANCE) hold identical data, compared value by value (source
`RELIANCE_EQ.csv`, 7,746 bars, 07-Nov-94 to 30-Dec-25, same processing and warnings); nothing was rejected. Integrity:
334 program files and 11 Market_Files copies unchanged. The tester briefly built the ZIP in the Windows temporary
folder before moving it into `Evidence_Round2` (nothing left there); no data or program file was affected.

| # | Observation | Classification | Action |
|---|---|---|---|
| R2-O1 | W18 SPARSE also shows "Long gaps between dates" | **Expected behaviour**: a real 10-day gap in the synthetic file (`date_gaps`, recorded since 03-Nov-26); the checklist wording ("only") was wrong | Checklist 2b and manual W18 corrected |
| R2-O2 | A restored file kept "Available again (restored by you)" after later scans | **Defect in the round-2 display correction, corrected** (owner choice A, 07-Nov-26) | Section 3 |
| R2-O3 | The Workbench offers both RELIANCE datasets | **Expected** until the owner's step-13 rejection | None |
| R2-O4 | Run ID time in UTC, file names local | **Expected** (D2-02), documented in round 2 | None |

## 3. R2-O2 correction (display only)

"Available again (restored by you)" is now shown only while the restore is newer than Q-MAP's last look at the file.
After the next scan, the Sources row and detail show that scan's result ("Unchanged (imported earlier)", "Accepted by
default"). Nothing stored changes: the restore stays in `dataset_user_decisions`, the dataset stays offered to analyses,
no dataset, observation or import is added or changed.

- Code: `Application/qmap_gui/source_services.py` (`_restored_since_last_look`, read-only `dataset_restore_times`),
  `Application/qmap_gui/sources.py` (passes the restore times to the row and the detail).
- Tests: `Tests/integration/test_uat_round1_corrections.py::test_after_a_later_scan_a_restored_file_shows_that_scans_result`
  (row and detail before and after the next scan; decision history `rejected, restored` unchanged; current decision
  `restored`; dataset count, dataset ids and stored outcome unchanged; still offered to analyses; a new rejection is
  shown at once) and `Tests/gui/test_window_sources.py::test_a_restored_file_shows_the_next_scans_result_on_the_window`.
- Old behaviour confirmed on the previous code `34116ff`: after a later scan the row still read
  "Available again (restored by you)".

**New build: code commit `06d8659`, build fingerprint `a202d43d78ed`** (full
`a202d43d78edb86db78bada3078e202e887e5a19d931dd6cf502c06176c9bea2`).

## 4. Tests on `06d8659`

| Where | Python | Passed | Skipped | Failed | Skips |
|---|---|---|---|---|---|
| Local Linux (Ubuntu 24.04.5, Xvfb, GUI required; 214 GUI passed) | 3.11.15 | 1,354 | 2 | 0 | Windows-junction tests |
| Local Linux (same) | 3.12.13 | 1,354 | 2 | 0 | same |
| GitHub CI Windows (GUI required; 214 GUI passed) | 3.11 | 1,355 | 1 | 0 | hard-link fallback test (macOS/Linux only) |
| GitHub CI Windows (same) | 3.12 | 1,355 | 1 | 0 | same |
| GitHub CI Ubuntu (no display) | 3.11 | 1,247 | 109 | 0 | 107 window tests (no display), 2 Windows-junction tests |
| GitHub CI Ubuntu (no display) | 3.12 | 1,247 | 109 | 0 | same |

Details: `uat_round2b_07_Nov_26/Local_pytest_py311.txt`, `Local_pytest_py312.txt`. MA Affinity output on the same
synthetic file is byte-identical on `56a72f4` and `06d8659` (and on `efb4bd9`):
`uat_round2b_07_Nov_26/MA_Affinity_output_unchanged.txt`.

**4a. GitHub CI (07-Nov-26), totals read from each job's log.**

| Run | Commit | Attempt | Result |
|---|---|---|---|
| #116 (push), #117 (pull_request) | `06d8659` | 1, and #117 attempt 2 at 02:32 UTC | **Not run (unavailable):** every job ended within seconds without a runner. GitHub's annotation: "The job was not started because recent account payments have failed or your spending limit needs to be increased." Account billing, not the code |
| #118 (push), #119 (pull_request) | `3b25fe8` (documents only) | 1 | **Not run (unavailable)**, same annotation |
| #117 | `06d8659` | 3 (02:50 UTC, after the repository was made public) | **Success, all four jobs**: the table above |
| #119 | `3b25fe8` | 2 (04:52 UTC) | **Success, all four jobs**, identical totals: Windows 3.11 and 3.12 1,355 passed, 1 skipped; Ubuntu 3.11 and 3.12 1,247 passed, 109 skipped; 0 failed |

No workflow, test or application change was made to obtain these results. The commit that adds this table changes
documents only; its own CI result is reported on PR #12 (a commit cannot record its own run).

## 5. What the owner repeats

Use `Q-MAP_v0.1_UAT_Round2c_Owner_Screen_Checklist_07_Nov_26_050239.md` with the new download (build `a202d43d78ed`).
Round 2c (07-Nov-26) supersedes the round-2b checklist (kept unchanged): V14 (step 21) and A4 (step 11) now expect 10
files "Unchanged (imported earlier)" and AKZOINDIA "Unchanged (rejected earlier)"; W18 (step 10) expects both SPARSE
warnings and includes the scan-folder check of the full Windows manual (folder
`Q-MAP_OUTPUT\Data_Management\SCAN_20261106_174124`, whose Scan_Report lists the six pattern files as Imported, as
verified in the round-1 evidence).
**A4 (step 11), W7 (step 14) and V14 (step 21)** are the checks this change affects. The other screen steps remain to
be done as before; Claude's round-2 engine results for them stay valid (the change touches only the restored-file
wording).

## 6. Readiness

- Ready for the remaining Windows screen checks: yes, after ChatGPT's review of this addendum.
- Ready for controlled analytical use: **no** (owner acceptance, decisions D3-15, D6-18, D6-19, D6-20, D6-21, OW-41,
  OW-35 independent verification and the merge approval are all outstanding).
