# Q-MAP data automation (owner instruction DQ-7 to DQ-10): implementation report, 03-Nov-26

Branch `claude/friendly-babbage-8xyrgo`, stacked on PR #9 (`claude/happy-brahmagupta-su6tnr`), which is stacked on
PR #4. Plan: `docs/architecture/Data_Automation_DQ7-DQ10_Plan_03_Nov_26_090000.md` (`ddc7c96`). Decisions D5-22 to
D5-31 in `docs/decision_log.md`. **Nothing is merged.**

## 1. Status at a glance

| Capability | Implemented | Automated tests (local) | CI | GUI acceptance (Windows/IDLE) | Ready for practical use |
|---|---|---|---|---|---|
| P1 exact duplicates / conflicting observations / overlap reports (DQ-10, DQ-9) | Yes | Pass | see PR | **Not done** | Not yet: needs W2, W3, W9 |
| P2 timeframe inference by sampling, any interval, MIXED (DQ-7) | Yes | Pass | see PR | **Not done** | Not yet: needs W1, W2 |
| P3 file-name cleaning, alias registry, identification (DQ-8) | Yes | Pass | see PR | **Not done** | Not yet: needs W1, W4, W5 |
| P4 default acceptance, reversible rejection, Stop, grouped exceptions, defaults for dates/zone | Yes | Pass | see PR | **Not done** | Not yet: needs W6-W12 |

"Ready for practical use" requires the owner's Windows/IDLE acceptance
(`Q-MAP_DQ7-DQ10_Acceptance_Checklist_03_Nov_26_120000.md`) and the open decisions in section 8.

## 2. What was implemented, per phase

### P1 — `dbce7ef` (DQ-10, DQ-9)
- `data_engine/process.py`: per instrument, after the time sort, rows sharing a timestamp are split into **exact
  duplicates** (every source column identical: the first kept, the others removed from the standardised copy and
  recorded) and **conflicting observations** (any difference: all kept, flag 32, warning with timestamps, fields and both
  values, and how many differ only in preserved extra columns). Row accounting includes removed duplicates.
- `validation.py`: the ERROR `no_duplicate_timestamps` is replaced; spacing, partial-session and one-bar-per-period
  checks count distinct timestamps (in stored order, so results do not depend on hash order).
- `overlap.py`: timestamps compared as sets of observations; findings carry source files, instrument, timeframe,
  range and "possible repeated import"; `check_new_datasets` and a consolidated `Overlap_Report_<stamp>.csv` used by
  the folder scan, Data Management (`qmap_gui/jobs.py`) and the command line (`cli.py`).
- Points of use (section 6.3): readiness shows a "conflicts" NOTE (never a failure); Dataset Summary adds
  "Conflicting timestamps"; derivation is no longer refused for conflicting dates (`derive.py`), periods flagged and
  warned. `CLEANING_CODE_VERSION` c1 → c2. Plain wording for the new checks (`messages.py`).

### P2 — `3e96bcc` (DQ-7)
- New `data_engine/timeframe_infer.py` (method in its docstring) and `core/timeframes.py` (open-ended values,
  `MIXED`). Configurable `[timeframe_sampling]`; part of the settings fingerprint (vs2).
- Every ingest path registers the measured interval (`process._settle_timeframe`); declared values are cross-checks
  (`timeframe_declared_differs`), used only when the data are too short (`timeframe_not_measurable`); `mixed_intervals`
  warning; record in `datetime_rules_json` and the info check `timeframe_inferred`.
- Readiness: `MIXED` FAILs for analyses needing one interval; Dataset Summary allows it with a NOTE.
- Sources interpretation rules v4: no timeframe questions unless unmeasurable; disagreements listed as warnings.

### P3 — `3876772` (DQ-8)
- New `data_engine/instrument_names.py`: `clean_filename`, alias registry (`Q-MAP_DATA/Reference_Files/
  Instrument_Aliases.csv`, validated: conflicts ignored and reported, duplicates, empty canonical, invalid), matching,
  `add_aliases` (bulk, backup, JSON record in its own run).
