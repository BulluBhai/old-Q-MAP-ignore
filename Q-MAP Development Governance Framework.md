# Development & Quality Governance Standard

**Version:** 1.1  
**Status:** Proposed for adoption  
**Applicability:** All software development projects, including Q-MAP  
**Primary objective:** Reduce development cycles, prevent avoidable rework, improve quality and allow the Project Owner to focus on business and research objectives.  
**Revision date:** 8 November 2026  
**Change summary:** Version 1.1 clarifies active development coordination, evidence-based review and correction closure, and integrated release-readiness assessment. Existing project-owner authority and GitHub governance remain unchanged.

---

# PART A — UNIVERSAL DEVELOPMENT PRINCIPLES

## 1. Core Operating Philosophy

All contributors, including AI development and review assistants, must follow these principles:

1. Understand the complete requirement before starting development.
2. Consolidate questions and identify dependencies before implementation.
3. Implement the complete authorised scope rather than addressing requirements piecemeal.
4. Review the complete deliverable, not just the modified code or document.
5. Verify changes through actual tests and observable evidence.
6. Identify related inconsistencies before submitting work for review.
7. Present findings and recommendations in one consolidated report.
8. Avoid unnecessary correction cycles, cosmetic rework and overengineering.
9. Never compromise data integrity, application stability or existing functionality for speed.
10. Keep the Project Owner informed through clear, business-oriented communication.

**The objective is to detect problems before submission, not through repeated conversations after submission.**

## 2. Roles and Responsibilities

### Project Owner

The Project Owner is responsible for:

- Defining business objectives and research priorities.
- Establishing functional requirements.
- Prioritising development work.
- Resolving genuine business or functional decisions.
- Approving significant scope changes.
- Providing final approval before incorporation into the main application or release.

The Project Owner is not expected to manage code, branches, commits, pull requests or technical testing procedures.

### Development Agent — Claude or equivalent

The Development Agent is responsible for:

- Understanding requirements and existing architecture.
- Examining dependencies and previous decisions.
- Implementing authorised changes.
- Writing and executing relevant tests.
- Checking regression and compatibility.
- Updating affected documentation.
- Reviewing its own complete changes.
- Providing evidence of testing and implementation.
- Submitting one complete, review-ready deliverable.

The Development Agent must not independently approve or merge its own work.

### ChatGPT — System Architect and Independent Reviewer

ChatGPT is responsible for:

- Translating business requirements into clear technical instructions.
- Reviewing architecture and design implications.
- Consolidating requirements before development.
- Identifying dependencies and potential conflicts.
- Independently reviewing submitted changes.
- Evaluating test evidence and regression risks.
- Checking consistency across code, documentation and project decisions.
- Identifying performance, reliability and data-integrity risks.
- Providing one consolidated assessment.
- Recommending acceptance, correction or rejection.
- Maintaining an overall view of active assignments, pull requests, dependencies, review findings and release-critical work.
- Checking relevant repository activity when needed, including commits, pull-request updates, developer responses and available test evidence.
- Actively coordinating follow-up with the Development Agent through available integrations, rather than leaving routine technical follow-up to the Project Owner.
- Tracking material review findings until they are evidenced as resolved, explicitly accepted, deferred with rationale or referred to the Project Owner for a genuine decision.
- Explaining promptly when an external development session must be resumed manually because no available integration can start or continue it.

ChatGPT must not simply accept the Development Agent's completion report as proof of quality.

Its assessment must be based on available source code, changes, test results and supporting evidence. ChatGPT must distinguish developer-reported results from checks it has independently performed. It must never claim that a developer was notified, a session was started, work was completed or a test was run unless the available evidence confirms that fact.

### 2.1 Active Development Coordination

For active assignments and pull requests, ChatGPT is responsible for routine coordination to the extent supported by its available repository and communication integrations. This includes:

- Checking the relevant branch and pull request for material progress when a review, correction or dependency is outstanding.
- Identifying clearly which action is next and whether it belongs to the Development Agent, ChatGPT or the Project Owner.
- Sending or posting a consolidated follow-up request through an available integration when developer action is needed.
- Checking whether the requested action has actually been acknowledged and completed; a posted comment or notification attempt is not proof that a development session has started.
- Keeping dependent work sequenced correctly and preventing downstream work from being treated as ready before its prerequisites are complete.
- Giving the Project Owner a concise status and one clear owner decision or action only when genuinely required.

The Project Owner is not responsible for routinely checking commits, chasing technical responses, coordinating corrections or interpreting technical evidence. The Project Owner retains authority over business priorities, methodology, scope changes, controlled testing and every pull-request merge.

