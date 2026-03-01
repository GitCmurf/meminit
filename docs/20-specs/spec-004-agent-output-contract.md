---
document_id: MEMINIT-SPEC-004
type: SPEC
title: Agent Output Contract
status: Approved
version: "1.1"
last_updated: 2026-02-26
owner: Product Team
docops_version: "2.0"
area: Agentic Integration
description: "Normative JSON output contract and error envelope for v2-migrated meminit CLI commands (currently check)."
keywords:
  - agent
  - output
  - json
  - contract
  - cli
related_ids:
  - MEMINIT-PRD-003
  - MEMINIT-PLAN-003
  - MEMINIT-STRAT-001
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-004
> **Owner:** Product Team
> **Status:** Approved
> **Version:** 1.1
> **Last Updated:** 2026-02-26
> **Type:** SPEC
> **Area:** Agentic Integration

# SPEC: Agent Output Contract

## 1. Purpose

This document defines the normative JSON output contract for v2-migrated Meminit CLI commands when `--format json` is used (currently `check`). It specifies the output envelope, error envelope, field semantics, determinism rules, and minimum required payloads per command.

Plain English: This is the single source of truth for what agents can rely on when they parse Meminit output.

## 2. Scope

In scope:

- JSON output for v2-migrated CLI commands (currently `check`).
- Error envelope and error code usage.
- Determinism and ordering rules for stable machine parsing.

Out of scope:

- Human-readable text or markdown output.
- Logging and telemetry formats.
- Runbook workflows.
- Full normative definition of legacy v1 envelopes for non-migrated commands (covered by `docs/20-specs/agent-output.schema.v1.json`).

## 3. Terminology and Conventions

- "MUST", "SHOULD", "MAY" are used as normative terms.
- "Envelope" refers to the top-level JSON object emitted by the CLI.
- "Command" refers to the Meminit CLI subcommand invoked (for example `check`, `scan`, `new`).
- "Agent" refers to an automated tool that consumes JSON output.

Plain English: When this spec says MUST, the output is required to follow it.

## 4. Output Envelope

### 4.1 Required Top-Level Fields

All v2 JSON outputs MUST include the following top-level fields.

1. `output_schema_version` (string)
2. `success` (boolean)
3. `command` (string) — the subcommand name, normalized to the canonical CLI name
4. `run_id` (string, UUIDv4)
5. `root` (string) — absolute path to the repository root
6. `data` (object) — command-specific payload (empty `{}` when not applicable)
7. `warnings` (array) — non-fatal issues (empty `[]` when none)
8. `violations` (array) — fatal or error-level issues (empty `[]` when none)
9. `advice` (array) — non-binding recommendations (empty `[]` when none)

For `command: check`, successful and validation-failure outputs MUST additionally include:

1. `files_checked`, `files_passed`, `files_failed`
2. `missing_paths_count`, `schema_failures_count`
3. `warnings_count`, `violations_count`
4. `files_with_warnings`, `files_outside_docs_root_count`, `checked_paths_count`
5. `warnings` (array)
6. `violations` (array)

Plain English: the stable base envelope is small, and `check` adds the normative counters/findings fields.

### 4.2 Optional Top-Level Fields

- `timestamp` (string, ISO 8601 UTC) MAY be present. Included only when `--include-timestamp` is passed. When present it MUST be in the form `YYYY-MM-DDTHH:MM:SS[.sss]Z` (fractional seconds optional).
- `error` (object) MAY be present for operational failures (see §5).

For `command: check`, additional top-level counter fields are REQUIRED (see §4.1).
Check counters (`files_checked`, `files_passed`, `files_failed`, `missing_paths_count`, `schema_failures_count`, `warnings_count`, `violations_count`, `files_with_warnings`, `files_outside_docs_root_count`, `checked_paths_count`) are REQUIRED for successful `check` responses and validation-failure responses, and MAY be omitted only when a top-level operational `error` object is present.

Plain English: Timestamp is allowed but not required, and it must be UTC.

Examples: `2026-02-18T14:30:45Z`, `2026-02-18T14:30:45.123Z`.

### 4.3 Top-Level Field Semantics

- `output_schema_version` identifies the contract version used to serialize the response.
- `success` indicates whether the command completed without fatal error.
- `run_id` is a unique identifier for correlating output and logs within a single invocation.
- `command` is the subcommand name used by the user, normalized to the canonical CLI name.
- `root` is the absolute path to the repository root used for the command.
- `data` contains command-specific payload details; empty `{}` when not applicable.
- `warnings` is a list of non-fatal issues; empty `[]` when none.
- `violations` is a list of fatal or error-level issues; empty `[]` when none.
- `advice` is a list of non-binding recommendations; empty `[]` when none.

Plain English: The envelope tells you what command ran, where it ran, and what it found.

## 5. Error Envelope

