---
document_id: MEMINIT-PLAN-012
type: PLAN
title: Phase 3 Detailed Implementation Plan
status: Draft
version: '0.2'
last_updated: '2026-04-14'
owner: GitCmurf
docops_version: '2.0'
area: AGENT
description: Detailed implementation plan for MEMINIT-PLAN-008 Phase 3 protocol governance
  work.
keywords:
- phase-3
- planning
- protocol
- governance
related_ids:
- MEMINIT-PLAN-008
- MEMINIT-PLAN-003
- MEMINIT-PRD-005
---

> **Document ID:** MEMINIT-PLAN-012
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.2
> **Last Updated:** 2026-04-14
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Detailed implementation plan for MEMINIT-PLAN-008 Phase 3 protocol governance work.

# PLAN: Phase 3 Detailed Implementation Plan

## Context

MEMINIT-PLAN-008 defines Phase 3 as the point where repo-local protocol files
such as `AGENTS.md` and the bundled skill assets stop being one-time scaffolds
and become governable clients of the Meminit contract.

This phase depends on Phase 1 because protocol governance without a
self-describing runtime contract would only codify drift. The goal is not to
turn protocol files into rigid generated artifacts with no room for local
judgment. The goal is to make supported sections verifiable and synchronizable.

Adoption note:

- The external usage footprint is still limited to one explicit testbed.
- That means this phase can choose a clean generated-versus-user-managed model
  without supporting many legacy protocol variants.

## 1. Purpose

Define the detailed implementation steps for Phase 3 of MEMINIT-PLAN-008 so
that Meminit can detect and remediate drift in agent-facing protocol files.

## 2. Scope

In scope:

- a governable model for `AGENTS.md` and bundled protocol assets
- drift detection and reporting
- a safe sync path with preview-first behavior
- test coverage for generated and user-managed regions
- CI and operator guidance for ongoing enforcement

Out of scope:

- broad semantic rewriting of user-authored guidance
- work-queue state expansion
- streaming and scale work
- semantic search
- non-repo protocol targets outside the explicitly supported asset set

## 3. Work Breakdown

### 3.1 Workstream A: Protocol Asset Boundary Definition

Problem:

- The current repo has protocol assets, but there is no explicit contract for
  which parts are generated, which parts are user-managed, and how drift is
  recognized.

Implementation tasks:

1. Inventory the supported protocol assets in scope for this phase.
2. Define generated regions, user-managed regions, and version stamps.
3. Decide how Meminit identifies ownership in a file without making user
   content fragile.
4. Record the rules in implementation docs before writing sync logic.

Acceptance criteria:

1. Every supported protocol file has an explicit ownership model.
2. User-managed content has a protected place to live.
3. Drift rules are precise enough to produce deterministic diagnostics.

### 3.2 Workstream B: Protocol Check Command

Problem:

- Operators and agents need a read-only way to know whether protocol assets are
  aligned with the live Meminit contract.

Implementation tasks:

1. Implement a protocol drift check surface, likely as `meminit protocol check`
   or an equivalent supported command shape.
2. Compare live assets against the supported generated model.
3. Produce machine-readable drift output that distinguishes:
   - missing assets
   - stale generated content
   - unsupported manual edits inside generated regions
4. Add tests for compliant, drifting, and partially customized cases.

Acceptance criteria:

1. Protocol drift can be detected without mutating the repo.
2. The output is actionable for both humans and agents.
3. Drift diagnostics are deterministic and contract-tested.

### 3.3 Workstream C: Protocol Sync Command

Problem:

- Drift detection without a supported repair path leaves operators doing manual,
  error-prone copy-editing.

Implementation tasks:

1. Implement a preview-first sync surface, likely `meminit protocol sync`.
2. Default the sync flow to dry-run or equivalent non-mutating preview mode.
3. Preserve user-managed regions while refreshing generated regions and version
   stamps.
4. Add tests proving idempotence and non-destructive behavior.

Acceptance criteria:

1. Supported drift can be repaired without manual copy-paste.
2. User-managed content is preserved.
3. Re-running sync on an already aligned repo is a no-op.

### 3.4 Workstream D: CI and Bundled Skill Alignment

Problem:

- Even a good local sync/check flow will drift again if enforcement is not
  wired into normal repo workflows.

Implementation tasks:

1. Decide where protocol checks fit into local and CI workflows.
2. Update bundled skill and setup guidance if the supported protocol model
   changes.
3. Add coverage showing that capabilities output and protocol generation remain
   aligned.
4. Validate the resulting workflow in the external testbed.

Acceptance criteria:

1. The supported enforcement path is documented and testable.
2. Bundled protocol assets remain aligned with live CLI behavior.
3. The external testbed can use the new check and sync workflow cleanly.

### 3.5 Workstream E: Documentation and Rollout Boundaries

Problem:

- Protocol governance can become intrusive if rollout boundaries are not stated
  explicitly.

Implementation tasks:

1. Document the supported asset set and non-goals of the phase.
2. Record how early adopters should handle local customizations.
3. Update planning docs if the phase boundary shifts materially.
4. Ensure the implementation documents explain what Meminit will and will not
   rewrite.

Acceptance criteria:

1. The rollout model is explicit and bounded.
2. Local customization guidance exists.
3. Code, docs, and tests remain synchronized.

## 4. Recommended Delivery Sequence

1. Workstream A: Protocol Asset Boundary Definition
2. Workstream B: Protocol Check Command
3. Workstream C: Protocol Sync Command
4. Workstream D: CI and Bundled Skill Alignment
5. Workstream E: Documentation and Rollout Boundaries

Reason:

- Generated-region ownership must be decided before any command can check or
  sync safely.
- Read-only check behavior should land before mutation behavior.
- CI and bundled-skill integration should follow once the local contract is
  stable.

## 5. Exit Criteria for Phase 3

Phase 3 can be considered complete when all of the following are true:

1. Supported protocol assets have an explicit generated-versus-user-managed
   model.
2. Meminit can detect protocol drift in a machine-readable way.
3. Meminit can sync supported protocol assets without clobbering user-managed
   content.
4. The Meminit repo and the external testbed both validate the supported
   workflow.
5. The governing docs describe the rollout and customization boundaries.

## 6. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-14 | GitCmurf | Initial draft created via `meminit new` |
| 0.2 | 2026-04-14 | Codex | Replaced stub with detailed Phase 3 workstreams, sequencing, and exit criteria |
