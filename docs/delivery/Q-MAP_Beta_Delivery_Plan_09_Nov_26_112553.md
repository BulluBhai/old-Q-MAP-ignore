# Q-MAP Controlled Analytical Beta: Integrated Delivery Plan

| | |
|---|---|
| Date | 09-Nov-26 (Day 1) |
| Required developer completion | **16-Nov-26** |
| Outer limit | 23-Nov-26, only for delays caused by Project Owner availability, decisions or acceptance testing |
| Lead Developer | Claude |
| Coordination and review | ChatGPT |
| Decisions, acceptance testing and merge approval | Sandeep (Project Owner) |

Claude acknowledges the 16-Nov-26 deadline. The extra week to 23-Nov-26 is not counted as development time.

Status words used in this plan:

| Word | Meaning |
|---|---|
| Implemented | The code exists on a branch. |
| Tested | Automated tests pass (local or CI, stated). |
| Reviewed | ChatGPT has reviewed it. |
| Accepted | Sandeep has tested it on Windows and accepted it. |

Nothing in this plan is called "accepted" unless Sandeep has accepted it.

---

## 1. Current state (audited 09-Nov-26)

### 1.1 Pull requests and how they stack

```
main
 └─ PR #3  sample-file testing and audit fixes
     └─ PR #4  Database Manager + Analytical Workbench (schema 7); contains PR #9 (discovery, schema 8)
         └─ PR #10  data automation DQ-7..DQ-10                         head b679a0f
             ├─ PR #21  owner acceptance fixes of 09-Nov-26 (W08, W14-W18, Add folder)   head 181b4ba
             └─ PR #12  v0.1 release candidate: MA Affinity (QLOPB) in the Workbench    head cbd6f08
                 └─ PR #15  docs: round-2c guide and tracker
                     └─ PR #16  docs: round-2c owner review
PR #20  docs only, to main: User Documentation Standard
```

PR #12 was based on an older PR #10 (`78323b4`). **Updated on Day 1:** final PR #10 and PR #21 were merged into PR #12
(`cb090db`, normal merge), PR #12's base was changed to PR #21's branch, and PRs #15/#16 were updated from it.

### 1.2 Status of each area

