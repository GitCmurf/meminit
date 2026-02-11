---
document_id: MEMINIT-PRD-001
owner: GitCmurf
status: Draft
version: 0.2
last_updated: 2025-12-18
title: Meminit Tooling Ecosystem PRD
type: PRD
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PRD-001
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.2
> **Type:** PRD

# 1. Product Requirements Document (PRD) — Meminit

---

## 1.0 Implementation Status (As of 2025-12-14)

This PRD predates the current MVP implementation. Each major requirement below is now marked as:

- **Met**: Implemented in the codebase and covered by tests.
- **Exceeded**: Implemented with additional safeguards/behavior beyond this PRD.
- **Not Yet Implemented**: Still outstanding work; no equivalent/superior replacement exists in the current MVP.
- **Superseded**: Replaced by an equivalent or superior implementation that covers the same utility.

Update note (2025-12-18): Strategy and planning were substantially refined since this PRD was drafted. This PRD remains a requirements inventory, but the canonical documents for constraints and sequencing are:

- MEMINIT-STRAT-001 (vision/constraints)
- MEMINIT-PLAN-003 (roadmap/sequencing)

## 1.1 Executive Summary

Meminit is an org-level DocOps toolkit for managing technical documentation across multiple repositories, enforcing a shared documentation constitution and providing low-friction tools (CLI, configs, templates, linting, hooks, CI examples) for compliance.

## It must make the compliant workflow the path of least resistance for humans and LLM agents, with machine-readable configuration, automatic document ID generation, and robust validation of metadata and layout, while minimising manual duplication (e.g. version tables) and human error.

## 1.2 Goals

1. Single source of truth for DocOps rules

- Maintain an organisation-wide DocOps Constitution and org-level config in the Meminit repo.

2. New repo bootstrap

- Generate a compliant `docs/` structure, repo-level config, and standards docs for new repositories.

3. Existing repo migration

- Provide tools to scan and suggest mappings/patches for existing repositories to adopt the structure and metadata.

4. Low-friction CLI

- Offer a CLI (`meminit`) that automates:
  - new document creation (IDs, paths, metadata, templates)
  - validation (linting)
  - index generation
  - link generation.

5. Tooling for CI/agents

- Provide pre-commit hooks and CI examples for validation.
- Make the CLI easily consumable by LLM agents (JSON I/O, atomic operations).

---

### 1.2.1 Goal-to-Implementation Mapping

- **Met**: CLI exists with `meminit init`, `meminit new`, `meminit check`, `meminit fix`.
- **Met**: `meminit check` supports JSON output (`--format json`).
- **Exceeded**: `meminit check` normalizes YAML scalar coercions (`last_updated`, `version`, `docops_version`) before schema validation to avoid false positives.
- **Exceeded**: schema file load errors are repository-level (missing vs invalid) rather than flooding per-document errors.
- **Not Yet Implemented**: Org-level config file (`org-docops.config.yaml`).
- **Not Yet Implemented**: `index`, `link`, `scan`, hooks/CI examples.

Licensing (planned):

- Apache-2.0 at first public OSS release (target tag: `v0.5.0`, immediately before “Agentic Integration” begins).

## 1.3 Non-goals

- Not a full documentation site generator (no replacement for MkDocs/Hugo).
- Not a content-writing assistant (LLMs may be used separately).
- Not a project-management tool (no issue tracking, roadmap management).
- Not responsible for rendering docs to HTML/PDF (just structure and metadata).

---

## 1.4 Target Users

Design center: agent orchestrators (Architext-class tooling), with human maintainers as primary beneficiaries.
Secondary: CI systems running validation in pipelines.
Tertiary: humans maintaining governed documentation.

---

## 1.5 Key Use Cases (abbreviated)

1. Initial org setup:

- You clone `meminit`, finalise Constitution and org config; other repos then reference it.

2. Bootstrap new repo:

- Run `meminit init` to create `docs/` structure, `docops.config.yaml`, governance docs, templates, and schema.

3. Create a new ADR:

- Run `meminit new --type adr --area INGEST --title "Use Redis as cache"`
- Tool generates ID, frontmatter, visible block, body skeleton.

4. Validate repo:

- Run `meminit check` locally or in CI; see any DocOps violations (IDs, metadata, layout).

5. Agent editing:

- An agent calls `meminit new`/`meminit update-frontmatter`/`meminit extract-section` as a tool to manipulate docs safely and consistently.

---

## 1.6 Functional Requirements

### F1. Org-level Constitution + Config

F1.1 Store the DocOps Constitution (markdown) in `meminit` repo. **Met**
F1.2 Provide an organisation-level `org-docops.config.yaml` defining: **Not Yet Implemented**

