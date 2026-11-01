# Q-MAP: architecture and implementation (Database Manager and Analytical Workbench)

Prepared 01-Nov-26 on branch `claude/adoring-curie-5h2mx4` (PR #4), stacked on PR #3; updated after two PR #4 reviews
(schema 6; tampering-detection limits), then after Blueprint v1.2 became readable on PR #5's branch (Temporary folder
decision OD-8 implemented as schema 7; gap review in section 8). Status: **implemented and tested; awaiting Project
Owner review and Windows/IDLE acceptance. Nothing has been merged.**

**Governing reference:** Blueprint **v1.2**, approved and adopted by the Project Owner on 1 November 2026, superseding
v1.0 and v1.1. It is in PR #5 (branch `docs/blueprint-v1.2-and-handover`, not yet merged). Section 1 below records what
was found on 01-Nov-26 before v1.2 was available; the conflict table shows how each finding stands now.

This document covers deliverables 1 (architecture and implementation summary), 2 (folder and entry-point guide) and 7
(migration and compatibility notes), plus the Phase 1 implementation assessment. User guides, the registry and schema
reference, the test report and the outstanding-work register are separate documents (see the end of this page).

---

## 1. Phase 1 assessment: what was found (inspected 01-Nov-26)

| Item | Finding |
|---|---|
| `main` | Only `README.md` and `docs/Q-MAP_Master_Blueprint_v1.0.md`. No code. |
| Open pull requests | Three stacked and unmerged: PR #1 (Stage 2 Foundation) → PR #2 (first GUI, `Q-MAP.py`) → PR #3 (sample-file testing and audit fixes, head `852247f`, CI green on Windows and Ubuntu). All application code lives there. |
| Base chosen for this work | PR #3's head. This work builds on it as one more stacked PR, so it neither conflicts with nor duplicates the open work. |
| Entry point | One: `Q-MAP.py`, opening one window with Home and Data Management. |
| Data preparation code (reused, unchanged in behaviour) | Configuration and path rules, Run IDs and manifests, SQLite registry (migrations 1-4), raw-file registration with checksums, readers (CSV, text, XLSX, XLS, Parquet), source profiles, strict date parsing, canonical OHLCV structure, validation, crash recovery. |
| Analysis code | **None.** There is no MIQP or QLOPB code in the repository (Blueprint section 14 refers to archives supplied outside it). |
| Registry | Mature: append-only attempts and checks, immutable identities, lineage from cleaned to raw. Permanent/Temporary storage: **absent.** Derived timeframes: the layer name `timeframe` existed but nothing used it. DuckDB: not used. |
| Tests | 614 passed at `852247f` (Python 3.12, Tk 8.6, virtual screen); CI on Windows and Ubuntu with Python 3.11. |
| Dependencies outside the code folder | None hard-coded. Data and output folders come from configuration or the GUI's remembered settings (outside the repository). |
| Blueprint version | At the time, only **v1.0** was in the repository (C1, C10). v1.2 and the handover were added later in PR #5. |

## 2. Conflicts with the Blueprint and the instruction, and how each was handled

