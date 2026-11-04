# Q-MAP v0.1: known limitations and release boundaries

Release candidate `0.1.0rc1`, prepared 03-Nov-26. Reference: Master Blueprint v1.35. Target maturity: **controlled
analytical use** by the Project Owner after Windows/IDLE acceptance. **Not production-ready.**

## 1. What v0.1 contains

| Area | In v0.1 |
|---|---|
| Database Manager | Sources (folder discovery, automatic interpretation, idempotent re-scans, questions only for real ambiguities, overlap/conflict reports), Data Management (single files with a profile), Datasets and Storage (Permanent/Temporary, reversible reject, derive weekly/monthly/quarterly/yearly from daily) |
| Data quality | Validation with hard failures, warnings and notes; timeframe inference (DQ-7); instrument identification and alias registry (DQ-8); exact-duplicate removal and conflict retention (DQ-10); overlap reporting (DQ-1, DQ-9) |
| Analytical Workbench | **MA Affinity (QLOPB MA Affinity Scanner V2)**, calculations unchanged, on registered daily/weekly/monthly datasets; Dataset Summary (descriptive utility) |
| Reproducibility | Run ID and own folder per run; Run_Metadata with parameters, input datasets and checksums, lineage, readiness warnings, method source and **code build** (version + source fingerprint + git commit/modified) |
| Data protection | Original source files never written; stored copies checksum-verified; recovery after interruption |

## 2. Release boundaries (excluded from v0.1 by owner decision)

| Excluded | Status |
|---|---|
| MIQP Market Intelligence (regime, breadth, sector, stock intelligence) | Not developed; no code or specification in the repositories; regime methodology is a Blueprint §17 open decision |
| DQ-11 asset category / venue | Approved design, separate task |
| DQ-12 source-specific ignore-columns | Approved design, separate task |
| DQ-14 full-file finding may set MIXED | Approved, separate task |
| OW-33 Option C, `vs3`, reprocessing, dataset identity changes | Not authorised. The read-only OW-33 impact report stays on its own branch for independent review |
| New quantitative methodologies; QLOPB pivots, CPR, Camarilla, Bollinger, combinations | Not in v0.1 |
| Provider APIs, direct cloud connectors, scheduled scans, DuckDB, Research Library screen, run reuse, Opportunity Scanner, backtesting, portfolio/risk | Future roadmap (Blueprint §15) |

## 3. Known limitations

### 3.1 Analysis (MA Affinity)

- Results **describe the past**; they are not trading signals or predictions.
- Many candidates are tested; p-values are **not corrected** for multiple comparisons. Neighbouring MA periods are
  near-duplicates; longer forward windows overlap.
- **Pending owner review (QLOPB):** Directed IR (forward-return component) and the affinity weight scheme; how
  incomplete first/last aggregated bars should be treated; time-zone edge cases. Kept exactly as in QLOPB V2 and
  printed in every report.
- QLOPB's own notes say intraday MA Affinity research is not validated; v0.1 therefore offers only daily, weekly and
  monthly datasets. Quarterly is not offered (it was not in the approved scope, although it was shown to be equal).
- One dataset per run (as in QLOPB). No cross-instrument comparison screen.
- **Start date on weekly/monthly data** (found in the final audit): a period filter keeps every bar whose date (the
  last session of the week or month) falls inside the period. With a start date in the middle of a week, that week's
  bar is kept and contains the sessions just before the start date. This uses earlier data, never later data (no
  look-ahead). For exact boundaries, start on the first trading day of a week or month. Dataset Summary behaves the
  same way.
- The standalone QLOPB program in its own repository (`main`) does not contain safeguards S-1..S-3; they are on its
  branch `claude/youthful-bardeen-11wtok` and in Q-MAP. Its results on clean data are the same. Its own file loader
  keeps the first row of a repeated timestamp and lists the others as rejected; Q-MAP never does this (conflicting
  rows are kept, flagged and block MA Affinity). On files with repeated timestamps the two can therefore differ.
- QLOPB's three safeguards (S-1 infinite prices, S-2 weights, S-3 extra CSV values) have **not been independently
  reviewed** yet. S-3 applies to QLOPB's own file loader, which Q-MAP keeps (with its tests) but does not use.
- The migrated engine was developed on pandas 2; this candidate was tested with pandas 3.1, which prints deprecation
  warnings (no effect on results in the tests). A future pandas may need a compatibility update.
- Weekly/monthly equivalence with QLOPB's aggregation was shown on one real daily file (228 bars) and a 16-year
  synthetic series with edge periods; longer real files are covered only by your acceptance checks V7-V12.

