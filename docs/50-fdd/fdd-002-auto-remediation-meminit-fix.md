---
document_id: MEMINIT-FDD-002
type: FDD
title: Auto-Remediation (meminit fix)
status: Approved
version: 1.0
last_updated: 2026-03-01
owner: GitCmurf
docops_version: 2.0
---

# FDD: Auto-Remediation (meminit fix)

## Feature Description

Provide a safe, deterministic fixer that can automatically remediate common compliance issues discovered by `meminit check`.

## User Value

- Accelerates migrations by handling mechanical fixes.
- Reduces ongoing toil for routine formatting/compliance tasks.

## Functional Scope (v0.1)

- Default mode is **dry-run**.
- Supports plan-driven execution via `--plan <path>` to deterministically run a previously generated scan plan artifact.
- When applied (`--no-dry-run`):
  - Rename files to satisfy filename convention, sanitizing invalid characters.
  - Add/repair frontmatter when missing to satisfy schema-required fields:
    - `document_id` (generated if missing)
    - `type` (inferred from directory when possible)
    - `title` (inferred from first H1 or filename)
    - `status` (defaults to `Draft`)
    - `version` (defaults to `0.1`)
    - `last_updated` (defaults to today)
    - `owner` (defaults to `__TBD__`)
    - `docops_version` (defaults to `2.0`)
  - Update missing `last_updated` / `docops_version` when required by schema validation.

## Non-goals (v0.1)

- Moving files between directories to satisfy `DIRECTORY_MATCH`.
- Resolving duplicate IDs automatically (requires human decisions).
- Inferring “correct” owners/areas beyond placeholders.

## Safety Guarantees

- Does not apply changes by default (dry-run).
- Does not claim a frontmatter fix is resolved unless the resulting metadata passes schema validation.

## Implementation Notes

- Use case: `src/meminit/core/use_cases/fix_repository.py`
- Relies on `CheckRepositoryUseCase` to discover violations and schema compliance.

## Tests

- Unit tests cover rename sanitization and frontmatter initialization to schema compliance.
