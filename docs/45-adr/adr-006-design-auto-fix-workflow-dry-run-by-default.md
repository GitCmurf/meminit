---
document_id: MEMINIT-ADR-006
type: ADR
title: Design auto-fix workflow (dry-run by default)
status: Draft
version: 0.1
last_updated: 2025-12-14
owner: GitCmurf
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-ADR-006
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2025-12-14
> **Type:** ADR

# MEMINIT-ADR-006: Design auto-fix workflow (dry-run by default)

- **Date decided:** 2025-12-14
- **Deciders:** Repo maintainers
- **Status:** Draft

## 1. Context & Problem Statement

Auto-modifying repositories is risky. `meminit fix` must help migrations and day-to-day hygiene while minimizing destructive behavior and false claims of compliance.

## 2. Decision Drivers

- Safety: no surprising changes; defaults must be non-destructive.
- Determinism: repeated runs should produce predictable results.
- Honesty: only report “fixed” when the fix actually resolves the violation.

## 3. Options Considered

- **Dry-run by default**
  - Pros: safe; supports review-before-apply workflows.
  - Cons: requires explicit `--no-dry-run` for application.
- **Apply by default**
  - Pros: convenience.
  - Cons: too risky for a repo-wide tool.

## 4. Decision Outcome

- **Chosen option:** `meminit fix` defaults to dry-run and only applies changes when explicitly requested.
- **Fix scope (v0.1):**
  - rename files to comply with filename convention
  - initialize/repair required frontmatter fields to satisfy schema (with placeholders like `owner: Unknown`)
  - update missing `last_updated` and `docops_version` when required by schema

## 5. Consequences

- Positive: safer adoption; easier review; fewer accidental changes.
- Negative: some fixes (e.g., moving files between directories) remain manual in v0.1.

## 6. Implementation Notes

- Fixer: `src/meminit/core/use_cases/fix_repository.py`
- CLI: `src/meminit/cli/main.py` (`--dry-run/--no-dry-run`)

## 7. Validation & Compliance

- Tests cover: dry-run behavior, rename sanitization, frontmatter initialization to schema compliance.
- When frontmatter is synthesized, human review is still expected (e.g., replace `owner: Unknown`).

## 8. Alternatives Rejected

- Apply-by-default: rejected on safety grounds.

## 9. Supersession

- Supersedes: none
- Superseded by: none

## 10. Notes for Agents

- Keywords: dry-run, safe automation, deterministic fixer
- Code anchors: `src/meminit/core/use_cases/fix_repository.py`, `src/meminit/cli/main.py`