- Identification (rules v5): columns > correction > file name (pattern or cleaned name + registry) > provisional.
  Name/column disagreement → warning, column used. NSE default; crypto → `CRYPTO` category, venue unknown. ON by
  default for new folders; existing folders switched on by schema migration 9. Corrections allowed for imported files.
  `Identification_Exceptions_<stamp>.csv` per scan, grouped by kind and cleaned name. An edited registry
  re-identifies files on the next scan (its checksum is part of the scan fingerprint).

### P4 — `66895cc` and the documentation commit (sections 7, 8)
- Schema migration 10 `dataset_user_decisions` and `data_engine/user_decisions.py`: reversible reject/restore;
  rejected datasets are not offered to the Workbench and readiness refuses them with the reason.
- Sources screen: detected timeframe and instrument columns; the detail in the requested form ("Detected timeframe /
  Validation: Consistent across N sampled blocks / Status: Accepted by default"); grouped **Exceptions** box;
  multi-select **Reject / Restore**, **Save answer / correction** (bulk), **Add selected names to alias registry**,
  **Open alias registry folder**, **Stop scan** (safe: finishes the current file; lists the rest).
- Datasets and Storage: **Reject (reversible)** / **Restore**. Command line: `scan --folder`, `reject`, `restore`.
- Section 8 (rules v6): ambiguous day/month → day-first + warning + correction; no zone for zone-less timestamps →
  Asia/Kolkata + warning + correction (no warning when the values carry their own offset).

Files touched overall: 26 application files (+1,911 / −321 lines) and the tests and documents listed below.

## 3. Automated tests (local, Linux container; not CI)

New test files: `test_dq10_duplicates_conflicts.py`, `test_dq7_timeframe_inference.py`, `test_dq8_identification.py`,
`test_p4_workflow.py`, and five P4 window tests in `Tests/gui/test_window_sources.py`.

| Run | Passed | Failed | Skipped |
|---|---|---|---|
| Before this work (`ddc7c96`), Python 3.12 + Xvfb | 987 | 0 | 0 |
| After P1 / P2 / P3 / P4 (each, Python 3.12 + Xvfb) | 1000 / 1034 / 1068 / 1080 | 0 | 0 |
| Final, Python 3.12 + Xvfb (208 GUI tests) | 1080 | 0 | 0 |
| Final, Python 3.13 without tkinter | 959 | 0 | 95 (GUI, no display) |

Tests that encoded REPLACED approved rules were updated to the new approved behaviour (not weakened), each named
in the commit messages: duplicate timestamps rejecting a file; timeframe questions and declared timeframes winning;
exchange questions; name/column contradictions rejecting; plain names off by default; date-layout and time-zone
questions. Where a test exercised the question mechanism itself, it now switches file-name identification off, so the
mechanism stays covered. The Stop window test was run five times in a row (all passed). The 1-million-row test asserts
that at most 620 rows are examined.

## 4. Performance: timeframe inference on 1,000,000 rows (synthetic 1-minute sessions, 375 bars a day)

| Measure | Result |
|---|---|
| Time (inference only, two runs) | 9.6 ms and 8.1 ms |
| Extra memory (tracemalloc peak) | about 100 KiB |
| Rows examined | 620 of 1,000,000 (20 initial + 20 blocks × 30) |
| Blocks | 20, starting at rows 21981, 55772, 127810, 155090, 234716, 278228, 319202, 392911, 422654, 486131, 537906, 564152, 620777, 662207, 721387, 762405, 801380, 895428, 936670, 966503 |
| Result | 1 minute, "Consistent across 20 sampled block(s)"; identical blocks and seed on a second run |

Reading, parsing and validating every row (needed for integrity: dates, OHLC, duplicates, conflicts) is unchanged and
dominates the time of a real load; sampling limits only the inference.

## 5. The owner's eight files (copies; Linux; folder settings all left empty)

| File | Result | Timeframe (blocks) | Instrument | Notes |
|---|---|---|---|---|
| 5PAISA_30min.csv | Imported | 30 minutes (10) | NSE:5PAISA, provisional | |
| AKZOINDIA.parquet | **Not loaded** | 1 minute (20) | NSE:AKZOINDIA, provisional | Two bars with low above open (08-Nov-25 Saturday session): a data error, unchanged rule. Its repeated days would now be kept as conflicts (750 timestamps; 428 differ only in the `index` counter, DQ-12) |
| CRYPTO_RIVERUSD, 180.csv | Imported | 3 hours (10) | CRYPTO:RIVERUSD, venue unknown | |
| ICICIBANK.txt | Imported | Daily (5) | NSE:ICICIBANK, provisional | |
| NSE_BANKNIFTY, 15.csv | Imported | 15 minutes (15) | NSE:BANKNIFTY (file name) | |
| OLAELEC.xlsx | Imported | 1 minute (20) | NSE:OLAELEC, provisional | 2,817 exact duplicate rows removed; 183 timestamps with 366 conflicting observations kept and warned; 66,183 stored rows; Dataset Summary READY with notes, "Conflicting timestamps" 183 |
| UJJIVAN.txt | Imported | 5 minutes (15) | NSE:UJJIVAN, provisional | 75 exact duplicate rows (26-Mar-24 repeated) removed; 4,925 rows |
| VERANDA_1min.csv | Imported | 1 minute (20) | NSE:VERANDA, provisional | |

No question was asked. Exceptions were grouped into five lines (data errors; conflicting observations; names not in
the alias registry, 6 files; crypto venue unknown; time zone assumed for the three zone-less files). A second scan
added nothing. Screenshots of the real windows with these files: `evidence_03_Nov_26/`.

## 6. Existing analytical modules and repeated timestamps (section 6.3)

Only Dataset Summary exists (MIQP and QLOPB are not in the repository, OD-2). It reads the stored rows in order and
computes its statistics row to row; with conflicts, each stored row counts as a bar (a "return" between two
observations of one timestamp is included). This method is unchanged; the limitation is shown in readiness and in
the "Conflicting timestamps" column. Weekly/monthly derivation applies its unchanged rules to all rows of a period.

## 7. Deviations from the instruction, and limitations

- **Category and venue** (section 9): the registry has no separate fields, so crypto uses `CRYPTO` in the exchange
  field and records "venue unknown" in the interpretation; a schema change is proposed, not made (DQ-11).
- **Exact duplicate = every source column identical.** Export artefacts such as AKZOINDIA's `index` make copies count as
  conflicts (safe: nothing is removed wrongly). Whether such columns should be ignored is DQ-12.
- **AKZOINDIA** stays rejected for two impossible bars; DQ-10 covers repeated timestamps, not OHLC errors.
- The canonical display name ("NIFTY 50") was not written to `instruments.name`: fixed in the review follow-up (section 10.2).
- After this update every dataset is processed once more (new cleaning code, fingerprint and rules): identical
  content gets new dataset numbers, the old ones are superseded (OW-31).
- A bare number after "_" or a space is kept as part of a name (`NIFTY_50`), so `BAJAJ-AUTO_5` is not shortened; an
  alias handles such cases.
- No Windows, IDLE, OneDrive or Google Drive testing by Claude.

## 8. Decisions still required

DQ-11 (category and venue fields), DQ-12 (immaterial columns for duplicates), DQ-13 (AKZOINDIA source cleaning),
plus the earlier open items in `docs/Outstanding_Work_Register.md`.

## 9. Manual acceptance still required

All of `Q-MAP_DQ7-DQ10_Acceptance_Checklist_03_Nov_26_120000.md` (W1-W12), on Windows in IDLE.

## 10. Independent review follow-up (03-Nov-26), commit `2393721` and the documentation commit

CI on `054d87a` (before this follow-up): successful on Ubuntu and Windows (confirmed by the reviewer). The CI result
for this follow-up is recorded on the PR.

### 10.1 DQ-7 timeframe edge cases

Probe of the sampler (synthetic sessions, no calendar). Seed, block positions (first row of each block, 1-based) and
rows examined are reported so each result can be repeated:

| Case | Rows | Result | Block intervals | Rows examined | Seed | Block positions |
|---|---|---|---|---|---|---|
| A 1m then 5m (last 30%) | 61050 | mixed MIXED | {'1m': 18, '5m': 2} | 620 | 78149163127756 | 543, 3855, 7872, 11776 ... 60205 (20 blocks) |
| A2 1m then 5m (last 3%) | 78217 | consistent 1m | {'1m': 20} | 620 | 54990678878582 | 678, 7023, 7876, 13525 ... 76991 (20 blocks) |
| B unrepresentative start: 5m first 25 rows, then 1m | 53275 | consistent 1m | {'1m': 15} | 470 | 130807607494862 | 3005, 4120, 10205, 11490 ... 51157 (15 blocks) |
| C intraday 1m then daily bars | 27400 | mixed MIXED | {'1m': 19, '1D': 1} | 620 | 68613001332051 | 1108, 1930, 3499, 4460 ... 27021 (20 blocks) |
| C2 daily then intraday 15m | 5075 | mixed MIXED | {'1D': 1, '15m': 4} | 170 | 253701685620064 | 876, 1570, 2689, 3814 ... 4746 (5 blocks) |
| D irregular 2,000-row section in middle | 81438 | consistent 1m | {'1m': 20} | 620 | 47370629968531 | 3828, 5233, 10212, 14658 ... 78444 (20 blocks) |
| D2 irregular 300-row section | 80550 | consistent 1m | {'1m': 20} | 620 | 239117717117393 | 2755, 7195, 8063, 13190 ... 78087 (20 blocks) |
| E repeated timestamps every 10 rows | 3548 | consistent 5m | {'5m': 15} | 458 | 148119297008189 | 9, 385, 684, 831 ... 3391 (15 blocks) |
| E2 out-of-order section of 100 rows | 3225 | consistent 5m | {'5m': 15} | 470 | 149730941969829 | 176, 400, 632, 835 ... 2997 (15 blocks) |
| E3 fully descending file | 3225 | consistent 5m | {'5m': 15} | 470 | 268242514775332 | 90, 240, 542, 787 ... 3190 (15 blocks) |
| F small file 15 rows | 15 | consistent 5m | {'5m': 1} | 15 | 82662908989839 | 1 (1 block) |
| F2 small 59 rows | 59 | consistent 5m | {'5m': 1} | 59 | 4127326843391 | 1 (1 block) |

Findings:
- **Defect (fixed):** a block that fell in a daily section of an intraday file was measured with minute steps,
  found none and was silently skipped; and a block measured in days could "agree" with a 1-minute interval because both
  step values are 1. Blocks are now measured by their own observations and a day-based block never agrees with a
  minute interval (case C is now MIXED; it was "consistent 1m").
- **Limitation (confirmed, not a defect of the rule):** sampling cannot see a section shorter than the distance between
  two blocks (cases A2, D, D2: a 3 % tail, a 2,000-row and a 300-row section). Increasing the sample would only move
  the threshold. **Proportionate improvement (done):** validation, which already reads every row, reports any section
  of >= 30 consecutive same-day steps of one other interval, or >= 30 consecutive one-bar dates in intraday data, as
  `interval_change_detected` with its source rows. Tested for the four missed cases; no false positive on the owner's
  eight files or on a synthetic illiquid file. Whether such a finding should relabel the dataset `MIXED` is DQ-14.
  **Refined by the second review (section 11):** those four sections are regular whole multiples of 1 minute, so they
  are now reported as `interval_change_uncertain`, not asserted.
- Unrepresentative first rows only change the number of blocks (case B: candidate 5m, 15 blocks), not the result.
  Repeated, out-of-order and fully descending timestamps give the right interval. Files shorter than two blocks
  (60 rows) are examined completely.
- Tests: `Tests/integration/test_dq7_review_edge_cases.py` (17).

### 10.2 DQ-8 canonical display name

`instruments.name` already exists and is outside the identity trigger. The scan now stores the alias registry's
canonical display name there ("NIFTY 50" beside symbol `NIFTY_50`), only while it is empty (never overwritten), for
canonical and alias matches only (never for provisional names). No schema change; identity, paths and processing
identity are unchanged. Shown in Datasets and Storage and available as `DatasetInfo.instrument_name`.

### 10.3 DQ-9/DQ-10 conflicts at the points of use

| Entry point | Conflict visibility |
|---|---|
| Workbench readiness (and `run_analysis` used by it) | "conflicts" NOTE; recorded in the run metadata (`readiness_warnings`) |
| Dataset Summary output | Separate columns: Conflicting timestamps; Conflicting observation rows; Returns between conflicting observations; Derived bars built from conflicting observations; Exact duplicate rows removed at load; Conflict note ("Potentially misleading ..."); plus a WARNING line in the run log |
| Weekly/monthly derivation | assessment warning, flagged periods, `period_has_conflicting_observations` |
| Command line | no analysis command exists; `ingest`/`scan` print the load outcome, overlap findings and report paths, and the conflict check is in the issues report |

**Defect (fixed):** for a DERIVED dataset, Dataset Summary counted periods built from conflicts as "Conflicting
timestamps". Counts are now never conflated: in the test, 1 conflicting timestamp, 3 observation rows, 2 returns
between them, 2 exact duplicates removed at load, 10 bars; for the weekly dataset, 1 derived bar built from
conflicts and no "conflicting timestamps". The calculation method is unchanged and no row is selected.

### 10.4 Reprocessing and provenance

Verified by `test_reprocessing_after_the_update_keeps_every_record_and_links_correctly` (registry built with the
previous cleaning code c1 and rules v5, a derived weekly dataset and a Dataset Summary run, then the current code):
raw source files and stored originals unchanged and not duplicated; old datasets kept, files present, marked
superseded and linked to their successors; new datasets have the same original file as parent and point to the attempt
of the right file; provenance lines exist for both; the earlier run's inputs and output files remain; a second
unchanged scan creates nothing. **Exception (by design, reported):** a derived dataset stays linked to the daily
dataset it was built from, which is now superseded; it is not re-derived automatically (deriving again from the new
daily dataset is a user action, and the assessment warns about a superseded source).

### 10.5 Proposals kept out of PR #10

`docs/architecture/Proposals_DQ11-DQ14_03_Nov_26_150000.md`: DQ-11 (asset category and venue columns, migration 11,
backward compatible), DQ-12 (controlled list of export columns ignored for duplicate comparison, audited), DQ-13
(AKZOINDIA rows 34185 and 34189 of 08-Nov-25 with their values and the evidence needed; nothing changed), DQ-14
(relabel MIXED when the full-file check finds a material section).

### 10.6 Tests after the follow-up (local, not CI)

Python 3.12 + Xvfb: **1101 passed, 0 failed, 0 skipped** (208 GUI). Python 3.13 without tkinter: **980 passed, 0 failed,
95 skipped** (GUI, no display). Owner acceptance on Windows/IDLE: **not done** (checklist W1-W12 unchanged; W9 now also shows the new
Dataset Summary columns).

## 11. Second review (03-Nov-26): full-file check versus missing bars, commit `fad8d2f`

### 11.1 Finding

`validation._interval_changes()` compared each run of >= 30 identical same-day steps only with the expected interval.
That conflicted with the DQ-7 principle that gaps of whole multiples may be missing bars: a regular grid of multiples
(every other 1-minute bar present; 10-minute steps in 5-minute data) was asserted as "another interval", and >= 30
consecutive one-bar dates of a sparse instrument were described "like daily data" whatever their times of day. Random
missing bars were not affected (they never form 30 identical steps; bound below), and genuine changes were detected.

### 11.2 Correction (detection unchanged, classification new)

| Section found (unchanged rule) | Now | Why |
|---|---|---|
| >= 30 identical steps, not a whole multiple of the interval (3m or 7m in 5m data; any finer step) | `interval_change_detected` (WARNING) | missing bars cannot produce such a step |
| >= 30 identical steps, a whole multiple (2m in 1m; 10m in 5m; a 5m tail in 1m data) | `interval_change_uncertain` (WARNING): "another interval, or bars present only every k intervals" | the timestamps cannot tell these apart |
| >= 30 consecutive one-bar dates, >= 90 % at one local time of day outside the times the multi-bar dates use (e.g. 00:00, 15:30 after a 15:29 last bar) | `interval_change_detected` | cannot be surviving intraday bars |
| the same at a time the intraday bars also use (e.g. 09:15) | `interval_change_uncertain` | daily data, or one intraday bar per date |
| one-bar dates at varying times | not reported here (still in `partial_session`) | a sparse instrument, not another interval |

Bound: with independent gaps, a step of k intervals has probability q(1-q)^(k-1) <= 0.25, so 30 identical steps have
probability <= 0.25^30 ≈ 8.7e-19 per position; random missing bars never reach either check. The registered timeframe
is never changed (DQ-14 not approved). Sampling (`timeframe_infer.py`) is untouched: seed, block positions, rows examined
and the consistency rule are as before. The GUI shows the uncertain case as its own exception group with its own
explanation. Time of day uses the profile's exchange time zone (the same zone that defines the trading date).

### 11.3 Targeted regression tests (`Tests/integration/test_dq7_full_file_classification.py`, 16 tests)

Sampling result on the same timestamps (zone Asia/Kolkata, default configuration), and the full-file result:

| Case | Rows | Sampling | Block intervals | Rows examined | Seed | Block positions (1-based) | Full-file check |
|---|---|---|---|---|---|---|---|
| 1a 1m, middle 20 % with bars randomly missing (p 0.5; > 20 % of its steps are 2-minute gaps) | 72476 | consistent 1m | {'1m': 20} | 620 | 47702885879248 | 1142, 4427, 9955, 11466 ... 69564 (20) | nothing (correct) |
| 1b 1m, 5 days with every other bar missing | 81938 | consistent 1m | {'1m': 20} | 620 | 142183988441694 | 3889, 7278, 8590, 13201 ... 81449 (20) | uncertain, 2-minute grid |
| 1c 1m, 20 days with every other bar missing | 83813 | **mixed MIXED** | {'1m': 19, '2m': 1} | 620 | 153212517993164 | 92, 4327, 12076, 14649 ... 83016 (20) | not run (MIXED is not a single intraday timeframe) |
| 2 5m, 3 % of bars missing | 10463 | consistent 5m | {'5m': 15} | 470 | 279309678846803 | 194, 927, 1728, 2445 ... 10410 (15) | nothing |
| 2 5m, 10 % missing | 9729 | consistent 5m | {'5m': 15} | 470 | 106325263972693 | 325, 858, 1879, 2122 ... 9104 (15) | nothing |
| 2 5m, 25 % missing | 8164 | consistent 5m | {'5m': 15} | 470 | 7060488642778 | 259, 611, 1593, 1879 ... 7621 (15) | nothing |
| 3 5m with 200 rows of 3m / 7m / 1m | 11000 | consistent 5m (section missed) | {'5m': 15} | 468 | 131435030026616 | 602, 1410, 1923, 2476 ... 10557 (15) | **detected**, with source rows |
| 3b 5m with 300 rows of 3m, 1 % of them missing | 11297 | consistent 5m | — | — | — | — | **detected** |
| 4 5m sparse: 40 consecutive one-bar dates at varying times + scattered one-bar dates | 11682 | consistent 5m | {'5m': 15} | 455 | 137507532262368 | 6, 975, 2020, 2960 ... 11157 (15) | nothing; `partial_session` lists the dates |
| 5 1m + 60 one-bar dates at 00:00 | 40560 | consistent 1m | {'1m': 20} | 620 | 189009869754661 | 329, 3074, 5890, 7005 ... 40304 (20) | **detected** (daily) |
| 5 1m + 60 one-bar dates at 15:30 | 40560 | consistent 1m | {'1m': 20} | 620 | 196591891031131 | 1925, 3625, 4161, 7416 ... 39891 (20) | **detected** (daily) |
| 5 1m + 60 one-bar dates at 09:15 | 40560 | consistent 1m | {'1m': 20} | 620 | 233629776672805 | 789, 3450, 4689, 6751 ... 39704 (20) | uncertain |

Comparison with the sampling consistency rule (a block agrees when >= 90 % of its steps are whole multiples of the
dominant interval and that interval is >= 10 % of its steps):
- Random gaps (1a, 2): both methods agree — consistent, nothing reported.
- Genuine non-multiple sections (3, 3b) and daily bars outside intraday times (5): both treat them as another interval
  (sampling only when a block lands there; here the sections are short enough to be missed, which is what the
  full-file check is for).
- **Remaining difference, recorded, not changed:** a regular whole-multiple section (1c) and a long stretch of sparse
  one-bar dates make a sampled block disagree, so sampling registers MIXED when a block lands there; the full-file
  check reports the same evidence as uncertain (1b) or not at all (4). Aligning sampling would change the approved
  DQ-7 rule; it is offered as an option in the revised DQ-14 proposal (register OW-33).
- Updated existing test: `test_dq7_review_edge_cases.py::test_short_sections_missed_by_sampling_are_reported_by_validation`
  — its four sections (5m tail, 7m sections, daily bars at 09:15 in 1-minute data) are regular whole multiples, so the
  expected check changed from `interval_change_detected` to `interval_change_uncertain`; the assertions on severity,
  source rows and wording are kept, and it now also asserts that nothing is asserted as detected. Detection of genuine
  non-multiple changes is covered by the new tests (case 3, 3b, 5).

### 11.4 Items the review asked to be recorded (DQ-8, DQ-9/DQ-10, provenance; accepted, not redesigned)

- **Display names separate from machine-safe symbols:** the canonical display name ("NIFTY 50") is stored in
  `instruments.name`; the symbol (`NIFTY_50`) and exchange stay the immutable identity and storage path. Filled only
  while empty, only for canonical/alias matches (section 10.2).
- **Separate counts** (Dataset Summary columns, never conflated): conflicting timestamps; conflicting observation rows
  (affected rows); returns between conflicting observations (same-timestamp returns); derived bars built from
  conflicting observations; exact duplicate rows removed at load (section 10.3).
- **Warnings at the analytical points of use:** Workbench readiness NOTE "conflicts" (also stored in the run's
  `readiness_warnings`); Dataset Summary conflict note and WARNING log line; weekly/monthly derivation assessment
  warning and `period_has_conflicting_observations`; the issues report for command-line loads (section 10.3).
- **Preservation:** original source files and stored originals never change; earlier datasets stay (superseded and
  linked to successors, files kept); run records, their inputs and outputs stay; provenance lines exist for old and
  new datasets (section 10.4).
- **Known behaviour:** a derived dataset is **not rebuilt automatically** when its daily source is superseded; it stays
  linked to that source, the assessment warns, and deriving again is a user action (section 10.4, register OW-32).

### 11.5 Decisions after the second review

DQ-11 and DQ-12 approved in principle, not for PR #10: separate proposals
`docs/architecture/Proposal_DQ11_Asset_Category_and_Venue_03_Nov_26_075552.md` and
`docs/architecture/Proposal_DQ12_Technical_Export_Columns_03_Nov_26_075552.md`. DQ-13: AKZOINDIA unchanged; rows
34185 and 34189 stay rejected until authoritative evidence; investigation separate. DQ-14: not approved, timeframe
unchanged; revised proposal `docs/architecture/Proposal_DQ14_Revised_03_Nov_26_075552.md` (1 % materiality, from a
200-seed simulation: sampling registers a 1 % section MIXED for 20.5 % of seeds, 3 % for 60.5 %, 5 % for 99 %).
Decision log D5-36 to D5-39.

### 11.6 Tests after the correction (local, Linux container, not CI)

- Python 3.12 + Xvfb: **1117 passed, 0 failed, 0 skipped** (208 GUI tests).
- Python 3.13 without tkinter: **996 passed, 0 failed, 95 skipped** (GUI tests, no display).
- The owner's eight files were not available in this container, so the "no false positive on the owner's files"
  check of section 10.1 was **not repeated** for this change (to be covered by acceptance W1-W2).
- CI (GitHub Actions, Ubuntu and Windows, Python 3.11): recorded on the PR for the latest commit.
- Windows/IDLE acceptance W1-W12: **outstanding**.
