# Q-MAP v0.1: final comprehensive release audit

Prepared 03-Nov-26 by Claude (lead developer); **closure update 04-Nov-26** after the independent review (sections 1, 3, 4, 5, 6, 8 and new section 9). Reference: Master Blueprint v1.35. Scope frozen as instructed (MIQP,
DQ-11, DQ-12, DQ-14, OW-33 Option C / `vs3` / reprocessing, Opportunity Scanner, backtesting, portfolio/risk excluded).
Audited object: the **cumulative release**, i.e. what `main` would contain after PR #1 → #2 → #3 → #4 → #9 → #10 → #12.
A trial merge of PR #12's head into current `main` (`b66c901`) gives a tree **identical** to PR #12's head, so testing
PR #12's head tests the cumulative release.

## 1. Conclusion

**READY FOR OWNER ACCEPTANCE** — no known release blocker remains; the Project Owner's Windows/IDLE acceptance
(REQUIRED checks in the Windows guide) and the independent review (OW-35) are outstanding.

## 2. Requirements-to-implementation matrix

Classes: **A** verified and ready (technical property fully evidenced; no owner-specific aspect) · **B** implemented,
awaiting owner acceptance · **C** implemented, insufficiently tested · **D** incomplete or defective · **E** deferred
from v0.1 · **F** future. "Real" = evidence on real market files; "synthetic" = generated data.

