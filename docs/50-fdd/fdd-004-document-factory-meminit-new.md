---
document_id: MEMINIT-FDD-004
type: FDD
title: Document Factory (meminit new)
status: Superseded
version: 0.3
last_updated: 2026-02-18
owner: GitCmurf
docops_version: 2.0
superseded_by: MEMINIT-PRD-002
---

# FDD: Document Factory (meminit new)

## Status Note

This FDD is superseded in scope by MEMINIT-PRD-002 and remains as an
implementation reference aligned to the current CLI behavior.

Maintenance note: This document is reference-only. New design decisions and
requirements must be recorded in MEMINIT-PRD-002.

Version 0.3 and the 2026-02-18 `last_updated` date capture the final implemented
state before supersession; MEMINIT-PRD-002 is the authoritative source.

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

## Functional Scope (v0.3)

- Structured output via `--format json` with stable envelopes.
- Extended metadata flags: `--owner`, `--area`, `--description`, `--status`,
  `--keywords`, `--related-ids`.
- Deterministic IDs via `--id` with idempotent success when content matches.
- Note: `meminit new` without `--id` is non-idempotent (allocates the next sequence).
- `--dry-run`, `--verbose`, `--list-types` for control and observability.
- Human UX: `--interactive`, `--edit` (with documented incompatibilities).
- Visible metadata block replacement when template contains
  `<!-- MEMINIT_METADATA_BLOCK -->`.
- Template frontmatter merge and placeholders:
  `{owner}`, `{area}`, `{description}`, `{keywords}`, `{related_ids}`.
- Concurrency safety via directory lock.

## Non-goals (v0.3)

- Cross-day idempotency beyond ignoring `last_updated` differences (handled in MEMINIT-PRD-002 N6.1, v0.12, which defines the cross-day idempotency rule and `last_updated` handling).
- In-prompt tab completion beyond shell completion (out of scope).

## Implementation Notes

- Use case: `src/meminit/core/use_cases/new_document.py`
- Config file: root `docops.config.yaml`

## Tests

- Unit tests cover ID auto-increment, template usage, and placeholder substitution.
