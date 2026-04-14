---
document_id: MEMINIT-SPEC-010
type: SPEC
title: Template Migration Specification
status: Draft
version: 0.2
last_updated: 2026-04-14
owner: Product Team
docops_version: 2.0
area: CORE
description: "Implementation specification for meminit migrate-templates command to convert legacy templates and configurations to Templates v2 format."
keywords:
  - migration
  - template
  - templates-v2
  - cli
related_ids:
  - MEMINIT-FDD-010
  - MEMINIT-PRD-006
  - MEMINIT-ADR-014
  - MEMINIT-SPEC-007
  - MEMINIT-PLAN-006
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-010
> **Owner:** Product Team
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-03-07
> **Type:** SPEC

# SPEC: Template Migration Tool (meminit migrate-templates)

## 1. Overview

This specification defines the implementation details for the `meminit migrate-templates` command.

## 2. Supported Legacy Config Keys

### 2.1 type_directories

Legacy format:

```yaml
type_directories:
  ADR: "45-adr"
  PRD: "10-prd"
  FDD: "50-fdd"
```

Conversion to `document_types`:

```yaml
document_types:
  ADR:
    directory: "45-adr"
  PRD:
    directory: "10-prd"
  FDD:
    directory: "50-fdd"
```

### 2.2 templates

Legacy format:

```yaml
templates:
  ADR: "docs/00-governance/templates/template-001-adr.md"
  PRD: "docs/00-governance/templates/template-001-prd.md"
```

Conversion to `document_types`:

```yaml
document_types:
  ADR:
    template: "docs/00-governance/templates/adr.template.md"
  PRD:
    template: "docs/00-governance/templates/prd.template.md"
```

### 2.3 Conflict Resolution

- If `document_types` already exists with a key, namespace-level `type_directories` does NOT override it
- Custom template paths in `document_types` are preserved
- If a key exists in both legacy and new format, the migration logs a warning and skips

## 3. Supported Legacy Placeholder Syntax

| Legacy Syntax      | New Syntax        | Notes |
| ------------------ | ----------------- | ----- |
| `{title}`          | `{{title}}`       |       |
| `{status}`         | `{{status}}`      |       |
| `{owner}`          | `{{owner}}`       |       |
| `{area}`           | `{{area}}`        |       |
| `{description}`    | `{{description}}` |       |
| `{keywords}`       | `{{keywords}}`    |       |
| `{related_ids}`    | `{{related_ids}}` |       |
| `<REPO>`           | `{{repo_prefix}}` |       |
| `<PROJECT>`        | `{{repo_prefix}}` |       |
| `<SEQ>`            | `{{seq}}`         |       |
| `<YYYY-MM-DD>`     | `{{date}}`        |       |
| `<Decision Title>` | `{{title}}`       |       |
| `<Feature Title>`  | `{{title}}`       |       |
| `<Team or Person>` | `{{owner}}`       |       |

### 3.1 Extraction Rules

- Replace exact matches only (case-sensitive for most, except as noted)
- Preserve whitespace around placeholders
- Skip replacements inside code fences (``` or indented code blocks)
- Skip replacements inside HTML comments that look like `<!-- code -->`

## 4. Failure Modes

### 4.1 Mixed Syntax

If a template file contains BOTH legacy placeholders AND new `{{variable}}` syntax:

- Log a warning about mixed syntax
- Still perform the migration but flag as "needs review"

### 4.2 Ambiguous Patterns

The following are rejected (require manual review):

- `{variable}` where variable is unknown (not in supported list)
- `<VARIABLE>` where VARIABLE is unknown

### 4.3 Missing Files

- If config file is missing: error with CONFIG_MISSING code
- If template directory is missing: skip template migration, warn

## 5. JSON Output Contract

### 5.1 Dry-Run Mode

```json
{
  "output_schema_version": "2.0",
  "success": true,
  "command": "migrate-templates",
  "run_id": "uuid",
  "root": "/repo",
  "data": {
    "config_file": "docops.config.yaml",
    "templates_dir": "docs/00-governance/templates/",
    "dry_run": true,
    "backup_path": ".meminit/migrations/backup-20260304-143052/",
    "summary": {
      "config_entries_found": 3,
      "config_entries_migrated": 3,
      "template_files_found": 3,
      "template_files_renamed": 3,
      "placeholder_replacements": 42
    },
    "changes": [
      {
        "type": "config",
        "action": "add",
        "path": "document_types.ADR.directory",
        "value": "45-adr"
      },
      {
        "type": "config",
        "action": "remove",
        "path": "type_directories.ADR"
      },
      {
        "type": "file",
        "action": "rename",
        "from": "docs/00-governance/templates/template-001-adr.md",
        "to": "docs/00-governance/templates/adr.template.md"
      },
      {
        "type": "file",
        "action": "replace",
        "file": "docs/00-governance/templates/adr.template.md",
        "from": "{title}",
        "to": "{{title}}",
        "count": 12
      }
    ]
  },
  "warnings": [],
  "violations": [],
  "advice": []
}
```

### 5.2 Apply Mode

Same as dry-run but with `"dry_run": false` and actual file modifications made.

### 5.3 Failure Mode

- Operational migration failures MUST return a schema-valid JSON error envelope.
- The envelope MUST include `success: false` and an `error` object with a stable code and message.
- The migration report MAY still be included in `data` for machine inspection.
- The command MUST exit non-zero on failure in all output formats, including Markdown.

## 6. Idempotency Rules

- Running migration twice should produce the same result
- Config migration: skip keys that are already in new format
- Placeholder migration: skip if placeholder is already in new format
- File renaming: skip if target already exists

## 7. Backup Strategy

- Default: create backup in `.meminit/migrations/backup-<timestamp>/`
- Config: copy original `docops.config.yaml`
- Templates: copy all affected template files

## 8. File Renaming Rules

Legacy pattern: `template-001-<type>.md`
New pattern: `<type>.template.md`

Examples:

- `template-001-adr.md` → `adr.template.md`
- `template-001-prd.md` → `prd.template.md`
- `template-001-fdd.md` → `fdd.template.md`

Conflict resolution:

- If target exists, append suffix: `adr.template.1.md`
