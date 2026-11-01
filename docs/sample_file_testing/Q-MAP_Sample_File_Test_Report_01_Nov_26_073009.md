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
1. *Decided 01-Nov-26:* `one_bar_per_period` and `timeframe_spacing` **stay non-blocking warnings for now**. They can be reconsidered later.
2. *Decided 01-Nov-26:* `ONESOURCE.parquet` **stays rejected** until its conflicting prices and other data-quality problems are investigated (see F.4).
3. File 8's constant volume: load it as volume (as now, with a warning) or treat the file as having no volume?
4. Approve or decline the grey "Waiting" row and summary text (D3-15).

**Limitations:**
1. **Windows/IDLE on your computer is not tested.** Please run the acceptance checklist on this branch, in a new folder.
2. **Incomplete trading days are not reliably detected.** See F.3 for the evidence and its impact.
3. The same data loaded from several files is stored as separate datasets. Choosing the "current" series is open decision F1.
4. Not covered by your samples: legacy `.xls`, multi-sheet workbooks, and semicolon or tab delimiters (the automated tests cover these with synthetic files).
5. Your sample files are **not** in the repository: only results, previews (first 8 rows) and fingerprints are.

---

## F. Follow-up review (01-Nov-26, before any merge request)

Documentation only: no code changed. Labels: **[V]** verified from the files, the stored data or GitHub · **[I]** inference · **[Q]** needs your confirmation.

### F.1 CI for PR #3 (head `3d1dc5c`): all 4 checks completed successfully [V]

| Job | Result |
|---|---|
| windows-latest (push run 41285153172) | 612 passed, 1 skipped (the Linux-only hard-link test); `GUI tests: 152 passed, 0 skipped … (required here: yes)` |
| windows-latest (pull-request run 41285123563) | Same counts. The Tk start-up retry fired **once** ("Can't find a usable init.tcl") and the next attempt succeeded |
| ubuntu-latest (both runs) | 561 passed, 52 skipped. The window tests skip by design (no display; required here: no) |

That retry matters. The main-thread clean-up (D3-13) fixed the test crash, but it did **not** stop the intermittent Windows Tk start-up fault. The earlier idea that the two were linked is therefore not supported [V]. The fault stays handled by the test-only retry, and its cause is unknown.

### F.2 Assumptions: what the data shows, and what only you can confirm

| Assumption used in testing | Evidence in your files | Status |
|---|---|---|
| **Instrument identity** (`TEST:F01`–`F11`) | No file name or column names an instrument [V]. On every day the files overlap (23, 26, 27, 29 and 30 Oct 2026), the 5-minute and 1-minute highs and lows lie within the daily file's range [V]. That fits one instrument, but cannot identify it [I]. Price levels: about 22,000–23,200 (2025–26 files), 900–1,000 (1995 file), 1,400–2,200 (Parquet) [V] | **[Q]** Exchange and symbol for each file, and whether the Parquet file is a different instrument |
| **Timeframes** 5m / 1D / 1m | Spacing measured: 5 minutes between 207 of 209 consecutive bars (files 1, 4, 9, 11); 1 minute for 429 of 430 (file 3) and 39,795 of 39,902 (Parquet); exactly one bar per date in the daily files [V] | Strongly supported. **[Q]** please confirm |
| **Bar timestamps mark the START of each bar** (new) | Full Parquet days run 09:15 → 15:29 (375 one-minute bars); full 5-minute days start 09:15 [V]. Q-MAP stores times exactly as given and does not record which convention a source uses | **[Q]** Confirm for each source. This matters later for avoiding look-ahead: a bar stamped 09:15 is only complete at 09:16 (or 09:20) |
| **Time zone Asia/Kolkata** | ISO files carry an explicit +05:30 [V], so only the trading date depends on the setting. Unix files: the first bars fall at 09:15 IST [V]. Naive Parquet times run 09:15–15:29 [V]; read as UTC instead, trading would be 14:45–20:59 IST, which is implausible [I] | Strongly supported. **[Q]** please confirm for the Parquet source |
| **Two-digit years** (`26` = 2026) | The same 24 rows read from `xls headers std.xlsx` as real Excel dates give 2026-09-25 … 2026-10-30, and stored identical rows [V]. The ISO-dated text file agrees on all 10 shared days [V] | Corroborated by the data. **[Q]** please confirm the source's convention |
| **Weekend bars** (new) | Daily Unix file: Saturday 01-Feb-25. Parquet: Saturday 08-Nov-25 (92 bars, 11:01–12:32, including the 3 rows with open below low) [V] | **[Q]** Real special sessions, or errors? |

