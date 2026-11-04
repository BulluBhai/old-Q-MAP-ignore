# Q-MAP v0.1: corrections after the independent audit of PR #12 head `3f4faea` (04-Nov-26)

Prepared 04-Nov-26 by Claude (developer). The independent read-only audit was carried out by ChatGPT on PR #12 head
`3f4faea`. Reference: Master Blueprint v1.35. Branch `claude/epic-darwin-33o518` (PR #12). Nothing has been merged.

Exclusions held: no MIQP, no DQ-11/12/14 implementation, no DuckDB, no Opportunity Scanner, backtesting or portfolio
work, no blanket reprocessing, no dataset-identity change, and no processing, cleaning-code (`c2`), rules or
fingerprint-scheme (`vs2`) version change. QLOPB calculations are unchanged.

## 0. Builds

| Item | Value |
|---|---|
| Code commit (last program change) | `919c697` |
| Build fingerprint (program files, see `core/build.py`) | `3fa925abf95b` (full `3fa925abf95b69e748361d81c3fb08f612bd75b82b731404bcc28459cdf1a8bc`) |
| Previous code under test | `5c779e6`, fingerprint `ec8398fcfddd` (PR head `3f4faea`) |
| PR head | see the commit table below. Commits after `919c697` change tests, acceptance fixtures, documents and `.gitattributes`, but no program file, so the fingerprint is unchanged |

**Commit history `3f4faea..0b33482` (reconciliation 04-Nov-26):**

| Commit | Classification | Contents |
|---|---|---|
| `a834d6a` | **Application code + tests** | A1, A2, B3: `core/config.py`, `data_engine/auto_interpret.py`, `discovery.py`, `ingest.py`, `storage/files.py`, `recovery.py`, `registry.py`, `storage_class.py`; tests `test_scan_change_detection.py`, `test_data_root_containment.py` |
| `919c697` | **Application code + tests** (last program change) | C4: `data_engine/process.py`, `qmap_gui/messages.py` (three check-name texts); tests `test_multi_instrument_timeframes.py`, `test_dq7_sparse_daily_characterisation.py` (C5), `test_placement_and_migration.py` (D6), `test_qlopb_research_engine.py` (D7) |
| `b2b5e93` | **Tests + acceptance fixtures + documents + `.gitattributes`**; no program file | one test added to `test_scan_change_detection.py` (W19 files); fixtures `docs/acceptance_testing/w19_same_size_files_04_Nov_26/version_A/ and version_B/NSE_SAMESIZE.csv`; `.gitattributes` (`-text` for those fixtures); decision log, register, final audit, known limitations, this record, Windows manual |
| `0b33482` | **Documents only** | final audit, known limitations, register, this record, Windows manual |

The interval `3f4faea..0b33482` as a whole therefore changes application code, tests, fixtures, documents and
`.gitattributes`; it is **not** documentation-only. Only `0b33482` (and the reconciliation commit that adds this
table) is documentation-only. `git diff 919c697 0b33482 -- Application pyproject.toml '*.py' ':!Tests'` is empty:
no program file changed after `919c697`, so the build fingerprint (program files only: `Application/**/*.py`,
top-level `.py`, `pyproject.toml`) stays `3fa925abf95b`; recomputed on `0b33482`: `qmap 0.1.0rc1 / c2 build
3fa925abf95b`. The git part of a build label shows the checked-out commit, so it differs between these commits while
the fingerprint does not.

## 1. Defects corrected

| Item | Defect | Correction | Regression tests | Status |
|---|---|---|---|---|
| A1 | `discovery._scan_one` skipped a file when its size and modification time matched the last observation, without calculating the current SHA-256. D5-08 makes the checksum part of the unchanged-file test | The fast path is removed: the current SHA-256 is always calculated before a file counts as unchanged. A file that changes after Q-MAP examined it is never registered: `ingest_file`/`receive_file` take `expected_sha256` and refuse (`E_CHANGED_SINCE_EXAMINED`; receipt `failed`, no dataset) if the checksum differs. The existing check after loading stays as a second line of defence | `Tests/integration/test_scan_change_detection.py`: (a) same contents, size and time → unchanged and skipped, with the checksum calculated now; (b) changed contents, same size, restored time → `changed`, processed, new raw dataset under its own checksum; (c) file rewritten after interpretation and before loading → failed, **nothing** registered; the next scan loads the new contents; sources byte-identical after scans. Tests (b) and (c) fail on the earlier code | Done and tested |
| A2 | `_inputs_fingerprint` omitted settings that change the outcome | Added: the resolved `timeframe_sampling`, the requirement set of the automatic profiles and its `require_volume`, `max_file_size_mb` and the cleaning-code version. Each is included **only when it differs from the value in force when the fingerprint was defined**, so every fingerprint made under the current settings is unchanged and no file is re-evaluated in bulk. Other settings reviewed: the validation limits were already included; `stale_minutes`, `log_level` and the folders cannot change a scan outcome; the run date is handled by `retry_on`; profile folders are not used by the automatic interpretation | Same file: default settings give exactly the old fingerprint (formula reproduced in the test); each setting change gives a new fingerprint; the next scan re-evaluates an unchanged file after a `timeframe_sampling` or `require_volume` change, then skips it again | Done and tested |
| B3 | `Settings.data_path` checked the text of a path only, so a symbolic link or Windows junction below Q-MAP_DATA could lead outside it. `safe_remove` cleared the read-only flag through a link, changing the file it points to. Recovery's file walk (`rglob`) follows junctions on Python 3.11 for Windows | `data_path` resolves the path (links and junctions followed) and raises `UnsafeDataPath` (a `ValueError`) unless it stays inside the resolved data root. `safe_remove` never touches a link or junction. Recovery walks with `os.walk`, without following, and skips links and junctions. Each unsafe registry path is reported in `problems` and skipped, so one bad entry never stops recovery at run start. The storage-class screens show an unsafe path as a blocker | `Tests/unit/test_data_root_containment.py` (17): malformed paths; a folder link or junction leading out is refused; a file link leading out is refused; a link that stays inside is accepted; `safe_remove` leaves both the link and the read-only target untouched; recovery does not walk or delete through a link or junction; a registered path that now leads outside is reported, and recovery and `verify` carry on. The two junction tests run on Windows (CI) only. On Windows without the symbolic-link privilege, the symbolic-link tests skip | Done and tested (Linux). Junction and Windows symbolic-link behaviour: CI only |
| C4 | Several instruments in one file: one timeframe was measured on the whole file and given to every instrument | See section 2. The file is refused when any instrument measured on its own rows differs | `Tests/integration/test_multi_instrument_timeframes.py` (6) | Done and tested. **Owner confirmation requested (D6-20)** |
| D6 | Migrations 9 and 10 were not pinned | Pinned with their SHA-256 values, which are unchanged since `3876772` and `66895cc` (verified across the git history of `schema.py`). `MIGRATION_PINS` covers every migration, and `test_every_migration_is_pinned` fails when a migration has no pin | `Tests/unit/test_placement_and_migration.py` | Done and tested |
| D7 | `Tests/qlopb/test_qlopb_research_engine.py` compared `src.read_bytes()` with itself | The bytes, SHA-256 and modification time are captured before the run and compared afterwards | same test | Done and tested |

Sources: no original market file is opened for writing. A1(a) to (c) and the existing tests check this byte for byte.

## 2. C4: files with several instruments

**Behaviour established** with synthetic files (symbol column, profile `symbol_from = "column"`, on the code before
this change):

| File | Before | Now |
|---|---|---|
| AAA daily (120 rows), then BBB weekly (120 rows) | Both registered **MIXED** (each is consistent on its own) | Rejected: `instrument_timeframes_differ` (AAA: 1D; BBB: 1W) |
| The same rows interleaved by date | Both **MIXED** | Rejected, same reason |
| AAA daily (120 rows), then BBB weekly (8 rows) | Both registered **1D**, no warning: **BBB was silently given AAA's timeframe** | Rejected, same reason |
| Both daily | 1D, 1D | Unchanged (INFO `instrument_timeframes_agree`) |
| One instrument with only 2 rows | Given the file's timeframe silently | Accepted, with WARNING `instrument_timeframe_not_verified` naming the instrument |
| One instrument | — | Unchanged (no per-instrument check) |

**Implementation.** `process.py`: once rows are grouped, and only when there are two or more instruments, the
approved DQ-7 inference (`infer_interval`, same configuration) is applied to each instrument's own rows in file order.
If any measurable instrument's result differs from the file-level result, one ERROR check rejects the file before
anything is written. The check lists every instrument's interval and advises splitting the file. The method itself
is unchanged. The per-instrument results are kept in the inference record (`per_instrument`).

**Impact.** New loads only. Datasets already registered from multi-instrument files are not re-examined or changed.
Under the existing reuse rule, an unchanged file with an accepted earlier attempt keeps that attempt. The folder scan
handles a file with a symbol column the same way (the automatic profile uses `symbol_from = "column"`).

**Recommendation.** Keep the refusal for v0.1 (D6-20). A later option is to register each instrument with its own
measured timeframe. That needs the owner's approval because it changes how datasets are produced from one file.

## 3. C5: sparse daily and weekly observations (investigation only; method unchanged)

`Tests/integration/test_dq7_sparse_daily_characterisation.py` (16 characterisation tests) records the current results
for synthetic files of 200 observations:

| Steps between observations (calendar days) | Registered | Base step present? |
|---|---|---|
| 1,1,1,1,3 (weekdays); daily with some gaps | 1D | yes |
| 7 | 1W | yes |
| 2 only; 2,2,3 (Mon/Wed/Fri); 3 only; 4 only | **1D, CONSISTENT** | **no 1-day step anywhere** |
| 5; 6; 9; 10; 5 and 10; 5,6,8,9 | **1W, CONSISTENT** | **no 7-day step anywhere** |
| 11; 14 | 11d; 14d (not 2W) | yes, as their own label |
| alternating 2 and 9 | MIXED | — |

**Cause.** A daily-or-longer block is labelled from its most common step in calendar days (1-4 → 1D, 5-10 → 1W,
26-35 → 1M, 85-95 → 1Q, 360-370 → 1Y) **before** the agreement rule runs. The rule "the interval itself occurs in the
block, or is the block's own most common step" then compares labels, not steps. A block of 2-day steps is labelled 1D,
so 1D is its "own most common step". In practice the DQ-7 requirement that the base interval itself must occur is
enforced for intraday data (minutes) but not for daily-or-longer data.

**Can sparse daily data be confused with another timeframe?** Yes, in one direction. Daily observations taken every
5-10 calendar days (for example weekly samples of a daily series, or a sparse daily file with long holiday gaps
throughout) are registered as **1W**. They would then be offered to weekly analyses (MA Affinity weekly) as if they
were weekly bars. Observations every 2-4 days are registered as 1D, which is a correct description of daily data with
missing days. Real weekly data are unaffected.

**Recommendation (not implemented; owner decision D6-21).** For daily-or-longer labels, require the label's base step
to occur in the block, as already required for intraday data: a 1-day step for 1D, a 6-8-day step for 1W, and the
equivalents for 1M, 1Q and 1Y. Otherwise the block keeps its plain day label (for example `5d`), so that a file of
5-day steps is not registered as 1W.
**Impact:** no registered dataset changes (no reprocessing). The rule would apply to new loads only. Files of
regular 2-4-day or 5-10-day steps would get labels such as `2d` or `5d`, and analyses that need 1D/1W/1M would refuse
them. Earlier classifications can be identified read-only from their recorded blocks, as done for OW-41. This touches
the approved DQ-7 method, so it needs the owner's explicit approval. It is related to OW-33 (sparse one-bar dates),
which is still deferred.

## 4. OW-35: review of the QLOPB integration

**Independence limitation (stated plainly).** This review was carried out by Claude, the developer who performed the
migration. It is therefore **not independent**. What it adds is a reproducible comparison against the original
repository, which ChatGPT or the owner can re-run (commands below). An independent review of S-1 to S-3 and of the
integration is still open (OW-35 stays open).

**Sources.**

| | Repository `BulluBhai/QLOPB` |
|---|---|
| Original program (`main`) | `be6d945` "Add QLOPB context and Claude Code instructions": MA Affinity Scanner V2 **without** S-1 to S-3 |
| Safeguarded source used for the migration | `6cbadc79fac6fb338eadfa7d260ff5cb459895f5` on branch `claude/youthful-bardeen-11wtok` = `be6d945` + `9b4702d` (S-1, S-2, S-3) + `e97c7b8` (stray `__pycache__` removed) + `6cbadc7` (S-2 weights checked before the no-records return). Not merged into QLOPB `main` |
| Q-MAP copy | `Application/qlopb` (`qlopb.SOURCE_COMMIT = 6cbadc79…`) |

**File-by-file comparison** (generated 04-Nov-26 from a fresh clone of `BulluBhai/QLOPB`). The Q-MAP file is shown
with its `from qlopb.<package>` imports turned back into `from <package>`. CRLF line endings are normalised.

The last column says whether the file is identical at QLOPB `main` `be6d945`. Where it says "no", the difference
comes only from safeguard commits `9b4702d` and `6cbadc7`.

| File | SHA-256 at 6cbadc7 | Q-MAP file, imports reverted | Identical | Import lines changed | Same as QLOPB main be6d945 |
|---|---|---|---|---|---|
| `analysis/__init__.py` | `e3b0c44298fc` | `e3b0c44298fc` | yes | 0 (empty file) | yes |
| `analysis/affinity_engine.py` | `6523da94232e` | `6523da94232e` | yes | 2 | no (safeguard change) |
| `analysis/combination_engine.py` | `ee3869cd9913` | `ee3869cd9913` | yes | 0 | yes |
| `analysis/comparison_engine.py` | `f3fc331b3c99` | `f3fc331b3c99` | yes | 0 | yes |
| `analysis/interaction_engine.py` | `8c6242800e10` | `8c6242800e10` | yes | 1 | yes |
| `config/__init__.py` | `e3b0c44298fc` | `e3b0c44298fc` | yes | 0 (empty file) | yes |
| `config/settings.py` | `da07c55eb886` | `da07c55eb886` | yes | 0 | no (safeguard change) |
| `core/__init__.py` | `e3b0c44298fc` | `e3b0c44298fc` | yes | 0 (empty file) | yes |
| `core/data_engine.py` | `3e02ebe190e2` | `3e02ebe190e2` | yes | 3 | no (safeguard change) |
| `core/research_engine.py` | `2627ce4b533f` | `2627ce4b533f` | yes | 14 | yes |
| `core/timeframe_engine.py` | `656f111d2279` | `656f111d2279` | yes | 1 | yes |
| `core/validation.py` | `150ad9093546` | `150ad9093546` | yes | 0 | no (safeguard change) |
| `gui/__init__.py` | `e3b0c44298fc` | `e3b0c44298fc` | yes | 0 (empty file) | yes |
| `gui/research_controls.py` | `e809c3611083` | `e809c3611083` | yes | 2 | no (safeguard change) |
| `references/__init__.py` | `96bdfef10cab` | `96bdfef10cab` | yes | 0 | yes |
| `references/bollinger_bands.py` | `596cbf12e072` | `596cbf12e072` | yes | 0 | yes |
| `references/camarilla.py` | `aae932d1fcee` | `aae932d1fcee` | yes | 0 | yes |
| `references/cpr.py` | `cd97eb53cdb5` | `cd97eb53cdb5` | yes | 0 | yes |
| `references/moving_average.py` | `a95915b67cfc` | `a95915b67cfc` | yes | 0 | yes |
| `references/other_references.py` | `ea4117e4c050` | `ea4117e4c050` | yes | 0 | yes |
| `references/pivot_points.py` | `9ee23d3e6836` | `9ee23d3e6836` | yes | 0 | yes |
| `references/previous_levels.py` | `4e38e5a6dab7` | `4e38e5a6dab7` | yes | 0 | yes |
| `reports/__init__.py` | `e3b0c44298fc` | `e3b0c44298fc` | yes | 0 (empty file) | yes |
| `reports/chart_report.py` | `31cb42339633` | `31cb42339633` | yes | 2 | yes |
| `reports/excel_report.py` | `7251ab516e6c` | `7251ab516e6c` | yes | 1 | yes |
| `reports/pdf_report.py` | `196c2a2eae37` | `196c2a2eae37` | yes | 1 | yes |
| `storage/__init__.py` | `e3b0c44298fc` | `e3b0c44298fc` | yes | 0 (empty file) | yes |
| `storage/file_provider.py` | `7f6b606c6cd8` | `7f6b606c6cd8` | yes | 1 | yes |
| `validation/__init__.py` | `e3b0c44298fc` | `e3b0c44298fc` | yes | 0 (empty file) | yes |
| `validation/is_oos.py` | `cd699d936a91` | `cd699d936a91` | yes | 0 | yes |
| `validation/robustness.py` | `a46c036b267b` | `a46c036b267b` | yes | 0 | yes |
| `validation/statistical_tests.py` | `fa43b1427edc` | `fa43b1427edc` | yes | 0 | yes |

All 32 files are identical to `6cbadc7` apart from 28 import lines. The changed lines are listed below; each is a
`from qlopb.…` import, and the line count of every file is unchanged:

```text
analysis/affinity_engine.py: from qlopb.config.settings import SettingsError, weight_problems
analysis/affinity_engine.py: from qlopb.validation.statistical_tests import binomial_pvalue_greater, reliability_score
analysis/interaction_engine.py: from qlopb.config import settings as cfg
core/data_engine.py: from qlopb.config import settings as cfg
core/data_engine.py: from qlopb.core.validation import ohlc_inconsistent_mask
core/data_engine.py:     from qlopb.storage.file_provider import safe_name   # local import keeps layers simple
core/research_engine.py: from qlopb.analysis.affinity_engine import score_window
core/research_engine.py: from qlopb.analysis.interaction_engine import build_interaction_records, detect_interaction_episodes
core/research_engine.py: from qlopb.config import settings as cfg
core/research_engine.py: from qlopb.config.settings import MAResearchSettings
core/research_engine.py: from qlopb.core.timeframe_engine import resample_ohlc
core/research_engine.py: from qlopb.core.validation import check_data_for_settings, validate_ohlc_frame
core/research_engine.py: from qlopb.references.moving_average import compute_ma
core/research_engine.py: from qlopb.storage.file_provider import FileProvider, RunLog, make_stamp, safe_name
core/research_engine.py: from qlopb.validation.is_oos import compute_split, consistency, freeze_top_n, rank_candidates
core/research_engine.py: from qlopb.validation.robustness import near_duplicate_pairs, neighbour_summary
core/research_engine.py:     from qlopb.core.data_engine import LoadOptions, load_file, save_processed
core/research_engine.py:             from qlopb.reports.chart_report import make_charts as _charts
core/research_engine.py:             from qlopb.reports.excel_report import write_excel
core/research_engine.py:             from qlopb.reports.pdf_report import write_pdf
core/timeframe_engine.py: from qlopb.core.data_engine import infer_frequency
gui/research_controls.py: from qlopb.config import settings as cfg
gui/research_controls.py: from qlopb.config.settings import MAResearchSettings, SettingsError
reports/chart_report.py: from qlopb.config import settings as cfg
reports/chart_report.py: from qlopb.references.moving_average import compute_ma
reports/excel_report.py: from qlopb.config import settings as cfg
reports/pdf_report.py: from qlopb.config import settings as cfg
storage/file_provider.py: from qlopb.config import settings as cfg
```

Not migrated: `gui/main_window.py`, `launcher.py` (QLOPB's own window and launcher; the Workbench replaces them),
`tests/*.py` (ported to `Tests/qlopb`, imports adapted; test files are not part of the engine identity check),
sample data, outputs and documents.

**Reproduce.**

```bash
git clone https://github.com/BulluBhai/QLOPB qlopb_src
```

```bash
git -C qlopb_src checkout 6cbadc79fac6fb338eadfa7d260ff5cb459895f5
```

Then, for each file `F` listed above, compare `qlopb_src/F` with `Application/qlopb/F` after replacing `from qlopb.`
with `from ` in the Q-MAP copy. The comparison is automated by
`Tests/qlopb/test_qlopb_migration_identity.py`, which pins every original SHA-256 value. The values in the table were
recomputed from the clone, not copied from the test.

**Safeguards (diff `be6d945..6cbadc7`, non-test files).**

| | Change | Where it acts in Q-MAP | Finding |
|---|---|---|---|
| S-1 | `validate_ohlc_frame` reports `inf`/`-inf`; the QLOPB loader marks `infinite_price` rows | `ma_affinity.dataset_checks` (readiness FAIL `ma_affinity_prices`) and again inside `run_ma_affinity` | Correct. `np.isinf` is tested after the NaN test, so the NaN message is unchanged. Q-MAP's own ingestion rejects non-finite prices before any dataset exists |
| S-2 | `weight_problems`: finite, not negative, finite total above 0; used by `MAResearchSettings.check`, `score_window` (before the no-records return) and the GUI text | `check_params` → `parse_settings` → `check()`; again in `score_window` | Correct. Weights are still divided by their sum (scheme pending owner review). The test expectations about NaN weights are met |
| S-3 | QLOPB CSV loader: `len(row) != ncols` (was `<`) | Not used: the Workbench never calls QLOPB's loader (Q-MAP ingestion reads source files) | Correct in QLOPB; no effect in Q-MAP |

**Integration review.** `qmap/analytical_engine/ma_affinity.py`:
- Readiness: conflicting observations, more than one bar per time, and MIXED or "earlier, would be MIXED" (D6-18)
  give FAIL. Non-finite prices and too little history give FAIL. Other datasets, gaps and edges give WARN. A FAIL blocks
  the run (`base.py`).
- The engine always runs with `timeframe = "as_loaded"`, and `_settings` raises an error otherwise. No aggregation
  takes place inside the analysis.
- Reports: the Excel Data_Quality sheet and the PDF heading carry the Run ID, build and dataset checksum
  (`test_ma_affinity_workbench`, which reads the PDF).

No defect was found. Observations (not changed): pandas `dayofweek` deprecation warnings (OW-36); p-values are not
corrected; Directed IR and the weight scheme are still pending (printed in every report).

**QLOPB's own tests re-run on 04-Nov-26** (CPython 3.11.15): `6cbadc7` **107 passed**; `be6d945` **96 passed**.

## 5. Decision-record reconciliation (E8, E9)

| Earlier decision | Later owner instruction that supersedes it | Code (unchanged here) |
|---|---|---|
| D5-15 (DQ-2): a file name that contradicts an exchange/symbol column is **rejected** | **DQ-8**, owner instruction 03-Nov-26, recorded as D5-26 under "Owner instruction DQ-7 to DQ-10 (approved 03-Nov-26)"; design conflict C-6 in `docs/architecture/Data_Automation_DQ7-DQ10_Plan_03_Nov_26_090000.md` | Column used, disagreement reported as a warning (`name_column_disagreement`), file READY (`3876772`) |
| D5-18: the crypto venue is **always asked** | **DQ-8** (no questions for the exchange), recorded as D5-27; plan conflict C-9 ("This replaces D5-18's venue question"). DQ-11 (D5-46) later approved separate category and venue fields in principle (not implemented in v0.1) | Category `CRYPTO`, venue recorded as unknown, warning `crypto_venue_unknown` |

**Gap:** the repository records the DQ-7 to DQ-10 instruction as approved, but it does **not** hold the owner's
written answers to the plan's questions 4 (C-6) and 6 (C-9). The supersession is recorded in the decision log (D6-19)
and needs Sandeep's confirmation. No code behaviour was changed.

## 6. Owner decisions required (one summary)

| Ref | Item | Implemented now | Owner status |
|---|---|---|---|
| D3-15 | Grey "Waiting - its dates are not allowed yet" row and summary text for files held back only by the future-date limit | Yes (since PR #2) | **Approval pending**: implemented before approval |
| D6-18 | MA Affinity refuses an earlier-classified dataset that the corrected DQ-7 comparison would call MIXED | Yes (safer default, reversible) | **Proposed, not approved**. Not removed |
| D6-19 | D5-15 and D5-18 superseded by DQ-8 (D5-26, D5-27) | Code already follows DQ-8 | **Confirmation requested**: the written answers to plan questions C-6/C-9 are not in the repository |
| D6-20 | Multi-instrument files with differing per-instrument intervals are refused (C4) | Yes (safer default, reversible) | **Confirmation requested** |
| D6-21 | DQ-7 for daily-or-longer data: require the base step to occur (C5) | **No** (recommendation only) | **Decision requested** |
| OW-41 | Whether earlier datasets are ever reclassified (needs authorised processing) | No | **Decision requested** |

## 7. Test results

**Local** (Linux container, CPython 3.11.15, Tk 9.0, Xvfb; `QMAP_REQUIRE_GUI_TESTS=1 xvfb-run -a python -m pytest -q
-p no:cacheprovider`) on code commit `919c697` plus the final test/document commit (program files unchanged, same build): **1340 passed, 2 skipped, 0 failed** (212 GUI tests passed). The code commit alone gave 1339 passed, 2 skipped; the extra test checks the W19 acceptance files. The 2
skips are the Windows-junction tests, which exist only on Windows.

New tests: 53 (A1/A2 13 including the W19 files, B3 17, C4 6, C5 16, D6 1).

**Earlier totals explained.** Each count was obtained by collecting the tests at that commit (`pytest --collect-only`,
04-Nov-26).

| Commit | Tests | Why |
|---|---|---|
| `5eec5b3` | 1,270 | Final code of the 03-Nov-26 closure report |
| `1291d63` | 1,286 | +16: DQ-7 calendar-unit fix (`test_dq7_calendar_units`) |
| `5c779e6` | 1,288 | +2: identification of earlier classifications (`test_dq7_correction_reuse`). This is the code that was under test for build `ec8398fcfddd` |
| `cbca66b` / `3f4faea` | 1,289 | +1: test only (a change of a folder's inputs re-interprets an unchanged file). No program change, same fingerprint |
| `919c697` + final test commit | 1,342 (1,340 run + 2 Windows-only) | +53: this correction cycle |

**CI (GitHub Actions, independently verifiable).** On the previous head `3f4faea`: run 95 (push) and run 96
(pull_request) **success**, both Windows and Ubuntu jobs, Python 3.11. Run 96:
https://github.com/BulluBhai/Q-MAP/actions/runs/41762511637. On head `b2b5e93` (code `919c697`, build `3fa925abf95b`): run #100 (`41772097006`) **success**. Windows: 1,341 passed, 1 skipped (macOS/Linux-only hard-link test), 0 failed. Ubuntu: 1,235 passed, 107 skipped (105 window tests without a display, 2 Windows-junction tests), 0 failed. https://github.com/BulluBhai/Q-MAP/actions/runs/41772097006. Runs #97-#99 also succeeded. On head `0b33482` (documents only): run #102 (`41800140103`) **success**. Windows: 1,341 passed, 1 skipped, 0 failed. Ubuntu: 1,235 passed, 107 skipped, 0 failed. These totals were read from run #102's own job logs; they equal run #100's because `0b33482` changes no test or program file. https://github.com/BulluBhai/Q-MAP/actions/runs/41800140103 (run #101, push, also succeeded).
