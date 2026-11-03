# Proposals DQ-11 to DQ-14 (PR #10 review, 03-Nov-26) — NOT implemented in PR #10

> **Latest status (owner decisions on the second review, D5-40..D5-43):** DQ-11 approved in principle (category list
> under review); DQ-12 approved in principle, source-specific; DQ-14 provisionally approved on stated terms; OW-33
> deferred to a separate assessment. None implemented. See the separate proposal documents.
>
> **Status after the owner's review (03-Nov-26):** DQ-11 and DQ-12 approved in principle, NOT for PR #10; their
> separate proposals are `Proposal_DQ11_Asset_Category_and_Venue_03_Nov_26_075552.md` and
> `Proposal_DQ12_Technical_Export_Columns_03_Nov_26_075552.md`. DQ-13: the source file and its values are not changed;
> rows 34185 and 34189 stay rejected under the current OHLC rule until authoritative evidence is obtained; the
> investigation is kept separate from PR #10. DQ-14: not approved; superseded by
> `Proposal_DQ14_Revised_03_Nov_26_075552.md`.

Each is a separate owner decision. Nothing below is built; PR #10 keeps today's behaviour, described in the
implementation report. Approve, amend or decline each one independently.

## DQ-11 — separate asset category and exchange/venue fields

**Today.** `instruments(exchange, symbol, name, sector, active, valid_from, valid_to)`; identity = (exchange, symbol),
immutable; the storage path is `<EXCHANGE>/<SYMBOL>/<TF>/`. Crypto files are stored under exchange `CRYPTO` (a category
used as an exchange) and "venue unknown" is only in the interpretation record of the scan.

**Proposal (smallest, backward compatible).** Schema migration 11 adds two NULLABLE columns, nothing else:

| Column | Values | Filled by |
|---|---|---|
| `instruments.asset_category` | `equity`, `index`, `crypto`, `currency`, `commodity`, `derivative` (controlled list), NULL = not yet classified | the scan: `crypto` for `CRYPTO_` files; `index` when the alias registry says so (optional extra registry column); otherwise NULL |
| `instruments.venue` | free text (`BINANCE`, `COINBASE` ...), NULL = unknown | a user correction, or a `venue` column in the file |

- **Identity and paths stay (exchange, symbol)**: no dataset is renamed or moved, no existing row changes meaning.
  `CRYPTO` remains the exchange key for crypto, now documented as "category key"; the real trading venue goes in
  `venue`. A user who later learns the venue records it there (a correction, not a new instrument).
- **Migration:** `ALTER TABLE ... ADD COLUMN` twice, then `UPDATE instruments SET asset_category = 'crypto' WHERE
  exchange = 'CRYPTO'`. The identity trigger is unchanged; a new trigger allows `asset_category` / `venue` to change
  only from NULL to a value or through a recorded user correction (append-only `instrument_changes` table if you want
  a history of edits; otherwise a single fill is enough).
- **Compatibility:** older code ignores the new columns; catalog, Workbench and reports show them where present. No
  re-processing is triggered. Risk: low. Effort: about one day with tests.
- **Not proposed:** changing the identity to (category, venue, symbol); that would move every stored file.

## DQ-12 — known technical/export columns in duplicate comparison

**Today (safe).** An exact duplicate must match in EVERY source column. AKZOINDIA's `index` (a per-download row
counter) differs between the two copies of 17-Oct-25 and 24-Oct-25, so all 750 repeated timestamps are conflicts,
although 428 of them have identical open, high, low, close and volume.

**Proposal.**
1. A controlled list in configuration, `[duplicates] ignore_columns = ["index", "Unnamed: 0", "row_id"]`, empty by
   default, exact column names (case-insensitive), never patterns.
2. A row is an exact duplicate when all columns EXCEPT the listed ones are identical. The listed columns are still
   stored (as `x_` columns, unchanged) and still shown.
3. Full auditability: the check `exact_duplicates_removed` names the ignored columns and, for each removed row, the
   values that differed only in them; the setting becomes part of the settings fingerprint (so a change re-processes
   the affected files as new datasets and never rewrites old ones); the scan report lists the files where the list
   mattered.
4. Never ignored, whatever the list says: date/time, open, high, low, close, volume, symbol, exchange.

Effect on the owner's files: AKZOINDIA's repeated days would become 428 exact duplicates (removed) and 322 conflicting
timestamps (kept). Risk: a wrongly listed column hides a real difference; mitigated by the explicit list, the audit
trail and point 4.

## DQ-13 — AKZOINDIA 08-Nov-25 (evidence only; the source and values are not changed)

File `AKZOINDIA.parquet`, SHA-256 starting `02b8a861ed223b15`. Q-MAP numbers Parquet rows from 1 (no header row), so
Q-MAP source row = 0-based Parquet row + 1. The two rows that fail `low_le_open_close`:

| Q-MAP source row | Parquet row | Date (as stored, naive IST) | Open | High | Low | Close | Volume | index |
|---|---|---|---|---|---|---|---|---|
| 34185 | 34184 | 2025-11-08 11:01:00 | 2641.0 | 3262.3 | 3262.3 | 3243.0 | 100 | 1500.0 |
| 34189 | 34188 | 2025-11-08 11:05:00 | 2641.0 | 3262.3 | 3262.3 | 3243.0 | 100 | 1504.0 |

Context from the same file: 08-Nov-25 is a **Saturday**; the file has 88 bars that day (11:01 to 12:28), 73 of them
with zero volume, only 11 distinct OHLC rows, closes from 3196.0 to 3700.0. Last close of 07-Nov-25: 3243.0; first open
of 10-Nov-25: 3261.0. In both failing rows the low (3262.3) is above the open (2641.0), which no real bar can have; the
open is about 19 % below the surrounding prices.

**What evidence is needed to correct them (the owner's decision, outside Q-MAP):**
1. Whether NSE held a trading session for this stock on Saturday 08-Nov-25 (an exchange circular or notice of a
   special or mock session). If it was a mock/test session, the right correction is to remove the whole day from the
   source copy, not to edit two values.
2. If it was a real session: the official bar or trade data for 11:01 and 11:05 from the exchange or a second,
   independent vendor, to replace the values in a corrected copy of the file.
3. The corrected file is then loaded as a new file (new raw dataset); the original file and its rejected attempt stay
   in the registry as they are.

## DQ-14 — when the full-file check finds a section with another interval

**Today.** Sampling decides the timeframe; validation's `interval_change_detected` reports a section it missed
(source rows, length, interval) as a warning; the dataset keeps the sampled timeframe.

**Proposal.** When `interval_change_detected` finds a section of at least 1 % of the rows (or 30 steps, whichever is
larger), register the dataset as `MIXED` instead, with the section listed, exactly as if a sampled block had landed in
it. Smaller sections stay a warning. This keeps the sampled inference unchanged and uses evidence validation already
computes; it changes only which label is stored. Risk: low; it can only make a timeframe more cautious.
