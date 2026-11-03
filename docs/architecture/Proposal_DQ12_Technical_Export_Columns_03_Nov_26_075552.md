# DQ-12 — ignoring known technical/export columns in exact-duplicate comparison — NOT implemented

Status: the Project Owner approved a **controlled, auditable policy** in principle (03-Nov-26). Implementation is
**not authorised inside PR #10**; this is a separate task. Supersedes the DQ-12 section of
`Proposals_DQ11-DQ14_03_Nov_26_150000.md`.

## 1. Today (safe rule, unchanged)

`process._repeated_timestamps`: rows of one instrument sharing a timestamp are exact duplicates only when **every
source column** is identical (`canonical.DUPLICATE_RULE`); otherwise all are kept as conflicting observations.
AKZOINDIA's `index` column (a per-download row counter) differs between its two copies of 17-Oct-25 and 24-Oct-25,
so all 750 repeated timestamps are conflicts although 428 have identical date/time, OHLC and volume.

## 2. Proposal

1. **Controlled list**, one entry to start: `[duplicates] ignore_columns = ["index"]` in the settings, **empty by
   default** (the owner switches it on). Exact column names, case-insensitive, after header trimming; no patterns or
   wildcards. Further names (e.g. `Unnamed: 0`) are added only by a later owner decision.
2. **Protected fields, never ignored** whatever the list says: the columns mapped to date, time or datetime, open,
   high, low, close, volume, symbol and exchange. A listed name that maps to one of them is refused at settings load
   with an error naming it.
3. **Comparison:** rows sharing a timestamp are exact duplicates when every column except the listed ones is
   identical. The first is kept; the others are removed from the standardised copy only. Rows that still differ
   remain conflicting observations, as today.
4. **Original source preserved:** source files and stored originals never change. The listed columns stay in the
   standardised copy as preserved `x_` columns with the kept row's value.
5. **Audit of every ignored difference and every removed row:**
   - `exact_duplicates_removed` (INFO) names the ignored columns; per removed row: source row, kept source row, and
     each ignored column with both values (e.g. `index 1500 -> 1504`).
   - Transformation step in the provenance record with the rule text and the list in force.
   - Issues report and the scan report list the files where the list changed the outcome, with counts
     (duplicates removed because of the list; conflicts that remain).
   - The list is part of the **settings fingerprint**: changing it re-processes affected files as **new datasets**;
     earlier datasets, attempts and runs stay as they are (superseded, never rewritten).
6. **Reversibility:** emptying the list and rescanning gives the current behaviour again (new datasets).

## 3. Expected effect on the owner's files

AKZOINDIA: of 750 repeated timestamps, 428 become exact duplicates (one copy removed, each audited) and 322 stay
conflicts. The file remains rejected in any case until DQ-13 (two bars of 08-Nov-25) is resolved. Other files: no
`index` column, no change.

## 4. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A listed column hides a real difference | explicit list, empty by default; protected fields; every ignored difference audited |
| Silent behaviour change on rescans | list in the fingerprint: a change creates new datasets, never rewrites |
| Name collision (a meaningful column called `index`) | the owner enables the list per settings file; the audit shows the values |

Effort: about half a day with tests (duplicate rule, protected-field refusal, audit content, fingerprint change).

## 5. Decisions requested

1. Approve `index` as the first and only list entry.
2. Approve the protected-field list in point 2.
3. Global setting, or per source folder? (Recommendation: global, simpler to audit.)
