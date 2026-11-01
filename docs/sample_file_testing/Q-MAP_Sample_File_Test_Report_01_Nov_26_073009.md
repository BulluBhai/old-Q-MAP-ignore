# Q-MAP: sample-file test report (01-Nov-26)

Branch `claude/qmap-audit-miqp-plan-547lid`. Code tested at commit `76dde7f` (the commit that adds this report changes
documentation only). Evidence: `evidence_01_Nov_26/` next to this file.

**How to read this.** "Accepted and verified" means Q-MAP loaded the file *and* every stored row was compared with an
independent reading of the original file (my own script, not Q-MAP code). Every stored row matched in date, time,
open, high, low, close and volume. It does **not** mean the data are correct market data, or that the instrument,
timeframe and time zone I chose are the right ones; those choices are listed under "Assumptions you need to confirm".

---

## A. Summary

**What was done.**
- PR #1 and PR #2 were reconciled onto a new feature branch.
- Your 11 files were inspected and tested stage by stage with matching profiles, through the GUI's own service layer and in a real Data Management window.
- Seven confirmed defects were fixed, each with regression tests, and the five fixes proposed earlier were included as separate commits.
- Nothing was merged. The pull request goes into PR #2's branch, not `main`.

**Reconciliation.** No conflict needed resolving. PR #2's head (`ff28305`) already contained every PR #1 commit up to `424955d` through merge `7f1ffbf`:
- recovery and run locks;
- configuration fingerprints;
- migrations 1–4;
- the future-date retry;
- raw restore.

The only Foundation file that differs between the two PRs is `core/config.py` (decision D3-02, behaviour unchanged). The feature branch starts from `ff28305`.
- Existing suite on that starting point: 506 passed and 38 skipped without tkinter; 564 passed with Tk under a virtual display.

**Your files.** All 11 actual files were available: you uploaded them as a zip, and their SHA-256 fingerprints are recorded. All 11 were tested.

| Result | Files |
|---|---|
| Accepted and verified row by row | **10**: all except `ONESOURCE.parquet` |
| Rejected as expected because of defects in the data itself | **1**: `ONESOURCE.parquet` (duplicate and conflicting timestamps, 3 impossible bars) |
| Failed because of a Q-MAP defect, with the right profile | **0** |
| Not tested | **0** |

**Readiness.** The data-loading path for these 11 layouts is ready for controlled use, but only once you have confirmed the assumptions below (instrument identity, timeframes, time zones).

Not yet verified:
- **Windows/IDLE on your own computer.** My tests ran on Linux, with real windows on a virtual screen.
- **Windows CI for this branch.** It runs when the pull request is opened.

---

## B. File-by-file results (your actual files)

Test identity: exchange `TEST`, symbols `F01`–`F11`. These are deliberately artificial, because the file names do not say which instrument each file is.

