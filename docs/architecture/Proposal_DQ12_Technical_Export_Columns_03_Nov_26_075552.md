# DQ-12 — ignoring known technical/export columns in exact-duplicate comparison — NOT implemented

Status (latest): **DESIGN APPROVED** as revised here — source profile or folder setting, profile over folder, no global
rule, default unchanged (D5-47); **not implemented**; separately planned outside PR #10.

Earlier status: **approved in principle** (03-Nov-26): controlled, auditable, `index` as the first approved column,
protected fields never ignored. **Revised** to source-specific configuration at the owner's request (D5-41). **Not
implemented**. Implementation is
**not authorised inside PR #10**; this is a separate task. Supersedes the DQ-12 section of
`Proposals_DQ11-DQ14_03_Nov_26_150000.md`.

## 1. Today (safe rule, unchanged)

`process._repeated_timestamps`: rows of one instrument sharing a timestamp are exact duplicates only when **every
source column** is identical (`canonical.DUPLICATE_RULE`); otherwise all are kept as conflicting observations.
AKZOINDIA's `index` column (a per-download row counter) differs between its two copies of 17-Oct-25 and 24-Oct-25,
so all 750 repeated timestamps are conflicts although 428 have identical date/time, OHLC and volume.

## 2. Proposal (revised: source-specific, not global)

The owner prefers **source-specific configuration** (03-Nov-26, D5-41): the same column name can mean different things
in different sources. There is therefore **no global list** and no global default.

### 2.1 Where the list lives and how it is associated

| Route into Q-MAP | Where the list is configured | How it is tied to the data |
|---|---|---|
| Data Management or command line with a **source profile** (`.toml`) | new optional profile section `[duplicates] ignore_columns = ["index"]` | the profile is already snapshotted and immutable per version (`source_profiles`); adding or changing the list is a **new profile version**, so the processing version (`<profile>@<version>+<cleaning code>`) changes and the result is a **new dataset**; old datasets are untouched |
| **Folder** sources (Sources screen, automatic interpretation) | new optional folder setting "Technical columns to ignore for duplicates" on the `data_sources` row (schema migration, nullable text, JSON list) | copied into the folder's `settings_snapshot` (recorded with every scan) and into the profile the automatic interpretation generates for each file; part of the scan's inputs fingerprint, so changing it re-interprets the folder's files on the next scan and creates new datasets |
| A file in a folder that also has a confirmed profile/answer | the profile/answer wins over the folder setting | recorded which one was used |

Precedence: explicit profile > folder setting > nothing. A list never applies to another source. Approved first entry:
`index`. The default for every source is an empty list (today's behaviour).

### 2.2 Rules

1. **Exact names**, case-insensitive after header trimming; no patterns or wildcards.
2. **Protected fields, never ignored** whatever a list says: the columns mapped to date, time or datetime, open, high,
   low, close, volume, symbol and exchange. A listed name that maps to one of them is refused when the profile or
   folder setting is saved/loaded, with an error naming it; nothing is processed with an invalid list.
3. **Comparison:** rows of one instrument sharing a timestamp are exact duplicates when every column except the
   listed ones is identical. The first is kept; the others are removed from the standardised copy only. Rows that
   still differ remain conflicting observations, exactly as today.
4. **Original source preserved:** source files and stored originals never change. Listed columns stay in the
   standardised copy as preserved `x_` columns with the kept row's value.
5. **Audit of every ignored difference and every removed row:**
   - `exact_duplicates_removed` (INFO) names the source and the list in force; per removed row: source row, kept
     source row, and each ignored column with both values (e.g. `index 1500 -> 1504`).
   - Provenance transformation step with the rule text, the list and where it came from (profile version or folder).
   - Issues report and scan report: the files where the list changed the outcome, with counts (duplicates removed
     because of the list; conflicts that remain).
6. **Reversibility:** removing the column from the source's list and loading again gives today's behaviour (new
   datasets); earlier datasets, attempts and runs stay as they are.

## 3. Expected effect on the owner's files

AKZOINDIA: of 750 repeated timestamps, 428 become exact duplicates (one copy removed, each audited) and 322 stay
conflicts. The file remains rejected in any case until DQ-13 (two bars of 08-Nov-25) is resolved. Other files: no
`index` column, no change.

## 4. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A listed column hides a real difference | explicit list, empty by default; protected fields; every ignored difference audited |
| Silent behaviour change on rescans | list in the fingerprint: a change creates new datasets, never rewrites |
| Name collision (a meaningful column called `index` in another source) | the list is per source (profile or folder), never global; the audit shows the values |

Effort: about one day with tests (duplicate rule, profile section, folder setting and its migration, precedence,
protected-field refusal, audit content).

## 5. Decisions requested

1. Approve the association in 2.1 (profile section; folder setting; profile wins).
2. Confirm the folder setting is edited in the Sources screen (and the CLI), recorded with every scan.
