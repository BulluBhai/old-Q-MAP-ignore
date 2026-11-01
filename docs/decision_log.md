# Q-MAP decision log

Change history required by Blueprint section 16.3. Dates are dd-mmm-yy.

## Stage 2 Foundation (31-Oct-26)

Status of every entry: implemented on branch `claude/keen-carson-x872ge`; **awaiting Project Owner review and merge approval**.

| Ref | Decision | Previously | Why | Affects |
|---|---|---|---|---|
| D2-01 | Code, Q-MAP_DATA and Q-MAP_OUTPUT are separate, non-overlapping, configurable locations; startup refuses anything else | Blueprint section 9 (proposed) | Mandatory separation principle | core/config |
| D2-02 | Run ID `<MODULE>_<YYYYMMDD>_<HHMMSS>` (UTC) with `_02`, `_03` suffix on collision; folder reserved by atomic `mkdir`, ID claimed by primary key | Format proposed in design review | Safe against simultaneous runs; sorts by time | core/runs |
| D2-03 | Raw files are content-addressed (`Raw_Data/<xx>/<sha256>.<ext>`); every receipt gets its own `ingest_events` row | Name-based raw paths | Identical content stored once without losing provenance | storage/registry |
| D2-04 | Registration commits an intent event before moving any file; `recover_incomplete` finishes or cleans interrupted work at the start of every run | Not specified | SQLite cannot make file operations atomic | storage/recovery |
| D2-05 | Raw files are never auto-deleted; unregistered raw files are reported, never removed; cleaned files are removed only if unregistered and stale | Not specified | Raw integrity safeguard | storage/recovery |
| D2-06 | Raw files are never "rejected"; each processing outcome is an append-only `ingest_attempts` row | Rejected status on datasets | A file rejected under one profile may be valid under a corrected one | schema, ingest |
| D2-07 | Uniqueness: identical raw content once (partial unique index); derivation = layer, parent, processing version, instrument, timeframe; one active dataset per parent/instrument/timeframe | Global unique SHA-256 | A global checksum constraint would block legitimate records in other layers | schema |
| D2-08 | Processing version = `<profile_id>@<profile_version>+<cleaning code version>`; a profile edited without a new version is refused | Not specified | Reproducibility and traceability | profiles, ingest |
| D2-09 | An attempt is compared with earlier ones by raw content, processing version AND the ingest request (exchange/symbol/timeframe supplied at ingest) | Processing version only | Found by testing: supplying a previously missing symbol is a different request, not an unchanged retry | ingest |
| D2-10 | Retrying an unchanged rejected file needs a written `force_reason`; reprocessing under a new version needs none | Proposed | Explicit retry rules without losing audit trail | ingest |
| D2-11 | Attempts and quality checks are append-only; datasets and receipts are never deleted and their identity cannot be edited (database triggers) | Proposed | Audit trail cannot be rewritten | schema |
| D2-12 | Source profiles are the only place where format, date rule, unit, time zone, volume mapping, instrument and timeframe are declared; nothing is inferred | Proposed | No silent guessing | profiles |
| D2-13 | Canonical dataset: `session_date`, `timestamp_utc`, OHLC, optional `volume` (null, never zero, when absent), `src_row`, `quality_flags`; extra source columns kept as `x_` and listed as not quantitative inputs | Proposed | Optional volume; traceability; no accidental inputs | canonical |
| D2-14 | The standardised copy is sorted by a stable ascending sort on the time key while `src_row` keeps source positions; unsorted source is a warning (or an error if the profile says so) | Proposed | Documented, reversible reordering without touching raw data | process |
| D2-15 | Any failed error-level check rejects the whole file; no row is repaired or dropped; every offending row is listed in `issues_event<N>.csv` | Proposed | Do not silently repair or discard invalid data | validation |
| D2-16 | Validation depends on availability and intended use via requirement sets (`price_only`, `price_volume`) | Proposed | Missing volume must not invalidate usable OHLC data | validation |
| D2-17 | Instrument identity is exchange + symbol, normalised to upper case; both must be declared; unknown instruments are created on first sight with an info record | Proposed | Shared symbols across exchanges | instruments |
| D2-18 | pandas is not a Stage 2 dependency; dependencies are numpy, pyarrow, openpyxl, tzdata (xlrd optional, pytest for development) | pandas listed in the design | The foundation needed only pyarrow and the standard library; pandas can be added when a stage needs it | pyproject |
| D2-19 | Cleaned file paths include the Run ID (`...<raw sha 12>_<version hash>_<Run ID>.parquet`) | Deterministic path proposed | A concurrent identical ingest can never overwrite a registered file | ingest |
| D2-20 | Documentation lives in the existing `docs/` folder | Design said `Documentation/` | The approved blueprint is already committed in `docs/` | docs |
| D2-21 | A registered raw file is verified against its registered SHA-256 before it is reused or processed (size is never trusted). On a mismatch the receipt fails with `E_RAW_CORRUPT`, nothing is processed, and the stored file is not used, overwritten or deleted. Recovery is explicit: `restore-raw` requires a written reason, a source that matches the registered checksum and a corrupt stored copy; the corrupt copy is moved to `Raw_Data/_quarantine` (never deleted) and the restore is recorded as its own receipt | Size-only check found in PR #1 review | A same-size corruption could be reused and processed as if it were the registered raw data | storage/registry, storage/recovery, cli |

