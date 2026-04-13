---
document_id: MEMINIT-PLAN-006
type: PLAN
title: "Atomic Worklist for Known Backlog"
status: Draft
version: "0.3"
last_updated: 2026-03-07
owner: GitCmurf
docops_version: "2.0"
area: PLAN
description: "Reviewed and prioritised atomic worklist for the remaining known backlog, aligned to MEMINIT-PLAN-005 and engineering-principles-v1.1."
keywords:
  - backlog
  - planning
  - templates
  - agent-interface
  - technical-debt
related_ids:
  - MEMINIT-PLAN-005
  - MEMINIT-PLAN-007
  - MEMINIT-PRD-001
  - MEMINIT-PRD-006
  - MEMINIT-PRD-007
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PLAN-006
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.3
> **Last Updated:** 2026-03-07
> **Type:** PLAN
> **Area:** Planning

# Atomic Worklist for Known Backlog

## 1. Purpose

This document is the execution worklist for the backlog captured in MEMINIT-PLAN-005.
It replaces the previous task dump with a review-driven plan that is:

- aligned to `engineering-principles-v1.1.md`
- grounded in current repository reality rather than PRD text alone
- atomic enough to execute as small PRs
- explicit about code, tests, and documentation for every item

This plan is intentionally conservative. If a backlog item is not clearly justified by current product documents or current code gaps, it is deferred instead of padded with speculative engineering work.

## 2. Critical Review of the Previous Version

The prior version of this plan was not ready to act on as a high-quality engineering worklist.

Primary issues found:

1. Several tasks were stale or incorrect against the codebase.
   - `NewDocumentResult` is in `src/meminit/core/domain/entities.py`, not `src/meminit/core/entities.py`.
   - `meminit context` is implemented in the repository code, so references treating it as missing are outdated.
   - `project-state.yaml` alphabetical ordering is already validated in `src/meminit/core/services/project_state.py`.
2. Some tasks described implementation mechanics, not outcomes.
   - This makes review harder and encourages solution lock-in instead of small, testable acceptance criteria.
3. Documentation and specification updates were under-scoped.
   - Per the repo rules and Section 1 of `engineering-principles-v1.1.md`, no backlog item is complete without code, tests, and documentation.
4. A few items were weakly justified.
   - `project-state.yaml` freshness warnings are not established as a required product behaviour and should not be treated as committed backlog without a spec or PRD update.
5. Some verification gates rewarded the wrong thing.
   - Coverage percentage targets alone are weaker than behaviour-based tests for critical paths.
6. Time estimates were overly precise for exploratory or design-heavy tasks.
   - For higher-uncertainty items, sizing should be at the workstream level until discovery is complete.

## 3. Planning Principles for This Worklist

This worklist follows these principles:

- Smallest viable change first.
- Specification and acceptance criteria before implementation for behaviour changes.
- Backward compatibility reviewed explicitly for CLI and JSON contracts.
- Prefer deterministic tests over broad, flaky stress exercises.
- No task is complete without synchronized code, tests, and docs.

## 4. Priority Summary

| Priority | Workstream                    | Why it matters now                                                               |
| -------- | ----------------------------- | -------------------------------------------------------------------------------- |
| P0       | Documentation alignment sweep | Backlog completion is not credible if governed docs drift from shipped behaviour |
| P1       | PRD-006 JSON output gap       | Public contract drift already exists between PRD/spec and implementation         |
| P2       | PRD-006 migration tooling     | Required to make Templates v2 adoption safe in legacy repos                      |
| P3       | PRD-001 org-level config      | Valid backlog, but lower urgency for single-repo operation                       |
| P4       | PRD-007 integration polish    | Useful hardening, but only after contract gaps are closed                        |
| P5       | Technical debt                | Important, but should target risk, not vanity metrics                            |

## 5. Atomic Worklist

### 5.0 Workstream P0: Documentation Alignment Sweep

Status assessment:

- The current plan requires documentation updates, but it does not explicitly enumerate the governed document families that must stay aligned with implementation.
- Given the repo rules, that is too implicit.