| Ref | Expected behaviour | Implementation | Tests (files) | Result / evidence | Limitation | Class |
|---|---|---|---|---|---|---|
| BP §9, D2-01 | Code, data, output separate; refused otherwise | `core/config.py` | test_config, test_architecture | pass (local + CI) | — | B |
| BP §9.2, D2-02 | Unique Run ID and folder; never overwrite | `core/runs.py` | test_runs, test_ma_affinity_workbench (repeat run) | pass | — | B |
| BP §8.5.11 G, §8.1 | Originals never modified | ingest copies, content-addressed raw store | test_raw_integrity, test_raw_registration, ma_affinity tests (SHA before/after), scan e2e | pass; real files (QLOPB samples) unchanged | owner's real files: W11 | B |
| BP §8.3, D2-11 | Registry, append-only history, lineage | `storage/schema.py`, `registry.py`, `catalog.provenance` | test_database, test_storage_integrity, test_ingest_versioning | pass | — | B |
| BP §8.5.2/8.5.6 | Folder sources, idempotent rescans, no duplicate datasets | `data_engine/discovery.py` | test_folder_discovery, test_scan_to_analysis_end_to_end | pass; real QLOPB files imported automatically | provider APIs, schedules: F | B |
| BP §8.5.4, DQ-2 | Automatic interpretation; ambiguity asked or rejected; headerless rules; file-name identity never overrides contents | `auto_interpret.py`, `datetime_parse.py` | test_auto_interpret, test_owner_decisions_dq1_dq2, test_datetime_parse, test_ingest_formats, test_sample_layouts | pass; real headerless file (Nifty500 Healthcare) read correctly | day-first default with warning (rules v6, approved) | B |
| BP §8.5.11 B, DQ-7 | Timeframe from data by reproducible sampling; MIXED / uncertain reported; missing bars ≠ another interval | `timeframe_infer.py` (seeded from data + config), `validation.py` full-file check | test_dq7_* (4 files), test_pr9_timeframe_3h, test_dq7_acceptance_pattern_files | pass (synthetic patterns); audit probes: a declared 1D file of 2h bars is registered 2h with a warning | OW-33/DQ-14 sampling asymmetry (E); **OW-39** daily file with a few two-bar dates measured as intraday without warning (documented; analyses refuse it) | B |
| BP §8.5.11 C, DQ-8 | Instrument identification, copy suffixes, alias registry outside code | `instrument_names.py` | test_dq8_identification, test_instruments | pass | DQ-11 category/venue: E | B |
| BP §8.5.11 D, DQ-10 | Exact duplicates removed and counted; source kept | `process.py` | test_dq10_duplicates_conflicts | pass | DQ-12 technical columns: E | B |
| BP §8.5.11 E, DQ-1/DQ-10 | Conflicts kept, flagged, reported; no winner chosen | `process.py`, `overlap.py`, flags | test_dq10_duplicates_conflicts, test_owner_decisions_dq1_dq2 | pass; audit check: Q-MAP's path never selects or drops a conflicting row (`process.py` keeps and flags them; accounting check of every source row) | Standalone QLOPB's own loader (not used by Q-MAP) keeps the FIRST row of a repeated timestamp and lists the others as rejected (its `duplicate_policy`); relevant only to the optional V12 comparison | B |
| D6-05 | Conflicts inside an MA Affinity period block; outside the period do not; overlap with another dataset only warns | `ma_affinity.dataset_checks` | test_ma_affinity_workbench (6 eligibility tests + acceptance file) | pass | — | B |
| v1.35 summary, BP §8.4 | Weekly/monthly/quarterly/yearly from daily; dated by last session (no look-ahead); lineage | `data_engine/derive.py` | test_derive, test_ma_affinity_timeframe_equivalence | pass; equal to QLOPB aggregation (real 1W; synthetic 1W/1M/1Q) | OW-40 start-date filter keeps the boundary week; no trading calendar (OD-5) | B |
| BP §8.3 | Permanent/Temporary, dependency checks, reversible reject | `storage_class.py`, `user_decisions.py` | test_storage_class, test_temporary_transition | pass | — | B |
| BP §4.4, §8.5.8 | Per-analysis readiness handshake; registry is not proof; explains what is missing | `catalog.check_readiness`, `analytical_engine/base.py` | test_catalog_and_analysis, test_workbench_dates_and_runs | pass | — | B |
| BP §5.11 | Dataset Summary utility | `dataset_summary.py` | test_catalog_and_analysis, scan e2e (independent calculation) | pass | — | B |
| D6-03 | MA Affinity uses QLOPB's engine unchanged | `Application/qlopb` (only imports changed) | test_qlopb_migration_identity (32 files vs SHA-256), Tests/qlopb (101) | pass | QLOPB methodology items pending owner review (E/F) | A |
| D6-03 | Q-MAP results = standalone QLOPB results | `ma_affinity.execute` | test_ma_affinity_workbench (real + synthetic) | identical tables; real sample file | — | A |
| D6-04 | Registered dataset and its timeframe used; never aggregated or substituted | `timeframe="as_loaded"` enforced | test_ma_affinity_workbench (weekly/monthly, intraday/quarterly refused) | pass | intraday/quarterly not offered (OW-38) | B |
| S-1/S-2/S-3 | Infinite prices, invalid weights, extra CSV values refused | QLOPB `validation`, `settings`, `data_engine` | Tests/qlopb (11 safeguard tests), test_ma_affinity_workbench (S-1, S-2 × 5) | pass | not independently reviewed (OW-35) | B |
| D6-06 | Builds distinguishable in every run record | `core/build.py`, runs, manifest, Run_Metadata, MA Affinity reports | test_build_id (6), ma_affinity report test | pass | ZIP copy has no git commit (fingerprint identifies it) | A |
| BP §13 rule 1 | Deterministic results | QLOPB engine | test_ma_affinity_workbench (repeat run byte-identical) | pass | — | A |
| BP §13 rule 4 | No look-ahead | derived bars dated by last session; QLOPB IS/OOS freeze, windows inside period | test_derive, Tests/qlopb (IS/OOS, boundaries) | pass | QLOPB "incomplete aggregated bar" question open | B |
| BP §8.5.5, §8.5.11 E, D6-12, D6-14 | Warnings and provenance visible in outputs | Run_Metadata, run log, Excel (Summary, Data_Quality), **PDF heading line and Warnings (04-Nov-26)** | test_ma_affinity_workbench (Excel content; **actual PDF text**; Run_Metadata) | pass; section 9 table | — | B |
| BP §5.10/5.11 GUI | Two separate GUIs; Workbench never imports source files | `qmap_gui/*`, entry points | Tests/gui (212 window tests incl. 4 MA Affinity) | pass on Linux/Xvfb and on GitHub Windows runner | real IDLE session: owner | B |
| Recovery | Interrupted work completed or cleaned; registry consistent | `storage/recovery.py` | test_ingest_recovery, test_storage_integrity | pass | raw restore only on command line (OW-07, F) | B |
| Windows | Runs on Windows, Python 3.11, IDLE, no install step | launcher, `environment.py` | CI windows-latest (full suite incl. GUI) | pass on CI | IDLE + package install on the owner's PC: V1 | B |
| Docs | v1.35 references, guide, limitations | README, user guides, docs/release | review | done | — | B |
| QLOPB standalone | Remains usable | `BulluBhai/QLOPB` unchanged | QLOPB suites 96 / 107 passed; launcher opened its window (Xvfb) | pass | QLOPB `main` lacks S-1..S-3 | B |
| MIQP; DQ-11/12/14; OW-33 C | — | not built | — | — | release boundary | E |
| Scanner, backtesting, portfolio, provider APIs, DuckDB, Research Library, run reuse | — | not built | — | — | roadmap | F |