Successful outputs MUST include the top-level fields listed in Section 4.1. Failed outputs MUST be a single JSON object and follow one of two shapes: an **error envelope** (with top-level `error`) for operational failures, or a **validation-failure envelope** (with top-level `violations`) for non-operational compliance findings.

### 5.1 Error Taxonomy

Meminit distinguishes between two types of failures to allow agents to handle them appropriately:

1. **Operational Errors**: Prevent the command from executing.
   - **JSON**: `success: false`, `error` object present.
   - **Arrays**: `warnings`, `violations`, `advice` are empty `[]`.
   - **Examples**: `CONFIG_MISSING`, `PATH_ESCAPE`, `UNKNOWN_TYPE`.
2. **Compliance Violations**: Successful execution that found non-compliant documents.
   - **JSON**: `success: false` (for `check`), `error` object absent.
   - **Arrays**: `violations` populated with findings.
   - **Examples**: `MISSING_FIELD`, `SCHEMA_INVALID`, `BROKEN_LINK`.

Plain English: If `error` exists, the tool failed; if `violations` exist, the documents failed.

### 5.2 Error Object

The `error` object MUST include:

1. `code` (string, from `ErrorCode` enum)
2. `message` (string)

The `error` object MAY include:

- `details` (object) with structured context

Plain English: Errors always have a stable code and a human-readable explanation.

## 6. Issue Object Format

`warnings` MUST be an array of Issue objects with the following fields.

1. `code` (string)
2. `message` (string)
3. `path` (string, relative to repo root)

Optional fields:

- `line` (integer)
- `severity` (string, one of `warning` or `error`)

For `check`, `violations` MAY contain grouped objects of the shape:

1. `path` (string)
2. `violations` (array of objects with required `code` and `message`, optional `line`)
3. optional `document_id` (string)

Plain English: warnings are flat issue objects; violations can be flat issues or grouped by file path.

## 7. Advice Object Format

`advice` MUST be an array of objects with these fields.

1. `code` (string) — stable identifier for deterministic sorting and agent handling
2. `message` (string)

Optional fields:

- `details` (object)

Plain English: Advice is informative only and should not be treated as a violation.

## 8. Command Payload Profiles

Current v2 scope includes `check` only. The `check` counters/findings are emitted at the top level (not nested under `data`).

| Command | Required top-level fields                                                                                                                                                                                            | Type     |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `check` | `files_checked`, `files_passed`, `files_failed`, `missing_paths_count`, `schema_failures_count`, `warnings_count`, `violations_count`, `files_with_warnings`, `files_outside_docs_root_count`, `checked_paths_count` | integers |

Plain English: in v2 today, `check` is the migrated command and its counters are top-level fields.

### 8.1 `check` Counter Semantics

For `command: check`, these counter semantics are normative:

- `files_checked` counts existing markdown files that were actually parsed and validated.
- `files_failed` counts only file-level failures among existing files.
- `missing_paths_count` counts unresolved path arguments in targeted mode.
- `schema_failures_count` counts repository-level schema failures (for example `SCHEMA_MISSING`, `SCHEMA_INVALID`).
- `violations_count` counts all emitted violations, including repository-level and missing-path violations.
- `success` is `false` if any file-level failures, missing paths, or schema failures exist, or when strict mode promotes warnings.

Plain English: `files_checked` is now strictly file-validation count, and repository-level failures are tracked separately.

## 9. Determinism Rules

1. Output MUST be a single JSON object on one line; a single trailing newline is permitted.
2. JSON object key ordering MUST be stable. The recommended order is:

`output_schema_version`, `success`, `command`, `run_id`, `timestamp`, `root`, `data`, `warnings`, `violations`, `advice`, `error`

3. Arrays MUST be sorted deterministically when their order is not semantically meaningful. Warnings MUST be sorted by `path`, then `line`, then `code`, then `message`. Violations MUST be sorted by `path`, then `code`, then `severity`, then `line`, then `message`. Advice MUST be sorted by `code` then `message`.
4. When `violations` are grouped by `path`, the outer list MUST be sorted by `path` and the inner `violations` array MUST be sorted by `code`, then `severity`, then `line`, then `message`.
5. When paths are included, they MUST be normalized with forward slashes and be relative to `root` unless explicitly documented otherwise.

Plain English: The same input should produce identical JSON output, so agents can diff reliably.

## 10. Compatibility and Versioning

- The output contract is versioned via `output_schema_version`.
- Backward-compatible changes MAY occur within the same version.
- Any breaking change MUST bump `output_schema_version` and be documented.
- Non-migrated commands remain on v1 and MUST validate against `docs/20-specs/agent-output.schema.v1.json` until explicitly migrated.

Plain English: If the output format changes in a breaking way, the version changes too.

## 11. JSON Schema (Normative)