## Independent review of PR #1 (31-Oct-26)

Every change below has a regression test in `Tests/integration/test_review_regressions.py`, `Tests/integration/test_config_fingerprint.py` or
`Tests/unit/test_placement_and_migration.py` that failed on the code as first submitted. Status: implemented on
branch `claude/keen-carson-x872ge`. D2-22 to D2-31: **awaiting Project Owner review**. D2-32: Project Owner decision
(see the entry). D2-33 and D2-34: **approved by the Project Owner on 31-Oct-26** (comment on PR #1).

| Ref | Decision | Previously | Why | Affects |
|---|---|---|---|---|
| D2-22 | Registered files are placed with one no-overwrite OS call (`os.rename` on Windows; `os.link` + unlink, or an exclusive-create claim, on macOS/Linux). An occupied destination is hashed: identical content is adopted, anything else fails the receipt and is left untouched | `exists()` check followed by `os.replace` | Reproduced: a file appearing between the check and the replace was overwritten; on Windows a concurrent identical ingest failed on the read-only target | storage/files, storage/registry |
| D2-23 | A run holds an OS lock on `Metadata/run_locks/<Run ID>.lock` while open. Recovery treats work as interrupted only if the run is not live AND (finished OR older than `stale_minutes`) | Age threshold only | Reproduced: a live run older than the limit was marked failed and its temp file deleted by another program's recovery | core/runs, storage/recovery |
| D2-24 | Recovery re-checks each temp/cleaned file against the database at the moment of deletion; cleaned temp names carry the Run ID; unreadable or vanishing files are reported, not fatal | One snapshot query, then deletes | Reproduced: a receipt started during recovery lost its temp file; a cleaned file registered during the scan could be deleted | storage/recovery, ingest |
| D2-25 | A receipt's final status cannot change (code guard and trigger); profile snapshots, runs and instruments cannot be deleted or rewritten (schema migration 2; migration 1 unchanged) | Application convention only | Historical explanation must not be rewritable | schema, registry |
| D2-26 | Only ingest-request values the profile actually takes from the request form the request identity (D2-09); ignored values are logged | All supplied values | Reproduced: `--timeframe 1D` with a fixed-1D profile crashed with a uniqueness error | ingest |
| D2-27 | Validation settings and the run date are recorded per attempt (`validation_settings_json`) and in each cleaned file; reuse and blocked messages state any difference (superseded in part by D2-32: they now also take part in the reuse identity) | Not recorded | Provenance gap: `min_rows`, date range, requirement sets and the large-move threshold change outcomes or `quality_flags` | ingest, schema |
| D2-28 | A failing migration is rolled back whatever the error type; a database newer than the code is refused | Only OperationalError rolled back | Reproduced: an IntegrityError left the connection in an open transaction | storage/db |
| D2-29 | Relative paths in the configuration file resolve against the file's folder; root environment variables must be absolute; numeric settings are type- and range-checked; registry paths cannot leave Q-MAP_DATA | Resolved against the working folder; `int()` tracebacks | Behaviour must not depend on where IDLE or a shortcut starts | core/config |
| D2-30 | Recovery done at the start of a run is written to that run's `recovery_report.json` and log; copy/placement errors mark the receipt `failed` and remove the temp file | Console only; receipt left `started` | Observability; no half-finished receipts in a long-lived session | core/runs, registry, cli |
| D2-31 | Windows CI (`.github/workflows/tests.yml`, Python 3.11, windows-latest and ubuntu-latest) | No Windows run | Windows is the primary environment | CI |
| D2-32 | **Project Owner decision (31-Oct-26):** validation settings that can change acceptance, dataset content or `quality_flags` are part of the processing identity. A configuration fingerprint `vs1:<16 hex>` (SHA-256 of `plausible_min_date`, `plausible_max_days_ahead`, `max_daily_move_pct`, `min_rows`, `requirement_set`, `require_volume`) is stored on each attempt and cleaned dataset and is part of the derivation uniqueness key (schema migration 3). Reuse, and blocking of an unchanged rejected retry, require the same raw content, processing version, relevant request AND fingerprint. A different fingerprint is reprocessed into a new dataset that supersedes the active one. The `processing_version` text is unchanged. Excluded and recorded only: `max_gap_days` (warning-only; a difference is reported on reuse) and the run date. Earlier attempts without a stored fingerprint use one computed from their recorded settings; attempts with no recorded settings are never reused | D2-27: recorded and reported only | Reproduced: changing `max_daily_move_pct` or `min_rows` still reused the earlier result | ingest, schema |
| D2-33 | A file rejected ONLY because some dates are later than run date + `plausible_max_days_ahead` (no other error check failed, no date before `plausible_min_date`) is processed again automatically, without a reason, once the run date reaches latest future date - `plausible_max_days_ahead`; until then it stays `BLOCKED` and the message gives that date. Evidence (`plausible_range`: limits, rows on each side, latest future date) is recorded in each attempt's date/time provenance; the retry is a new attempt linked by `revalidation_of_attempt_id` with an info check `retry_after_date_limit`. Attempts without this evidence keep the old rule (blocked; `force_reason` works) | Any unchanged rejected retry blocked | Follow-up review F-01, reproduced: with the run date outside the identity (D2-32), a file that had become valid stayed blocked and needed a manual reason | ingest, datetime_parse |
| D2-34 | Schema migration 4: new derived datasets and attempts must carry a configuration fingerprint (a NULL would escape the derivation-uniqueness index); rows written before migration 3 keep their NULL. Migrations 1-4 are pinned by SHA-256 in a test so a released migration cannot be edited unnoticed | Application convention | Follow-up review F-02/F-03 | schema |

D2-27's open question (should validation settings be part of the processing identity?) was decided by the Project
Owner and implemented as D2-32.

## Follow-up review (31-Oct-26)

Regression tests: `Tests/integration/test_future_date_retry.py` (D2-33) and the migration tests in
`Tests/unit/test_placement_and_migration.py` (D2-34). Status: implemented on branch `claude/keen-carson-x872ge`;
**approved by the Project Owner on 31-Oct-26** (comment on PR #1). No change to methodology: the validation rules and
their severities are unchanged;
only the decision of when an unchanged rejected file may be processed again.

## Open decisions carried forward (not needed for Stage 2)

Front-end technology, intraday data source and retention, corporate-action policy, trading calendar, selection of the
"current" dataset across several raw sources, Polars/DuckDB/PostgreSQL, and the confirmation of time zone and two-digit-year
rules for each real data source.

## First graphical version, Data Management (31-Oct-26)

Status of every entry: implemented on branch `claude/gui-data-management`; **awaiting Project Owner review and merge approval**.

| Ref | Decision | Why | Affects |
|---|---|---|---|
| D3-01 | The GUI is a separate package (`qmap_gui`). Screens contain no processing, storage or registry code; a tkinter-free services layer calls the Foundation; the Foundation never imports the GUI or tkinter (tests enforce this) | Front-end independence (Blueprint 4.3, 11) | qmap_gui |
| D3-02 | The one Foundation change: the "folder is inside the code folder / overlaps" rules were moved into two small public functions, used by `validate_roots` and by the GUI, so the safeguard is not duplicated. Behaviour and messages are unchanged | Reuse instead of copying a safeguard | qmap.core.config |
| D3-03 | Launcher `Q-MAP.py` at the top level adds `Application` to the path (no install step), checks Python version, packages and tkinter, and explains any gap in plain words (offers to install missing packages) | Works with F5 in Thonny/IDLE; understandable errors | Q-MAP.py |
| D3-04 | The two folders are chosen in the window, validated with the Foundation's own rules, and remembered in the user's own settings folder (APPDATA on Windows), refused if that would be inside the repository. "Create folder" always asks first and applies the same rules | Independent, remembered locations; nothing generated in the repository | settings_store, services |
| D3-05 | The user's own source profiles live in the user's settings folder, never in the repository; examples are read-only (copy, then edit) | Keep configuration outside Git | services, profile_editor |
| D3-06 | Module readiness comes from one catalogue; only working functionality is READY (Data Management); everything else is Coming Soon with its roadmap stage. A test fails if anything else is marked ready | Genuine readiness | modules |
| D3-07 | Long work runs in a non-daemon worker thread that only puts events on a queue; the main thread polls with `after()` and is the only code that touches widgets. Closing the window asks a running load to stop after its current file and the program waits for that file | Responsive window; no half-written file | app, jobs |
| D3-08 | Python's cyclic garbage collector is switched off while a worker runs and run again on the main thread afterwards | Found by testing: collecting a leftover window inside a worker thread made Tcl abort the whole program (6 of 6 repeated test runs crashed before the fix, 0 of 10 after) | app |
| D3-09 | Plain tkinter in one scrollable frame (`_scroll_frame`) with the specified `_on_closing` order, split over several small files instead of one file | The requested GUI/processing separation outweighs the single-file preference | app, widgets |
| D3-10 | Dates shown in the window use dd-mmm-yy; technical error codes are never shown to the user | Owner preference; understandable messages | data_management, messages |
| D3-11 | Not in this version: data-coverage view and restoring a damaged raw file from the screen (the command line keeps `restore-raw`, `recover`, `verify`) | Keep the first workflow small | docs |