#### Task P0.1: Add a backlog-wide documentation sync pass for each delivered workstream

Outcome:

- Every shipped backlog item includes an explicit review of the governed documents that describe or operationalise that behaviour.

Required changes:

- Review and update, where applicable:
  - interface and output specs
  - ADRs
  - FDDs
  - runbooks
  - PRDs
  - planning/status docs such as MEMINIT-PLAN-005
- Remove stale statements that describe behaviour no longer matching the code.
- Add cross-references when a new doc becomes the primary source of truth.

Acceptance criteria:

- No workstream in this plan is marked complete until the relevant governed docs are aligned with the shipped code.
- If a document family is intentionally not updated, the reason is recorded in the PR or plan note rather than left implicit.

#### Task P0.2: Add a final documentation-consistency verification step before backlog closure

Outcome:

- The backlog can only be closed when code and governed documentation agree on exposed behaviour and operator workflow.

Required changes:

- Before closing a workstream, review changed behaviour against the relevant spec, ADR, FDD, and runbook set.
- Update examples, command snippets, JSON payloads, and acceptance tables that have drifted.

Acceptance criteria:

- Examples and command references match the implemented behaviour.
- Backlog tracking docs do not report completed features as partial or missing.

Sizing:

- Small, but mandatory for every other workstream

### 5.1 Workstream P1: Close the PRD-006 JSON Output Gap

Status assessment:

- The repository already computes rendered document content in `NewDocumentUseCase`.
- The CLI currently emits `rendered_content` from `result.content`.
- The domain result object still uses the ambiguous field name `content`.

This is therefore a contract-alignment task, not a greenfield feature.

#### Task P1.1: Align the domain result model with Templates v2 terminology

Outcome:

- `NewDocumentResult` uses an explicit `rendered_content` field, or an equivalent compatibility strategy is documented and tested.

Required changes:

- Update the domain entity in `src/meminit/core/domain/entities.py`.
- Preserve CLI/output compatibility during the rename or aliasing step.
- Update internal call sites in `src/meminit/core/use_cases/new_document.py` and `src/meminit/cli/main.py`.

Acceptance criteria:

- Code uses one unambiguous authoritative field for full rendered document text.
- No caller depends on an undocumented legacy field shape.
- Tests cover both success and dry-run paths.

#### Task P1.2: Verify the `new` JSON envelope matches PRD-006 and MEMINIT-SPEC-007

Outcome:

- `meminit new --format json` emits the full Templates v2 payload expected by the backlog documents that claim only a partial implementation.

Required changes:

- Review emitted JSON for `rendered_content`, `content_sha256`, template provenance, and section metadata.
- Fix any mismatch between runtime payload and documented contract.
- Update MEMINIT-PLAN-005 if the backlog status changes from partial to complete.

Acceptance criteria:

- One integration-style CLI test asserts the complete `data` shape for a templated document.
- One regression test asserts the payload matches the rendered file content exactly.
- Related planning/status docs no longer misreport implementation state.

#### Task P1.3: Reconcile command availability and local developer workflow

Outcome:

- The repo documentation distinguishes between repository source state and any older globally installed `meminit` binary.

Required changes:

- Update docs or runbooks where necessary to explain that repository code may be ahead of the installed CLI.
- Prefer verification via tests or local module execution when validating newly added commands.

Acceptance criteria:

- Developer-facing documentation does not imply that PATH-installed `meminit` is always the source of truth during local development.

Sizing:

- Small

### 5.2 Workstream P2: Deliver `meminit migrate-templates`

Status assessment:

- PRD-006 expects migration tooling.
- The codebase already warns users to run `meminit migrate-templates`.
- **IMPLEMENTED**: Command `meminit migrate-templates` is now available.

Implementation references:

- Spec: `docs/20-specs/spec-010-template-migration.md`
- Use case: `src/meminit/core/use_cases/migrate_templates.py`
- CLI: `src/meminit/cli/main.py` (command: `migrate-templates`)
- Tests: `tests/core/use_cases/test_migrate_templates.py`

#### Task P2.1: Write the implementation spec before code

