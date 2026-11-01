# Q-MAP naming and reference conventions

A supporting standard to Blueprint v1.2. It is **not** part of the Blueprint, and nothing here changes it. Prepared
01-Nov-26 on PR #4 (branch `claude/adoring-curie-5h2mx4`).

## Approval status at a glance

| Section | Convention | Status |
|---|---|---|
| A | Reference IDs (`TC`, `OBV`, `RQT`, `DCN`, `CR`, `TR`), separate module field, timeframe reference `TF_1m` vs application value `1m`, Excel master register, Markdown handoff | **Agreed** (stated by the Project Owner in the enhancement requirements, 01-Nov-26) |
| B | File-format codes `C`/`T`/`E`/`P`; time-representation codes `ISO`/`UNI`/`STD`; date-order codes `DMY`/`YMD` | **Proposed, not approved.** Not used in any Q-MAP name. |
| C | Source-profile naming standard (IDs, file names, display names, statuses, legacy names) | **Introduced in PR #4, awaiting the Project Owner's approval** |
| D | Abbreviation glossary | Each entry has its own status |

---

## A. Reference IDs and register conventions (agreed)

| Record category | Prefix | Example |
|---|---|---|
| Test Case | `TC` | `TC-001` |
| Observation | `OBV` | `OBV-001` |
| Requirement | `RQT` | `RQT-001` |
| Decision | `DCN` | `DCN-001` |
| Change Request | `CR` | `CR-001` |
| Test Result | `TR` | `TR-001` |

- **Independent numbering:** each category has its own sequence; `TC-001` and `OBV-001` are different records.
- **No reuse:** an ID is never reused, even after its record is resolved or closed.
- **Separate fields:** the module is a separate field (Reference ID `OBV-001`, Module `Data Management`). It is never
  part of the ID.
- **Timeframe references:** the reference `TF_1m` and the application value `1m` are separate fields.
  - Q-MAP's code and data store only the application value: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1D`, `1W`, `1M`,
    `1Q`, `1Y`.
  - `TF_<value>` (for example `TF_1D`) is used only in testing and development records to refer to that value.
  - Q-MAP never writes `TF_...` into data, profiles or the registry.
- **Formats:** Excel is the primary master testing register; Markdown is used for development handoffs, requirements
  and instructions.

**How the repository's existing record numbers relate.** The repository's decision log and work register predate this
scheme and use their own series:
- `D2-xx`, `D3-xx` and `D4-xx` decisions;
- `OD-x` owner decisions;
- `OW-x` open work.

They are kept unchanged, because commits, pull requests and earlier reports cite them. New repository entries
continue those series until the Project Owner decides otherwise.

**Decision needed (one numbering authority):** issuing `DCN-` numbers from the repository could collide with numbers
already used in the Excel master register. **Recommendation:** the Excel register stays the single issuer of
`TC`/`OBV`/`RQT`/`DCN`/`CR`/`TR` numbers. Repository entries quote those numbers when a register record exists.

## B. File-format, time-representation and date-order codes (PROPOSED, not approved)

These codes were discussed but not formally finalised. They are recorded here, with their meanings, so that the
proposal is not lost. **No Q-MAP profile, file name, ID or parsing rule uses them.**

| Kind | Code | Intended meaning | Illustration |
|---|---|---|---|
| File format | `C` | CSV | |
| File format | `T` | Text | |
| File format | `E` | Excel | |
| File format | `P` | Parquet | |
| Time representation | `ISO` | ISO-formatted date/time | `2026-10-30`, `2026-10-30T09:15:00` |
| Time representation | `UNI` | Unix timestamp | `1793262840` |
| Time representation | `STD` | Standard human-readable date/time | `30-10-26`, `30-10-26 09:15:00` |
| Date order | `DMY` | Day–Month–Year | `30-10-2026` |
| Date order | `YMD` | Year–Month–Day | `2026-10-30` |

Notes:
- `STD` does not specify a date order, separator or time component.
- The lists are not exhaustive.
- File format, time representation, date order, time component, time zone and market-data timeframe are **separate
  properties**. For example, a CSV can hold ISO dates or Unix timestamps. A Unix timestamp has no human-readable date
  order, but its time zone still matters when converting it to a market date.

