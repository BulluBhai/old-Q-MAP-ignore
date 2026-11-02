# Blueprint v1.3 implementation audit and migration proposal

Prepared 02-Nov-26 on branch `claude/happy-brahmagupta-su6tnr` (stacked on PR #4). Reference: `Q-MAP_Master_Blueprint_v1.3.md`
on `main` (merged by PR #8, merge commit `f5129d2`). Blueprint §16.2 and §19.4 require that differences are recorded
as findings first. Section 9 records what this branch then implemented.

**Evidence labels used below.** *Inspected* = read in the source on 02-Nov-26. *Tested here* = a test was run in this
session (Linux container, Python 3.12, Tk 8.6 under Xvfb). *Reported* = stated in an earlier PR or report and not
re-verified here.

---

## 1. Repository and pull-request state (inspected 02-Nov-26)

| Item | Finding |
|---|---|
| `main` | Documentation only: `README.md`, Blueprint v1.0 (in `docs/`), Blueprint v1.3 (`.md` and `.html`, root), the standing instructions and `CLAUDE.md`. **No application code.** |
| Application code | Only on the stacked, open, unmerged PRs: #1 `claude/keen-carson-x872ge` (base `main`) → #2 `claude/gui-data-management` → #3 `claude/qmap-audit-miqp-plan-547lid` → #4 `claude/adoring-curie-5h2mx4` (head `417552f`, unchanged since the assignment). |
| PR #5 | Open, documentation only (Blueprint v1.2 and handover). v1.3 now supersedes v1.2 where they differ. |
| PR #8 | GitHub's list view shows `merged: false, state: closed`, but `main` contains merge commit `f5129d2` ("Merge pull request #8") with both Blueprint files. The files are on `main`; the API flag is noted, not relied on. |
| Blueprint copies | The `.md` and `.html` copies are identical in content: the HTML is the Markdown text inside one `<pre>` block, and after HTML-unescaping the two texts match character for character (checked 02-Nov-26). One internal inconsistency in v1.3 itself: §"Version authority" still says "Version 1.2 is the primary reference for new development" in its second paragraph, while the first paragraph and the header make v1.3 authoritative. Treated as an editorial leftover; flagged for the owner (DQ-6). |
| Baseline tests at PR #4 head + `main` merged | **Tested here:** 842 passed, 0 skipped, 0 failed (all 195 GUI tests ran). Without Tk: 734 passed, 82 skipped. CI on Windows and Ubuntu for `417552f`: *reported* green in PR #4. |

### Branch and PR strategy

- This work continues **on top of PR #4**, not on `main`: `main` has no code, and re-basing the four open PRs would
  rewrite reviewed history. The designated branch `claude/happy-brahmagupta-su6tnr` was reset to PR #4's head (it held
  only `main`'s history, so nothing was lost) and `origin/main` was merged in, so the branch carries Blueprint v1.3 and
  the standing instructions.
- A new PR is opened from this branch **into `claude/adoring-curie-5h2mx4`** (PR #4's branch), making it the fifth PR in
  the stack. PR #4's commits, acceptance evidence and review history are untouched. No base branch of an existing PR
  was changed, nothing was force-pushed and nothing is merged.
- Merge order, when the owner approves: #1 → #2 → #3 → #4 → this PR. The `main` merge inside this branch contains only
  files already on `main`, so it cannot conflict when the stack reaches `main`.

## 2. Current architecture (inspected)

PR #4 already delivers the two-module, two-GUI design that v1.3 retains (§4.4): `database_manager.py` and
`analytical_workbench.py` launch one shared platform (`Application/qmap`, no GUI code) through `Application/qmap_gui`.
The data path is: original file → content-addressed, read-only copy in `Q-MAP_DATA/Raw_Data` → profile-driven reading,
parsing and validation → canonical Parquet in `Cleaned_Data` (or `Temporary/`) → SQLite registry
(`Metadata/qmap_metadata.sqlite`, schema 7, append-only audit tables and immutability triggers) → per-analysis readiness
check in `qmap/catalog.py` → analysis runs with Run IDs and output folders in `Q-MAP_OUTPUT`.

The main gap against v1.3 is the **operating model of ingestion**. v1.2 accepted explicit source profiles chosen by the
user. v1.3 §8.5.1 and §8.5.8 require automatic discovery and interpretation wherever unambiguous, with "routine
source-profile selection ... not required". In PR #4 every load needs a profile and typed exchange, symbol and
timeframe, and there is no concept of a source folder.

## 3. Requirement-to-implementation matrix

Status key: **IV** implemented and verified · **IU** implemented, verification incomplete · **P** partial · **N** not
implemented · **C** conflicting · **NA** not applicable at this stage. "Before" is PR #4; "After" is this branch.

| # | v1.3 ref | Requirement (business outcome) | Where (files) | Tests | Before | After | Remaining gap / acceptance |
|---|---|---|---|---|---|---|---|
| R1 | §4.3-4.4 | Two modules, two GUIs, two entry points; engines GUI-free | entry points, `qmap_gui/app.py` | `test_architecture.py`, `test_two_applications.py` | IV | IV | Owner Windows/IDLE acceptance (OW-01) |
| R2 | §4.4 | Readiness handshake per analysis (registered, file present, checksum, timeframe, columns, coverage, quality visible) | `catalog.check_readiness` | `test_catalog_and_analysis.py`, `test_workbench_dates_and_runs.py` | IV | IV | — |
| R3 | §5.10, §8.5.2, §8.5.6 | Configure source folders and discover supported files | — | — | **N** | IV | Sources screen (new); scheduled scanning deliberately not built |
| R4 | §8.5.1, §8.5.4 | Interpret unambiguous files automatically, without profile selection | `profiles.py` (manual) | — | **C** (profile required) | IV | Rules A-1…A-9 (section 6); owner confirmation of rule choices DQ-2 |
| R5 | §8.5.4 | Ambiguity → ask or reject; never guess dates, zones, columns, identity | `datetime_parse.py` (strict per profile) | `test_datetime_parse.py` | P (strict, but the *user* resolved it by choosing a profile) | IV | — |
| R6 | §8.5.4 | Record user confirmations; reuse only for a compatible structure | — | — | N | IV | Answers keyed by structure signature |
| R7 | §8.5.4 | Headerless positional reading only under documented rules shown in the record | profiles with positions | `test_sample_layouts.py` | P | IV | Rule A-5 |
| R8 | §8.5.4 | Canonical OHLCV; extra fields kept with meaning and provenance; unknown fields reported | `canonical.py`, `parquet_io.py` (`x_` columns) | `test_ingest_formats.py`, `test_volume.py` | IV | IV | Extra columns are preserved but not yet *typed* (e.g. open interest as number) |
| R9 | §8.5.5, §8.4 | Validation: fields, numbers, timestamps, duplicates, chronology, OHLC, negatives, gaps, timeframe consistency | `validation.py`, `process.py` | `test_validation.py`, `test_sample_file_findings.py` | IV | IV | Exchange calendar (OD-5), corporate actions (OW-05) |
| R10 | §8.5.5 | Hard failures vs warnings vs info; hard failures never research-ready | `results.py`, `ingest.py` | many | IV | IV | — |
| R11 | §8.5.6, §8.3 | Repeated scans idempotent; changed files detected; overlaps and conflicts reported; no blind append | content reuse in `ingest.py` | `test_ingest_versioning.py` | P (same content never duplicates; no folder state; overlaps across files not reported) | IV for detection and reporting | **Resolution policy** for conflicting overlaps is an owner decision (DQ-1) |
| R12 | §8.5.6 | User sees discovered / imported / skipped / rejected and why | — | — | N | IV | — |
| R13 | §5.10, §8.5.10 | Originals never modified | `storage/registry.py`, `files.py` | `test_raw_integrity.py`; sample checksums before/after (*reported*) | IV | IV | Re-checked for scans (new test) |
| R14 | §8.3 | Permanent/Temporary, user-controlled, no expiry, dependency checks on move/delete | `storage_class.py`, schema 5-7 | `test_storage_class.py`, `test_storage_integrity.py` | IV | IV | OD-3 |
| R15 | §8.3, §8.5.9 | Parquet storage; SQLite registry; DuckDB query engine | `parquet_io.py`, `storage/db.py` | yes | P (no DuckDB) | P | DuckDB when a module queries across datasets (OW-03). Not needed by any current analysis. |
| R16 | §8.2, change summary | Weekly/monthly/quarterly/yearly derived from daily with defined rules; no look-ahead | `derive.py` | `test_derive.py` (hand-computed expectations, *inspected*) | IV | IV | Daily-from-intraday blocked by OD-5 |
| R17 | §8.5.8 | Registry exposes source, identity, instrument, timeframe, coverage, fields, times, status, warnings, fingerprint, storage ref, provenance | `catalog.py`, schema | yes | P (no "source" concept) | IV | — |
| R18 | §5.11 | Workbench: readiness, run records, explanations, no ingestion | `analytical_engine`, `qmap_gui/analysis.py` | yes | IV | IV | — |
| R19 | §5.11, §14 | MIQP and QLOPB in the Workbench | — | — | **N** (no source in repo) | N | **Blocked: OD-2** (QLOPB code, MIQP specs not supplied) |
| R20 | §9.1 | Code, data and outputs separate; configurable locations | `core/config.py` | `test_config.py` | IV | IV | Folder names OD-10 |
| R21 | §9.2 | Unique Run ID, separate output folder, no overwrite | `core/runs.py` | `test_runs.py` | IV | IV | — |
| R22 | §13 | Deterministic, no look-ahead, versioned methods, no silent data changes | throughout | yes | IV | IV | — |
| R23 | §13.1 | Result reuse for equivalent runs | — | — | N | N | OW-15 |
| R24 | §5.9 | Research Library (statuses per v1.3) | `research_records` (unused, old statuses) | — | N | N | OW-08, OW-14 |
| R25 | §7.3 | Feature Store | — | — | N | N | OW-12, with the first module that needs it |
| R26 | §8.5.2, §8.5.7 | Provider API adapters (target five), same pipeline, credentials safe | — | — | N | N | **Not started in this session** (section 8); recommended as its own session |
| R27 | §8.5.7 | Synchronised cloud folders treated as folders | — | — | N | IU | A OneDrive/Google Drive folder is just a folder to Q-MAP; placeholder files that are not downloaded fail to read and are reported. Not tested against a real sync client. |
| R28 | §8.4 | Instrument changes, symbol mapping | — | — | N | N | Owner scope decision (market universe) |
| R29 | §5.10 | Coverage view by instrument × timeframe × date range | per-dataset coverage | — | P | P | OW-16 |
| R30 | §15.1 | Workbench not presented as ready for routine research until readiness is reliable | module catalogue | `test_logic_modules_env_store.py` | IV | IV | — |

## 4. Quantitative integrity audit (existing calculations)

| Calculation | Inputs → outputs | Method | Time alignment / look-ahead | Survivorship, adjustments | Independent check |
|---|---|---|---|---|---|
| Standardisation (`process.py`) | source rows → canonical bars | values kept as read; sort by timestamp, rows flagged when moved; nothing repaired | session date from the exchange time zone for instants; date-only stays a date | none; corporate actions not handled (OW-05) | row-by-row against the owner's 11 files (*reported*, PR #3) |
| Derived timeframes (`derive.py`, method v1) | daily → W/M/Q/Y | open = first, high = max, low = min, close = last, volume = sum (empty if any missing), period by calendar boundary, incomplete last period flagged | uses only bars inside each period; no forward fill | inherits source adjustment status | `test_derive.py` uses hand-computed values (*inspected*) |
| Dataset Summary (`dataset_summary`, v1) | canonical bars → descriptive statistics | returns = close / previous close − 1; sample std (n − 1) | each return uses only its own and the previous bar | descriptive only | **This branch:** end-to-end test recomputes every figure independently from the original CSV text (section 9) |

No defect was found that changes a result. Two limitations stay visible: (1) a later file that overlaps an earlier
dataset with different values produced two active datasets with no notice. This branch now reports it (R11), but
**which one is "right" is not decided by Q-MAP**. (2) No corporate-action adjustment status is recorded, so adjusted
and unadjusted series from different sources cannot be told apart automatically (OW-05).

## 5. What is preserved, corrected, missing

- **Preserved unchanged:** all 7 schema migrations (checksum-pinned), every profile and its reading rules, reuse and
  retry rules (D2-32, D2-33), validation, storage classes, recovery, both GUIs and every existing screen. Manual
  profile loading remains available for unusual files and as a compatibility path.
- **Corrected / extended:** ingestion gains automatic interpretation and folder sources, built *on* the existing
  pipeline. An auto-interpreted file is still read, parsed, validated, stored and registered by the same code as a
  profile-loaded file.
- **Missing after this branch:** API adapters, DuckDB, MIQP/QLOPB, Research Library, Feature Store, result reuse,
  calendars, corporate actions, conflict *resolution* policy.

## 6. Automatic interpretation rules (implemented on this branch)

Every rule produces a generated source profile, so the existing engine does all reading and validation. The profile
text is stored in the registry (`source_profiles`) and its ID is its content hash (`auto_<12 hex>`). The same layout
with the same answers always gives the same profile, so re-scans reuse earlier results instead of duplicating them.

| Rule | What is decided automatically | When Q-MAP asks or rejects instead |
|---|---|---|
| A-1 Format | Parquet / XLSX / XLS / text from the file's bytes (existing `format_detect`) | Unsupported, damaged, encrypted, archives, JSON, PDF → rejected with the existing messages |
| A-2 Delimiter (text) | The one candidate among `,` `;` tab `|` that splits every non-blank line into the same number (≥ 5) of fields | None or several qualify → rejected ("cannot tell how columns are separated") |
| A-3 Header | Row 1 is a header when its cells are not numbers or dates and at least the date and four price names are recognised | Row 1 has words but they are not recognised → asked/rejected with the names found |
| A-4 Column names | Exact, case-insensitive names: date (`date`, `time`, `datetime`, `timestamp`, `trade_date`, `day`), `time` as a separate column when a date column also exists, `open`/`o`, `high`/`h`, `low`/`l`, `close`/`c`/`last`/`ltp`, `volume`/`vol`/`qty`/`quantity`; `adj close` is never read as close | A required field matched by two columns → rejected; missing field → rejected |
| A-5 Headerless | Positions date, open, high, low, close [, volume] only if **every** row has a parseable date in column 1, numbers in columns 2-5, and high ≥ open, close, low and low ≤ open, close, high on every row. Column 6 is volume only if every value is a whole number ≥ 0. Columns 7+ are kept, never used as volume. Rules v3 (D5-20): if column 2 is a time of day on **every** row (and column 1 never), the columns are date, time, open, high, low, close [, volume] and the same conditions apply one column on | Any row breaks the rule → rejected ("column order cannot be confirmed") |
| A-6 Dates | Every non-empty value must fit exactly one candidate: ISO date/time (with or without offset), `DD-MM-YY[YY]`, `DD/MM/YY[YY]`, `MM/DD/YYYY`, `YYYYMMDD`, `DD-Mon-YY[YY]`, each optionally with ` HH:MM[:SS]`; Unix seconds / milliseconds (10 / 13 digits); native Excel/Parquet dates. Two-digit years use Q-MAP's existing fixed rule (00-68 → 2000-2068, 69-99 → 1969-1999). If several candidates fit (for example day-first and month-first), only those whose dates are in file order (all non-decreasing or all non-increasing) are kept | Still more than one candidate, or none → **question**: the user picks the format; the answer is recorded |
| A-7 Time zone | Values with an offset, Unix times and date-only values need no assumption. The trading date of an instant uses the **source folder's market time zone**, which the user confirms when adding the folder | Naive date-times, or instants, with no confirmed market time zone → question |
| A-8 Instrument | Precedence (owner decision DQ-2, rules v2): `exchange`/`symbol`/`ticker` columns in the file; then the user's recorded answer; then a file name of the form `EXCHANGE_SYMBOL…` (recognised exchange code, then `_`, then letters/digits/`&`/`-`), the same pattern as the existing Example profiles; then, only if the user enabled it for the folder, the file name as the symbol, with the folder's default exchange (rules v3, D5-17: only when the rest of the name is a timeframe token; otherwise, or with the option off, the name is a pre-filled suggestion the user confirms). `CRYPTO_SYMBOL` names give the symbol but never the default exchange (D5-18). A file name that contradicts an exchange or symbol column is **rejected**, never used | Exchange and symbol both unknown → question; only the exchange unknown → exchange-only question |
| A-9 Timeframe | From the data: date-only (or one bar per date) with a typical gap of 1-4 days → `1D`, 5-9 → `1W`, 27-33 → `1M`; intraday from the most common step if it is 1, 5, 15, 30, 60 or 240 minutes (180 = `3h` pending DQ-7) and covers ≥ 60 % of steps. A file-name token (`, 1D`, `_5m`, `_30min`, `, 60` …) is evidence only. Rules v3 (D5-19): a recorded answer that contradicts a clearly measured intraday interval is not used | Too few bars, irregular steps, or a file-name token that contradicts the data → question. A clear interval with no matching timeframe → rejected (never relabelled) |

Volume (A-4/A-5): one recognised volume column → used. "Net volume", "delivery", "open interest" and every other
unrecognised column are preserved as `x_` columns (existing behaviour) and listed in the import record.

## 7. Material risks

| Risk | Mitigation on this branch | Residual |
|---|---|---|
| A wrong automatic interpretation enters research | Every rule needs evidence from **all** rows; ambiguity asks; the generated profile and the evidence are stored with the attempt and the scan record; validation still runs in full | Rules A-5 (headerless convention) and A-8 (file-name identity) are conventions, recorded and visible; owner to confirm (DQ-2) |
| Re-scans create duplicates | Content reuse (existing) + scan state (size, time, checksum, inputs) | — |
| Overlapping files with conflicting bars | Reported as a warning on the new dataset (counts and examples); both datasets kept unchanged | No automatic choice of the "current" dataset (DQ-1) |
| Schema change | Migration 8 adds tables only, append-only triggers, earlier migrations untouched and pinned | Old code cannot open a schema-8 database (existing rule D2-28) |
| Scan scope | Only the chosen folder (sub-folders only if ticked), only supported extensions, exclusion patterns; hidden and system files skipped | — |

## 8. API adapters (Part 7 of the assignment): status and recommendation

**Not started in this session.** v1.3 §8.5.2 asks to prioritise folder ingestion and add adapters incrementally after
a feasibility review of coverage, authentication, cost and licensing. No credentials, accounts or permitted access
were available here, and the choice of the first five providers is the owner's (§8.5.2). The folder pipeline built
here is the shared path an adapter will use: an adapter retrieves data, writes the provider's response as a retained
source file with a provenance sidecar, and passes it through the same interpretation, validation and registration.
Recommended next session: (1) owner names the first two providers and supplies sandbox credentials; (2) adapter
contract and mocked tests; (3) live tests only with permitted access, reported separately.

## 9. Implementation phases and status

| Phase | Content | Status |
|---|---|---|
| 1 Stabilise | Verify PR #4 baseline; merge `main` (v1.3) into the stack | Done and tested (842 passed) |
| 2 Automatic ingestion | `data_engine/auto_interpret.py` (rules A-1…A-9), `data_engine/discovery.py` (folder sources, scans, answers, change and overlap detection), schema migration 8 | Done and tested (see the PR) |
| 3 User workflow | Database Manager **Sources** screen (add folder, scan, results, answer questions, open dataset list) | Done and tested in a virtual screen; **not** tested on Windows/IDLE |
| 4 Quantitative evidence | End-to-end: folder → scan → registered dataset → Workbench readiness → Dataset Summary; every figure recomputed independently from the original text | Done and tested (synthetic data) |
| 5 API adapters | — | Not done (section 8) |
| 6 Handover | Docs, owner checklist, PR | Done; owner acceptance outstanding |

## 10. Decisions for the Project Owner

| Ref | Question | Why it matters | Options | Recommendation | If delayed |
|---|---|---|---|---|---|
| DQ-1 | Update conflict policy (Blueprint §17 open decision) | — | — | **Decided by the Project Owner 02-Nov-26 (PR #9 discussion): REPORT ONLY.** Both datasets are kept unchanged; no winner, merge or overwrite; the conflict stays visible. See section 12 for implementation and test status | — |
| DQ-2 | Rules A-5 (headerless) and A-8 (file-name identity) | — | — | **Approved by the Project Owner 02-Nov-26 (PR #9 discussion)**, with the condition that explicit instrument information in a file is never silently overridden by its name. See section 12 | — |
| DQ-3 | First API providers (two of Zerodha, Dhan, Angel One, FYERS, NSE, Yahoo) and permitted credentials | §8.5.2 requires an owner priority and licensing review | — | Start with one broker API you already hold an account for | Adapters stay unbuilt |
| DQ-4 | Carry-over: OD-2 (QLOPB source, MIQP specs), OD-3, OD-4, OD-5, OD-10, OD-12-14 | See `Outstanding_Work_Register.md` | — | — | MIQP/QLOPB integration cannot start without OD-2 |
| DQ-5 | Should scanning offer an optional schedule? | §8.5.6 makes it optional | On-demand only (implemented) / add an in-app schedule | On-demand until daily use shows a need | None |
| DQ-6 | v1.3 "Version authority" paragraph 2 still names v1.2 as the primary reference | Editorial inconsistency inside the approved document | Correct in a v1.3 maintenance edit / leave | Correct it (both copies together) | None; v1.3 is treated as authoritative |

## 11. Handover in plain English (02-Nov-26)

**What you can do now.** In Database Manager, open **Sources**, add the folder where your market files are kept and
press **Scan**. Q-MAP reads each file's layout by itself, checks it with the same rules as before, and loads it. It asks
you a short question only when the file genuinely leaves something open: which instrument it is, which of two date
readings is right, the market time zone, or a timeframe the file name contradicts. Scanning again skips unchanged files.
A changed file is loaded as a new version, and any bars that differ from what you already have are flagged. Your
folder is only ever read.

**What was kept.** Everything in PR #4: both applications, the data checks, Permanent/Temporary storage, derived
timeframes, the Workbench's readiness checks and run records, and loading a single file with a chosen profile (still
there, for unusual files).

**What was checked.** About 60 new automated tests, plus the 842 existing ones: 903 in total passed, 0 failed, run in
a Linux container. One end-to-end test takes a file from a folder through to a Dataset Summary and recomputes every
figure separately from the file's own text; all match. The data was synthetic.

**What was not checked.** Windows/IDLE with your real files (please use the checklist in
`docs/acceptance_testing/`), a real OneDrive or Google Drive client, and any provider API (none was built).

**What is still to do.** Provider APIs (after you choose providers, DQ-3), MIQP and QLOPB
(the code and specifications are needed, OD-2), DuckDB, Research Library, result reuse.

**Recommended next milestone.** First, your Windows/IDLE acceptance of PR #4 and this PR. DQ-1 and DQ-2 were decided on 02-Nov-26 (section 12). Then agree
the merge order #1 → #2 → #3 → #4 → this PR. Then a separate session for the first API adapter.

## 12. Owner decisions DQ-1 and DQ-2: implementation and test status (02-Nov-26)

Decisions recorded by the Project Owner in the PR #9 discussion on 02-Nov-26. Each line separates four things: the
decision, the code, the automated tests, and the owner's Windows/IDLE acceptance.

| Decision | Approved | Code | Automated tests (Linux container, Python 3.12, Tk under Xvfb) | Windows/IDLE acceptance |
|---|---|---|---|---|
| **DQ-1** Conflicting overlapping bars: report only; keep both datasets unchanged; no winner, merge or overwrite; conflict visible | Yes, 02-Nov-26 | **Already met; no code change.** `data_engine/overlap.py` records a warning on the new dataset (counts, field, both values, the other dataset's ID); nothing else is written | Passing. `test_owner_decisions_dq1_dq2.py`: the earlier dataset's registry row, file bytes and checks are identical before and after; both stay active, nothing superseded; each holds only its own file's values; the conflict shows in the dataset's warnings, in readiness and in the scan result, survives later scans, and is not recorded twice. Identical overlap is info only; other instruments are not compared | **Not done** (owner) |
| **DQ-2** Headerless files: Date, Open, High, Low, Close; Volume only when the rules support it | Yes, 02-Nov-26 | **Already met; no code change.** Rule A-5: column 6 is volume only if every value is a whole number ≥ 0; otherwise (negative, fraction, blank, text) it is kept as `x_col5` and never used; columns 7+ are never volume | Passing. Positions checked against stored values; each failing volume case; column 7 never volume; files whose columns do not behave like OHLC, with too few columns, or whose first column is not a date are rejected | **Not done** (owner) |
| **DQ-2** File-name identity (`NSE_NIFTY, 1D.csv`); file contents never silently overridden | Yes, 02-Nov-26 | **Corrected (smallest change, `auto_interpret.py`, rules version 1 → 2).** Before: a file with an `exchange` column but no `symbol` column took the exchange from its NAME, and the column was silently ignored. A name that contradicted an exchange column, or a multi-symbol column, was not reported. Now: columns always win; a contradicting name is rejected with the reason. A file lacking only its exchange gets an exchange-only question (the Sources screen now enables just that box) | Passing. Name supplies identity when the file has none (recorded in the evidence); agreeing columns are used; four contradiction cases rejected (each failed on the old code); exchange column + symbol from name; exchange-only question answered and loaded (also a real-window test) | **Not done** (owner) |

**Remaining limitations (not marked complete):**
- Overlap and conflict checks run for datasets registered by a **folder scan**. A file loaded through the older
  Data Management screen is not itself checked when loaded, although a later scanned file is compared with it.
- Which of two conflicting datasets to analyse is the user's choice in the Workbench; Q-MAP shows the warning but
  does not mark either as preferred (by decision).
- The rules-version change means a file already loaded by rules v1 is re-read on the next scan and registered under
  the new processing version. For a dataset from the same original file, the earlier one is marked superseded by the
  existing ingestion rule (one active dataset per original file, instrument and timeframe); nothing is deleted. No owner data was loaded with rules v1 (acceptance has not started).
