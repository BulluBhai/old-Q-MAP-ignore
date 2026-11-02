# Q-MAP Database Manager: user guide

Open `Q-MAP_APP/database_manager.py` in Thonny or IDLE and press **F5**. If something is missing (Python version,
a package, tkinter), a message explains it and, for packages, offers to install them.

Database Manager prepares the data every analysis depends on. It **never changes your original files**.

## Home

- **Your folders**: choose `Q-MAP_DATA` and `Q-MAP_OUTPUT` once. They are checked with the platform's own rules
  (separate, outside the program folder) and remembered for both Q-MAP applications.
- **Data at a glance**: the number of instruments, active datasets per timeframe, Permanent and Temporary datasets,
  superseded datasets, datasets you deleted, and preserved original files.
- The two working areas below, each with an **Open** button.

## Sources: automatic loading (the normal way to load data)

Added 02-Nov-26 for Blueprint v1.3 §8.5. You do not choose profiles or type layouts here.

1. **Input - folders.** Press **Add folder...** and choose the folder that holds your files (any folder on this
   computer, including a synchronised OneDrive or Google Drive folder; files must be downloaded, not "online only").
   Before adding, set:
   - **Market time zone** (for Indian exchanges `Asia/Kolkata`): used to work out each bar's trading date and for
     times written without an offset. Leave it empty and Q-MAP asks for it when a file needs it.
   - **Default exchange** (for example `NSE`), used when a file does not say its exchange.
   - **File name is the symbol** (optional): `RELIANCE.csv` is read as symbol RELIANCE on the default exchange. Off
     by default, so a name like `prices.csv` is never mistaken for a symbol.
   - **Include sub-folders** and **Skip files matching** (for example `*backup*`).
   Q-MAP's own data, output and program folders are refused as sources. To change settings later, select the folder,
   edit the boxes and press **Save settings of selected folder**. **Stop using selected folder** stops scanning; it
   deletes nothing.
2. **Output - files.** After a scan, every file in the folder is listed with its result: *Imported*, *Already
   loaded*, *Needs your answer*, *Rejected* (with the reason), *Ignored* (not a data file type), *Failed* (for example
   unreadable) or *No longer in the folder*. Select a file to see exactly how Q-MAP read it (separator, header,
   which column is which, date layout, time zone, instrument, timeframe) and any question. Each scan also writes a
   `Scan_Report_<dd_Mmm_yy_hhmmss>.csv` into its run folder in `Q-MAP_OUTPUT/Data_Management`.
3. **Options - scan and answer.** **SCAN SELECTED FOLDER NOW** looks at the folder. For a file that needs an answer,
   select it: only the boxes its question needs are switched on (exchange and symbol, timeframe, date layout, or market
   time zone). **Save answer**, then scan again. An answer is reused only while the file keeps the same layout.

What a scan does, and does not do:

- Files that have not changed since the last scan are skipped (same size, time and checksum). Scanning twice never
  creates duplicates; the same content under two names is loaded once.
- A changed file is loaded as a new version. If its bars overlap an existing dataset of the same instrument and
  timeframe, identical bars are noted, and **different values are shown as a warning** on the new dataset. Neither
  dataset is changed and nothing is merged: you choose which one to analyse (your decision DQ-1, 02-Nov-26: report only).
- Every loaded file goes through exactly the same checks as Data Management. A file that fails a check is rejected
  and never becomes available to the Workbench. A file rejected only because its last dates are in the future is
  loaded again automatically by a scan on or after the date that allows them.
- Nothing in your folder is ever created, changed, moved or deleted.

How layouts are recognised (rules A-1 to A-9, in `docs/architecture/Blueprint_v1.3_Implementation_Audit.md`,
section 6): column names such as `date`/`time`, `open`, `high`, `low`, `close`, `volume`; files without a header only
when columns 2-5 behave like open, high, low, close on every row; dates in ISO, `25-02-26`, `25/02/2026`, `25-Feb-26`,
`20260225`, Unix seconds or milliseconds, or spreadsheet date cells. When two date readings both fit (for example
day-first and month-first) and the order of the rows does not settle it, Q-MAP asks. Two-digit years: 00-68 =
2000-2068, 69-99 = 1969-1999. Instrument from `exchange`/`symbol` columns in the file first, then your answer, then a file name such as
`NSE_NIFTY, 1D.csv`. A file whose name contradicts its own exchange or symbol column is rejected, never read with the
name's value (your decision DQ-2). If only the exchange is missing, only the exchange is asked. Timeframe from the spacing of the bars; a file name that disagrees with the data is asked about.

## Data Management: loading files with a chosen profile

For unusual layouts that automatic reading rejects. The screen and its rules are unchanged from the first graphical
version:

1. **Input**: add files and preview any of them. Previewing saves nothing.
2. **Output**: your folders, the last run folder and the problem report.
3. **Options**: pick the **source profile** that describes the file layout (header row, date format, time zone,
   volume column ...). Q-MAP never guesses these. If the profile cannot read the exchange, symbol or timeframe from
   the file, type them.
   - The list shows each profile's plain description first. For example: "Headered CSV: time (DD-MM-YY), open,
     high, low, close, Volume, Net Volume   [Standard]   (csv_hdr_ddmmyy v1)".
   - **Standard** profiles are recommended for routine use; each was checked against your sample files.
   - **Example** profiles are for learning and testing. They read the exchange and symbol from the file name (for
     example `NSE_NIFTY_1D.csv`), and each names the Standard profile to use instead.
   - Your own profiles are shown as **My profile**.
   - Profiles renamed under the naming standard keep working when asked for by their earlier names. Datasets loaded
     before the rename are unaffected. See `docs/standards/Q-MAP_Naming_and_Reference_Conventions.md`.

   | Your file | Standard profile |
   |---|---|
   | CSV with a header row, dates like 30-10-26 | `csv_hdr_ddmmyy` |
   | CSV with a header row, ISO date-times with +05:30 | `csv_hdr_isodt` |
   | CSV with a header row, Unix seconds | `csv_hdr_unixs` |
   | CSV without a header row, ISO date-times | `csv_nohdr_isodt` |
   | CSV without a header row, Unix seconds | `csv_nohdr_unixs` |
   | Text with a header row, dates like 2026-10-30, daily | `txt_hdr_isodate` |
   | Text without a header row, two identical volume columns, daily | `txt_nohdr_isodate_dupvol` |
   | Excel with a header row, ISO date-times as text | `xlsx_hdr_isodt` |
   | Excel without a header row, ISO date-times as text | `xlsx_nohdr_isodt` |
   | Excel with a header row, real date cells | `xlsx_hdr_xldate` |
   | Parquet with Date (no time zone), Open ... Volume, 1-minute | `parquet_hdr_naivedt` |
   - **Check files** tests everything and saves nothing.
   - **LOAD FILES INTO Q-MAP** stores the original, standardises it, validates it and registers the result.

A profile that does not match the file (for example, a Unix-seconds profile on a `DD-MM-YY` file) is rejected with a
plain explanation of what is wrong. Click the result row to read it.

Results: **Accepted**, **Reused** (already processed the same way), **Rejected** (see the problem report; nothing is
repaired or dropped), **Blocked** or **Unsupported**.

"Loaded" is not the same as "ready for research". Validation can pass with warnings, and each analysis checks its own
requirements (see the Workbench guide).

## Datasets and Storage

**1. Input.** Every prepared dataset in the Data Registry:

| Column | Meaning |
|---|---|
| Dataset | Its number in the registry |
| Instrument | Exchange and symbol |
| Timeframe | Daily, weekly, 5 minutes ... |
| Type | **Standardised** (loaded from a file) or **Derived** (built from daily data) |
| Bars, From, To | Number of bars and the date range |
| Validation | **Passed** or **Passed with warnings** |
| Storage | **Permanent** or **Temporary** |
| State | **Active**, **Superseded** (replaced by a newer processing of the same data) or **File deleted** |

Filter by timeframe; tick "Show superseded" or "Show deleted" to see those too. Click a row for the details: where it
is stored, processing version, settings fingerprint, original file name, validation warnings and its full **lineage**
back to the preserved original file.

**2. Output.** Where Permanent, Temporary and original data are kept, and the last run folder. Every action below runs
as a recorded run with a Run ID, a log and a manifest in `Q-MAP_OUTPUT/Data_Management`.

**3. Options.** Every action is checked first. You see what will happen, and why anything cannot happen, before
confirming.

| Action | What it does | Rules |
|---|---|---|
| **Move to Temporary** | Moves the dataset's file to `Q-MAP_DATA/Temporary/...` and updates the registry. (A dataset moved to Temporary by an earlier test version may still be in the old folder `Temporary_Data`; it is safe there, and its details explain how to relocate it.) | The data are copied and checked byte for byte (checksum) before the registry is switched; only then is the old copy removed. A file is never overwritten. |
| **Make Permanent** | Moves it back | Same safeguards |
| **Delete Temporary dataset...** | Deletes the data file of a **Temporary** dataset | Only Temporary datasets. Refused while other datasets were built from it. If research runs used it, you must confirm a second time. The registry record, lineage and audit trail are kept for ever. Cannot be undone. |
| **Derive selected timeframes** | Builds weekly, monthly, quarterly or yearly bars from a **daily** dataset | See below. Deriving the same thing twice reuses the existing dataset. |

Original source files (raw data) are always permanent. They are never moved, changed or deleted by any action.

**Temporary data never expire.** Only you delete them. Q-MAP never deletes anything automatically.

**Reason (recorded)** is stored with each move or deletion.

### Derived timeframes: the rules

| Field | Rule |
|---|---|
| Open | First session's open in the period |
| High | Highest high in the period |
| Low | Lowest low in the period |
| Close | Last session's close in the period |
| Volume | Sum. If any session's volume is empty, the period's volume is **empty** (never a partial sum). If the source has no volume, it is empty. |
| Periods | Calendar periods: ISO week (Monday-Sunday), month, quarter, year |
| Date of a bar | The **last trading day it contains**, so a weekly bar never appears before its week's data exist (no look-ahead) |
| Edge periods | The first and last periods may be incomplete because there is no trading calendar yet. They are flagged `period_may_be_incomplete` and shown as a validation warning. |

Only daily (1D) datasets with exactly one bar per date can be a source. Building daily bars from intraday data needs
trading-session rules that do not exist yet, so it is refused, with that reason.

## Command line (unchanged, optional)

`recover`, `verify` and `restore-raw` remain available (see the README). Both applications run recovery automatically
at the start of each run.

## Known limitations

- No trading calendar: incomplete days and periods are only flagged heuristically.
- No corporate-action adjustment.
- Loading a file whose dataset you deleted does not re-create it unless the profile gets a new `profile_version`
  (owner decision OD-3).
- New loads are always Permanent; move them afterwards (owner decision OD-6).
- Sources: folders only. Provider APIs and direct cloud connections are not built; scans run when you press the
  button (no schedule). Numbers with thousands separators (`22,393.60`) are not read automatically; use Data
  Management with a profile that declares them.
- Overlapping datasets with different values are reported, not resolved (owner decision DQ-1). Only files loaded
  through Sources are compared when they are loaded.
