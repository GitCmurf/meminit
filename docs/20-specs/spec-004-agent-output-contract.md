---
document_id: MEMINIT-SPEC-004
type: SPEC
title: Agent Output Contract
status: Draft
version: "0.2"
last_updated: 2026-02-18
owner: Product Team
docops_version: "2.0"
area: Agentic Integration
description: "Normative JSON output contract and error envelope for all meminit CLI commands."
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
> **Status:** Draft
> **Version:** 0.2
> **Last Updated:** 2026-02-18
> **Type:** SPEC
> **Area:** Agentic Integration

# SPEC: Agent Output Contract

## 1. Purpose

This document defines the normative JSON output contract for all Meminit CLI commands when `--format json` is used. It specifies the output envelope, error envelope, field semantics, determinism rules, and minimum required payloads per command.

Plain English: This is the single source of truth for what agents can rely on when they parse Meminit output.

## 2. Scope

In scope:
- JSON output for all CLI commands.
- Error envelope and error code usage.
- Determinism and ordering rules for stable machine parsing.

Out of scope:
- Human-readable text or markdown output.
- Logging and telemetry formats.
- Runbook workflows.

## 3. Terminology and Conventions

- "MUST", "SHOULD", "MAY" are used as normative terms.
- "Envelope" refers to the top-level JSON object emitted by the CLI.
- "Command" refers to the Meminit CLI subcommand invoked (for example `check`, `scan`, `new`).
- "Agent" refers to an automated tool that consumes JSON output.

Plain English: When this spec says MUST, the output is required to follow it.

## 4. Output Envelope

### 4.1 Required Top-Level Fields

All successful JSON outputs MUST include the following top-level fields.

1. `output_schema_version` (string)
2. `success` (boolean)
3. `command` (string)
4. `run_id` (string)
5. `root` (string)
6. `data` (object)
7. `warnings` (array)
8. `violations` (array)
9. `advice` (array)

Plain English: Every success response has the same fields, in the same places.

### 4.2 Optional Top-Level Fields

- `timestamp` (string, ISO 8601 UTC) MAY be present. When present it MUST be in the form `YYYY-MM-DDTHH:MM:SS[.sss]Z` (fractional seconds optional).

Plain English: Timestamp is allowed but not required, and it must be UTC.

Examples: `2026-02-18T14:30:45Z`, `2026-02-18T14:30:45.123Z`.

### 4.3 Top-Level Field Semantics

- `output_schema_version` identifies the contract version used to serialize the response.
- `success` indicates whether the command completed without fatal error.
- `command` is the subcommand name used by the user, normalized to the canonical CLI name.
- `run_id` is a unique identifier for correlating output and logs within a single invocation.
- `root` is the absolute path to the repository root used for the command.
- `data` contains command-specific payload details.
- `warnings` is a list of non-fatal issues.
- `violations` is a list of fatal or error-level issues.
- `advice` is a list of non-binding recommendations.

Plain English: The envelope tells you what command ran, where it ran, and what it found.

## 5. Error Envelope

Successful outputs MUST include the top-level fields listed in Section 4.1. Failed outputs MUST be a single JSON object that includes an `error` object and MAY omit `data`, `warnings`, `violations`, and `advice`. This failed shape is the **error envelope**.

### 5.1 Error Object

The `error` object MUST include:

1. `code` (string, from `ErrorCode` enum)
2. `message` (string)

The `error` object MAY include:

- `details` (object) with structured context

Plain English: Errors always have a stable code and a human-readable explanation.

## 6. Issue Object Format

Both `warnings` and `violations` MUST be arrays of Issue objects with the following fields.

1. `code` (string)
2. `message` (string)
3. `path` (string, relative to repo root)

Optional fields:
- `line` (integer)
- `severity` (string, one of `warning` or `error`)

Plain English: Each issue is a simple object so agents do not need to parse nested structures.

## 7. Advice Object Format

`advice` MUST be an array of objects with these fields.

1. `message` (string)

Optional fields:
- `code` (string)
- `details` (object)

Plain English: Advice is informative only and should not be treated as a violation.

## 8. Command Payload Profiles

Each command MUST populate `data` with at least the fields listed below.