| # | File | Actual format | Profile used | Preview | Validation | Ingestion | Data verification | Issues | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `csv headers iso.xlsx` | XLSX (1 sheet), header row | `xlsx_headers_iso_offset` (same as new `example_xlsx_headers_iso_offset`), timeframe 5m | Pass: 210 rows, 7 columns | Pass; note: 27-Oct-26 has 67 bars vs 71 on another day | Accepted | 210/210 rows identical (UTC time, IST trading date, OHLC, Volume); Net Volume kept unchanged as `x_net_volume`; stored raw copy byte-identical | None. Timestamps are ISO text with +05:30 in Excel cells | `stage_outputs/F01_*`, `screenshots/F01_window.png` |
| 2 | `csv headers std.csv` | CSV, header row | `csv_headers_dd_mm_yy` (copy of `example_csv_dd_mm_yy` that asks for exchange/symbol), 1D | Pass: 24 rows | Pass. Day-first order is proven by the data (days above 12) | Accepted | 24/24 identical; 25-Sep-26 .. 30-Oct-26 | The example reads identity from the file name, which this name cannot give (finding A) | `F02_*` |
| 3 | `csv headers unix.csv` | CSV, header row | `csv_headers_unix_seconds` (copy of the example that asks for identity), 1m | Pass: 431 rows | Pass | Accepted | 431/431 identical; Unix seconds → 29-Oct-26 14:04 .. 30-Oct-26 15:14 IST | First day starts at 14:04 (incomplete) and is not flagged (limitation 4). Net Volume = ±Volume on every row | `F03_*` |
| 4 | `csv noheaders iso.csv` | CSV, **no** header | `csv_noheaders_iso_offset` (new example), 5m | Pass: first row shown as data | Pass | Accepted | 210/210 identical; **first row kept as data** (source row 1 = 23-Oct-26 09:20) | Column 7 is Net Volume, not a copy of volume (identical in only 7/210 rows), so the "duplicated volume" example rightly refuses it (case B2) | `F04_*` |
| 5 | `csv noheaders unix.csv` | CSV, **no** header | `csv_noheaders_unix_seconds` (new example), 1D | Pass: 144 rows | Pass | Accepted | 144/144 identical; daily bars stamped 09:15 IST (03:45 UTC); trading dates 01-Feb-25 .. 02-Sep-25 | None | `F05_*` |
| 6 | `ONESOURCE.parquet` | Parquet: `Date` timestamp (no zone), `Open`, `High`, `Low`, `Close`, `Volume` (int), `index` (decimal) | `example_parquet_naive_timestamp` (time zone Asia/Kolkata declared), 1m, exchange/symbol typed | Pass: 39,903 rows, 7 columns | **Rejected** (correctly), see below | Not attempted (stage rule). Stage 8: loading anyway is rejected, and the audit trail and problem report are correct | Interpretation checked on all 39,903 rows **without storing**: 0 mismatches in time (naive 09:15 → 03:45 UTC), trading date, OHLC, volume and `index` | **Defects in the data**: 750 timestamps appear twice (whole sessions 17-Oct-25 and 24-Oct-25; 322 of the pairs conflict); 3 bars on 08-Nov-25 have open 1425 below a low of 1777.6; 2 out-of-order steps. Not a reader defect | `F06_*`, `stage8_rejection_handling_ONESOURCE.txt` |
| 7 | `text headers ymd.txt` | Text (comma), header, 6 columns | `example_text_headered_iso_date`, 1D (fixed) | Pass: 10 rows | Pass | Accepted | 10/10 identical; the same 10 days match `csv headers std.csv` exactly | None | `F07_*` |
| 8 | `text no headers ymd.txt` | Text, **no** header, 7 columns | `example_text_headerless_seven_columns`, 1D | Pass | Pass, with **warning**: volume is 38,948,210 on every row | Accepted | 10/10 identical; columns 6 and 7 identical on every row, as the profile requires | Volume looks like a **placeholder** (decision 6) | `F08_*` |
| 9 | `xls headers iso.csv` | **CSV** (despite "xls" in the name), header | `csv_headers_iso_offset` (copy of `example_csv_iso_offset` that asks for identity), 5m | Pass: detected as text from its content | Pass; same note as file 1 | Accepted | 210/210 identical; same stored data as files 1, 4 and 11 | None. Content, not name, decides the format | `F09_*` |
| 10 | `xls headers std.xlsx` | XLSX, header, real Excel **date cells** | `xlsx_headers_native_date` (new example), 1D | Pass: 24 rows | Pass | Accepted | 24/24 identical; same stored data as file 2 | None | `F10_*` |
| 11 | `xls noheaders iso.xlsx` | XLSX, **no** header | `xlsx_noheaders_iso_offset` (new example), 5m | Pass | Pass; same note as file 1 | Accepted | 210/210 identical | None | `F11_*` |

**Cross-checks** [verified]:
- Files 1, 4, 9 and 11 (the same 5-minute data in four containers) stored identical rows.
- Files 2 and 10 (DD-MM-YY text and Excel date cells) stored identical rows.
- All 13 files in your zip are unchanged (SHA-256 before and after: `sample_files_sha256_*.txt`).
- All tests wrote only to isolated test folders.

**Real window** (`real_window_results.json`, `screenshots/`). For each file I added the file, chose the profile with **Browse for a profile file**, typed the exchange, symbol and timeframe, ran **Check files** and then **Load files into Q-MAP**. The results matched the table: 10 accepted, and the Parquet file "Would be rejected".

