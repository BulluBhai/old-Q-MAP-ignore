# Q-MAP
Quantitative Market Analytics Platform [Q-MAP]

**Release:** v0.1 release candidate `0.1.0rc1`, for **controlled analytical use after the Project Owner's Windows/IDLE
acceptance** (not yet given). Start here:
[Q-MAP v0.1 Windows operating and acceptance guide](docs/release/Q-MAP_v0.1_Windows_Operating_and_Acceptance_Guide_03_Nov_26_180000.md)
and [v0.1 known limitations and release boundaries](docs/release/Q-MAP_v0.1_Known_Limitations_and_Release_Boundaries_03_Nov_26_180000.md).

The governing document is **Q-MAP Master Blueprint v1.35**
([Q-MAP_Master_Blueprint_v1.35.md](Q-MAP_Master_Blueprint_v1.35.md), with an `.html` copy), approved and adopted by the
Project Owner on 3 November 2026 and superseding v1.3, v1.2, v1.1 and v1.0 where they differ. v1.3 is kept at the top
level for history; v1.2 is in PR #5; v1.0 is in the repository history; no v1.1 file was ever committed (see the
[v0.1 release documents](docs/release/)). How the code meets v1.35 is in the
[v0.1 release-readiness audit](docs/release/Q-MAP_v0.1_Release_Readiness_Audit_03_Nov_26_165501.md) (earlier:
[Blueprint v1.3 implementation audit](docs/architecture/Blueprint_v1.3_Implementation_Audit.md)).
Material decisions are recorded in [docs/decision_log.md](docs/decision_log.md).

## Two applications, one platform

| Open (Thonny or IDLE, press F5) | Application | For |
|---|---|---|
| **`database_manager.py`** | Q-MAP Database Manager | Add the folders where your market files are kept and scan them: new and changed files are read, checked and loaded automatically, and you are asked only when something is unclear. Also: load and check single files with a chosen profile, see every prepared dataset with its lineage, keep it Permanent or Temporary, delete Temporary data, derive weekly/monthly/quarterly/yearly data from daily data |
| **`analytical_workbench.py`** | Q-MAP Analytical Workbench | Run analyses on prepared data: **MA Affinity (QLOPB)** and Dataset Summary. Readiness checks first, a Run ID and a full record of inputs and of the code build for every run. Never imports source files |
| `Q-MAP.py` | (older launcher) | Opens Database Manager |

Both use the same Data Registry, data definitions and remembered folders. They can be open at the same time, and
neither needs the other to be running. Clone or copy this repository into a folder named **`Q-MAP_APP`** next to
`Q-MAP_DATA`, `Q-MAP_OUTPUT` and `Q-MAP_TEST_FILES`.

Documentation:
- [Architecture and implementation](docs/Q-MAP_Architecture_and_Implementation.md) (includes the folder guide and
  migration notes)
- [Database Manager guide](docs/user_guides/Database_Manager_User_Guide.md)
- [Analytical Workbench guide](docs/user_guides/Analytical_Workbench_User_Guide.md)
- [Data Registry and schema](docs/Data_Registry_and_Schema.md)
- [Testing and acceptance report](docs/acceptance_testing/Q-MAP_Testing_and_Acceptance_Report_01_Nov_26_160000.md)
- [Sources acceptance checklist (Windows/IDLE)](docs/acceptance_testing/Q-MAP_Sources_Acceptance_Checklist_02_Nov_26_183000.md)
- [Outstanding work and owner decisions](docs/Outstanding_Work_Register.md)

**Working now:**
- the Stage 2 foundation: configuration, Run IDs, the SQLite registry, raw-file preservation, readers for CSV, text,
  Excel and Parquet, source profiles, validation and recovery;
- Sources: folder discovery with automatic interpretation, idempotent re-scans, questions only for real
  ambiguities, overlap and conflict reports (Blueprint v1.35 §8.5), timeframe inference, instrument identification
  with an alias registry, exact-duplicate removal and conflict retention (DQ-7 to DQ-10);
- Data Management; Datasets and Storage; derived weekly/monthly/quarterly/yearly timeframes;
- the Analytical Workbench with **MA Affinity (QLOPB MA Affinity Scanner V2, calculations unchanged; daily, weekly and
  monthly datasets)** and Dataset Summary, a descriptive utility;
- a build identifier (version, source fingerprint, git commit) in every run record.

**Not implemented yet:** MIQP Market Intelligence (outside v0.1), provider API adapters (Blueprint v1.35 §8.5.2),
DuckDB queries, QLOPB pivot/CPR/other references, other research modules, backtesting, portfolio and risk. They are
shown as COMING SOON. Full list: the known-limitations document above.

