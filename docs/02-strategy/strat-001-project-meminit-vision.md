---
document_id: MEMINIT-STRAT-001
owner: Strategy Team
approvers: GitCmurf
status: Draft
version: 1.0
last_updated: 2025-12-22
title: Project Meminit Vision
type: STRAT
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-STRAT-001
> **Owner:** Strategy Team
> **Approvers:** GitCmurf
> **Status:** Draft
> **Version:** 1.0
> **Last Updated:** 2025-12-22
> **Type:** STRAT

# Project Meminit Vision

## 1. Executive Summary

**Meminit** is "DocOps for the Agentic Age."

Meminit addresses a critical gap in AI-integrated software engineering: the drift between code and documentation. By treating documentation as a governed ("Constitution-first"), toolable asset, and integrating agentic AI workflows as foundational design principles, Meminit aims to enable human-AI hybrid teams to maintain high-quality, up-to-date documentation with minimal friction.

We are building the **scaffolding and migration tooling** that allows repositories to adopt strict DocOps standards, making them readable by humans and understandable by AI agents, with the vision that this should involve no more (and we think it will be less) friction than existed in the human hand-coding era good practice with tools like `adr-tools` (nods respectfully to the OG).

The governed documentation will:

- default to a recognisable set of common-practice document types spanning the entire SDLC
- refer and align to wider-organisation "Constitution" standards/policies/SOPs
- be configurable to the specific repo needs (more/less breadth/depth) and adaptable as these change
- remain human-readable and human-editable with fully-flexible structure, content and formatting options
- be predominantly machine-generated
- be machine-maintained for efficient and effective agentic coding assistance
- respect strict modularisation and separation of concerns, -- not infringing on other tools but facilitating interfaces (code wiki, code notes graph, org KBs, etc.)
- enable linting and checking
- remain a unix-like small tool
- forward-looking to 2026 software development paradigms with future-proofing and optionality (MCP-aware, but anticipating evolution of the MCP model to tool-calls)

### 1.1 Current State (As of 2025-12-22)

`meminit` currently provides:

- Repo scaffolding: `meminit init`
- Document creation: `meminit new`
- Compliance validation: `meminit check`
- Auto-remediation: `meminit fix` (dry-run by default)
- Repo readiness self-check: `meminit doctor`
- Brownfield scan (read-only): `meminit scan`
- Pre-commit installer: `meminit install-precommit`

## 2. Core Pillars

1.  **Governance**: Enforceable standards via the DocOps Constitution.
2.  **Automation**: Tooling (`meminit` CLI) to validate, generate, and maintain docs.
3.  **Agentic Collaboration**: First-class support for AI agents as contributors. Documentation must be "Agent-Ready."

## 3. Strategic Decisions

### 3.1 Technology Stack

We standardize on **Python** for the Core Logic and CLI.

- **Rationale:** Python offers the best ecosystem for text processing, RAG indexing, and agentic integration. It simplifies the developer experience for our target audience (AI engineers and backend devs).
- **Clarification:** A top-level `package.json` may exist for future/adjacent tooling, but the `meminit` CLI is intended to be usable as a standalone Python tool; Node.js must not be required for the core CLI in v0.1.

### 3.2 Scope & Boundaries

- **NOT a Project Management Tool:** We are not building a Jira competitor.
- **NOT a Documentation CMS:** We are not building Confluence/Notion; we govern plain Markdown in git.
- **DocOps for Tasks:** We treat `TASK` files as a governed document type (`docs/05-planning/tasks/`). This enables structured “what to do / what changed” artifacts without becoming a full PM suite.

### 3.3 Licensing

- **Current:** All Rights Reserved (Proprietary). A 'safe' placeholder.
- **Future:** Apache-2.0 at first public release (target: `v0.5.0`; see Section 7.3 and MEMINIT-PLAN-003).

## 4. Roadmap (Source of Truth: MEMINIT-PLAN-003)

The detailed development roadmap (phases, sequencing, and work tracking) is defined in MEMINIT-PLAN-003: [Project Roadmap](../05-planning/plan-003-roadmap.md).

If this vision and the roadmap diverge:

- the roadmap is the sequencing source of truth
- this vision is the constraint set (goals + non-negotiables)

### Phase 1: Foundation (Current)

Focus: baseline CLI tooling + repository self-discipline.

- `meminit init`: Scaffold baseline directory structure, config, templates, and schema.
- `meminit new`: Create governed documents from templates with valid metadata.
- `meminit check`: Validate governed docs for schema + structural compliance.
- `meminit fix`: Provide safe mechanical remediation (dry-run by default).
- `meminit doctor`: Verify “is this repo ready for meminit?”

### Phase 2: Core Tooling