| Command | Required `data` fields | Type |
| --- | --- | --- |
| `check` | `files_checked`, `files_passed`, `files_failed` | integers |
| `fix` | `fixed`, `remaining`, `dry_run` | integers, boolean |
| `scan` | `report` | object |
| `new` | `document_id`, `path`, `type`, `title` | strings |
| `index` | `index_path`, `document_count` | string, integer |
| `resolve` | `document_id`, `path` | strings |
| `identify` | `path`, `document_id` | strings |
| `link` | `document_id`, `link` | strings |
| `doctor` | `status`, `errors`, `warnings` | string, arrays |
| `context` | `repo_prefix`, `docops_version`, `docs_root`, `namespaces`, `schema_path`, `index_path` | strings, array |

Plain English: The `data` object has a minimum shape for every command.

## 9. Determinism Rules

1. Output MUST be a single JSON object on one line; a single trailing newline is permitted.
2. JSON object key ordering MUST be stable. The recommended order is:

`output_schema_version`, `success`, `command`, `run_id`, `timestamp`, `root`, `data`, `warnings`, `violations`, `advice`, `error`

3. Arrays MUST be sorted deterministically when their order is not semantically meaningful. Warnings MUST be sorted by `path`, then `line`, then `message`. Violations MUST be sorted by `path`, then `code`, then `severity`. Advice MUST be sorted by `code` then `message`.
4. When paths are included, they MUST be normalized with forward slashes and be relative to `root` unless explicitly documented otherwise.

Plain English: The same input should produce identical JSON output, so agents can diff reliably.

## 10. Compatibility and Versioning

- The output contract is versioned via `output_schema_version`.
- Backward-compatible changes MAY occur within the same version.
- Any breaking change MUST bump `output_schema_version` and be documented.

Plain English: If the output format changes in a breaking way, the version changes too.

## 11. JSON Schema (Normative)

The following schema defines the required shape of the output envelope for contract conformance.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Meminit Output Envelope v1",
  "type": "object",
  "required": [
    "output_schema_version",
    "success",
    "command",
    "run_id",
    "root"
  ],
  "properties": {
    "output_schema_version": {"type": "string"},
    "success": {"type": "boolean"},
    "command": {"type": "string"},
    "run_id": {"type": "string"},
    "timestamp": {"type": "string", "format": "date-time"},
    "root": {"type": "string"},
    "data": {"type": "object"},
    "warnings": {
      "type": "array",
      "items": {"$ref": "#/definitions/issue"}
    },
    "violations": {
      "type": "array",
      "items": {"$ref": "#/definitions/issue"}
    },
    "advice": {
      "type": "array",
      "items": {"$ref": "#/definitions/advice"}
    },
    "error": {"$ref": "#/definitions/error"}
  },
  "allOf": [
    {
      "if": {"properties": {"success": {"const": true}}},
      "then": {
        "required": ["data", "warnings", "violations", "advice"],
        "not": {"required": ["error"]}
      }
    },
    {
      "if": {"properties": {"success": {"const": false}}},
      "then": {"required": ["error"]}
    }
  ],
  "definitions": {
    "issue": {
      "type": "object",
      "required": ["code", "message", "path"],
      "properties": {
        "code": {"type": "string"},
        "message": {"type": "string"},
        "path": {"type": "string"},
        "line": {"type": "integer"},
        "severity": {"type": "string"}
      }
    },
    "advice": {
      "type": "object",
      "required": ["message"],
      "properties": {
        "message": {"type": "string"},
        "code": {"type": "string"},
        "details": {"type": "object"}
      }
    },
    "error": {
      "type": "object",
      "required": ["code", "message"],
      "properties": {
        "code": {"type": "string"},
        "message": {"type": "string"},
        "details": {"type": "object"}
      }
    }
  }
}
```

Plain English: This schema is what agents and tests should validate against.

## 12. Examples

### 12.1 Success Example

```json
{"output_schema_version":"1.0","success":true,"command":"check","run_id":"20260218-1f2c3a","root":"/repo","data":{"files_checked":42,"files_passed":41,"files_failed":1},"warnings":[],"violations":[{"code":"SCHEMA_INVALID","message":"Missing required field: owner","path":"docs/10-prd/prd-007-sample.md","line":5,"severity":"error"}],"advice":[]}
```

### 12.2 Error Example

```json
{"output_schema_version":"1.0","success":false,"command":"new","run_id":"20260218-1f2c3a","root":"/repo","error":{"code":"UNKNOWN_TYPE","message":"Unknown document type: XYZ","details":{"valid_types":["ADR","PRD","FDD"]}}}
```

## 13. Compliance Checklist

1. All commands emit a JSON envelope when `--format json` is requested.
2. All errors use the structured error object.
3. Output is deterministic and stable across repeated runs.
4. JSON output passes schema validation tests.

Plain English: If these are true, the contract is implemented.
