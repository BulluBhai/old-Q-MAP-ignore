# Q-MAP
Quantitative Market Analytics Platform [Q-MAP]

The governing document is [docs/Q-MAP_Master_Blueprint_v1.0.md](docs/Q-MAP_Master_Blueprint_v1.0.md).
Material decisions are recorded in [docs/decision_log.md](docs/decision_log.md).

## Status: Stage 2 (Foundation)

Implemented: configuration and path management, structured logging, unique Run IDs and run manifests,
the SQLite registry, raw-data registration with a receipt for every file received, readers for CSV, text,
Excel (.xlsx, optional .xls) and Parquet, explicit source profiles, strict date/time parsing, the canonical
OHLC(V) structure, validation with rejection reports, crash recovery and reprocessing controls.

Not implemented (later roadmap stages): research modules, backtesting, portfolio and risk, any front end.

## Three separate locations

| Location | What it holds | In Git? |
|---|---|---|
| **Code folder** (this repository) | programs, tests, example settings, source profiles | yes |
| **Q-MAP_DATA** | raw files, cleaned datasets, the metadata database, future research repository | never |
| **Q-MAP_OUTPUT** | one folder per run: logs, manifests, rejection reports, later reports and charts | never |

Both data and output folders must already exist, must be **outside** the code folder, and must not be inside
each other. Q-MAP stops with a clear message otherwise.

In the configuration file, write Windows paths with forward slashes (`data_root = "D:/Q-MAP_DATA"`) or in single
quotes (`data_root = 'D:\Q-MAP_DATA'`); TOML treats a backslash inside double quotes as an escape. A relative path in
the file is taken relative to the **configuration file's own folder**, never to the folder Q-MAP was started from
(IDLE, a shortcut and a terminal can each start somewhere else). The environment variables `QMAP_DATA_ROOT`,
`QMAP_OUTPUT_ROOT` and `QMAP_CONFIG` override the file; the two root variables must be full paths.

## One-time setup (Windows commands shown; on macOS/Linux use `bin/python` instead of `Scripts\python.exe`)

You need Python 3.11 or newer. Check with:

```bash
python --version
```

1. Choose a folder for Q-MAP's private Python environment. It must be outside the code folder, Q-MAP_DATA and
   Q-MAP_OUTPUT. Do not move it later (if you must, delete it and repeat steps 2 and 3).
2. Create the environment (replace `<ENV_FOLDER>` with your choice):

```bash
python -m venv "<ENV_FOLDER>"
```