![Database Manager: Datasets and Storage](docs/acceptance_testing/evidence_01_Nov_26/screenshots/04_datasets_and_storage_01_Nov_26.png)
![Analytical Workbench after a run](docs/acceptance_testing/evidence_01_Nov_26/screenshots/06_workbench_completed_01_Nov_26.png)

## Database Manager: Data Management (loading files)

1. Install Python 3.11 or newer from python.org (keep "tcl/tk and IDLE" ticked). No other installation step is needed: on
   first start Q-MAP lists any missing package and offers to install it for you (the developer setup below is optional).
2. Open **`database_manager.py`** (in this folder) in **Thonny** or **IDLE** and press **F5**.
   - In Thonny, make sure the interpreter is the Python of your Q-MAP environment: Tools > Options > Interpreter,
     then choose the `python.exe` inside your `<ENV_FOLDER>\Scripts` folder.
   - If something is missing (an old Python, or a package), Q-MAP explains it in a message and, for missing
     packages, offers to install them for you.
3. On first start choose your two folders (**Q-MAP_DATA** and **Q-MAP_OUTPUT**) on the Home screen. Q-MAP checks them
   with the same rules as the Foundation and remembers them in your own user settings (on Windows:
   `%APPDATA%\Q-MAP\gui_settings.json`), never inside the program folder. Your own source profiles are kept
   in a `profiles` folder next to that file.
4. **Data Management** follows the numbered sections on the screen:
   - **1. Input**: add files, preview any of them (nothing is saved by previewing).
   - **2. Output**: your two folders, and buttons to open the last run folder and the problem report.
   - **3. Options**: pick a source profile (its settings are shown in plain English; you can copy an example,
     edit and check it, or browse for a profile file). Type exchange, symbol or timeframe only if the profile
     says it cannot read them from the file; a note under the boxes says where this profile takes each value from.
     Some examples read the exchange and symbol from the file NAME (for example `NSE_NIFTY_1D.csv`). If your file
     names do not look like that, click **Copy so it asks me for exchange and symbol...**: it makes your own copy of
     the profile that asks you to type them (Q-MAP still never guesses them).
   - Example profiles exist for CSV and text (with or without a header row), Excel `.xlsx` (with or without a header
     row, ISO text timestamps or real Excel date cells) and Parquet. Check every setting against your file first.
   - **Check files** tests everything and saves nothing. **Load files into Q-MAP** loads them with the Foundation.
   - Progress, results (click a row for a plain-English explanation of any problem) and a live log are shown below.
5. **Datasets and Storage** and the **Analytical Workbench** are described in their user guides (links above).

If you close the window while a load is running, Q-MAP finishes the file it is working on and then stops; the next
start tidies up anything unfinished.

## Three separate locations

| Location | What it holds | In Git? |
|---|---|---|
| **Code folder** (this repository) | programs, tests, example settings, source profiles | yes |
| **Q-MAP_DATA** | raw files, cleaned datasets, derived timeframes, Temporary datasets, the metadata database | never |
| **Q-MAP_OUTPUT** | one folder per run: logs, manifests, rejection reports, later reports and charts | never |

Both data and output folders must already exist, must be **outside** the code folder, and must not be inside
each other. Q-MAP stops with a clear message otherwise.

In the configuration file, write Windows paths with forward slashes (`data_root = "D:/Q-MAP_DATA"`) or in single
quotes (`data_root = 'D:\Q-MAP_DATA'`); TOML treats a backslash inside double quotes as an escape. A relative path in
the file is taken relative to the **configuration file's own folder**, never to the folder Q-MAP was started from
(IDLE, a shortcut and a terminal can each start somewhere else). The environment variables `QMAP_DATA_ROOT`,
`QMAP_OUTPUT_ROOT` and `QMAP_CONFIG` override the file; the two root variables must be full paths.

## Developer setup (optional; NOT needed to use Q-MAP from IDLE)

To *use* Q-MAP you only open `database_manager.py` or `analytical_workbench.py` in IDLE and press F5; missing packages
are offered for installation (see the Windows guide above). The steps below are for developers and running the tests.
Windows commands are shown; on macOS/Linux use `bin/python` instead of `Scripts\python.exe`.

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

The tests that open real windows need a screen, so they run on a normal Windows/macOS desktop. On a Linux machine
without a screen they are skipped, or can be run with `xvfb-run`. Without `tkinter` they are skipped too.

You never need to "activate" the environment. Use its own `python.exe` as shown. To open IDLE with it:

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m idlelib
```

## Using it

Every file needs a **source profile**: a small settings file that states, for one file layout, everything that
could otherwise be guessed (header or not, date format and unit, time zone, volume columns, instrument,
timeframe). Q-MAP never guesses. Q-MAP's own profiles are in `Configuration/source_profiles/`: **Standard** profiles are
recommended for routine use, **Example** profiles are for learning and testing (naming standard:
[docs/standards/Q-MAP_Naming_and_Reference_Conventions.md](docs/standards/Q-MAP_Naming_and_Reference_Conventions.md)).
Copy one to adapt it. Check every setting against your own file before use (time zones and two-digit-year rules
especially). Profiles renamed under the standard are still found by their earlier names.

Look at a file first. This registers nothing and writes nothing:

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m qmap --config "<CONFIG_FILE>" preview --profile csv_hdr_unixs --exchange NSE --symbol NIFTY --timeframe 1D "<FILE>"
```

