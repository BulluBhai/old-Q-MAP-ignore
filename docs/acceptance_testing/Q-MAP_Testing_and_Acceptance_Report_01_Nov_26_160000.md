# Q-MAP: testing report and acceptance checklist (01-Nov-26)

Branch `claude/adoring-curie-5h2mx4`. Code tested at commit `1c55f07`; later commits change documentation only.
Evidence: `evidence_01_Nov_26/` next to this file.

Status words used: **Passed**, **Failed**, **Skipped**, **Not run**, **Blocked** (by environment or dependency), **Not
applicable**.

## 1. Automated tests (local)

| Run | Environment | Command | Result |
|---|---|---|---|
| Baseline, before any change (PR #3 head `852247f`) | Ubuntu 24.04, Python 3.12.3, Tk 8.6, virtual screen (Xvfb) | `QMAP_REQUIRE_GUI_TESTS=1 xvfb-run -a python3.12 -m pytest -p no:cacheprovider` | **614 passed**, 0 failed (153 GUI tests) |
| Final, with GUI | Same | Same | **685 passed**, 0 failed, 0 skipped (175 GUI tests, all required to run) |
| Final, no tkinter, Python 3.11 (the CI Python version) | Ubuntu 24.04, Python 3.11 | `python3.11 -m pytest -p no:cacheprovider` | **597 passed, 62 skipped** (window tests skip without tkinter, by design), 0 failed |
| Final, no tkinter, Python 3.13 | Ubuntu 24.04, Python 3.13 | `python3.13 -m pytest -p no:cacheprovider` | **597 passed, 62 skipped**, 0 failed |

New failures introduced: **none**. Pre-existing failures: **none**.

**71 new tests**:

| File | Tests | Covers |
|---|---|---|
| `test_storage_class.py` | 15 | Moves, deletion, protection of raw files, dependents, confirmation for runs, crash recovery during a move |
| `test_derive.py` | 17 | Calendar periods, aggregation rules, look-ahead dating, edge flags, volume rule, refusals, provenance, reuse |
| `test_catalog_and_analysis.py` | 17 | Catalogue, lineage, readiness (passing and each failure), run pipeline, metadata, an independent statistics check, blocked and failed runs |
| `test_two_applications.py` | 15 | Each entry point, both apps open together, shared folders, Datasets screen, Workbench readiness and runs, two regressions found in acceptance |
| `test_architecture.py` | 4 more | Entry points; the Workbench loads no data-preparation code; one registry access path; the engine has no GUI dependency |
| `test_logic_modules_env_store.py` | 2 more | The module catalogue split by application |
| `test_window_home_and_folders.py` | 1 more | The Home test now runs once per application |

Tests changed because a requirement changed (none weakened or removed):

| Test | Change |
|---|---|
| `test_placement_and_migration.py` | Expects schema 5; migration 5 pinned |
| `test_logic_modules_env_store.py` | Exact READY set updated |
| `test_window_home_and_folders.py` | Each app's Home lists its own modules |
| `Tests/gui/conftest.py` | The harness can start either app |

## 2. CI

**Not run yet for this branch.** CI (`.github/workflows/tests.yml`, Windows and Ubuntu, Python 3.11) runs when the pull
request is opened. Its result will be reported on the pull request. The base branch (PR #3 head `852247f`) was green on
both operating systems.

## 3. Practical acceptance

**How it was done.** `evidence_01_Nov_26/acceptance_walkthrough.py` drives the **real** windows of both applications
on a virtual screen (Linux), clicking the same buttons a person would. Where possible it checks results with plain
Python, independently of Q-MAP code: rows against the source CSV, weekly bars, statistics. Results:
`acceptance_results_01_Nov_26.json`; screenshots in `screenshots/`.

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
| 9 | Permanent/Temporary and safe registry update | **Passed** | Moved to `Temporary_Data/...`; checksum unchanged; `verify` found nothing missing or mismatched; audit row "completed" with its reason (screenshot 04) |
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

## 4. Acceptance checklist for the Project Owner (Windows, Thonny or IDLE, your own files)

**Outstanding.** Please tick each item on your own computer:

- [ ] Open `database_manager.py` (F5); choose the folders. The Home "Data at a glance" box shows your data.
- [ ] Open `analytical_workbench.py` (F5) while Database Manager is open. Its folders are already filled in.
- [ ] Load 2-3 of your sample files (for example `csv headers std.csv` with your dd-mm-yy profile).
- [ ] Check one file against a deliberately wrong profile: it must be rejected with an understandable reason.
- [ ] In Datasets and Storage, click a dataset: the details show your original file name and the lineage.
- [ ] Derive Weekly and Monthly from a daily dataset; compare a few weekly bars with your own calculation.
- [ ] Move a dataset to Temporary and back; confirm `Q-MAP_DATA/Temporary_Data` is used, and nothing else changed.
- [ ] Try to delete a Permanent dataset (refused), then a Temporary one with derived data (refused, with the reason).
- [ ] In the Workbench, run Dataset Summary on a daily dataset; open the run folder and read the CSV and the
      Run_Metadata file.
- [ ] Set a start date after your data ends: the run must be refused with an explanation.
- [ ] Confirm your original sample files are unchanged (compare file dates and sizes, or the checksums in
      `docs/sample_file_testing/`).
