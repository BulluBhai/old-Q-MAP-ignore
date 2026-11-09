# Q-MAP v0.1, step A: PR dependency/status table and confirmed correction scope

Prepared 03-Nov-26 by Claude after the Project Owner's decisions on the release-readiness audit
(`Q-MAP_v0.1_Release_Readiness_Audit_03_Nov_26_165501.md`). Reference: Master Blueprint v1.35.
Nothing has been merged. No code has been changed yet.

## 1. PR dependency and status table

Each code PR targets the branch of the one before it; each head contains the previous head unchanged
(verified with `git merge-base --is-ancestor` on 03-Nov-26). Only PR #1 targets `main`.

| PR | Branch (head) | Base branch | Own commits | Last commit | Purpose | Depends on | Status | Superseded content |
|---|---|---|---|---|---|---|---|---|
| #1 | `claude/keen-carson-x872ge` (`424955d`) | `main` (at `ad1baf1`; `main` is now 11 commits ahead, documents only) | 8 | 31-Oct-26 | Stage 2 Foundation: configuration, registry, ingestion, validation, recovery | - | Open, unmerged | Its README/docs cite Blueprint v1.2 (updated later in the stack and again in Batch 1). Carries `docs/Q-MAP_Master_Blueprint_v1.0.md`, which the owner deleted on `main` (`4592692`); the file is unchanged in the stack, so the deletion is kept when merged (checked by a trial merge) |
| #2 | `claude/gui-data-management` (`ff28305`) | `claude/keen-carson-x872ge` | 7 | 01-Nov-26 | First GUI: `Q-MAP.py` launcher, Data Management | #1 | Open, unmerged | `Q-MAP.py` is kept as the older launcher (opens Database Manager); superseded as main entry point by #4 |
| #3 | `claude/qmap-audit-miqp-plan-547lid` (`852247f`) | `claude/gui-data-management` | 7 | 01-Nov-26 | Owner sample-file testing (11 files), fixes, audit fixes | #2 | Open, unmerged | None found |
| #4 | `claude/adoring-curie-5h2mx4` (`417552f`) | `claude/qmap-audit-miqp-plan-547lid` | 17 | 02-Nov-26 | Database Manager + Analytical Workbench (two entry points), schema 7, Temporary folder, profile naming | #3 | Open, unmerged | Blueprint v1.2 references (updated in #9 to v1.3) |
| #9 | `claude/happy-brahmagupta-su6tnr` (`b7a76c2`) | `claude/adoring-curie-5h2mx4` | 8 | 02-Nov-26 | Blueprint v1.3 Sources: discovery, automatic interpretation, schema 8, overlap reports | #4 | Open, unmerged | Some timeframe/identification rules refined by #10 (DQ-7..DQ-10, decisions D5-xx); history kept |
| #10 | `claude/friendly-babbage-8xyrgo` (`78323b4`) | `claude/happy-brahmagupta-su6tnr` | 17 | 03-Nov-26 | DQ-7..DQ-10 data automation, PR #9 acceptance findings, W1-W18 guide | #9 | Open, unmerged; CI green (Ubuntu + Windows) | Documents cite Blueprint v1.3 (to v1.35 in Batch 1) |

Not part of the release chain:

