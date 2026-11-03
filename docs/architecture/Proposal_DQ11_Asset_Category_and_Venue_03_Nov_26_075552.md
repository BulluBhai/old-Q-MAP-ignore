# DQ-11 — separate asset category and trading venue: migration and compatibility proposal — NOT implemented

Status (latest): **APPROVED** with the nine-category list below (D5-46, 03-Nov-26); **not implemented**; a separate
task outside PR #10.

Earlier status: **principle approved** by the Project Owner (03-Nov-26; confirmed in the second decision note the same day,
D5-40). Category list revised as requested (ETF, Fixed Income, Unclassified added): **awaiting the owner's review of the
list**. **Not implemented**; implementation is **not authorised inside PR #10**;
this is a separate task, to be built on its own branch after PR #10 when approved. Supersedes the DQ-11 section of
`Proposals_DQ11-DQ14_03_Nov_26_150000.md` (same design, with the migration, compatibility and legacy-key rules made
explicit).

## 1. Today

- `instruments(instrument_id, exchange, symbol, name, sector, active, valid_from, valid_to)`, `UNIQUE(exchange, symbol)`,
  both upper-case and non-empty (migration 1). Trigger `trg_instruments_identity` (migration 2) makes
  (exchange, symbol) immutable; instruments are never deleted.
- Storage paths include the exchange: `Cleaned_Data/<EXCHANGE>/<SYMBOL>/<TF>/...` and
  `Timeframe_Data/<EXCHANGE>/<SYMBOL>/<TF>/...` (`storage/paths.py`); dataset rows, provenance, run inputs and reports
  refer to the instrument by `instrument_id` and to files by these paths.
- Crypto (`auto_interpret.CRYPTO_CATEGORY`): a file named `CRYPTO_<SYMBOL>` is stored as exchange **`CRYPTO`**. This is
  an asset category used in the exchange field because no category field exists; the real venue is unknown and only
  written in the scan's interpretation record ("trading venue unknown").

## 2. Proposal

Schema migration 11 (next number after 10) adds two nullable columns and one audit table; nothing else changes.

```sql
ALTER TABLE instruments ADD COLUMN asset_category TEXT NOT NULL DEFAULT 'unclassified'
  CHECK (asset_category IN ('equity','etf','index','fixed_income','currency','commodity','derivative','crypto',
                            'unclassified'));
ALTER TABLE instruments ADD COLUMN venue TEXT
  CHECK (venue IS NULL OR (length(venue) > 0 AND venue = upper(trim(venue))));
CREATE TABLE instrument_attribute_changes (          -- append-only history of category/venue edits
  change_id INTEGER PRIMARY KEY, instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
  field TEXT NOT NULL CHECK (field IN ('asset_category','venue')), old_value TEXT, new_value TEXT,
  origin TEXT NOT NULL,                                -- scan | user_correction | migration
  run_id TEXT REFERENCES runs(run_id), recorded_at TEXT NOT NULL);
-- + no-update / no-delete triggers on instrument_attribute_changes (same pattern as the other audit tables)
UPDATE instruments SET asset_category = 'crypto' WHERE exchange = 'CRYPTO';   -- recorded with origin 'migration'
```

- `asset_category`: controlled list, revised after the owner's review:

  | Value | Meaning |
  |---|---|
  | `equity` | shares |
  | `etf` | exchange-traded funds (kept apart from equity: an ETF tracks a basket, which matters for index comparisons) |
  | `index` | indices (NIFTY 50, BANKNIFTY spot) |
  | `fixed_income` | bonds, government securities, T-bills |
  | `currency` | currency pairs and currency futures' underlyings |
  | `commodity` | commodities |
  | `derivative` | futures and options (the underlying's category is a later, separate question) |
  | `crypto` | cryptocurrencies |
  | `unclassified` | **default**: not yet classified, or not determinable. Every existing instrument starts here, except `CRYPTO` |

  One explicit `unclassified` value (not NULL) so "unknown" is visible, filterable and auditable, and every row always
  has a category. Filled by the scan (`crypto` for `CRYPTO_` files; a category from an optional alias-registry
  column) or by a user correction. Never guessed from a symbol pattern. Extending the list later is a new migration.
- `venue`: the real trading venue (`BINANCE`, `COINBASE`, `NSE` ...), NULL = unknown. Filled only from a `venue`
  column in the data or a user correction; never guessed from a file name.
- Every change of either field is written to `instrument_attribute_changes` (old value, new value, origin, run).

## 3. Identities and storage paths are preserved (owner condition, 03-Nov-26)

- Identity stays **(exchange, symbol)**; the identity trigger is not touched; no instrument is renamed, merged or
  deleted; no dataset, file or path moves; `instrument_id` values are unchanged.
- No re-processing: category and venue are not part of the processing identity, the cleaning code or the settings
  fingerprint, so no dataset gets a new number.

## 4. The legacy `CRYPTO` key (owner condition: retained for compatibility, never a venue)

- `CRYPTO` remains the **exchange key** of existing (and new) crypto instruments, because it is part of their
  identity and storage path. It is documented and displayed as an **identity key for the asset category, not a
  venue**: screens and reports show "Category: crypto · Venue: unknown" (or the recorded venue), never
  "Exchange: CRYPTO" as if it were a market.
- `CRYPTO` is reserved: it can never be entered as a `venue`, and a user correction that sets a venue does **not**
  change the exchange key (that would be a new identity). Learning that `CRYPTO:RIVERUSD` trades on BINANCE sets
  `venue = 'BINANCE'` on the same instrument.
- If the same symbol later arrives with a real venue column (for example `BINANCE` in the data), DQ-2 precedence
  applies as today (column first): it is a different identity, `BINANCE:RIVERUSD`, with category crypto and venue
  BINANCE. The two are not merged automatically; the overlap report (DQ-9) shows the overlap, and linking them is a
  separate owner decision (an alias, not a rewrite).

## 5. Compatibility

| Area | Effect |
|---|---|
| Existing databases | migration 11 runs once, forward only, inside the usual migration transaction with a backup copy |
| Older code reading a migrated database | ignores the new columns (no column is renamed or removed) |
| Catalog, Datasets and Storage, Workbench | show category and venue where present; filters optional |
| Alias registry CSV | optional new column `category`; files without it keep working |
| CLI | `instrument set-venue / set-category` (writes a correction and the audit row) |
| Tests | schema-version tests 10 -> 11; new tests for the migration, the CRYPTO rules and the audit table |

Risk: low (additive). Effort: about one day with tests and documentation (schema document, user guides).

## 6. Decisions requested

1. Approve the revised category list in section 2 (nine values, default `unclassified`), or amend it.
2. Approve that `CRYPTO` stays as identity key and is reserved from the venue field.
3. Approve that a venue column in the data creates a separate identity (no automatic merge).