No item is classed **C** or **D** after the corrections in section 5.

## 3. Final release blocker and limitation register

| # | Item | Class | Status |
|---|---|---|---|
| 1 | MA Affinity Excel/PDF did not show Q-MAP data notes, Run ID, build or dataset checksum (BP §8.5.5, §8.5.11 E; owner instruction 5) | was **Release blocker** | Excel fixed in `afa6652`. **The 03-Nov-26 version of this report wrongly said the PDF was also complete**: inspection of a generated PDF on 04-Nov-26 showed build, fingerprint and checksum missing. **PDF fixed in `5eec5b3`** and verified by reading the PDF in an automated test (section 9). No QLOPB code or calculation change |
| 2 | Windows guide depended on two other documents | was **Release blocker** (usability of acceptance) | **Fixed** in `b04c0cd`. W13-W18 **restored to REQUIRED** on 04-Nov-26 (D5-44 preserved, D6-13); A6, A8, V4, V8, V10, V11 OPTIONAL |
| 3 | README said a declared timeframe is always used (outdated since DQ-7) | was documentation defect | **Fixed** |
| 4 | OW-39: daily file with a few two-bar dates registered as intraday without a warning | Important limitation | Documented; MA Affinity and derivation refuse it; fix belongs to the OW-33/DQ-14 decision |
| 5 | OW-40: start date inside a week/month keeps that period's bar (earlier sessions included) | Important limitation | Documented with workaround (start on the first trading day of the week/month) |
| 6 | QLOPB methodology items pending (Directed IR, weights, incomplete aggregated bars); p-values uncorrected | Important limitation | Printed in every report |
| 7 | No trading calendar, no corporate actions, bar-time convention not detected, gaps only warned | Important limitation | Documented |
| 8 | OW-33/DQ-14 sampling asymmetry | Important limitation (deferred) | Documented |
| 9 | Safeguards S-1..S-3 and the integration not independently reviewed (OW-35) | Important — review outstanding | ChatGPT review |
| 10 | Windows/IDLE owner acceptance (OW-34) | Outstanding owner action | Guide ready |
| 11 | pandas 3 deprecation warnings in the QLOPB engine (OW-36) | Enhancement | Not changed (would touch migrated code) |
| 12 | Intraday/quarterly MA Affinity (OW-38), Blueprint v1.1 file (OW-37), raw restore GUI (OW-07), run reuse (OW-15) | Enhancement / owner | Deferred |

## 4. Test evidence

Environment: Linux container, CPython **3.11.15**, pypdf 6 (tests only) (python-build-standalone, Tk 9.0), Xvfb virtual display; pandas
3.1.0, numpy 2.4.6, pyarrow 26.0.1, scipy 1.17.1, matplotlib 3.11.2, reportlab 5.1.0, openpyxl 3.1.5.

| Run | Command | Commit | Result |
|---|---|---|---|
| Q-MAP full suite, window tests required (**final code commit**) | `QMAP_REQUIRE_GUI_TESTS=1 xvfb-run -a python -m pytest -q -p no:cacheprovider` | `5eec5b3` | **1270 passed, 0 failed, 0 skipped** (212 GUI) |
| Q-MAP full suite, no display (final code commit) | `python -m pytest -q -p no:cacheprovider` (DISPLAY unset) | `5eec5b3` | 1165 passed, 105 skipped (window tests, no display), 0 failed |
| Earlier: Q-MAP full suite, window tests required | same | `b04c0cd` | 1269 passed, 0 failed, 0 skipped (212 GUI) |
| Q-MAP full suite, no display | `python -m pytest -q -p no:cacheprovider` (DISPLAY unset) | `b04c0cd` | 1164 passed, 105 skipped (window tests, no display), 0 failed |
| QLOPB original repository | `python -m unittest discover` in `tests` | QLOPB `6cbadc7` (safeguards) | 107 passed |
| QLOPB original repository | same | QLOPB `be6d945` (`main`) | 96 passed |

Independent checks made by Claude during the audit (scripts outside the repository):
- Repeatability: the same MA Affinity request twice → byte-identical candidate and interaction tables, two Run IDs.
- Excel content inspected (sheets Summary … Charts); before the fix "Bar size: as loaded", no Run ID (finding 1).
- A declared-1D file of 2-hour bars → registered 2h with `timeframe_declared_differs`; MA Affinity refuses it.
- A daily file with 10 % two-bar dates → registered 30m (finding OW-39).
- Weekly data filtered from a Wednesday → first bar is that week's (finding OW-40).
- Standalone QLOPB launcher opened its window under Xvfb; the Workbench MA Affinity screen inspected by screenshot.
- Trial merge of PR #12's head into `main`: identical tree.