| PR / branch | Status | Decision |
|---|---|---|
| OW-33 branch `claude/youthful-babbage-d71hnl` (`2be97b1`, stacked on #10, no PR) | CI green; unreviewed | **Kept outside v0.1** (owner decision 5). Not merged into the release branch |
| **PR #5** `docs/blueprint-v1.2-and-handover` (`043a7f7`, base `main`) | Open | **Not closed.** See section 2 |

Trial merge: the whole stack (OW-33 head, which contains #10) merges into current `main` with no conflicts.
Release branch: `claude/epic-darwin-33o518` = PR #10 head + `main` merged (`b54be39`) + audit documents.
Merge order after acceptance, only with the owner's explicit approval: #1 → #2 → #3 → #4 → #9 → #10 → RC PR.

## 2. PR #5: not closed

PR #5 contains **unique content that Blueprint v1.35 still requires**: `docs/Q-MAP_Master_Blueprint_v1.2.md` and
`.html` exist on no other branch and not on `main`. v1.35 ("Version authority and supersession") says versions
1.0-1.3 "must be retained as historical records". The handover note in PR #5 is historical only.

Related finding: `main` holds v1.3 and v1.35 only. v1.0 was deleted from `main` on 03-Nov-26 (`4592692`; it is still
in the history), and **no v1.1 file exists anywhere in the repository**.

**Owner decision needed (R-6a):** either (a) merge PR #5 (documents only) so v1.2 is retained on `main`, possibly
restoring v1.0 the same way; or (b) accept retention in git history only and close PR #5 with that reason. Claude
recommends (a). PR #5 stays open until you choose.

## 3. IndexAnalytics repositories (read-only, for v0.2)

| Repository | What it is | Relevant to MIQP? |
|---|---|---|
| `BulluBhai-IndexAnalytics` (public; `a95b4e7`, 20-Jul-26; about 4,400 lines Python) | Streamlit app "Index Analytics v4.1": reads NSE index-constituent CSV files and a market-cap master workbook (`Mkt_Cap.xlsx`); SQLite schema (companies, indices, index_constituents, snapshots, nse_weight_caps); screens for index summary, free-float market cap, NSE weight-cap compliance, top holdings, company search, concentration, weight distribution, industry breakdown, cross-index comparison, heatmaps, Jaccard similarity | **Partly**: sector/stock intelligence (Blueprint §5.3-5.4) through index membership, industry weights and concentration. **No** OHLCV, market-regime, breadth or price methodology |
| `IndexAnalytics_v2` (public; `91e90d3`, 20-Jul-26; about 1,500 lines) | Earlier/smaller version of the same app with a dev-container | Same, less complete |

Reusable later: the constituent/weight processing engine (`processor.py`, declared UI- and database-free), its
data model, and the weight-cap rules. Would need decisions before use: constituent and market-cap data as a new
registered (non-OHLCV) dataset type in the Data Registry; source and licensing of constituent and market-cap files;
the weight-cap rule set and its provenance; the GUI (Streamlit is not the approved tkinter route; the GUI choice is
a Blueprint §17 open decision); committed `analytics.db` files containing data. **No MIQP regime/breadth material
was found.** Nothing from these repositories enters v0.1.

## 4. The three QLOPB safeguards (documented before implementation)

Source: QLOPB `PROJECT_NOTES.md` ("Current approved task: the owner approved only these three technical
safeguards") and `docs/project-context/MA_AFFINITY_V2_STATUS.md` (review findings 1-3). Implemented on QLOPB branch
`claude/youthful-bardeen-11wtok` (`9b4702d`, `e97c7b8`, `6cbadc7`), not merged into QLOPB `main`, **not independently
reviewed**. They change no formula, score, interaction rule or IS/OOS rule.

| # | Safeguard | Purpose | Code | Existing tests (QLOPB) |
|---|---|---|---|---|
| S-1 | Reject non-finite prices (+inf, -inf) | Infinity passed the "missing" and "positive" checks and could enter MAs and returns | `core/validation.validate_ohlc_frame` (research input), `core/data_engine.load_file` and `_load_parquet` (row reason `infinite_price`) | `test_infinite_prices_rejected_in_csv`, `test_infinite_prices_rejected_in_parquet`, `test_infinite_price_rejected_in_research_input`, `test_finite_prices_still_pass` |
| S-2 | Weights must be finite and not negative, with a finite total above 0, checked before any scoring (also with no interactions) | NaN/inf weights could contaminate every affinity score silently | `config/settings.weight_problems`, used by `MAResearchSettings.check` and `analysis/affinity_engine.score_window`; GUI text in `gui/research_controls.weight_text` | `test_invalid_weights_stop_scoring`, `test_invalid_weights_rejected_even_with_no_records`, `test_bad_weights_reported`, `test_zero_and_overflowing_total_weight_reported`, `test_valid_weights_still_pass` |
| S-3 | CSV rows with too many values are rejected (previously only too few) | Extra values were silently ignored, which can hide a shifted column | `core/data_engine.load_file` (`len(r) != ncols_expected`) | `test_row_with_too_few_columns_rejected`, `test_row_with_extra_columns_rejected_not_ignored` |

In Q-MAP, S-1 and S-2 apply directly (research input and settings). S-3 belongs to QLOPB's own file loader, which
Q-MAP does not use (Q-MAP's ingestion reads files); the loader is migrated unchanged so its tests keep running, but
the Workbench never calls it. QLOPB's 107 tests (96 on `main` + 11 safeguard tests) all passed locally on 03-Nov-26.

## 5. Timeframe suitability (owner decision 3)

Static comparison done (code read side by side); the numerical check runs as the first item of Batch 1 and must pass
before the Workbench offers weekly/monthly datasets to MA Affinity.

| Aspect | QLOPB `resample_ohlc` (not used in Q-MAP) | Q-MAP `derive` (`ohlcv_period_aggregation` v1) | Effect on MA Affinity |
|---|---|---|---|
| Source | any finer data | registered **daily** dataset only (intraday → daily refused, OD-5) | Daily-from-intraday is unavailable, not substituted |
| Periods | pandas periods W (Mon-Sun), M, Q | ISO week Mon-Sun, calendar month, quarter, year | Same |
| OHLC | first / max / min / last | first / max / min / last | Same |
| Volume | partial sum allowed | empty if any session empty | **Not used** by MA Affinity |
| Bar date | date of the last bar in the period | `session_date` = last included session | Same (no look-ahead) |
| Edge periods | first and last always `boundary_period` | `period_may_be_incomplete` only when the data start/end inside the period | Neither is used in the calculation; QLOPB's open item "incomplete aggregated bars" stays an owner question and is shown as a warning |

Expected result: identical bars and identical MA Affinity results. The check compares, on the real daily file and a
long synthetic daily series: bar dates, OHLC values, and the full MA Affinity result table for Q-MAP-derived W/M/Q
versus QLOPB's own aggregation of the same daily data. If any difference appears, the work stops and it is reported.

MA Affinity in Q-MAP runs **only on the timeframe of the dataset selected**. If no weekly/monthly dataset is
registered, the Workbench says so and points to Database Manager (Derive); it never aggregates on its own.

## 6. Dataset eligibility for MA Affinity (owner decision 4)

Readiness items, using **existing** Q-MAP classifications only (no DQ rule changes):

| Situation (existing Q-MAP classification) | MA Affinity | Message names |
|---|---|---|
| Rows flagged `conflicting_observation` (DQ-10: same timestamp, different values, kept and unresolved), including derived bars built from them | **FAIL** | number of conflicting timestamps and the first few dates |
| Timeframe `MIXED` | **FAIL** (existing readiness rule) | the measured intervals |
| Exact duplicate rows removed at load (DQ-10) | PASS, shown as information | count removed |
| Overlap/conflict with **another** dataset (DQ-1/DQ-9 report-only) | WARN, not blocking | the other dataset |
| Full-file interval finding "uncertain" or small "detected" section (DQ-7) | WARN | finding text |
| Gaps, large moves, `period_may_be_incomplete`, `date_order_unverified` | WARN | counts |
| Superseded, rejected, deleted, raw, damaged file | FAIL (existing rules) | as today |
| Too few bars for the chosen MA range / forward window | FAIL (QLOPB's own settings check, unchanged) | QLOPB's message |

## 7. Confirmed correction scope (Batch 1), in separate commits

1. **Timeframe check** (section 5): an integration test; it must pass before 2-4.
2. **QLOPB migration**: `Application/qlopb/` = QLOPB safeguard-branch engine, references, analysis, validation,
   reports and its 107 tests, **calculations unchanged** (a test confirms the migrated files match QLOPB `6cbadc7`
   byte for byte apart from import paths). QLOPB's tkinter GUI and launcher are not migrated.
3. **MA Affinity Workbench analysis** (`analytical_engine/ma_affinity.py`): reads the registered dataset, readiness
   per section 6, QLOPB parameters with QLOPB defaults, outputs (Excel, PDF, PNG charts, CSV tables, run log) in the
   Run ID folder with Run_Metadata; shown as available in the Workbench with QLOPB's limitation text. New runtime
   requirements pandas, scipy, matplotlib, reportlab (offered for install by the existing launcher).
4. **Build identification**: version `0.1.0rc1` plus a **build ID** in every run record and Run_Metadata: the git
   commit and a "modified" marker when run from a git checkout; otherwise a SHA-256 fingerprint of the
   application's source files (so two different builds with the same version are always distinguishable).
5. **Tests**: Q-MAP-fed versus standalone equality on both real files and synthetic data; each readiness case in
   section 6; Workbench GUI run; build ID differs when a source file changes; originals unchanged.
6. **Documentation**: references to v1.35; IDLE-first install; one **v0.1 Windows operating and acceptance guide**
   (setup, launch, Sources, Dataset Summary, MA Affinity, results, errors, close and restart; W1-W18 and A1-A8
   included); **v0.1 known limitations and release boundaries**; register and decision log entries.

Then step C (full Q-MAP + QLOPB suites, Linux local + CI Ubuntu/Windows), D (release documentation), E (RC PR, not
merged), F (owner Windows/IDLE acceptance support).

Out of scope, unchanged: MIQP, DQ-11, DQ-12, DQ-14, OW-33 Option C, `vs3`, reprocessing, dataset identities,
methodology changes, new modules.