| Area | Implemented | Tested | Accepted |
|---|---|---|---|
| Database Manager: load, check, register, Datasets and Storage, derive weekly/monthly | Yes (PR #3/#4) | Yes, CI | Owner rounds 1-2c; final acceptance pending merge chain |
| Automatic folder discovery, scan integrity (PR #9) | Yes | Yes, CI | Owner W1-W18 run 09-Nov-26: two findings, fixed in PR #21 |
| Data automation DQ-7..DQ-10 (PR #10) | Yes | Yes, CI Windows + Ubuntu | Owner run 09-Nov-26: W08 and W14-W18 failed, fixed in PR #21 |
| PR #21 fixes | Yes | Yes: 11 new tests; local 1190 passed / 0 failed; **CI passed** Windows + Ubuntu (runs 42605682426, 42605786432) | No; owner retest needed |
| Analytical Workbench framework | Yes | Yes | Owner round 2c |
| Run ID, run folder, Run_Metadata (parameters, dataset checksums, build, lineage) | Yes | Yes | Part of round 2c |
| Readiness checks before a run | Yes | Yes | Part of round 2c |
| MA Affinity (QLOPB engine, unchanged calculations) on daily/weekly/monthly registered datasets | Yes (PR #12) | Yes: local 09-Nov-26 on PR #12, 1353 passed / 0 failed / 3 skipped (214 GUI) | Round 2c on an earlier build; not accepted as a beta |
| MIQP | **No.** Blueprint v1.35 §14.2: the MIQP material is documentation and an inventory, not an implemented application | - | - |

### 1.3 Gaps between MA Affinity today and the beta definition

| Beta requirement | Today | Gap |
|---|---|---|
| 1. Clear research question | Implicit in QLOPB | Write it down in the guide and in the reports |
| 2. Registered, suitable input data | Yes: registered datasets only, readiness checks | None |
| 3. Transparent parameters and methodology | Parameters shown; method source recorded | Methodology note for owner readers |
| 4. Real Python calculations | Yes (QLOPB engine) | None |
| 5. Meaningful results and presentation | Excel, PDF, PNG, CSV | Interpretation guidance |
| 6. Unique Run ID | Yes | None |
| 7. Provenance | Run_Metadata with dataset checksums, build, parameters, lineage | Check it is complete; add the input data date range used |
| 8. Reproducibility | Same inputs give identical CSVs (one test) | **No way to re-run a recorded Run ID and prove the result is identical** |
| 9. Readiness checks and warnings | Yes | None |
| 10. Limitations and interpretation guidance | Partial | Write them |
| Accuracy against an independent reference | Hand-calculated unit cases; identity with the original QLOPB code (same code, so not independent) | **An independent end-to-end reference calculation** |
| No look-ahead or leakage | MA "the future never changes the past" unit test; IS/OOS split | **An end-to-end test that later data cannot change in-sample ranking** |

### 1.4 Day 1 progress (09-Nov-26)

| Task | Status |
|---|---|
| T1 PR #21 guide corrections + retest guide (W08R, W14R-W18R only) | Done (`f2c9905`) |
| T2 PR #12 integration | Done (`cb090db`); local 1425 passed / 0 failed / 7 skipped (220 GUI); CI on the PR |
| T3 PRs #15/#16 updated | Done (`6e53fca`, `43121d1`) |
| Finding | PR #12 had already fixed the W14-W18 display gap in UAT round 1 (`56a72f4`, finding O1), but it never reached PR #10. PR #21 now uses that same implementation (`e5c9e69`), so the stack has one |

---

## 2. Selected beta workflow

**MA Affinity research on one registered NSE instrument (daily data; weekly and monthly as already supported).**

**Research question.** For this instrument, which moving averages (type and period) has price historically interacted with most reliably? Here "interacted" means price came within a set percentage of the MA, then moved in the expected direction over the following bars. Do the leaders chosen on the earlier (in-sample) part of the history keep that behaviour on the later (out-of-sample) part?

Why this workflow:

- It is the only mature quantitative workflow already in Q-MAP. The QLOPB calculations were migrated unchanged, with a test showing the code is identical to the original.
- It already runs only on registered data, with readiness checks, a Run ID and Run_Metadata.
- The remaining gaps (independent validation, re-running a recorded Run ID, leakage evidence, documentation) can be closed in seven days without new infrastructure.
- MIQP is not implemented. Building any MIQP capability in seven days would mean new, unvalidated calculations.

Single instrument per run, so survivorship bias across a universe does not arise. This is stated as a limitation, not claimed as a control.

---

## 3. Development tasks

The responsible person is Claude unless stated otherwise.

| ID | Task | Depends on | Output |
|---|---|---|---|
| T1 | PR #21: correct guide v2 (§4.4 step 2 and W8, which are ambiguous; the new "Folder settings not saved" window) and write a targeted retest procedure for W08, W14-W18 and Add folder, following the documentation standard | - | Guide update on PR #21 |
| T2 | Integrate PR #12 with final PR #10 + PR #21 by a normal merge (no rebase), resolve the 6 conflicting files, full suite, CI | T1 code final | PR #12 updated |
| T3 | Update PR #15 and #16 (docs only) from PR #12 by normal merge | T2 | PRs #15/#16 updated |
| T4 | **Independent reference implementation** of MA Affinity, written in the test suite from the methodology, not from the engine code. It covers MAs, zone entries, cooldown, forward returns, success, scores, IS/OOS split and the Top-N freeze. Compare the full candidates and interactions tables on synthetic data with known answers and on one fixture file | T2 (beta branch) | Validation tests + evidence file |
| T5 | Hand-worked reference case: a short series whose results are worked out by hand and listed in the validation evidence | T4 | Evidence document |
| T6 | **Leakage tests**: (a) changing or removing bars after the in-sample cut-off leaves the in-sample ranking and the frozen Top-N unchanged; (b) changing bars after bar t leaves every MA value and zone entry up to t unchanged; (c) forward outcomes never use bars beyond the period end | T2 | Tests |
| T7 | **Reproduce a run**: given an earlier Run ID, read its Run_Metadata, check each input dataset still has the recorded checksum and that the build is the same (if not, say so), re-run with the recorded parameters, then compare result-table checksums. Writes `Reproducibility_Report_<stamp>.csv` in the new run folder. Workbench button + one function; no new storage | T2 | Feature + tests |
| T8 | Provenance completeness: record the bars actually used (first/last date, row count) and the methodology version in Run_Metadata and the reports; test that all items in §7 are present | T2 | Code + tests |
| T9 | Research question, methodology summary and limitations printed in the PDF/Excel report header (text only; calculations untouched) | T8 | Reports |
| T10 | End-to-end research example: scan → readiness → run → results → reproduce, on synthetic data; outputs captured as evidence | T4-T9 | Evidence folder |
| T11 | MA Affinity beta user guide: research question, how to run, every parameter, how to read the results, limitations | T9 | `docs/user_guides/` |
| T12 | Owner Windows beta acceptance guide + tracker (documentation standard) | T7, T11 | `docs/acceptance_testing/` |
| T13 | Full regression, Windows/Ubuntu CI, defect correction | all | CI links |
| T14 | Beta readiness pack: requirements-to-evidence matrix, PR map, test and CI results, validation and reproducibility evidence, limitations, status | all | `docs/delivery/` |
| R1 | Review PR #21, the plan, then T4-T9 as they land | Each PR | ChatGPT |
| O1 | Decisions D-1..D-7 (section 6) | - | Sandeep |
| O2 | Retest PR #21 on Windows (W08, W14-W18, Add folder) | T1 | Sandeep |
| O3 | Beta acceptance on Windows | T12 | Sandeep |

**New branch:** `claude/beta-ma-affinity`, stacked on PR #12 after T2, opened as one PR. It holds T4-T12. PR #21 stays on `claude/laughing-lamport-tqy0vr`.

**Parallel work.**

- These four run side by side: T1 and O2 (PR #21); T2 then T3 (stack integration); T4, T5 and T6 (validation); T7 and T8 (reproducibility and provenance).
- T4 and T6 can start on Day 2 against PR #12 as it is. They are not blocked by owner decisions.

---

## 4. Daily milestones

| Day | Date | Claude | ChatGPT | Sandeep |
|---|---|---|---|---|
| 1 | 09-Nov-26 | Audit; this plan; T1; start T2 | Review plan and PR #21 | Decisions D-1..D-7 |
| 2 | 10-Nov-26 | Finish T2 (CI green), T3; start T4, T6 | Review T2 | Retest PR #21 (O2) if T1 is ready |
| 3 | 11-Nov-26 | T4, T5, T6 complete; start T7 | Review validation approach | O2 if not done |
| 4 | 12-Nov-26 | T7, T8 complete with tests | Review T7/T8 | - |
| 5 | 13-Nov-26 | T9, T10, T11 | Review guide | - |
| 6 | 14-Nov-26 | T12; full regression + CI (T13); fixes | Independent review of the beta PR | - |
| 7 | 15-Nov-26 | T14 readiness pack; all PRs submitted | Final review | Start O3 |
| 8 | 16-Nov-26 | **Developer work complete**; any review fixes | - | O3 |

---

## 5. Testing and numerical validation

- Every change runs the full suite locally (with tkinter under xvfb, so GUI tests run) and on CI (Windows and Ubuntu, Python 3.11). Local and CI results are reported separately.
- **Independent reference (T4):** a separate, plain implementation written from the written methodology. It must agree with the engine on every row of the candidates and interactions tables:
  - counts and statuses exactly;
  - numbers to 1e-9 relative.
  Any disagreement is investigated and reported, never tolerated by loosening the comparison.
- **Known-answer cases (T5):** synthetic series built so that interactions, forward returns and success rates can be worked out by hand.
- **Leakage (T6):** perturbation tests, as described in T6.
- **Reproducibility (T7):**
  - re-running a recorded Run ID gives byte-identical result tables;
  - a changed dataset or build is detected and reported, not hidden.
- **Regression:** existing QLOPB identity and output tests stay unchanged. No test is weakened.

---

## 6. Decisions required from Sandeep

| ID | Decision | Impact if delayed | Default Claude continues with |
|---|---|---|---|
| D-1 | Approve MA Affinity (single NSE instrument, daily, plus registered weekly/monthly) as the beta workflow | Scope of T4-T12 | MA Affinity, as proposed |
| D-2 | The forward-return weight uses "Directed IR", marked "pending owner review" since 03-Nov-26. Accept it for the beta, or change it | Results and guide wording | Keep as is, labelled pending in reports |
| D-3 | Approve the stack integration: PR #21 and final PR #10 merged into PR #12 by normal merges; beta PR stacked on PR #12 | T2 | Proceed (no merge to main, no rebase) |
| D-4 | Where Add folder first opens | - | **Decided 09-Nov-26 (PR #21 comment): the application folder, then the last folder chosen** |
| D-5 | Your available days for the PR #21 retest (about 30 minutes) and the beta acceptance (about 1-2 hours) | Acceptance dates | 10-11-Nov-26 retest, 15-16-Nov-26 beta |
| D-6 | Python version on your laptop: open IDLE and read the first line (records say 3.12.10; you said 3.11) | Launch instructions | Both supported; guide says "3.11 or newer" |
| D-7 | PR #12 contains two QLOPB fixture files (`NSE_SBIN, 60.csv`, `Nifty500 Healthcare.txt`) that appear to be real market data. The working rule is "no real market data". Confirm they may stay, or they will be replaced with synthetic data | Validation uses synthetic data only either way | Use synthetic data for all new evidence |

Merges: no PR is merged without your explicit approval. The beta can be completed and evidenced without merges, but "accepted" needs your testing and approval.

---

## 7. Beta acceptance criteria

1. The full suite passes locally and on Windows and Ubuntu CI on the beta PR head.
2. The independent reference agrees with the engine on every candidates and interactions value (T4, T5).
3. The leakage tests pass (T6).
4. Re-running a recorded Run ID gives identical result tables. A changed dataset or build is reported (T7).
5. Run_Metadata names:
   - the run ID;
   - the analysis and its version;
   - the method source;
   - the build (code version);
   - every parameter;
   - each input dataset with its ID, checksum, processing version and lineage;
   - the bars used (date range and row count);
   - the readiness warnings.
6. A dataset that fails readiness is refused before any run, with the reason.
7. The reports state the research question, the method, the IS/OOS split and the limitations.
8. The user guide and the owner acceptance guide follow the documentation standard.
9. Sandeep completes the Windows beta acceptance and records the result. Only then is the beta "accepted".

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| The PR #12 integration conflicts take longer than planned (6 files, 5 code conflict blocks) | Day 2 is reserved for it; T4 and T6 start on PR #12 as it is |
| The independent reference finds a difference in the QLOPB engine | Report it immediately with the case. Do not change QLOPB calculations without your decision (they are approved as unchanged) |
| Owner availability for retest and acceptance | Retest kept short; the developer pack is complete regardless; delays recorded against the outer limit |
| The merge chain (#3 → #4 → #10 → #21 → #12) is not merged by 16-Nov-26 | The beta is evidenced on the stacked branch. Merging is your decision and does not block developer completion |
| Windows CI is the only Windows evidence before your test | Your acceptance guide covers launching and running on your laptop |

## 9. Deferred until after the beta

- MIQP (any part).
- Opportunity Scanner.
- General backtesting.
- Portfolio and risk analytics.
- Multi-instrument or universe research.
- Broad intraday expansion. MA Affinity stays daily/weekly/monthly; intraday and quarterly are refused as today.
- Additional data providers.
- CPR, pivots and other QLOPB placeholder references, which already refuse to calculate.
- GUI polish not needed for the workflow.
- The open items DQ-3, DQ-5, DQ-6, D3-xx, OW-32/33/40/41, unless they block the beta.
