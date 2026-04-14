---
document_id: MEMINIT-PLAN-013
type: PLAN
title: Phase 4 Detailed Implementation Plan
status: Draft
version: '0.2'
last_updated: '2026-04-14'
owner: GitCmurf
docops_version: '2.0'
area: AGENT
description: Detailed implementation plan for MEMINIT-PLAN-008 Phase 4 work queue
  layer.
keywords:
- phase-4
- planning
- state
- work-queue
related_ids:
- MEMINIT-PLAN-008
- MEMINIT-PLAN-003
- MEMINIT-PRD-007
---

> **Document ID:** MEMINIT-PLAN-013
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.2
> **Last Updated:** 2026-04-14
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Detailed implementation plan for MEMINIT-PLAN-008 Phase 4 work queue layer.

# PLAN: Phase 4 Detailed Implementation Plan

## Context

MEMINIT-PLAN-008 defines Phase 4 as the point where Meminit moves from
dashboard-oriented state reporting toward an actionable work-queue layer for
agentic coding agents.

This phase depends on Phase 2 because readiness, blockers, and next-work
queries become much more valuable once the repository graph exists. The goal is
to let an agent ask deterministic questions such as "what is ready next?" or
"what is blocked and by what?" without inventing its own local planning model.

Adoption note:

- The installed base outside Meminit remains only one explicit testbed.
- That makes it reasonable to evolve `project-state.yaml` more directly than a
  broadly distributed stable product would, as long as the migration and
  operator guidance are explicit.

## 1. Purpose

Define the detailed implementation steps for Phase 4 of MEMINIT-PLAN-008 so
that Meminit can provide a deterministic, queryable work-queue layer.

## 2. Scope

In scope:

- expansion of the project state model
- deterministic readiness, blocker, and next-action semantics
- new state query commands
- minimal dashboard or report updates needed to reflect the richer state
- migration guidance for the current state file shape

Out of scope:

- protocol governance
- semantic search
- streaming and NDJSON delivery
- non-deterministic prioritization or autonomous scheduling logic
- issue tracker integration outside the repo-owned state model

## 3. Work Breakdown

### 3.1 Workstream A: State Model v2 Definition

Problem:

- The current state model supports implementation-state reporting but not
  serious planning or execution coordination.

Implementation tasks:

1. Define the Phase 4 state fields, likely including:
   - `priority`
   - `depends_on`
   - `blocked_by`
   - `assignee`
   - `next_action`
2. Decide which fields are required, optional, or derived.
3. Define valid values and ordering rules for priority and readiness concepts.
4. Record migration expectations for existing `project-state.yaml` files.

Acceptance criteria:

1. The v2 state model is documented before implementation is finalized.
2. Required versus optional fields are explicit.
3. The model can answer readiness and blocker questions deterministically.

### 3.2 Workstream B: State Mutation and Migration Path

Problem:

- A richer model is only useful if it can be updated safely and predictably.

Implementation tasks:

1. Extend the state write path to support the new fields.
2. Decide whether the current `state set` surface grows flags or whether a new
   mutation surface is warranted.
3. Ensure migrations from the current file shape are explicit and safe.
4. Add tests for create, update, and partial-update behavior.

Acceptance criteria:

1. Existing state files can be upgraded without manual guesswork.
2. State mutations remain deterministic and idempotent where appropriate.
3. Tests cover both legacy and v2-shaped state content.

### 3.3 Workstream C: Query Commands for Ready, Blocked, and Next Work

Problem:

- The current `state get` and `state list` commands are too thin for agent
  execution planning.

Implementation tasks:

1. Add query surfaces such as:
   - `state next`
   - `state blockers`
   - `state list --ready`
2. Define deterministic selection rules for "next" so agents see stable
   results for the same underlying state.
3. Decide how document graph relationships influence readiness when dependency
   data is incomplete.
4. Add adapter tests for the new command paths and JSON outputs.

Acceptance criteria:

1. Agents can retrieve ready work and blocker information directly.
2. "Next" selection has clear, documented tie-breaking rules.
3. The query outputs are machine-readable and contract-tested.

### 3.4 Workstream D: Dashboard and Reporting Alignment

Problem:

- The richer state model should not live only in raw YAML and CLI output.

Implementation tasks:

1. Update any state-derived dashboards or reports that should expose readiness
   and blocker data.
2. Keep those outputs bounded to deterministic information rather than
   speculative prioritization.
3. Ensure the richer model does not silently break current dashboard behavior.
4. Validate the new reporting shape in the external testbed.

Acceptance criteria:

1. The richer state data is visible in the supported operator surfaces.
2. Existing reporting remains coherent after the model change.
3. The external testbed confirms the new queries are practically useful.

### 3.5 Workstream E: Documentation and Operating Guidance

Problem:

- A work-queue layer changes how maintainers and agents should manage repo
  planning data.

Implementation tasks:

1. Document the new state fields and their intended use.
2. Record examples of ready, blocked, and next-action workflows.
3. Update the planning chain if the implementation reveals new dependencies.
4. Keep the phase bounded to deterministic repo-local planning support.

Acceptance criteria:

1. The operating model is understandable without reading the code.
2. Maintainers can update the richer state file confidently.
3. Code, docs, and tests remain synchronized.

## 4. Recommended Delivery Sequence

1. Workstream A: State Model v2 Definition
2. Workstream B: State Mutation and Migration Path
3. Workstream C: Query Commands for Ready, Blocked, and Next Work
4. Workstream D: Dashboard and Reporting Alignment
5. Workstream E: Documentation and Operating Guidance

Reason:

- The state model must be stable before mutation and query surfaces are added.
- Query behavior depends on the richer stored data.
- Reporting and operator guidance should follow once the semantics are stable.

## 5. Exit Criteria for Phase 4

Phase 4 can be considered complete when all of the following are true:

1. Meminit supports a documented richer state model.
2. Agents can query ready work, blockers, and a deterministic next action.
3. Existing state files have an explicit migration path.
4. The Meminit repo and the external testbed both validate the new planning
   workflow.
5. The state docs, examples, and tests reflect the shipped behavior.

## 6. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-14 | GitCmurf | Initial draft created via `meminit new` |
| 0.2 | 2026-04-14 | Codex | Replaced stub with detailed Phase 4 workstreams, sequencing, and exit criteria |
