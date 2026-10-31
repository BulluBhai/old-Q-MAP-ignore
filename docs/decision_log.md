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
| D2-18 | pandas is not a Stage 2 dependency; dependencies are pyarrow, openpyxl, tzdata (xlrd optional, pytest for development) | pandas listed in the design | The foundation needed only pyarrow and the standard library; pandas can be added when a stage needs it | pyproject |
| D2-19 | Cleaned file paths include the Run ID (`...<raw sha 12>_<version hash>_<Run ID>.parquet`) | Deterministic path proposed | A concurrent identical ingest can never overwrite a registered file | ingest |
| D2-20 | Documentation lives in the existing `docs/` folder | Design said `Documentation/` | The approved blueprint is already committed in `docs/` | docs |
| D2-21 | A registered raw file is verified against its registered SHA-256 before it is reused or processed (size is never trusted). On a mismatch the receipt fails with `E_RAW_CORRUPT`, nothing is processed, and the stored file is not used, overwritten or deleted. Recovery is explicit: `restore-raw` requires a written reason, a source that matches the registered checksum and a corrupt stored copy; the corrupt copy is moved to `Raw_Data/_quarantine` (never deleted) and the restore is recorded as its own receipt | Size-only check found in PR #1 review | A same-size corruption could be reused and processed as if it were the registered raw data | storage/registry, storage/recovery, cli |

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