Outcome:

- A concrete spec or design addendum defines migration inputs, outputs, dry-run semantics, and idempotency rules.

Required changes:

- Document supported legacy config keys and placeholder rewrites.
- Define failure modes for mixed or ambiguous template syntax.
- Define JSON output contract for dry-run and apply modes.

Acceptance criteria:

- The implementation can be reviewed against a written behaviour contract.
- Non-goals are explicit, especially around semantic document rewriting.

#### Task P2.2: Implement config migration for legacy template settings

Outcome:

- Legacy `type_directories` and legacy template configuration can be converted to `document_types` safely.

Required changes:

- Add a dedicated migration service with pure transformation logic.
- Support dry-run first.
- Reject ambiguous or conflicting input rather than guessing.

Acceptance criteria:

- Unit tests cover clean migration, conflict detection, and idempotency.
- CLI output clearly distinguishes proposed vs. applied changes.

#### Task P2.3: Implement placeholder syntax migration

Outcome:

- Legacy placeholders are rewritten to the Templates v2 `{{variable}}` form.

Required changes:

- Convert only supported legacy patterns documented in PRD-006 and MEMINIT-SPEC-007.
- Avoid touching non-template markdown or code fences incorrectly.
- Do not silently rewrite unknown placeholders.

Acceptance criteria:

- Tests cover single-file conversion, mixed-syntax rejection, and idempotent reruns.
- Migration preserves non-placeholder content byte-for-byte apart from intended rewrites.

#### Task P2.4: Expose the CLI command with safe defaults

Outcome:

- `meminit migrate-templates` exists and defaults to non-destructive preview behaviour.

Required changes:

- Add CLI registration and help text.
- Ensure output contracts and error codes are consistent with existing command patterns.

Acceptance criteria:

- `--dry-run` is the default unless there is a strong repo-wide reason to do otherwise.
- Help text explains when to use the command and what it will not rewrite.

#### Task P2.5: Complete end-to-end tests and user docs

Outcome:

- The migration path is documented and regression-tested.

Required changes:

- Add integration tests for full workflow.
- Update PRD/spec/runbook or planning docs that reference the command.

Acceptance criteria:

- A maintainer can migrate a small legacy fixture repo using only the documented flow.

Sizing:

- Medium

### 5.3 Workstream P3: Org-Level Config (`org-docops.config.yaml`)

Status assessment:

- This remains a valid deferred requirement from MEMINIT-PRD-001.
- It is still lower urgency than PRD-006 contract closure because the current repo primarily operates as a single repo.

#### Task P3.1: Confirm scope and architecture boundary

Outcome:

- The feature scope is reduced to the minimum useful product shape for v1 of org-level config.
- Scope is documented in [MEMINIT-PLAN-007](./plan-006a-org-config-scope.md).

Required changes:

- Review and align with scope decision in MEMINIT-PLAN-007.

Acceptance criteria:

- Scope is documented before any loader or schema code is written.

#### Task P3.2: Add schema and loader for org defaults

Outcome:

- Repositories can read a governed org-level config with deterministic precedence.

Required changes:

- Add schema and loader code.
- Validate boundary rules at load time.
- Keep repo config override behaviour explicit.

Acceptance criteria:

- Tests cover absent file, valid file, invalid file, and repo-overrides-org precedence.

#### Task P3.3: Integrate into commands that actually need it

Outcome:

- Only the commands that depend on configuration resolution are changed.

Required changes:

- Wire org config into the existing config loading path carefully.
- Avoid cross-cutting edits where no behaviour change is required.

Acceptance criteria:

- `new`, `check`, and other affected commands preserve existing behaviour when no org config exists.

#### Task P3.4: Document the migration and operating model

Outcome:

- Repo operators know when org config is appropriate and how precedence works.

Required changes:

- Update relevant planning/spec/runbook docs.
- Include at least one concrete example config.

Acceptance criteria:

- Docs explain deterministic local include behaviour and avoid any implication of runtime network fetch.

Sizing:

- Medium

### 5.4 Workstream P4: PRD-007 Integration Hardening

Status assessment:

