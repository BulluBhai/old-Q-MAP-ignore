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

Added 02-Nov-26 (Blueprint v1.3 §8.5); made automatic by default on 03-Nov-26 (owner instruction DQ-7 to DQ-10). You do
not choose profiles, type layouts or confirm files one by one. Routine files are **accepted automatically**; anything
material is listed once, grouped, in **Exceptions**, where you can reject, restore or correct many files at once.

1. **Input - folders.** Press **Add folder...** and choose the folder with your files (any folder on this computer,
   including a synchronised OneDrive or Google Drive folder; files must be downloaded, not "online only"). The first
   time, the folder window opens at the folder Q-MAP is running from (the folder that holds `database_manager.py`);
   after that it opens at the folder you chose last, also after Q-MAP is restarted (added 09-Nov-26). Settings:
   - **Market time zone**: leave empty for Indian data. Timestamps without a time zone are then read as Asia/Kolkata
     (the default), and the files are listed under "Time zone assumed" so you can see it. Timestamps with their own
     offset (`+05:30`) and Unix times are read as they are.
   - **Default exchange**: leave empty for NSE (the default). Cryptocurrency files (`CRYPTO_...`) are never NSE: they
     are stored under the category CRYPTO with the trading venue unknown, which you can correct.
   - **Identify the instrument from the file name**: ON by default, for new and existing folders. `RELIANCE.csv`,
     `RELIANCE (1).csv`, `RELIANCE - Copy.csv` and `RELIANCE_Copy.csv` are all RELIANCE. Switch it off only if a
     folder's file names say nothing about the instrument; Q-MAP then asks for the symbol.
   - **Include sub-folders** and **Skip files matching** (for example `*backup*`).
   - A scan always uses the folder's **saved** settings (the ones shown in the folder list). If you change a setting
     and press **SCAN SELECTED FOLDER NOW** without **Save settings of selected folder**, Q-MAP shows the window
     **Folder settings not saved** with each difference. **Yes** saves your changes and scans with them; **No** scans
     with the saved settings and puts the boxes back to them (added 09-Nov-26). When **Include sub-folders** is off
     and the folder has sub-folders, the scan result says how many were not scanned. The first line of
     `Scan_Report_...csv` records whether sub-folders were included and the skip patterns used.
2. **Output - files.** Each file is listed with its result, **detected timeframe**, **instrument** (and how it was
   found: registry, alias, file name, provisional), change and datasets. Select a file to see, for example:

       Detected timeframe: 5 minutes
       Validation: Consistent across 15 sampled blocks (470 of 20000 rows examined)
       Status: Accepted by default

   followed by every warning. Under **Checks of the whole file** are the warnings found when every row of the file
   was checked, for example `WARNING: Some days have fewer bars than usual` or `WARNING: Part of the file may have
   another bar interval`, each with its detail (shown here since 09-Nov-26; the Analytical Workbench readiness check
   shows the same warnings). Below the list, **Exceptions found** groups everything that needs your attention:
   files not loaded (data errors), mixed bar intervals, a file name whose timeframe differs from the data, conflicting
   observations, bars that differ from another dataset, names not in the alias registry, ambiguous names, file name
   and file columns that disagree, crypto venue unknown, assumed day-first dates, assumed time zone, and files you
   rejected. Each scan also writes, in its run folder in `Q-MAP_OUTPUT/Data_Management`: `Scan_Report_...csv`,
   `Identification_Exceptions_...csv` and, when there are overlaps, `Overlap_Report_...csv`.
3. **Options - scan, review and correct.**
   - **SCAN SELECTED FOLDER NOW**; **Stop scan** stops safely: the file being read is finished, the rest is listed as
     "not processed" in the scan report, and everything already done is kept. Scan again to continue.
   - Select one or more files (Ctrl+click, Shift+click), then:
     - **Reject selected**: the data are kept unchanged but no longer offered to analyses. It is recorded with your
       reason and is **reversible**: **Restore selected** undoes it. Nothing is ever deleted.
     - **Save answer / correction**: correct the exchange, symbol, date layout or time zone of the selected files. The
       next scan registers the corrected data as new datasets; the earlier ones stay (reject them if you wish).
     - **Add selected names to alias registry**: type the canonical name (for example `RELIANCE`) and press the
       button; the selected files' cleaned names become its aliases. A backup of the registry is kept. The next scan
       identifies these files, and future files with these names, again.

**How Q-MAP reads a file automatically** (details: `docs/architecture/Blueprint_v1.3_Implementation_Audit.md`,
section 6, and `docs/acceptance_testing/Q-MAP_DQ7-DQ10_Implementation_Report_03_Nov_26_120000.md`):

- **Timeframe** is measured from the time stamps, never taken from a list, the file name or a typed value. Q-MAP
  looks at the first rows, then at blocks of rows spread over the whole file (20 blocks for 1-minute data ... 5 for
  daily), chosen the same way every time. Missing bars, nights, weekends and holidays do not change the interval; no
  exchange calendar is used. Any interval works (3 minutes, 75 minutes, 2 hours, 3 hours ...). If different parts of a
  file have different intervals, the file is kept as one dataset with timeframe **MIXED** and listed; analyses that
  need one interval say they cannot use it. A file-name timeframe that disagrees is reported; the data win.
- **Instrument**: an `exchange` / `symbol` column in the file comes first (never overridden by the file name; a
  disagreement is listed with both values). Otherwise the cleaned file name is matched against the **alias
  registry** `Q-MAP_DATA/Reference_Files/Instrument_Aliases.csv` (first column the canonical name, then its aliases;
  edit it with Excel or Notepad). No match: the cleaned name is used as a **provisional** instrument and listed.
  A bare number stays part of the name (`NIFTY 50`, `NIFTY_50`); `(1)`, `- Copy`, `_download` and dates are removed.
- **Dates**: when a date could be day-first or month-first, day-first is used (the Indian default) and listed; you
  can choose the other layout for the file. Two-digit years: 00-68 = 2000-2068, 69-99 = 1969-1999.
- **Repeated rows**: rows identical in every column are kept once (the copies are counted in the problem report;
  your file is not changed). Rows with the same time stamp but different values are **all kept**, flagged and listed
  as conflicting observations; Q-MAP never chooses between them, and you can still analyse the data.
- **Overlaps** with data already loaded (same instrument and timeframe) are reported, never merged or overwritten.
- Files whose contents have not changed since the last scan are skipped. Q-MAP compares the file's checksum on every
  scan, so an edited file is always read again, even if its size and date did not change. Scanning twice never
  creates duplicates; the same content under two names is loaded once.
- If a folder inside the source cannot be read (for example, access is denied) and **Include sub-folders** is ticked,
  the scan does not stop: the files it can read are processed, and the message under Progress / Status turns red and
  includes **Scan INCOMPLETE:**, naming the folder. Files last seen in that folder show as *Failed* ("Not checked: the
  folder ... could not be read"), never as *No longer in the folder*, and their data are unchanged. Fix the folder's
  access and scan again.
- Shortcuts and links inside the folder (symbolic links, Windows junctions) are never followed. They are listed in
  the scan report as "Link not followed". Copy the files into the folder if they should be scanned.
- Nothing in your folder is ever created, changed, moved or deleted.

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