**Your earlier observations, re-tested** (`observation_cases.json`, 22 cases):

| Observation | Finding | Type |
|---|---|---|
| A. `NSE_NIFTY, 1(1).csv` with `example_csv_iso_offset` | The name lacks the `_` after the symbol that the pattern needs, so rejection is correct. **But** the message said "supply the value when ingesting" while the window disabled those boxes, and the engine ignores typed values for such profiles | Expected rejection, plus a **defect** in the advice (fixed) |
| B. `csv noheaders iso.csv` with a headered profile | Profile mismatch, correctly rejected. With the right header-less profile the file loads, its first row is kept as data, and the volume columns are handled correctly | Expected rejection; usability improved |
| C. `ONESOURCE.parquet`, E_INSTRUMENT_REQUIRED | Correct: that profile asks you to type exchange and symbol. With them typed, the reader and timestamps are correct; the file is rejected only for its data defects | Expected rejection; not a reader defect |
| D. Excel files with CSV/text profiles | Correctly rejected, **but** the window said "File type not supported – save as CSV or Excel" | Expected rejection, plus a **wording defect** (fixed) |
| E. Dates, times and timeframes | Wrong date order, wrong Unix unit, missing time zone, and date-only data declared intraday are all rejected with clear messages. **But** 5-minute bars declared `1D` were accepted silently | **Data-integrity gap** (now a warning; decision 1) |

---

## C. Defects and corrective changes