**Recommendation, if the owner wants these finalised:**
- Use them only as register or test-case attributes, one column per property; never combine them into one identifier.
- Define `STD` more narrowly, or replace it with explicit patterns (for example `DD-MM-YY`).
- Keep profile IDs on the descriptive tokens in section C.

## C. Source-profile naming standard (introduced in PR #4, awaiting approval)

### C.1 Fields of a profile and what each is for

| Field | Purpose | Rule |
|---|---|---|
| File name | Where the profile lives | Exactly `<profile_id>.toml` (Q-MAP finds a profile by this name) |
| `profile_id` | Unique internal identifier, stored with every load and in each dataset's processing version | Lower-case tokens joined by `_`: `<format>_<structure>_<datetime>[_<qualifier>...]` |
| `display_name` | What people see in the profile list | `<Structure> <FORMAT>: <date column> (<date/time form>), <other columns in file order>[ - <fixed timeframe>]` |
| `source_label` | Short label recorded with each received file when you leave "Where it came from" empty | `<FORMAT>, <headered/headerless>, <date/time form>[, <qualifier>]` |
| `description` | Full explanation: structure, date/time rule, time zone, volume handling, who supplies exchange, symbol and timeframe | Plain sentences; examples begin with `EXAMPLE` and name their standard counterpart |
| `status` | What the profile is for (section C.3) | `standard`, `example`, `template`, `legacy` or `custom` |
| `legacy_ids` | Earlier names of this same layout, still recognised | Each earlier name belongs to exactly one profile |
| `profile_version` | Version of the reading rules | Raise it whenever an already-used profile changes |

The fields identify the same profile but deliberately differ in wording. For example:

| Field | Value |
|---|---|
| ID | `csv_hdr_ddmmyy` |
| Display name | "Headered CSV: time (DD-MM-YY), open, high, low, close, Volume, Net Volume" |

### C.2 ID tokens (approved for profile names when this standard is approved)

| Position | Token | Meaning |
|---|---|---|
| format | `csv` | Comma-separated values file |
| format | `txt` | Delimited text file (.txt, or .csv text read by the text rules) |
| format | `xlsx` | Excel workbook (Office Open XML) |
| format | `parquet` | Apache Parquet file |
| structure | `hdr` | First row holds column names (Parquet: named columns); columns are found by name |
| structure | `nohdr` | No header row; columns are found by position (0, 1, 2 ...) |
| date/time | `ddmmyy` | Human-readable date `DD-MM-YY`, day first, two-digit year |
| date/time | `isodate` | ISO 8601 date `YYYY-MM-DD` |
| date/time | `isodt` | ISO 8601 date-time with a UTC offset, e.g. `2026-10-23T09:20:00+05:30` |
| date/time | `unixs` | Unix timestamp in seconds |
| date/time | `xldate` | Native Excel date cells |
| date/time | `naivedt` | Date-time values stored without a time zone (the profile declares the zone) |
| qualifier | `dupvol` | A second volume column must be identical to the first |
| qualifier | `idfromname` | Exchange and symbol are read from the file name (all other profiles: you type them) |

Rules:
- A new token is added only when no existing token describes the behaviour.
- One concept has one token.
- Volume and Net Volume handling is stated in the display name and description, not in the ID.

### C.3 Statuses

| Status | Meaning | Shown as | In the library now |
|---|---|---|---|
| `standard` | Recommended for routine use. Its reading rules were verified against representative files. | Standard | 11 |
| `example` | For learning and testing. It names the standard profile to use instead. | Example | 3 |
| `template` | A starting point to copy and adapt; not usable as it is | Template | none (any profile can be copied with "New profile from this one") |
| `legacy` | Kept only for compatibility | Legacy | none (earlier names are aliases, see C.5) |
| `custom` | Your own profile (in your settings folder); also the default when a profile states no status | My profile | |

Your own copies are always shown as "My profile", whatever their file says. Copying a library profile sets its status
to `custom`, removes the library's earlier names, and marks the display name "My copy: …".

### C.4 Inventory: the library before and after (reading rules unchanged)