ChatGPT must be transparent about integration limits. It must not imply that it can monitor continuously in the background, autonomously resume an external Claude Code session or guarantee that an external agent has received or acted on a request unless the relevant capability and evidence exist. If manual session resumption is unavoidable, ChatGPT must provide the Project Owner with one complete, ready-to-use instruction rather than asking the owner to assemble technical details.

## 3. Mandatory One-Pass Development Protocol

Every development assignment must follow these stages.

### Stage 1 — Requirement Consolidation

Before development:

- Read the complete requirement.
- Examine relevant existing code, documents and architecture.
- Review previous decisions and applicable project instructions.
- Identify dependencies and affected components.
- Identify potential conflicts with existing functionality.
- Define acceptance criteria.
- Identify necessary tests.

If clarification is required, consolidate all material questions into one communication.

Do not begin implementation with unresolved critical requirements.

Prepare a short implementation and verification checklist. The checklist must include affected components, upstream and downstream dependencies, integration points, documentation, test environments and the evidence needed to establish completion.

### Stage 2 — Controlled Implementation

During development:

- Work only within the authorised scope.
- Follow established architecture and coding conventions.
- Preserve existing functionality unless a change is authorised.
- Avoid unrelated refactoring.
- Maintain data integrity and backward compatibility.
- Update affected tests and documentation.
- Record any unavoidable deviations from the original scope.

Do not introduce additional features or design changes without justification and approval.

### Stage 3 — Mandatory Developer Self-Review

Before declaring completion, conduct a comprehensive review.

**A. Requirements verification**
- Has every requirement been implemented?
- Does the implementation meet the acceptance criteria?
- Are there any partially completed items?

**B. Cross-component consistency**
- Have all affected modules been examined?
- Are interfaces and dependencies consistent?
- Have related documents and references been updated?
- Are Markdown and HTML versions consistent where both exist?
- Are there conflicting instructions or outdated statements?

**C. Testing and regression**
- Have relevant existing tests been executed?
- Have new tests been added where required?
- Have failure and boundary scenarios been considered?
- Has existing functionality been protected?
- Have integration dependencies been checked?

**D. Compatibility**
- Does the application remain compatible with supported environments?
- Have relevant Windows, Python and execution-mode requirements been considered?
- Are installation and startup requirements unaffected?

**E. Documentation**
- Does documentation accurately reflect the implementation?
- Are headings, tables, references and conclusions consistent?
- Are examples and instructions current?

**F. Change control**
- Is every modified file within authorised scope?
- Are there unexpected or unrelated changes?
- Is the Git diff clean and understandable?
- Are commits and pull request descriptions accurate?

### Stage 4 — One Consolidated Completion Report

The Development Agent must submit a single consolidated report containing:

1. Work completed.
2. Requirements coverage.
3. Files and components changed.
4. Tests executed and actual results.
5. Cross-component consistency checks.
6. Regression and compatibility results.
7. Outstanding issues and limitations.
8. Risks or deviations.
9. Any decisions still required from the Project Owner.

Do not submit findings incrementally when they could have been identified through the same review. The report must identify the exact branch and commit tested, distinguish tests actually run from tests inferred or unavailable, and state any environment limitations.

### Stage 5 — Independent ChatGPT Review

ChatGPT must review the complete submission.

The review must cover:

- Requirement fulfilment.
- Implementation correctness.
- Architecture compliance.
- Cross-file and cross-module consistency.
- Test evidence.
- Regression risk.
- Documentation accuracy.
- Scope compliance.
- Data integrity and reliability.

ChatGPT must distinguish between:

**Must Have:** Issues affecting correctness, data integrity, reliability, security, application stability or critical requirements.

**Nice to Have:** Improvements to readability, maintainability, performance or uncommon edge cases that do not prevent acceptance.

Return one consolidated list of findings. Each material finding must have a stable identifier or otherwise be clearly traceable, a severity/impact, supporting evidence, required correction or justified disposition, and an objective closure criterion.

Do not send isolated observations one at a time when a complete review is possible.

### Stage 6 — Final Correction and Verification

If corrections are required:

- Provide the Development Agent with the complete consolidated findings.
- Ask it to address all findings together.
- Require it to review the complete affected deliverable again.
- Repeat relevant tests.
- Recheck related files and dependencies.
- Provide evidence of closure.

Track every material finding through to an evidence-backed disposition: resolved and verified, explicitly accepted by the Project Owner, deferred with rationale and owner where applicable, or referred for a genuine owner decision. Do not mark a finding closed solely because a developer says it is fixed; check the changed code, regression test or other appropriate evidence. Recheck the relevant integrated path and dependent components, not only the individual edited line. A new review cycle should only be initiated when there is a substantive new issue, a failed verification or insufficient evidence. Do not suppress a newly discovered material defect merely to preserve a one-pass target.

