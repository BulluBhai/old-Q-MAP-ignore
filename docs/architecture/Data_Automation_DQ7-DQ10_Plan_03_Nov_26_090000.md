# Q-MAP data automation (instruction DQ-7 to DQ-10): inspection, plan and design concerns

Prepared 03-Nov-26 on branch `claude/friendly-babbage-8xyrgo` (head `67fc095`, stacked on PR #9 → PR #4 → #3 → #2 → #1).
**Status: plan only. Nothing in this document is implemented yet.** Implementation starts after the decisions in
section 4 are answered.

Note on numbering: the instruction reuses DQ-7 to DQ-10, which the 02-Nov-26 findings report used for other questions.
The instruction's meanings supersede them: DQ-7 (3h approval) → general interval inference; DQ-8 (file-name option
default) → answered **ON**; DQ-9 (OW-25) → approved; DQ-10 (clean source files) → automatic duplicate/conflict handling.

## 1. What exists today (inspection)

| Area | Current state | Against the instruction |
|---|---|---|
| Ingestion paths | (a) Sources folder scan: `discovery.py` + `auto_interpret.py` (rules A-1..A-9) → generated profile → `ingest.py`. (b) Data Management screen with a chosen profile → `qmap_gui/jobs.py` → `ingest.py`. (c) CLI `qmap ingest` with a profile (`cli.py`). No CLI scan command | Reuse all three; the scan path is the automation path |
| Formats | CSV/TXT/TSV/DAT (any of `,` `;` tab `|`), XLSX, XLS, Parquet, detected from bytes | Already met |
| Timeframe | Inferred from the data (A-9: most common same-day step over **all** rows; daily/weekly/monthly from the median date gap), but only into a **fixed label list** `1m 5m 15m 30m 1h 4h 1D 1W 1M` (+ `3h` in commit `6f1e365`). File name is evidence; contradiction → question. Answers are checked against the measured step (D5-19). No exchange calendar is used anywhere | Partially met: no arbitrary intervals, no sampling, no mixed-interval classification, a question instead of default acceptance |
| Label list is used by | `profiles.ALLOWED_TIMEFRAMES` / `INTRADAY_MINUTES` (profile validation, process), `validation.py` (spacing and partial-session checks), `catalog.py` (labels, ordering, intraday set), three GUI filter lists, `derive.py` (1D source only), storage path `Cleaned_Data/<EXCH>/<SYMBOL>/<TF>/` | All must accept any `<n>m`, `<n>h`, `1D`, `1W`, `1M` value |
| Identity | Precedence (owner DQ-2): exchange/symbol **columns** > recorded answer > `EXCHANGE_SYMBOL` name > plain name (folder option, **off** by default) + suggestion. `CRYPTO_` prefix: venue asked. No alias registry. Symbols allow only `A-Z 0-9 . _ & -` (no spaces), because they are path segments (rule D2-19) | Partially met; alias registry, copy-suffix cleaning, default-on and "provisional identity instead of a question" missing |
| Duplicates within a file | `no_duplicate_timestamps` is an **ERROR**: the whole file is rejected (AKZOINDIA, OLAELEC, UJJIVAN) | Conflicts with DQ-10 (section 3, C-1) |
| Overlap across datasets | `overlap.py`, report-only (DQ-1), called **only** by the folder scan; it keys bars by timestamp in a dict, so it cannot see repeated timestamps | DQ-9: add to Data Management and CLI; must handle repeated timestamps |
| Default acceptance / reject / abort | Scan imports READY files without prompts. No Stop button during a scan. No way to "reject" an accepted interpretation after import except Datasets and Storage (Move to Temporary, then Delete) | Missing |
| Provenance | `ingest_events`, `ingest_attempts` (profile text, request, validation settings), `quality_checks`, `source_file_observations` (interpretation JSON with evidence), `source_answers`, run folders with manifests | Reuse; no parallel mechanism needed |
| Reference data | `Q-MAP_DATA/Reference_Files/` exists (created by the platform, unused) | Location for the alias registry |
| MIQP / QLOPB | **Not in the repository** (OD-2 still open) | Nothing to preserve or break |
| Tests | 987 (Linux, incl. 203 GUI); Windows + Ubuntu CI | Extend |

## 2. Proposed implementation (after the decisions in section 4)

Four independent parts; I propose four commits (or four sessions, per the standing instructions), in this order.

**P1. DQ-10 + DQ-9: duplicates, conflicts, overlap report** (`process.py`, `validation.py`, `overlap.py`,
`jobs.py`, `cli.py`, `catalog.py`, Datasets screen)
- Exact duplicate rows (every source field equal, including extra `x_` fields) are removed from the standardised copy;
  counts, source rows and file recorded as an INFO check `exact_duplicates_removed` on the attempt. Source never touched.
