---
document_id: MEMINIT-FDD-004
type: FDD
title: Document Factory (meminit new)
status: Draft
version: 0.1
last_updated: 2025-12-14
owner: GitCmurf
docops_version: 2.0
---

# FDD: Document Factory (meminit new)

## Feature Description

Create new governed documents with schema-valid frontmatter, predictable filenames, and template-driven content using `meminit new`.

## User Value

- Reduces human error in frontmatter and IDs.
- Provides a standardized “document creation workflow” for humans and agents.

## Functional Scope (v0.1)

- Command: `meminit new <TYPE> <TITLE>`
- Chooses target directory by type (default: `ADR` → `docs/45-adr/`), overridable via `docops.config.yaml:type_directories` for brownfield repos (e.g., `ADR` → `docs/adrs/`).
- Generates a new `document_id` using `repo_prefix` from `docops.config.yaml`:
  - `MEMINIT-ADR-001`, `MEMINIT-PRD-002`, etc.
- Generates filename `type-seq-slug.md` (e.g., `adr-001-my-decision.md`).
- Safety: must not overwrite an existing file at the target path; fail fast if the file already exists.
- Prepends schema-valid frontmatter.
- Loads a type-specific template when configured; otherwise uses a default skeleton.
  - Template keys are treated as case-insensitive document types (e.g., `ADR` and `adr` behave the same).
- Supports basic placeholder substitution:
  - `{title}`, `{status}`
  - legacy tokens like `<REPO>`, `<SEQ>`, `<YYYY-MM-DD>`, `<Decision Title>`

## Non-goals (v0.1)

- `--output json` for `new`.
- Area validation and config-driven controlled vocabularies beyond the JSON schema.

## Implementation Notes

- Use case: `src/meminit/core/use_cases/new_document.py`
- Config file: root `docops.config.yaml`

## Tests

- Unit tests cover ID auto-increment, template usage, and placeholder substitution.
