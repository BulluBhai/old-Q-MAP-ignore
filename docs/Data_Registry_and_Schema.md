# Q-MAP Data Registry and data definitions

The registry is one SQLite file, `Q-MAP_DATA/Metadata/qmap_metadata.sqlite`. Market data are Parquet files under
`Q-MAP_DATA`. Both applications use the same registry and the same definitions. Read access for both goes through
`qmap/catalog.py`.

## Canonical market-data structure (schema version 1, unchanged)

One Parquet file per instrument and timeframe.

| Column | Type | Meaning |
|---|---|---|
| `session_date` | date | Trading date. For a derived bar: the **last** session it contains. |
| `timestamp_utc` | timestamp (UTC) | Bar start for intraday data; empty for daily and longer |
| `open`, `high`, `low`, `close` | float64 | Mandatory |
| `volume` | float64 | Optional. Empty when absent, never zero-filled. |
| `src_row` | int64 | 1-based position in the original source. Empty for derived bars. |
| `quality_flags` | int64 | Bit mask: 1 volume_missing, 2 date_order_unverified, 4 large_move, 8 moved_by_sort, **16 period_may_be_incomplete** (derived data only), **32 conflicting_observation** (03-Nov-26, DQ-10: another row has the same timestamp with different values; derived periods built from such dates inherit it) |
| `x_<name>` | as read | Preserved source columns (for example `x_net_volume`), kept exactly as read. **Not quantitative inputs**; `catalog.read_dataset` never returns them. |

Derived-timeframe files add four columns: `period_start`, `period_end`, `first_session_date` and `bars_in_period`.
Every file carries its provenance in its Parquet metadata (`qmap` key).

`Volume` and `Net Volume` are never merged. A second volume-like column is preserved separately unless a profile
explicitly maps it.

**Repeated timestamps (03-Nov-26, DQ-10, cleaning code `c2`).** Rows identical in every source column are exact
duplicates: the first is kept in the standardised copy, the others are recorded (check `exact_duplicates_removed`,
issues report, transformation step) and never stored. Rows that share a timestamp with any difference are conflicting
observations: ALL are kept, in source order within the timestamp, flagged 32, and reported (`conflicting_observations`,
a warning, never an error). One timestamp can therefore have several rows; Q-MAP never chooses between them.

**Timeframe values (03-Nov-26, DQ-7).** Open-ended: `<n>m` (any whole minutes below a day, e.g. `3m`, `75m`), `<n>h`
(whole hours, e.g. `2h`, `3h`), `1D`, `1W`, `1M` (`1Q`, `1Y` derived), `<n>d` for other day periods, and `MIXED` for a
file whose sampled blocks show different intervals. The registered value is the interval measured in the data.

## Where data live

| Folder under Q-MAP_DATA | Content | Storage class |
|---|---|---|
| `Raw_Data/<xx>/<sha256>.<ext>` | Preserved originals, stored by content, read-only | Always permanent; never moved or deleted |
| `Cleaned_Data/<EXCHANGE>/<SYMBOL>/<TF>/...parquet` | Standardised datasets | Permanent |
| `Timeframe_Data/<EXCHANGE>/<SYMBOL>/<TF>/...parquet` | Derived timeframes | Permanent |
| `Temporary/<the permanent path>` | Any standardised or derived dataset classified Temporary (Blueprint v1.2 §9.1; owner decision OD-8; schema 7) | Temporary |
| `Temporary_Data/<the permanent path>` | **Legacy:** datasets moved to Temporary by earlier PR #4 code, before OD-8. They stay valid where they are and are never moved automatically; relocate with Make Permanent, then Move to Temporary. Nothing new is ever written here. | Temporary |
| `*/_incoming/` | Files being written; owned by a live run, cleaned by recovery | |
| `Metadata/` | Registry database, run locks | |

There is one file per dataset and no database per instrument. File names end with the Run ID that created them, so two
runs can never overwrite each other.

## Registry tables (schema version 10)

