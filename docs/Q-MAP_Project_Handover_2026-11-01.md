# Q-MAP Project Handover

**Prepared:** 1 November 2026  
**Updated:** 1 November 2026, evening, after the Blueprint v1.2 review, the Temporary-folder decision (OD-8) and the PR #5 documentation corrections  
**Purpose:** Transfer the current project context, decisions, risks and next actions to the next Q-MAP development/review session.  
**Status:** Working handover snapshot. Verify the live GitHub state before acting.

---

## 1. Executive summary

Q-MAP (Quantitative Market Analytics Platform) integrates market intelligence and quantitative price-behaviour research
into a modular, reproducible research platform.

**Q-MAP Master Blueprint v1.2** is the Project Owner-approved, authoritative product and architecture baseline. The
Project Owner, Sandeep, approved and adopted it on 1 November 2026, and it supersedes v1.0 and v1.1. Approval of the
Blueprint does not by itself approve individual code changes or authorise a merge. The Blueprint and this handover are
recorded in the repository through **PR #5** (open, not merged).

The application work is in **PR #4** (Database Manager and Analytical Workbench, stacked on PR #3; open, not merged).
Its latest head passed GitHub CI on Windows and Ubuntu. **The next step is the Project Owner's Windows/IDLE acceptance
of PR #4 with real sample files.** PR #4 is not to be merged until that acceptance and the remaining owner decisions
are addressed.

## 2. Product purpose and architecture

Q-MAP combines two existing work areas:

- **MIQP (Market Intelligence & Query Platform):** market regime analysis, breadth, sector strength/weakness, stock
  intelligence and market-wide research.
- **QLOPB (Quant Lens on Price Behaviour):** moving-average affinity, price behaviour, technical indicators and
  measurable market-pattern research.

**Roadmap (Blueprint v1.2, section 15):**

1. Blueprint and decisions.
2. Existing-code audit and migration plan.
3. Database Manager foundation.
4. Analytical Workbench foundation.
5. Market Intelligence (MIQP).
6. Price Behaviour (QLOPB).
7. Extensible research.
8. Research-to-scanner integration (historical Opportunity Scanner).
9. Strategy research (backtesting).
10. Portfolio and risk.
11. Additional scale, only when justified.

PR #4 delivers the foundations of Stages 3 and 4.

**Architecture principles to preserve (Blueprint v1.2):**

- Two major modules (Database and Analytical) with two separate GUIs over one shared platform: Database Manager
  (`database_manager.py`) and Analytical Workbench (`analytical_workbench.py`), in one `Q-MAP_APP` folder.
- The Analytical Workbench checks the readiness of the specific data each analysis needs. It does not ingest source
  files; it directs the user to the Database Manager.
- Python performs the quantitative calculations. AI may assist with research and explanation, but must not invent or
  replace calculations.
- Keep source code, market data and generated outputs separate. The top-level folders are `Q-MAP_APP`, `Q-MAP_DATA`,
  `Q-MAP_OUTPUT` and `Q-MAP_TEST_FILES`.
- Original source files are never modified.
- Permanent and Temporary are user-controlled storage classifications. Temporary data do not expire automatically.
- Parquet, DuckDB and SQLite are the proposed storage direction, subject to technical validation. Updates must not
  blindly append.
- Maintain common definitions, a central Data Registry, reusable analytical features, provenance, calculation
  parameters and unique Run IDs.
- Preserve reproducibility and guard against look-ahead bias, survivorship bias and data leakage.
- Preserve existing QLOPB functionality during migration, and MIQP's approved requirements.
- Avoid unnecessary complexity. Do not silently change approved architecture or quantitative methodology.
- Use feature branches, pull requests, review and Project Owner approval before merging to `main`.

**Primary reference:** `docs/Q-MAP_Master_Blueprint_v1.2.md` and `docs/Q-MAP_Master_Blueprint_v1.2.html` (identical
in version, status and substance). They become the canonical published copies when PR #5 is merged.
`docs/Q-MAP_Master_Blueprint_v1.0.md` is kept for history.

## 3. GitHub status (verify live before acting)

Repository: `BulluBhai/Q-MAP`. `main` still contains only the initial README and Blueprint v1.0. All application code
is in the open, stacked pull requests #1 → #2 → #3 → #4.

