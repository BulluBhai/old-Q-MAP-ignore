# Q-MAP v0.1: release reconciliation and readiness (07-Nov-26)

**Prepared by Claude after the Project Owner's formal acceptance of the round-2c Windows UAT. Documents only; no
program, data, registry or research output was changed. No PR was merged.**

## 1. Acceptance status

| Item | Status | Record |
|---|---|---|
| Windows owner acceptance (UAT round 2c, build `a202d43d78ed`) | **ACCEPTED** by the Project Owner, 07-Nov-26: "I formally accept the Round 2c Windows UAT results recorded in PR #16." | D6-27; OW-34 resolved; `docs/acceptance_testing/Q-MAP_v0.1_UAT_Round2c_Owner_Results_Review_07_Nov_26_173737.md` |
| Test 21 pop-up calendar | **ACCEPTED** separately by the Project Owner | Review section 6 |
| Real-data W5 decision (old duplicate NSE:RELIANCE_EQ) | **Done** in test 16: dataset 13 rejected (reversible), dataset 18 NSE:RELIANCE active | Review section 3, D6-27 |
| **Controlled analytical use** | **Not approved.** UAT acceptance confirms the application behaves as specified on Windows. It is not an approval to rely on research results. | Section 6 below |
| Merge of any PR | **Not done.** The Project Owner holds merge authority. | - |

## 2. Pull requests

CI is the repository workflow "tests" (Windows and Ubuntu, Python 3.11 and 3.12). It is defined only on the release
chain branches, so PRs based on `main` have no CI.

| PR | Content | Base | Head | Latest CI on head | State |
|---|---|---|---|---|---|
| #1 | Stage 2 foundation | `main` | `424955d` | #12 success | Ready (reviewed in earlier rounds) |
| #2 | First GUI, Data Management | #1 | `ff28305` | #21 success | Ready |
| #3 | Sample-file testing and audit fixes | #2 | `852247f` | #27 success | Ready |
| #4 | Database Manager / Analytical Workbench (schema 7) | #3 | `417552f` | #48 success | Ready |
| #9 | Sources, automatic interpretation (schema 8) | #4 | `b7a76c2` | #54 success | Ready |
| #10 | Data automation DQ-7..DQ-10 | #9 | `78323b4` | #72 success | Ready |
| #12 | v0.1 release candidate (code `06d8659`, build `a202d43d78ed`) | #10 | `cbd6f08` | #122/#123 success | Ready. UAT accepted; open owner decisions listed in section 3 do not change its code |
| #15 | Docs: round-2c easy guide and tracker | #12 | `7b26334` | #128/#129 success | Ready (historical guide used for round 2c) |
| #16 | Docs: round-2c results review (accepted), guide v2, tracker v2, records | #15 | this update | see PR | Ready |
| #17 | Docs: permanent User Documentation Standard | `main` | `cd72480` | no CI (docs only; base without workflow) | Ready |
| #5 | Docs: Blueprint v1.2 copies and 01-Nov-26 handover | `main` | `043a7f7` | no CI | Approved in D6-09; **merge awaits the Project Owner's confirmation of its content check** |
| #13 | Docs: GitHub governance | `main` | `8d93c07` | no CI | **Duplicate**: its only file, `docs/GITHUB_GOVERNANCE.md`, is already on `main` with identical content (merged by #14). Recommend closing it without merging (Project Owner's choice) |

**Conflict check:** each PR head was merged with the current `main` (`6a3ec7b`) using `git merge-tree`. #1, the whole
chain up to #16, #17 and #5 all merge without conflicts. #16 and #17 together also merge without conflicts.

## 3. Owner decisions still open

None of these was decided by the UAT acceptance. Their statuses are unchanged from the decision log.

