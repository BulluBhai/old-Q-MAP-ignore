# PR #9: reconciliation with Master Blueprint v1.35 and branch-preparation review (08-Nov-26)

Branch `claude/happy-brahmagupta-su6tnr` (PR #9), stacked on PR #4 (`claude/adoring-curie-5h2mx4`). Governing
reference: **Q-MAP Master Blueprint v1.35** ([../../Q-MAP_Master_Blueprint_v1.35.md](../../Q-MAP_Master_Blueprint_v1.35.md)),
approved and adopted by the Project Owner on 3 November 2026. This document supplements the
[Blueprint v1.3 implementation audit](Blueprint_v1.3_Implementation_Audit.md) of 02-Nov-26, which stays as the
historical record of the work as audited against v1.3. Nothing here approves a decision, accepts a test or merges a PR.

**Evidence labels.** *Inspected* = read in the code or documents on 08-Nov-26. *Tested here* = run in this session
(Linux container; see section 7). *Verified at PR #10's head* = checked in this session against PR #10's current
head `78323b4` (section 5). *Stated by PR #10* = taken from PR #10's description or commits and **not re-verified**
here. *Owner* = recorded as the Project Owner's decision or acceptance.

**Document status.** This is a **current** review record for PR #9. Which other documents are current and which are
historical is listed in section 10.

**Classification** (as required by the 08-Nov-26 instruction): **1** implemented and verified · **2** implemented, not
sufficiently verified · **3** partially implemented · **4** not implemented · **5** not applicable to PR #9 ·
**6** requires an explicit Project Owner decision.

---

## 1. Scope of PR #9

PR #9 adds automatic interpretation of market-data files (rules A-1 to A-9), folder sources with idempotent scans,
overlap and conflict reports, schema migration 8 and the Database Manager **Sources** screen, on top of the existing
ingestion, validation, storage and registry pipeline of PR #4. It does **not** implement all of Blueprint v1.35. The
detailed operating principles that v1.35 added (§8.5.11) are mostly assigned to PR #10 (DQ-7 to DQ-10), which is
stacked on this branch.

## 2. What changed from v1.3 to v1.35 (inspected: full text comparison of the two `.md` files)

| Area | Change |
|---|---|
| Authority text, §19.1, §19.2 | v1.35 governs from 3 November 2026 and supersedes v1.3, v1.2, v1.1 and v1.0; those versions are kept as history |
| "Version authority", paragraph 2 | Now names v1.35 as the primary reference. The v1.3 wording raised as **DQ-6** is not in this paragraph of v1.35. DQ-6 is **not** closed by this (section 2.1) |
| §8.5.11 A-G (new) | Detailed data-ingestion and validation operating principles: automation-first operation, timeframe detection, instrument identification, duplicates, conflict warnings, exchange/venue/asset metadata, traceability |
| §8.5.1-§8.5.10 and all other sections | **Unchanged** (same text, same numbering). Section references in PR #9's code comments ("v1.3 §8.5.x") therefore still point at the same requirements |

### 2.1 DQ-6 and two editorial items in v1.35 (inspected 08-Nov-26; nothing changed in the Blueprint files)

**DQ-6, as originally raised** (v1.3 audit section 10 and the outstanding-work register, 02-Nov-26): v1.3's "Version
authority", paragraph 2, still names v1.2 as the primary reference. Options recorded: "Correct in a v1.3 maintenance
edit / leave". Recommendation recorded: correct both copies together. No explicit closure criterion was written; the
only outcomes it defines are a correction of **both v1.3 copies** or an owner decision to **leave** them.

| Check | Result |
|---|---|
| v1.3 `.md` and `.html`, line 51 | Still say "Version 1.2 is the primary reference for" (unchanged) |
| v1.35 `.md` and `.html`, "Version authority" paragraph 2 | Name v1.35 as the primary reference |
| v1.35 §19.4, last paragraph (`.md` line 2162) | Still says "**Version 1.2** does not establish that the described capabilities are implemented", carried over unchanged from v1.3 |
| Owner decision to close or leave DQ-6 | None found in the decision log, the register or PR #9's discussion |
| `.md` and `.html` copies | Same text in each version (the HTML is the Markdown inside one `<pre>` block; compared after unescaping) |

**Conclusion: DQ-6 stays open.** The evidence does not support closing it: neither recorded outcome has happened, and
v1.35 still contains a stale "Version 1.2" reference of the same kind (§19.4). This supersedes the recommendation to
close DQ-6 given in this document's previous version (commit `f5f3630`).

**Canonical location.** v1.35 §19.1 names `docs/Q-MAP_Master_Blueprint_v1.35.md` and `.html` as the canonical
location, but the approved files are at the repository root on `main` (as v1.3's were). PR #9 does **not** move the
files and does **not** edit the Blueprint: the Blueprint's controlled document-change rules require both copies to be
changed together with a change record, and the files belong to `main`, outside PR #9's scope. Every reference in PR #9's
own documents points to the actual root location (link check, section 7).

**Proposed controlled maintenance change** (for the owner to approve or decline; to be made on its own documentation
branch from `main`, both copies together, recorded in the repository history as a minor editorial correction that
changes no requirement):

| Place (both `.md` and `.html` of v1.35) | Now | Proposed |
|---|---|---|
| §19.1, "Canonical location" | `docs/Q-MAP_Master_Blueprint_v1.35.md` and `docs/Q-MAP_Master_Blueprint_v1.35.html` | `Q-MAP_Master_Blueprint_v1.35.md` and `Q-MAP_Master_Blueprint_v1.35.html` at the repository root |
| §19.4, last paragraph | "Version 1.2 does not establish ..." | "This Blueprint does not establish ..." |
| v1.3 copies, "Version authority" paragraph 2 (DQ-6) | Unchanged historical text | Either leave as historical (v1.35 governs), or add a dated "superseded" note at the top of both v1.3 copies (Blueprint change rule 4: "mark superseded copies clearly") |

## 3. Requirements R1-R30 (v1.3 audit, section 3), re-checked against v1.35

The requirement text behind R1-R30 is unchanged in v1.35, so the mapping stays valid. Classification for PR #9:

| # | Requirement (short) | Class | Evidence | Note |
|---|---|---|---|---|
| R1, R2, R9, R10, R14, R16, R18, R20-R22, R30 | Platform foundation, readiness, validation, storage classes, derived timeframes, Workbench, separation, runs, integrity | 5 | Delivered by PRs #1-#4; full suite passes on this branch (section 7) | Not changed by PR #9, except that readiness now also lists warnings recorded later on a dataset (`catalog._warnings_for`, needed for DQ-1) |
| R3 | Configure source folders and discover files | 1 | `test_folder_discovery.py`, `test_window_sources.py` | Scheduled scans not built (DQ-5) |
| R4 | Interpret unambiguous files without choosing a profile | 2 | `test_auto_interpret.py` (26 test functions), end-to-end test | The owner's Windows/IDLE session of 02-Nov-26 found F-01, F-03 (section 5); fixed in PR #10 (verified at PR #10's head `78323b4`, section 5) |
| R5 | Ambiguity → question or rejection; never guess | 3 | `test_auto_interpret.py`, `test_owner_decisions_dq1_dq2.py` | F-02a (a timeframe answer was used without checking the measured interval) and F-02c (the folder's default exchange was applied to `CRYPTO_` files) break this rule on PR #9 alone; fixed in PR #10 (verified at PR #10's head `78323b4`, section 5) |
| R6 | Record answers; reuse only for a compatible structure | 2 | `test_folder_discovery.py` (answer reused only for the same signature) | F-04: a rules-version change discards answers (safe direction: asked again) and re-registers identical datasets; fixed in PR #10 (verified at PR #10's head `78323b4`, section 5) |
| R7 | Headerless positional reading under documented rules | 1 | DQ-2 tests (6) | Owner decision DQ-2 |
| R8 | Canonical OHLCV; extra fields preserved and reported | 3 | `test_ingest_formats.py`, interpretation evidence | Extra fields kept as text `x_` columns, not typed (OW-20) |
| R11 | Idempotent scans; changes, overlaps and conflicts reported | 3 | `test_folder_discovery.py`, DQ-1 tests | Overlaps are checked only for datasets registered by a folder scan (OW-25; extended to every load path in PR #10, stated by PR #10) |
| R12 | User sees discovered/imported/skipped/rejected and why | 1 | Scan report CSV, Sources screen tests | |
| R13 | Originals never modified | 1 | `test_source_files_are_unchanged_by_all_of_the_above`, checksum checks in discovery tests | |
| R15, R19, R23-R25, R29 | DuckDB, MIQP/QLOPB, result reuse, Research Library, Feature Store, coverage view | 5 | — | Outside PR #9 (QLOPB MA Affinity is in PR #12) |
| R17 | Registry exposes source, identity, provenance | 1 | Schema 8 tables; `test_migration_8_sources.py` | |
| R26 | Provider API adapters | 4, 6 | — | Not started; DQ-3 (providers) is the owner's |
| R27 | Synchronised cloud folders treated as folders | 2 | Code path only | Not tested with a real OneDrive/Google Drive client (OW-23) |
| R28 | Instrument changes, symbol mapping | 4 | — | Alias registry is in PR #10 (stated by PR #10) |
| R31 (new, 08-Nov-26) | A scan never reads outside the chosen folder | 2 | `test_source_folder_containment.py` (5 tests) | **Defect fixed on this branch** (section 6.1). Junctions simulated; not tested on Windows |

## 4. Blueprint v1.35 §8.5.11: requirement-level mapping for PR #9

"PR #10" in the last column means PR #10's description or commits state that it addresses the item; this was
**not re-verified** in this review.

| Ref | v1.35 requirement (short) | Class | PR #9 behaviour (inspected) | Where addressed |
|---|---|---|---|---|
| A1 | Routine cleaning, normalisation, identification, duplicate handling automatic where reliable | 3 | Layout, dates, zone, timeframe and identity are automatic when unambiguous; duplicate timestamps reject the whole file | PR #10 (DQ-10) |
| A2 | Intervention only for material exceptions | 3 | Questions only for ambiguity; but every plain file name (`ICICIBANK.txt`) is asked unless "File name is the symbol" is on (F-01) | PR #10 (suggestion pre-filled) |
| A3 | Safe validation accepted by default; no repetitive prompts | 3 | Accepted automatically when unambiguous; answers are per file, no bulk answers | PR #10 (P4) |
| A4 | Consolidated exception summaries, bulk handling, reject/abort | 3 | Scan report CSV and "needs attention" filter; no bulk handling; no reject of an accepted dataset; the scan cannot be stopped (`ScanJob.cancel` is not connected to `scan_source`) | PR #10 (P4, Stop) |
| B1 | Interval inferred from timestamps, not file names or labels | 1 | Rule A-9; a file-name token is evidence only and a contradiction is asked | — |
| B2 | Arbitrary identifiable intervals | 4 | Fixed list only: 1, 5, 15, 30, 60, 240 minutes; 1D, 1W, 1M. Other intervals are asked (and, before PR #10, could be answered with a wrong label: F-02a) | PR #10 (DQ-7) |
| B3 | Interval-dependent sampling, not exhaustive inspection | 4 | Every row is inspected (correct, not sampled) | PR #10 (P2) |
| B4 | No exchange calendars for timeframe inference; missing bars stay missing | 1 | No calendar used; nothing reconstructed | — |
| B5 | Accept a consistent timeframe by default, show it, allow reject/abort | 3 | Accepted and shown in the evidence; no reject/abort option | PR #10 |
| B6 | Mixed or uncertain intervals keep a MIXED/uncertain status and a warning | 3 | Inconclusive → question. **But** an intraday file whose most common step covers ≥ 60 % of steps is registered under that timeframe; other steps produce only the existing `timeframe_spacing` warning. No MIXED status exists on PR #9 | PR #10 (MIXED); DQ-14 approved for separate work |
| C1 | Explicit identifiers first; file name a candidate; never overrides contents | 1 | Owner decision DQ-2; 6 DQ-2 identity tests | — |
| C2 | Clean download/copy suffixes, keep the original name | 3 | `NSE_NIFTY (1)`, `NSE_NIFTY - Copy`, `NSE_NIFTY, 1D (2)` give NSE:NIFTY (inspected 08-Nov-26); no general cleaning step; original name kept | PR #10 (DQ-8) |
| C3 | Editable alias registry outside the code | 4 | None | PR #10 (DQ-8, schema 9) |
| C4 | Clear matches automatic; ambiguous ones in a consolidated summary | 3 | Automatic for `EXCHANGE_SYMBOL` names; others are per-file questions | PR #10 |
| C5 | Source identity and file name disagree → **keep the source identity and warn**; record decisions and overrides | 3 | The file is **rejected** with the reason (rules v2, D5-15): stricter than v1.35, and it meets DQ-2's "never silently overridden". Decisions and answers are recorded (append-only) | PR #10 commit `3876772`: the column is used and a warning is recorded (inspected in the code on PR #15's branch, 08-Nov-26) |
| D1-D2 | Identical duplicate observations removed from the standardised copy, and counted | 4 | The whole file is rejected (`no_duplicate_timestamps`) | PR #10 (DQ-10) |
| D3 | Same timestamp, different values: never discarded or overwritten | 1 | Nothing is discarded; the file is rejected | — |
| D4 | Conflicting observations preserved and reported | 3 | Within a file: rejected, not preserved as a dataset. Across datasets: reported (DQ-1) | PR #10 (DQ-9, DQ-10) |
| E1 | Conflict → visible warning in the dataset's validation status | 3 | Warning on the **new** dataset (warnings, readiness, scan result). The earlier dataset carries no warning | PR #10 (stated: conflicts on every load path) |
| E2 | Conflicts do not by themselves block analysis | 1 | Warnings never block readiness | — |
| E3 | Enough detail for an informed decision | 1 | Counts, other dataset ID, up to three examples with both values | — |
| E4 | No silent winner; outputs disclose conflict limitations | 1 | No winner (DQ-1). Run metadata records `validation_warnings` and `readiness_warnings` of the analysed dataset | Applies to the new dataset (see E1) |
| F1 | NSE as the default exchange when none is supplied | 4 | A default is used only if the user sets one for the folder; otherwise asked | PR #10 (DQ-8) |
| F2 | Exchange/venue optional metadata, not an import condition | 4 | An exchange is required (asked) | DQ-11 approved (D5-46), not implemented |
| F3 | Crypto identified separately, never NSE | 4 | F-02c: the folder's default exchange was applied to `CRYPTO_` files | PR #10 (prefix); DQ-11 not implemented |
| F4 | Calendars not a dependency of timeframe inference | 1 | None used | — |
| G1 | Original source files never modified | 1 | R13 | — |
| G2 | Transformations, inferred properties, results, warnings, overrides recorded | 1 | Interpretation evidence and decisions per observation; answers append-only; quality checks | — |
| G3 | Provenance sufficient to reproduce and explain | 1 | Generated profile text stored and content-addressed; Run IDs; inputs fingerprint | F-04 caveat (R6) |

## 5. Known defects in PR #9's own state, fixed by PR #10 (stated by PR #10, not re-verified here)

Found in the owner's Windows/IDLE session on PR #9 (02-Nov-26) and recorded on PR #10's branch in
`docs/acceptance_testing/Q-MAP_PR9_Acceptance_Findings_02_Nov_26_210000.md`. **These defects remain in PR #9.**

**Verification of 08-Nov-26** (tested here, Linux, Python 3.12.3). The same synthetic files and calls of
`auto_interpret.interpret_file` (market time zone Asia/Kolkata, default exchange NSE) were run against PR #9's head
`f5f3630` and against PR #10's current head `78323b4` (`claude/friendly-babbage-8xyrgo`), each from its own read-only
copy of the branch. The check script is a scratch file and is not committed. In addition, PR #10's own regression file
`Tests/integration/test_pr9_acceptance_findings.py` was run at `78323b4`: **46 passed, 0 failed** (confirmed to import
PR #10's code, rules version 6).

| Ref | Defect on PR #9 | Effect if PR #9 were used without PR #10 | Result at PR #9 `f5f3630` | Result at PR #10 `78323b4` |
|---|---|---|---|---|
| F-01b | With "File name is the symbol" on, the first word of any name became the symbol | Wrong identity (opt-in folder option only) | `CRYPTO_RIVERUSD, 180.csv` → symbol **CRYPTO**, exchange **NSE**: defect present | Symbol RIVERUSD, exchange key CRYPTO (not NSE): **fixed** |
| F-02a | A recorded timeframe answer was used without checking the measured interval | 180-minute bars registered as 4h (validation only warns) | Answer `4h` for 180-minute bars → ready as **4h**: defect present | Answer not used; ready as **3h** (measured): **fixed** |
| F-02c | The folder's default exchange was applied to `CRYPTO_` files | Crypto data registered under NSE | Exchange **NSE** applied: defect present | Exchange key CRYPTO, never NSE: **fixed** |
| F-03 | Headerless files with separate date and time columns were rejected | Safe rejection only | Rejected ("column 2 is not a number"): defect present | Read automatically: **fixed** |
| F-04 | A rules-version change re-registered identical datasets and discarded answers | No data loss; extra superseded copies, repeated questions | Rules version + 1 → different profile ID and signature: defect present | Same profile ID and signature: **fixed** |

Limits of this verification: it shows the fixes exist at PR #10's current head, which is still based on PR #9's
**old** head `b7a76c2`. The combination of PR #10 with this updated PR #9 has not been built or tested (that is part of
PR #10's preparation). The exchange key `CRYPTO` at PR #10's head is the legacy key that DQ-11 (approved, not
implemented) separates into asset category and venue. Nothing was run on Windows.

These were **not back-ported** to PR #9: the same lines are rewritten by PR #10, so a back-port would duplicate
PR #10's reviewed work and create conflicts when PR #10 is next updated. Consequence: PR #9 should not be used on its own
for real data; PR #9 and PR #10 should be merged one after the other (section 8).

## 6. Review findings of 08-Nov-26

### 6.1 Defect fixed on this branch

**Folder scans followed Windows junctions out of the source folder.** `os.walk(followlinks=False)` does not treat
Windows junctions as links, so with "include sub-folders" on, a junction inside a source folder was entered and the
files behind it were read (read only; nothing was written). `discovery.list_candidate_files` now skips every folder and
file whose real location is not simply inside the chosen folder, and anything that cannot be resolved. The function is
unchanged on the later stacked branches, so the fix carries forward without conflicts. Tests:
`Tests/integration/test_source_folder_containment.py`; the junction and unresolvable-entry tests fail on the previous
code. **Not tested on Windows** with a real junction.

### 6.2 Checked and found correct (inspected and tested here)

- **DQ-1** (owner, 02-Nov-26): `overlap.py` only inserts quality checks on the new dataset; it never updates, supersedes
  or merges. Tests: `test_dq1_*` (4) and `test_conflicting_overlap_is_a_visible_warning_and_nothing_is_overwritten`.
- **DQ-2 headerless** (owner): positions and the volume rule (whole numbers ≥ 0, column 6 only). Tests: `test_dq2_headerless_*` (6).
- **DQ-2 identity** (owner): columns always used; contradicting names rejected; exchange-only question. Tests:
  `test_dq2_*` identity tests (6) and the real-window test `test_a_file_that_lacks_only_its_exchange_asks_only_for_the_exchange`.
- **Determinism:** the profile ID is the hash of the generated text; candidate order is fixed; a re-scan of an
  unchanged file is skipped by size, time and checksum plus an inputs fingerprint that includes answers, folder
  settings, validation settings and the rules version.
- **Re-scans, missing files, retries:** unchanged files are skipped; a missing file is recorded once and its data
  kept; `failed` is not a final outcome, so it is retried; a file rejected only for future dates is retried on the date
  that cures it. A file that changes while it is being loaded is recorded as failed and processed again next time.
- **Pipeline:** every automatically read file goes through `ingest_file`; no parallel reading, validation or storage
  path exists. Overlap checks read the stored Parquet files only.
- **Migration 8:** tables, indexes and triggers only; migrations 1-7 untouched and hash-pinned; each migration runs in
  one transaction. New tests: a populated schema-7 registry upgrades with every record unchanged, a failing migration 8
  is rolled back completely, re-opening changes nothing, and every append-only, identity, CHECK, UNIQUE and foreign-key
  rule of the four tables is enforced (`source_answers` was not covered before).
- **Folders managed by Q-MAP:** a source inside `Q-MAP_DATA`, `Q-MAP_OUTPUT` or the application folder is refused;
  such folders are also skipped during a scan. Hidden files, Office lock files and links are skipped.
- **GUI threading:** the scan runs in a worker thread that only posts events; polling stops when the window closes.

### 6.3 Limitations recorded, not changed

- The scan cannot be stopped once started (`ScanJob.cancel` exists but is not connected); PR #10 adds Stop.
- Identity requires an exchange (v1.35 F2); DQ-11 is approved but not implemented.
- Migration 8's description string says "Blueprint v1.3". It is stored in every upgraded registry and is left as is.
- Three pre-existing pyflakes warnings in `qmap_gui/services.py` (PR #4): re-exported names that tests patch; no
  functional effect.

## 7. Test evidence (tested here, 08-Nov-26)

Linux container (Ubuntu 24.04), not Windows and not IDLE, unless marked CI.

| Commit | Python | GUI | Command | Result |
|---|---|---|---|---|
| `92e05db` (merge of PR #4 into PR #9) | 3.12.3, Tk 8.6, Xvfb | Required (`QMAP_REQUIRE_GUI_TESTS=1`), 199 of 199 GUI tests ran | `xvfb-run -a python3.12 -m pytest -q -p no:cacheprovider` | 949 passed, 0 failed, 0 skipped |
| `92e05db` | 3.11.18 (no tkinter) | Not available | `python3.11 -m pytest -q -p no:cacheprovider` | 837 passed, 0 failed, 86 skipped (all: no tkinter) |
| `7b3ef9b` (junction fix and new tests) | 3.12.3, Tk 8.6, Xvfb | Required, 199 of 199 ran | as above | 975 passed, 0 failed, 0 skipped |
| `7b3ef9b` | 3.11.18 (no tkinter) | Not available | as above | 863 passed, 0 failed, 86 skipped (all: no tkinter) |
| `f5f3630` (documentation) | 3.12.3, Tk 8.6, Xvfb | Required, 199 of 199 ran | as above | 975 passed, 0 failed, 0 skipped |
| `f5f3630` | 3.11.18 (no tkinter) | Not available | as above | 863 passed, 0 failed, 86 skipped (all: no tkinter) |
| `f5f3630`, **CI** push run [42451835236](https://github.com/BulluBhai/Q-MAP/actions/runs/42451835236) and pull-request run [42451838494](https://github.com/BulluBhai/Q-MAP/actions/runs/42451838494) | 3.11 | Windows: required, 199 of 199 ran; Ubuntu: not required | `python -m pytest -p no:cacheprovider` | All 4 jobs passed. Windows (pull-request run): 974 passed, 1 skipped (hard-link fallback test, macOS/Linux only). Ubuntu: 883 passed, 92 skipped (GUI, no display) |

Results for the commit that adds this table are in the PR description.

The 26 new tests are in `test_migration_8_sources.py` (21) and `test_source_folder_containment.py` (5). No existing
test was changed, weakened, removed or skipped. With Python 3.11 the GUI test modules that need tkinter are skipped as
whole files, so fewer tests are collected there (949 against 975).

## 8. Decisions for the Project Owner arising from this review

| Ref | Question | Options | Recommendation |
|---|---|---|---|
| R-1 | PR #9 alone carries the known defects F-01b, F-02a, F-02c, F-03 and F-04, fixed at PR #10's head (section 5) | (a) merge PR #9 and PR #10 one after the other, with no use of `main` for real data in between; (b) back-port the fixes into PR #9 | (a) |
| R-2 | DQ-6 stays open (section 2.1): the v1.3 copies are unchanged and v1.35 §19.4 still says "Version 1.2" | (a) leave the v1.3 copies as historical and close DQ-6 by decision; (b) mark both v1.3 copies superseded; (c) also correct v1.35 §19.4 | (a) together with (c); your decision. *Replaces the earlier recommendation to close DQ-6 on the evidence* |
| R-3 | v1.35 §19.1 names `docs/` as the canonical location; the files are at the repository root | Approve the controlled maintenance change in section 2.1 (separate documentation branch from `main`, both copies) / leave | Approve; not done in PR #9, and the files are not moved |

## 9. Acceptance and readiness boundaries

- Automated tests passed locally; this is **not** owner acceptance. PR #9's own state was **not** accepted: the owner's
  02-Nov-26 session produced findings F-01 to F-04. The round 2c acceptance (D6-27, 07-Nov-26) covered a later build of
  the whole stack (`a202d43d78ed`), not PR #9 on its own.
- Not claimed: owner acceptance of PR #9 or PR #4; production readiness; readiness of automatic discovery for
  unrestricted real-market data; readiness for trading or automated decisions.
- Still open and unchanged by this review: D3-01 to D3-11, D3-15, DQ-3, DQ-5, DQ-6, D6-18 to D6-21, OW-40, OW-41.

## 10. Current and historical documents relevant to PR #9 (08-Nov-26)

**Current** means it describes the governing baseline or this branch's present state. **Historical** means it is a
dated record, kept unchanged as evidence of what applied or was found at the time. Historical records are not edited
to read as current, and are not deleted.

| Document | Status | Note |
|---|---|---|
| `Q-MAP_Master_Blueprint_v1.35.md` / `.html` (root, from `main`) | **Current, governing** | Approved and adopted 3 November 2026. Editorial items in section 2.1 |
| `Q-MAP_Master_Blueprint_v1.3.md` / `.html` (root, from `main`) | Historical, superseded by v1.35 | Kept as required by v1.35. No "superseded" mark inside the files (R-2) |
| This document | **Current** | Reconciliation and review of PR #9 against v1.35 |
| `docs/architecture/Blueprint_v1.3_Implementation_Audit.md` | Historical (02-Nov-26) | Marked historical at the top. Its rules A-1 to A-9 (section 6) still describe the code on this branch |
| `README.md` | **Current** | Governing sentence for v1.35; links checked |
| `docs/decision_log.md`, D5-01 to D5-15 | Historical decision records, still valid | Written under v1.3; section numbers unchanged in v1.35. D5-13 to D5-15 record owner decisions DQ-1 and DQ-2 |
| `docs/Outstanding_Work_Register.md` | **Current** register, with dated history | DQ-6 open; header dated 08-Nov-26 |
| `docs/Q-MAP_Architecture_and_Implementation.md` | **Current** header; sections 1-10 historical | Header names v1.35; earlier sections kept as written |
| `docs/Data_Registry_and_Schema.md` | **Current** | Schema 8. "Blueprint v1.3" in the migration 8 line records when it was added |
| `docs/user_guides/Database_Manager_User_Guide.md`, Sources section | **Current** for this branch | "Added 02-Nov-26 for Blueprint v1.3 §8.5" is a dated note; §8.5 is unchanged in v1.35 |
| `docs/acceptance_testing/Q-MAP_Sources_Acceptance_Checklist_02_Nov_26_183000.md` | Historical (02-Nov-26) | The checklist the owner used for PR #9 on 02-Nov-26; its findings are F-01 to F-04. It is not an acceptance record |
| Code comments citing "Blueprint v1.3 §8.5.x" | Historical references | Same section numbers and text in v1.35; not edited, to avoid conflicts with PR #10 |