Focus: brownfield adoption primitives and deterministic integration.

- Expand the “brownfield adoption” package beyond the MVP delivered in Phase 1:
  - `meminit scan` enrichment (better type inference, collisions, richer recommendations)
  - enforcement hardening (more CI examples, pre-commit ergonomics)
- Begin the artifact boundary: repo index + ID/path resolution commands (Section 6.5).

### Phase 3: Architext Support (Public Release Gate)

Focus: prove the orchestrator design center in a real pilot repo.

- Architext is the first external pilot target (Meminit pinned to a specific version/sha; upgrades only via intentional change).
- Public OSS release under Apache-2.0 occurs at the end of this phase (immediately before Phase 4), target tag: `v0.5.0`.

### Phase 4: Agentic Integration

Focus: first-class agent workflows built on deterministic artifacts/contracts.

- Agent protocol/interface spec for structured integrations.
- A dedicated agent that proactively maintains documentation (optional; depends on proven contracts).

### Phase 5: Ecosystem

Focus: integrations and adjacent tooling.

- Optional adjacency: “Code Notes Graph” for linking code symbols to documentation (explicitly separate tool that consumes Meminit index artifacts).
- IDE extensions and broader CI integration patterns.

## 5. Success Metrics

- **Compliance:** 100% of docs in a repo have valid IDs and Frontmatter.
- **Brownfield adoption:** For repos in the published size class (≤ 200 governed Markdown docs), time-to-first-green is ≤ 120 minutes on a typical developer machine.
- **Freshness:** "Last Updated" dates correlate with code changes.
- **Agent Success:** AI agents can successfully navigate the repo using _only_ the documentation.

## 6. Decisions & Commitments (Dialectic Closure for 2026)

This section records the concrete product decisions we have committed to. Treat these as constraints.

### 6.0 Vocabulary (terms used in this vision)

- **Governed docs**: documents Meminit validates/enforces (IDs, schema, rules).
- **Non-governed docs**: explicitly excluded artifacts (e.g., `WIP-…`) that tooling must ignore for compliance.
- **Design center**: the primary user the product is optimized for. One design center.
- **Repo size class**: the maximum number of governed Markdown documents for which we publish a practical brownfield adoption promise.
- **Time-to-first-green**: time from a fresh checkout of the target repo (e.g., `git clone` or a new working copy) to “`meminit check` returns zero violations”, following the documented migration workflow.
- **Placeholder metadata**: temporary values during migration to satisfy schema. Placeholders must be machine-searchable and must block `Approved`.
- **Pinned include (config)**: an org-level config referenced from a deterministic local file path (committed/vendored/submodule), not fetched from the network at runtime.
- **Pin (dependency)**: another repo/tool depends on a specific released version or specific commit hash so behavior cannot silently change.
- **Artifact boundary**: the explicit files and commands Meminit owns so other tools can build on it reliably.

### [x] 6.1 Governance Boundary

**Committed decision:** Dual boundary.

- Anything under `docs/` is governed **unless** explicitly opted out by:
  - `excluded_paths`, or
  - `excluded_filename_prefixes` (default `WIP-`) applied to either a file or any parent directory.
- WIP policy:
  - `WIP-` artifacts are **not governed** and **must not be committed**, but remain available for local agent workflows.
  - Anything important enough to share/review must be promoted to a governed doc (frontmatter + ID + status `Draft`).

### [x] 6.2 Scope and Product Shape

**Committed decision:** Design center is **agent orchestrators** (Architext-class tooling).

- Non-negotiable consequence: every command used by orchestrators must have deterministic machine output, stable semantics, and test coverage for edge cases.
- Brownfield v0.2 promise (published limits):
  - Repo size class: **≤ 200** governed Markdown docs.
  - Time-to-first-green: **≤ 120 minutes** (aspiration: < 60 minutes).
- Safety invariants:
  - `meminit fix` defaults to dry-run; `--no-dry-run` is required to write.
  - No deletions (only additive changes + renames) unless a future explicit `--allow-delete` is added.
  - Renames are deterministic and always surfaced explicitly in reports.
- Placeholder policy:
  - Universal placeholder token: `__TBD__`.
  - Hard gate: `status: Approved` is invalid if any required field contains `__TBD__`.

### [x] 6.3 Configuration Philosophy

**Committed decision:** Declarative config + local includes (no code execution).

- Includes must be deterministic: no runtime network fetch and no ambiguous “latest” resolution.
- Precedence: org defaults < repo overrides.
- v0.2 priority order:
  1. Allowed types enforcement (schema enum / repo allowlist)
  2. Org-level shared config include
  3. Controlled vocabularies (areas/keywords)

### [x] 6.4 Agent Interface and Compatibility