### F.3 Known limitation: incomplete trading days are not reliably detected

**How it works now.** The warning "Some trading days are incomplete" compares each day's bar count with the most common count *in the same file*. Q-MAP has no trading calendar and no session hours, so it cannot know how many bars a full day should have. Days with *more* bars than usual are not flagged by this check either. Duplicated days are caught separately, as errors.

**Evidence from your files** [V]:

| File | Day | Bars (IST) | Full session would be | Flagged? |
|---|---|---|---|---|
| 5-minute (files 1, 4, 9, 11) | 23-Oct-26 | 71 (09:20–15:10) | 75 (09:15–15:25) | No |
| | 26-Oct-26 | 72 (09:15–15:10) | 75 | No |
| | 27-Oct-26 | 67 (09:15–14:45) | 75 | **Yes** |
| 1-minute (file 3) | 29-Oct-26 | 71 (14:04–15:14) | 375 (09:15–15:29) | No |
| | 30-Oct-26 | 360 (09:15–15:14) | 375 | No |
| Parquet | 21-Oct-25 | 61 (13:45–14:45) | 375 | Yes |
| | 08-Nov-25 (Sat) | 92 (11:01–12:32) | – | Yes |

So **4 of the 5 incomplete intraday days in your 5-minute and 1-minute files were not flagged.** None of those days is complete. ("Full session" assumes NSE's regular 09:15–15:30 hours with start-of-bar stamps [I].)

**Impact.**
- **Loading is not affected.** Every bar is stored exactly as in the source, and nothing is filled in or dropped.
- **The risk is to later research that treats a day's bars as a full session.** That includes daily open and close built from intraday bars, session returns, opening-range and closing studies, volume-by-time-of-day, bars-per-day statistics, and session-based features in MIQP and QLOPB.
- Example [V]: the last 5-minute close on 23-Oct-26 is 22,517.00, while the daily file's close is 22,600.00. Aggregating the 5-minute file would give a daily close that is 83 points off, and that day is not flagged.
- **Until this is fixed, do not use the warning as proof that a day is complete.** Check intraday coverage before any session-based analysis.

**Remedy (not implemented; needs your decision later).** A trading calendar with session hours per exchange, including special sessions. It is already listed as an open decision ("trading calendar"). With it, Q-MAP could flag every short, long or out-of-hours day against the expected session.

### F.4 ONESOURCE.parquet stays rejected

Rejection is the existing behaviour, so nothing changed. Items to investigate with the data provider [V]:

1. **Two whole sessions appear twice.** 17-Oct-25 and 24-Oct-25 (750 rows each instead of 375; source rows 28501–30811). 322 of the 750 duplicated timestamps have *different* prices or volume, so neither copy can be assumed right.
2. **Impossible bars.** Three rows on Saturday 08-Nov-25 (11:01, 11:02, 11:05; source rows 34187, 34188, 34191) have open 1425 below a high and low of 1777.6.
3. **Unusual sessions.** 21-Oct-25 has only 61 bars (13:45–14:45). 08-Nov-25 is a Saturday.
4. **Zero volume and an extra column.** 922 bars have zero volume (allowed, recorded). The `index` column (0–2,249, on 14,778 of 39,903 rows) looks like a row counter left over from processing; it is kept as `x_index` and never used.

After correction, the file can be loaded as new content with the same profile. The old rejection stays in the audit trail.

### F.5 Scope of PR #3 [V]

- **Branches.** PR #3 is based on PR #2's head `ff28305` and adds 6 commits (5 at the last review, plus this documentation-only one).
- **What it changes.**
  - `Application/qmap/data_engine`: ingest, mapping, process, readers and validation.
  - `Application/qmap_gui`.
  - Five new example profiles.
  - Tests.
  - One CI workflow line.
  - README, the decision log, and `docs/sample_file_testing/`.
- **What it does not touch.** Storage, the registry, the database schema and migrations, `core` configuration and runs, `pyproject.toml` and `CLEANING_CODE_VERSION`. No file is deleted.
- **Other branches unchanged.** `main` (`ad1baf1`), PR #1 (`424955d`) and PR #2 (`ff28305`) are as they were.
