---
document_id: MEMINIT-SPEC-005
type: SPEC
title: Scan Plan Format
status: Draft
version: "0.2"
last_updated: 2026-02-18
owner: Product Team
docops_version: "2.0"
area: Adoption
description: "Normative JSON format for brownfield scan plans and plan-driven fixes."
keywords:
  - scan
  - plan
  - fix
  - migration
  - brownfield
related_ids:
  - MEMINIT-PRD-004
  - MEMINIT-PLAN-003
  - MEMINIT-STRAT-001
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-005
> **Owner:** Product Team
> **Status:** Draft
> **Version:** 0.2
> **Last Updated:** 2026-02-18
> **Type:** SPEC
> **Area:** Adoption

# SPEC: Scan Plan Format

## 1. Purpose

This document defines the JSON format for Meminit scan plans. Scan plans are machine-readable migration plans produced by `meminit scan --plan` and applied by `meminit fix --plan`.

Plain English: This spec describes the exact structure of the plan file that tells Meminit how to migrate a brownfield repo.

## 2. Scope

In scope:
- The plan file format and semantics.
- Required fields, action types, and validation rules.
- Deterministic ordering and safety constraints.

Out of scope:
- Heuristic algorithms used to create the plan.
- How humans should review the plan (runbook material).

## 3. Terminology and Conventions

- "Plan" refers to the JSON document written by `meminit scan --plan`.
- "Action" refers to a single migration step in the plan.
- "MUST", "SHOULD", and "MAY" are normative terms.

Plain English: When this spec says MUST, the plan has to follow it.

## 4. Top-Level Plan Structure

The plan MUST be a JSON object with these fields.

1. `plan_version` (string)
2. `generated_at` (string, ISO 8601 UTC)
3. `root` (string, absolute path)
4. `actions` (array of Action objects)
5. `summary` (object)

Plain English: Every plan has a version, a timestamp, a root path, and a list of actions.

### 4.1 Summary Object

`summary` MUST include:

1. `action_count` (integer)
2. `paths_scanned` (integer)
3. `governed_markdown_count` (integer)
4. `notes` (array of strings)

Plain English: The summary tells you how big the plan is and what was scanned.

## 5. Action Object

Each entry in `actions` MUST be an object with the following fields.

1. `id` (string)
2. `action` (string)
3. `path` (string, repo-relative)
4. `confidence` (number, 0.0 to 1.0)
5. `rationale` (array of strings)
6. `changes` (object)

Plain English: Every action says what to do, where to do it, and why.

### 5.1 Action Types

The `action` field MUST be one of the following values.

- `add_frontmatter`
- `update_frontmatter`
- `add_metadata_block`
- `rename_file`
- `move_file`
- `update_config`

Plain English: Actions are limited to safe, predictable operations.

Rename vs move semantics: use `rename_file` when the file stays in the same
directory and only the filename changes. Use `move_file` when the directory
path changes (including cases where the filename also changes).

### 5.2 Action-Specific `changes` Fields

`changes` MUST follow the rules below, based on `action`.

- `add_frontmatter` and `update_frontmatter`
  1. `metadata` (object, compliant with `docs/00-governance/metadata.schema.json`)

- `add_metadata_block`
  1. `block_text` (string, literal block to insert)

- `rename_file`
  1. `to` (string, repo-relative path)

- `move_file`
  1. `to` (string, repo-relative path)

- `update_config`
  1. `docops_config_patch` (object)

Plain English: The `changes` object is different depending on the action type.

## 6. Deterministic Ordering

1. `actions` MUST be sorted by `path` (ascending), then by `action` (ascending).
2. `id` MUST be stable and deterministic for a given input repository and MUST be assigned sequentially after sorting. Implementers MAY choose any string format as long as those constraints are met (e.g., `A0001`, `A0002`).

Plain English: The same repo should always produce the same plan.

## 7. Validation Rules

A plan MUST be rejected if any of the following are true.

1. `root` does not match the repository root where `meminit fix` is executed.
2. Any `path` is outside the repository root after normalization.
3. Any `to` path would overwrite an existing file.
4. Any `metadata` object fails the repo schema validation.
5. Any two actions reference the same source `path`, or any two actions produce the same `to` path.
6. Any `rename_file` or `move_file` action produces a `to` path that conflicts with another action's `path` or `to` path.

Normalization for containment checks MUST:
- Convert paths to absolute form.
- Normalize path separators (use `/` in plans; normalize to platform separators for checks).
- Collapse `.` and `..` segments.
- Remove redundant and trailing slashes.
- Resolve symbolic links when validating containment. If a symlink resolves outside the
  repository root, the plan MUST be rejected. If a symlink cannot be resolved
  (broken link, permission error) or a cycle is detected, the plan MUST be rejected.
- Use a bounded resolution algorithm to detect cycles and prevent escape.
- Normalize Windows drive letters and UNC paths to a canonical form before comparison.

Plain English: Plans are rejected if they could be unsafe or inconsistent.

## 8. Safety Constraints