Evidence type: real market data = the two QLOPB sample files (NSE SBIN hourly 2,812 bars; Nifty500 Healthcare daily
228 bars). Everything else is synthetic. The owner's own files have not been seen in this session; they are covered
only by the REQUIRED checks in the Windows guide.

## 5. Changes made during this audit

| Commit | Change | Methodology/architecture change? |
|---|---|---|
| `afa6652` | MA Affinity reports: Q-MAP data note via QLOPB's `quality` input (bar size, Run ID, build, dataset, checksum, lineage, warnings), readiness notes in the reports' warnings, Run ID in the label; `RunContext.readiness_warnings`; tests for report content, repeatability, acceptance file with the guide's settings | No (calculation unchanged; tested against a plain engine run) |
| `5eec5b3` | PDF provenance: heading line with Run ID, build, fingerprint, dataset checksum; dataset validation warnings in the reports' warnings; XML-escaped PDF text; automated test reading the PDF (pypdf as a test-only dependency) | No (QLOPB code and calculations unchanged) |
| closure docs | W13-W18 back to REQUIRED; guide V7 expects the PDF provenance; D6-12 corrected, D6-13 decided, D6-14; this report | No |
| `b04c0cd` | Windows guide made self-contained with REQUIRED/OPTIONAL checks; limitations OW-39, OW-40, QLOPB `main` without safeguards; README DQ-7 wording; decisions D6-12, D6-13 | No |
| this document | Final audit | No |

## 6. GitHub and CI

- Final code commit: `5eec5b3`. The release head is the documentation commit after it (closure report); its CI
  result is stated in the closure reply and on the PR. Earlier heads: `b04c0cd` runs 83/84 success; `ee14b89` runs 85/86
  success (Ubuntu and Windows).
- CI on `9caa140` (previous head): run 81 (push) and run 82 (pull_request) **success**, Ubuntu and Windows.
- Review threads: none open on PRs #1, #2, #3, #4 (two resolved), #9, #10, #12; no requested changes. PR #9 carries the
  owner's DQ-1/DQ-2 decisions comment.
- Unapproved changes: none. PR #10 → PR #12 changes only the files of D6-01..D6-13 (QLOPB engine and tests, analysis,
  build ID, GUI listing, docs, `.gitattributes`) plus `main`'s own Blueprint v1.35 files and its deletion of the v1.0
  copy.

## 7. PR dependency and merge sequence (only with the owner's explicit approval)

`main` ← #1 (`keen-carson`) ← #2 (`gui-data-management`) ← #3 (`qmap-audit-miqp-plan`) ← #4 (`adoring-curie`) ← #9
(`happy-brahmagupta`) ← #10 (`friendly-babbage`) ← **#12** (`epic-darwin`). Merge in that order, each into `main` after
retargeting, or merge #12's chain at once; both give the same tree. PRs #1-#3 are part of the chain although they were
not named in the instruction. Separate: PR #5 (Blueprint v1.2 documents; merge agreed, pending your click or
confirmation); the OW-33 branch (not in the release).

## 8. Windows/IDLE acceptance

`docs/release/Q-MAP_v0.1_Windows_Operating_and_Acceptance_Guide_03_Nov_26_180000.md`, Part 9.
REQUIRED (only the owner can do these): V1-V3, W1-W18, A4, A5, A7, V5-V7, V9, V13, V14 (installation and IDLE, real
files, File Explorer, visual behaviour, restart; W13-W18 by D5-44 - the automated Windows test
`test_dq7_acceptance_pattern_files` supplements but does not replace them). OPTIONAL, each backed by an automated test
that runs on GitHub's Windows runner: A6 (`test_year_buttons_move_a_whole_year_and_keep_the_month`, real window), A8
(`test_a_missing_folder_is_explained_not_a_crash`, real window), V11 (`test_invalid_weights_are_reported_as_parameters`,
real window), V4 and V8 (`test_acceptance_file_conflictdaily_is_imported_and_refused_with_its_date`, same folder settings
as the guide), V10 (`test_intraday_and_quarterly_datasets_are_refused_with_the_reason`); V12 (standalone comparison).

## 9. Provenance verification of the generated reports (closure review, 04-Nov-26)

