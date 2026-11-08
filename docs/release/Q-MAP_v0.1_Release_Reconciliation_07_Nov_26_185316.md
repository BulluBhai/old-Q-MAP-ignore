# Q-MAP v0.1: release reconciliation and readiness (07-Nov-26)

**Prepared by Claude after the Project Owner's formal acceptance of the round-2c Windows UAT. Documents only; no
program, data, registry or research output was changed.**

**Update 07-Nov-26 (housekeeping):**
- PR #17 was merged into `main` with a normal merge commit `cc454dec705199af9d33f046d4617338e47f1155`, with the Project
  Owner's authorisation.
- PRs #5 and #13 were closed without merging; their branches and history are kept.
- D6-09 is superseded by D6-28.
- The OW-35 review is recorded (D6-29).
- No other PR was merged, and `main` was not changed directly.

**Update 08-Nov-26:**
- PR #1 was merged into `main` (`b5dda5a`) after ChatGPT's independent review and the Project Owner's explicit approval. Its head `e34b673` includes the non-finite configuration-value correction.
- OD-10 decided: existing folder names retained. Pre-migration backup deferred (OW-46). Both recorded in D6-30.
- Because of that correction, the build ID of the merged release will differ from the UAT-accepted `a202d43d78ed`.

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
| #1 | Stage 2 foundation | `main` | `e34b673` | #144/#145 success (Ubuntu 458 passed; Windows 457 passed, 1 skipped) | **Merged** into `main` 08-Nov-26, merge commit `b5dda5a` (normal merge commit; Project Owner approval; D6-30) |
| #2 | First GUI, Data Management | #1 | `ff28305` | #21 success | Ready |
| #3 | Sample-file testing and audit fixes | #2 | `852247f` | #27 success | Ready |
| #4 | Database Manager / Analytical Workbench (schema 7) | #3 | `417552f` | #48 success | Ready |
| #9 | Sources, automatic interpretation (schema 8) | #4 | `b7a76c2` | #54 success | Ready |
| #10 | Data automation DQ-7..DQ-10 | #9 | `78323b4` | #72 success | Ready |
| #12 | v0.1 release candidate (code `06d8659`, build `a202d43d78ed`) | #10 | `cbd6f08` | #122/#123 success | Ready. UAT accepted; open owner decisions listed in section 3 do not change its code |
| #15 | Docs: round-2c easy guide and tracker | #12 | `7b26334` | #128/#129 success | Ready (historical guide used for round 2c) |
| #16 | Docs: round-2c results review (accepted), guide v2, tracker v2, records, this reconciliation | #15 | `1b6bb2a` + this update | #138/#139 success on `1b6bb2a`: all four jobs (Windows 3.11 and 3.12: 1,355 passed, 1 skipped; Ubuntu 3.11 and 3.12: 1,247 passed, 109 skipped; 0 failed) | Ready |
| #17 | Docs: permanent User Documentation Standard | `main` | `cd72480` | no CI (docs only; base without workflow) | **Merged** into `main` 07-Nov-26, merge commit `cc454dec705199af9d33f046d4617338e47f1155` (normal merge commit) |
| #5 | Docs: Blueprint v1.2 copies and 01-Nov-26 handover | `main` | `043a7f7` | no CI | **Closed without merging** 07-Nov-26. Superseded by the approved Master Blueprint v1.35 on `main` (D6-28, which supersedes D6-09). Branch `docs/blueprint-v1.2-and-handover` and history kept as the historical record |
| #13 | Docs: GitHub governance | `main` | `8d93c07` | no CI | **Closed without merging** 07-Nov-26: duplicate of `docs/GITHUB_GOVERNANCE.md`, already on `main` through #14. Branch `docs/github-governance` and history kept |

**Conflict check:** each PR head was merged with `main` using `git merge-tree`, before and after #17 was merged
(`6a3ec7b`, then `cc454de`). #1 and the whole chain up to #16 merge without conflicts.

## 3. Owner decisions still open

None of these was decided by the UAT acceptance. Their statuses are unchanged from the decision log.

