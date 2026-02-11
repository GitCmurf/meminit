---
document_id: MEMINIT-FDD-001
type: FDD
title: Compliance Checker (meminit check)
status: Draft
version: 0.1
last_updated: 2025-12-14
owner: GitCmurf
docops_version: 2.0
---

# FDD: Compliance Checker (meminit check)

## Feature Description

Provide a deterministic repository scanner that validates DocOps compliance for governed markdown documents under `docs/`.

## User Value

- Enables CI gating and local hygiene checks.
- Provides machine-readable results for agents via JSON output.

## Functional Scope (v0.1)

- Scan `docs/` recursively for `*.md` (excluding `docs/00-governance/templates/`).
- Validate:
  - Frontmatter existence (error)
  - Frontmatter schema compliance against `docs/00-governance/metadata.schema.json` (error)
  - `document_id` regex and uniqueness (error)
  - Filename convention `^[a-z0-9-]+\\.md$` (warning)
  - Directory mapping for known types (warning)
  - Markdown inline links to files (error), ignoring fragments (`#...`) for existence checks

## Non-goals (v0.1)

- ID-to-path resolution for links (requires indexing).
- Anchor validation (`#heading`) correctness.
- Pre-commit / CI integration scaffolding.

## Inputs / Outputs

- Input: repo root directory.
- Output: list of violations. CLI supports text table and `--format json`.

## Edge Cases

- YAML scalar coercions: unquoted `last_updated` dates and numeric `version`/`docops_version` are normalized before schema validation.
- Schema errors include field path context when possible (e.g., `title: ...`).
- Schema load failures are repository-level and do not flood per-document:
  - `SCHEMA_MISSING` when the schema file is missing.
  - `SCHEMA_INVALID` when the schema file is unreadable/invalid JSON/invalid Draft 7 schema.

## Implementation Notes

- Use case: `src/meminit/core/use_cases/check_repository.py`
- Validators: `src/meminit/core/services/validators.py`

## Tests

- Unit tests for schema validator, link checker, and repository checking live under `tests/core/`.
