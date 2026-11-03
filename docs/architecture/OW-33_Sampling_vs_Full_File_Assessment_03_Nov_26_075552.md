# OW-33 — should sampling and full-file validation classify regular-multiple sections and sparse one-bar dates the same way? Technical assessment — NOT implemented

> **Owner decision (D5-49): Option C selected.** Only step 1 is authorised: a read-only impact report of existing
> MIXED datasets whose classification would change under Option C. Option C itself, the `vs3` identity change and any
> reprocessing are **not authorised** until the owner has reviewed that report.

Requested by the Project Owner, 03-Nov-26 (D5-43). **Assessment only.** The approved DQ-7 sampling method is not
changed in PR #10. Any change below needs a separate approval.

## 1. The inconsistency

| Evidence in the file | Sampling (approved DQ-7 rule) when a block lands in it | Full-file check (`fad8d2f`) |
|---|---|---|
| Regular grid of whole multiples (every other 1-minute bar; a 5-minute tail in 1-minute data) | the block's dominant step is not the file's interval and the interval is < 10 % of its steps → block disagrees → **MIXED** | `interval_change_uncertain` (timeframe kept) |
| >= 30 consecutive one-bar dates at varying times (sparse instrument) | a block of one bar per date is measured in days and never agrees with minutes → **MIXED** | not reported (stays in `partial_session`) |
| Random gaps; non-multiple sections; daily bars outside intraday times | consistent / MIXED / MIXED | nothing / detected / detected (same conclusion) |

So for the first two rows the label depends on whether a block happens to land in the section (seed-dependent).

## 2. How often sampling registers MIXED today (simulation, 200 seeds each, default configuration)

Regular 2-minute section (every other bar) in 80,625 synthetic 1-minute rows:

| Section share of rows | Sampling MIXED |
|---|---|
| 1 % (806 rows) | 18.0 % of seeds |
| 3 % | 56.5 % |
| 5 % | 98.5 % |
| 10 % | 100 % |

Sparse stretch: N consecutive weekdays with one bar each at varying times, appended to 21,450 synthetic 5-minute rows:

| One-bar dates (share of rows) | Sampling MIXED |
|---|---|
| 30 (0.14 %) | 0.5 % of seeds |
| 60 (0.28 %) | 3.5 % |
| 120 (0.56 %) | 5.5 % |
| 240 (1.1 %) | 17.0 % |

A 5-minute tail of 1 % / 3 % / 5 % in 1-minute data gives 20.5 % / 60.5 % / 99 % (DQ-14 proposal, section 3) — the
same behaviour, because that tail is also a regular whole multiple.

## 3. Options

| Option | Regular multiples | Sparse one-bar dates | Effect on genuine changes |
|---|---|---|---|
| A. No change (today) | sampling MIXED when hit; full-file uncertain | sampling MIXED when hit; full-file nothing | none |
| B. Full alignment to the full-file view | sampling: "uncertain", timeframe kept | sampling: block ignored as missing data | **a genuine 1m → 5m switch covering 30 % of a file would no longer be MIXED** (test `test_an_interval_change_that_covers_a_material_part_of_the_file_is_mixed` would change), so single-interval analyses would no longer be blocked on it; only the NOTE would remain |
| C. Sparse-only alignment (recommended for assessment) | unchanged: sampling MIXED when hit (conservative for analyses) | a sampled block whose dates have one bar each at **varying** times of day is treated as missing data (insufficient), not as a day interval; at one time of day it stays a day interval | none for regular multiples; removes the seed-dependent MIXED for sparse instruments only |

Recommendation: **C**, if anything. Option B removes a protection the approved DQ-7 rule gives (a material coarser
section blocks single-interval analyses) and would contradict the case the owner already accepted as MIXED. Under C
the remaining asymmetry for regular multiples is deliberate: sampling's MIXED is the conservative reading, and DQ-14
(provisional) keeps the full-file uncertain finding as a NOTE without changing the label.

## 4. Impact on existing datasets

- **The owner's eight files:** in the last recorded scan (implementation report section 5, before `fad8d2f`) all
  seven loaded files were registered **consistent** (none MIXED); AKZOINDIA was not loaded. Options B and C only
  change blocks that today **disagree**, so a file whose blocks all agree keeps its label: **no label change expected
  for any of the eight**. Not re-verified with the files in this container (they were not available).
- **Other registries:** affected are only datasets registered MIXED whose disagreeing blocks are sparse one-bar
  stretches (C) or regular-multiple sections (B). Each dataset stores its inference (`datetime_rules_json`: seed,
  blocks, patterns) and its standardised data, so the exact list can be produced by a read-only report before any
  change: list MIXED datasets, re-run the candidate rule on their stored timestamps with the recorded seed, show
  which would change. Proposed as the first implementation
  step, for the owner to see the numbers before approving.

## 5. Is a processing-version change or reprocessing needed?

Yes, for either B or C (read from the code; not tested):
- Today no identity component records the sampling **code**: the settings fingerprint (`ingest.FINGERPRINT_KEYS`)
  holds the sampling **settings** only, and the scan's inputs fingerprint holds `RULES_VERSION`. Changing the rule
  silently would let old and new datasets of the same file disagree without a trace.
- Minimum: an inference method version recorded with every inference and included in the identity, e.g. fingerprint
  scheme `vs3` (sampling settings + method version) or a cleaning-code version step. As with OW-31 (c2/vs2), that makes
  **every dataset be processed once more** at the next scan or load: new dataset numbers, old ones superseded and
  linked, nothing deleted; files whose label does not change get identical content.
