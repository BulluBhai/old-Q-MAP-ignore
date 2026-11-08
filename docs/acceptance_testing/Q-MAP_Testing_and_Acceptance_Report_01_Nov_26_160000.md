# Q-MAP: testing report and acceptance checklist (01-Nov-26, updated after the PR #4 reviews; review-finding fixes 02-Nov-26)

Branch `claude/adoring-curie-5h2mx4` (PR #4).

| Commit | Kind of change |
|---|---|
| `dee232e` | Code: storage classes (schema 5), derived timeframes, catalogue, analytical engine |
| `1c55f07` | Code: the two applications |
| `8ea0f4a` | Documentation |
| `832b788` | **Code**: schema migration 6 (audited storage changes) and the recovery consistency report |
| `330a9aa` | **Code**: original-path reconstruction for detecting earlier tampering (no schema change) |
| `de624a6` | Documentation |
| `1760b57` | **Code**: Temporary area moved to `Q-MAP_DATA/Temporary/` (OD-8), schema **migration 7**, safe transition; Workbench roadmap stage numbers per Blueprint v1.2 |
| `fb19fb0` | **Code**: Workbench dates and calendar, request states, Open Output Folder, source-profile naming standard |
| `057b510` | Documentation (reviewed commit for the 02-Nov-26 findings) |
| `95a93c6` | **Code**: review-finding fixes: year 0000 in typed dates; NO DATA IN THIS PERIOD only when every selected dataset is empty (section 8) |
| `99d12b1` | **Code**: Windows-only fix found by CI: readiness date text no longer uses `strftime` (section 8) |
| later commits | Documentation only (this report, guides, decision log, register, architecture, conventions) |

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
| `330a9aa` | Python 3.12.3, Tk 8.6, Xvfb, GUI tests required | as above | 704 passed, 0 failed, 0 skipped |
| `330a9aa` | Python 3.11, no tkinter | as above | 616 passed, 62 skipped, 0 failed |
| `1760b57` | Python 3.12.3, Tk 8.6, Xvfb, GUI tests required | as above | 712 passed, 0 failed, 0 skipped |
| `1760b57` | Python 3.11, no tkinter | as above | 624 passed, 62 skipped, 0 failed |
| `fb19fb0` | Python 3.12.3, Tk 8.6, Xvfb, GUI tests required | as above | **797 passed**, 0 failed, 0 skipped (191 GUI) |
| `fb19fb0` | Python 3.11, no tkinter | as above | 693 passed, 78 skipped (window tests skip without tkinter, by design), 0 failed |
| `95a93c6` | Python 3.12.3, Tk 8.6, Xvfb | `xvfb-run -a python3.12 -m pytest -p no:cacheprovider` | 841 passed, 0 failed, 0 skipped (195 GUI) |
| `95a93c6` | Python 3.11.18, no tkinter | `python3.11 -m pytest -p no:cacheprovider` | 733 passed, 82 skipped, 0 failed |
| `99d12b1` | Python 3.12.3, Tk 8.6, Xvfb | as above | 842 passed, 0 failed, 0 skipped (195 GUI) |
| **`99d12b1` (latest code)** | Python 3.11.18, no tkinter | `python3.11 -m pytest -p no:cacheprovider` | **734 passed, 82 skipped** (window tests skip without tkinter, by design), 0 failed |
| **`7256cf1` (code `99d12b1`)** | Python 3.12.3, Tk 8.6, Xvfb, **GUI tests required** | `QMAP_REQUIRE_GUI_TESTS=1 xvfb-run -a python3.12 -m pytest -p no:cacheprovider` | **842 passed**, 0 failed, 0 skipped (195 GUI tests, all required and passed) |

New failures introduced: none. Pre-existing failures: none.

**New tests in PR #4: 228.** 98 before the enhancement; 85 for it (`test_user_dates.py` 39, `test_workbench_dates_and_runs.py` 17, `test_workbench_dates_and_output.py` 16, `test_profile_library.py` 13); and 45 for the 02-Nov-26 review findings (`test_user_dates.py` 28, `test_workbench_dates_and_runs.py` 13, `test_workbench_dates_and_output.py` 4; section 8). 797 + 45 = 842.

| File | Tests | Covers |
|---|---|---|
| `test_storage_class.py` | 15 | Moves, deletion, raw protection, dependents, confirmation for runs, crash recovery during a move |
| `test_storage_integrity.py` | 19 | Migration 6: every invalid direct update refused; the audit trail cannot be faked; normal workflows; earlier tampering reported, including a class and path changed together and ending Permanent elsewhere |
| `test_temporary_transition.py` | 8 | OD-8 transition: fresh install creates only `Temporary/`; new moves go there; upgrading a database left by earlier PR #4 code moves and rewrites nothing; legacy datasets stay valid, readable and consistent; recovery in the old folder; audited relocation; the Datasets-screen notice; nothing new under the old prefix |
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
| `test_placement_and_migration.py` | Expects schema **7**; migrations 5, 6 and 7 pinned by SHA-256 |
| `test_storage_class.py`, `test_two_applications.py` | Expect the new `Temporary/` folder (OD-8); the GUI test also checks that no `Temporary_Data` folder is created |
| `test_storage_integrity.py` | Uses the real Temporary→Permanent mapping instead of slicing the old prefix length (two tests had kept passing for the wrong reason after the rename) |
| `test_logic_modules_env_store.py` | Exact READY set updated |
| `test_window_home_and_folders.py` | Each app's Home lists its own modules |
| `Tests/gui/conftest.py` | The harness can start either app |
| `test_storage_integrity.py::test_tampering_done_before_migration_6_is_reported` | One assertion made precise: a class changed without its path is reported once, as a class/path mismatch |

## 2. GitHub CI (workflow `tests`, Windows and Ubuntu, Python 3.11, GUI tests required on Windows)

| Commit | Run(s) | Windows | Ubuntu |
|---|---|---|---|
| `852247f` (base, PR #3) | from PR #3 | success | success |
| `832b788` | 41325137464 and 41325143242 (push and pull-request triggers) | **success** (both) | **success** (both) |
| `de624a6` (same code as `330a9aa`) | 41328085918 and 41328091330 | **success** (both) | **success** (both) |
| `1760b57` and later | see the PR #4 checks | reported in the PR description | reported in the PR description |
| `9b2d063` (code `95a93c6`) | 41376952565 and 41376957877 (push and pull-request triggers) | **failure** (both): 839 passed, **1 failed** (`test_the_widest_valid_years_simply_cover_all_the_data`: `ValueError: format %y requires year >= 1900 on Windows`), 1 skipped | **success** (both) |
| `35fc897` (code `99d12b1`) | 41377917088 and 41377922020 (push and pull-request triggers) | **success** (both): 841 passed, 1 skipped (a macOS/Linux-only test), 195 GUI tests required and passed | **success** (both) |
| `7256cf1` (code `99d12b1`) | 41378632961 and 41378638271 (push and pull-request triggers) | **success** (both): 841 passed, 1 skipped (a macOS/Linux-only test), 195 GUI tests required and passed | **success** (both): 754 passed, 88 skipped |
| later commits (documentation only) | see the PR #4 checks | | |

The totals agree: Windows 841 + 1 = 842 and Ubuntu 754 + 88 = 842, the same 842 tests as the local run. Ubuntu CI has
no display, so its window tests skip; they are required on Windows. The one Windows skip is a test of a
macOS/Linux-only fallback.

## 3. What is NOT covered by any of the above

- Windows with Thonny or IDLE on the owner's computer (CI uses Windows, but not an IDE, and not the owner's files).
- The owner's 11 real sample files (not available in this environment; PR #3 tested them through Data Management,
  which is unchanged).