| Ref | Subject | Current state | Blocks a limited pilot? |
|---|---|---|---|
| D6-18 / OW-41 | Earlier-classified datasets whose recorded blocks would now give MIXED: MA Affinity refuses them, Dataset Summary shows a NOTE | Safer default implemented (reversible); **owner confirmation requested**. OW-41 also asks whether such datasets should ever be reclassified (would need authorised processing) | **Confirm before a pilot**: it decides which datasets MA Affinity accepts |
| D6-20 / OW-43 | Multi-instrument files with differing intervals are refused | Safer default implemented, tested; **owner confirmation requested** | No, if the safer default is confirmed for the pilot |
| D6-21 / OW-42 | Daily-or-longer timeframe labels do not require the base step (2-4-day steps give 1D) | **Not implemented; owner decision requested** | No for the pilot's own data if its files are checked in Datasets and Storage; decide before wider use |
| D6-19 / OW-44 | Missing written record of the answers to plan questions C-6/C-9 (supersession of D5-15, D5-18) | **Confirmation requested** (record only; code unchanged since `3876772`) | No |
| D3-15 / OD-7 | Grey "Waiting" row for files held back by the future-date limit | Implemented; **approval of the grey row and text pending** | No |
| OW-35 | Independent review of the QLOPB integration and safeguards S-1..S-3 | Claude's comparison done (not independent); **independent review outstanding** | **Yes, recommended before relying on MA Affinity results** |
| OW-40 | Start date inside a week/month keeps that period's bar | Documented limitation; owner decision | No, if pilot users know it (known-limitations document) |
| D6-09 / PR #5 | Merge of Blueprint v1.2 copies | Merge awaits the content-check confirmation | No |
| Controlled analytical use | Scope and approval of research use | **Not given** | Yes, by definition |

## 4. Remaining technical and documentation items

- **OW-45 (minor, future):** Stop scan counter shows all files done after a stop. Display only.
- **OW-38, OW-39, OW-26 (known limitations):**
  - MA Affinity is not offered on intraday or quarterly data;
  - a daily file with some double-bar dates is measured as intraday;
  - the bar-time convention differs between sources.

  See `docs/release/Q-MAP_v0.1_Known_Limitations_and_Release_Boundaries_03_Nov_26_180000.md`.
- **Documentation standard:** guide v2 and tracker v2 (PR #16) refer to `docs/standards/Q-MAP_User_Documentation_Standard.md`,
  which exists only once PR #17 is merged.
- **Laptop observations from round 2c engine checks** (not failures):
  - local run on Python 3.12 only;
  - 7 environment skips;
  - "access violation" messages printed during 4 concurrency tests that passed.

  Recorded in PR #12.
- **Repository housekeeping:** PR #13 is a duplicate of merged #14 and can be closed.

## 5. Recommended merge sequence (only with the Project Owner's explicit approval)

1. **#17** (documentation standard, base `main`). It is independent of the chain. Merging it first means the
   references in #16 resolve as soon as #16 lands.
2. **#5** (Blueprint v1.2 copies), once its content check is confirmed. It is independent and can also come later.
3. **#1 → #2 → #3 → #4 → #9 → #10 → #12 → #15 → #16**, in this order.
   - Use **"Create a merge commit"** for every stacked PR, not "Squash" or "Rebase". Squashing a lower PR rewrites
     its commits, and the next PR would then show conflicts.
   - After each merge, check that the next PR's base shows `main`. GitHub changes it automatically only when the
     merged branch is deleted. Otherwise use **Edit** next to the PR title to change the base to `main`. Then wait for
     its CI to finish green before merging it.
4. **#13:** close without merging, if the Project Owner agrees.

## 6. Readiness for a limited controlled research pilot

**Assessment:** the v0.1 application is functionally ready. Windows UAT is accepted, CI is green on every chain PR,
MA Affinity results are reproducible across builds, and the owner's data was left unchanged. It is **not yet cleared
for controlled analytical use.** The following are still needed, in order of importance:

1. **The Project Owner's explicit approval of controlled analytical use, with a stated scope.** For example:
   - which instruments and timeframes (MA Affinity on daily, weekly or monthly datasets only);
   - who uses the results, for what, and that they are not trading signals;
   - how results are recorded (Run IDs, build line).
2. **OW-35: independent review of the QLOPB integration** (the only research module in v0.1), or the Project Owner's
   explicit acceptance of the risk of proceeding without it. The evidence for the review is ready.
3. **D6-18: confirmation of the safer default** (MA Affinity refuses "would be MIXED" datasets). D6-20 is best
   confirmed at the same time.
4. **Merging the chain to `main`** (section 5), so that the pilot runs from a merged, identifiable build.
   Alternatively, the pilot can run from the accepted build `a202d43d78ed`, provided every report's build line is
   checked.

D3-15, D6-19, D6-21 (for files checked in Datasets and Storage), OW-40, OW-45 and PR #5 do not block a limited pilot.
They should be decided before wider use.