- A narrower alternative (reprocess only datasets whose label would change) needs a reuse rule that ignores the
  method version when the result is identical; it saves the one-off reprocessing but adds complexity to the
  processing identity. Not recommended unless the one-off reprocessing is a practical problem.

## 6. Decisions requested (before any implementation)

1. Choose A (keep), B (full alignment) or C (sparse-only alignment).
2. If B or C: approve the read-only impact report as step 1, and the identity change (`vs3` with a one-off
   reprocessing) as step 2.

## 7. Step 1 — the read-only impact report (authorised by D5-49; review corrections D5-53; prepared outside PR #10)

Branch `claude/youthful-babbage-d71hnl` (stacked on PR #10's branch; no pull request opened). **Option C is not
applied**; production sampling (`timeframe_infer.py`) is unchanged; no `vs3`, no reprocessing, no migration.
**Status: implemented and tested on synthetic data; NOT yet independently reviewed; NOT accepted; not yet run on the
owner's registry.**

### 7.1 What exactly is reconstructed

The registered inference is computed ONCE per ingest attempt on the parsed timestamps of EVERY row of the file, in
file order, before rows are split into instrument groups (`process.process_table` → `_settle_timeframe` →
`infer_from_parsed`); every cleaned dataset of that attempt registers the same timeframe. The exact input of a
dataset's inference is therefore the whole file's sequence, not its own rows. `reconstruct_input` rebuilds it only
when it can prove it complete and exact, otherwise the dataset is **NOT EVALUABLE** with the reason:

| Check | NOT EVALUABLE when |
|---|---|
| creating attempt | not recorded, outcome not `accepted`, evidence not readable, no recorded inference, no recorded sampling configuration |
| observation count | recorded `rows_total` differs from the attempt's rows read |
| shared inference | another dataset of the attempt is registered with a different timeframe |
| each dataset of the attempt (all statuses) | stored file missing; stored row count differs from the registry; a `src_row` outside 1..rows read; a source row stored twice; a row without a timestamp; timestamps and date-only values mixed |
| duplicate-removal lineage | count and listed pairs differ; unreadable pair; a removed row is stored; its kept row is not stored |
| completeness | any file position neither stored nor recorded as a removed duplicate (the reason says if no removal record exists) |

### 7.2 Reproduction check (before any Option C conclusion)

The unchanged sampling is re-run on the rebuilt sequence with the recorded configuration and compared with the
recorded evidence: observation count, seed, candidate, number of blocks, rows examined, block patterns, status,
timeframe, the registered timeframe, and for every block its start row, size, measured interval, step count,
agreeing share and agreement. Any difference is listed precisely (e.g. "block 3 (recorded start row 10933): steps
reconstructed 29, recorded 30") and the dataset is NOT EVALUABLE.

### 7.3 Option C calculation, shown per block

For every evaluable dataset the CSV has one `dataset` row and one `block` row per sampled block: start row, size,
interval, steps, agreeing share, original agreement, Option C role (`used` / `excluded` / `not measured`), the sparse
test with its facts (rows, dates, maximum distinct bars per date, distinct times of day, most common time share) and
the block's agreement under Option C. Rules: a block is excluded only if it is day-based, every date has one distinct
bar, fewer than 90 % of its bars share one time of day, AND another block of the same inference measures minutes.
Minute blocks (including regular whole multiples) are never excluded; fixed-time daily blocks are never excluded; a
series with no minute block is never affected.

### 7.4 Files, how to run, tests

- Code: `Application/qmap/data_engine/ow33_impact.py`; IDLE runner `ow33_impact_report.py` (top level).
- Run: open `ow33_impact_report.py` in IDLE, press F5. It uses the Q-MAP_DATA / Q-MAP_OUTPUT folders the Q-MAP
  applications remember (asks if none). The registry is opened read-only (SQLite `mode=ro`); settings are loaded
  without creating folders. It writes only `Q-MAP_OUTPUT\OW33_Impact\OW33_Impact_Report_<dd_Mmm_yy_hhmmss>.csv` and
  `OW33_Impact_Summary_<dd_Mmm_yy_hhmmss>.txt` and shows the counts.
- Tests: `Tests/integration/test_ow33_impact_report.py` (13): sparse blocks excluded only under Option C (production
  sampling unchanged); regular-multiple blocks stay MIXED; fixed-time daily blocks stay MIXED; a varying-time daily
  series without a minute block is unaffected; a two-instrument interleaved file with exact duplicates — each
  dataset's rebuilt input equals the file's sequence exactly, and a per-group concatenation would not reproduce the
  record; full report on a registry of four MIXED datasets, every stored file and the registry byte-identical
  afterwards; NOT EVALUABLE for a source row stored twice, a stored row missing, matching seed but a changed block step
  count, missing and incomplete duplicate lineage, and missing stored files (tampering only on copies).

### 7.5 Known limitations

- Not run on Windows and not on the owner's registry; the owner's report has not been produced.
- Datasets registered before the timeframe-inference record existed (no `timeframe_inference` or sampling
  configuration in the attempt) are NOT EVALUABLE by design.
- Only active MIXED cleaned datasets are examined; superseded datasets are not listed (their successors are).
- The report states consequences for lineage (new dataset and path, superseded old one, derived datasets not rebuilt,
  earlier runs keep inputs); it does not simulate the processing itself.
