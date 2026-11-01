# Q-MAP outstanding work register

Updated 01-Nov-26. Status words: **Open**, **Decision needed** (Project Owner), **Planned** (roadmap stage).

## Decisions needed from the Project Owner

| Ref | Decision | Why it matters | Recommendation |
|---|---|---|---|
| OD-1 | Commit **Blueprint v1.2** to `docs/`, and confirm D4-01 (the repository folder is `Q-MAP_APP`; entry points at its top level) | This work could only follow the instruction's description of v1.2 | Commit v1.2 and approve D4-01 |
| OD-2 | Supply the **QLOPB source code** and the **MIQP specifications** | Nothing can be migrated or preserved until they are in the repository | Add them on a branch first; their review is the next milestone after data foundations |
| OD-3 | When a Temporary dataset's file was deleted and the same source file is loaded again unchanged: keep today's behaviour (reported, not re-created), or re-create it? | Re-creating changes the approved reuse identity (D2-32) | Re-create, recorded as a new attempt linked to the old one. Needs a schema migration. |
| OD-4 | Name the **minute-data indices** and the **hourly stock universe**, and their retention | Storage supports any combination, but nothing enforces or reports the intended universes | Define them as named universes in configuration |
| OD-5 | **Trading calendar** source (NSE holidays and session times) | Needed to confirm complete days and periods; today only heuristics flag them | Start with an exchange holiday list file under `Reference_Files` |
| OD-6 | Should a load be able to go **straight to Temporary**? | Today every load is Permanent and must be moved afterwards | Yes: an option in Data Management |
| OD-8 | **Temporary folder name**: approve `Temporary_Data/` as a recorded deviation (Option A), or align with `Temporary/` from Blueprint v1.2 and the handover (Option B: new migration 7, Temporary datasets made Permanent before upgrading, no automatic file movement) | `Temporary_Data/` was chosen by Claude without approval; the database rules of schema 6 contain the prefix | Option B if v1.2 is confirmed authoritative (cheapest before merge); details in the architecture document, section 7 |
| OD-9 | **Record which Blueprint version is approved** and resolve the conflict between v1.2's own approval wording and the handover's statement that it is authoritative; commit v1.2 and the handover to `docs/` | Claude cannot see either document; the repository records no approval of v1.2 | Record the approval in the decision log |
| OD-7 | Carry-over from PR #3: D3-15 (grey "Waiting" row) and the incomplete-day limitation | Unchanged by this work | As in PR #3 |

## Open technical work and known limitations

| Ref | Item | Status |
|---|---|---|
| OW-01 | Run the acceptance checklist on Windows, in Thonny or IDLE, with the owner's 11 sample files | Open (owner) |
| OW-02 | GitHub CI for each new commit of PR #4 | `832b788`: Windows and Ubuntu passed. Later commits: see the PR checks |
| OW-03 | DuckDB for cross-dataset queries (Blueprint 8.3) | Planned; add it in `qmap/catalog.py` when a module queries across datasets |
| OW-04 | Daily bars derived from intraday data | Blocked by OD-5 (session rules, incomplete-day detection) |
| OW-05 | Corporate-action adjustment | Planned (Blueprint open decision) |
| OW-06 | Re-create a deleted derived dataset under the same method version | Depends on OD-3 |
| OW-07 | Restore a damaged raw file from the screen (command line only today) | Open |
| OW-08 | Research Library screen (tables and run records exist) | Planned |
| OW-09 | Technical debt: derived datasets carry their source's `created_by_attempt_id` (rule from migration 1); the real derivation record is in `dataset_derivations`. A future migration could rebuild `datasets` to relax the rule | Open, low priority |
| OW-10 | Selecting the "current" dataset when several raw files exist for one instrument and timeframe | Open (carried over) |
| OW-11 | The Workbench window shell shares `qmap_gui/app.py` with Database Manager, which imports the folder-checking helpers in `services.py`. Those helpers sit beside the profile helpers at import time; no preparation workflow can start from the Workbench (tested) | Optional clean-up: move folder helpers to their own module |
| OW-13 | Detection of storage tampering done before schema 6 cannot show intermediate states or timing, and depends on the D2-19 naming rule (see "Limits of detecting earlier tampering" in the registry document) | Documented limitation |
| OW-12 | Feature Store (reusable calculated features with method and parameter versions) | Planned with the first research module that needs one |

## Roadmap after this work (unchanged priorities)

1. Owner acceptance of Database Manager (OW-01) and decisions OD-1 to OD-6.
2. QLOPB migration into `Application/qmap/analytical_engine` as an `AnalysisSpec` (Stage 4), once the source is
   supplied (OD-2).
3. MIQP Market Intelligence (Stage 3) from approved specifications.
4. Stage Analysis (Weinstein) and other methods: each needs explicit rules, parameters, outputs and validation
   criteria first.
5. Opportunity Scanner, Strategy Backtesting, Portfolio and Risk (Stages 6-8).