- The plan should focus on actual gaps, not re-implement behaviour already present.
- Sorting validation already exists; any pre-commit work should reuse that logic.

#### Task P4.1: Extend `install-precommit` to cover project-state changes cleanly

Outcome:

- Repositories using `meminit install-precommit` receive a useful guardrail for `project-state.yaml` changes without duplicating validation logic.

Required changes:

- Decide whether to expand the existing hook or add a dedicated hook entry.
- Reuse existing `meminit check`, `doctor`, or shared validation logic rather than re-encoding rules in YAML hook scripts.

Acceptance criteria:

- One test verifies the installed pre-commit configuration covers the intended state-file workflow.
- The implementation does not create a second source of truth for sorting or validation rules.

#### Task P4.2: Document and validate the operator workflow

Outcome:

- Users understand how `project-state.yaml`, `meminit state`, `meminit doctor`, and generated indices fit together.

Required changes:

- Update runbook or PRD-adjacent docs if current operator flow is incomplete.

Acceptance criteria:

- A maintainer can update project state and understand which command validates or regenerates which artifact.

Deferred from the previous plan:

- A freshness warning based on file age is not included in this worklist.
- It is not justified as a committed requirement and risks adding noisy heuristics without measurable value.

Sizing:

- Small

### 5.5 Workstream P5: Technical Debt with Measurable Risk Reduction ✅

Status assessment:

- **COMPLETE**: Added behavioral tests for CLI edge cases and deterministic contention tests for ID allocation.
- CLI coverage for `src/meminit/cli/main.py` increased to ~65%.
- Multi-process locking verified.

#### Task P5.1: Add missing behavioural tests for CLI edge cases ✅

Outcome:

- Important CLI failure and compatibility paths are protected by tests.

Required changes:

- Identify currently untested or weakly tested branches in `src/meminit/cli/main.py`.
- Prioritise user-visible error handling, output contract correctness, and incompatible flag behaviour.

Acceptance criteria:

- New tests are tied to specific behaviours or bug classes, not only to coverage movement.
- Any coverage increase is treated as a side effect, not the goal.

#### Task P5.2: Add deterministic contention tests for ID allocation ✅

Outcome:

- ID-generation safety is validated without relying on flaky ad hoc stress runs.

Required changes:

- Start with a deterministic multi-process or lock-contention test fixture.
- Add a separate manual stress script only if the deterministic tests expose residual risk.

Acceptance criteria:

- Automated tests prove no duplicate IDs under the defined contention scenario.
- Manual stress tooling, if added, is clearly marked as non-gating.

Sizing:

- Small to medium

## 6. Dependency Order

Recommended execution order:

1. P0.1-P0.2 as a gate on every shipped workstream
2. P1.1-P1.2
3. P2.1-P2.5
4. P4.1-P4.2
5. P5.1-P5.2
6. P3.1-P3.4

Rationale:

- P0 prevents backlog closure with stale specs or runbooks.
- P1 closes an already-documented contract gap.
- P2 removes the largest remaining Templates v2 product gap.
- P4 and P5 are tactical hardening.
- P3 is still important, but lower urgency unless multi-repo adoption becomes active.

## 7. Definition of Done

An item in this plan is done only when all of the following are true:

1. The behaviour change is implemented with the smallest reasonable code change.
2. Automated tests prove the intended behaviour and key failure modes.
3. Documentation is updated in the same change across every affected governed document family: spec, ADR, FDD, runbook, PRD, and planning/status docs.
4. Any CLI or JSON contract change is explicitly reviewed for compatibility impact.
5. `meminit check` passes, or remaining violations are unrelated and documented.

## 8. History

| Version | Date       | Author | Changes                                                                                                 |
| ------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------- |
| 0.1     | 2026-03-07 | Kilo   | Initial atomic task list                                                                                |
| 0.2     | 2026-03-07 | Codex  | Reworked as a critical reviewed backlog worklist aligned to current codebase and engineering principles |
| 0.3     | 2026-03-07 | Codex  | Mark Workstream P5 complete (CLI tests and contention testing)                                          |
