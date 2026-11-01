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
| `quality_flags` | int64 | Bit mask: 1 volume_missing, 2 date_order_unverified, 4 large_move, 8 moved_by_sort, **16 period_may_be_incomplete** (derived data only) |
| `x_<name>` | as read | Preserved source columns (for example `x_net_volume`), kept exactly as read. **Not quantitative inputs**; `catalog.read_dataset` never returns them. |

Derived-timeframe files add four columns: `period_start`, `period_end`, `first_session_date` and `bars_in_period`.
Every file carries its provenance in its Parquet metadata (`qmap` key).

`Volume` and `Net Volume` are never merged. A second volume-like column is preserved separately unless a profile
explicitly maps it.

## Where data live

| Folder under Q-MAP_DATA | Content | Storage class |
|---|---|---|
| `Raw_Data/<xx>/<sha256>.<ext>` | Preserved originals, stored by content, read-only | Always permanent; never moved or deleted |
| `Cleaned_Data/<EXCHANGE>/<SYMBOL>/<TF>/...parquet` | Standardised datasets | Permanent |
| `Timeframe_Data/<EXCHANGE>/<SYMBOL>/<TF>/...parquet` | Derived timeframes | Permanent |
| `Temporary_Data/<the permanent path>` | Any standardised or derived dataset classified Temporary | Temporary |
| `*/_incoming/` | Files being written; owned by a live run, cleaned by recovery | |
| `Metadata/` | Registry database, run locks | |

There is one file per dataset and no database per instrument. File names end with the Run ID that created them, so two
runs can never overwrite each other.

## Registry tables (schema version 6)

| Table | Holds | Protection |
|---|---|---|
| `datasets` | Every raw, standardised and derived dataset: layer, instrument, timeframe, path, SHA-256, rows, dates, parent, processing version, canonical schema version, volume status, requirement set, settings fingerprint, status (active/superseded), **storage_class**, **file_deleted_at** | Never deleted. Identity is immutable. Storage class and path always agree (Temporary ⇔ `Temporary_Data/...`), and change only together, under a matching recorded `move` action. `file_deleted_at` is set only under a recorded `delete_file` action. Raw is always permanent. Only temporary files can be deleted, and a deletion is final. |
| `instruments` | Exchange + symbol | Never deleted; identity immutable |
| `ingest_events` | Every file received (name, path, time, checksum) | Never deleted |
| `ingest_attempts` | Every processing attempt and its full interpretation (profile, mapping, date rules, settings) | Append-only |
| `quality_checks` | Every check result (error, warning, info) for an attempt or a dataset | Append-only |
| `source_profiles` | A snapshot of every profile version used | Immutable |
| `runs`, `run_outputs`, `run_inputs` | Every run (Run ID, module, status, parameters, code version), its outputs and the datasets it used | Runs never deleted |
| **`storage_actions`** (new) | Every move and deletion: dataset, from/to class and path, reason, Run ID, status | Inserted only as `started`; at most one open per dataset; finished once; `completed` only if the dataset shows the change, never `failed` if it does |
| **`dataset_derivations`** (new) | For each derived dataset: method, method version, parameters, source dataset and checksum, Run ID | Append-only |
| `research_records`, `modules` | Reserved for the Research Library | |

### Identifiers and versions

| Item | Format |
|---|---|
| Dataset | Integer `dataset_id` |
| Run | Run ID `<MODULE>_<YYYYMMDD>_<HHMMSS>` (UTC); modules `FOUND` (loading), `DBM` (Database Manager actions), `DSUM` (Dataset Summary) |
| Processing version, standardised data | `<profile_id>@<profile_version>+<cleaning code version>` |
| Processing version, derived data | `derive:ohlcv_period_aggregation@1` |
| Settings fingerprint | `vs1:<16 hex>` |
| Schema | `schema_version` table; currently 6 |

## Three separate statuses

| Status | Where it comes from |
|---|---|
| Processing outcome | `ingest_attempts.outcome`, or a registered derivation |
| Validation status | Warnings among the dataset's quality checks: **Passed** or **Passed with warnings** |
| Readiness | Computed per analysis by `catalog.check_readiness` from the dataset AND that analysis's requirements. It is never stored, because it depends on the question being asked. |
