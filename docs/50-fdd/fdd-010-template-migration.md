---
document_id: MEMINIT-FDD-010
type: FDD
title: Template Migration Tool (meminit migrate-templates)
status: Draft
version: 0.1
last_updated: 2026-03-04
owner: Product Team
docops_version: 2.0
area: CORE
description: "Functional design for the meminit migrate-templates command to convert legacy templates and configurations to Templates v2 format."
keywords:
  - migration
  - template
  - templates-v2
  - cli
related_ids:
  - MEMINIT-PRD-006
  - MEMINIT-ADR-014
  - MEMINIT-SPEC-007
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-FDD-010
> **Owner:** Product Team
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-03-04
> **Type:** FDD

# FDD: Template Migration Tool (meminit migrate-templates)

## Feature Description

Automated migration tool to convert legacy Meminit template configurations and placeholder syntax to Templates v2 format.

## User Value

- Reduces manual effort in migrating to Templates v2
- Provides deterministic, reviewable migration output
- Enables safe rollback with dry-run mode
- Supports gradual migration with selective options

## Functional Scope (v0.1)

### Command Interface

```bash
meminit migrate-templates [OPTIONS]
```

### Options

| Option                    | Description                             | Default                         |
| ------------------------- | --------------------------------------- | ------------------------------- |
| `--dry-run`               | Show changes without applying them      | `true`                          |
| `--no-dry-run`            | Apply changes                           | `false`                         |
| `--config`                | Path to config file                     | `docops.config.yaml`            |
| `--templates-dir`         | Path to templates directory             | `docs/00-governance/templates/` |
| `--backup`                | Create backup before modifying          | `true`                          |
| `--no-backup`             | Skip backup                             | `false`                         |
| `--legacy-type-dirs`      | Migrate type_directories config         | `true`                          |
| `--no-legacy-type-dirs`   | Skip type_directories migration         | `false`                         |
| `--legacy-templates`      | Migrate templates config                | `true`                          |
| `--no-legacy-templates`   | Skip templates migration                | `false`                         |
| `--placeholder-syntax`    | Migrate placeholder syntax              | `true`                          |
| `--no-placeholder-syntax` | Skip placeholder syntax migration       | `false`                         |
| `--rename-files`          | Rename template files to \*.template.md | `true`                          |
| `--no-rename-files`       | Skip file renaming                      | `false`                         |
| `--format`                | Output format (text, json)              | `text`                          |

### Migration Steps

#### 1. Config Migration (type_directories → document_types)

Convert legacy `type_directories` configuration to `document_types` format.

**Before:**

```yaml
type_directories:
  ADR: "45-adr"
  PRD: "10-prd"
  FDD: "50-fdd"
templates:
  ADR: "docs/00-governance/templates/template-001-adr.md"
  PRD: "docs/00-governance/templates/template-001-prd.md"
```

**After:**

```yaml
document_types:
  ADR:
    directory: "45-adr"
    template: "docs/00-governance/templates/adr.template.md"
  PRD:
    directory: "10-prd"
    template: "docs/00-governance/templates/prd.template.md"
  FDD:
    directory: "50-fdd"
    template: "docs/00-governance/templates/fdd.template.md"
```

**Preservation Rules:**

- If a `document_types` key already exists, merge legacy entries into it
- Namespace-level `type_directories` take precedence over defaults
- Custom template paths are preserved

#### 2. Template File Renaming

Rename template files from `template-001-*.md` to `*.template.md`.

**Mappings:**

- `template-001-adr.md` → `adr.template.md`
- `template-001-prd.md` → `prd.template.md`
- `template-001-fdd.md` → `fdd.template.md`
- `template-001-<type>.md` → `<type>.template.md`

**Conflict Resolution:**

- If target file exists, append suffix: `adr.template.1.md`
- Log conflicts in output

#### 3. Placeholder Syntax Migration

Convert legacy placeholder syntax to `{{variable}}` format.

**Legacy → New:**

- `{title}` → `{{title}}`
- `{status}` → `{{status}}`
- `{owner}` → `{{owner}}`
- `{area}` → `{{area}}`
- `{description}` → `{{description}}`
- `{keywords}` → `{{keywords}}`
- `{related_ids}` → `{{related_ids}}`
- `<REPO>` → `{{repo_prefix}}`
- `<PROJECT>` → `{{repo_prefix}}`
- `<SEQ>` → `{{seq}}`
- `<YYYY-MM-DD>` → `{{date}}`
- `<Decision Title>` → `{{title}}`
- `<Feature Title>` → `{{title}}`
- `<Team or Person>` → `{{owner}}`
- `<AREA>` → `{{area}}`

**Extraction Rules:**

- Replace exact matches only (case-sensitive)
- Preserve whitespace around placeholders
- Skip replacements inside code fences (marked as boundaries)

## Output Format

### Text Output (default)

```text
Template Migration Tool (meminit migrate-templates)
=====================================================

Config file: docops.config.yaml
Templates dir: docs/00-governance/templates/
Dry run: true

Migration summary:
- Config entries: 3 found, 3 migrated
- Template files: 3 found, 3 renamed
- Placeholder replacements: 42 across 3 files

Changes to apply:
1. Config: Add document_types.ADR.directory = "45-adr"
2. Config: Add document_types.ADR.template = "docs/00-governance/templates/adr.template.md"
3. Config: Remove type_directories.ADR
4. Config: Remove templates.ADR
5. File: Rename template-001-adr.md → adr.template.md
6. File: Replace {title} with {{title}} (12 occurrences)
...

Backup: .meminit/migrations/backup-20260304-143052/

Run with --no-dry-run to apply changes.
```

### JSON Output

```json
{
  "output_schema_version": "2.0",
  "success": true,
  "command": "migrate-templates",
  "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
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
        "action": "add",
        "path": "document_types.ADR.template",
        "value": "docs/00-governance/templates/adr.template.md"
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

## Non-goals

- Migration of document content (only templates and configs)
- Automatic section marker addition to existing templates
- Validation of migrated template content
- Migration of custom organizational profiles

## Implementation Notes

- Use case: `src/meminit/core/use_cases/migrate_templates.py` (Planned, not yet implemented)
- Config file: root `docops.config.yaml`
- Backup location: `.meminit/migrations/backup-<timestamp>/`

### Security Considerations

- Validate all file paths before renaming
- Ensure backup directory is within repo root
- Reject path traversal attempts
- Validate template syntax after migration

## Error Handling

| Error Code       | Condition                     | Resolution                 |
| ---------------- | ----------------------------- | -------------------------- |
| `CONFIG_MISSING` | No `docops.config.yaml` found | Create with `meminit init` |
| `PATH_ESCAPE`    | Backup path outside repo      | Fail with error            |
| `FILE_EXISTS`    | Target template file exists   | Append suffix, log warning |
| `INVALID_CONFIG` | Config cannot be parsed       | Fail with error details    |

## Tests

- Unit tests for config migration logic
- Unit tests for placeholder replacement
- Integration tests for full migration workflow
- Dry-run verification tests
- Backup and rollback tests

## Rollback Strategy

1. Backups are created in `.meminit/migrations/backup-<timestamp>/`
2. Original config file is copied before modification
3. Original template files are copied before modification
4. Manual rollback: Restore from backup directory
5. Future: `meminit migrate-templates --rollback` command
