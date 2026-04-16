---
document_id: MEMINIT-SPEC-008
type: SPEC
title: Agent Output Contract (Templates v2 → v3)
status: Draft
version: "1.1"
last_updated: 2026-04-16
owner: GitCmurf
docops_version: "2.0"
area: AGENT
description: "Normative JSON output contract and error envelope for v2-migrated meminit CLI commands (currently check and new)."
keywords:
  - agent
  - output
  - json
  - contract
  - cli
  - templates-v2
related_ids:
  - MEMINIT-SPEC-004
  - MEMINIT-SPEC-007
  - MEMINIT-PRD-006
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-008
> **Owner:** Product Team
> **Status:** Approved
> **Version:** 1.0
> **Last Updated:** 2026-03-05
> **Type:** SPEC
> **Area:** Agentic Integration

# SPEC: Agent Output Contract (Templates v2)

## 1. Purpose

This document defines the normative JSON output contract for v2-migrated Meminit CLI commands when `--format json` is used (currently `check` and `new`). It specifies the output envelope, error envelope, field semantics, determinism rules, and minimum required payloads per command.

This is the v2 evolution of [MEMINIT-SPEC-004](spec-004-agent-output-contract.md).

## 2. Scope

In scope:

- JSON output for v2-migrated CLI commands (currently `check` and `new`).
- Error envelope and error code usage.
- Determinism and ordering rules for stable machine parsing.

Out of scope:

- Human-readable text or markdown output.
- Logging and telemetry formats.
- Runbook workflows.

## 3. Terminology and Conventions

- "MUST", "SHOULD", "MAY" are used as normative terms.
- "Envelope" refers to the top-level JSON object emitted by the CLI.
- "Command" refers to the Meminit CLI subcommand invoked.
- "Agent" refers to an automated tool that consumes JSON output.

## 4. Output Envelope

### 4.1 Required Top-Level Fields

All v3 JSON outputs MUST include the following top-level fields:

1. `output_schema_version` (string) — `"3.0"`
2. `success` (boolean)
3. `command` (string)
4. `run_id` (string, UUIDv4)
5. `data` (object)
6. `warnings` (array)
7. `violations` (array)
8. `advice` (array)

#### 4.1.1 Conditional Fields

- `root` (string, absolute path) — **required** for repo-aware commands (`@agent_repo_options()`), **absent** for repo-agnostic commands (`capabilities`, `explain`, `org install`). Consumers MUST NOT assume `root` is universally present; check `output_schema_version` and the `command` field.
- `correlation_id` (string) — present only when the caller supplied `--correlation-id`.
- `timestamp` (string, ISO 8601) — present only when `--include-timestamp` is set.

For `command: check`, additional required fields include counters (see [MEMINIT-SPEC-004](spec-004-agent-output-contract.md)).

### 5. Command Payload Profiles

Current v2 scope includes `check`, `new`, and `state` commands.

| Command         | Required `data` fields                                                   | Type     |
| --------------- | ------------------------------------------------------------------------ | -------- |
| `check`         | See SPEC-004 counters                                                    | integers |
| `new`           | `data.document_id`, `data.path`, `data.type`, `data.title`               | strings  |
| `state set/get` | `data.document_id`, `data.impl_state`, `data.updated`, `data.updated_by` | strings  |
| `state list`    | `data.entries`                                                           | array    |

### 5.1 `new` Command Payload (Templates v2)

For `command: new`, the following `data` fields are normative for Templates v2:

Required:

- `document_id`
- `path`
- `type`
- `title`

Optional:

- `rendered_content`: Full rendered content.
- `content_sha256`: SHA-256 hash.
- `template`: Object with `applied`, `source`, `path`, `sections`.

### 5.2 `state` Command Payload

For `command: state set` and `command: state get`, the `data` object MUST contain:

Required:

- `document_id`
- `impl_state`
- `updated` (ISO-8601 string)
- `updated_by`

Optional:

- `notes`

For `command: state list`, the `data` object MUST contain:

Required:

- `entries`: Array of objects containing the fields above.

## 6. Determinism Rules

Same as [MEMINIT-SPEC-004](spec-004-agent-output-contract.md).

## 7. JSON Schema

The normative schema is `docs/20-specs/agent-output.schema.v3.json`.
