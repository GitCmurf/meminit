---
document_id: MEMINIT-FDD-004
type: FDD
title: Document Factory (meminit new)
status: Superseded
version: "1.0"
last_updated: 2026-03-05
owner: Product Team
docops_version: 2.0
superseded_by: MEMINIT-FDD-011
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-FDD-004
> **Owner:** Product Team
> **Status:** Superseded
> **Version:** 1.0
> **Last Updated:** 2026-03-05
> **Type:** FDD
> **Superseded By:** [MEMINIT-FDD-011](file:///home/cmf/code/Meminit/docs/50-fdd/fdd-011-document-factory-v2.md)

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
- Chooses target directory by type (default: `ADR` → `docs/45-adr/`), overridable via `docops.config.yaml:document_types` for brownfield repos (e.g., `ADR` → `docs/adrs/`).
- Generates a new `document_id` using `repo_prefix` from `docops.config.yaml`:
  - `MEMINIT-ADR-001`, `MEMINIT-PRD-002`, etc.
- Generates filename `type-seq-slug.md` (e.g., `adr-001-my-decision.md`).
- Safety: must not overwrite an existing file at the target path; fail fast if the file already exists.
- Prepends schema-valid frontmatter.
- Loads a type-specific template when configured via `document_types`; otherwise uses a default skeleton.
  - Template keys are treated as case-insensitive document types (e.g., `ADR` and `adr` behave the same).
- Supports placeholder substitution via `{{variable}}` syntax (Templates v2):
  - `{{title}}`, `{{status}}`, `{{document_id}}`, `{{owner}}`, `{{date}}`, `{{repo_prefix}}`, `{{seq}}`, `{{type}}`, `{{area}}`, `{{description}}`, `{{keywords}}`, `{{related_ids}}`
  - Legacy syntax (`{title}`, `<REPO>`, `<SEQ>`, etc.) is rejected with `INVALID_TEMPLATE_PLACEHOLDER` error.

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
- Template frontmatter merge and placeholders via `{{variable}}` syntax (Templates v2):
  `{{owner}}`, `{{area}}`, `{{description}}`, `{{keywords}}`, `{{related_ids}}`.
- Template resolution precedence chain (Templates v2): config → convention → builtin → skeleton.
- Section marker parsing (`<!-- MEMINIT_SECTION: id -->`) with code-fence awareness.
- Concurrency safety via directory lock.

## Non-goals (v0.3)

- Cross-day idempotency beyond ignoring `last_updated` differences (handled in MEMINIT-PRD-002 N6.1, v0.12, which defines the cross-day idempotency rule and `last_updated` handling).
- In-prompt tab completion beyond shell completion (out of scope).

## Implementation Notes

- Use case: `src/meminit/core/use_cases/new_document.py`
- Config file: root `docops.config.yaml`
- Templates v2 implementation:
  - `TemplateResolver` service (`src/meminit/core/services/template_resolver.py`)
  - `TemplateInterpolator` service (`src/meminit/core/services/template_interpolation.py`)
  - `SectionParser` service (`src/meminit/core/services/section_parser.py`)
  - `DocumentTypeConfig` dataclass in `RepoConfig` for `document_types` configuration

## Tests

- Unit tests cover ID auto-increment, template usage, and placeholder substitution.
- Templates v2 tests cover template resolution, interpolation syntax, and section parsing.
