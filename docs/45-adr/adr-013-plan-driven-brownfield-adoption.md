---
document_id: MEMINIT-ADR-013
type: ADR
title: Plan-Driven Brownfield Adoption
status: Approved
version: "0.1"
last_updated: "2026-03-01"
owner: GitCmurf
area: Adoption
docops_version: "2.0"
template_type: adr-standard
template_version: 1.1
---

> **Document ID:** MEMINIT-ADR-013
> **Owner:** GitCmurf
> **Status:** Approved
> **Version:** 0.1
> **Last Updated:** 2026-03-01
> **Type:** ADR
> **Area:** Adoption

# MEMINIT-ADR-013: Plan-Driven Brownfield Adoption

- **Date decided:** 2026-03-01
- **Status:** Approved
- **Deciders:** GitCmurf
- **Consulted:**
- **Informed:**
- **References:** MEMINIT-PRD-004

## 1. Context & Problem Statement

Meminit's `scan` and `fix` workflows for brownfield repositories previously required heavy manual interpretation and iteration. Scans provided high-level hints, while fixes applied a limited set of changes without a concrete execution plan. This created a high-risk migration path for repositories with hundreds of existing Markdown files, as humans and agents lacked a deterministic view of what actions would be taken, why, and whether those actions were safe.

## 2. Decision Drivers

- **Safety:** Prevent destructive actions (e.g., deletions, unintentional overwrites).
- **Determinism:** Provide a stable, repeatable, and machine-parseable execution plan.
- **Reviewability:** Give humans and agents a clear `scan` -> `plan` -> `review` -> `fix` workflow.
- **Agent Integration:** Emit output contracts aligning with the v1 Agent Interface.

## 3. Options Considered

- **Option A:** Direct inline fix application (legacy).
  - Pros: Simplest implementation.
  - Cons: High risk; hard to preview exact transformations; difficult for agents to reason about without parsing logs.
- **Option B:** Plan-driven execution with strict action enums and safety validation (Chosen).
  - Pros: High safety; explicit human/agent review gate; deterministic execution.
  - Cons: Requires modeling a new plan schema and separating heuristic generation from mutation logic.

## 4. Decision Outcome

- **Chosen option:** Option B
- **Why this option:** It strongly aligns with the safety-first strategy (MEMINIT-STRAT-001) and the DocOps Constitution. By separating heuristics into a generated `MigrationPlan`, users (and agents) can review exact planned mutations, including confidences and rationales, before execution. Strict action enums ensure that `fix --plan` applies a validated set of operations without unexpected filesystem changes.
- **Scope/Applicability:** Brownfield repository migrations managed by `meminit scan` and `meminit fix`.
- **Status gates:** Approved.

## 5. Consequences

- Positive: Brownfield repositories can reach first-green much faster and safer. The workflow is highly compatible with the Agent Interface.
- Negative / trade-offs: `meminit fix` becomes more complex as it must parse, validate, and orchestrate actions defined in a plan.

## 6. Implementation Notes

- Plan artifacts will reuse the Meminit JSON envelope.
- Plan actions will be a closed enum (e.g., `insert_metadata_block`, `update_metadata`, `move_file`, `rename_file`).
- Plan application (`meminit fix --plan`) will strictly enforce non-destructive invariants (no deletes, no overwrites unless explicitly permitted by safety flags) and drift detection/preconditions.

## 7. Validation & Compliance

- Tests required: Model parsing/serialization, stable deterministic sorting, unsafe path rejection, precondition mismatch tests, and full E2E idempotency checks.

## 8. Alternatives Rejected

- Inline interactive prompting: Rejected because it breaks headless agentic workflows and deterministic outputs.

## 9. Supersession

- Supersedes: none
- Superseded by: none

## 10. Notes for Agents

- Code anchors: `src/meminit/core/services/scan_plan.py`, `src/meminit/core/use_cases/scan_repository.py`, `src/meminit/core/use_cases/fix_repository.py`