### 3.2 Data

- No trading calendar (OD-5): incomplete days and periods cannot be confirmed; daily bars cannot be built from
  intraday data. First/last weekly/monthly periods may be incomplete (flagged).
- No corporate-action adjustment (OW-05); adjustment status is unknown unless the source says so.
- Bar-time convention (start vs end of bar) is not detected (OW-26). Unexplained multi-day gaps are only warned
  (OW-27).
- Conflicting observations are kept and reported, never resolved (DQ-1, DQ-10). MA Affinity refuses datasets that
  contain them in the chosen period; Dataset Summary runs with a warning.
- OW-33: a small section with another interval may or may not make a dataset MIXED depending on the sample (DQ-14
  pending). The full-file check still warns.
- **Daily file with a few two-bar dates** (found in the final audit; same area as OW-33/DQ-14): if some dates of a
  daily file carry a second bar at another time, DQ-7 measures only same-date steps and registers the file as intraday
  (for example "30 minutes"), without a warning. Nothing is lost or changed, MA Affinity refuses it (timeframe not
  supported) and weekly/monthly derivation refuses it (needs daily). Dataset Summary would describe it as intraday.
  Changing this needs the DQ-14/OW-33 decision; not changed in v0.1.
- **DQ-7 correction of 04-Nov-26 (D6-15)**: files mixing daily, weekly, monthly, quarterly or yearly sections are now
  MIXED when the sampled blocks land in both sections (before: wrongly one timeframe). Datasets registered earlier are
  not reclassified automatically (OW-41). A section too small to be sampled can still be missed (same limit as OW-33).
- DQ-11/DQ-12 not built (see section 2). Thousands separators and decimal commas are not read automatically (OW-21);
  multi-symbol files are usually asked, not inferred (OW-22).

### 3.3 Platform and operation

- **Windows/IDLE acceptance is outstanding** (V1-V14, W1-W18, A4-A8). GUI tests ran on Linux (virtual screen) and
  on GitHub's Windows runner; neither replaces your session.
- The code build is recorded, but a ZIP download has no git commit: the source fingerprint is then the identifier.
- Keep Q-MAP_DATA on a local disk (file locks); keep paths short (Windows 260-character limit).
- `recover`, `verify` and `restore-raw` exist only on the command line (OW-07).
- Each analysis creates a new run; equivalent earlier results are not reused (OW-15).

## 4. What to avoid until further development

- Do not treat MA Affinity rankings as validated strategies or use them for live trading decisions.
- Do not run gap-, session- or adjustment-sensitive research (opening/closing studies, daily values from intraday)
  without checking the data yourself.
- Do not delete or edit files inside Q-MAP_DATA by hand; use Datasets and Storage.
- Do not use Q-MAP with your real folders until the acceptance in the Windows guide has passed.

## 5. Repository inventory (separate applications)

| Repository | What it is | Relation to Q-MAP v0.1 |
|---|---|---|
| `BulluBhai/Q-MAP` | This platform | The release candidate |
| `BulluBhai/QLOPB` | **QLOPB, the MA Affinity / price-behaviour application** (standalone tkinter program) | Its engine (commit `6cbadc7`) is migrated unchanged into `Application/qlopb`; the repository stays the reference baseline (Blueprint §14.3) |
| `BulluBhai/IndexAnalytics_v2` | **NSE Index Analytics application** (Streamlit): index constituents, market cap, NSE weight caps, industry, concentration, similarity | Not used in v0.1. Its constituent-processing engine is a **possible future MIQP / v0.2 opportunity** (sector and stock intelligence); it needs decisions on a constituent dataset type in the registry, data source and licensing, weight-cap rule provenance, and the GUI choice |
| `BulluBhai/BulluBhai-IndexAnalytics` | A larger version of the same NSE Index Analytics application (screens labelled v4.1); same date as IndexAnalytics_v2 | As above |

No MIQP market-regime or breadth material was found in any of these repositories.

## 6. Blueprint version retention

Blueprint v1.35 requires v1.0, v1.1, v1.2 and v1.3 to be retained. On `main`: v1.3 and v1.35. v1.2: only in PR #5
(three documentation files; owner agreed to merge it). v1.0: removed from `main` on 03-Nov-26 (`4592692`) but kept
in the repository history and on the PR branches. **v1.1: never committed to any branch of the repository**; it is
known only from the version-history tables of v1.2-v1.35 ("1.1, 1 November 2026, prior proposed"). It has not been
recreated. If you hold a copy, it can be added as a historical record.
