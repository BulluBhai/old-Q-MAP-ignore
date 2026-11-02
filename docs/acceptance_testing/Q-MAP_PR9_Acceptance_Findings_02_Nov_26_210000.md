# Q-MAP PR #9: acceptance findings, fixes and verification (02-Nov-26)

Consolidated report for the change and acceptance instructions issued after the owner's Windows/IDLE acceptance session
on PR #9 (stacked on PR #4). Branch: `claude/friendly-babbage-8xyrgo`, created from PR #9's head `b7a76c2`
(`claude/happy-brahmagupta-su6tnr`). **Nothing is merged. PR #9 and PR #4 remain open and unmerged.**

Status words: **Confirmed defect**, **Expected behaviour**, **Source-data issue**, **Limitation**, **Unconfirmed**.
Test words: **done and tested**, **done but not tested**, **not done**.

Evidence base: copies of the owner's eight files (`5PAISA_30min.csv`, `AKZOINDIA.parquet`, `CRYPTO_RIVERUSD, 180.csv`,
`ICICIBANK.txt`, `NSE_BANKNIFTY, 15.csv`, `OLAELEC.xlsx`, `UJJIVAN.txt`, `VERANDA_1min.csv`), analysed in full (every
row, with pandas, independently of Q-MAP) and scanned with the real Sources code in a Linux container (Python 3.12,
Xvfb). The files are **not** committed; the regression tests use synthetic data in the same layouts (repository
convention). Nothing here was run on Windows or in IDLE.

## 1. Findings and root causes