3. Install Q-MAP into it (replace `<CODE_FOLDER>` with this repository's folder):

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m pip install -e "<CODE_FOLDER>"
```

   Only if you need old `.xls` files, also run:

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m pip install -e "<CODE_FOLDER>[xls]"
```

4. Copy `Configuration/qmap.example.toml` to a new file named `qmap.local.toml` (Git ignores it) and set
   `data_root` and `output_root` to your two existing folders.
5. Check that everything works. This installs the test tool and runs all automated tests:

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m pip install -e "<CODE_FOLDER>[dev]"
```

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m pytest "<CODE_FOLDER>"
```

You never need to "activate" the environment. Use its own `python.exe` as shown. To open IDLE with it:

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m idlelib
```

## Using it

Every file needs a **source profile**: a small settings file that states, for one file layout, everything that
could otherwise be guessed (header or not, date format and unit, time zone, volume columns, instrument,
timeframe). Q-MAP never guesses. Examples are in `Configuration/source_profiles/`; copy one and edit it.
Check every example setting against your own file before use (time zones and two-digit-year rules especially).

Look at a file first. This registers nothing and writes nothing:

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m qmap --config "<CONFIG_FILE>" preview --profile example_csv_unix_seconds --timeframe 1D "<FILE>"
```

Ingest one or more files:

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m qmap --config "<CONFIG_FILE>" ingest --profile example_csv_unix_seconds --timeframe 1D "<FILE>"
```

The result is `ACCEPTED`, `REUSED` (already processed the same way), `REJECTED` (see the issues report named in
the output; nothing is repaired or dropped), `BLOCKED` (retrying an unchanged rejected file needs a written
`--force-reason`) or `UNSUPPORTED` (the reason is shown). Each run's folder in Q-MAP_OUTPUT holds its log,
`run_manifest.json` and any report.

Finish or clean up after a crash, and check every stored file against its checksum (both print every action taken
and every problem found):

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m qmap --config "<CONFIG_FILE>" recover
```

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m qmap --config "<CONFIG_FILE>" verify
```

## What recovery does (and when it deletes something)

Recovery runs automatically at the start of every run (its actions are written to that run's
`recovery_report.json` and log) and on demand with `recover`. `verify` runs the same recovery, except that it never
deletes cleaned files, and then re-hashes every registered file.

A run is **live** while its program is running: it holds a lock on `Q-MAP_DATA/Metadata/run_locks/<Run ID>.lock`,
which Windows/macOS/Linux release automatically when the program ends in any way. Recovery never touches the work of
a live run, however long it takes. Work is treated as interrupted only if its run is not live **and** the run is
finished or older than `stale_minutes` (default 60).

| Found | Action |
|---|---|
| Interrupted receipt whose stored raw file is present and matches its checksum | registration completed |
| Interrupted receipt without a valid stored file | its temporary copy is **deleted**; receipt marked `failed` |
| Temporary file in `Raw_Data/_incoming` whose receipt is finished (or unknown and older than `stale_minutes`) | **deleted** |
| Unregistered file in `Cleaned_Data` (or `Cleaned_Data/_incoming`) of a run that is not live | **deleted** (it is reproducible from the raw file); the database is re-checked just before deleting |
| Raw file with no database record | reported as `orphan_raw_files`, **never deleted**; ingest the original to adopt it |
| Registered file missing, unreadable or with the wrong checksum | reported, never changed |
| Run left `running` by a program that has ended | marked `failed` (`interrupted`) |

Raw files (registered or not) and anything in `Raw_Data/_quarantine` are never deleted by Q-MAP. An orphan raw file
whose content does not match its name cannot be adopted (ingest refuses to overwrite it); move it aside by hand after
checking it.

## If a stored raw file turns out to be corrupt

Whenever you ingest content that is already registered, Q-MAP re-reads the stored copy and checks its SHA-256
against the registered checksum (file size alone is never trusted). If they differ:

- the ingest is reported as `FAILED` with the code `E_RAW_CORRUPT`, nothing is processed, and the stored file is
  **not** used, overwritten or deleted;
- the problem is recorded in the audit trail, and `verify` lists the file under `checksum_mismatches`.

To fix it you need the original, unmodified file (the one you were just ingesting matches the registered checksum, so
it qualifies). Restore explicitly, with a written reason (use the dataset number from the message):

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m qmap --config "<CONFIG_FILE>" restore-raw --dataset-id <NUMBER> --from "<ORIGINAL_FILE>" --reason "<why this is correct>"
```

Q-MAP refuses if the reason is missing, if the file does not match the registered checksum, or if the stored file is
intact. On success the corrupt copy is **moved** to `Q-MAP_DATA/Raw_Data/_quarantine` (kept as evidence, never
deleted), the original is put back, and the restore is recorded next to the earlier failure. After a crash during a
restore, run `recover`, then ingest the original again.

## What the foundation guarantees

- Original files are never changed. Identical content is stored once (whatever its name or extension) and every
  receipt is still recorded with its own filename, path, time and source.
- Raw files are never overwritten or automatically deleted, and a stored raw file is checksum-verified before every reuse.
  A file is put in place with a single operating-system call that fails if anything is already there, so even two
  programs ingesting at the same moment cannot replace each other's file.
- A finished receipt, a stored profile snapshot, an attempt, a quality check, a dataset's identity, a run and an
  instrument cannot be deleted or rewritten (database triggers).
- Invalid data is reported, never repaired or discarded. A rejected file leaves an audit trail.
- Dates, timestamp units, time zones, instrument identity and volume mapping are declared, never guessed.
- Missing volume does not invalidate OHLC data unless the requirement set says volume is required.
- Each cleaned dataset records its profile version, processing-code version and lineage back to the raw file.
- Preserved extra columns (`x_...`) are not quantitative inputs; use `read_quant_columns` to read only the inputs.

## Known limitations (Stage 2)

- Automated tests run on Linux and, through `.github/workflows/tests.yml`, on Windows (Python 3.11). Network drives,
  OneDrive-synchronised folders and antivirus interference are not covered by any automated test.
- Very long folder names can exceed Windows' 260-character path limit; keep the data and output roots short.
- Only a command line exists; there is no graphical front end (the front end is an open Blueprint decision).
- Selecting the "current" dataset across several raw files for one instrument is not defined yet.
- Re-receiving registered content re-reads the stored copy to verify it, so very large files take correspondingly longer.
- The validation settings in the configuration file (date range, `min_rows`, move and gap thresholds, requirement
  sets) and the run date are **recorded** with every attempt and in every cleaned file, but they are not part of the
  processing version. If they change, a repeat ingest still reuses the earlier result and says that the settings
  differ (open decision, see the decision log).
- Reusing a processing version that has since been superseded returns that version's (superseded) datasets and says so.
- Run liveness relies on operating-system file locks. Keep Q-MAP_DATA on a local disk; locks on network shares are
  not reliable, and the `stale_minutes` age rule is then the only safeguard.
- Parquet is used for cleaned data; DuckDB (Blueprint section 8.3) is not used yet, because nothing in Stage 2 queries
  across datasets.