Method: an MA Affinity run on a dataset that has a validation warning and an overlap NOTE (synthetic `NSE:M&M`, '&'
included on purpose), then the generated files were read: the PDF with pypdf (text of every page), the workbook with
openpyxl, the JSON as text. Before the fix (`ee14b89`) the PDF lacked version, build, fingerprint and checksum. After
the fix (`5eec5b3`):

| Item | Excel Summary | Excel Data_Quality | PDF report | Run_Metadata JSON |
|---|---|---|---|---|
| Run ID | yes (Instrument / file line) | yes | yes (heading line) | yes (`run_id`) |
| Q-MAP version / build label | no | yes (Code build) | yes (heading: "Q-MAP build: qmap 0.1.0rc1 / c2 build ... git ...") | yes (`build`) |
| Source fingerprint (full SHA-256) | no | yes | yes (heading) | yes (`build.source_fingerprint`) |
| Dataset identity (instrument, timeframe, dataset number) | yes | yes | yes (heading) | yes (`input_datasets`) |
| Dataset checksum (SHA-256) | no | yes | yes (heading) | yes (`input_datasets[].sha256`) |
| Dataset validation warnings | yes (Warnings: "Q-MAP dataset validation warning: ...") | yes | yes (Warnings) | yes (`input_datasets[].validation_warnings`) |
| Readiness notes shown before the run | yes (Warnings: "Q-MAP data: ...") | yes | yes (Warnings) | yes (`readiness_warnings`) |

The Excel Summary sheet deliberately keeps QLOPB's layout; the full record is on its Data_Quality sheet. Automated
test: `Tests/integration/test_ma_affinity_workbench.py::test_pdf_and_excel_and_metadata_carry_the_full_provenance`
(every item in the PDF, Data_Quality and Run_Metadata; '&' rendered correctly), plus the existing Excel Summary test.

## 10. Independent review finding and correction (04-Nov-26)

**Finding (confirmed).** `timeframe_infer.py` counted each sampled block's steps in the block's own unit (days, weeks,
months, quarters, years) and `_base_unit()` returned 1 for every daily-or-longer label; the only unit check separated
minutes from everything else. A weekly block's steps (1, 1, 1 weeks) therefore looked like whole multiples of a daily
interval in which the daily interval "occurred", and the reverse. Reproduced with deterministic synthetic dates: daily
+ weekly, weekly + daily, daily + monthly, monthly + daily, weekly + monthly, monthly + weekly, monthly + quarterly,
quarterly + yearly and daily + yearly files were all CONSISTENT although the sampled blocks landed in both sections.

**Correction (`1291d63`).** A block agrees only with an interval measured in the same unit (minute; day, including
"Nd"; week; month; quarter; year). Within a unit the approved rule is unchanged (90 % of steps whole multiples AND the
interval occurs in the block). No version bumped: no reprocessing, no change for files that were classified correctly
(all 171 existing DQ-7, interpretation and derivation tests pass unchanged). Existing registered datasets are not
reclassified automatically (OW-41, owner decision).

**Tests.** `Tests/integration/test_dq7_calendar_units.py` (16): the nine mixed pairs above, each asserting that blocks
land in both sections and only the minority-unit blocks disagree; uniform daily (weekends, random holidays, a holiday
week), weekly (missing weeks, Thursday closes), monthly (missing months, varying month-end days), quarterly and yearly
files stay CONSISTENT; reproducibility; end-to-end scan registers MIXED and MA Affinity refuses it. Ten of them fail on
the previous code (verified by running them against it).

**Results on `1291d63`** (Linux, CPython 3.11.15, Xvfb): full suite with window tests **1286 passed, 0 failed,
0 skipped** (212 GUI); without a display 1181 passed, 105 skipped (window tests), 0 failed; QLOPB 107 / 96 passed
(`6cbadc7` / `be6d945`). CI: see PR #12 and the closure reply.

**Matrix update.** Row "BP §8.5.11 B, DQ-7": defect D found and corrected; class B (awaiting owner acceptance).
Build fingerprint of the code under test: `4956d0b680a7` (unchanged by documentation commits; also verified on a
`git archive` export, i.e. what a ZIP download contains).

**Windows manual.** `Q-MAP_v0.1_Windows_Operating_and_Acceptance_Guide_03_Nov_26_180000.md` is now the "Q-MAP v0.1 —
Windows Owner Acceptance Testing Manual" (same path; earlier versions in Git history). All approved REQUIRED checks
kept; W13-W18 REQUIRED; W11 gains a content check by SHA-256 through Q-MAP itself (D6-16); W8 has practical
instructions and a documented fallback.