Ingest one or more files:

```bash
"<ENV_FOLDER>\Scripts\python.exe" -m qmap --config "<CONFIG_FILE>" ingest --profile csv_hdr_unixs --exchange NSE --symbol NIFTY --timeframe 1D "<FILE>"
```

The result is `ACCEPTED`, `REUSED` (already processed the same way, with the same validation settings), `REJECTED` (see the issues report named in
the output; nothing is repaired or dropped), `BLOCKED` (see below) or `UNSUPPORTED` (the reason is shown). Each run's
folder in Q-MAP_OUTPUT holds its log, `run_manifest.json` and any report.

### Retrying a rejected file

| Situation | What happens when you ingest the same file again |
|---|---|
| You changed the profile (new `profile_version`) or a validation setting that affects the result | It is processed again; no reason needed |
| It was rejected **only** because some dates were later than "today + `plausible_max_days_ahead`" | It is `BLOCKED` until those dates are allowed; the message gives the first run date on which they are. From that date on it is processed again automatically (recorded as `retry_after_date_limit`); no reason needed |
| Anything else, unchanged | `BLOCKED`: the same file under the same rules would give the same result |
| You want to try again anyway | Add `--force-reason "<why>"`. All checks still apply; the reason is recorded |

Every attempt, including each rejection and its issues report, is kept. A retry never changes or removes an earlier
attempt; it is linked to it (`revalidation_of_attempt_id`).

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
- Both applications have been exercised on Linux (real windows on a virtual screen), **not yet on Windows**: Windows-only behaviour (opening folders, remembered-settings location, high-DPI
  text) is covered by simulation. The command line remains for `recover`, `verify` and `restore-raw`.
- Selecting the "current" dataset across several raw files for one instrument is not defined yet.
- A daily, weekly or monthly timeframe on data with several bars per day/week/month (for example 5-minute bars
  declared `1D`) is reported as a warning (`one_bar_per_period`), not rejected; a 5-minute file declared `1m` is
  likewise only a warning (`timeframe_spacing`). The timeframe you declare is always used as declared.
- **Incomplete trading days are not reliably detected.** The note "Some days have fewer bars than usual" compares each day with
  the most common day length in the same file; there is no trading calendar. In the owner's sample files 4 of 5
  incomplete intraday days were not flagged. Every bar is still stored exactly as in the source, but do not treat
  the absence of this warning as proof that a day is complete before session-based analysis (daily values built
  from intraday bars, opening/closing studies). Details: `docs/sample_file_testing/`, section F.3.
- Bar timestamps are stored exactly as given; whether a source stamps the start or the end of each bar is not
  recorded yet and must be confirmed per source.
- Results of testing the Project Owner's 11 sample files: `docs/sample_file_testing/`.
- Re-receiving registered content re-reads the stored copy to verify it, so very large files take correspondingly longer.
- A result is reused only when the raw content, processing version, ingest request **and validation settings** match.
  Changing `plausible_min_date`, `plausible_max_days_ahead`, `max_daily_move_pct`, `min_rows` or a requirement set's
  `require_volume` reprocesses the file into a new dataset (the previous one is superseded, never deleted); its
  `config_fingerprint` identifies the settings used. `max_gap_days` only affects a warning, and the run date only moves
  the "not in the future" limit, so neither prevents reuse; both are recorded, and a different `max_gap_days` is
  mentioned when a result is reused. Results recorded before the fingerprint existed are reused only if their recorded
  settings match; results with no recorded settings are reprocessed.
- Reusing a processing version that has since been superseded returns that version's (superseded) datasets and says so.
- "Today" for the future-date check is the UTC date. Exchange dates east of UTC (for example India) can be up to one
  calendar day ahead of it, so keep `plausible_max_days_ahead` at 1 or more (the default is 1).
- The time-zone database version (tzdata) used for UTC conversion is not recorded; historical rules rarely change.
- Run liveness relies on operating-system file locks. Keep Q-MAP_DATA on a local disk; locks on network shares are
  not reliable, and the `stale_minutes` age rule is then the only safeguard.
- Parquet is used for cleaned and derived data; DuckDB (Blueprint section 8.3) is not used yet, because nothing queries
  across datasets.
- More limitations and the decisions needed: [docs/Outstanding_Work_Register.md](docs/Outstanding_Work_Register.md).