| # | Item | Classification | Root cause and evidence | Fix |
|---|---|---|---|---|
| F-01 | 2.1 Manual symbol entry for `5PAISA_30min.csv`, `AKZOINDIA.parquet`, `ICICIBANK.txt`, `OLAELEC.xlsx`, `VERANDA_1min.csv` | **Expected behaviour under D5-06**, with a usability gap and two parsing defects | Only `EXCHANGE_SYMBOL...` names with a recognised exchange code give identity automatically (`NSE_BANKNIFTY, 15.csv` matches: NSE is recognised). A plain name is used only when the folder option **File name is the symbol** is on (off by default, D5-06). The owner's folder had it off, so all five were asked. Defects found while checking: (a) `_30min`/`_1min` tokens were not recognised as timeframes; (b) with the option on, the old plain-name rule took the first word of **any** name, so `CRYPTO_RIVERUSD, 180` became symbol **CRYPTO** on **NSE** | Rule A-8: a plain name is the symbol only when the rest of the name is a timeframe token (`ICICIBANK`, `5PAISA_30min`, `VERANDA_1min`); otherwise nothing. With the option off, the name is **suggested**: the Sources screen fills in the symbol and the exchange already known, and the user confirms with Save answer (one click). D5-06 itself is unchanged (DQ-8). A-9: `min` tokens recognised |
| F-02a | 2.2 `CRYPTO_RIVERUSD, 180.csv` registered as 4 h | **Confirmed defect** | Every same-day step is 180 minutes (3,003 rows, 100 %). 180 minutes was not a supported timeframe, so Q-MAP asked for the timeframe and offered the full list; the only nearby choice was `4h`. A recorded answer was used without checking it against the measured interval, and validation only **warned** (`timeframe_spacing`). The mislabel entered at the answer step (`auto_interpret._interpret`, A-9) | A timeframe answer that contradicts a clearly measured intraday interval is no longer used: asked again with the only consistent choice, or **rejected** if no timeframe fits. Nothing is relabelled, resampled or aggregated |
| F-02b | 180-minute support | **Limitation** (approved timeframe list) | `ALLOWED_TIMEFRAMES` (and the naming standard) has no 180-minute value. Downstream: validation spacing check, catalog labels and screen filters are list-driven; Dataset Summary accepts every listed timeframe; derived timeframes come only from 1D data, so they are unaffected | Smallest safe change: add the application value `3h` (180 minutes). **Implemented in its own commit, pending owner approval (DQ-7)**. Without it, the file is rejected with the reason |
| F-02c | RIVERUSD exchange | **Confirmed defect** | `CRYPTO` is not an exchange code, so the folder's default exchange (NSE) was applied silently | `CRYPTO_` is a market prefix: symbol `RIVERUSD` from the name; the default exchange is never applied; the venue is asked |
| F-03 | 2.3 `UJJIVAN.txt` rejected | **Confirmed defect** (layout) **and source-data issue** | The headerless rule required column 2 to be a number; here column 2 is the time of day (`2024-01-20,12:10:00,589.9,...`) | Headerless rule A-5 extended: when column 2 is a time of day on **every** row (and column 1 never is), the columns are date, time, open, high, low, close [, volume]; the same OHLC and volume checks apply one column on; the market time zone is applied. The file now reads correctly but is still **rejected**, rightly: 26-Mar-24 appears twice (75 identical bars, rows 3201-3350), so 150 rows share a timestamp. Verified with a scratch copy without the repeated block: 4,925 rows, timestamps (IST to UTC), OHLC and volume all identical to the source |
| F-04 | 4.3 Repeat scans after a rules change | **Confirmed defect** (found during this work) | The generated profile's ID and the structure signature included the rules version. Bumping it (as v1 to v2 did) re-processed unchanged files under a new profile, superseding every dataset with an identical copy, and silently discarded recorded answers ("structure has changed") | Profile seed and signature version are pinned (`PROFILE_RULES_SEED`, `SIGNATURE_RULES` = 2); the rules version still triggers re-interpretation. Unchanged files are now **reused** and answers kept (tested) |
| D-01 | 3.1 AKZOINDIA `index` column | **Source characteristic** (export artefact) | Full file: 14,773 of 39,897 rows have a value, from 06-Oct-25 onwards; it counts 0, 1, 2 ... and restarts at 0 at rows 25124, 26998, 29248, 30809, 32684, 34272, 36147, 38022 (eight download batches). It is a per-batch row counter, not market data | Recognised as an additional field (evidence: "Kept unchanged as additional fields: ['index']"): it would be stored as an `x_` text column, never used as price or volume. The file is rejected for other reasons (D-03, D-04), so nothing is stored yet. No change |
| D-02 | 3.2 ICICIBANK column 7 | **Expected behaviour** | All 7,166 rows compared: columns 6 and 7 are equal on 5,133 rows (every row before 27-Jul-18, plus 12 later rows) and differ on 2,033 (from 27-Jul-18). Column 7 is never larger than column 6 (13 %-84 % of it), so it looks like delivery quantity, not a duplicate. Column 6 passes the volume rule | Column 6 = volume; column 7 preserved as `x_col6`, never volume (verified equal to the source on every row). No change |
| D-03 | 3.3 AKZOINDIA, OLAELEC repeated timestamps | **Source-data issue** | AKZOINDIA: 17-Oct-25 and 24-Oct-25 each appear twice, as two complete 375-bar blocks (1,500 rows, 750 timestamps); 322 of the 750 pairs differ: always in the open, sometimes also in the high or low (close and volume never differ). OLAELEC: eight full days (04-Apr-25, 09-May, 15-May, 16-May, 30-May, 13-Jun, 04-Jul, 08-Aug-25) appear twice as consecutive 375-bar blocks (6,000 rows, 3,000 timestamps); 183 pairs differ (open always; high or low in 32 of them; close and volume never). Pattern: overlapping downloads appended. Parsing and timeframe are correct (`Date` cells are native datetimes, 1-minute steps) | No change. Rejected by `no_duplicate_timestamps`; nothing deduplicated or chosen. The owner can remove the second block of each day (or confirm which copy is right) and scan again |
| D-04 | 3.4 AKZOINDIA `low_le_open_close` | **Source-data issue** | Rows 34185 and 34189 (source rows, header = 1): 08-Nov-25 11:01 and 11:05, Open 2641.0, High 3262.3, Low 3262.3, Close 3243.0. Low is above the open, which is impossible. 08-Nov-25 is a **Saturday** with 88 bars, prices up to 3,700 and mostly zero volume: consistent with an exchange mock/test session, not trading | Rule unchanged and correct. Recommend removing 08-Nov-25 from the file |
| D-05 | 3.5 ICICIBANK detail shown twice | **Unconfirmed** | Reproduced the owner's flow in the real windows (Xvfb): the Datasets and Storage detail and the Workbench readiness box each show the ICICIBANK block **once**. No code path builds it twice | No change |
| D-06 | 3.6 Warnings | See section 1.1 | | No suppression |
| D-07 | 5.2 ICICIBANK Dataset Summary | **Verified correct** | Independent pandas calculation on the source file: 08-Jan-26 to 02-Nov-26 = 201 bars, first close 1,435.00, last close 1,387.40, change -3.3171 %, mean daily return -0.0082 %, standard deviation 1.3181 %, largest +5.1144 %, smallest -3.2557 %, average volume (column 6) 14,518,331.47; all equal to Q-MAP's output. Both reported source rows match. The period starts on 08-Jan-26 because that was the chosen start date (the file has bars from 01-Jan-26; with 01-Jan-26 Q-MAP gives 206 bars, also verified) | No change |
| OW-25 | 4.4 Conflict check for Data Management loads | **Limitation** (scope confirmed) | `record_overlaps` is called only by the folder scan (`discovery._scan_one`). Data Management (`qmap_gui/jobs.py`) and the command line (`cli.py`) call `ingest_file` only. A later scanned file **is** compared with a Data Management dataset (tested), so the gap is one direction only | **Proposed, not implemented** (instruction 4.4): after an accepted ingest in `jobs.py` and `cli.py`, call the same `record_overlaps` (report-only, both datasets unchanged, DQ-1), and show its notes in the results table. About 10 lines plus tests. Awaiting approval (DQ-9) |

