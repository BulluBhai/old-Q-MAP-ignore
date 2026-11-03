# DQ-14 (revised) — what the full-file interval check should do to the registered timeframe — NOT implemented

Supersedes the DQ-14 section of `Proposals_DQ11-DQ14_03_Nov_26_150000.md`. Written after the second PR #10 review
correction (commit `fad8d2f`). **Nothing below is built.** The registered timeframe stays the sampled one; the
full-file check only reports.

> **Latest (D5-48): APPROVED FOR SEPARATE IMPLEMENTATION on the terms below; not implemented; not in PR #10.**
>
> **Owner decision, 03-Nov-26 (D5-42): PROVISIONALLY APPROVED, not implemented.**
> - 30-step minimum evidence and the 1 % materiality threshold (of distinct timestamps) for registering MIXED.
> - A **detected** section covering >= 1 % of distinct timestamps may cause the dataset to be registered as MIXED.
> - A **detected** section below 1 % is still reported as a warning; never silently ignored.
> - An **uncertain** section never changes the registered timeframe automatically: the timeframe is kept and a clear
>   warning/NOTE is shown, whatever its size.
> - The 1 % threshold is an **operational classification rule**, not a claim that smaller sections are harmless for
>   every analytical calculation.
> - The optional sampling alignment (section 6, last paragraph) is **not** approved; it is assessed separately in
>   `OW-33_Sampling_vs_Full_File_Assessment_03_Nov_26_075552.md` and must come back for approval.
> - Implementation needs a separate go-ahead (outside PR #10 unless the owner says otherwise).

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
2. **Size for the classification:** the section (all its runs together) is at least **1 % of the dataset's distinct
   timestamps**. Below 1 % it is reported as a warning but does not change the label. This is an operational
   classification rule: it does not claim that a smaller section is harmless for every calculation (a single
   section can still matter, e.g. for an event study that lands in it), which is why the warning always stays.

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
| Uncertain (regular multiple; daily bars at an intraday time) | **timeframe kept** (never changed automatically), warning kept, readiness shows a NOTE "possible interval change in rows ..."; the owner decides by correction (split the file, or confirm) | timeframe kept, warning (today) |
| Sparse one-bar dates; random gaps | nothing | nothing |

Optional, for consistency (separate decision, changes the approved sampling rule; **not approved**, assessed in
`OW-33_Sampling_vs_Full_File_Assessment_03_Nov_26_075552.md`): make sampling treat a block that is a regular
whole-multiple grid, or a block of one-bar dates at varying times, the same way. Without it, sampled sections keep
the stronger MIXED label.

Effects: a processing-rule version change (as with c2/vs2 in PR #10), so every dataset is processed once more (new numbers, old ones
superseded, nothing deleted). Effort: about one day with tests. Risk: low; the label only becomes more cautious for
detected sections and never changes for random gaps or sparse data.

## 7. Supporting evidence retained

- Simulation table in section 3 (200 seeds per share; 80,625 synthetic 1-minute rows; 5-minute tail).
- Regression tests: `Tests/integration/test_dq7_full_file_classification.py` (16) and
  `Tests/integration/test_dq7_review_edge_cases.py`; seeds, block positions and rows examined per case in the
  implementation report, section 11.3.

## 8. Decisions

1. 30-step run and 1 % threshold — **provisionally approved** (D5-42).
2. MIXED for detected sections >= 1 % — **provisionally approved**; below 1 % warning — **approved**.
3. Uncertain sections keep the timeframe with a NOTE — **approved** (no automatic change).
4. Sampling alignment — **deferred** (OW-33 assessment, separate approval).
5. Implementation — **not authorised yet**.