1. No action may delete content or delete files.
2. All file writes MUST use safe path validation.
3. `meminit fix` MUST remain dry-run by default.

Plain English: The plan is always safe by default and cannot destroy content.

## 9. Compatibility and Versioning

- `plan_version` MUST start at `1.0.0` and use Semantic Versioning (MAJOR.MINOR.PATCH).
- Draft or experimental plans MAY use `0.y.z` during spec development; bump to `1.0.0` when the format is stable and public.
- A breaking change includes: removing or renaming required fields, changing field types, changing field semantics, or tightening validation rules.
- Non-breaking additive changes (new optional fields, relaxed validation) MAY keep the same major version.

Plain English: If the plan format changes in a breaking way, the version changes too.

## 10. JSON Schema (Informative)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Meminit Scan Plan v1",
  "type": "object",
  "required": ["plan_version", "generated_at", "root", "actions", "summary"],
  "properties": {
    "plan_version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
    "generated_at": {"type": "string", "format": "date-time"},
    "root": {"type": "string"},
    "actions": {
      "type": "array",
      "items": {"$ref": "#/definitions/action"}
    },
    "summary": {
      "type": "object",
      "required": ["action_count", "paths_scanned", "governed_markdown_count", "notes"],
      "properties": {
        "action_count": {"type": "integer"},
        "paths_scanned": {"type": "integer"},
        "governed_markdown_count": {"type": "integer"},
        "notes": {"type": "array", "items": {"type": "string"}}
      }
    }
  },
  "definitions": {
    "action": {
      "type": "object",
      "required": ["id", "action", "path", "confidence", "rationale", "changes"],
      "properties": {
        "id": {"type": "string"},
        "action": {
          "type": "string",
          "enum": [
            "add_frontmatter",
            "update_frontmatter",
            "add_metadata_block",
            "rename_file",
            "move_file",
            "update_config"
          ]
        },
        "path": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "rationale": {"type": "array", "items": {"type": "string"}},
        "changes": {"type": "object"}
      },
      "allOf": [
        {
          "if": {
            "properties": {"action": {"const": "add_frontmatter"}},
            "required": ["action"]
          },
          "then": {
            "properties": {
              "changes": {
                "type": "object",
                "required": ["metadata"],
                "properties": {"metadata": {"type": "object"}}
              }
            }
          }
        },
        {
          "if": {
            "properties": {"action": {"const": "update_frontmatter"}},
            "required": ["action"]
          },
          "then": {
            "properties": {
              "changes": {
                "type": "object",
                "required": ["metadata"],
                "properties": {"metadata": {"type": "object"}}
              }
            }
          }
        },
        {
          "if": {
            "properties": {"action": {"const": "add_metadata_block"}},
            "required": ["action"]
          },
          "then": {
            "properties": {
              "changes": {
                "type": "object",
                "required": ["block_text"],
                "properties": {"block_text": {"type": "string"}}
              }
            }
          }
        },
        {
          "if": {
            "properties": {"action": {"const": "rename_file"}},
            "required": ["action"]
          },
          "then": {
            "properties": {
              "changes": {
                "type": "object",
                "required": ["to"],
                "properties": {"to": {"type": "string"}}
              }
            }
          }
        },
        {
          "if": {
            "properties": {"action": {"const": "move_file"}},
            "required": ["action"]
          },
          "then": {
            "properties": {
              "changes": {
                "type": "object",
                "required": ["to"],
                "properties": {"to": {"type": "string"}}
              }
            }
          }
        },
        {
          "if": {
            "properties": {"action": {"const": "update_config"}},
            "required": ["action"]
          },
          "then": {
            "properties": {
              "changes": {
                "type": "object",
                "required": ["docops_config_patch"],
                "properties": {"docops_config_patch": {"type": "object"}}
              }
            }
          }
        }
      ]
    }
  }
}
```

Plain English: This schema is how tests should validate plan files.

## 11. Examples

### 11.1 Add Frontmatter

```json
{
  "id": "A0003",
  "action": "add_frontmatter",
  "path": "docs/decisions/2020-foo.md",
  "confidence": 0.82,
  "rationale": ["path_segment:decisions", "title:Decision"],
  "changes": {
    "metadata": {
      "document_id": "MEMINIT-ADR-042",
      "type": "ADR",
      "title": "Decision: Foo",
      "status": "Draft",
      "version": "0.1",
      "owner": "__TBD__",
      "docops_version": "2.0",
      "last_updated": "2026-02-18"
    }
  }
}
```

### 11.2 Rename File

```json
{
  "id": "A0011",
  "action": "rename_file",
  "path": "docs/45-adr/Decision Foo.md",
  "confidence": 0.91,
  "rationale": ["filename:spaces", "type_dir:45-adr"],
  "changes": {
    "to": "docs/45-adr/decision-foo.md"
  }
}
```

## 12. Compliance Checklist

1. `meminit scan --plan` writes a plan that validates against this spec.
2. `meminit fix --plan` rejects invalid or unsafe plans.
3. Plan actions are deterministic and stable for the same input repo.

Plain English: If these are true, the plan format is implemented.