| New ID (file) | Status | Display name | Earlier names (still recognised) | Verified against |
|---|---|---|---|---|
| `csv_hdr_ddmmyy` | Standard | Headered CSV: time (DD-MM-YY), open, high, low, close, Volume, Net Volume | `csv_headers_dd_mm_yy` | sample file 2 |
| `csv_hdr_isodt` | Standard | Headered CSV: time (ISO date-time with UTC offset), … Net Volume | `csv_headers_iso_offset` | sample file 9 |
| `csv_hdr_unixs` | Standard | Headered CSV: time (Unix seconds), … Net Volume | `csv_headers_unix_seconds` | sample file 3 |
| `csv_nohdr_isodt` | Standard | Headerless CSV: time (ISO date-time with UTC offset), … Net Volume | `example_csv_noheaders_iso_offset`, `csv_noheaders_iso_offset` | sample file 4 |
| `csv_nohdr_unixs` | Standard | Headerless CSV: time (Unix seconds), … Net Volume | `example_csv_noheaders_unix_seconds`, `csv_noheaders_unix_seconds` | sample file 5 |
| `txt_hdr_isodate` | Standard | Headered TXT: date (YYYY-MM-DD), open, high, low, close, Volume - daily | `example_text_headered_iso_date` | sample file 7 |
| `txt_nohdr_isodate_dupvol` | Standard | Headerless TXT: date (YYYY-MM-DD), open, high, low, close, Volume, Volume copy - daily | `example_text_headerless_seven_columns` | sample file 8 |
| `xlsx_hdr_isodt` | Standard | Headered XLSX: time (ISO date-time with UTC offset), … Net Volume | `example_xlsx_headers_iso_offset`, `xlsx_headers_iso_offset` | sample file 1 |
| `xlsx_nohdr_isodt` | Standard | Headerless XLSX: time (ISO date-time with UTC offset), … Net Volume | `example_xlsx_noheaders_iso_offset`, `xlsx_noheaders_iso_offset` | sample file 11 |
| `xlsx_hdr_xldate` | Standard | Headered XLSX: time (Excel date cells), … Net Volume | `example_xlsx_headers_native_date`, `xlsx_headers_native_date` | sample file 10 |
| `parquet_hdr_naivedt` | Standard | Parquet: Date (date-time, no time zone), Open, High, Low, Close, Volume - 1-minute | `example_parquet_naive_timestamp` | sample file 6 (interpretation; that file is rejected for data defects) |
| `csv_hdr_ddmmyy_idfromname` | Example | Example - Headered CSV: time (DD-MM-YY), …; exchange and symbol from the file name - daily | `example_csv_dd_mm_yy` | as `csv_hdr_ddmmyy` |
| `csv_hdr_isodt_idfromname` | Example | Example - Headered CSV: time (ISO date-time with UTC offset), …; exchange and symbol from the file name | `example_csv_iso_offset` | as `csv_hdr_isodt` |
| `csv_hdr_unixs_idfromname` | Example | Example - Headered CSV: time (Unix seconds), …; exchange and symbol from the file name | `example_csv_unix_seconds` | as `csv_hdr_unixs` |

"Sample file N" refers to `docs/sample_file_testing`, where each of these layouts was verified row by row in PR #3.

**Problems found in the old library, and how each was fixed:**

| Problem | Fix |
|---|---|
| Every profile was called `example_…`, including those fit for routine use | Status field: 11 Standard, 3 Example |
| The same concept was spelled differently: `headers`, `headered`, `noheaders`, `headerless`, `seven_columns` | One token per concept (C.2) |
| The three headered-CSV examples read the exchange and symbol from the file name, which the owner's file names do not contain (sample-file finding A) | The verified "you type them" versions became the Standard profiles; the file-name versions are kept as Examples |
| The verified copy for Unix-seconds CSV described its columns by position although it has a header row | Corrected description |
| The list showed only technical names | The list now shows the display name, status and ID |

**Where profile names were referenced:**
- **Application code:** none.
- **Tests:** 82 references, all updated to the profile with the same reading rules.
- **Documents:** README and test report updated.
- **Historical evidence files in `docs/sample_file_testing/`:** deliberately unchanged. They record what was run at
  the time.