The canonical schema for this contract version is `docs/20-specs/agent-output.schema.v2.json`.
For non-migrated commands, the canonical legacy schema is `docs/20-specs/agent-output.schema.v1.json`.
The inline schema below is a representative excerpt.
In v2, check counters are required for non-error payloads when `command` is
`check` or omitted (implicit check-shape envelope).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Meminit Output Envelope v2",
  "type": "object",
  "required": [
    "output_schema_version",
    "success",
    "command",
    "run_id",
    "root",
    "data",
    "warnings",
    "violations",
    "advice"
  ],
  "properties": {
    "output_schema_version": { "type": "string" },
    "success": { "type": "boolean" },
    "command": { "type": "string" },
    "run_id": { "type": "string", "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$" },
    "timestamp": { "type": "string", "format": "date-time" },
    "root": { "type": "string" },
    "data": { "type": "object" },
    "warnings": {
      "type": "array",
      "items": { "$ref": "#/definitions/issue" }
    },
    "violations": {
      "type": "array",
      "items": {
        "oneOf": [
          { "$ref": "#/definitions/issue" },
          { "$ref": "#/definitions/grouped_violations" }
        ]
      }
    },
    "advice": {
      "type": "array",
      "items": { "$ref": "#/definitions/advice" }
    },
    "error": { "$ref": "#/definitions/error" }
  },
  "allOf": [
    {
      "if": { "properties": { "success": { "const": true } } },
      "then": { "not": { "required": ["error"] } }
    },
    {
      "if": { "properties": { "success": { "const": false } } },
      "then": {
        "anyOf": [
          { "required": ["error"] },
          { "properties": { "violations": { "minItems": 1 } } }
        ]
      }
    },
    {
      "if": {
        "allOf": [
          { "not": { "required": ["error"] } },
          {
            "anyOf": [
              { "not": { "required": ["command"] } },
              { "properties": { "command": { "const": "check" } } }
            ]
          }
        ]
      },
      "then": {
        "required": [
          "files_checked",
          "files_passed",
          "files_failed",
          "missing_paths_count",
          "schema_failures_count",
          "warnings_count",
          "violations_count",
          "files_with_warnings",
          "files_outside_docs_root_count",
          "checked_paths_count",
          "warnings",
          "violations"
        ]
      }
    }
  ],
  "definitions": {
    "issue": {
      "type": "object",
      "required": ["code", "message", "path"],
      "properties": {
        "code": { "type": "string" },
        "message": { "type": "string" },
        "path": { "type": "string" },
        "line": { "type": "integer" },
        "severity": { "type": "string" }
      }
    },
    "grouped_violations": {
      "type": "object",
      "required": ["path", "violations"],
      "properties": {
        "path": { "type": "string" },
        "document_id": { "type": "string" },
        "violations": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
              "code": { "type": "string" },
              "message": { "type": "string" },
              "line": { "type": "integer" }
            }
          }
        }
      }
    },
    "advice": {
      "type": "object",
      "required": ["code", "message"],
      "properties": {
        "message": { "type": "string" },
        "code": { "type": "string" },
        "details": { "type": "object" }
      }
    },
    "error": {
      "type": "object",
      "required": ["code", "message"],
      "properties": {
        "code": { "type": "string" },
        "message": { "type": "string" },
        "details": { "type": "object" }
      }
    }
  }
}
```

Plain English: This schema is what agents and tests should validate against.

## 12. Examples

### 12.1 Validation Failure Example

```json
{
  "output_schema_version": "2.0",
  "success": false,
  "command": "check",
  "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "root": "/repo",
  "files_checked": 42,
  "files_passed": 41,
  "files_failed": 1,
  "missing_paths_count": 0,
  "schema_failures_count": 1,
  "warnings_count": 0,
  "violations_count": 2,
  "files_with_warnings": 0,
  "files_outside_docs_root_count": 0,
  "checked_paths_count": 43,
  "data": {},
  "warnings": [],
  "violations": [
    {
      "path": "docs/00-governance/metadata.schema.json",
      "violations": [
        { "code": "SCHEMA_INVALID", "message": "Schema is invalid", "line": 0 }
      ]
    },
    {
      "path": "docs/10-prd/prd-007-sample.md",
      "violations": [
        {
          "code": "MISSING_FIELD",
          "message": "Missing required field: owner",
          "line": 5
        }
      ]
    }
  ],
  "advice": []
}
```

### 12.2 Error Example

```json
{
  "output_schema_version": "2.0",
  "success": false,
  "command": "check",
  "run_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "root": "/repo",
  "data": {},
  "warnings": [],
  "violations": [],
  "advice": [],
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "File not found: docs/missing.md",
    "details": { "path": "docs/missing.md" }
  }
}
```

## 13. Compliance Checklist

1. All v2-migrated commands emit a JSON envelope when `--format json` is requested.
2. All operational errors use the structured error object.
3. Output is deterministic and stable across repeated runs.
4. JSON output passes schema validation tests.
5. Non-migrated command outputs continue to validate against the v1 schema until migrated.

Plain English: If these are true, the contract is implemented.
