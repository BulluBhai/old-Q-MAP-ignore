# Q-MAP v0.1: release-readiness audit, gap list and proposed correction scope

Prepared 03-Nov-26 by Claude (lead developer) for the Project Owner (Sandeep) and independent review (ChatGPT).
Reference: **Q-MAP Master Blueprint v1.35** (`main`, PR #11, read in full from `origin/main` at `b66c901`).

**Status of this document: audit and proposal only (steps 1-2 of the release instruction).** No corrective
development has been done. Batch 1 below starts only after the Project Owner decides R-1 to R-7 (section 6).

## 1. What was inspected

| Item | Version inspected |
|---|---|
| Blueprint v1.35 (whole document, both §8.5.11 and §1-§19) | `origin/main` `b66c901` |
| Q-MAP code stack PR #1 → #2 → #3 → #4 → #9 → #10 (all open, unmerged, each based on the previous) | PR #10 head `78323b4` |
| OW-33 branch (read-only impact report, no PR) | `claude/youthful-babbage-d71hnl` `2be97b1` |
| Outstanding Work Register, decision log (D1-D5-53), architecture/implementation documents, user guides, acceptance checklists and guides | as on PR #10 / OW-33 branch |
| **QLOPB** (separate private repository `BulluBhai/QLOPB`, attached read-only for this audit) | `main` `be6d945`; unmerged safeguard branch `claude/youthful-bardeen-11wtok` `6cbadc7` |
| **MIQP** | No code or specification exists in either repository. Blueprint §14.2 says the MIQP archive is "primarily documentation" and does not establish an implementation |
| Other repositories visible to the session: `BulluBhai-IndexAnalytics`, `IndexAnalytics_v2` | Not inspected (not named as MIQP anywhere); see question R-1 |

PR #5 (Blueprint v1.2 documents) is also still open; it is superseded by v1.35 for content (R-6).

## 2. Readiness levels used

Four separate levels, never merged into one:
**Code** = implemented in code; **Auto** = automated tests pass; **Workflow** = verified through an actual workflow
(here: by Claude, on Linux, in this audit or an earlier recorded one); **Owner** = accepted by the Project Owner.

Classification: **R** Ready for controlled analytical use · **AT** Implemented, requires acceptance testing ·
**E** Incomplete, essential for v0.1 · **D** Incomplete, can be deferred · **F** Not yet developed, future roadmap.

## 3. Release-readiness matrix

| # | Capability (Blueprint ref) | Code | Auto | Workflow | Owner | Class |
|---|---|---|---|---|---|---|
| 1.1 | Code / data / output separation, folder checks, configuration (§9, §9.1) | Yes | Yes | Yes (this audit) | Partly (PR #9 session 02-Nov-26) | AT |
| 1.2 | Run IDs, run folders, locks, no overwrite (§9.2) | Yes | Yes | Yes | No | AT |
| 1.3 | SQLite metadata registry, schema 8, migrations, Parquet storage (§8.3, §8.5.9) | Yes | Yes | Yes | No | AT |
| 1.4 | DuckDB analytical queries (§8.3) | No | - | - | - | D (OW-03) |
| 2.1 | Folder Sources, discovery, idempotent re-scan (§8.5.2, §8.5.6) | Yes | Yes | Yes (2 real files, this audit) | Partly (F-01..F-04 fixed, re-test A1-A8 open) | AT |
| 2.2 | Automatic interpretation: format, header, columns, dates, time zone (§8.5.4) | Yes | Yes | Yes | Partly | AT |
| 2.3 | Validation, hard fail / warning / info, no silent repair (§8.5.5) | Yes | Yes | Yes | Partly | AT |
| 2.4 | Timeframe inference with sampling + full-file check, MIXED/uncertain (§8.5.11 B; DQ-7) | Yes | Yes | Yes (synthetic W13-W18 files, tests) | No (W1-W18 open, OW-29) | AT |
| 2.5 | Instrument identification, copy-suffix cleaning, editable alias registry (§8.5.11 C; DQ-8) | Yes | Yes | Yes | No | AT |
| 2.6 | Exact duplicates removed, conflicts kept and reported (§8.5.11 D/E; DQ-10) | Yes | Yes | Yes | No | AT |
| 2.7 | Overlap/conflict reports across loads, report-only policy (DQ-1, DQ-9) | Yes | Yes | Yes | No | AT |
| 2.8 | Asset category vs venue; crypto not NSE (§8.5.11 F; DQ-11) | No (approved, not built) | - | - | Approved design | D |
| 2.9 | Source-specific ignore columns for exact duplicates (DQ-12) | No (design approved) | - | - | Approved design | D |
| 2.10 | Full-file finding may make a dataset MIXED (DQ-14) | No (approved for separate task) | - | - | Approved design | D |
| 2.11 | OW-33 Option C sparse-only alignment | No (not authorised); read-only impact report on OW-33 branch | 13 tests | No | No | D |
| 2.12 | Trading calendar, corporate actions, bar-time convention (§8.4; OD-5, OW-05, OW-26) | No | - | - | Open decisions | D (documented limitation) |
| 2.13 | Provider API adapters, direct cloud connectors, scheduled scans (§8.5.2, §8.5.7; DQ-3, DQ-5) | No | - | - | - | F |
| 3.1 | Data Registry: source, identity, timeframe, coverage, fields, status, fingerprints, lineage (§8.5.8) | Yes | Yes | Yes | No | AT |
| 3.2 | Permanent/Temporary, move/delete with dependency checks (§8.3) | Yes | Yes | Yes (earlier, PR #4) | No (OW-01) | AT |
| 3.3 | Derived weekly/monthly/quarterly/yearly from daily (v1.35 change summary) | Yes | Yes | Yes (PR #4) | No | AT |
| 3.4 | Coverage view by instrument × timeframe × date range (§5.10) | Per dataset only | - | - | - | D (OW-16) |
| 4.1 | **MIQP** Market Intelligence: regime, breadth, sector, stock intelligence (§5.2-5.4, §14.2) | **No code, no specification in the repository**; final regime methodology is a Blueprint §17 open decision | - | - | - | **F** (see R-1) |
| 5.1 | **QLOPB MA Affinity** research engine (§14.1) | Yes, **in the separate QLOPB repository**, own loader and own tkinter GUI | QLOPB `main` 96 passed; safeguard branch 107 passed (this audit) | Yes, standalone (QLOPB sample outputs 11-Oct-26) | **No** (QLOPB README: "awaiting independent review and owner acceptance") | **E** |
| 5.2 | QLOPB inside Q-MAP: registered dataset → readiness → MA Affinity → Run ID outputs (§4.4, §5.11, §14.1) | **No** (Workbench lists it COMING SOON) | - | **Feasibility verified** in this audit (section 5.3) | No | **E** |
| 5.3 | QLOPB methodology open items: Directed IR, score weights, incomplete aggregated bars, time-zone cases (§14.1, §17) | Implemented as "pending owner review" | - | - | **Open** | D (documented limitation; must stay labelled) |
| 5.4 | QLOPB Pivot, CPR, Camarilla, Bollinger, combinations (placeholders) | Placeholders | - | - | - | F |
| 6.1 | Database Manager GUI: Sources, Data Management, Datasets and Storage, Derive (§5.10) | Yes | Yes (208 window tests, Linux Xvfb; Windows CI runner) | Linux only | Partly | AT |
| 6.2 | Analytical Workbench GUI: module list, readiness, parameters, run, outputs (§5.11) | Yes, one utility analysis (Dataset Summary) | Yes | Linux only | No | AT (no research module yet → see 5.2) |
| 6.3 | Opportunity Scanner, Price Behaviour Lab, Backtesting, Portfolio, Research Library screens (§5.1-5.9) | No | - | - | - | F |
| 7.1 | Run metadata: parameters, dataset references, Run ID, outputs (§5.11, §9.2) | Yes | Yes | Yes | No | AT |
| 7.2 | Code/method version in run records (§5.11, §13.6) | Static `qmap 0.1.0 / c2`; analysis version per spec; **no commit/release identifier** | Partly | - | - | **E** (small; G-B2) |
| 7.3 | Research outputs: Dataset Summary CSV; QLOPB Excel/PDF/PNG exist only in QLOPB | Partly | Yes | Yes | No | E (with 5.2) |
| 7.4 | Run reuse / Research Run Manager, Research Library (§13.1, §5.9) | No (tables exist) | - | - | - | D (OW-15, OW-08) |
| 8.1 | Launch from IDLE/Thonny with F5, no installation step; missing packages offered for install (§11) | Yes | Yes | Linux only | Partly | AT |
| 8.2 | Install instructions for a non-programmer | README leads with `venv` + `pip install -e` (developer route) | - | - | - | **E** (documentation) |
| 8.3 | Windows compatibility | GitHub CI `windows-latest` Python 3.11 runs the full suite incl. GUI tests (green on PR #10 and OW-33 heads) | Yes (CI) | No real Windows desktop session since PR #9 | No | AT |
| 9.1 | Originals never modified (§8.5.11 G) | Yes | Yes | Yes (SHA-256 before/after, this audit) | No | AT |
| 9.2 | Interrupted-run recovery, storage integrity, tamper detection | Yes | Yes | Yes (tests) | No | AT |
| 9.3 | Restore a damaged raw file from the screen | Command line only | - | - | - | D (OW-07) |
| 10.1 | User guides (Database Manager, Workbench), architecture, registry/schema docs | Yes, but they cite **Blueprint v1.3** and link the deleted v1.0 file | - | - | - | **E** (documentation) |
| 10.2 | One v0.1 Windows operating and acceptance procedure (install → close/restart, incl. QLOPB) | **No** (separate per-PR checklists and the W1-W18 guide) | - | - | - | **E** |
| 10.3 | Known-limitations list for v0.1 | Scattered across register and reports | - | - | - | **E** |

**Summary.** The Database Module (areas 1-3, 6.1, 9) is substantially built and well tested, but **none of it is
owner-accepted on Windows**. The Analytical Module has the readiness/Run ID framework and **no research module**:
QLOPB exists and works but outside Q-MAP; MIQP does not exist.

## 4. Consolidated defect and gap list

### A. Release blockers

| Ref | Problem | Consequence | Correction / workaround | Dependencies, risks |
|---|---|---|---|---|
| **A-1** | QLOPB MA Affinity is not available in the Analytical Workbench; it is a separate program with its own file loader | The owner cannot run any genuine analysis on Q-MAP-prepared data; using standalone QLOPB bypasses the registry, readiness and provenance (§4.4, §5.11, §8.5.8) | **Migrate** the existing QLOPB engine (unchanged formulas, scoring, IS/OOS, statuses) into `Application/qlopb/` and register it as a Workbench analysis that reads the registered dataset. Outputs (Excel, PDF, PNG, CSV, run log) go into the Run ID folder with Run_Metadata. Include the three owner-approved QLOPB safeguards (branch `youthful-bardeen-11wtok`, unreviewed). QLOPB's own repository stays as the reference baseline (§14.3) | Decisions R-2 to R-4. Adds pandas, scipy, matplotlib, reportlab to Q-MAP's requirements (the launcher already offers to install missing packages). Risk low: section 5.3 shows identical results |
| **A-2** | MIQP: no code and no specification in the repository; its regime methodology is an open decision (§17) | v0.1 cannot offer Market Intelligence. Building it now would be new development with an unapproved methodology, which the instruction excludes | **Defer MIQP from v0.1** and state it as a known limitation, unless the owner supplies approved specifications (R-1) | Owner decision |
| **A-3** | No single Windows operating/acceptance procedure covering install → Database Manager → Workbench (Dataset Summary and MA Affinity) → results → errors → close/restart; W1-W18 (OW-29), A1-A8 re-test (OW-19) and OW-01 are still outstanding | The owner cannot accept v0.1 without developer help; acceptance cannot be claimed | Write one consolidated procedure that absorbs W1-W18 and A1-A8, with "what success looks like" per step; IDLE-first, no venv | After A-1 (screens must exist) |
| **A-4** | Install instructions lead with `python -m venv` and `pip install -e` | A non-programmer may fail before first launch | README and user guides: download/unzip into `Q-MAP_APP`, open `database_manager.py` in IDLE, F5, accept the offered package install. Keep the venv route as an optional appendix | None |
| **A-5** | Seven open, stacked PRs (#1, #2, #3, #4, #9, #10, plus docs #5) | No single release candidate exists; merge order is easy to get wrong | One release-candidate branch (this branch: PR #10 head + `main` merged, conflict-free) and one RC pull request stacked on PR #10. Merge order after acceptance: #1 → #2 → #3 → #4 → #9 → #10 → RC, **only with the owner's approval** | R-7 |

### B. Important (documented limitation or controlled workaround acceptable)

| Ref | Problem | Consequence | Proposed handling |
|---|---|---|---|
| B-1 | Docs cite Blueprint v1.3; README links the v1.0 file deleted on `main` (`4592692`) | Wrong authority reference | Update references to v1.35 in Batch 1 (documentation only) |
| B-2 | Run records carry `qmap 0.1.0` only; two different builds look identical | Weak code-version traceability (§5.11, §13 rule 6) | Set version `0.1.0rc1`; add the git commit to Run_Metadata when available, otherwise "not a git checkout" (routine) |
| B-3 | DQ-11 not built: `CRYPTO` legacy key; venue and asset category not separate | Crypto files identified, but category/venue reporting is coarse | Limitation; separate task as approved |
| B-4 | DQ-12 not built: technical export columns (e.g. `index`) can stop exact duplicates being recognised | Such rows appear as conflicts (kept, warned), not removed | Limitation; separate task |
| B-5 | DQ-14 not built; OW-33 sampling/full-file asymmetry | A small section may be MIXED or not depending on the sample; the full-file check still warns | Limitation; OW-33 report stays separate and read-only |
| B-6 | No trading calendar, no corporate-action adjustment, bar-time convention not detected (OD-5, OW-05, OW-26), multi-day gaps reported only (OW-27) | Gap-, session- and adjustment-sensitive research may mislead | Limitations shown in the v0.1 list; QLOPB already records adjustment as "unknown" |
| B-7 | QLOPB methodology items pending owner review: Directed IR, weights, incomplete aggregated bars; p-values not corrected for multiple comparisons; intraday research not validated | MA Affinity rankings are exploratory evidence | Keep QLOPB's existing limitation text in every report; Workbench label "exploratory, methodology items pending owner review" |
| B-8 | Datasets with unresolved conflicting observations (DQ-10) contain two rows at one timestamp; QLOPB requires unique timestamps | MA Affinity on such data would fail or mislead | Readiness contract for MA Affinity: FAIL with a plain explanation (R-4) |
| B-9 | Workbench passes a dataset's bars; QLOPB can also aggregate D/W/M/Q itself | Two aggregation paths could give different weekly bars | R-3 |
| B-10 | Windows evidence is CI only (GitHub `windows-latest`); no Windows desktop/IDLE session since PR #9 | Possible Windows-only GUI issues | Owner acceptance per A-3 |

### C. Enhancements (after v0.1)

DuckDB (OW-03); provider APIs (OW-18, DQ-3); scheduled scans (DQ-5); Research Library and run reuse (OW-08, OW-14,
OW-15); coverage view (OW-16); raw-file restore from the screen (OW-07); go-straight-to-Temporary (OD-6); OD-3 re-create
deleted Temporary; typed extra fields (OW-20); thousands separators (OW-21); multi-symbol files (OW-22); intraday→daily
(OW-04); folder renames (OD-10); QLOPB Pivot/CPR/other references; Opportunity Scanner, backtesting, portfolio.

## 5. Tests and verification done in this audit

### 5.1 Environment

Linux container, **Python 3.11.15** (python-build-standalone, Tk 9.0), virtual display Xvfb. Packages from
`pyproject.toml` `[dev,xls]`, plus scipy/matplotlib/reportlab/pandas for QLOPB. Not Windows, not IDLE.

### 5.2 Automated tests (local; separate runs, not combined)

| Suite | Code | Result |
|---|---|---|
| Q-MAP full suite, window tests required | PR #10 head `78323b4` | **1119 passed, 0 failed, 0 skipped** (208 GUI) |
| Q-MAP full suite, window tests required | OW-33 branch `2be97b1` | **1132 passed, 0 failed, 0 skipped** (208 GUI; includes the 13 OW-33 tests) |
| QLOPB unit tests | QLOPB `main` `be6d945` | **96 passed, 0 failed** |
| QLOPB unit tests | QLOPB safeguards `6cbadc7` | **107 passed, 0 failed** |

CI (GitHub Actions, Ubuntu + Windows, Python 3.11): green on PR #10 head and on OW-33 `2be97b1` (run 77).
QLOPB has no CI.

### 5.3 End-to-end workflow verified by Claude (independently of the test suite)

Script outside the repository; temporary `Q-MAP_APP`/`Q-MAP_DATA`/`Q-MAP_OUTPUT`/`Q-MAP_TEST_FILES` folders; the two
**real market files** shipped with QLOPB (`NSE_SBIN, 60.csv`, 2,812 hourly bars with extra ATR columns;
`Nifty500 Healthcare.txt`, headerless, 228 daily bars).

1. Folder source added, scanned: both files **imported automatically** (no questions): `NSE:SBIN 1h` (passed with
   warnings) and `NSE:NIFTY500_HEALTHCARE 1D` (passed).
2. Source files: SHA-256 identical before and after.
3. Dataset Summary through the Workbench engine: run `DSUM_…` completed, CSV written.
4. **QLOPB MA Affinity (safeguard branch) fed from the registered Parquet dataset** vs **QLOPB standalone on the
   original file**, default settings: identical frozen Top-N (SBIN: SMA 141, 140, 195, 196, 97), identical status
   counts (SBIN 230 OK / 11 insufficient; Healthcare 0 OK / 109 insufficient / 132 no interactions — too short),
   identical interaction counts (5,623 / 403) and identical full candidate result tables.

This shows the migration in A-1 can preserve QLOPB results exactly on these files. It does not prove correctness
on all real market data, and it is not owner acceptance.

## 6. Decisions required from the Project Owner

| Ref | Decision | Recommendation |
|---|---|---|
| **R-1** | MIQP in v0.1? | **Defer.** No code or specification exists and the regime methodology is open. If `BulluBhai-IndexAnalytics` / `IndexAnalytics_v2` hold approved MIQP material, say so and it will be assessed (not built) for v0.2 |
| **R-2** | Migrate QLOPB MA Affinity into Q-MAP as `Application/qlopb/` + one Workbench analysis, methodology unchanged, including the three approved safeguards | **Approve.** It is existing functionality (§14.1, Stage 6), not a new module |
| **R-3** | Timeframe for MA Affinity: (a) run on the selected registered dataset as it is (choose a Q-MAP-derived weekly dataset for weekly research), QLOPB's own D/W/M/Q aggregation not offered; or (b) also offer QLOPB's internal aggregation | **(a)** One aggregation path (Q-MAP derive), shown in provenance. QLOPB's "incomplete aggregated bar" question stays open either way |
| **R-4** | Readiness for MA Affinity: FAIL datasets with unresolved conflicting observations, and MIXED datasets; WARN for gaps | **Approve** (Blueprint §8.5.11 E allows an analysis-specific readiness contract) |
| **R-5** | OW-33 read-only report in the release candidate? | **No**: keep it on its own branch pending independent review |
| **R-6** | PR #5 (Blueprint v1.2 docs): close as superseded by v1.35? | Close (history kept) |
| **R-7** | Release path: one RC PR stacked on PR #10; after acceptance merge #1 → #2 → #3 → #4 → #9 → #10 → RC | **Approve**; nothing merged without your explicit approval |

## 7. Proposed correction scope (after decisions)

**Batch 1 (essential, one coordinated change set on this branch):**
1. A-1: `Application/qlopb/` (migrated engine, references, analysis, validation, reports; GUI not migrated) and
   `analytical_engine/ma_affinity.py` (AnalysisSpec: parameters = QLOPB settings, readiness per R-4, outputs per Run
   ID). Workbench lists "MA Affinity (QLOPB)" as available, with its limitations.
2. B-2: version `0.1.0rc1`, commit in Run_Metadata.
3. Regression tests: QLOPB's 107 tests run inside Q-MAP's suite; equality test Q-MAP-fed vs standalone on both real
   files and synthetic fixtures; readiness FAIL cases; GUI test for the new analysis; source files unchanged.
4. A-3, A-4, B-1: README and user guides on v1.35, IDLE-first install, **one v0.1 Windows operating and acceptance
   procedure** (absorbing W1-W18 and A1-A8), **v0.1 known-limitations list**.

**Batch 2:** full consolidated regression and end-to-end runs (Linux + Windows CI), release-candidate handover
(report A-I of the instruction), RC pull request for independent review. Not merged.

Out of scope (unchanged): DQ-11, DQ-12, DQ-14, OW-33 Option C, `vs3`, reprocessing, MIQP, new modules.