- Same timestamp, any differing field: all rows kept, flagged in `quality_flags`, WARNING `conflicting_observations`
  with timestamps, fields, both values (first N in the detail, all in the issues CSV). Dataset is "Passed with
  warnings" and usable (readiness: WARN, not FAIL).
- `overlap.py` rewritten to compare lists per timestamp (exact duplicates vs conflicts across datasets); called after
  every accepted ingest in Data Management and CLI as well as scans; a consolidated overlap report CSV per run.
- Analytical impact made visible (section 3, C-2).

**P2. DQ-7: timeframe inference by sampling** (`auto_interpret.py` → new `timeframe_infer.py`, `profiles.py`,
`validation.py`, `catalog.py`, GUI filters)
- First ~20 rows → candidate step; then N blocks of consecutive rows (table in the instruction, configurable in
  `qmap.toml` `[timeframe_sampling]`), positions from a seeded RNG (seed = hash of file SHA-256, so repeatable and
  explainable). Small files: blocks shrink to what exists.
- Dominant interval = most common same-day step; gaps that are whole multiples are "missing bars", overnight/multi-day
  gaps ignored; daily/weekly/monthly from date gaps (as today). Blocks disagree → "inconsistent/mixed" (C-4).
- Labels become open-ended: `<n>m` for minutes below 60 or not a whole hour (3m, 75m), `<n>h` for whole hours (2h,
  3h), `1D`, `1W`, `1M`. Validation spacing check reads minutes from the label. Commit `6f1e365` (3h) is superseded.
- File name and manual timeframe: cross-check only; a disagreement is a WARNING on the dataset, never a question,
  never an override. The current "recorded answer" for timeframe is replaced by "reject" (C-3).
- Recorded: inferred step, blocks, seed, share, outcome, file-name token and agreement, in the interpretation JSON and
  as an INFO check on the attempt.

**P3. DQ-8: file-name cleaning and alias registry** (new `instrument_names.py`, `auto_interpret.py`, reference CSV)
- Cleaning: strip extension; remove trailing ` (n)`, ` - Copy`, `_Copy`, ` - Copy (n)`, `copy of `, recognised
  download suffixes (`_download`, `(downloaded)`, date stamps only when separated), timeframe tokens (`_5min`, `, 15`),
  exchange/market prefixes (`NSE_`, `CRYPTO_`); collapse repeated separators; upper-case. Brackets that are part of a
  name (e.g. `M&M`, `BAJAJ-AUTO`, `L&T (PARTLY PAID)`) kept unless they match a copy pattern exactly.
- Registry `Q-MAP_DATA/Reference_Files/Instrument_Aliases.csv` (canonical, alias1, alias2, ...). A template is written
  only if absent; never overwritten. Validated on load: duplicate aliases, an alias used by two canonicals, empty
  canonical → listed errors; the conflicting entries are ignored (not the whole file).
- Matching on normalised keys (case, spaces, `_`, `-` folded). Clear match → canonical; no match → cleaned name kept
  as a **provisional** identity with a WARNING; ambiguous (two canonicals) → provisional + WARNING listing both.
- File name ON by default (folder option default flips; existing folders keep their saved setting unless C-6 says
  otherwise). Original file name is already preserved (`ingest_events.original_filename`).
- Consolidated "Identification exceptions" report per scan (CSV + Sources screen group), with a bulk "Add to alias
  registry" action that appends rows to the CSV (with a backup copy) for selected exceptions.

**P4. Default acceptance, reject and abort** (Sources screen, `discovery.py`, maybe schema 9)
- Scan: no questions for timeframe or identity any more (only genuinely unreadable layouts are rejected; date-layout
  and time-zone questions stay, see C-7). Results grouped: Imported / Imported with warnings / Rejected, with the
  detected timeframe, validation line ("Consistent across 15 sampled blocks") and identity method per file.
- **Stop scan** button: finishes the current file, stops before the next; recorded as `stopped` (C-5).
- **Reject** on a selected imported file (bulk selection allowed): records the user's rejection and takes the dataset
  out of use (C-5); the next scan does not re-import it unless the file or the user's correction changes.
- **Correct identity / exchange** (bulk): recorded override, re-processed on the next scan as a new version.

Tests (each part): the instruction's section 9 list, synthetic data, asserting stored rows, flags and warnings, not
only that code runs; plus a run of the owner's eight files (results in the report, not committed).

## 3. Design conflicts and concerns (need a decision before building)