### PR #4: Database Manager and Analytical Workbench
- **URL:** https://github.com/BulluBhai/Q-MAP/pull/4
- **State:** open, unmerged; branch `claude/adoring-curie-5h2mx4`, stacked on PR #3
  (`claude/qmap-audit-miqp-plan-547lid`).
- **Head at this update:** `bfa4dda` (latest code commit `1760b57`).
- **GitHub CI on `bfa4dda`:** passed, 4 of 4 jobs (Windows and Ubuntu, Python 3.11, push and pull-request runs
  41333762280 and 41333766212).
- **Local results reported by Claude for `1760b57`:**
  - 712 passed on Python 3.12 with every GUI test required;
  - 624 passed and 62 skipped (the window tests) on Python 3.11.
  - These are Claude's own runs, not an independent check.
- **Practical acceptance by Claude:** real windows on a virtual Linux screen, with synthetic files. 13 scenarios
  passed; 1 is not applicable, because there is no MIQP/QLOPB analysis to re-run.
- **Database schema:** version 7. Migrations 1-7 are checksum-pinned; 1-4 are unchanged from PR #3.
- **Do not equate green CI with release readiness.** The Project Owner's Windows/IDLE acceptance remains outstanding.

### PR #5: Blueprint v1.2 and handover (documentation only)
- **URL:** https://github.com/BulluBhai/Q-MAP/pull/5
- **Branch:** `docs/blueprint-v1.2-and-handover`; target `main`; open, not merged.
- **Contents:**
  - `docs/Q-MAP_Master_Blueprint_v1.2.md`;
  - `docs/Q-MAP_Master_Blueprint_v1.2.html`;
  - this handover, `docs/Q-MAP_Project_Handover_2026-11-01.md`;
  - the existing `docs/Q-MAP_Master_Blueprint_v1.0.md`, unchanged.
- **Corrections approved by the Project Owner and applied:**
  1. The Markdown version history now records v1.2 as "Approved and adopted by the Project Owner", matching the HTML,
     the header and section 19.1.
  2. The Markdown "canonical copy" paragraph now matches the HTML (`docs/` paths).
  3. The three files were moved from the repository's top level into `docs/`, the canonical location stated in
     section 19.1.
  4. This handover was updated.

  No requirement was changed. The Markdown and HTML copies were re-checked word by word, and their remaining
  differences are formatting only.
- **Do not merge PR #5 without the Project Owner's review.**

### PR #3 and the stacked-PR dependency
PR #4 is stacked on PR #3, which is stacked on PR #2, which is stacked on PR #1. The intended merge order is
#1 → #2 → #3 → #4, each only with the Project Owner's explicit approval.

## 4. Technical state and decisions

### Storage integrity (PR #4, verified by tests in the PR)
- Migration 6:
  - storage class and path always agree;
  - every move or deletion needs a matching recorded action;
  - actions start as "started", with at most one open per dataset;
  - completion and failure must match what really happened.
- Raw files are always permanent; deletions are final.
- Recovery and `verify` report (never repair) records that the audit history cannot explain. This includes earlier
  tampering, detected by rebuilding each dataset's original path from immutable lineage records. The limits are
  documented in PR #4's `docs/Data_Registry_and_Schema.md`.

