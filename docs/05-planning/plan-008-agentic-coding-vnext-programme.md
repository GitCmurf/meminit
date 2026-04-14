---
document_id: MEMINIT-PLAN-008
type: PLAN
title: Agentic Coding vNext Programme
status: Draft
version: '0.1'
last_updated: '2026-04-14'
owner: GitCmurf
docops_version: '2.0'
area: AGENT
description: Phased improvement programme for Meminit as a stronger platform for agentic
  coding agents.
keywords:
- agent
- roadmap
- planning
- orchestration
related_ids:
- MEMINIT-STRAT-001
- MEMINIT-PLAN-003
- MEMINIT-PRD-003
- MEMINIT-PRD-005
- MEMINIT-PRD-007
---

> **Document ID:** MEMINIT-PLAN-008
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-04-14
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Phased improvement programme for Meminit as a stronger platform for agentic coding agents.

# PLAN: Agentic Coding vNext Programme

## Context

Meminit already has a meaningful agent-facing foundation:

- deterministic JSON envelopes for core CLI commands
- `meminit context` for repo discovery
- index and resolution helpers
- project-state support with dashboard generation
- repo bootstrap assets for `AGENTS.md` and a bundled `meminit-docops` skill

That foundation is good enough for scripted use, but it is not yet a strong
platform for agentic coding agents operating at scale.

The current gaps are structural, not cosmetic:

1. The CLI is not yet self-describing at runtime.
   - There is no `meminit capabilities --format json`.
   - There is no `--correlation-id`.
   - There is no machine-readable `explain` path for error codes.
2. The repository index is still an inventory, not a graph.
   - It does not yet expose resolved cross-document links or supersession edges
     as committed in MEMINIT-STRAT-001.
3. Agent protocol surfaces are bootstrapped but not governed.
   - `AGENTS.md` and skill files can drift from live CLI behavior.
4. State support is useful for dashboards but too thin for work-queue use.
   - It does not yet give agents a first-class next-action surface.
5. Scale-oriented outputs are still monolithic.
   - Large-output commands do not support streaming formats.

This plan turns those gaps into a phased programme that is small-PR friendly,
DocOps-compliant, and sequenced to reduce rework.

## 1. Purpose

Define the next implementation programme for Meminit as a stronger tool for
agentic coding agents, with:

- explicit phases
- milestone-level acceptance criteria
- a proposed governed document set
- clear sequencing between contract work, graph work, protocol work, and
  scale work

This plan is intentionally implementation-aware but not code-prescriptive. It
states outcomes, decision gates, and documentation expectations; the detailed
feature design belongs in the PRDs, FDDs, and specs listed in Section 7.

## 2. Planning Principles

This programme follows the repo's non-negotiables:

1. Code, docs, and tests move together.
2. Runtime contracts come before convenience features.
3. Deterministic machine behavior takes priority over presentation polish.
4. Existing governed docs are updated where they are already the right source
   of truth; new docs are created only where a new boundary is warranted.
5. Each phase must leave the repo in a shippable, validated state.

## 3. Baseline Assessment

### 3.1 What already exists

- Agent output envelopes and schema validation
- Shared CLI output flags
- `meminit context`
- `meminit index|resolve|identify|link`
- `project-state.yaml` with `state set|get|list`
- Bundled `AGENTS.md` and `meminit-docops` skill assets
- Strong doc/test coverage around many existing contracts

### 3.2 What is not yet sufficient

| Area | Current state | Why it is still a gap for coding agents |
| ---- | ------------- | --------------------------------------- |
| Runtime capability discovery | Documented in PRD-005, not implemented | Agents still need repo-local assumptions and wrappers |
| Multi-step orchestration metadata | `run_id` only | Cross-command tracing is still external and brittle |
| Repository graph | Inventory + state merge | Agents still need secondary scans to reason about references and supersession |
| Protocol surfaces | Created once | No built-in drift detection or sync path |
| Work queue support | Dashboard-oriented | No direct next-task, blockers, or readiness query model |
| Large-output ergonomics | Single JSON object | Monorepo-scale scans/indexes remain heavyweight |

### 3.3 Immediate quality gate

Before starting new feature delivery, the current foundation must be made
fully reliable. As of this plan's drafting, the repository test suite is not
green because a `fix` path writes a date that can drift by one day across
clock/timezone assumptions. That class of issue is small in code size but
high leverage in agent workflows because it undermines deterministic repair
loops.

## 4. Programme Summary