| # | Observed | Intended | Cause | Correction | Regression tests | Result |
|---|---|---|---|---|---|---|
| 1 | After typing exchange and symbol in the window, **Check and Load stayed disabled** and the hint still said "Type the exchange". Reproduced in a real window on `ff28305` | Typing re-checks at once | Nothing re-checked the form when the boxes changed | Re-check on every change to exchange, symbol and timeframe | `test_typing_the_exchange_and_symbol_enables_check_and_load_at_once` | Pass |
| 2 | File-name profiles: "supply the value when ingesting / type the exchange and symbol" | Advice that can be followed | Generic text; such profiles ignore typed values (D2-26) | Message names the pattern and says to rename the file or use a profile that asks; the window gains a note and a **"Copy so it asks me for exchange and symbol..."** button; a name that does not fit is noted before loading (advice, not a block) | `test_a_name_that_does_not_fit_is_rejected_with_advice_that_can_be_followed`, `test_logic_identity.py` (6), window test | Pass |
| 3 | Title "Exchange or symbol is missing" shown for a missing **timeframe** and for an **invalid** code | Correct title | One check name covers all three | Title "Exchange, symbol or timeframe is missing or not valid"; typed codes validated before anything runs | `test_invalid_typed_codes_are_reported_before_anything_runs` | Pass |
| 4 | A switched-off box kept showing an earlier value (e.g. Timeframe "1D" for a profile fixed at 1m) | An empty, switched-off box | Value not cleared when the profile changed | Cleared when switched off; the engine already ignored it | `test_a_switched_off_box_does_not_keep_showing_an_earlier_value` | Pass |
| 5 | Profile for another file type: "File type not supported – save as CSV or Excel" | "The profile is for a different file type" | Same check name as a truly unsupported file | New check name `format_matches_profile` with its own wording | `test_a_profile_for_another_file_type_is_reported_as_a_mismatch_not_as_unsupported` | Pass |
| 6 | An Excel workbook named `.csv` was detected as Excel but **could not be previewed or checked** (load worked, since it reads Q-MAP's stored copy) | Content decides everywhere | openpyxl refuses a file name without an Excel ending | Open the workbook through a file object | `test_an_excel_workbook_with_a_csv_ending_is_read_by_its_content` | Pass |
| 7 | **5-minute bars declared `1D` were accepted with no message** | The mismatch is reported | No check for several bars per day/week/month | Warning `one_bar_per_period`; the timeframe is never changed | 4 tests in `test_sample_file_findings.py` | Pass. **Blocking is your decision** |

Usability improvements (not defects):
- **Header hints.** A headered profile on a header-less file now says "the first row looks like data"; the opposite case gets warning `first_row_looks_like_header`.
- **Five new example profiles.** Previously no example could read an XLSX file, and none covered header-less ISO or Unix CSV files.

Also on this branch are the five fixes proposed earlier, as separate commits `ad8011f`, `e02d3ad` and `cfd84b2`:
- the GUI-test requirement on Windows CI;
- the main-thread clean-up that fixes the test crash;
- the Tk 9 drop-down fix;
- the "Waiting" status (its grey row and summary text await your approval);
- the decision-log status of D2-33 and D2-34.

---

## D. Automated testing

Test environments: Linux in my sandbox. E1 = Python 3.11.18 without tkinter; E2 = Python 3.11.15 with Tk 9.0; E3 = Python 3.12.13 with Tk 9.0. Windows was not tested here.
- Command: `python -m pytest -p no:cacheprovider -q`.
- For E2 and E3, run under `xvfb-run -a` with `QMAP_REQUIRE_GUI_TESTS=1`.

| Run | Starting point `ff28305` | Final `76dde7f` |
|---|---|---|
| E1 | 506 passed, 38 skipped | 541 passed, 46 skipped (window tests need tkinter) |
| E2 (GUI tests required) | not run at this exact commit | **613 passed**, 152 of 152 GUI tests ran |
| E3 (GUI tests required) | 564 passed | **613 passed**, 152 of 152 GUI tests ran |
| E3, 2 fresh environments | 6 of 6 crashed (reported earlier) | 2 of 2 passed (613) |
| pyflakes | clean | clean |

**New tests.** 23 in `Tests/integration/test_sample_file_findings.py`, 6 in `Tests/gui/test_logic_identity.py`, and 3 new window tests; plus the 17 tests from the earlier fixes. All use synthetic data.
- Run against the unmodified code (`ff28305`), **21 of the new tests fail**.
- The 8 that pass there confirm behaviour that must keep working: the new example layouts load, a fitting file name is read, and date-only daily data is unaffected.

**Manual and real-file tests** (separate from the automated suite):
- the stage-by-stage matrix on your 11 files;
- 22 observation cases;
- the real-window run of all 11 files;
- stage-8 rejection handling;
- the cross-container comparisons.

The scripts used are in `evidence_01_Nov_26/` (`run_matrix.py`, `obs_cases.py`, `gui_real_files.py`, `inspect_samples.py`).

---

## E. Remaining limitations and assumptions

**Assumptions you need to confirm before real use:**
1. **Instrument identity of each file.** I used `TEST:F01`–`F11`.
2. **Timeframes**, chosen from my reading of the data:
   - 5m for files 1, 4, 9 and 11;
   - 1D for files 2, 5, 7, 8 and 10;
   - 1m for files 3 and 6.
3. **Time zone Asia/Kolkata** for the naive Parquet timestamps and for every file's trading date.
4. **Two-digit years** in file 2: `26` is read as 2026 (pivot 69).

**Decisions for you:**
1. Should `one_bar_per_period`, and the existing `timeframe_spacing` warning (e.g. 5-minute data declared `1m`), **block** loading instead of warning?
2. `ONESOURCE.parquet`: correct the source, or decide which copy of each duplicated session is right. Q-MAP will not choose between conflicting rows.
3. File 8's constant volume: load it as volume (as now, with a warning) or treat the file as having no volume?
4. Approve or decline the grey "Waiting" row and summary text (D3-15).

**Limitations:**
1. **Windows/IDLE on your computer is not tested.** Please run the acceptance checklist on this branch, in a new folder.
2. "Some trading days are incomplete" compares days within the same file. With two or three days, or no complete day, it can miss one: files 1 and 3 have incomplete first days that were not flagged. There is no trading calendar yet.
3. The same data loaded from several files is stored as separate datasets. Choosing the "current" series is open decision F1.
4. Not covered by your samples: legacy `.xls`, multi-sheet workbooks, and semicolon or tab delimiters (the automated tests cover these with synthetic files).
5. Your sample files are **not** in the repository: only results, previews (first 8 rows) and fingerprints are.
