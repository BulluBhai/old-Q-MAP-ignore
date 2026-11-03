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
- The canonical display name ("NIFTY 50") is not written to `instruments.name`; the symbol is `NIFTY_50` (OW-30).
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
