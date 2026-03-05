---
document_id: MEMINIT-FDD-011
type: FDD
title: Document Factory (meminit new) - Templates v2
status: Draft
version: "1.0"
last_updated: 2026-03-05
owner: Product Team
docops_version: "2.0"
area: CORE
description: "Functional design for the meminit new command using Templates v2 system."
related_ids:
  - MEMINIT-FDD-004
  - MEMINIT-PRD-006
  - MEMINIT-SPEC-007
---

# FDD: Document Factory (meminit new) - Templates v2

## Feature Description

The `meminit new` command creates new governed documents using the Templates v2 resolution and interpolation system.

## User Value

- Consistent document creation across repositories
- Automatic metadata generation and frontmatter enrichment
- Support for agent-orchestratable section markers
- Secure template resolution precedence chain

## Functional Scope

### 1. Template Resolution

The command resolves templates using this deterministic precedence chain:

1. **Config**: `document_types.<type>.template` in `docops.config.yaml`
2. **Convention**: `<docs_root>/00-governance/templates/<type>.template.md`
3. **Built-in**: Package assets (ADR, PRD, FDD)
4. **Skeleton**: Minimal fallback if no other template is found

### 2. Interpolation

Uses the `TemplateInterpolator` to replace `{{variable}}` placeholders with:

- `title`
- `document_id`
- `owner`
- `status`
- `repo_prefix`
- `seq`
- `date`
- `area`, `description`, `keywords`, `related_ids`

### 3. Metadata Generation

Generates standard frontmatter and a visible `<!-- MEMINIT_METADATA_BLOCK -->`.

## Implementation Notes

- Orchestration: `src/meminit/core/use_cases/new_document.py`
- Resolution: `src/meminit/core/services/template_resolver.py`
- Interpolation: `src/meminit/core/services/template_interpolation.py`
- Parsing: `src/meminit/core/services/section_parser.py`
