# DQ-14 (revised) — what the full-file interval check should do to the registered timeframe — NOT implemented

Supersedes the DQ-14 section of `Proposals_DQ11-DQ14_03_Nov_26_150000.md`. Written after the second PR #10 review
correction (commit `fad8d2f`). **Nothing below is built.** The registered timeframe stays the sampled one, as
instructed; the full-file check only reports.

## 1. Today (after `fad8d2f`)

| Finding of the full-file check | Check | Severity | Registered timeframe |
|---|---|---|---|
| >= 30 identical steps that are not whole multiples of the interval (3m or 7m in 5m data; anything finer) | `interval_change_detected` | WARNING | unchanged |
| >= 30 identical steps that are whole multiples (2m in 1m data, 10m in 5m data) | `interval_change_uncertain` | WARNING | unchanged |
| >= 30 consecutive one-bar dates at one time of day outside the intraday bar times (e.g. 00:00) | `interval_change_detected` | WARNING | unchanged |
| the same at a time the intraday bars also use (e.g. 09:15) | `interval_change_uncertain` | WARNING | unchanged |
| one-bar dates at varying times of day (sparse instrument) | none (dates stay in `partial_session`) | — | unchanged |
| randomly missing bars (irregular 2, 3, 4 ... interval gaps) | none | — | unchanged |

Sampling is unchanged (seed, block positions, rows examined, consistency rule: a block agrees when >= 90 % of its
steps are whole multiples of the dominant interval and that interval itself is >= 10 % of the steps).

## 2. What constitutes a material interval change

Two conditions, both required:

1. **Evidence it is a section, not noise:** a run of at least 30 identical steps (30 = one sampled block, so the
   full-file check and sampling judge the same amount of evidence). Under independent random missing bars a step of
   k intervals has probability q(1-q)^(k-1) <= 0.25 (maximum at k = 2, q = 0.5), so 30 identical steps have
   probability <= 0.25^30 ≈ 8.7e-19 per position; across a 1,000,000-row file <= 1e-12. Random gaps therefore never
   form a section; only a systematic pattern does.
2. **Size that matters for results:** the section (all its runs together) is at least **1 % of the dataset's distinct
   timestamps**. Below 1 % it affects at most 1 % of bar-to-bar returns; it is reported but not material.

## 3. Why 1 %: quantitative justification

Simulation (`fad8d2f` code, 80,625 synthetic 1-minute rows, a 5-minute tail of the given share, 200 different
sampling seeds; 20 blocks of 30 rows):

| Section share of rows | Rows | Sampling registers MIXED |
|---|---|---|
| 0.5 % | 403 | 8.5 % of seeds |
| 1 % | 806 | 20.5 % |
| 2 % | 1,612 | 42.5 % |
| 3 % | 2,418 | 60.5 % |
| 5 % | 4,031 | 99.0 % |
| 10 % | 8,062 | 100 % |

This matches the expected hit rate ≈ section share × number of blocks (20). Between about 1 % and 5 % the label
today depends on where the blocks happen to fall: the same kind of file can be MIXED or not, decided by the seed.
Using the full-file finding from 1 % upwards removes that dependence where it matters; above 5 % sampling already
finds the section almost always, so the change only aligns the two methods. Below 1 % the effect on results is
small and the warning is enough.

## 4. Missing-bar multiples versus another interval

- **Not a whole multiple of the interval** (including finer steps): missing bars cannot produce it. Another interval.
- **Regular whole multiple** (every step exactly k intervals for 30+ steps): either another interval or bars removed
  at regular positions. The timestamps cannot separate these; no rule should pretend otherwise.
- **Irregular multiples** (2, 3, 4 ... mixed): missing bars. Not reported.

Note the current asymmetry: when a sampled block lands in a regular-multiple section, the approved sampling rule
(dominant interval below 10 % of the block's steps) marks the block as disagreeing and the file is registered MIXED
(test `test_sampling_still_labels_a_sampled_regular_multiple_grid_mixed`). The full-file check is now more cautious
than sampling for the same evidence.

## 5. Sparse instruments

One-bar dates at varying times of day are missing observations, not daily data: never relabelled. Asymmetry today:
a sampled block that falls inside a long stretch of one-bar dates is measured in days and never agrees with a minute
interval, so sampling can register a sparse file MIXED (seed-dependent, recorded in
`test_a_sparse_instrument_with_one_bar_dates_is_not_another_interval`).

## 6. Proposed result

| Full-file finding | >= 1 % of timestamps | < 1 % |
|---|---|---|
| Detected (non-multiple, or daily bars outside intraday times) | **MIXED** (registered, with the section listed; same readiness rules as sampled MIXED) | warning only (today) |
| Uncertain (regular multiple; daily bars at an intraday time) | **unresolved classification**: sampled timeframe kept, warning kept, readiness shows a NOTE "possible interval change in rows ..."; the owner decides by correction (split the file, or confirm) | warning only (today) |
| Sparse one-bar dates; random gaps | nothing | nothing |

Optional, for consistency (separate decision, changes the approved sampling rule): make sampling treat a block that
is a regular whole-multiple grid, or a block of one-bar dates at varying times, the same way (unresolved, not MIXED).
Without it, sampled sections keep the stronger MIXED label.

Effects: a processing-rule version change (as with c2/vs2 in PR #10), so every dataset is processed once more (new numbers, old ones
superseded, nothing deleted). Effort: about one day with tests. Risk: low; the label only becomes more cautious for
detected sections and never changes for random gaps or sparse data.

## 7. Decisions requested

1. Approve the 1 % materiality threshold and the 30-step run.
2. Approve MIXED for material detected sections.
3. Approve "unresolved" (keep timeframe, NOTE) for material uncertain sections.
4. Decide whether sampling should be aligned (section 6, optional).
