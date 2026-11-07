# Q-MAP — GitHub Repository Governance

## 1. Repository information

- Repository: `BulluBhai/Q-MAP`
- Visibility: PUBLIC
- Default branch: `main`
- Active ruleset: Protect Main Branch
- Ruleset target: Default branch (`main`)

## 2. Active branch protections

The following protections are active:

- All changes to main must go through Pull Requests.
- Direct changes to main are not permitted.
- Required PR approvals: zero.
- Review conversations must be resolved before merging.
- Branch deletion is blocked.
- Force pushes are blocked.
- No bypass actors are configured.

Do not modify these settings without explicit owner authorisation.

## 3. Mandatory development workflow

1. All development must take place on separate feature/development branches.
2. Direct pushes to main are prohibited.
3. All changes must be submitted through Pull Requests.
4. Each PR must explain its purpose, scope, files changed, testing results, outstanding issues and risks.
5. All review conversations must be resolved before merging.
6. No PR may be merged without explicit approval from the Project Owner.
7. No developer or reviewer may bypass or modify repository protections.

## 4. Responsibilities

**Project Owner**

- Owns business and research requirements.
- Approves important product and methodology decisions.
- Performs user acceptance testing where required.
- Retains final authority over all merges.

**Claude — Lead Developer**

- Implements approved changes.
- Develops on feature branches.
- Performs and documents testing.
- Creates and updates Pull Requests.
- Does not merge without explicit owner approval.

**ChatGPT — Business and Technical Reviewer**

- Helps translate business requirements into development instructions.
- Independently reviews implementation and evidence.
- Assesses whether acceptance criteria have been met.
- Recommends whether a PR is ready for owner approval.

## 5. Merge authority

GitHub's zero-approval requirement does not grant developers permission to merge.

The Project Owner's explicit approval is mandatory before any PR is merged.

These governance rules remain in force unless explicitly changed by the Project Owner.
