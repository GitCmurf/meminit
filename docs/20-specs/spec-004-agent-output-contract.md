---
document_id: MEMINIT-SPEC-004
type: SPEC
title: Agent Output Contract
status: Superseded
version: "1.1"
last_updated: 2026-03-05
owner: Product Team
docops_version: "2.0"
area: Agentic Integration
description: "Normative JSON output contract and error envelope for v2-migrated meminit CLI commands (currently check)."
superseded_by: MEMINIT-SPEC-008
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
> **Status:** Superseded  
> **Version:** 1.1  
> **Last Updated:** 2026-03-05  
> **Type:** SPEC  
> **Area:** Agentic Integration  
> **Superseded By:** [MEMINIT-SPEC-008](spec-008-agent-output-contract-v2.md)

# SPEC: Agent Output Contract

> [!IMPORTANT]
> This document is **Superseded** by [MEMINIT-SPEC-008](spec-008-agent-output-contract-v2.md).
> Content below is preserved for historical audit purposes only.

## 1. Purpose

This document defines the normative JSON output contract for v2-migrated Meminit CLI commands when `--format json` is used (currently `check`). It specifies the output envelope, error envelope, field semantics, determinism rules, and minimum required payloads per command.

## 2. Scope

In scope:

- JSON output for v2-migrated CLI commands (currently `check`).
- Error envelope and error code usage.
- Determinism and ordering rules for stable machine parsing.

Out of scope:

- Table or text output formats.
- Future v2 commands not yet migrated (e.g., `new`, `context`).

## 3. High-Level Design

The contract uses a single, stable JSON envelope for all commands. This envelope contains metadata (run ID, timestamp, root path) and a command-specific `data` object.

## 4. Output Envelope Structure

Every successful or partially successful execution MUST return a JSON object with the following top-level fields:

- `output_schema_version` (string): Current version of the output contract (e.g., "2.0").
- `success` (boolean): `true` if the command completed its primary task without blocking errors.
- `command` (string): The name of the command executed.
- `run_id` (string): UUID v4 uniquely identifying this execution.
- `timestamp` (string): ISO 8601 timestamp of execution.
- `root` (string): Absolute path to the repository root.
- `data` (object): Command-specific payload.
- `warnings` (array): List of non-blocking issues found.
- `violations` (array): List of document or repository violations.
- `advice` (array): List of recommended actions.

## 5. Error Envelope Structure

When a command fails with a blocking error (e.g., `git` not found, file permission denied), the envelope MUST include:

- `success`: `false`
- `error` (object):
  - `code` (string): Stable error identifier.
  - `message` (string): Human-readable error message.
  - `details` (object): Key-value pairs with error context.

## 6. Field Semantics

- **UUIDs**: All `run_id` and document IDs MUST be unique.
- **Paths**: All paths in the output MUST be relative to `root` and use forward slashes `/`.
- **Enums**: Error and violation codes MUST use UPPER_SNAKE_CASE.

## 7. Performance Considerations

- JSON generation SHOULD NOT add more than 50ms to command execution time.
- Large datasets (e.g., thousands of files) MUST be streamed or batched if memory limits are a concern, though current scope assumes in-memory JSON construction is acceptable.

## 8. Command Payload Profiles

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
    "run_id": {
      "type": "string",
      "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
    },
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
