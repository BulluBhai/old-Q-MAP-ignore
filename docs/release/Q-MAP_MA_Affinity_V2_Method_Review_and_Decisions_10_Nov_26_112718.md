# MA Affinity V2 release candidate: method review and decisions needed

**Date:** 10-Nov-26. **Author:** Claude (developer). **Not independently reviewed.**
**Scope:** the consolidated instruction of 10-Nov-26, sections 3, 4 and 9. This note records what was reviewed, what
was changed, what stays provisional and which decisions only the Project Owner can make.
**Nothing here is owner-approved methodology** unless it says so with a date and a reference.

## 1. What is V1 and what is V2

| | MA Affinity (QLOPB) = **V1** | MA Affinity V2 (chance-tested) = **V2** |
|---|---|---|
| Analysis id / Run ID prefix | `ma_affinity` / `MAAF_` | `ma_affinity_v2` / `MAA2_` |
| Status | Owner-tested beta (commit `2c81d3a`, A1-A7 passed 10-Nov-26) | Release candidate (beta), provisional defaults |
| Calculations | QLOPB Scanner V2, unchanged (identity-locked, D6-03) | V1's calculations reused unchanged, plus the additions in section 2 |
| Old runs | Reproducible as before | New; has its own result tables |

V1 was not changed. The only V1 code change in this cycle passes progress and cancel to QLOPB's existing arguments
(PR A); the V1 worked example still reproduces the frozen 09-Nov-26 evidence byte for byte.

## 2. V2 additions and their status