### OD-8: Temporary folder (decided and implemented in PR #4)
- **Decision:** the Project Owner adopted `Q-MAP_DATA/Temporary/`, as proposed by Blueprint v1.2 sections 8.3 and 9.1.
- **Implementation:** schema migration 7 (decision D4-15 in PR #4's decision log).
  - New Temporary data go to `Temporary/`.
  - Nothing new can be written to the earlier `Temporary_Data/` folder.
  - Datasets already there from earlier PR #4 test builds stay valid and are never moved automatically. They are
    relocated with Make Permanent, then Move to Temporary.

### OD-9: Blueprint authority and repository record (resolved)
- v1.2's approval is recorded in the document itself (header, "Version authority", section 19.1 and now section 19.2).
- The documents are in `docs/` through PR #5.

### Open decisions (Project Owner)

| Ref | Decision |
|---|---|
| OD-1 | Confirm that the repository folder is `Q-MAP_APP` with both entry points at its top level (matches Blueprint v1.2 §4.4 and §9.1) |
| OD-2 | Supply the QLOPB source code and the MIQP specifications (nothing of either is in the repository yet) |
| OD-3 | Whether reloading an unchanged source file should re-create a Temporary dataset whose file was deleted |
| OD-4 | Name the minute-data indices (about 4-5) and the hourly stock universe (about 200-500), and their retention |
| OD-5 | Trading-calendar source |
| OD-6 | Whether a load can go straight to Temporary |
| OD-7 | Carry-over items from PR #3 (D3-15 grey "Waiting" row; incomplete-day limitation) |
| OD-10 | Whether to align the other proposed §9.1 folder names: `Permanent/` and `Reference_Data/`, and the output folders `Database_Reports/` and `Analytical_Results/`. The recommendation is to keep the current data-folder names. |

### Known gaps against Blueprint v1.2 (recorded in PR #4, section 8 of its architecture document)
- DuckDB not used yet.
- No Research Run Manager result reuse.
- Research Library statuses still in the old form, in an unused table.
- No update-conflict policy across files (still a Blueprint open decision).
- No trading calendar and no corporate-action adjustment.
- No instrument × timeframe coverage view.
- MIQP and QLOPB not yet in the repository.

## 5. Approval and review rules

1. Blueprint v1.2 is the Project Owner-approved, authoritative reference.
2. Blueprint approval is not blanket approval for all implementation choices. Material deviations and open decisions
   must be raised explicitly.
3. Do not merge any pull request solely because CI is green.
4. Use feature branches and pull requests, review diffs and tests, and obtain Sandeep's approval before merging into
   `main`.
5. Do not claim that code, tests, GitHub state or local acceptance have been independently verified unless they have.
6. Keep Blueprint v1.0 (and v1.1 where available) for history.

## 6. Next actions

### Sandeep (Project Owner)
1. **Windows/IDLE acceptance of PR #4** with real sample files, using the checklist in PR #4's
   `docs/acceptance_testing/Q-MAP_Testing_and_Acceptance_Report_01_Nov_26_160000.md`, section 5.
2. Review PR #5 and decide whether to merge it.
3. Decide OD-1, OD-3 and OD-10, and supply the material for OD-2 when available.
4. Approve the merge order for PRs #1 → #4 when satisfied.

### Claude (Lead Python Developer)
1. Support the Windows acceptance: explain each checklist step, and investigate and fix any problem found.
2. Keep PR #4 on its feature branch, preserve existing behaviour, run tests, and report evidence and limitations.
3. After the merges and OD-2: migrate QLOPB as the first research module on the analytical pipeline.
4. Do not merge pull requests or bypass review.

### ChatGPT (Business Analyst / Product Coordinator)
1. Re-check the live state of PRs #3, #4 and #5, branch bases, CI and review comments before advising on merges.
2. Independently review proposed changes, and distinguish verified facts from Claude-reported results.

## 7. Acceptance checklist for PR #4

Before calling PR #4 ready to merge, confirm:
- [x] Latest Windows and Linux CI checks are green on the current PR head (`bfa4dda`; re-check after any new commit).
- [ ] PR #1 → #2 → #3 dependency and merge order are understood and approved.
- [x] OD-8 folder decision is resolved, and the implementation matches it (`Temporary/`, migration 7).
- [ ] Migration and integrity checks reviewed by the owner, including report-only handling of historical
      inconsistencies.
- [x] No unintended repair, deletion or destructive migration (covered by tests; recovery reports, never repairs).
- [ ] Sandeep completes Windows/IDLE acceptance using realistic files and the agreed checklist.
- [x] Documentation and Blueprint references aligned (PR #4 documents cite v1.2; PR #5 corrected).
- [ ] Review comments are resolved (none open at this update).
- [ ] Sandeep explicitly approves merging.

## 8. Handover caveats

This is a working snapshot. GitHub states, branch heads, CI runs, comment threads, file contents and decision records
may change after it was written. The next session should re-check live evidence before making claims or taking action.

Do not infer that a pull request is merged, that a local acceptance test passed, or that an open decision is resolved
unless there is explicit evidence.
