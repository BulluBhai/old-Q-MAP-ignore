# Q-MAP Project Handover

**Prepared:** 1 November 2026  
**Purpose:** Transfer the current project context, decisions, risks, and next actions to the next Q-MAP development/review session.  
**Status:** Working handover snapshot — verify live GitHub state before acting.

---

## 1. Executive summary

Q-MAP (Quantitative Market Analytics Platform) is intended to integrate market intelligence and quantitative price-behaviour research into a modular, reproducible research platform.

The immediate focus is reviewing the Database Manager and Analytical Workbench work in **PR #4** and recording the approved **Q-MAP Master Blueprint v1.2** in the repository through **PR #5**. Automated CI was reported green in the latest status check described in the conversation, but local Windows/IDLE acceptance remains outstanding. PR #4 is not to be merged until acceptance and unresolved decisions have been addressed.

Blueprint v1.2 has been explicitly confirmed by the Project Owner, Sandeep, as **authoritative and final**. This approval establishes the governing product/architecture reference; it does not automatically approve individual code changes or authorize a merge.

## 2. Product purpose and architecture

Q-MAP combines two existing work areas:

- **MIQP — Market Intelligence & Query Platform:** market regime analysis, breadth, sector strength/weakness, stock intelligence, and market-wide research.
- **QLOPB — Quant Lens on Price Behaviour:** moving-average affinity, price behaviour, technical indicators, and measurable market-pattern research.

Longer-term roadmap:
1. Foundation: ingestion, validation, storage, registries, and common infrastructure.
2. MIQP.
3. QLOPB.
4. Additional research modules.
5. Opportunity Scanner.
6. Strategy Backtesting.
7. Portfolio and Risk Analytics.
8. Further scaling only when justified.

Architecture principles to preserve:
- Python performs quantitative calculations; AI may assist with research/explanation but must not invent or replace calculations.
- Keep source code, market data, and generated outputs separate: `Q-MAP_CODE`, `Q-MAP_DATA`, and `Q-MAP_OUTPUT`.
- Parquet and DuckDB are part of the analytical data architecture; SQLite is the initial metadata/registry direction, subject to technical validation.
- Maintain common definitions, a central Data Registry, reusable analytical features, provenance, calculation parameters, and unique Run IDs.
- Preserve reproducibility and guard against look-ahead bias, survivorship bias, and data leakage.
- Preserve existing QLOPB functionality during migration and MIQP's approved requirements.
- Avoid unnecessary complexity and do not silently change approved architecture or quantitative methodology.
- Use feature branches, pull requests, review, and Project Owner approval before merging to `main`.

**Primary reference:** `docs/Q-MAP_Master_Blueprint_v1.2.md` and `.html` are being introduced through PR #5. Confirm the latest repository copy and document-control wording before relying on it.

## 3. GitHub status

Repository: `BulluBhai/Q-MAP`

### PR #4 — Database Manager and Analytical Workbench
- **URL:** https://github.com/BulluBhai/Q-MAP/pull/4
- **Reported state:** Open and unmerged; stacked on PR #3's branch rather than directly on `main`.
- **Latest commit mentioned in the conversation:** `de624a618ae78091d14239c25b63231484c02b82`.
- **CI run reported:** https://github.com/BulluBhai/Q-MAP/actions/runs/41328091330
- The latest status check reported Windows Python 3.11 and Ubuntu/Linux Python 3.11 jobs passed (2/2 jobs in the PR-triggered run); a corresponding push-triggered run was also reported as 2/2 jobs passed.
- A later status summary reported no new review comments, review submissions, or unresolved inline review threads. These observations are a snapshot from the conversation, not a guarantee of current live status.
- Earlier Claude-reported local test totals included 704 passed on Python 3.12 (including GUI tests) and 616 passed / 62 skipped on Python 3.11. These totals were reported by Claude and were not independently run by ChatGPT.
- **Do not equate green CI with release readiness.** Local Windows/IDLE acceptance by Sandeep remains outstanding.

### PR #5 — Blueprint v1.2 documentation
- **URL:** https://github.com/BulluBhai/Q-MAP/pull/5
- **Branch:** `docs/blueprint-v1.2-and-handover`
- **Target:** `main`
- **Reported state:** Open, not merged.
- The branch contains `Q-MAP_Master_Blueprint_v1.2.md` and `Q-MAP_Master_Blueprint_v1.2.html`.
- The branch was reported as four commits ahead of `main` at the time of the screenshot. Re-check live state before acting.
- The PR description states that the documentation aligns approval wording with the Project Owner's confirmation. Review the actual contents of both files and confirm that the Markdown and HTML versions agree.
- The handover document was not included when PR #5 was first created. This handover can be added to the same branch/PR if that is still appropriate, after checking the live PR state and avoiding duplicate or conflicting files.
- **Do not merge PR #5 without review.**