| # | Conflict | Why it matters | My recommendation |
|---|---|---|---|
| C-1 | DQ-10 reverses an approved validation rule: `no_duplicate_timestamps` is an ERROR today (Stage 2 foundation), and the 02-Nov-26 report recommended rejection for AKZOINDIA/OLAELEC | With DQ-10, AKZOINDIA (428 identical pairs removed, 322 conflicting pairs kept), OLAELEC and UJJIVAN (all identical → clean) will import | Implement as instructed: exact duplicates removed; conflicts → WARNING. Applies to **all** ingest paths (scan, Data Management, CLI) so the rule is the same everywhere |
| C-2 | Conflicting rows in one dataset break assumptions of existing code: Dataset Summary computes bar-to-bar returns on consecutive rows (a 0-minute "return" between two copies); derived weekly/monthly bars require one bar per date; the overlap check keys by timestamp | The instruction forbids silently changing methodology | Keep calculations unchanged; readiness shows a WARN "N timestamps have conflicting observations; bar-to-bar statistics include both rows" and Dataset Summary adds a "Conflicting timestamps" column; derivation stays blocked for such datasets with that reason; overlap check fixed. Row order: by timestamp, then source row |
| C-3 | DQ-7 "manual timeframe must not override the data" vs the current timeframe question and recorded answers (and Data Management profiles that declare a timeframe) | Profiles with a fixed timeframe exist in the library | Scan: inferred value always used; "reject" stops the file. Data Management/CLI: a declared timeframe that disagrees with the measured one is rejected with the reason (today: warning) |
| C-4 | Mixed-interval files: "do not force a single timeframe", but every dataset needs one timeframe (storage path, filters, analyses) | | Do not import; report as "Mixed or inconsistent intervals" with the blocks' findings (a material exception, grouped in the report). Alternative: import under timeframe `mixed`, unusable by analyses until resolved |
| C-5 | "Reject" after default acceptance: datasets and the registry are append-only by design; deleting a Permanent dataset is not allowed (Temporary-only deletion) | | Schema migration 9: a `user_decisions` table (append-only) plus dataset status `rejected_by_user` (hidden from the Workbench, file kept, reversible). Alternative without schema change: move to Temporary and delete (irreversible) |
| C-6 | DQ-8 "file name is the primary source" vs owner decision DQ-2 / D5-15: explicit exchange/symbol **columns** are never overridden by a file name, and a contradiction is **rejected** | Both are owner decisions | Keep columns first (DQ-2); turn a contradiction into a WARNING with both values, using the column, instead of a rejection. Folder option ON for new folders and for existing ones |
| C-7 | Date-layout and market-time-zone questions remain (day-first vs month-first; naive times without a zone) | Guessing them silently corrupts data; the instruction lists "ambiguous column mappings" as warn-only, but a wrong date layout is not recoverable by a warning | Keep these two questions (they are per folder/layout, not per file: one answer covers every file with the same structure). Default zone `Asia/Kolkata` pre-filled for new folders |
| C-8 | Canonical names with spaces (`NIFTY 50`, `BANK NIFTY`): symbols are path segments and must not contain spaces (D2-19) | | Store the canonical name in `instruments.name`; symbol = canonical with spaces → `_` (`NIFTY_50`). No storage-rule change |
| C-9 | Exchange optional (section 8) vs `instruments.exchange NOT NULL` and the storage path `<EXCH>/<SYMBOL>` | | Equities without an exchange → `NSE` (default, recorded as "default"). Crypto → category value `CRYPTO` in the exchange field (recorded as "category, venue unknown"), editable later; no question. This replaces D5-18's venue question |
| C-10 | Sampling vs full checks: inference will sample, but validation (OHLC, spacing, duplicates) still reads every row, as it must for the stored data | Performance on million-row files is dominated by reading/validation, not inference | Accept; sampling limits only the inference. Measure on a synthetic 1-million-row file and report |
| C-11 | Existing datasets re-processed after these rule changes (fingerprint changes) | DQ-10 changes the standardised content for files with duplicates (new processing version); clean files keep their profile → reused (D5-16) | Accept: only previously rejected files and files whose identity changes produce new datasets |

## 4. Decisions requested from Sandeep (one line each)

1. C-1/C-2: proceed as recommended (conflicts kept, flagged, visible; calculations unchanged)?
2. C-4: mixed-interval files **not imported** (reported), or imported under `mixed`?
3. C-5: schema 9 with a reversible `rejected_by_user` status (recommended), or irreversible Temporary + Delete?
4. C-6: file-name/column contradiction becomes a warning (column wins), and the option is ON for existing folders too?
5. C-7: keep the date-layout and time-zone questions?
6. C-9: crypto without a venue stored under the category `CRYPTO`?
7. Work plan: four commits P1-P4 on this branch, opened as a PR stacked on PR #9 for review?
