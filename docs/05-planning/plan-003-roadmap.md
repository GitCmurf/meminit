---
document_id: MEMINIT-PLAN-003
owner: Product Team
approvers: GitCmurf
status: Draft
version: 0.2
last_updated: 2025-12-22
title: Project Roadmap
type: PLAN
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PLAN-003
> **Owner:** Product Team
> **Approvers:** GitCmurf
> **Status:** Draft
> **Version:** 0.2
> **Type:** Planning

# Meminit Development Roadmap

This is the detailed development roadmap and the sequencing source of truth.
If this roadmap and the vision diverge, the roadmap wins for sequencing and the vision wins for constraints: see [MEMINIT-STRAT-001](../02-strategy/strat-001-project-meminit-vision.md).

## Idea catcher (not yet sequenced or properly specified)

### 2025-11-27

- [ ] make a prettified README suitable as a public GitHub intro
  - [x] copy write text
  - [ ] use the project logo? simplify for favicon?
  - [ ] some form of intro graphic or GIF/video
- [x] public release
- [ ] wiki for project (use GitHub native?)
  - GitHub Projects space?
- [ ] tests with Google Code Wiki after first push
- integration of GitHub actions CI/CD and PR auto-reviewers (CodeRabbit, Qodo, Greptile, ??)
  - [x] Greptile set up to review PR
  - [?] CI/CD
  - [ ] other?
- [ ] instructions for machine use (what to go into AGENTS.md? what to refer to? what to output for `--help` flags or similar: CLI best practices)
  - [ ] review/improve AGENTS.md
  - [ ] review/improve meminit skill
- maximum backward compatibility with `adr-tools` without unintentionally importing GPL terms (CLI option matching ok? need a config setting for full compatibility? smooth aliasing? or an interpretation layer--could also allow orgs to alias existing tools?)
  - [x] implemented
  - [ ] make a note about aliasing
  - [ ] need to check behaviour
- [ ] auto-update tool for repo's own AGENTS.md
  - keep repo file structure up to date
  - other info AGENTS need that could otherwise go stale?
- [ ] full template set:
  - overlap with Project Architext--how keep aligned?
  - which docs?
  - tasks list (check chatGPT discussions)
- [?] make Python and TypeScript implementations in parallel? (DCI principles should minimise friction?)
- GitHub Super Linter--how to interact? Patterns for other popular linting tools (including pre-commit, Ruff, Flake8, mypy, ESLint, Prettier).
- static-site generator alignment and benefits optimisation (MkDocs vs Sphinx vs)
- Obsidian and logseq friendly? How to deal with `docs/` being a 'vault directory' for PKM-like tools--flexibility without breaking structure and linting/checking
- [ ] VS Code integration--what features? how?

## Phase 1: Foundation (Current)

- [x] Repository Initialization
- [x] Governance Framework Setup
- [x] Full, clear articulation of Project Vision
- [x] CI/CD Pipeline Implementation (PR-only enforcement; least-privilege workflow permissions)
- [x] Basic CLI Tooling: internally-consistent green-light on own doc-linting checks
- [ ] Full internal consistency: pass checks by all major code AIs
- [x] Best practices for GitHub public sites? e.g., initial issues recorded?

### Consolidated Work Remaining

- [x] Pre-commit hook snippet (or installer) for `meminit check`.
- [x] GitHub Actions example workflow for `meminit check`.
- [x] `meminit scan` (migration planner) for brownfield adoption.
- [x] Index artifact + resolution helpers: `meminit index|resolve|identify|link` and `docs/01-indices/meminit.index.json`.
- [ ] Decide whether to add an OrgConfig model (or explicitly defer and document why).
- [ ] Agent interface phase: JSON schema for outputs; agent protocol spec; `meminit context`.
- [ ] Templates for other doc types (e.g., `prd`, `fdd`, `task`) -- develop a common 'syntax' that can apply equally to Project `Architext` and possibly also Project `HypoGraph`.

## Phase 2: Core Tooling

- [ ] Linter Implementation (Constitution compliance beyond schema; include structural rules and constitution alignment)
- [ ] Metadata generator improvements (templates + safe placeholder workflows; migration helpers)
- [ ] Link validation improvements (cross-doc integrity; resolution via index)

## Phase 3: Architext support

- [ ] Plan to deal with conflict between mutable metadata (status, approved-by, owner) and hashed doc control
- [ ] Plan for metadata sidecars / repo-index alternatives
- [ ] Ensure user-tunable repo config can accommodate Architext-type requirements
- [ ] Make common configs easily selectable, including Architext-support option (without making meminit overly complex).
- [ ] Public OSS release under Apache-2.0 at end of Phase 3 (immediately before Phase 4), target tag: `v0.5.0`.
  - Gates: `meminit doctor` green, `meminit check` green, `pytest` green, secrets/PII hygiene pass, greenfield run, Architext + 1 other pilot repo.

## Phase 4: Agentic Integration

- [ ] Context Awareness Module
- [ ] Automated Doc Generation
- [ ] Semantic Search

## Phase 5: Ecosystem

- [ ] IDE Extensions
- [ ] GitHub Actions
- [ ] Web Dashboard