**Committed decision:** Backward compatible within a major version (once `v1.0` is cut).

- Until `v1.0`, Meminit is unstable; external consumers must pin to a specific version/sha and upgrade intentionally.
- Contract shape:
  - `violations[]` is machine-validated and stable.
  - `advice[]` is optional and explicitly non-binding.
- If other tools depend on JSON outputs, Meminit must version the output contract explicitly (e.g., `output_schema_version` in JSON).

### [x] 6.5 Roadmap Prioritization and Artifact Boundary

**Committed decision:** deliver `scan` + enforcement as a single coherent “brownfield adoption” package (Q1 2026).
MVP versions of `scan` and enforcement live in Phase 1; Phase 2 completes the package and hardens it.

**Committed default artifact:** `docs/01-indices/meminit.index.json` (repo may override via `index_path` in config).

- Contains at least: `document_id`, path, type, title, status, links, supersession edges.

**Committed command set (names accepted):**

- `meminit index`: build/update the index artifact.
- `meminit resolve <DOCUMENT_ID>`: print canonical path (and optionally a Markdown link).
- `meminit identify <PATH>`: print the document_id (or error if non-governed/unparseable).
- `meminit link <DOCUMENT_ID>`: print a Markdown link using the index.

## 7. Strategic Decisions & Open Questions (Next Dialectic Round)

Section 7 records committed decisions plus any explicitly stated open questions for the next dialectic round.

### [x] 7.1 `adr-tools` Compatibility Boundary

**Committed decision (2026 baseline):** Option 1 — alias-only (for now).

Plain language definition:

- “Alias-only” means we may provide `meminit adr …` entrypoints for familiarity, but we do **not** promise `adr-tools` behavior parity, and ADR-compatibility must not dictate Meminit’s internal representations.

Compatibility intent:

- Compatibility is a mode, not the internal representation.
- Facilitate compatibility where it is cheap and high-leverage (target the common “daily” workflows first).
- Do not accidentally block future compatibility improvements; if we must break compatibility for core aims, do it consciously and document it.

Clean-room rule (not legal advice):

- Implement from scratch (no copying code or documentation text); no GPL dependencies.

Candidate `adr-tools`-style commands to consider (not yet committed):

- `adr init <ADR DIR>` (ADR directory setup only; not full `meminit init`)
- `adr new <TITLE>` (already: `meminit adr new`)
- `adr new -s <OLD NUM> <TITLE>`
- `adr list`
- `adr link <SOURCE> <LINK TEXT> <TARGET> <REVERSE LINK TEXT>`
- `adr generate toc`
- Explicit non-goals (unless strategy changes): `adr generate graph`, `adr upgrade-repository`
- Out of scope for Meminit core: `approve` / `reject` governance decisioning (separate domain)

Open question:

- Do we want a first-class `meminit search|find` capability, or is this satisfied by `meminit index/resolve/identify` plus existing tools (`rg`, etc.)?

### [x] 7.2 Enforcement Packaging

**Committed decision:** Option B — maintained reference integrations.

Plain language definition:

- “Reference integrations” means Meminit ships example enforcement integrations that we run ourselves. If they break in the supported environments below, we treat it as a bug (not “user error”).

Tested environments (initial):

- OS: GitHub-hosted Linux + Windows runners.
- Python: 3.11 and 3.12 (Meminit runtime requirement; the target repo can be any language).
- Mac: not in the initial supported set, but avoid unnecessary OS-specific behavior.

Pinning rule (plain language):

- Automation must use an exact Meminit version tag (e.g., `0.2.0`) or an exact commit SHA for pilots; never float “latest”.
- `X.Y.Z` is the standard three-part version format (major.minor.patch). Pinning to an exact tag keeps CI deterministic.

Learning gap to close (before claiming this is “done”):

- Pick and document the default CI example (GitHub Actions is the likely default because it is common, but enforcement must remain CI-provider-agnostic).

### [x] 7.3 Public Release and Licensing

**Committed decision:** Apache-2.0.

Public release timing:

- Immediately before “Agentic Integration” begins (Roadmap Phase 4).
- Concretely: end of Roadmap Phase 3 (“Architext support”) as defined in MEMINIT-PLAN-003.
- Target first public OSS tag: `v0.5.0` (stay in `0.x` until the machine contracts are proven stable; reserve `v1.0` for explicit compatibility discipline).

Public readiness gates (non-negotiable):

- Apache-2.0 licensing implemented in-repo (LICENSE + packaging metadata aligned).
- `meminit doctor` green.
- `meminit check` green.
- `pytest` green.
- secrets/PII hygiene pass (per security practices doc; re-confirm it remains fit-for-purpose).
- successful greenfield run.
- successful run through Architext and at least one other pilot repo.