| # | Addition | What was checked | Status |
|---|---|---|---|
| 1 | **Chance test**: block-shuffled in-sample OHLC (bar ratios: gap, body, upper and lower wick), the full candidate scan on each shuffle, p = (1 + shuffles whose #1 >= real #1) / (shuffles + 1) | Every shuffled series is finite, positive and valid OHLC (many seeds, block lengths 2-40); first and last close kept; bar shapes kept; the full scan (every candidate) runs on every shuffle; the fast scorer equals `score_window` (V1 and relative strength references); same seed gives the same result; out-of-sample prices change no chance number; a planted MA bounce stands out, a random walk does not | Implemented, tested. **Defaults provisional**: 200 shuffles, 15-bar blocks, seed 1, threshold 0.05 |
| 2 | **Drift baseline**, report only | Equals a direct count; never enters the score | Implemented, tested. Report-only status is the owner's direction (10-Nov-26 chat) |
| 3 | **Relative interaction strength**: reference = min(V1 reference, median interactions of the same MA type within +/-20% of the period, at least +/-2); out-of-sample reference scaled by usable OOS / IS bars | Equals the documented rule; `Strength rule = v1` reproduces V1 | Implemented, tested. **The +/-20% median rule is provisional** |
| 4 | **Neighbour grouping**: same-type periods within Group % of a higher-ranked leader join its group; Top-N = leaders; full ranking kept | Reproducible; `Group % = 0` gives the V1 Top-N; members listed | Implemented, tested. **Group % 10 provisional** |
| 5 | **Optional ATR zone**: MA +/- k x Wilder ATR(p); first ATR = mean of the first p true ranges; no zone before that | Equals a direct ATR; the general detector equals V1's with a percentage zone | Implemented, tested. **p 14, k 1.0 provisional**; default zone stays `percent` |
| 6 | **MA warm-up** (added in this review): with a Start date, the MAs (and regime MA and ATR) also use the dataset's earlier bars; nothing is counted before the Start date; the in-sample/out-of-sample split is made on the chosen period only | No interaction before the start; the MA at each interaction equals the full-history MA; the warm-up bars stay real in every shuffle; readiness says how many earlier bars exist (PASS), warns when fewer than the longest MA, and refuses conflicting observations in them; `MA warm-up = none` is the V1 behaviour | Implemented, tested. **Provisional V2 default `earlier`** |
| 7 | **Executive interpretation** (eight plain-English answers) at the top of the findings file, the Excel Summary and the PDF | Every number in it is taken from the run's results (tested); it never calls a result proof of an edge | Implemented, tested. Wording to evolve with real examples (owner A8 direction) |
| 8 | Python and library versions in every build record; a reproduction states whether they differ | As in the merge package | Implemented, tested |

**V1 parity.** With `Strength rule = v1`, `Group % = 0` (and no Start date, or `MA warm-up = none`), V2 gives every V1
number exactly (engine-level tests over all five MA types). The frozen V1 evidence is reproduced by the V1 worked example.

## 3. Review of the earlier method observations (instruction section 3.6)

| Observation | Finding | Action |
|---|---|---|
| MA warm-up before the Start date | Genuine limitation in V1: rows before the Start date are dropped before the MAs are calculated, so EMA/RMA restart and an MA-200 loses 200 bars | V1 unchanged (identity-locked); fixed in V2 only (item 6), documented |
| EMA initialisation | QLOPB seeds EMA and RMA with the SMA of the first N bars (TradingView's `ta.ema` starts from the first price). Only the first bars of long MAs differ | **Design choice, not a defect.** Kept unchanged in V1 and V2. Changing it would be a methodology change needing an owner decision |
| Interaction side label | The side (Support/Resistance) compares the PREVIOUS bar's close with the MA of the event bar | Documented convention (the bar approaching the MA decides the side); unchanged |
| Stability and unused observations | Stability uses 4 chunks of n//4 interactions; up to 3 latest interactions are left out | Design limitation; unchanged; documented here |
| Interaction-strength cap and long MAs | V1 gives full strength at max(3 x min interactions, 20) for every period; long MAs produce fewer interactions | Addressed in V2 by item 3 (provisional); V1 unchanged |
| Fixed percentage zone | 3% means different things for quiet and volatile instruments | Addressed in V2 by the optional ATR zone (item 5); `percent` stays the default |
| Directed IR (+0.5 offset) and score weights | Open owner-review items | **Not changed and not finalised.** Pending owner decision |

## 4. Simplification audit (instruction section 9)

QLOPB code that Q-MAP never calls: `qlopb/core/data_engine.py` (613 lines, QLOPB's own file loader, reached only
through `run_full_pipeline`), `run_full_pipeline` in `qlopb/core/research_engine.py`, placeholder modules
`references/{pivot_points, cpr, camarilla, bollinger_bands, previous_levels, other_references}.py` (18 lines each;
imported by `references/__init__.py`, so loaded but not functional) and `analysis/{comparison_engine,
combination_engine}.py`. `storage/file_provider.py` and `core/timeframe_engine.py` are imported by the engine itself
(the latter's resampling is never used, because Q-MAP always runs on the registered dataset's own timeframe).

**Recommendation: keep them in this cycle.** Removing them changes files pinned by the identity test (D6-03,
`Tests/qlopb/test_qlopb_migration_identity.py`), so it needs a deliberate owner decision to relax that lock. They do
not affect any result. If removal is approved later, do it in its own PR: delete the loader, the pipeline function and the
placeholders together with their QLOPB tests, and replace the identity lock by a
recorded method version.

## 4A. Statistical interpretation and invalid null distributions

The legacy binomial baseline p-values are exploratory diagnostics, not definitive inferential evidence. The usual binomial
interpretation relies on independent observations. Market observations can be dependent and forward windows overlap;
these features can make nominal p-values too small and overstate the strength of evidence. The calculations are
deliberately preserved and must not be treated as proof of statistical significance or a trading edge.

The block-shuffle chance test requires a complete null distribution. Every requested shuffle must produce a finite
maximum score. If any shuffle is invalid, the overall chance result is marked **INCONCLUSIVE**, requested, valid and
invalid counts are recorded, and no empirical p-value or positive verdict is emitted. Candidate-adjusted p-values follow
the same completeness rule. Shuffle count, block length, seed, threshold and scoring method are unchanged.

## 5. Decisions needed from the Project Owner

1. **Chance-test defaults**: confirm or change 200 shuffles, 15-bar blocks, seed 1 and the 0.05 threshold.
2. **Relative strength rule**: confirm the +/-20% median rule, or choose another (the V1 rule stays selectable).
3. **Group %**: confirm 10, or choose another (0 = off).
4. **ATR zone**: confirm period 14 and multiple 1.0 as the option's defaults (`percent` stays the default zone).
5. **MA warm-up**: confirm `earlier` as V2's default.
6. **Directed IR and the score weights** (open since D6): still pending; nothing was changed.
7. **QLOPB unused code (D7-09)**: keep (recommended for now) or remove in a separate PR with the identity lock relaxed.

Until decided, each item stays a clearly labelled provisional default in the application, the reports and this note.