### PR #3 and stacked-PR dependency
PR #4 is stacked on PR #3 (`claude/qmap-audit-miqp-plan-547lid`, according to the latest discussion). Check PR #3's current state and the intended stacked-PR merge order before deciding how PR #4 can be merged.

## 4. Technical findings and outstanding decisions

### Storage-integrity protections
The work described for PR #4 includes Schema Migration 6 protections such as:
- Temporary dataset class/path consistency.
- Move/delete audit records.
- Started action state and one open action per dataset.
- Completion/failure state consistency with recorded results.
- Report-only historical tampering checks.

The intent of historical checks is to report inconsistencies rather than silently repair older records. Migrations 1–5 were reported as hash-pinned and unchanged, with migration 6 pinned.

These details are drawn from the discussion and developer-reported work. Review the current PR code, tests, and migration files before treating every implementation detail as independently verified.

### OD-8 — temporary storage folder naming (unresolved)
- Blueprint v1.2 Section 9.1 specifies `Q-MAP_DATA/Temporary/` for user-managed temporary datasets and says there is no automatic expiry initially.
- The implementation/documentation discussed in PR #4 still used `Temporary_Data/` in at least `Application/qmap/storage/recovery.py` and related documentation.
- Claude reported that it did not change the name because it could not find explicit owner approval for the change.
- Sandeep confirmed v1.2 as authoritative, but the conversation treated the separate OD-8 decision as needing clarification before changing implementation. Do not assume the folder rename has been approved merely because the Blueprint was approved.
- **Next action:** inspect the exact OD-8 wording in the handover/decision log and present the specific choice to Sandeep. Until resolved, do not silently rename paths or make a migration that could affect user data.

### OD-9 — Blueprint and handover recorded in GitHub
- The discussion referenced OD-9 as calling for v1.2 and the handover to be committed under `docs/`.
- PR #5 currently concerns the two Blueprint formats; the handover was not included at PR creation.
- **Next action:** add this handover to the documentation branch/PR only after checking whether an existing canonical handover/decision log already exists. Avoid creating conflicting duplicate project records.

## 5. Approval and review rules

1. Blueprint v1.2 is the Project Owner-approved, authoritative and final reference.
2. Blueprint approval is not blanket approval for all implementation choices; material deviations and open decisions must be raised explicitly.
3. Do not merge PR #4 or PR #5 solely because CI is green.
4. Use feature branches and PRs; review diffs and tests; obtain Sandeep's approval before merging into `main`.
5. Do not claim that code, tests, GitHub state, or local acceptance have been independently verified unless they actually have.
6. Keep the original v1.0 document for history unless a separately approved change says otherwise.

## 6. Next actions

### ChatGPT — Business Analyst / Product Coordinator
1. Re-check live PR #3, PR #4, PR #5, branch bases, CI, and review comments before advising on merges.
2. Review the actual v1.2 Markdown/HTML wording and consistency against Sandeep's approval.
3. Locate the existing project handover/decision log and establish the exact wording of OD-8 and OD-9, if available.
4. Explain the OD-8 choice to Sandeep in business terms; do not make the decision on his behalf.
5. Independently review proposed changes and distinguish verified facts from Claude-reported results.

### Claude — Lead Python Developer
1. Read the committed Blueprint v1.2 and handover/decision record once accessible in the repository.
2. Reconcile PR #4's documentation and implementation against the approved Blueprint without silently changing methodology or data paths.
3. Identify the exact OD-8 decision and request owner confirmation before making any folder-name change.
4. Keep PR #4 on its feature branch, preserve existing behavior, run appropriate tests, and report evidence and limitations.
5. Do not merge PRs or bypass the established review process.

### Sandeep — Project Owner
1. Complete practical Windows/IDLE acceptance of PR #4 after receiving a concise checklist and test build/instructions.
2. Decide OD-8 only after the exact decision and impact are clearly explained.
3. Review and approve PRs before any merge to `main`.

## 7. Acceptance checklist for PR #4

Before calling PR #4 ready to merge, confirm:
- [ ] Latest Windows and Linux CI checks are green on the current PR head.
- [ ] PR #3 dependency and stacked-branch merge order are understood.
- [ ] OD-8 folder naming decision is resolved and implementation matches the approved decision.
- [ ] Migration and integrity checks are reviewed, including report-only handling of historical inconsistencies.
- [ ] No unintended repair, deletion, or destructive migration occurs.
- [ ] Sandeep completes Windows/IDLE acceptance using realistic files and the agreed checklist.
- [ ] Documentation and Blueprint references are aligned.
- [ ] Review comments are resolved.
- [ ] Sandeep explicitly approves merging.

## 8. Handover caveats

This is a working snapshot assembled from the conversation, not a fresh repository audit. GitHub states, branch heads, CI runs, comment threads, file contents, and OD decision records may have changed. The next session should re-check live evidence before making claims or taking action.

Do not infer that a PR is merged, that a local acceptance test passed, or that an open decision is resolved unless there is explicit evidence.