| Phase | Name | Primary outcome | Exit condition |
| ----- | ---- | --------------- | -------------- |
| 0 | Foundation Hardening | Green, deterministic baseline | `pytest` green and contract matrix in place |
| 1 | Agent Contract Core | Self-describing CLI surface | Capabilities, correlation, and explain implemented |
| 2 | Repository Graph | Index becomes graph-grade agent artifact | Graph fields emitted and validated |
| 3 | Protocol Governance | `AGENTS.md` and skills become governable clients | Drift can be detected and synced |
| 4 | Work Queue Layer | Agents can ask "what next?" without repo-wide inference | State/query surfaces support readiness and blockers |
| 5 | Scale and Streaming | Large repos are handled cleanly | NDJSON and incremental workflows available |

## 5. Phased Programme

### 5.1 Phase 0: Foundation Hardening

Objective:

- Stabilize the current behavior so later agent-facing features build on a
  reliable baseline.

Work in scope:

- Fix the `last_updated` date-source inconsistency in remediation paths.
- Add a command-matrix contract test that verifies every CLI command that
  claims JSON support emits a schema-valid envelope.
- Tighten stdout/stderr isolation tests for machine-consumed modes.
- Reconcile any remaining drift between current implementation and the
  normative agent output docs.

Acceptance criteria:

1. `pytest` passes in the repository root.
2. The `fix` path uses one consistent date source for governed metadata writes.
3. The CLI command matrix has automated coverage for JSON support and envelope
   validity.
4. PRD/SPEC text describing the current agent contract is not materially out of
   sync with the code.

Definition of done:

- Code merged
- Tests added or updated
- Relevant docs updated

### 5.2 Phase 1: Agent Contract Core

Objective:

- Make Meminit self-describing and easier to orchestrate without brittle
  wrapper logic.

Work in scope:

- Implement `meminit capabilities --format json`.
- Add optional `--correlation-id` support across agent-facing commands.
- Implement `meminit explain <ERROR_CODE> --format json`.
- Expose capability metadata in a deterministic, fast, filesystem-light way.

Acceptance criteria:

1. `meminit capabilities --format json` exists and is deterministic.
2. Capability output includes supported commands, standard flags, output
   formats, and contract feature flags.
3. `--correlation-id` is echoed back as `correlation_id` when supplied and
   omitted otherwise.
4. `meminit explain <ERROR_CODE> --format json` returns stable, machine-readable
   remediation guidance.
5. Tests validate capability output and correlation behavior.

Definition of done:

- Runtime feature implemented
- Error-code and contract docs updated
- New acceptance tests added

### 5.3 Phase 2: Repository Graph

Objective:

- Upgrade the index from "document inventory" to "document graph".

Work in scope:

- Extend index entries with resolved links, related-document edges, and
  supersession edges.
- Define which edge types are guaranteed by the artifact and which are
  best-effort.
- Add index-backed integrity checks where that creates clear product value.

Acceptance criteria:

1. `meminit index` emits the graph fields committed in MEMINIT-STRAT-001 or
   explicitly records any deferral in updated strategy/planning docs.
2. The artifact schema and examples are documented.
3. Edge extraction is deterministic and covered by tests.
4. `resolve`, `identify`, and `link` remain backward compatible.

Definition of done:

- Graph fields documented and shipped
- Existing resolution helpers remain stable
- Test fixtures cover cross-doc references and supersession

### 5.4 Phase 3: Protocol Governance

Objective:

- Treat repo-local protocol files as clients of the Meminit contract, not as
  static scaffolding.

Work in scope:

- Define the supported protocol surfaces: at minimum `AGENTS.md` and skill
  files.
- Add a drift-check mechanism such as `meminit protocol check`.
- Add a safe refresh/sync path such as `meminit protocol sync`.
- Introduce a lightweight version stamp or capability reference model so
  generated protocol content can be audited in CI.

Acceptance criteria:

1. Protocol surfaces and their contract relationship are explicitly documented.
2. Drift between live CLI capabilities and shipped protocol assets can be
   detected automatically.
3. The sync path is additive and safe for brownfield repos.
4. The bundled `AGENTS.md` and `meminit-docops` skill are upgraded to point to
   the runtime contract rather than static assumptions where possible.

Definition of done:

- Drift-check command or equivalent shipped
- Protocol docs updated
- CI guidance added

### 5.5 Phase 4: Work Queue Layer

Objective:

- Give agents a first-class coordination surface for "what is ready, blocked,
  or next".

Work in scope:

- Extend `project-state.yaml` with optional planning fields such as priority,
  dependencies, blockers, and next action.