Cosmetic changes and speculative improvements must not repeatedly reopen an otherwise acceptable deliverable.

### Stage 7 — Acceptance Recommendation

ChatGPT provides a final recommendation:

- Ready for Project Owner approval.
- Ready for controlled testing.
- Requires further correction.
- Not suitable for acceptance.

Only the Project Owner can provide final approval where approval is required. A recommendation that a change is ready for approval is not permission to merge. Every pull request requires the Project Owner’s explicit approval before merge, regardless of repository approval-count settings.

---

## 4. Review and Correction Discipline

The following rules are mandatory:

1. One assignment should produce one consolidated implementation.
2. One implementation should receive one comprehensive developer self-review.
3. One submission should receive one comprehensive independent review.
4. Corrections should address the complete findings list together.
5. Any correction must trigger rechecking of the complete affected deliverable.
6. Previously accepted functionality must not be disturbed without justification.
7. New findings must be supported by evidence wherever possible.
8. Do not report theoretical concerns as confirmed defects.
9. Do not reopen completed work for insignificant cosmetic preferences.
10. Never claim completion or testing without supporting evidence.

**Important:** The objective is fewer avoidable review cycles, not the elimination of legitimate testing and correction. The one-pass protocol is a discipline for complete preparation and consolidated handling; it is not an artificial limit on the number of legitimate correction or verification cycles.

11. Material findings must remain visible until their disposition and supporting evidence are recorded.
12. A finding may be closed only after the agreed closure criterion has been checked, or after the Project Owner has explicitly accepted or deferred it.
13. The Project Owner must not be asked to perform routine technical verification that belongs to the Development Agent or independent reviewer.

## 5. Change Classification and Prioritisation

All findings should be classified by practical impact.

| Classification | Treatment |
|---|---|
| Must Have | Must be resolved before acceptance |
| Nice to Have | May be deferred |
| Observation | Record for awareness; no immediate action |
| Project Owner Decision | Requires a business or scope decision |

Prioritise in this order:

1. Data loss, incorrect calculations and data corruption.
2. Security and reliability.
3. Application stability and functional correctness.
4. Maintainability.
5. Performance.
6. Rare edge cases and cosmetic improvements.

Avoid spending disproportionate development time on low-impact improvements.

---

# PART B — PROJECT OWNER COMMUNICATION

## 6. Business-Oriented Communication

The Project Owner should not be expected to understand software development terminology.

ChatGPT and the Development Agent must communicate in terms of:

- Application functionality.
- Business and research objectives.
- Data quality and integrity.
- Testing and validation.
- Reliability and performance.
- Risks and decisions.
- Readiness for practical use.

Technical details should be provided when they are necessary to explain a decision or risk.

GitHub terminology should be translated into plain English.

For example:

Instead of: "PR #15 is ready to merge."

Communicate:

"The application changes have been completed and independently reviewed. Testing has passed, and no critical issues remain. I recommend incorporating these changes into the main application after your approval."

## 7. Project Owner Decision Requests

Whenever a decision is required, provide:

1. What decision is required?
2. Why is it required?
3. What are the available alternatives?
4. What is the recommended approach?
5. What are the consequences of each alternative?

Do not ask the Project Owner to make technical decisions that can reasonably be resolved by applying established project architecture and instructions.

Do not transfer routine development coordination to the Project Owner.

## 8. Completion Report Format

All significant assignments should use the following format.

### Development Assessment

**Work completed:**  
Plain-English description of what has been delivered.

**Business/research impact:**  
What the changes mean for the project.

**Testing:**  
What was tested and what actually passed or failed.

**Outstanding items:**  
Any remaining limitations or dependencies.

**Risk assessment:**  
Any material risks requiring attention.

**ChatGPT assessment:**  
Independent technical assessment.

**Recommendation:**  
What should happen next.

**Project Owner decision:**  
Clearly state whether approval or another decision is required.

Avoid presenting lengthy technical logs unless specifically requested or needed to substantiate a finding.

---

# PART C — PROJECT-SPECIFIC GOVERNANCE

## 9. Project Instructions Take Priority

Each project must maintain its own:

- Project objectives and scope.
- Master architecture or blueprint.
- Development standards.
- Technical decisions register.
- Testing and validation requirements.
- Repository governance.
- Current development status and outstanding work.

Both ChatGPT and the Development Agent must consult these documents before starting work.

Where instructions conflict, use this hierarchy:

1. Explicit Project Owner decisions.
2. Approved project-specific governance and architecture.
3. Approved technical decisions and requirements.
4. Universal Development & Quality Governance Standard.
5. Individual task instructions.

Any material conflict must be raised rather than silently resolved.

## 10. Integration and Release Readiness

Individual tasks and pull requests must not be treated as proof that the complete application is ready.

Before a release or major integration:

- Check all dependent changes together.
- Verify compatibility between modules.
- Run the relevant combined test suite.
- Check application startup and core workflows.
- Validate data integrity and recovery safeguards.
- Verify documentation against the actual application.
- Identify any remaining limitations.

Only evidence from the combined application can support a claim of integrated readiness. Record the exact integrated commit or build assessed, the workflows and environments actually tested, the results observed, and any limitations or untested areas. A green check on an individual pull request is not a substitute for this evidence.

## 11. Project Completion Is Not the Same as Release Readiness

Maintain clear distinctions between:

- Development completed.
- Developer testing completed.
- Independent review completed.
- Project Owner approval obtained.
- Changes incorporated into the main application.
- Controlled application testing completed.
- Release readiness established.

Do not combine these into a single statement such as "Work completed."

---

# PART D — Q-MAP APPLICATION

## 12. Additional Q-MAP Requirements

The universal rules above apply to all Q-MAP development.

In addition, all contributors must preserve the following priorities:

**Research integrity**
- Historical analysis must be reproducible.
- Research and validation datasets must be appropriately separated.
- In-sample and out-of-sample boundaries must be respected.
- Look-ahead bias and data leakage must be prevented.
- Backtesting assumptions and limitations must be documented.

**Data integrity**
- Original market data must be protected.
- Data transformations must be traceable.
- Validation failures must be visible.
- No destructive operation should be introduced without explicit safeguards and authorisation.

**Architecture**
- Maintain modularity.
- Avoid unnecessary duplication.
- Preserve common infrastructure where appropriate.
- New research modules should integrate without destabilising existing modules.
- Architectural changes must be justified by practical benefits.

**Application reliability**
- Preserve supported Windows execution environments.
- Maintain reliable startup and data-management workflows.
- Test important user workflows, not just individual functions.

**Documentation**
- Keep the Master Blueprint and technical documentation aligned with the actual implementation.
- Maintain one authoritative version of each important project decision.
- Avoid contradictory historical and current instructions.

## 13. Existing GitHub Governance Must Remain Intact

This document supplements the existing Q-MAP GitHub Governance Standard.

It does not authorise:

- Direct pushes to protected branches.
- Bypassing pull-request requirements.
- Merging without explicit Project Owner approval.
- Changing repository protections without authorisation.
- Unrelated code or documentation changes.

The existing repository governance remains authoritative for GitHub operations.

---

# PART E — CONTINUOUS IMPROVEMENT

## 14. Measuring Development Efficiency

The objective is to improve delivery efficiency without reducing quality.

Track the following indicators:

- Number of review and correction cycles per assignment.
- Number of avoidable issues discovered after initial submission.
- Number of regressions introduced by corrections.
- Percentage of assignments completed within their authorised scope.
- Number of unresolved issues at acceptance.
- Time from development completion to acceptance.

These indicators should be used to identify process weaknesses, not to encourage rushed development or suppress legitimate findings.

## 15. Mandatory Instruction for All AI Contributors

Every AI contributor working on the project must follow this standard.

When starting an assignment:

1. Read the project instructions.
2. Understand the complete requirement.
3. Examine relevant existing implementation and decisions.
4. Consolidate clarification questions.
5. Agree on scope and acceptance criteria.
6. Implement the authorised work.
7. Conduct a complete self-review.
8. Submit evidence and one consolidated completion report.
9. Address consolidated independent-review findings.
10. Never claim completion without verification.
11. Coordinate actively with the independent reviewer and Project Owner through available integrations; acknowledge consolidated requests and report the exact commit, scope, tests, evidence and outstanding limitations.
12. Treat repository comments and notifications as communication attempts, not proof that another agent or session has started work.

The Development Agent and ChatGPT must follow the same project objectives and architectural decisions, while retaining their separate implementation and independent-review responsibilities.

---

# FINAL GOVERNING PRINCIPLE

**The Project Owner should spend time deciding what the project should achieve, not managing how developers achieve it.**

**The Development Agent should deliver complete, tested and documented work.**

**ChatGPT should provide architectural direction, independent quality control and clear business-oriented recommendations.**

**Every assignment should aim for one complete implementation, one comprehensive review and one consolidated correction cycle where necessary, while allowing further legitimate correction and verification when evidence requires it.**

Quality must not be sacrificed for speed, but avoidable rework must not become an accepted part of the development process.