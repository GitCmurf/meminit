---
document_id: MEMINIT-ADR-009
type: ADR
title: Add Minimal Repo Configuration For Brownfield Adoption
status: Draft
version: 0.1
last_updated: 2025-12-14
owner: GitCmurf
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-ADR-009
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2025-12-14
> **Type:** ADR

# MEMINIT-ADR-009: Add Minimal Repo Configuration For Brownfield Adoption

- **Date decided:** 2025-12-14
- **Deciders:** Repo maintainers
- **Status:** Draft

## 1. Context & Problem Statement

`meminit` is intended to be usable both in greenfield repos (created with `meminit init`) and in existing/brownfield repos that already have a documentation tree and conventions.

Earlier iterations hardcoded assumptions such as:

- Governed docs live under `docs/`
- JSON schema is at `docs/00-governance/metadata.schema.json`
- Doc type folders are fixed (e.g., `ADR` → `docs/45-adr/`)
- Only `docs/00-governance/templates/` is excluded from scanning

In a brownfield repo, these assumptions often don’t hold (e.g., `docs/adrs/`, existing template folders, non-governed markdown in `docs/`), leading to noisy warnings and unnecessary migrations.

## 2. Decision Drivers

- Enable incremental adoption in existing repositories without forcing immediate restructuring.
- Keep `meminit` a small, deterministic “unix-like” tool (avoid a sprawling config surface).
- Preserve strong defaults for greenfield repos.
- Keep configuration repo-local (no hidden global state).

## 3. Options Considered

- **Option A: Hardcode everything**
  - Pros: simplest implementation.
  - Cons: discourages brownfield adoption; produces false positives on legitimate repo layouts.
- **Option B: Highly flexible configuration / plugins**
  - Pros: can model any repo.
  - Cons: higher complexity, higher support burden, more room for misconfiguration.
- **Option C: Minimal repo configuration with safe defaults**
  - Pros: supports common brownfield variations (folders + exclusions) while keeping the tool small.
  - Cons: still requires some manual migration for schema/frontmatter differences.

## 4. Decision Outcome

- **Chosen option:** Option C
- **Why this option:** It covers the highest-impact adoption friction (where to scan and what to ignore) without turning `meminit` into a framework.
- **Scope/Applicability:** Applies to `meminit check`, `meminit fix`, and `meminit new` resolution of docs paths and type → directory expectations.

## 5. Consequences

- Positive:
- Brownfield repos can adopt `meminit` while keeping existing doc folder structure.
- Repos can exclude known non-governed markdown (e.g., template folders) to keep compliance output actionable.
- Negative / trade-offs:
- Adds a small amount of configuration surface area that must be documented and tested.
- Incorrect configuration can hide violations (e.g., overly broad exclusions); defaults remain strict.

## 6. Implementation Notes

- Implemented a shared config loader: `src/meminit/core/services/repo_config.py`.
- Added optional keys in `docops.config.yaml`:
  - `docs_root`
  - `schema_path`
  - `excluded_paths`
  - `type_directories`
- Updated use cases to consume this config:
  - `src/meminit/core/use_cases/check_repository.py`
  - `src/meminit/core/use_cases/fix_repository.py`
  - `src/meminit/core/use_cases/new_document.py`
  - `src/meminit/core/use_cases/init_repository.py` (writes defaults for new repos)

## 7. Validation & Compliance

- Tests cover:
  - `excluded_paths` skipping non-governed markdown
  - `type_directories` affecting directory warnings and `new`/`fix` behavior
- `pytest` passes.

## 8. Alternatives Rejected

- Option A rejected because it blocks brownfield adoption.
- Option B rejected as unnecessary complexity for v0.1.

## 9. Supersession

- Supersedes: none
- Superseded by: none

## 10. Notes for Agents

- Recommended brownfield workflow:
  1. Ensure `docops.config.yaml` reflects the repo layout (especially `excluded_paths` and `type_directories`).
  2. Run `meminit check` to establish baseline violations.
  3. Use `meminit fix --dry-run` before applying mechanical changes.
- Keywords: brownfield, configuration, exclusions, type_directories
- Code anchors: `src/meminit/core/services/repo_config.py`, `src/meminit/core/use_cases/*`
