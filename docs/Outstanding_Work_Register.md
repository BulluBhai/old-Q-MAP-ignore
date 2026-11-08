# Q-MAP outstanding work register

Updated 08-Nov-26 (PR #9 brought up to date with PR #4; reconciliation with Blueprint **v1.35**, approved and adopted 3 November 2026: `docs/architecture/Blueprint_v1.35_Reconciliation_PR9.md`; no status changed). Earlier update 02-Nov-26 for **Blueprint v1.3** (merged to `main` by PR #8): decisions DQ-1 to DQ-6 and items OW-18 to OW-24
added; see `docs/architecture/Blueprint_v1.3_Implementation_Audit.md`. Earlier update 02-Nov-26 (roadmap wording: PR #4 vs PR #5). Earlier update 01-Nov-26, after reviewing Blueprint v1.2 (approved and adopted 1 November 2026, in PR #5). Status words:
**Open**, **Decision needed** (Project Owner), **Planned** (Blueprint v1.2 roadmap stage), **Resolved**.

## Decisions needed from the Project Owner

| Ref | Decision | Why it matters | Recommendation |
|---|---|---|---|
| DQ-3 | Name the first API providers and supply permitted credentials | §8.5.2 needs your priorities and a licensing review | One broker API you already hold an account for |
| DQ-5 | Optional scheduled scanning? | §8.5.6 optional | On demand only, until daily use shows a need |
| DQ-6 | v1.3 "Version authority", paragraph 2, still calls v1.2 the primary reference | Editorial inconsistency in the approved document. Note 08-Nov-26: v1.35 (the governing version) no longer contains it; the v1.3 copies still do. Status unchanged until the owner decides | Correct both copies in a maintenance edit, or close because v1.35 resolves it |
| OD-1 | Confirm D4-01: the repository folder is `Q-MAP_APP`, with both entry points at its top level | Blueprint v1.2 §4.4 and §9.1 describe exactly this target. Internal sub-folders are mapped onto existing packages, not renamed (architecture document, C3). | Approve D4-01 |
| OD-2 | Supply the **QLOPB source code** and the **MIQP specifications** | Blueprint v1.2 §14 and Stages 5-6; nothing can be migrated until they are in the repository | Add them on a branch; QLOPB first (it is existing working code) |
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
| OW-01 | Run the acceptance checklist on Windows, in Thonny or IDLE, with your 11 sample files | **Open (owner)** |
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
| OW-19 | Owner acceptance of the Sources screen on Windows/IDLE with real files (checklist `docs/acceptance_testing/Q-MAP_Sources_Acceptance_Checklist_02_Nov_26_183000.md`) | **Open (owner)** |
| OW-20 | Extra source columns (open interest, delivery volume) are kept as text `x_` columns; typed, named fields are not built | Open |
| OW-21 | Automatic reading does not accept thousands separators or decimal commas (rejected with a reason; Data Management with a profile still works) | Open, low priority |
| OW-22 | A file with several symbols in one `symbol` column: timeframe is measured across all rows, so it is usually asked rather than inferred | Open, low priority |
| OW-23 | Sources tested only in a Linux container (Xvfb), not against a real OneDrive/Google Drive client or Windows | Open (owner acceptance) |
| OW-24 | Choosing the "current" dataset when overlapping datasets disagree | By decision DQ-1, Q-MAP does not choose; the user selects. Revisit only if the owner wants a preference flag |
| OW-25 | Overlap/conflict checks run for files registered by a folder scan; a file loaded through Data Management is not itself checked when loaded (a later scanned file is compared with it) | Open, low priority |
| OW-17 | Datasets still in the legacy `Temporary_Data/` folder (only if earlier PR #4 test builds created any) | Safe where they are; relocate with Make Permanent, then Move to Temporary. Recovery lists them. |

## Roadmap (Blueprint v1.2 section 15)

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
