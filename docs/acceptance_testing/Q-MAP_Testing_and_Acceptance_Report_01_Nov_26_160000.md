# Q-MAP: testing report and acceptance checklist (01-Nov-26, updated after the PR #4 reviews)

Branch `claude/adoring-curie-5h2mx4` (PR #4).

| Commit | Kind of change |
|---|---|
| `dee232e` | Code: storage classes (schema 5), derived timeframes, catalogue, analytical engine |
| `1c55f07` | Code: the two applications |
| `8ea0f4a` | Documentation |
| `832b788` | **Code**: schema migration 6 (audited storage changes) and the recovery consistency report |
| `330a9aa` | **Code**: original-path reconstruction for detecting earlier tampering (no schema change) |
| later commits | Documentation only (this report, guides, decision log, register) |

**Four kinds of evidence, kept separate:**

| Kind | Who / where | Status |
|---|---|---|
| Automated tests run locally | Claude, Ubuntu 24.04 container | Section 1 |
| GitHub CI | GitHub Actions, Windows and Ubuntu, Python 3.11 | Section 2 |
| Practical acceptance | Claude, real windows on a virtual Linux screen, synthetic files | Section 4 |
| Windows / Thonny or IDLE acceptance with the owner's real sample files | Project Owner, own computer | **Outstanding** (section 5) |

Status words: **Passed**, **Failed**, **Skipped**, **Not run**, **Blocked**, **Not applicable**.

## 1. Automated tests run locally by Claude

| Code commit | Environment | Command | Result |
|---|---|---|---|
| `852247f` (PR #3 head, baseline) | Python 3.12.3, Tk 8.6, Xvfb | `QMAP_REQUIRE_GUI_TESTS=1 xvfb-run -a python3.12 -m pytest -p no:cacheprovider` | 614 passed |
| `1c55f07` | Same | Same | 685 passed, 0 failed, 0 skipped |
| `1c55f07` | Python 3.11 / 3.13, no tkinter | `python3.11 -m pytest -p no:cacheprovider` | 597 passed, 62 skipped, 0 failed (each) |
| `832b788` | Python 3.12, Tk, Xvfb | as above | 701 passed, 0 failed, 0 skipped |
| `832b788` | Python 3.11, no tkinter | as above | 613 passed, 62 skipped, 0 failed |
| **`330a9aa` (latest code)** | Python 3.12.3, Tk 8.6, Xvfb, GUI tests required | as above | **704 passed**, 0 failed, 0 skipped (175 GUI) |
| **`330a9aa`** | Python 3.11, no tkinter | as above | **616 passed, 62 skipped** (window tests skip without tkinter, by design), 0 failed |

New failures introduced: none. Pre-existing failures: none.

**New tests in PR #4: 90.**

| File | Tests | Covers |
|---|---|---|
| `test_storage_class.py` | 15 | Moves, deletion, raw protection, dependents, confirmation for runs, crash recovery during a move |
| `test_storage_integrity.py` | 19 | Migration 6: every invalid direct update refused; the audit trail cannot be faked; normal workflows; earlier tampering reported, including a class and path changed together and ending Permanent elsewhere |
| `test_derive.py` | 17 | Calendar periods, aggregation rules, look-ahead dating, edge flags, volume rule, refusals, provenance, reuse |
| `test_catalog_and_analysis.py` | 17 | Catalogue, lineage, readiness, run pipeline, metadata, an independent statistics check, blocked and failed runs |
| `test_two_applications.py` | 15 | Entry points, both apps together, shared folders, Datasets screen, Workbench, two regressions found in acceptance |
| `test_architecture.py` | +4 | Entry points; the Workbench loads no data-preparation code; one registry access path; no GUI dependency in the engine |
| `test_logic_modules_env_store.py` | +2 | Module catalogue split by application |
| `test_window_home_and_folders.py` | +1 | Home test runs once per application |

**Proof that the migration-6 tests detect the issue:** with migration 6 withheld, 10 of the then 16 integrity tests
fail. The other 6 cover migration-5 safeguards and the normal workflow. The reconstruction test was confirmed by a
reproduction on the code before `330a9aa`, where `find_storage_inconsistencies()` returned an empty list for the same
history.

Tests changed because a requirement changed (none weakened or removed):

| Test | Change |
|---|---|
| `test_placement_and_migration.py` | Expects schema **6**; migrations 5 and 6 pinned by SHA-256 |
| `test_logic_modules_env_store.py` | Exact READY set updated |
| `test_window_home_and_folders.py` | Each app's Home lists its own modules |
| `Tests/gui/conftest.py` | The harness can start either app |
| `test_storage_integrity.py::test_tampering_done_before_migration_6_is_reported` | One assertion made precise: a class changed without its path is reported once, as a class/path mismatch |

## 2. GitHub CI (workflow `tests`, Windows and Ubuntu, Python 3.11, GUI tests required on Windows)

| Commit | Run(s) | Windows | Ubuntu |
|---|---|---|---|
| `852247f` (base, PR #3) | from PR #3 | success | success |
| `832b788` | 41325137464 and 41325143242 (push and pull-request triggers) | **success** (both) | **success** (both) |
| `330a9aa` and later | see the PR #4 conversation and checks tab | reported in the PR description | reported in the PR description |

## 3. What is NOT covered by any of the above

- Windows with Thonny or IDLE on the owner's computer (CI uses Windows, but not an IDE, and not the owner's files).
- The owner's 11 real sample files (not available in this environment; PR #3 tested them through Data Management,
  which is unchanged).

## 4. Practical acceptance in a virtual Linux environment (performed by Claude)

**How it was done.** `evidence_01_Nov_26/acceptance_walkthrough.py` drives the **real** windows of both applications
on a virtual screen (Linux), clicking the same buttons a person would. Where possible it checks results with plain
Python, independently of Q-MAP code: rows against the source CSV, weekly bars, statistics. Results:
`acceptance_results_01_Nov_26.json`; screenshots in `screenshots/`.

Re-run unchanged on code commits `832b788` and `330a9aa`: same 13 passed, 1 not applicable.

**Limitations.**

- **Synthetic files only.** The source was a dd-mm-yy CSV in your sample layout, with Volume and Net Volume. Your 11
  actual sample files are not available in this environment. The previous round (PR #3) tested them through Data
  Management, which is unchanged.
- **Not run on Windows, and not in Thonny or IDLE.**

| # | Scenario | Result | Evidence (short) |
|---|---|---|---|
| 1 | Launch Database Manager independently | **Passed** | `database_manager.py --selftest` opened and closed cleanly |
| 2 | Launch Analytical Workbench independently | **Passed** | `analytical_workbench.py --selftest` opened and closed cleanly |
| 3 | Import and preview a supported sample file | **Passed** | Preview showed format, delimiter, header advice, columns; nothing saved |
| 4 | Apply a compatible source profile | **Passed** | `example_csv_dd_mm_yy`: "Would be accepted", 60 rows |
| 5 | Reject or flag an incompatible profile | **Passed** | `example_csv_unix_seconds` on the dd-mm-yy file: "Would be rejected", with "Some dates or times could not be understood" (screenshot 02) |
| 6 | Standardise and validate | **Passed** | Loaded: "Accepted, 1 dataset(s) created" |
| 7 | Register and access the dataset | **Passed** | All 60 stored rows identical to the source (dates, OHLC, volume); Net Volume kept separately, exactly as read |
| 8 | Original source file unchanged | **Passed** | SHA-256 identical before and after the whole walkthrough |
| 9 | Permanent/Temporary and safe registry update | **Passed** | Moved to `Temporary_Data/...` (folder name awaiting owner decision OD-8); checksum unchanged; `verify` found nothing missing or mismatched; audit row "completed" with its reason (screenshot 04) |
| 9a | Derived timeframes (extra) | **Passed** | Weekly (12 bars) and monthly (3 bars) created; every weekly bar equals an independent re-calculation |
| 10 | Workbench discovers and uses ready data | **Passed** | Offered daily, weekly and monthly; folders shared |
| 11 | Analysis blocked with a clear explanation | **Passed** | A period without data: "NOT READY", with the reason and a pointer to Database Manager; no run created (screenshot 05) |
| 12 | An existing supported analysis still works | **Not applicable** | No MIQP or QLOPB analysis exists in the repository. Dataset Summary was run instead; its statistics match an independent calculation. |
| 13 | Outputs and run metadata saved | **Passed** | `Research_Reports/DSUM_.../` holds the CSV, Run_Metadata JSON (2 inputs, each with checksum and lineage), manifest and log (screenshot 06) |
| 14 | Both GUIs independent, one shared registry | **Passed** | 1 and 2 above; both windows open together; the Workbench showed the Database Manager's Temporary move at once |

**Defects found by this walkthrough, both fixed with regression tests:**

1. A delayed table-selection event could clear a readiness result that was already shown.
2. With both applications in one Python process, Tk variables created without an owner attached to the first window,
   so the second window showed empty labels. The real entry points run separately, so users would not normally see
   this.

A third mismatch was in the walkthrough script itself: it compared the text-preserved Net Volume with a number. The
script was corrected; Q-MAP was right.

## 5. Windows / IDLE acceptance on the Project Owner's computer: OUTSTANDING

**Outstanding.** Please tick each item on your own computer:

- [ ] Open `database_manager.py` (F5); choose the folders. The Home "Data at a glance" box shows your data.
- [ ] Open `analytical_workbench.py` (F5) while Database Manager is open. Its folders are already filled in.
- [ ] Load 2-3 of your sample files (for example `csv headers std.csv` with your dd-mm-yy profile).
- [ ] Check one file against a deliberately wrong profile: it must be rejected with an understandable reason.
- [ ] In Datasets and Storage, click a dataset: the details show your original file name and the lineage.
- [ ] Derive Weekly and Monthly from a daily dataset; compare a few weekly bars with your own calculation.
- [ ] Move a dataset to Temporary and back; confirm the Temporary folder under `Q-MAP_DATA` is used (today `Temporary_Data`; see OD-8), and nothing else changed.
- [ ] Try to delete a Permanent dataset (refused), then a Temporary one with derived data (refused, with the reason).
- [ ] In the Workbench, run Dataset Summary on a daily dataset; open the run folder and read the CSV and the
      Run_Metadata file.
- [ ] Set a start date after your data ends: the run must be refused with an explanation.
- [ ] Confirm your original sample files are unchanged (compare file dates and sizes, or the checksums in
      `docs/sample_file_testing/`).



## 6. Storage-integrity reviews of PR #4 (01-Nov-26)

**Review 1 (fixed in `832b788`, schema migration 6).** Confirmed first: on a real migrated database, six direct
updates bypassing Q-MAP were allowed by schema 5:

1. class without path;
2. class with an arbitrary path;
3. a correctly mapped move without an audit record;
4. Temporary to Permanent by class only;
5. `file_deleted_at` without a delete action;
6. a storage action inserted as already "completed".

All six are refused at schema 6.

**Review 2 (improved in `330a9aa`, no schema change).** Reproduced: a database at schema 5 had its class and path
changed together twice without an audit action, ending Permanent at a different path. Before `330a9aa`, recovery
reported nothing. It now rebuilds the original path from immutable lineage records and reports the unexplained path.
The limits of this detection are in `docs/Data_Registry_and_Schema.md`, section "Limits of detecting earlier tampering".