| Ref | Subject | Current state | Blocks a limited pilot? |
|---|---|---|---|
| D6-18 / OW-41 | Earlier-classified datasets whose recorded blocks would now give MIXED: MA Affinity refuses them, Dataset Summary shows a NOTE | Safer default implemented (reversible); **owner confirmation requested**. OW-41 also asks whether such datasets should ever be reclassified (would need authorised processing) | **Confirm before a pilot**: it decides which datasets MA Affinity accepts |
| D6-20 / OW-43 | Multi-instrument files with differing intervals are refused | Safer default implemented, tested; **owner confirmation requested** | No, if the safer default is confirmed for the pilot |
| D6-21 / OW-42 | Daily-or-longer timeframe labels do not require the base step (2-4-day steps give 1D) | **Not implemented; owner decision requested** | No for the pilot's own data if its files are checked in Datasets and Storage; decide before wider use |
| D6-19 / OW-44 | Missing written record of the answers to plan questions C-6/C-9 (supersession of D5-15, D5-18) | **Confirmation requested** (record only; code unchanged since `3876772`) | No |
| D3-15 / OD-7 | Grey "Waiting" row for files held back by the future-date limit | Implemented; **approval of the grey row and text pending** | No |
| OW-35 | Independent review of the QLOPB integration and safeguards S-1..S-3 | **Technical review completed 07-Nov-26 (ChatGPT): supportive** (D6-29). **Documented limitation:** the upstream 32-file comparison with QLOPB `6cbadc7` could not be rerun independently, because the original QLOPB repository could not be retrieved through the available GitHub connection | The review supports proceeding. The Project Owner decides whether the limitation is acceptable for a pilot |
| OW-40 | Start date inside a week/month keeps that period's bar | Documented limitation; owner decision | No, if pilot users know it (known-limitations document) |
| D6-09 / PR #5 | Merge of Blueprint v1.2 copies | **Superseded by D6-28** (PR #5 closed without merging; D6-09 kept unchanged as history) | No (closed) |
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
- **Repository housekeeping:** done. PRs #5 and #13 are closed without merging, with branches kept. PR #17 is merged.

## 5. Recommended merge sequence (only with the Project Owner's explicit approval)

1. ~~#17~~: **done** (merged 07-Nov-26, `cc454de`). The documentation-standard references in #16 now resolve on `main`.
2. ~~#5~~: **closed without merging** (D6-28).
3. ~~#1~~ (merged 08-Nov-26, `b5dda5a`) → **#2 → #3 → #4 → #9 → #10 → #12 → #15 → #16**, in this order, each after ChatGPT's review and the Project Owner's
   explicit approval.
   - Use **"Create a merge commit"** for every stacked PR, not "Squash" or "Rebase". Squashing a lower PR rewrites
     its commits, and the next PR would then show conflicts.
   - After each merge, check that the next PR's base shows `main`. GitHub changes it automatically only when the
     merged branch is deleted. Otherwise use **Edit** next to the PR title to change the base to `main`. Then wait for
     its CI to finish green before merging it.
4. ~~#13~~: **closed without merging**.

## 6. Readiness for a limited controlled research pilot

**Assessment:** the v0.1 application is functionally ready. Windows UAT is accepted, CI is green on every chain PR,
MA Affinity results are reproducible across builds, and the owner's data was left unchanged. It is **not yet cleared
for controlled analytical use.** The following are still needed, in order of importance:

1. **The Project Owner's explicit approval of controlled analytical use, with a stated scope.** For example:
   - which instruments and timeframes (MA Affinity on daily, weekly or monthly datasets only);
   - who uses the results, for what, and that they are not trading signals;
   - how results are recorded (Run IDs, build line).
2. **OW-35:** the technical review of the QLOPB integration was completed and is supportive (D6-29). The Project Owner
   decides whether the documented limitation is acceptable for the pilot: the upstream 32-file comparison could not
   be rerun independently.
3. **D6-18: confirmation of the safer default** (MA Affinity refuses "would be MIXED" datasets). D6-20 is best
   confirmed at the same time.
4. **Merging the chain to `main`** (section 5), so that the pilot runs from a merged, identifiable build.
   Alternatively, the pilot can run from the accepted build `a202d43d78ed`, provided every report's build line is
   checked.

D3-15, D6-19, D6-21 (for files checked in Datasets and Storage), OW-40 and OW-45 do not block a limited pilot.
They should be decided before wider use.