### 1.1 Warnings on the imported datasets (3.6)

All warnings are kept; none was suppressed. Severity: warnings never block import; errors reject.

| Dataset | Warning | Meaning | Assessment |
|---|---|---|---|
| NSE:BANKNIFTY 15m | partial_session: 12-Nov-23 5/25, 02-Mar-24 10/25, 18-May-24 10/25, 01-Nov-24 4/25, 21-Oct-25 4/25 | Fewer bars than a normal day | **Legitimate**: Muhurat sessions (12-Nov-23, 01-Nov-24, 21-Oct-25) and NSE special Saturday sessions (02-Mar-24, 18-May-24) |
| NSE:5PAISA 30m | date_gaps (e.g. 15-Dec-17 to 05-Jan-18, 14-May-20 to 03-Jun-20); partial_session (e.g. 27-Oct-19 2/13 Muhurat) | Missing calendar ranges; short days | Partial days mostly legitimate. The three-week gaps are **not explained by holidays**: possibly suspension/illiquidity or missing data. Owner judgement needed before using this file for gap-sensitive research |
| NSE:VERANDA 1m | date_gaps 13-Jun-22 to 23-Jun-22, 22-Aug-22 to 01-Sep-22; partial_session (many days with 300-374 of 375 bars) | | Missing minutes are typical of an illiquid stock (no trades, no bar). The two 10-day gaps are unexplained; owner judgement as above |
| CRYPTO:RIVERUSD 3h | large_moves: 17 bars over 25 % (first at source row 18); partial_session: 22-Sep-25 4/8, 02-Oct-26 7/8 | | **Legitimate** for a newly listed crypto asset (first bar 2.56 to 1.63). Partial first/last days are the start and end of the file. `partial_session` counts days in Asia/Kolkata, which is only a convention for a 24/7 market |
| UJJIVAN (scratch copy) 5m | partial_session: 20-Jan-24 41/75, 02-Mar-24 9/75 | | **Legitimate**: NSE special Saturday sessions |
| ICICIBANK 1D | none | | Passed |

Rejected files also showed `source_order` (rows out of time order, caused by the repeated blocks) and, for AKZOINDIA,
partial sessions 21-Oct-25 (Muhurat, legitimate) and 08-Nov-25 (the suspected mock session, D-04).

## 2. Changes implemented