## 4. Practical acceptance in a virtual Linux environment (performed by Claude)

**How it was done.** `evidence_01_Nov_26/acceptance_walkthrough.py` drives the **real** windows of both applications
on a virtual screen (Linux), clicking the same buttons a person would. Where possible it checks results with plain
Python, independently of Q-MAP code: rows against the source CSV, weekly bars, statistics. Results:
`acceptance_results_01_Nov_26.json`; screenshots in `screenshots/`.

Re-run on code commits `832b788`, `330a9aa`, `1760b57` and `fb19fb0`: same 13 passed, 1 not applicable. On `fb19fb0` scenario 11 shows "NO DATA IN THIS PERIOD" (the walkthrough's check was updated to accept the new, more precise wording). On `1760b57` the Temporary move landed in `Temporary/Cleaned_Data/...` and no `Temporary_Data` folder was created. The evidence files in `evidence_01_Nov_26/` are from the original run, so they still show `Temporary_Data/`; that was correct for the code at the time.

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
| 9 | Permanent/Temporary and safe registry update | **Passed** | Moved to `Temporary_Data/...` in the original run (now `Temporary/...`, OD-8); checksum unchanged; `verify` found nothing missing or mismatched; audit row "completed" with its reason (screenshot 04) |
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
- [ ] Move a dataset to Temporary and back; confirm `Q-MAP_DATA/Temporary` is used, and nothing else changed.
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


## 7. Enhancement: Workbench dates, Open Output Folder, profile naming (01-Nov-26)

**Implemented and tested automatically.** The local results are in section 1; see the PR description for CI.

| Requirement | Evidence (automated) |
|---|---|
| Calendar on both date fields | `test_workbench_dates_and_output.py`: both boxes have a calendar; pick, clear and change month; typing still works afterwards |
| Four formats, DDMMYY, two-digit-year rule | `test_user_dates.py`: all four formats; six digits always DDMMYY; Unix timestamps refused; rule 00-68 / 69-99 for every format and equal to the profiles' pivot; independent of the computer's language |
| Invalid / impossible / reversed / blank | `test_user_dates.py`, `test_workbench_dates_and_runs.py` |
| Valid period without bars versus invalid input | `test_workbench_dates_and_runs.py` (after, before and inside the data on a weekend); window test |
| No run records or outputs for refused requests | Each refused case checks that there are no `runs` rows and no `Research_Reports` folder |
| Open Output Folder | Window tests: disabled before any run; exact recorded folder after a run; read-only copyable path; read from the registry after a restart; failed or refused runs do not replace it; missing folder; operating-system refusal |
| Profile standard and compatibility | `test_profile_library.py`: 14 IDs follow the rule; file name equals ID; display names match format, structure, Net Volume and fixed timeframe; Standard versus Example; each example reads like its standard; each standard reads like the verified sample-file profile; all earlier names resolve; glossary covers every token; user documents use no retired name; copies are labelled as yours; re-loading under a new name keeps the old dataset |

**Awaiting manual verification by the Project Owner (Windows, IDLE).** This is the short guide. Use the test folders
from the acceptance procedure.

1. **Database Manager → Data Management → Source profile list.**
   - Entries read like "Headered CSV: time (DD-MM-YY), … [Standard] (csv_hdr_ddmmyy v1)".
   - The Standard profiles come first, then the three "Example - …" profiles.
   - Selecting one shows "Kind of profile", "Profile ID" and "Earlier names".
2. **Load `csv headers std.csv`** with `csv_hdr_ddmmyy` (Standard; type the exchange, symbol and 1D).
   - **Expected:** accepted, 24 rows. This is the same result as with the earlier profile.
3. **Analytical Workbench → Run an analysis.** Select the dataset.
   - In **Start date**, type each of `07/10/26`, `07-10-26`, `07-Oct-26` and `071026` in turn.
   - **Expected:** each time, "= 07-Oct-2026" appears next to the box.
4. **Click Calendar...**, pick a day, then reopen it and press Clear.
   - **Expected:** the box fills with a date like "15-Oct-26", then empties.
5. **Type End date `31/02/26`.**
   - **Expected:** a red "not a real calendar date: February 2026 has 28 days".
   - **Run** → "INVALID DATE INPUT", and nothing is created in `Research_Reports`.
6. **Start date `01-Jan-30`, End date empty** → Run.
   - **Expected:** "NO DATA IN THIS PERIOD", showing the data's coverage. Nothing is created.
7. **Clear both dates** → Run.
   - **Expected:** "Completed".
   - "Last run folder" shows the run's folder; you can select the path and copy it with Ctrl+C.
   - **Open Output Folder** opens exactly that folder in File Explorer.
8. **Close and reopen the Workbench.**
   - **Expected:** the same folder is shown, and the button works.

**Known limitations:**
- The calendar is a small separate window; it closes when you pick a day, press Close or press Esc.
- Month abbreviations are English (Jan … Dec) by design, independent of Windows' language.

## 8. Independent review findings on `057b510` (02-Nov-26), fixed in `95a93c6` and `99d12b1`

| Finding | Confirmed? | Correction | Regression tests (all pass; the new ones fail on `057b510`) |
|---|---|---|---|
| `01/01/0000` raised Python's `ValueError` instead of `DateInputError` (`core/dates.py`) | **Yes.** `calendar.monthrange(0, 1)` works, and `date(0, 1, 1)` then fails. Only year 0000 can be typed and is out of range, because the formats allow exactly 4 year digits and Python supports 0001-9999. | The year is checked against `MINYEAR`-`MAXYEAR` first: "not a real calendar date: there is no year 0000 …". No narrower limit, because Q-MAP documents none. Related: a calendar pick outside 1969-2068 is now written with four digits, because `15-Jun-50` would read back as 2050. | `test_user_dates.py` (+28): every year-0000 spelling; every year 0000-9999 in three formats; 0001 and 9999 valid; valid and invalid leap days (2000, 2024, 2400, 0004 / 1900, 2100, 2025, 1969); two-digit-year boundaries (existing tests kept); box round-trip. `test_workbench_dates_and_runs.py`: Check and Run give INVALID DATE INPUT with no run record or folder; 0001-9999 covers all the data. Window tests (+4): live feedback, Check and Run for year 0000; calendar pick of June 1950. |
| A mixed selection was called NO DATA IN THIS PERIOD (`analytical_engine/base.py`) | **Yes.** The rule tested only the *failing* datasets, so one ready dataset plus one empty dataset gave `no_eligible_data`. | `no_eligible_data` now requires **every** selected dataset to be empty in the period, with no other failure and no selection problem. A mixed selection is `not_ready`, and the empty datasets are named in the readiness box, the Run message and the refusal. No new state. The per-dataset readiness facts are unchanged. | `test_workbench_dates_and_runs.py` (+12, plus 1 for the Windows fix), cases 1-6: one with bars; one without; several, all without; one with and one without (both orders); selection, timeframe and invalid-date problems take precedence; empty dates (both empty, and one empty). Each refusal: no run row, no folder, no outputs. The readiness-box text is checked for each state. |
| The roadmap told the reader to "review and merge PR #5" for Stages 3-4 "this PR" (`Outstanding_Work_Register.md`) | **Yes** | The roadmap now says PR #4 holds the implementation (stacked on #3, #2 and #1) and PR #5 holds documentation only. No decision status was changed. | Not applicable (documentation) |

**Found by Windows CI after the fix (commit `99d12b1`).** The new test with years 0001-9999 failed on Windows
only: `catalog.fmt_date` used `strftime("%d-%b-%y")`, and Windows refuses `%y` for years before 1900. A valid start
date such as `01/01/1850` would therefore have crashed Check readiness on Windows. `fmt_date` now uses the shared
date writer, which gives the same text for 1969-2068 (`05-Jan-26`) and keeps four digits otherwise. A new test
forbids `strftime` on this path, so it fails on Linux too (confirmed against the code before the fix).

Unchanged and still covered by the full suite: all date formats, the profile aliases and reading rules, the output
folder behaviour, and the earlier functionality.

**Additional Windows/IDLE checks (Project Owner; still outstanding):**
1. Type Start date `01/01/0000`. **Expected:** a red "there is no year 0000" next to the box. Check gives INVALID
   DATE INPUT, Run gives "Not started: the dates are not valid", and nothing appears in `Research_Reports`.
2. Load a second instrument with different dates. Select both datasets and enter a period that only one of them
   covers. **Expected:** NOT READY, naming the dataset that has no bars, and **not** NO DATA IN THIS PERIOD. Nothing
   is created.
