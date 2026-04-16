---
document_id: MEMINIT-PLAN-014
type: PLAN
title: Phase 5 Detailed Implementation Plan
status: Draft
version: '0.2'
last_updated: '2026-04-14'
owner: GitCmurf
docops_version: '2.0'
area: AGENT
description: Detailed implementation plan for MEMINIT-PLAN-008 Phase 5 scale and streaming
  work.
keywords:
- phase-5
- planning
- streaming
- ndjson
related_ids:
- MEMINIT-PLAN-008
- MEMINIT-PLAN-003
- MEMINIT-PRD-005
---

> **Document ID:** MEMINIT-PLAN-014
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.2
> **Last Updated:** 2026-04-14
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Detailed implementation plan for MEMINIT-PLAN-008 Phase 5 scale and streaming work.

# PLAN: Phase 5 Detailed Implementation Plan

## Context

MEMINIT-PLAN-008 defines Phase 5 as the scale and streaming phase. By the time
this phase starts, the expectation is that the runtime contract is stable
enough that Meminit can expose large-output workflows cleanly rather than
forcing every consumer to buffer one large JSON object.

This phase is intentionally about delivery ergonomics and large-repo behavior.
It is not a license to reopen earlier contract ambiguity. The standard
non-streaming surfaces should already be settled by earlier phases.

Adoption note:

- Outside Meminit, only one explicit testbed repo currently exists.
- That low adoption makes it reasonable to choose the cleanest streaming shape
  rather than preserving awkward temporary compromises, provided the upgrade
  story is documented.

## 1. Purpose

Define the detailed implementation steps for Phase 5 of MEMINIT-PLAN-008 so
that Meminit can handle large-output workflows with deterministic streaming and
incremental rebuild support.

## 2. Scope

In scope:

- normative NDJSON or equivalent streaming contract definition
- streaming support for the large-output command set
- incremental index rebuild design and implementation
- tests and fixtures for large-output behavior
- operator guidance for choosing standard versus streaming modes

Out of scope:

- semantic search
- protocol governance
- work-queue semantics
- non-deterministic background services
- arbitrary long-running daemons outside the supported CLI model

## 3. Work Breakdown

### 3.1 Workstream A: Streaming Contract Decision

Problem:

- The repo needs one explicit streaming design instead of ad hoc large-output
  behavior.

Implementation tasks:

1. Decide the supported streaming interface shape, such as `--format ndjson`,
   a separate stream flag, or an equivalent explicit contract.
2. Define record ordering, record types, final-summary behavior, and failure
   signaling for streaming mode.
3. Specify which commands participate in the first streaming wave.
4. Record how streaming capability is advertised through the runtime contract.

Acceptance criteria:

1. The streaming shape is documented before implementation is finalized.
2. Consumers can tell exactly how a streamed run begins, progresses, and ends.
3. The chosen design is explicit enough to validate with contract tests.

### 3.2 Workstream B: Shared Streaming Emitter Infrastructure

Problem:

- If each command hand-rolls its own streaming behavior, the contract will
  drift immediately.

Implementation tasks:

1. Build shared emitter utilities for streaming records and final summaries.
2. Ensure stdout remains the sole machine channel while logs remain on stderr.
3. Define how correlation and run metadata appear in streamed records.
4. Add tests for ordering, failure behavior, and stderr isolation.

Acceptance criteria:

1. Streaming behavior is implemented through shared infrastructure.
2. Machine-consumed stdout remains deterministic and log-free.
3. Correlation and run metadata are consistent with the non-streaming contract.

### 3.3 Workstream C: Command Rollout for Large-Output Surfaces

Problem:

- Streaming should land where it materially helps rather than being added
  indiscriminately.

Implementation tasks:

1. Prioritize the first command set for streaming support, expected to include
   `index`, `scan`, and `context --deep`.
2. Keep current non-streaming behavior available unless a deliberate breaking
   change is approved and documented.
3. Add tests for streamed success, streamed failure, and output stability.
4. Validate the chosen command set in the external testbed.

Acceptance criteria:

1. The selected large-output commands support the documented streaming mode.
2. Existing non-streaming workflows remain explicit and understood.
3. The external testbed can consume the streamed outputs as documented.

### 3.4 Workstream D: Incremental Index Rebuilds

Problem:

- Streaming helps with output size, but it does not by itself reduce needless
  recomputation in larger repos.

Implementation tasks:

1. Design an incremental rebuild model for the index artifact.
2. Decide the cache or fingerprint boundary used to detect unchanged content.
3. Keep incremental behavior deterministic and debuggable rather than opaque.
4. Add tests for correctness under repeated, no-change, and partial-change
   rebuilds.

Acceptance criteria:

1. Incremental rebuilds produce the same final artifact as full rebuilds.
2. Cache invalidation rules are explicit and test-covered.
3. Incremental behavior does not rely on hidden mutable global state.

### 3.5 Workstream E: Documentation, Upgrade Notes, and Scale Fixtures

Problem:

- A streaming and incremental phase is only successful if the operator guidance
  is as clear as the implementation.

Implementation tasks:

1. Document when to use standard JSON versus streaming mode.
2. Record upgrade notes for the external testbed and future adopters.
3. Build fixtures that exercise larger output sets without turning the suite
   into an unreliable performance benchmark.
4. Update the planning chain if implementation constraints alter sequencing.

Acceptance criteria:

1. Operators can choose the right output mode intentionally.
2. The upgrade story is explicit.
3. Code, docs, and tests remain synchronized.

## 4. Recommended Delivery Sequence

1. Workstream A: Streaming Contract Decision
2. Workstream B: Shared Streaming Emitter Infrastructure
3. Workstream C: Command Rollout for Large-Output Surfaces
4. Workstream D: Incremental Index Rebuilds
5. Workstream E: Documentation, Upgrade Notes, and Scale Fixtures

Reason:

- The streaming contract must be decided before command rollout begins.
- Shared infrastructure should prevent per-command drift.
- Incremental rebuilds then land on top of the stable output model.

## 5. Exit Criteria for Phase 5

Phase 5 can be considered complete when all of the following are true:

1. Meminit exposes a documented streaming mode for the selected large-output
   commands.
2. Streamed runs preserve deterministic machine output and stderr isolation.
3. Incremental index rebuilds are implemented and test-covered.
4. The Meminit repo and the external testbed both validate the new scale
   workflow.
5. The operator and upgrade docs describe the shipped behavior clearly.

## 6. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-14 | GitCmurf | Initial draft created via `meminit new` |
| 0.2 | 2026-04-14 | Codex | Replaced stub with detailed Phase 5 workstreams, sequencing, and exit criteria |
