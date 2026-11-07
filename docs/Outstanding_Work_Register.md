# Q-MAP outstanding work register

Updated 07-Nov-26: OW-34 resolved (round-2c Windows UAT accepted by the Project Owner, D6-27); OW-45 added (Stop scan counter, minor future display correction).
Updated 04-Nov-26 after the independent audit of PR #12 head `3f4faea` (corrections A1-D7, D6-19..D6-23; OW-34, OW-35, OW-41 status; OW-42..OW-44 added; details `docs/release/Q-MAP_v0.1_Review_Corrections_04_Nov_26_100000.md`). Earlier update 03-Nov-26 for the **v0.1 release candidate** (Blueprint v1.35; decisions D6-01..D6-11): OD-2 resolved for QLOPB (MA Affinity migrated) and closed for MIQP in v0.1 (outside the release); OW-34..OW-41 added (OW-39/40 from the final release audit; OW-41 from the DQ-7 correction of 04-Nov-26). Earlier update 03-Nov-26 (owner decisions D5-46..D5-51: DQ-11 approved, DQ-12 design approved, DQ-14 approved for separate implementation, OW-33 option C step 1 authorised; PR #10 scope fixed). Earlier update 03-Nov-26 (owner decisions on the second review: DQ-11/DQ-12 approved in principle, DQ-14 provisionally approved, OW-33 deferred, W13-W18 added). Earlier update 03-Nov-26 (second PR #10 review): DQ-11/DQ-12 approved in principle as separate tasks, DQ-13 kept separate, DQ-14 revised; OW-33. Earlier update 03-Nov-26 for the **data-automation instruction DQ-7..DQ-10** (DQ-7..DQ-10 of 02-Nov-26 answered/superseded; DQ-11..DQ-13, OW-29..OW-31). Earlier update 02-Nov-26 for the **PR #9 acceptance findings** (DQ-7 to DQ-10, OW-25 proposal, OW-26 to OW-28). Earlier update 02-Nov-26 for **Blueprint v1.3** (merged to `main` by PR #8): decisions DQ-1 to DQ-6 and items OW-18 to OW-24
added; see `docs/architecture/Blueprint_v1.3_Implementation_Audit.md`. Earlier update 02-Nov-26 (roadmap wording: PR #4 vs PR #5). Earlier update 01-Nov-26, after reviewing Blueprint v1.2 (approved and adopted 1 November 2026, in PR #5). Status words:
**Open**, **Decision needed** (Project Owner), **Planned** (Blueprint v1.2 roadmap stage), **Resolved**.

## Decisions needed from the Project Owner

| Ref | Decision | Why it matters | Recommendation |
|---|---|---|---|
| DQ-11 | Separate `asset_category` and `venue` fields. **Approved (D5-46)**, nine categories incl. Unclassified; **not implemented**; separate task outside PR #10 | Decided | Implement on its own branch when scheduled | See `docs/architecture/Proposal_DQ11_Asset_Category_and_Venue_03_Nov_26_075552.md`; separate task after PR #10 |
| DQ-12 | Source-specific ignore-columns for exact duplicates (`index` first). **Design approved (D5-47)**; **not implemented**; separately planned | Decided | Implement on its own branch when scheduled | See `docs/architecture/Proposal_DQ12_Technical_Export_Columns_03_Nov_26_075552.md`; separate task after PR #10 |
| DQ-14 | What the full-file interval check does to the registered timeframe. **Approved for separate implementation (D5-48)** on the D5-42 terms; **not implemented** | Sampling labels a 1-5 % section MIXED or not depending on the seed (20 % of seeds at 1 %); regular multiples cannot be told from regularly missing bars | Revised proposal `docs/architecture/Proposal_DQ14_Revised_03_Nov_26_075552.md`: >= 1 % detected -> MIXED; >= 1 % uncertain -> unresolved (NOTE); smaller -> warning |
| DQ-13 | AKZOINDIA 08-Nov-25 (source rows 34185, 34189: low above open). The source file and values are NOT changed; both rows stay rejected under the current OHLC rule until authoritative evidence (exchange notice of the Saturday session; official or second-vendor bars) is obtained. Investigation kept separate from PR #10 | Q-MAP never chooses or edits values | Owner obtains evidence; a corrected copy is loaded as a new file |
| DQ-3 | Name the first API providers and supply permitted credentials | §8.5.2 needs your priorities and a licensing review | One broker API you already hold an account for |
| DQ-5 | Optional scheduled scanning? | §8.5.6 optional | On demand only, until daily use shows a need |
| DQ-6 | v1.3 "Version authority", paragraph 2, still calls v1.2 the primary reference | Editorial inconsistency in the approved document | Correct both copies in a maintenance edit |
| OD-1 | Confirm D4-01: the repository folder is `Q-MAP_APP`, with both entry points at its top level | Blueprint v1.2 §4.4 and §9.1 describe exactly this target. Internal sub-folders are mapped onto existing packages, not renamed (architecture document, C3). | Approve D4-01 |
| OD-2 | QLOPB source code and MIQP specifications | **Resolved for QLOPB (D6-03)**: `BulluBhai/QLOPB` `6cbadc7` migrated unchanged into `Application/qlopb`. **MIQP: outside v0.1 (D6-02)**; no specification supplied; IndexAnalytics repositories inspected (no regime/breadth material) | Supply approved MIQP specifications for v0.2 |
| OD-3 | When a Temporary dataset's file was deleted and the same source file is loaded again unchanged: keep today's behaviour (reported, not re-created), or re-create it? | Re-creating changes the approved reuse identity (D2-32) | Re-create, recorded as a new attempt linked to the old one; needs a schema migration |
| OD-4 | Name the **minute-data indices** (v1.2: about 4-5) and the **hourly stock universe** (v1.2: about 200-500), and their retention | Storage supports any combination; nothing enforces or reports the intended universes | Define them as named universes in configuration |
| OD-5 | **Trading calendar** source (NSE holidays and session times) | v1.2 §8.4; needed to confirm complete days and periods | Start with an exchange holiday list file |
| OD-6 | Should a load be able to go **straight to Temporary**? | Today every load is Permanent and must be moved afterwards | Yes: an option in Data Management |
| OD-7 | Carry-over from PR #3: D3-15 (grey "Waiting" row) and the incomplete-day limitation | Unchanged by this work | As in PR #3 |
| OD-12 | Which record is the single issuer of `TC`/`OBV`/`RQT`/`DCN`/`CR`/`TR` numbers? | Issuing them from the repository could collide with the Excel master register | The Excel register issues them; repository entries quote them |
| OD-13 | Finalise (or drop) the proposed codes `C`/`T`/`E`/`P`, `ISO`/`UNI`/`STD`, `DMY`/`YMD` | They are recorded as proposals only; `STD` is not precise enough to drive parsing | Use them only as separate register attributes, define `STD` narrowly, and keep profile IDs on the descriptive tokens |
| OD-14 | Approve the source-profile naming standard (IDs, display names, statuses, earlier-name aliases) | Introduced in PR #4 | Approve as documented |
| OD-10 | Align the **other §9.1 folder names** with v1.2's proposal? Data: `Permanent/` (today `Cleaned_Data/` + `Timeframe_Data/`), `Reference_Data/` (today `Reference_Files/`). Output: `Database_Reports/`, `Analytical_Results/` (today `Ingestion/`, `Data_Management/`; `Research_Reports/` already matches). | v1.2 calls them "proposals, not a demand" and asks for the smallest safe migration. A data-folder rename touches every stored path, recovery and the naming rule, but could reuse the OD-8 transition pattern. Output folders hold no registered data. | Keep the data folders as they are. Rename output folders for NEW runs only if you want strict alignment. |

**Resolved:**

- **DQ-1** (owner, 02-Nov-26, PR #9): conflicting overlapping bars are reported only; both datasets kept unchanged
  (D5-13). Code and tests done; Windows/IDLE acceptance outstanding (OW-19).
- **DQ-2** (owner, 02-Nov-26, PR #9): headerless convention and file-name identity approved; file contents never
  silently overridden (D5-14, D5-15; identity rule corrected). Code and tests done; Windows/IDLE acceptance outstanding (OW-19).
- **OD-8** (Temporary folder): you adopted `Q-MAP_DATA/Temporary/`. Implemented with schema migration 7 and a
  no-data-movement transition (decision D4-15; architecture document, section 7).
- **OD-9** (Blueprint authority): v1.2 states its own approval and adoption on 1 November 2026, and it supersedes
  v1.0 and v1.1.
- **OD-11** (PR #5 corrections, approved by the Project Owner): applied on PR #5's branch in commit `043a7f7`. The
  Markdown version history and canonical-copy paragraph now match the HTML; all three files are in `docs/`; the
  handover reflects the current state. PR #5 remains open for the owner's review.

## Open technical work and known limitations

| Ref | Item | Status |
|---|---|---|
| OW-01 | Run the acceptance checklist on Windows, in Thonny or IDLE, with your 11 sample files | **Resolved 07-Nov-26**: absorbed into OW-34 (03-Nov-26), which the Project Owner accepted (D6-27). Earlier status: Open (owner) |
| OW-02 | GitHub CI for each new commit of PR #4 | Recorded per commit in the test report and the PR description |
| OW-03 | DuckDB for cross-dataset queries (v1.2 §8.3) | Planned; add it in `qmap/catalog.py` when a module queries across datasets |
| OW-04 | Daily bars derived from intraday data | Blocked by OD-5 (session rules, incomplete-day detection) |
| OW-05 | Corporate-action adjustment | Planned (v1.2 open decision) |
| OW-06 | Re-create a deleted derived dataset under the same method version | Depends on OD-3 |
| OW-07 | Restore a damaged raw file from the screen (command line only today) | Open |
| OW-08 | Research Library screen (tables and run records exist) | Planned |
| OW-09 | Technical debt: derived datasets carry their source's `created_by_attempt_id` (migration-1 rule); the real record is in `dataset_derivations` | Open, low priority |
| OW-10 | Selecting the "current" dataset when several raw files exist for one instrument and timeframe | Open; related to v1.2's update-conflict policy (open decision, gap G-6) |
| OW-11 | The Workbench's window shell imports the folder-checking helpers in `services.py`, which sit beside profile helpers; no preparation workflow can start from the Workbench (tested) | Optional clean-up |
| OW-12 | Feature Store (v1.2 §7.3) | Planned with the first research module that needs one |
| OW-13 | Detection of storage tampering done before schema 6 cannot show intermediate states or timing, and depends on the D2-19 naming rule | Documented limitation |
| OW-14 | `research_records` statuses (migration 1: Hypothesis ... Superseded) differ from v1.2 §5.9 (Under Research, Promising, Validated, Archived). The table is unused. | Change with a new migration when the Research Library is built |
| OW-15 | Research Run Manager result reuse (v1.2 §13.1): every analysis creates a new run today | Planned |
| OW-16 | Coverage view by instrument × timeframe × date range (v1.2 §5.10) | Open (per-dataset coverage exists) |
| OW-18 | Provider API adapters (v1.3 §8.5.2, target five): adapter contract, mocked tests, live tests with permitted access | Not started (DQ-3) |
| OW-19 | Owner acceptance of the Sources screen on Windows/IDLE with real files (checklist `docs/acceptance_testing/Q-MAP_Sources_Acceptance_Checklist_02_Nov_26_183000.md`). First session done by the owner 02-Nov-26; findings F-01 to F-04 fixed (report `Q-MAP_PR9_Acceptance_Findings_02_Nov_26_210000.md`); re-test steps A1-A8 in the checklist addendum | **Resolved 07-Nov-26**: absorbed into OW-34 (03-Nov-26), which the Project Owner accepted (D6-27). Earlier status: Open (owner) |
| OW-20 | Extra source columns (open interest, delivery volume) are kept as text `x_` columns; typed, named fields are not built | Open |
| OW-21 | Automatic reading does not accept thousands separators or decimal commas (rejected with a reason; Data Management with a profile still works) | Open, low priority |
| OW-22 | A file with several symbols in one `symbol` column: timeframe is measured across all rows, so it is usually asked rather than inferred | Open, low priority |
| OW-23 | Sources tested only in a Linux container (Xvfb), not against a real OneDrive/Google Drive client or Windows | Open (owner acceptance) |
| OW-24 | Choosing the "current" dataset when overlapping datasets disagree | By decision DQ-1, Q-MAP does not choose; the user selects. Revisit only if the owner wants a preference flag |
| OW-25 | Overlap/conflict checks for Data Management and command-line loads | **Resolved 03-Nov-26** (DQ-9, D5-24) |
| OW-29 | GUI acceptance on Windows/IDLE of the DQ-7..DQ-10 workflow, W1-W18 (step-by-step guide `docs/acceptance_testing/Q-MAP_Windows_IDLE_Acceptance_Guide_03_Nov_26_150000.md`) (checklist `docs/acceptance_testing/Q-MAP_DQ7-DQ10_Acceptance_Checklist_03_Nov_26_120000.md`; W13-W18 use the synthetic files in `dq7_pattern_files_03_Nov_26/`). The owner's eight files were not re-run after `fad8d2f` | **Resolved 07-Nov-26**: absorbed into OW-34 (03-Nov-26), which the Project Owner accepted (D6-27). Earlier status: Open (owner) |
| OW-30 | Canonical display name in `instruments.name` | **Resolved 03-Nov-26** (D5-34) |
| OW-32 | Derived datasets stay linked to the daily dataset they were built from after it is superseded by re-processing; not re-derived automatically | By design; derive again from the new daily dataset if wanted |
| OW-33 | Sampling and the full-file check treat a regular whole-multiple section and a stretch of sparse one-bar dates differently | **Option C selected (D5-49).** Step 1 only: read-only impact report (prepared on branch `claude/youthful-babbage-d71hnl`, outside PR #10; the owner runs it on the real registry). Option C, `vs3` and reprocessing **not authorised** |
| OW-31 | Every dataset is processed once more after this update (cleaning code c2, fingerprint vs2, rules v6): identical content gets new dataset numbers and the old ones become superseded | Expected one-off; documented |
| OW-26 | Bar-time convention: some sources label intraday bars by their END time (UJJIVAN 5m: 09:20 ... 15:30), others by their START (09:15 ...). Q-MAP stores times as written and does not detect or convert the convention | Open; needs an owner rule before cross-source comparison of intraday data |
| OW-27 | Unexplained multi-day gaps in 5PAISA (e.g. 15-Dec-17 to 05-Jan-18) and VERANDA (13-Jun-22 to 23-Jun-22, 22-Aug-22 to 01-Sep-22) | Reported as warnings; owner judgement before gap-sensitive research |
| OW-28 | Owner's registry after this update: the earlier RIVERUSD dataset registered as 4h stays until removed (Datasets and Storage: Move to Temporary, then Delete) | Owner action |
| OW-34 | **v0.1 Windows/IDLE acceptance**: one guide `docs/release/Q-MAP_v0.1_Windows_Operating_and_Acceptance_Guide_03_Nov_26_180000.md` (V1-V14 + W1-W19 + A4-A8; absorbs OW-01, OW-19, OW-29). 04-Nov-26: manual updated for build `3fa925abf95b` (code `919c697`) with the new REQUIRED check W19 (same-size, restored-date change is detected) | **Resolved 07-Nov-26 (D6-27)**: round-2c Windows owner screen tests (build `a202d43d78ed`) completed and formally accepted by the Project Owner; record `docs/acceptance_testing/Q-MAP_v0.1_UAT_Round2c_Owner_Results_Review_07_Nov_26_173737.md`. Earlier: round 1 done 06-Nov-26 (engine-level; 0 FAIL, 7 NOT TESTED; `docs/acceptance_testing/uat_round1_06_Nov_26/`); round-2 corrections (build `21d31f0fe259`). Controlled analytical use not yet approved |
| OW-35 | Independent review of the QLOPB integration (D6-03..D6-05) and of QLOPB safeguards S-1..S-3. 04-Nov-26: reproducible file-by-file comparison with QLOPB `6cbadc7` (branch `claude/youthful-bardeen-11wtok`; `main` is `be6d945` without safeguards) and a review of S-1..S-3, readiness and reports supplied by Claude, no defect found (D6-23). That review is **not independent** (same author as the migration) | **Open (ChatGPT)**: evidence ready for independent verification |
| OW-36 | The QLOPB engine prints pandas 3 deprecation warnings (`DatetimeIndex.dayofweek` ...); no effect on tested results. Updating them would touch migrated code: only with owner approval | Open, low priority |
| OW-37 | Blueprint v1.1 was never committed to the repository (v1.35 asks for it to be retained) | Open (owner: supply a copy if one exists) |
| OW-38 | MA Affinity on intraday and quarterly datasets is not offered in v0.1 (QLOPB: intraday not validated; quarterly outside the approved scope although shown equal) | Open; owner decision for v0.2 |
| OW-39 | Final audit finding (DQ-7, same area as OW-33/DQ-14): a daily file in which some dates carry a second bar is measured as intraday (only same-date steps count) and registered e.g. as 30m without a warning. MA Affinity and derivation refuse it; nothing is changed or lost | Open; input to the OW-33/DQ-14 review; documented limitation for v0.1 |
| OW-40 | Final audit finding: a start date inside a week/month keeps that period's bar (dated by its last session), which contains sessions just before the start. Earlier data only (no look-ahead); same for Dataset Summary | Open; documented limitation; owner decision whether periods should be cut at the boundary |
| OW-41 | DQ-7 correction (D6-15) and earlier classifications. Investigated (D6-17): an unchanged file in the same folder is skipped and keeps its earlier result; identical content as a new file, and new files, use the corrected comparison (the earlier dataset is kept, not superseded). Earlier and corrected results share a processing version (no version bump: it would reprocess everything). Resolved for identification: every new inference record is marked, and Q-MAP judges each stored record read-only (corrected / earlier, same result / earlier, would be MIXED) and says so in Datasets and Storage, Sources, readiness and Run_Metadata; MA Affinity refuses the "would be MIXED" case (D6-18). No dataset is reclassified or reprocessed | **Partly resolved**; owner decisions still open (04-Nov-26): confirm D6-18 (implemented as the safer default, not approved); whether earlier "would be MIXED" datasets should ever be re-classified (needs authorised processing) |
| OW-42 | C5: DQ-7 does not require the base step for daily-or-longer labels (regular 2-4-day steps → 1D, 5-10-day steps → 1W); characterisation tests record it (D6-21) | **Decision needed** (owner) |
| OW-43 | C4: multi-instrument files with differing intervals are refused (D6-20); per-instrument registration with each instrument's own timeframe is a possible later option. Datasets registered earlier from such files are not re-examined | **Decision needed** (confirm D6-20) |
| OW-44 | Decision-record gap: owner's written answers to plan questions C-6/C-9 (supersession of D5-15, D5-18 by DQ-8) are not in the repository (D6-19) | **Decision needed** (confirmation) |
| OW-45 | Stop scan progress counter (UAT round 2c, test 19, 07-Nov-26): after **Stop scan** the Sources screen showed "Files done: 10 / 10" and a full bar although 8 of the 10 files were not processed. The message ("Stopped by you after 2 file(s); 8 file(s) not processed ..."), the Live Log and the scan report were correct. Cause: the scan reports full progress after its loop even when stopped (`discovery.py`). Display only; no data affected | **Planned**: minor future display correction, agreed by the Project Owner; no code change and no further testing now |
| OW-17 | Datasets still in the legacy `Temporary_Data/` folder (only if earlier PR #4 test builds created any) | Safe where they are; relocate with Make Permanent, then Move to Temporary. Recovery lists them. |

## Roadmap (Blueprint v1.35 section 15)

1. **Stages 3-4** (Database Manager and Analytical Workbench foundations). The implementation is in **PR #4**,
   which is stacked on PR #3, PR #2 and PR #1. Still needed: the owner's Windows/IDLE acceptance of PR #4 (OW-01)
   and decisions OD-1, OD-3, OD-10; then, with the owner's approval, merge PR #1, #2, #3 and #4 in that order.
   **PR #5** is separate and holds documentation only (Blueprint v1.2 and the handover, based on `main`). It is
   reviewed and merged on its own and does not contain or replace the PR #4 implementation.
2. **Stage 6**: QLOPB price-behaviour migration into `analytical_engine` as an `AnalysisSpec`, once the source is
   supplied (OD-2). v1.2 lists MIQP (Stage 5) first; the order of 5 and 6 can follow which material is available.
3. **Stage 5**: MIQP Market Intelligence from approved specifications.
4. **Stage 7**: extensible research (Stage Analysis, Ichimoku, candlesticks ...). Each needs explicit rules,
   parameters, outputs and validation criteria first.
5. **Stages 8-10**: historical Opportunity Scanner, strategy backtesting, portfolio and risk.