- Add query-oriented commands or subcommands that answer ready/blocked/next
  questions directly.
- Keep byte-invariance and the current governance/status split intact.

Acceptance criteria:

1. The state model remains optional and backward compatible for repos that do
   not use advanced planning fields.
2. At least one query path exists for next-work or ready-work retrieval.
3. Validation rules for new state fields are deterministic and documented.
4. Index output can surface the richer state without breaking existing clients.

Definition of done:

- State schema updated
- Query surface implemented
- Dashboard/index integration documented and tested

### 5.6 Phase 5: Scale and Streaming

Objective:

- Make Meminit more usable for large repos and long-lived orchestrators.

Work in scope:

- Add `ndjson` streaming for large-output commands such as `scan`, `index`, and
  deep context modes.
- Define deterministic record ordering and end-of-stream behavior.
- Investigate incremental rebuild/update paths for index-heavy workflows.

Acceptance criteria:

1. At least the agreed large-output commands support a documented streaming
   format.
2. Streaming behavior is covered by schema/rule tests.
3. STDOUT remains machine-safe and logs remain isolated.
4. The docs explain when agents should prefer standard JSON vs streaming.

Definition of done:

- Streaming contract shipped
- Runbook guidance added
- No regression to existing JSON contract consumers

## 6. Delivery Order and Dependency Rules

The phases are intentionally sequenced:

1. Phase 0 before all other work.
2. Phase 1 before Phase 3 and Phase 5.
3. Phase 2 before any index-backed link validation hardening.
4. Phase 4 only after Phase 2 has established the stronger repository model.
5. Phase 5 after the standard runtime contract is stable enough to stream.

The key dependency logic is:

- self-description before protocol governance
- graph before sophisticated coordination
- deterministic core before scale features

## 7. Proposed Governed Document Set

This programme does not need every item to be a new document. Where an
existing document already owns the boundary, update it instead of creating a
parallel source of truth.

| Action | Type | Proposed document | Reason |
| ------ | ---- | ----------------- | ------ |
| Update | PRD | MEMINIT-PRD-005 Agent Interface v2 | It already owns capabilities, correlation, streaming, and protocol integration scope |
| Update | SPEC | MEMINIT-SPEC-006 ErrorCode Enum | It already owns the canonical error registry that `explain` should build on |
| Update | PLAN | MEMINIT-PLAN-003 Project Roadmap | It remains the sequencing source of truth and should reference this plan |
| New | FDD | Agent Capabilities and Explain Commands | Implementation boundary for `capabilities`, `correlation_id`, and `explain` |
| New | FDD | Index Graph Enrichment | Implementation boundary for links, related IDs, and supersession edges |
| New | FDD | Protocol Surface Governance | Implementation boundary for protocol drift detection and sync |
| New | FDD | Agent Work Queue Queries | Implementation boundary for richer state queries and readiness/blocker logic |
| New | SPEC | NDJSON Streaming Contract | Normative streaming record shape and ordering rules |
| New | RUNBOOK | Agent Integration and Upgrade Workflow | Operator guidance for adopting the new capability surfaces safely |

Document creation rules:

- Do not create the new FDD/SPEC/RUNBOOK set until the corresponding phase is
  approved to start.
- If a phase is reduced in scope, reduce the document set as well rather than
  creating speculative artifacts.

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
| ---- | ------ | ---------- |
| Capability output becomes a second drifting contract | High | Treat `capabilities` as a tested, versioned artifact with deterministic ordering |
| Protocol sync becomes destructive in brownfield repos | High | Default to check/report mode; require explicit action for writes |
| Graph extraction overreaches and becomes heuristic-heavy | Medium | Ship a narrow, well-defined first edge set and test it thoroughly |
| Work queue scope expands into project management | Medium | Keep fields optional and tightly tied to agent execution needs |
| Streaming introduces contract ambiguity | High | Define record order, summary semantics, and error behavior before implementation |

## 9. Closure Criteria for the Programme

This programme is complete when:

1. The planned phases that are approved for delivery have shipped with aligned
   code, docs, and tests.
2. Meminit can describe its own capabilities at runtime.
3. The repository index is strong enough to serve as an agent navigation graph.
4. Protocol surfaces can be checked for drift.
5. Agents have a direct way to retrieve actionable next-work information.

## 10. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-14 | GitCmurf | Initial draft created via `meminit new` |
| 0.2 | 2026-04-14 | Codex | Replaced stub with phased vNext programme, acceptance criteria, and proposed governed document set |