| Ref | Conflict or gap | What was done | Needs the owner? |
|---|---|---|---|
| C1 | The instruction's reference, Blueprint **v1.2**, is not in the repository; v1.0 does not mention two GUIs, `Q-MAP_APP`, Permanent/Temporary storage or minute/hourly separation. | The requirements stated in the development instruction were used as the v1.2 reference. **Resolved**: v1.2 is now readable in PR #5 and was reviewed against this implementation (section 8). | PR #5 to be merged by the owner |
| C2 | Folder names: Blueprint 9.1 and the existing README call the code folder `Q-MAP_CODE` (with `Application/`, `Tests/`, `Configuration/`). The instruction puts the entry points in `Q-MAP_APP`. | **The repository folder is the `Q-MAP_APP` folder.** Clone or copy it into a folder named `Q-MAP_APP` next to `Q-MAP_DATA`, `Q-MAP_OUTPUT` and `Q-MAP_TEST_FILES`. Both entry points sit at its top level. Nothing was moved: moving about 18,000 lines would have broken all three open PRs and gained nothing (decision D4-01). | Confirm D4-01. |
| C3 | The suggested sub-folders (`common/`, `database_engine/`, `analytical_engine/`, `miqp/`, `qlopb/`). | Mapped onto what exists (table in section 3). `analytical_engine/` was added. No empty `miqp/` or `qlopb/` folders were created, because there is no code to put in them. | No |
| C4 | "Preserve MIQP and QLOPB" | There is nothing in the repository to preserve or migrate. Both are listed as **Coming Soon** with that reason, and are not presented as working. | **Yes**: supply the QLOPB source code and MIQP specifications. |
| C5 | **Temporary folder name.** Blueprint v1.2 (sections 8.3 and 9.1) proposes `Q-MAP_DATA/Temporary/` "to be confirmed during implementation planning". The first PR #4 code used `Temporary_Data/` (Claude's choice, never approved). | **Resolved:** the Project Owner adopted `Q-MAP_DATA/Temporary/` (OD-8). Implemented with schema migration 7 and a no-data-movement transition (section 7, decision D4-15). | No |
| C6 | Blueprint 8.3: Parquet + DuckDB + SQLite | Parquet and SQLite are used. **DuckDB is not adopted yet**: nothing queries across datasets. The data catalogue (`qmap/catalog.py`) is the single place where it would be added. | Later |
| C7 | Minute data for selected indices and hourly data for a selected stock universe | Storage already keeps each instrument and timeframe separate, and no instrument is assumed to have every timeframe. **The universes themselves are not defined**, so nothing enforces "minute only for indices X, Y". | **Yes**: name the universes and retention. |
| C8 | A derived dataset must name a `created_by_attempt_id` (a migration-1 rule written before derived data existed). | A derived dataset carries its source's attempt as *inherited lineage*. The true derivation record (method, version, parameters, source checksum, Run ID) is in the new `dataset_derivations` table. Rebuilding the `datasets` table to relax the rule was judged riskier than the benefit. | No (recorded as technical debt OW-09) |
| C10 | **Which Blueprint is authoritative.** Before v1.2 was readable, its approval status could not be confirmed. | **Resolved:** v1.2's header, its "Version authority" section, §19.1 and (since PR #5 commit `043a7f7`) §19.2 state "Approved and adopted by the Project Owner" (1 November 2026); the handover confirms it. | No |
| C9 | After a Temporary dataset's file is deleted, loading the same source file unchanged would "reuse" the deleted dataset (approved reuse rules D2-32). | The reuse rule is unchanged. The result now says clearly that the dataset's file was deleted and how to process it again. | **Yes**: decide whether re-loading should re-create it (decision OD-3) |

## 3. Architecture as implemented

```text
Q-MAP_APP/   (= this repository; the code folder)
├── database_manager.py        entry point: Q-MAP Database Manager (prepare and manage data)
├── analytical_workbench.py    entry point: Q-MAP Analytical Workbench (research on prepared data)
├── Q-MAP.py                   older launcher, kept: opens Database Manager
├── Application/
│   ├── qmap/                  the platform (no GUI code; never imports tkinter)
│   │   ├── core/              COMMON: configuration and paths, Run IDs and manifests, logging, errors
│   │   ├── catalog.py         COMMON: the ONE read-only view of the Data Registry, plus readiness checks
│   │   ├── data_engine/       DATABASE ENGINE: readers, profiles, parsing, canonical structure, validation,
│   │   │                      ingestion, derive.py (derived timeframes)
│   │   ├── storage/           DATABASE ENGINE: SQLite registry and migrations, raw registration, Parquet,
│   │   │                      storage_class.py (Permanent/Temporary), recovery and verify
│   │   └── analytical_engine/ ANALYTICAL ENGINE: analysis description and run pipeline; Dataset Summary
│   └── qmap_gui/              both GUIs (plain tkinter)
│       ├── app.py             shared window shell + DatabaseManagerApp + AnalyticalWorkbenchApp
│       ├── home.py, locations.py, widgets.py, common.py, launch.py      shared by both
│       ├── data_management.py, datasets.py, services.py, jobs.py, registry_services.py   Database Manager
│       └── analysis.py, workbench_services.py                            Analytical Workbench
├── Configuration/             example settings and source profiles
├── Tests/                     unit, integration and GUI tests
└── docs/
```