- **Persistent data:** a profile's name is stored in the registry (profile snapshot, each load attempt, each dataset's
  processing version) and in each cleaned file's metadata. See C.5.

**Reading behaviour.** Every new profile reads files exactly like the profile it replaces:
- the same file settings, columns, date rule, time zones, volume rule and instrument source;
- checked automatically for all 19 earlier names (`Tests/integration/test_profile_library.py`).

### C.5 Compatibility and migration

- **Old names keep working.** Asking for a profile by an earlier name finds the profile that now carries it (for
  example, a command line with `--profile example_csv_unix_seconds` uses `csv_hdr_unixs_idfromname`).
- **Existing datasets are not touched.** They stay valid and readable, and their records keep the name they were made
  with. Historical records are not rewritten.
- **Loading the same file again under a new name** is treated as new processing, because the profile name is part of
  the processing version (approved rule D2-08). The new dataset becomes active; the earlier one is kept, superseded,
  never deleted. The data are identical (tested). This affects only databases created while testing PR #4, which is
  not merged.
- **Your own profiles** (in your settings folder) keep their names. A name used by the library, or listed as one of
  its earlier names, cannot be saved as your own.
- **Not done:** treating an earlier name as the same processing identity. That would change the approved reuse rule
  (D2-32), so it is left as an owner decision, if ever wanted.

### C.6 Adding a profile in future

1. Check that no existing profile already reads the layout. Same reading rules means use the existing profile.
2. Build the ID from the C.2 tokens; the file name is `<id>.toml`. Add a new token only if none fits, and record it in
   C.2.
3. Write the display name (C.1 pattern) and a description covering:
   - structure;
   - date/time rule and two-digit years;
   - time zone;
   - volume and Net Volume;
   - who supplies exchange, symbol and timeframe.
4. Set `status`:
   - `standard` only after the rules are verified against representative real files;
   - otherwise `example` or `template`.
5. If the profile replaces an earlier one with the same rules, list the earlier name in `legacy_ids`.
6. Run the tests. `test_profile_library.py` checks the ID pattern, display name, status and earlier names.
7. Never change the rules of a used profile without raising `profile_version`.

## D. Abbreviation glossary

| Term | Meaning in Q-MAP | Status |
|---|---|---|
| CSV | Comma-separated values file | Approved (established usage) |
| TXT | Delimited text file | Approved with section C |
| XLSX | Excel workbook (.xlsx). Old `.xls` files are read only if the optional `xlrd` package is installed | Approved (established usage) |
| Parquet | Apache Parquet columnar file | Approved (established usage) |
| Headered / Headerless | First row holds column names / does not (columns by position) | Approved with section C |
| OHLC / OHLCV | Open, High, Low, Close (/ and Volume) bar values | Approved (Blueprint glossary) |
| Volume | Traded quantity used as Q-MAP's volume | Approved |
| Net Volume | A separate signed volume measure supplied by some sources. Kept as an extra column (`x_net_volume`), never merged with or used as Volume | Approved (decision D2-13) |
| ISO date / ISO date-time | ISO 8601 `YYYY-MM-DD` / `YYYY-MM-DDTHH:MM:SS±HH:MM` | Approved |
| Unix timestamp | Seconds (or milliseconds, stated explicitly) since 1970-01-01 UTC | Approved |
| DD-MM-YY | Human-readable date, day first, two-digit year | Approved |
| Two-digit years | 00-68 mean 2000-2068; 69-99 mean 1969-1999 (Workbench dates and profiles with `two_digit_year_pivot = 69`) | Approved behaviour (documented and tested) |
| UTC offset | `+05:30` etc. inside an ISO date-time | Approved |
| Timeframe values | `1m 5m 15m 30m 1h 4h 1D 1W 1M 1Q 1Y` | Approved (application values) |
| `TF_<value>` | Timeframe reference in testing and development records only | Agreed (section A) |
| DMY / YMD, ISO / UNI / STD, C / T / E / P | Date-order, time-representation and file-format codes | **Proposed only** (section B) |