| Commit | Content | Status |
|---|---|---|
| `03d7d16` | Rules version 2 to 3: F-01 (`min` tokens, stricter plain-name symbol, suggestion pre-filled), F-02a/c (answers that would relabel measured bars are not used; `CRYPTO_` prefix), F-03 (headerless date + time), F-04 (pinned profile seed and signature). Workbench: `<<`/`>>` year buttons; Open Output Folder beside the completion message | Done and tested (Linux) |
| `6f1e365` | Proposed timeframe `3h` (180 minutes): profiles, interpretation, catalog, three screen filters, naming-standard note | Done and tested (Linux); **owner approval pending (DQ-7)**; revert this commit alone if declined |
| this commit | This report; decision log D5-16 to D5-21; outstanding-work register; audit rules A-5, A-8, A-9; user guides; acceptance-checklist addendum | Documentation |

Open Output Folder (instruction 7): the Workbench already had this button in section 2 (PR #4). A second button with
the same action now sits under the completion message in Progress / Status. Both open the folder **recorded** for the
latest completed run (`runs.output_path`, via `latest_completed_run`), are disabled until a run completes, explain a
missing or refused folder in a message, and never change run contents. On Windows the folder is opened with
`os.startfile`, which opens File Explorer at that folder without waiting for it.

Date picker (instruction 8): `<<` and `>>` move one year and keep the month; `<` and `>` are unchanged. Date
interpretation rules are unchanged.

## 3. Automated test results (local, Linux container; not CI)

| Run | Passed | Failed | Skipped |
|---|---|---|---|
| Baseline before changes (PR #9 head `b7a76c2`), Python 3.12 + Xvfb | 928 | 0 | 0 |
| After `03d7d16` (no `3h`), Python 3.12 + Xvfb | 978 | 0 | 0 |
| After `6f1e365` (with `3h`), Python 3.12 + Xvfb (203 GUI tests) | 987 | 0 | 0 |
| After `6f1e365`, Python 3.13 without tkinter | 861 | 0 | 90 (GUI, no display) |

New tests fail on the previous code: 28 of the 45 tests then in `test_pr9_acceptance_findings.py` failed against
`b7a76c2`; the other 17 lock in behaviour that was already right (no deduplication, both datasets kept, rejections).
One existing GUI test was changed on purpose: the Sources answer boxes are now pre-filled, so the test empties them
before checking the "please give" warning, and also asserts the pre-fill and that nothing is saved until Save answer.
GitHub CI: see the PR (Windows and Ubuntu runners).

## 4. Import, registry and repeat-scan verification with the owner's files (Linux, not Windows)

Folder settings: Asia/Kolkata, NSE, symbol from the file name **on**; RIVERUSD venue answered `CRYPTO` (example only).

| File | Result | Rows stored / source | First / last (UTC) | Values compared with the source |
|---|---|---|---|---|
| 5PAISA_30min.csv | Imported, NSE:5PAISA 30m | 14,399 / 14,399 | 16-Nov-17 03:45 / 11-Oct-22 09:45 | timestamps, OHLC, volume: all identical |
| CRYPTO_RIVERUSD, 180.csv | Imported, CRYPTO:RIVERUSD **3h** (with DQ-7) | 3,003 / 3,003 | 22-Sep-25 09:00 / 02-Oct-26 15:00 | timestamps, OHLC identical; ATR columns kept as `x_` |
| ICICIBANK.txt | Imported, NSE:ICICIBANK 1D | 7,166 / 7,166 | 02-Jan-98 / 02-Nov-26 (dates) | dates, OHLC, volume identical; column 7 kept as `x_col6`, identical |
| NSE_BANKNIFTY, 15.csv | Imported, NSE:BANKNIFTY 15m | 20,233 / 20,233 | 01-Nov-22 03:45 / 06-Feb-26 09:45 | timestamps, OHLC identical; ATR kept |
| VERANDA_1min.csv | Imported, NSE:VERANDA 1m | 38,674 / 38,674 | 18-Apr-22 03:45 / 07-Oct-22 09:59 | timestamps, OHLC, volume identical |
| AKZOINDIA.parquet | Rejected (D-03, D-04) | - | - | - |
| OLAELEC.xlsx | Rejected (D-03) | - | - | - |
| UJJIVAN.txt | Rejected (repeated 26-Mar-24) | - | - | scratch copy without the repeat: 4,925 rows, all identical |

- **Rejected files** never appear in Datasets and Storage or the Workbench (checked in the real windows). Their
  original file is kept as a raw audit record (layer `raw`), with the rejected attempt and its checks; that is the
  existing, intended audit trail, not a dataset.
- **Repeat scans:** second and third scans of the unchanged folder: every file `unchanged`/`skipped`, datasets 15 to
  15, instruments 6 to 6. Answers were applied on the next scan. Changed files: existing tests
  (`test_folder_discovery.py` 27-29, DQ-1 tests) pass.
- **Upgrade path for the owner's existing registry** (tested with synthetic data): after this update every file is
  interpreted once more (rules version 3). Imported files are **reused** (no new datasets). RIVERUSD's recorded `4h`
  answer is no longer used: the file asks again (pre-filled `3h`) or, without DQ-7, is rejected. The existing 4h
  dataset is **not** changed or deleted automatically; to remove it, use Datasets and Storage (Move to Temporary, then
  Delete).

## 5. Dataset Summary and Workbench (5.1-5.3)

| Stage | Result |
|---|---|
| Data registered | ICICIBANK dataset registered and verified against the source (section 4) |
| Selected by the Workbench | Yes: listed and selectable in the real Workbench window (Xvfb), with the other imported datasets |
| Analysis executed | Dataset Summary, 08-Jan-26 to 02-Nov-26: completed, run folder with CSV, metadata JSON, log, manifest |
| Results independently verified | Yes: every figure equals the independent pandas calculation (D-07) |

## 6. Windows/IDLE acceptance (to be done by the owner; nothing here was run on Windows)

Only checks that a Linux container cannot establish, and only where this change affects behaviour, are listed in the
addendum of `Q-MAP_Sources_Acceptance_Checklist_02_Nov_26_183000.md` (A1-A8). Checks already passed by the owner
and not affected (window opening, folder choice, scan responsiveness, clean shutdown) are not repeated.

## 7. Remaining risks and limitations

- **Bar-time convention:** UJJIVAN's 5-minute bars are labelled 09:20 ... 15:30 (bar **end** times); the other files
  use start times (09:15 ...). Q-MAP stores the times as written and does not detect or convert the convention, so two
  sources of the same instrument could look shifted by one bar (OW-26).
- Unexplained multi-day gaps in 5PAISA and VERANDA (section 1.1) are reported, not resolved.
- `CRYPTO_` is the only market prefix recognised; other aggregator prefixes (e.g. `BINANCE_`) give no identity and are
  asked (safe default).
- The owner's earlier 4h RIVERUSD dataset stays until the owner removes it.
- OW-25 remains open until DQ-9 is decided.
- No Windows, IDLE or real cloud-folder testing by Claude.

## 8. Owner decisions required

| Ref | Decision | Recommendation |
|---|---|---|
| DQ-7 | Approve the new timeframe value `3h` (180-minute bars) | Approve: smallest change; no schema change; keeps the data's real interval |
| DQ-8 | Keep "File name is the symbol" off by default (with the new one-click suggestion), or switch it on by default | Keep off: the suggestion removes the typing, and a name like `prices.csv` is never taken as a symbol without confirmation |
| DQ-9 | Approve the OW-25 change: run the same report-only conflict check after Data Management and command-line loads | Approve |
| DQ-10 | Source files: remove the repeated days in AKZOINDIA, OLAELEC and UJJIVAN, and the 08-Nov-25 session in AKZOINDIA, then rescan | Owner action; Q-MAP will not choose between the copies |

## 9. Commit and PR status

Commits `03d7d16`, `6f1e365` and this documentation commit, on `claude/friendly-babbage-8xyrgo` (based on PR #9's head
`b7a76c2`). No pull request was opened for this branch; PR #9 and PR #4 are open and **unmerged**. Merging requires
Sandeep's approval.