**Rules enforced by tests** (`Tests/gui/test_architecture.py`):

- The platform (`qmap`) never imports the GUI or tkinter.
- Screens contain no processing, storage or registry code. They call tkinter-free logic modules.
- **The Workbench's screen, logic and analytical engine load no data-preparation code** (ingestion, profiles,
  readers, registration, storage changes, or Database Manager screens).
- Both GUI logic layers read the registry only through `qmap.catalog`. Neither contains SQL.
- Both entry points need no installation step and import only `sys` and `pathlib` before the environment check.

**How the two applications share one platform**

- Same Data Registry (`Q-MAP_DATA/Metadata/qmap_metadata.sqlite`), same canonical data definition, same configuration
  rules, same Run ID and manifest mechanism, same crash recovery.
- Same remembered folders (one settings file in the user's profile). Saving re-reads the file first, so neither
  application overwrites a change the other just made.
- Both can be open at the same time. SQLite write locks and run liveness locks already make this safe (D2-23).
- They run as separate programs; neither needs the other running. No server, service or background process was added.

## 4. What changed

**Database engine**

- Schema **migrations 5 and 6** (migrations 1-4 untouched; 1-6 all checksum-pinned). **The current schema version is 6.**
  - Migration 5 adds `datasets.storage_class` (`permanent` or `temporary`), `datasets.file_deleted_at`, the
    `storage_actions` audit trail and `dataset_derivations`. Raw files are always permanent. Only a temporary
    dataset's file can be deleted, and a deletion is final.
  - Migration 6 (PR #4 review) makes every storage change auditable:
    - class and path always agree: Temporary ⇔ the path is in the Temporary area (`Temporary/`, plus the legacy
      `Temporary_Data/` for datasets that were already there, since migration 7);
    - a class or path change must follow the Temporary mapping and match an unfinished `move` action exactly;
    - `file_deleted_at` can only be set under an unfinished `delete_file` action;
    - actions are inserted only as `started`, at most one is open per dataset, and an action is `completed` only if
      the dataset shows the change and never `failed` if it does.
- Schema **migration 7** (OD-8): new Temporary data go to `Q-MAP_DATA/Temporary/`. The two migration-6 rules that
  contained the old folder name are recreated. Nothing new can be placed under `Temporary_Data/`, but datasets already
  there stay valid (section 7). **The current schema version is 7.**
- `storage/storage_class.py`: assess, move and delete. The intent is recorded first, then the file is copied and its
  checksum verified, placed without overwriting, the registry is switched in one transaction, and only then is the
  old copy removed.
- Recovery:
  - finishes or undoes interrupted storage actions;
  - never deletes a file that an unfinished move is writing;
  - cleans the new `_incoming` folders;
  - reports, but never deletes, unknown files in `Temporary/` (and the legacy `Temporary_Data/`);
  - reports, but never repairs, any dataset whose storage state the audit trail does not explain
    (`storage_inconsistencies`). This includes rebuilding the dataset's original path from immutable lineage records
    (`storage/paths.py`, D4-14). The limits are in the registry and schema document;
  - does not report a file the user deleted on purpose as missing.
- `data_engine/derive.py`: weekly, monthly, quarterly and yearly bars from registered daily data (rules in the
  Database Manager guide).
- `ingest.py`: one change. A reused dataset whose file was deleted is now reported as such. The reuse rules are
  unchanged.

**Shared**: `catalog.py` (dataset listing, overview, lineage, readiness, reading quantitative columns for a period).

**Analytical engine**: `analytical_engine/base.py`:
- checks parameters and readiness first; if anything is missing, no run is created;
- reserves a Run ID and a folder in `Q-MAP_OUTPUT/Research_Reports`;
- records the inputs in `run_inputs`;
- writes outputs only inside the run folder;
- writes `Run_Metadata_<dd_mmm_yy_hhmmss>.json`, then the manifest.

The first analysis is `dataset_summary`, a descriptive utility (not a methodology).

**GUIs**: two applications on one shell, a new Datasets and Storage screen, a new Run an analysis screen, and a module
catalogue split by application.

**Enhancement (01-Nov-26, decisions D4-16 to D4-21):**
- Workbench calendar date boxes, and typed dates in four formats with a fixed two-digit-year rule (`qmap/core/dates.py`).
- Requests classified as invalid input / no eligible data / not ready / ready before anything runs.
- **Open Output Folder** for the latest completed run.
- The source-profile naming standard: 11 Standard and 3 Example profiles, earlier names still recognised, reading rules
  unchanged.
- Conventions document: `docs/standards/Q-MAP_Naming_and_Reference_Conventions.md`.

## 5. Folder and entry-point guide

| To... | Open | Then |
|---|---|---|
| Load, check and manage data | `Q-MAP_APP/database_manager.py` in Thonny or IDLE, press **F5** | Home → choose folders → Data Management or Datasets and Storage |
| Run an analysis | `Q-MAP_APP/analytical_workbench.py`, press **F5** | Home → Run an analysis |
| Use an old shortcut | `Q-MAP_APP/Q-MAP.py` | Opens Database Manager |

Recommended layout. The paths are examples; any locations work, as long as data and output are outside the code folder
and not inside each other:

```text
<your drive>/Q-MAP/
├── Q-MAP_APP/          this repository (code only)
├── Q-MAP_DATA/         Raw_Data (originals, never changed), Cleaned_Data, Timeframe_Data, Temporary, Metadata ...
├── Q-MAP_OUTPUT/       Ingestion/, Data_Management/, Research_Reports/  (one folder per Run ID)
└── Q-MAP_TEST_FILES/   your sample files (Q-MAP only reads them)
```

The one-time setup (Python 3.11+, packages) is unchanged; see the README. Each entry point checks the environment
and offers to install any missing package.

## 6. Migration and compatibility notes

- **Existing databases** are upgraded automatically to schema version 7 the first time either application opens them:
  - 5 adds storage classes;
  - 6 makes every storage change require a matching recorded action (D4-13);
  - 7 moves the Temporary area to `Temporary/` (D4-15).

  Existing datasets from PR #3 become **Permanent**. No data file is moved or rewritten by any upgrade. A database
  upgraded to version 7 cannot be opened by older code (the existing rule D2-28).
- **Existing behaviour preserved**: every one of the 614 tests from PR #3 still passes. The changed tests are listed
  below. Loading, validation, reuse, retry, recovery and verify rules are unchanged, apart from the deleted-file note
  (C9) and recovery's knowledge of the new folders.
- **Tests changed because a requirement changed** (two applications, new storage):

  | Test | Change |
  |---|---|
  | `test_placement_and_migration.py` | Expects schema version 7; migrations 5, 6 and 7 are pinned |
  | `test_logic_modules_env_store.py` | The READY set is now Data Management, Datasets and Storage, Dataset Summary (still an exact pin) |
  | `test_window_home_and_folders.py` | Each application's Home lists its own modules |

  No test was weakened or removed.
- `Q-MAP.py` still works and opens Database Manager. `qmap_gui.app.QMapApp` is still importable (an alias).
- Helpers moved without behaviour change into `qmap_gui/common.py` (`fmt_duration`, `fmt_clock`,
  `open_in_file_manager`, the log bridge). They are still importable from their old modules.
- Output folders: data-management actions write their run folders to `Q-MAP_OUTPUT/Data_Management`; analyses to
  `Q-MAP_OUTPUT/Research_Reports`.

## 7. Temporary folder: decision OD-8 and the transition (implemented)

**Decision.** The Project Owner adopted `Q-MAP_DATA/Temporary/`, the location proposed by Blueprint v1.2 (sections 8.3
and 9.1).

**What depended on the old name** (full repository search):
- the folder setting and the list of folders created at start-up;
- the Permanent↔Temporary path mapping;
- recovery: interrupted-copy clean-up, the unknown-file report and the consistency check;
- the two migration-6 database rules, where the name was written into the rule text;
- tests, guides and this document.

The Datasets screen reads the setting and followed automatically.

**Transition (schema migration 7, decision D4-15).** It needs no data movement:

| Situation | Behaviour |
|---|---|
| Fresh installation | Only `Q-MAP_DATA/Temporary/` is created |
| New Move to Temporary | Goes to `Temporary/<permanent path>`; the database refuses anything else |
| Dataset already Temporary under `Temporary_Data/` (made by earlier PR #4 code) | Stays valid and readable where it is, and passes readiness, `verify` and the consistency check. Not moved, not rewritten. |
| Relocating such a dataset | **Make Permanent** (returns it to its original permanent path), then **Move to Temporary** (into `Temporary/`). Both are normal audited moves. The Datasets screen explains this when you select the dataset; recovery lists such datasets as a notice. |
| Temporary file you already deleted under `Temporary_Data/` | Record kept as it is; deletion stays final |
| Files in `Temporary_Data/` that Q-MAP does not know | Reported, never deleted. The empty old folder is never removed by Q-MAP. |
| Interrupted copies in either `_incoming` folder | Cleaned up by recovery once their run has ended (as before) |
| Old code meeting a schema-7 database | Refused with a plain message (existing rule) |
| Migration 7 missing while new code runs (cannot normally happen) | Moves to the new folder are refused by the database and the data stay where they are (tested) |

**Evidence:**
- 8 dedicated tests in `Tests/integration/test_temporary_transition.py`, using a database built exactly as the earlier
  PR #4 code left it;
- the full suite;
- the real-window walkthrough re-run (the move now lands in `Temporary/`).

## 8. Gap review against Blueprint v1.2 (01-Nov-26)

Blueprint §19.4 says differences are to be recorded as gaps first, not silently remediated.

**Findings in PR #5 itself.** Documentation only. **All three were corrected on PR #5's branch in commit `043a7f7`, with
the Project Owner's approval (OD-11):**

| Ref | Finding | Suggested correction |
|---|---|---|
| B-1 | The Markdown version-history row for v1.2 (§19.2) says "Approved/adopted for Project Owner review; adoption pending". The HTML copy, the header and §19.1 say "Approved and adopted by the Project Owner". | Change the Markdown row to match |
| B-2 | The "canonical copy" paragraph differs between the two formats: the HTML names `docs/Q-MAP_Master_Blueprint_v1.2.md`/`.html`, the Markdown does not. Both §19.1 copies name `docs/`, but PR #5 adds the files at the repository's top level. | Move both files (and the handover) into `docs/`, and align the paragraph |
| B-3 | The handover names the code folder `Q-MAP_CODE`; v1.2 uses `Q-MAP_APP`. It also describes OD-8 as unresolved (now decided) and places files in `docs/`. | Refresh the handover, or mark it as a dated snapshot |

All other differences between the Markdown and HTML copies are formatting only: list numbers, table wrapping,
apostrophes and dashes. This was checked word by word.

**Implementation gaps against v1.2** (for decision or later work; nothing changed silently):

| Ref | v1.2 says | PR #4 has | Recommendation |
|---|---|---|---|
| G-1 | §9.1 proposed data layout: `Permanent/`, `Temporary/`, `Reference_Data/`, `Metadata/` ("proposals, not a demand"; smallest safe migration) | `Temporary/` now aligned. Permanent data are in `Cleaned_Data/` and `Timeframe_Data/`; `Reference_Files/` | Owner decision OD-10. A rename would follow the same no-movement pattern as OD-8, but touches every stored path and the D2-19 naming rule. Recommend keeping the current names unless you want strict alignment. |
| G-2 | §9.1 output folders: `Database_Reports/`, `Analytical_Results/`, `Research_Reports/` ... | `Ingestion/`, `Data_Management/` (Database Manager) and `Research_Reports/` (Workbench) | Owner decision OD-10. Output folders hold no registered data, so renaming would be low-risk for new runs; old run folders would stay where they are. |
| G-3 | §5.9 Research Library statuses: Under Research, Promising, Validated, Archived | Table `research_records` (migration 1, unused) only allows Hypothesis, Research complete, OOS validated, Strategy validated, Superseded | Change with a new migration when the Research Library is built (OW-14). Nothing uses the table today. |
| G-4 | §13.1 Research Run Manager: reuse an equivalent earlier result | Every analysis creates a new run; the inputs are recorded, so reuse can be added | Planned (OW-15) |
| G-5 | §8.3 DuckDB as the analytical query engine | Not used (nothing queries across datasets) | Planned (OW-03) |
| G-6 | §8.3 and §17 update-conflict policy: no blind append; explicit handling of duplicates and overlaps across updates | Within a file: duplicates and conflicts rejected. Across files: each load is a separate dataset, and no merge exists. | Owner decision (Blueprint open decision) before any merge or update feature |
| G-7 | §5.10 coverage and readiness "by instrument, date range and timeframe", published for the Workbench | Per-dataset coverage in Datasets and Storage; readiness is checked per analysis in the Workbench | Adequate for now; an instrument×timeframe coverage view is open (OW-16) |
| G-8 | §8.4 trading calendars, corporate actions | Not implemented (known limitations) | OD-5 / OW-05 |
| G-9 | §5.11 MIQP and QLOPB in the Workbench | Not in the repository | OD-2 |
| G-10 | §15.1 the Workbench is not ready for routine research until readiness checks are reliable | Readiness checks are implemented and tested; there are no research modules yet | Consistent: the Workbench is not presented as ready for routine research |

Consistent with v1.2:
- two modules, two GUIs and two entry points in `Q-MAP_APP` (§4.4);
- the per-analysis readiness handshake (§4.4);
- the Workbench never ingests and points to Database Manager (§5.11);
- originals never modified (§5.10);
- Permanent/Temporary, user-controlled, no expiry, registry and dependencies checked on move or delete (§8.3);
- weekly, monthly, quarterly and yearly bars derived from daily data (change summary);
- Run IDs and no overwriting of earlier runs (§9.2);
- no look-ahead in derived bars (§13).

## 9. Other documents

| Deliverable | Document |
|---|---|
| 3. Database Manager user guide | [user_guides/Database_Manager_User_Guide.md](user_guides/Database_Manager_User_Guide.md) |
| 4. Analytical Workbench user guide | [user_guides/Analytical_Workbench_User_Guide.md](user_guides/Analytical_Workbench_User_Guide.md) |
| 5. Data Registry and schema | [Data_Registry_and_Schema.md](Data_Registry_and_Schema.md) |
| 6. Testing report and acceptance checklist | [acceptance_testing/Q-MAP_Testing_and_Acceptance_Report_01_Nov_26_160000.md](acceptance_testing/Q-MAP_Testing_and_Acceptance_Report_01_Nov_26_160000.md) |
| 8. Outstanding work register | [Outstanding_Work_Register.md](Outstanding_Work_Register.md) |
| Naming and reference conventions | [standards/Q-MAP_Naming_and_Reference_Conventions.md](standards/Q-MAP_Naming_and_Reference_Conventions.md) |
| Decisions | [decision_log.md](decision_log.md), entries D4-01 to D4-21 |
