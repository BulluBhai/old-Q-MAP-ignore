# Q-MAP: architecture and implementation (Database Manager and Analytical Workbench)

Prepared 01-Nov-26 on branch `claude/adoring-curie-5h2mx4` (PR #4), stacked on PR #3; updated after two PR #4 reviews
(schema 6; Temporary-folder conflict; tampering-detection limits). Status: **implemented and tested; awaiting
Project Owner review. Nothing has been merged.**

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
| Blueprint version | Only **v1.0** is in the repository. **v1.2 and the project handover are not** (conflicts C1, C10). |

## 2. Conflicts with the Blueprint and the instruction, and how each was handled

| Ref | Conflict or gap | What was done | Needs the owner? |
|---|---|---|---|
| C1 | The instruction's reference, Blueprint **v1.2**, is not in the repository; v1.0 does not mention two GUIs, `Q-MAP_APP`, Permanent/Temporary storage or minute/hourly separation. | The requirements stated in the development instruction were used as the v1.2 reference. | **Yes**: commit v1.2 to `docs/` so the implementation can be checked against it. |
| C2 | Folder names: Blueprint 9.1 and the existing README call the code folder `Q-MAP_CODE` (with `Application/`, `Tests/`, `Configuration/`). The instruction puts the entry points in `Q-MAP_APP`. | **The repository folder is the `Q-MAP_APP` folder.** Clone or copy it into a folder named `Q-MAP_APP` next to `Q-MAP_DATA`, `Q-MAP_OUTPUT` and `Q-MAP_TEST_FILES`. Both entry points sit at its top level. Nothing was moved: moving about 18,000 lines would have broken all three open PRs and gained nothing (decision D4-01). | Confirm D4-01. |
| C3 | The suggested sub-folders (`common/`, `database_engine/`, `analytical_engine/`, `miqp/`, `qlopb/`). | Mapped onto what exists (table in section 3). `analytical_engine/` was added. No empty `miqp/` or `qlopb/` folders were created, because there is no code to put in them. | No |
| C4 | "Preserve MIQP and QLOPB" | There is nothing in the repository to preserve or migrate. Both are listed as **Coming Soon** with that reason, and are not presented as working. | **Yes**: supply the QLOPB source code and MIQP specifications. |
| C5 | **Temporary folder name.** According to the PR #4 review, Blueprint v1.2 and the project handover specify `Q-MAP_DATA/Temporary/`. The code uses `Q-MAP_DATA/Temporary_Data/<the dataset's permanent path>`. That choice was made by Claude (D4-04) when v1.2 was not available and is **not approved** by the Project Owner: no decision-log entry, PR comment or other record approves it. | Not changed: the path and the database rules are left as they are until the owner decides (section 7). | **Yes: OD-8** |
| C6 | Blueprint 8.3: Parquet + DuckDB + SQLite | Parquet and SQLite are used. **DuckDB is not adopted yet**: nothing queries across datasets. The data catalogue (`qmap/catalog.py`) is the single place where it would be added. | Later |
| C7 | Minute data for selected indices and hourly data for a selected stock universe | Storage already keeps each instrument and timeframe separate, and no instrument is assumed to have every timeframe. **The universes themselves are not defined**, so nothing enforces "minute only for indices X, Y". | **Yes**: name the universes and retention. |
| C8 | A derived dataset must name a `created_by_attempt_id` (a migration-1 rule written before derived data existed). | A derived dataset carries its source's attempt as *inherited lineage*. The true derivation record (method, version, parameters, source checksum, Run ID) is in the new `dataset_derivations` table. Rebuilding the `datasets` table to relax the rule was judged riskier than the benefit. | No (recorded as technical debt OW-09) |
| C10 | **Which Blueprint is authoritative.** According to the PR #4 review, Blueprint v1.2's own version and approval wording does not match the handover's statement that v1.2 is authoritative. Neither document is in the repository, so Claude could not read the exact wording. v1.0, the only version in the repository, describes itself as "Initial consolidated baseline — for owner review and approval". The development instruction used v1.2 "subject to the Project Owner's formal approval and the repository's recorded approval status", and the repository records no approval of v1.2. | v1.2 treated as the intended target design, not as approved policy | **Yes: OD-9** |
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
    - class and path always agree: Temporary ⇔ the path starts with `Temporary_Data/`;
    - a class or path change must follow the Temporary mapping and match an unfinished `move` action exactly;
    - `file_deleted_at` can only be set under an unfinished `delete_file` action;
    - actions are inserted only as `started`, at most one is open per dataset, and an action is `completed` only if
      the dataset shows the change and never `failed` if it does.
- `storage/storage_class.py`: assess, move and delete. The intent is recorded first, then the file is copied and its
  checksum verified, placed without overwriting, the registry is switched in one transaction, and only then is the
  old copy removed.
- Recovery:
  - finishes or undoes interrupted storage actions;
  - never deletes a file that an unfinished move is writing;
  - cleans the new `_incoming` folders;
  - reports, but never deletes, unknown files in `Temporary_Data`;
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
├── Q-MAP_DATA/         Raw_Data (originals, never changed), Cleaned_Data, Timeframe_Data, Temporary_Data, Metadata ...
├── Q-MAP_OUTPUT/       Ingestion/, Data_Management/, Research_Reports/  (one folder per Run ID)
└── Q-MAP_TEST_FILES/   your sample files (Q-MAP only reads them)
```

The one-time setup (Python 3.11+, packages) is unchanged; see the README. Each entry point checks the environment
and offers to install any missing package.

## 6. Migration and compatibility notes

- **Existing databases** are upgraded automatically to schema version 6 (5 adds storage classes; 6 makes every storage
  change require a matching recorded action, decision D4-13) the first time either application opens them.
  Existing datasets become **Permanent**. No data file is moved or rewritten. A database upgraded to version 6 cannot
  be opened by older code (the existing rule D2-28).
- **Existing behaviour preserved**: every one of the 614 tests from PR #3 still passes. The changed tests are listed
  below. Loading, validation, reuse, retry, recovery and verify rules are unchanged, apart from the deleted-file note
  (C9) and recovery's knowledge of the new folders.
- **Tests changed because a requirement changed** (two applications, new storage):

  | Test | Change |
  |---|---|
  | `test_placement_and_migration.py` | Expects schema version 6; migrations 5 and 6 are pinned |
  | `test_logic_modules_env_store.py` | The READY set is now Data Management, Datasets and Storage, Dataset Summary (still an exact pin) |
  | `test_window_home_and_folders.py` | Each application's Home lists its own modules |

  No test was weakened or removed.
- `Q-MAP.py` still works and opens Database Manager. `qmap_gui.app.QMapApp` is still importable (an alias).
- Helpers moved without behaviour change into `qmap_gui/common.py` (`fmt_duration`, `fmt_clock`,
  `open_in_file_manager`, the log bridge). They are still importable from their old modules.
- Output folders: data-management actions write their run folders to `Q-MAP_OUTPUT/Data_Management`; analyses to
  `Q-MAP_OUTPUT/Research_Reports`.

## 7. Temporary folder: specification conflict and alignment plan (awaiting the Project Owner, OD-8)

**Status.** `Temporary_Data/` is in the code, the schema-6 rules (`trg_datasets_class_path_insert`,
`trg_datasets_move_audited`), recovery, tests and guides. It is an **unapproved deviation** from `Temporary/` as stated
for Blueprint v1.2 and the handover. Nothing has been changed pending your decision.

**Option A: keep `Temporary_Data/`.** No code change. Record your approval of the deviation in the decision log, and
amend the Blueprint or handover.

**Option B: align with `Temporary/` (smallest safe change).**

1. `TEMPORARY_FOLDER = "Temporary"` in `core/config.py`. This one constant drives the storage mapping, the
   temporary-folder location and the `_incoming` folder.
2. New **migration 7**. Migration 6 is pinned and must not be edited. Migration 7 drops and recreates the two schema-6
   triggers with the prefix `Temporary/` (prefix length 10 instead of 15), and replaces the literal in recovery's
   consistency check with the constant.
3. **Existing data are never rewritten automatically.** Migration 7 refuses to run while any dataset is still
   Temporary at `Temporary_Data/...`. You first use **Make Permanent** in the current version (an audited move), then
   upgrade, then move datasets back if wanted. No file is moved by the migration.
4. Datasets whose Temporary file you already **deleted** keep their recorded `Temporary_Data/...` path; deletions are
   final. Recovery's consistency check must accept the old prefix for those deleted rows only.
5. Q-MAP never deletes the old, empty `Q-MAP_DATA/Temporary_Data` folder; remove it by hand if you wish.
6. Update about 15 test strings, the guides and this document.

**Implication.** PR #4 is unmerged, and no Temporary dataset has been created on your own data as far as the
repository shows, so Option B is cheapest now. After acceptance it would need the step-3 procedure on every
installation.

**Recommendation.** Option B if you confirm v1.2 as approved and authoritative (OD-9); otherwise Option A, with a
recorded approval.

## 8. Other documents

| Deliverable | Document |
|---|---|
| 3. Database Manager user guide | [user_guides/Database_Manager_User_Guide.md](user_guides/Database_Manager_User_Guide.md) |
| 4. Analytical Workbench user guide | [user_guides/Analytical_Workbench_User_Guide.md](user_guides/Analytical_Workbench_User_Guide.md) |
| 5. Data Registry and schema | [Data_Registry_and_Schema.md](Data_Registry_and_Schema.md) |
| 6. Testing report and acceptance checklist | [acceptance_testing/Q-MAP_Testing_and_Acceptance_Report_01_Nov_26_160000.md](acceptance_testing/Q-MAP_Testing_and_Acceptance_Report_01_Nov_26_160000.md) |
| 8. Outstanding work register | [Outstanding_Work_Register.md](Outstanding_Work_Register.md) |
| Decisions | [decision_log.md](decision_log.md), entries D4-01 to D4-14 |