- allowed types, default directories, other org-wide parameters.
  F1.3 Provide a way for repo configs to declare which Constitution version they follow. **Met** (via `docops_version` field)

### F2. Repo Initialisation

F2.1 `meminit init` MUST: **Exceeded** (supersedes the older `init-repo` naming in this PRD)

- creates the default `docs/` structure.
- creates root `docops.config.yaml` (includes `repo_prefix`, `docops_version`, and template paths).
- creates `docs/00-governance/templates/` and a baseline schema at `docs/00-governance/metadata.schema.json`.
- creates `AGENTS.md`.

Not yet implemented sub-requirements:

- generating a repo-specific “Document Standards” doc from templates + config.
- installing pre-commit hooks and CI workflow examples.

### F3. New Document Creation

F3.1 `meminit new` MUST create a new document with a valid ID + correct directory. **Met**

- Current CLI signature is `meminit new <TYPE> <TITLE>` (flags like `--area`/`--id` are **Not Yet Implemented**).
- Reads root `docops.config.yaml` for `repo_prefix` and template paths. **Met**
- Computes next sequence number by scanning the target directory. **Met**
- Creates a schema-valid frontmatter block and a body skeleton. **Met**
- Visible metadata block generation is **Not Yet Implemented**.

F3.2 JSON output for `meminit new`. **Not Yet Implemented**

### F4. Linting / Validation

F4.1 `meminit check` MUST:

- frontmatter presence **Met**
- required fields and types via JSON schema **Met**
- `document_id` format and uniqueness **Met**
- directory alignment (warns when mismatched for known types) **Met**
- filename convention (warns) **Met**
- `status` enum is enforced by schema **Met**
- `type` allowlist against config is **Not Yet Implemented**
  F4.2 It MUST exit non-zero on violations (for CI and pre-commit).
  **Met** (non-zero exit on violations)

### F5. Migration Tools

F5.1 `meminit scan` MUST: **Not Yet Implemented**

- scan existing repo `docs/` (or configurable paths)
- detect markdown files missing frontmatter or mislocated
- propose a mapping (e.g. “this file looks like a design doc → 30-design”).
  F5.2 “dry-run” and “generate patches” mode for scan. **Not Yet Implemented**
- generate suggested frontmatter blocks and file moves in a separate folder or patch files, _not_ modify in-place by default.

### F6. Index \& Linking Helpers

F6.1 `meminit index` MUST: **Not Yet Implemented**

- build a machine-readable index `docs/01-indices/doc_index.json` mapping `document\_id` → relative path (and optionally title, type, area).
  F6.2 `meminit link` <DOCUMENT_ID> SHOULD: **Not Yet Implemented**
- print a Markdown snippet including ID and relative link if inside same repo;
- with `--absolute` flag, print absolute GitHub URL if configured.

### F7. Hooks and CI

F7.1 Provide sample pre-commit hook configuration that runs `meminit check`. **Not Yet Implemented**
F7.2 Provide a GitHub Actions workflow example that runs `meminit check` on PRs. **Not Yet Implemented**

## 1.7 Non-functional Requirements

N1: Implemented in a language easy to run locally and portable across platforms. **Met** (Python)
N2: Library-first design (CLI is a thin wrapper). **Met**
N3: Deterministic/idempotent operations where possible. **Met** (`init` is idempotent; `check` is read-only; `fix` is deterministic)
N4: Clear error messages for humans; machine-readable mode for agents. **Exceeded** (`check` supports JSON output; schema errors include field context)
N5: Good test coverage; core behaviours are unit + integration tested. **Met**

## 1.8 Success Metrics

- [ ] All repos under your control can be bootstrapped/migrated to Meminit without manual rework.
- [ ] Creating a new ADR/PRD is faster with `meminit new` than doing it by hand.
- [ ] `meminit check` can run in CI and reliably catch violations.
- [ ] LLM agents can use the CLI to create and update docs without breaking invariants.

### 1.8.1 Notes on Success Metrics

- **Met (locally)**: `meminit check` and `meminit fix` provide a working compliance loop in-repo.
- **Not Yet Implemented**: CI + pre-commit integration.
- **Not Yet Implemented**: Migration tooling (`scan`, file moving) and index/link helpers.

## 2. Next Sprint Candidates (Work Remaining)

The following items are not covered by an equivalent/superior implementation yet:

1. `meminit index` to generate a `document_id` → path index (needed for reliable ID-to-path mapping).
2. `meminit link` to emit stable markdown snippets from an ID using the index.
3. `meminit scan` (migration) to classify and propose changes without in-place edits by default.
4. Pre-commit + CI examples that run `meminit check` (and optionally `meminit fix --dry-run` as advisory).
5. Config evolution: move beyond the current minimal root `docops.config.yaml` toward explicit repo/org configuration models.