| Table | Holds | Protection |
|---|---|---|
| `datasets` | Every raw, standardised and derived dataset: layer, instrument, timeframe, path, SHA-256, rows, dates, parent, processing version, canonical schema version, volume status, requirement set, settings fingerprint, status (active/superseded), **storage_class**, **file_deleted_at** | Never deleted. Identity is immutable. Storage class and path always agree (Temporary ⇔ `Temporary/...`, or the legacy `Temporary_Data/...` for rows already there), and change only together, under a matching recorded `move` action. `file_deleted_at` is set only under a recorded `delete_file` action. Raw is always permanent. Only temporary files can be deleted, and a deletion is final. |
| `instruments` | Exchange + symbol | Never deleted; identity immutable |
| `ingest_events` | Every file received (name, path, time, checksum) | Never deleted |
| `ingest_attempts` | Every processing attempt and its full interpretation (profile, mapping, date rules, settings) | Append-only |
| `quality_checks` | Every check result (error, warning, info) for an attempt or a dataset | Append-only |
| `source_profiles` | A snapshot of every profile version used | Immutable |
| `runs`, `run_outputs`, `run_inputs` | Every run (Run ID, module, status, parameters, code version), its outputs and the datasets it used | Runs never deleted |
| **`storage_actions`** (new) | Every move and deletion: dataset, from/to class and path, reason, Run ID, status | Inserted only as `started`; at most one open per dataset; finished once; `completed` only if the dataset shows the change, never `failed` if it does |
| **`dataset_derivations`** (new) | For each derived dataset: method, method version, parameters, source dataset and checksum, Run ID | Append-only |
| `research_records`, `modules` | Reserved for the Research Library | |
| **`data_sources`** (schema 8) | Folder sources: location, name, market time zone, default exchange, "file name is the symbol", sub-folders, skip patterns, active/removed | Never deleted; location and identity immutable; settings may change (each scan keeps a snapshot) |
| **`source_scans`** (schema 8) | One row per scan: source, Run ID, settings snapshot, status, counts | Never deleted; finished once |
| **`source_file_observations`** (schema 8) | What each scan saw for each file: size, modification time, SHA-256, change (new/changed/unchanged/missing/unreadable), action, outcome, links to the ingest event, attempt and datasets, the full interpretation (evidence and generated profile ID), open questions, retry date | Append-only. A file's current state is its latest observation (no second, updatable copy) |
| **`source_answers`** (schema 8) | The user's answers to interpretation questions and corrections (exchange, symbol, date layout, time zone), with the file's structure signature | Append-only; an answer is used only while the file keeps that structure. Since 03-Nov-26 a correction can also be recorded for an imported file; the next scan registers the corrected data as a new dataset |
| **`dataset_user_decisions`** (schema 10) | Reversible user decisions on standardised/derived datasets: `rejected` / `restored`, reason, origin (sources, datasets, command line), Run ID, time. A dataset's current decision is its latest one | Append-only; never for raw originals. A rejected dataset is unchanged but not offered to analyses (readiness FAILs with the reason) |

### Identifiers and versions

| Item | Format |
|---|---|
| Dataset | Integer `dataset_id` |
| Run | Run ID `<MODULE>_<YYYYMMDD>_<HHMMSS>` (UTC); modules `FOUND` (loading), `DBM` (Database Manager actions), `SCAN` (folder scans), `DSUM` (Dataset Summary) |
| Processing version, standardised data | `<profile_id>@<profile_version>+<cleaning code version>`. For automatically read files the profile is generated: `auto_<12 hex>@1+c2`, where the hex is the hash of the generated profile text (stored in `source_profiles`), so the same layout always gives the same processing version |
| Processing version, derived data | `derive:ohlcv_period_aggregation@1` |
| Settings fingerprint | `vs2:<16 hex>` (since 03-Nov-26 it includes the `[timeframe_sampling]` settings; `vs1` before) |
| Cleaning code version | `c2` since 03-Nov-26 (exact duplicates removed, conflicting observations kept); `c1` before |
| Schema | `schema_version` table; currently 10 (migration 7: Temporary area moved to `Temporary/`, OD-8; migration 8: folder sources and scans, Blueprint v1.3; migration 9: file-name identification ON for every folder, DQ-8; migration 10: `dataset_user_decisions`) |
| Alias registry | `Q-MAP_DATA/Reference_Files/Instrument_Aliases.csv`: first column canonical name, then aliases. Edited by the user; Q-MAP only appends through "Add to alias registry" (backup and record in the run folder) |

## Three separate statuses

| Status | Where it comes from |
|---|---|
| Processing outcome | `ingest_attempts.outcome`, or a registered derivation |
| Validation status | Warnings among the dataset's quality checks (those of the attempt that created it, plus checks recorded later on the dataset itself, such as `conflicts_with_existing_dataset`): **Passed** or **Passed with warnings** |
| Readiness | Computed per analysis by `catalog.check_readiness` from the dataset AND that analysis's requirements. It is never stored, because it depends on the question being asked. |

## Limits of detecting earlier tampering (report-never-repair)

Since schema 6, the database itself refuses storage changes that are not covered by a matching recorded action. Rows
changed directly **before** schema 6 cannot be prevented any more, only detected. Recovery and `verify` list them as
`storage_inconsistencies`, and never change them.

**What is detected:**

1. Class and path disagree (Temporary but not under `Temporary/` or the legacy `Temporary_Data/`, or the reverse).
2. A file marked deleted without a completed `delete_file` action for that path.
3. A current path that its **original path plus its completed moves** do not explain. The original path is rebuilt
   with the naming rule in `storage/paths.py` (decision D2-19) from records that earlier migrations already make
   immutable:
   - standardised datasets: instrument, timeframe, parent raw checksum, processing version, and the Run ID of the
     creating attempt;
   - derived datasets: the derivation's source checksum and Run ID.

   This covers a class and path changed together and ending Permanent at a different path.
4. A recorded move that does not start where the dataset was.

**What is NOT, or not fully, detected:**

- *Which* intermediate classes and paths a tampered row passed through, and *when*: the registry keeps only the
  current path, and the tampering left no record. Only the fact that the current path is unexplained can be shown.
- Raw (original) files are not checked this way. Their path has been immutable since migration 1 and their class since
  migration 5, so there is nothing to detect.
- Tampering that also deleted or rewrote the immutable lineage records. Triggers prevent that unless they themselves
  were dropped with a database tool; no database-level rule can protect against someone who removes the rules.
- A dataset written by code that named files differently from `storage/paths.py` would be reported as unexplained.
  That would be a false alarm, never a repair. All code in this repository has used the same rule since PR #1.
- Whether the **file on disk** matches the registry is a separate check: `verify` re-hashes every registered file and
  reports missing or changed files.
