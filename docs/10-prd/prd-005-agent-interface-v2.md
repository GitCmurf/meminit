---
document_id: MEMINIT-PRD-005
type: PRD
title: Agent Interface v2
status: Draft
version: "0.2"
last_updated: 2026-02-23
owner: GitCmurf
docops_version: "2.0"
area: Agentic Integration
description: "Next-step improvements beyond Agent Interface v1: capability negotiation, streaming outputs, correlation support, stronger schemas, and better integration with agent protocol files/skills."
keywords:
  - agent
  - interface
  - capabilities
  - streaming
  - ndjson
  - correlation
  - session
  - skills
  - protocol
  - docops
related_ids:
  - MEMINIT-STRAT-001
  - MEMINIT-PLAN-003
  - MEMINIT-PRD-003
  - MEMINIT-SPEC-004
  - MEMINIT-RUNBOOK-006
  - ORG-GOV-001
  - MEMINIT-GOV-003
---

# PRD: Agent Interface v2

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PRD-005
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.2
> **Last Updated:** 2026-02-23
> **Type:** PRD
> **Area:** Agentic Integration

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Context and Motivation](#2-context-and-motivation)
3. [Problem Statement](#3-problem-statement)
4. [Goals and Non-Goals](#4-goals-and-non-goals)
5. [Scope](#5-scope)
6. [Proposed Requirements](#6-proposed-requirements-fr)
7. [Migration and Versioning Strategy](#7-migration-and-versioning-strategy)
8. [Open Questions (With Options and Recommendations)](#8-open-questions-with-options-and-recommendations)
9. [Acceptance Criteria](#9-acceptance-criteria-ship-ready-definition)
10. [Risks and Mitigations](#10-risks-and-mitigations)
11. [Related Documents](#11-related-documents)
12. [Document History](#12-document-history)

---

## 1. Executive Summary

Agent Interface v1 ([MEMINIT-PRD-003](../10-prd/prd-003-agent-interface-v1.md))
standardizes Meminit's CLI as a deterministic orchestration surface: uniform
flags, uniform JSON envelopes, stable error semantics, and a repository
bootstrap mechanism (`meminit context`).

This PRD (Agent Interface v2) captures known next-step improvements that are
deliberately **out of scope** for v1 implementation, but are high-leverage for:

- long-lived, production agent orchestrators,
- multi-tool environments (Codex skills, `AGENTS.md`, IDE agents, CI),
- large monorepos where outputs can be large and discovery must be cheap,
- and a mature contract discipline (capabilities, version negotiation, and a
  formal error-code registry).

**Design center:** still agent orchestrators (per [MEMINIT-STRAT-001](../02-strategy/strat-001-project-meminit-vision.md)).

---

## 2. Context and Motivation

### 2.1 What v1 Delivers (Baseline)

Agent Interface v1 establishes the baseline production contract:

- deterministic JSON envelope outputs for all commands (once migrated),
- strong separation of STDOUT (machine output) and STDERR (logs),
- consistent exit-code semantics and error taxonomy,
- and `meminit context` as the portability primitive for monorepos.

### 2.2 Why v2 Exists (What v1 Does Not Solve)

Even with a strong v1 envelope, real production agent usage quickly hits:

1. **Staleness of protocol files and skills.**
   - Repo-local playbooks (for example `.codex/skills/*/SKILL.md`) inevitably
     drift. Agents need a way to discover "what Meminit actually supports"
     at runtime without scraping docs.
2. **Multi-command orchestration ergonomics.**
   - Agents frequently run command sequences (`context` → `new` → `check` →
     `fix` → `check`). Correlation and step attribution are currently entirely
     external, which complicates durable agent logs and PR comments.
3. **Large outputs and long-running commands.**
   - In monorepos, `scan`, `index`, and deep context may produce large payloads.
     "One big JSON object" can be memory-heavy for both producers and consumers.
4. **Contract evolution pressure.**
   - As Meminit's contract becomes widely consumed by multiple agent runtimes,
     it needs first-class capability negotiation and a formal deprecation story
     that is discoverable by machines, not just humans.

---

## 3. Problem Statement

Meminit aims to be a reliable DocOps primitive in an agentic SDLC. For that to
remain true as adoption grows, Meminit needs to:

- be self-describing (capabilities and version support are discoverable),
- support scalable outputs (streaming where needed),
- integrate cleanly with agent protocol surfaces that can drift,
- and provide a disciplined, centrally documented error code registry that
  scales across commands.

Without these v2 capabilities, orchestrators remain brittle across versions and
teams spend time maintaining wrappers, rather than building features.

---

## 4. Goals and Non-Goals

### 4.1 Goals

1. **Capabilities negotiation:** An agent can query Meminit for supported
   commands, flags, output schema versions, and contract features.
2. **Correlation support:** An agent can pass an optional correlation id that
   Meminit will echo back, enabling robust multi-step orchestration traces.
3. **Streaming output option:** Commands with large outputs can emit an
   NDJSON/streaming form that preserves deterministic semantics without
   requiring a single monolithic JSON object.
4. **Protocol integration:** Provide a better story for `.codex/skills/`,
   `AGENTS.md`, and other protocol surfaces that are inherently stale:
   - treat them as _clients_ of the contract,
   - give them stable primitives to rely on,
   - and optionally validate them.
5. **Formal error code registry:** Move the canonical `ErrorCode` inventory
   into a dedicated spec (as foreshadowed in [MEMINIT-PRD-003](../10-prd/prd-003-agent-interface-v1.md) Appendix C 29.5) and add a way for agents to
   resolve a code into meaning and remediation guidance.

### 4.2 Non-Goals

1. Rewriting document body content for style or tone.
2. Turning Meminit into an LLM-driven "writer". Meminit remains a deterministic
   tool that agents call.
3. Building a hosted service; this PRD is CLI-first.
4. Introducing breaking changes without a clear versioned migration path.

---

## 5. Scope

In scope for v2:

- A machine-readable capabilities surface.
- Optional correlation support for multi-command workflows.
- Optional streaming output modes for large payload commands.
- A documented interface between Meminit and repo-local agent protocol files.
- A formal error code registry spec and a programmatic "explain" mechanism.

Out of scope for v2 (explicitly):

- Removing the v1 envelope or changing its semantics without versioning.
- A mandatory session daemon or persistent server.
- Repo-specific heuristics embedded in Meminit beyond reading configuration.

---

## 6. Proposed Requirements (FR)

> [!NOTE]
> These FRs are intentionally high-level. They capture "what we should build"
> for v2; v1 remains the implementation priority and must ship first.

### FR-1 Capabilities Command

Requirement: Meminit MUST expose a `meminit capabilities --format json` command
that returns a deterministic description of the CLI surface.

Minimum payload SHOULD include:

- supported `output_schema_version` values,
- supported `--format` values (for example `text`, `json`, `ndjson`),
- list of commands/subcommands and which support JSON envelopes,
- supported standardized flags (`--output`, `--include-timestamp`, etc.),
- and contract feature flags (for example `stdout_json_only: true`).

Builder note: `capabilities` MUST be fast and MUST NOT touch the filesystem by
default. It is a "what can you do" command, not a "what is in this repo"
command.

### FR-2 Correlation Id Support

Requirement: Meminit SHOULD accept an optional `--correlation-id <string>` flag
for all commands, and echo it into the JSON envelope as `correlation_id`.

Notes:

- If omitted, the field MUST be omitted to preserve minimal outputs.
- The correlation id MUST be treated as opaque.
- This MUST NOT replace `run_id` (which remains Meminit-generated).

### FR-3 Streaming Output Mode for Large Payload Commands

Requirement: Commands expected to produce large payloads (at minimum `scan`,
`index`, and any `--deep` modes) SHOULD support `--format ndjson`.

Notes:

- NDJSON records MUST be self-describing and include `output_schema_version`.
- If NDJSON is introduced, v2 MUST define:
  - a deterministic record order,
  - an end-of-stream summary record (or equivalent),
  - and error behavior (how operational errors are represented mid-stream).

### FR-4 Structured Logging Surface (Optional)

Requirement: Meminit SHOULD offer a way to emit structured logs to STDERR (or
to a separate file) without contaminating STDOUT JSON output.

Options include:

- `--log-format text|json`,
- or `--log-output <path>`.

### FR-5 Error Code Registry Spec + Explain Command

Requirement: Meminit MUST move the canonical `ErrorCode` registry into a
dedicated spec document (candidate: `docs/20-specs/spec-006-errorcode-enum.md`,
name TBD) and MUST provide a machine-readable explanation mechanism.

Two compatible approaches:

1. `meminit explain <ERROR_CODE> --format json` that returns remediation advice.
2. Include stable links/ids in the `error.details` payload that point to the
   registry entries.

### FR-6 Agent Protocol Integration Contract

Requirement: v2 MUST define how Meminit relates to repo-local agent protocol
surfaces, without making those surfaces normative for Meminit contracts.

Minimum expectations:

- Document which files are considered protocol surfaces (at least
  `AGENTS.md`, `.codex/skills/*/SKILL.md`).
- Document what those files SHOULD reference: v1/v2 envelope contracts, not
  ad-hoc parsing instructions.
- Provide optional validation guidance (linting) so protocol files can be
  checked in CI for drift (for example: "this skill assumes `--output` exists").

---

## 7. Migration and Versioning Strategy

### 7.1 Terminology: Agent Interface Versions vs Output Schema Versions

- "Agent Interface v1/v2" refers to product milestones (PRD-level scope).
- `output_schema_version` refers to the JSON envelope contract version.

Agent Interface v1 targets `output_schema_version: "2.0"` across commands.
Agent Interface v2 may:

- remain on `"2.x"` if changes are backward compatible additions, or
- introduce `"3.0"` if breaking changes are required.

### 7.2 Backward Compatibility Expectations

1. v2 MUST preserve v1 behaviors by default, unless explicitly version-gated.
2. When new flags are added (for example `--correlation-id`), they MUST be
   optional and MUST not change existing outputs unless invoked.
3. Capability negotiation MUST allow orchestrators to fail safe: if a feature
   is not supported, the orchestrator should be able to fall back.

---

## 8. Open Questions (With Options and Recommendations)

### 8.1 Where Should Capabilities Live?

**Options:**

1. **Option A (Recommended):** New `meminit capabilities --format json`.
   - Trade-off: Another command to maintain.
   - Benefit: Clean separation; fast; no repo context required.
2. **Option B:** Embed capabilities in `meminit context`.
   - Trade-off: Conflates "tool capabilities" with "repo configuration".
   - Benefit: Fewer commands.
3. **Option C:** Include capabilities in every JSON envelope.
   - Trade-off: Output bloat.
   - Benefit: Always available, no extra call.

**Recommendation:** Option A. Keep capabilities orthogonal to repo context.

### 8.2 Should Correlation Be First-Class in v2?

Agent Interface v1 explicitly recommends external correlation. v2 may revisit.

**Options:**

1. **Option A (Recommended):** Add `--correlation-id`, echo `correlation_id`.
   - Trade-off: Slight flag surface increase.
   - Benefit: Durable multi-command traces and PR comment attribution become easy.
2. **Option B:** Continue to require external correlation only.
   - Trade-off: Agents maintain more state; harder to standardize logs.
   - Benefit: No CLI expansion.
3. **Option C:** Introduce a session daemon.
   - Trade-off: Complex, changes operational model.
   - Benefit: Strongest multi-command semantics.

**Recommendation:** Option A.

### 8.3 Streaming Format Choice

**Options:**

1. **Option A (Recommended):** Add `--format ndjson` for large-output commands.
   - Trade-off: Another consumer parser mode.
   - Benefit: Simple, widely supported, works in shell pipelines.
2. **Option B:** Keep `--format json` only and require `--output` for large outputs.
   - Trade-off: Extra file IO and lifecycle management for orchestrators.
   - Benefit: Single parser.
3. **Option C:** Introduce a binary format.
   - Trade-off: Overkill; ecosystem friction.
   - Benefit: Performance.

**Recommendation:** Option A.

### 8.4 How Should Skills/Protocol Drift Be Managed?

**Options:**

1. **Option A (Recommended):** Treat protocol surfaces as clients and provide
   `meminit capabilities` so they can be validated (CI lint) and adapted at runtime.
2. **Option B:** Keep protocol drift as a human-only documentation problem.
3. **Option C:** Generate protocol files from Meminit automatically.

**Recommendation:** Option A. Provide machine-checkable primitives rather than
trying to make protocol files authoritative.

---

## 9. Acceptance Criteria (Ship-Ready Definition)

This PRD is considered implemented when:

1. `meminit capabilities --format json` exists, is deterministic, and is fast
   (no filesystem work by default).
2. Large-output commands support a streaming mode (`--format ndjson` or
   equivalent) with documented record ordering and error semantics.
3. Optional correlation id support exists and is echoed in JSON outputs.
4. A dedicated error-code registry spec exists and is referenced from outputs
   (directly or via `meminit explain`).
5. Protocol file integration guidance exists and is referenced from
   [MEMINIT-RUNBOOK-006](../60-runbooks/runbook-006-codex-skills-setup.md).

---

## 10. Risks and Mitigations

| Risk                                                     | Impact | Likelihood | Mitigation                                                                                                   |
| -------------------------------------------------------- | ------ | ---------- | ------------------------------------------------------------------------------------------------------------ |
| Capability surface becomes a second contract that drifts | High   | Medium     | Treat `capabilities` output as contract: deterministic ordering, schema validation tests, spec coverage.     |
| NDJSON streaming makes consumers more complex            | Medium | Medium     | Keep `--format json` as default; document minimal NDJSON record shape; provide sample parsers in tests/docs. |
| Correlation ids become mistaken for security boundaries  | Medium | Low        | Specify correlation id is opaque and non-sensitive; never use it for authorization decisions.                |
| Protocol surface linting becomes brittle                 | Medium | Medium     | Validate only stable primitives (flags/commands exist); do not attempt to validate natural language.         |

---

## 11. Related Documents

| Document ID                                                             | Title                          | Relationship                                                               |
| ----------------------------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------------- |
| [MEMINIT-PRD-003](../10-prd/prd-003-agent-interface-v1.md)              | Agent Interface v1             | Baseline envelope + CLI contract; v2 is explicitly out-of-scope follow-on. |
| [MEMINIT-SPEC-004](../20-specs/spec-004-agent-output-contract.md)       | Agent Output Contract          | Normative schema/spec for v1 outputs; v2 likely extends or supersedes.     |
| [MEMINIT-RUNBOOK-006](../60-runbooks/runbook-006-codex-skills-setup.md) | Codex Skills Setup for Meminit | Protocol-surface guidance and maintenance practices.                       |
| [MEMINIT-STRAT-001](../02-strategy/strat-001-project-meminit-vision.md) | Project Meminit Vision         | Strategic design center and constraints.                                   |
| [MEMINIT-GOV-003](../00-governance/gov-003-security-practices.md)       | Security Practices             | Governs safe output and repo privacy constraints.                          |

---

## 12. Document History

| Version | Date       | Author    | Changes                                                                                                                     |
| ------- | ---------- | --------- | --------------------------------------------------------------------------------------------------------------------------- |
| 0.1     | 2026-02-23 | System    | Created via `meminit new PRD`.                                                                                              |
| 0.2     | 2026-02-23 | Architect | Populated as a v1 out-of-scope backlog PRD: capabilities, correlation, streaming, protocol integration, and error registry. |
