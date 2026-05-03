---
document_id: MEMINIT-SPEC-008
type: SPEC
title: Agent Output Contract (Templates v2 → v3)
status: Approved
version: "1.4"
last_updated: 2026-04-30
owner: Product Team
docops_version: "2.0"
area: AGENT
description: "Normative JSON output contract and error envelope for v2-migrated meminit CLI commands (including state queue surfaces)."
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
  - MEMINIT-PRD-007
  - MEMINIT-PLAN-013
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-008
> **Owner:** Product Team
> **Status:** Approved
> **Version:** 1.4
> **Last Updated:** 2026-04-30
> **Type:** SPEC
> **Area:** Agentic Integration

# SPEC: Agent Output Contract (Templates v2 → v3)

## 1. Purpose

This document defines the normative JSON output contract for all JSON-supporting Meminit CLI commands when `--format json` is used. It specifies the shared v3 envelope, error envelope, field semantics, determinism rules, and Phase 1–4 command payload profiles. Section 5 provides the authoritative per-command payload specification.

This is the v2 evolution of [MEMINIT-SPEC-004](spec-004-agent-output-contract.md).

## 2. Scope

In scope:

- JSON output for all JSON-supporting CLI commands (see Section 5 for the full command set, including Phase 1–4 payload profiles).
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

Current scope includes the shared v3 envelope plus the listed Phase 1-4 command payload profiles.

| Command             | Required `data` fields                                                                                   | Payload Type |
| ------------------- | -------------------------------------------------------------------------------------------------------- | ------------ |
| `check`             | See SPEC-004 counters                                                                                    | Object with integer counters |
| `new`               | `data.document_id`, `data.path`, `data.type`, `data.title`                                               | Object with string fields |
| `state set/get`     | `data.document_id`, `data.impl_state`, `data.updated`, `data.updated_by`                                 | Object with string fields |
| `state list`        | `data.entries`                                                                                           | Object containing an array |
| `state next`        | `data.entry`, `data.selection`, `data.reason`                                                            | Object containing `entry` object or `null`, selection object, and nullable reason |
| `state blockers`    | `data.blocked`, `data.summary`                                                                           | Object containing blocked-entry array and summary object |
| `capabilities`      | `data.capabilities_version`, `data.cli_version`, `data.commands`, `data.features`, `data.error_codes` | Object with strings, arrays, and feature-flag object |
| `explain`           | `data.code`, `data.category`, `data.summary`, `data.cause`, `data.remediation`, `data.spec_reference` | Object with detailed explanation, or array of summaries for `--list` |
| `index`             | `data.index_path`, `data.node_count`, `data.edge_count`, `data.nodes`, `data.edges`, `data.filtered` | Object containing graph index data |
| `resolve`           | `data.document_id`, `data.path`                                                                          | Object with resolution result (FILE_NOT_FOUND error on miss) |
| `identify`          | `data.path`, `data.document_id`                                                                          | Object with identification result (FILE_NOT_FOUND error on miss) |
| `link`              | `data.document_id`, `data.link`                                                                          | Object with link generation result (FILE_NOT_FOUND error on miss) |
| `protocol check`    | `data.summary`, `data.assets`                                                                            | Object with asset status array and counters |
| `protocol sync`     | `data.dry_run`, `data.applied`, `data.assets`, `data.summary`                                            | Object with sync outcome |

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

Optional:

- `advice`: Array of advisory items. Each item has required keys `code` and `message`, and MAY include `document_id` (string, per-item locator) and `path` (string, state-file reference).

For `command: state next`, the `data` object MUST contain:

Required:

- `entry`: The selected queue item, or `null` when the queue is empty.
- `selection`: Object containing the selection rule, candidate count, and applied filters.
- `reason`: `null` when an entry is returned; otherwise a stable empty-state reason such as `queue_empty` or `state_missing`.

For `command: state blockers`, the `data` object MUST contain:

Required:

- `blocked`: Array of blocked entries with their open blockers.
- `summary`: Object containing total entry counts and blocked/ready counts.

<!-- MEMINIT_SECTION: index_payload -->
### 5.3 `index` Command Payload

For `command: index`, the `data` object MUST contain:

Required:

- `index_path`: string (repo-relative path to written `meminit.index.json`, falling back to absolute if outside root)
- `node_count`: integer
- `edge_count`: integer
- `nodes`: Array of document node objects.
- `edges`: Array of directed relationship objects.
- `filtered`: boolean (true if `--status` or `--impl-state` filter was active)

Optional:

- `catalog_path`: string (repo-relative path to generated `catalogue.md` or equivalent, falling back to absolute if outside root)
- `kanban_path`: string (repo-relative path to generated `kanban.md`, falling back to absolute if outside root)

<!-- /MEMINIT_SECTION -->

<!-- MEMINIT_SECTION: protocol_sync_payload -->
### 5.4 `protocol sync` Command Payload

For `command: protocol sync`, the `data` object MUST contain:

Required:

- `dry_run`: boolean. Reflects whether the command was run in dry-run mode.
- `applied`: boolean. True only when a write or file-mode repair actually occurred and the command is not a dry run.
- `summary`: Object containing `total`, `rewritten`, `refused`, and `noop` counts.
- `assets`: Array of asset result objects.

Asset result fields:

- `id`: string asset ID.
- `target_path`: string relative path.
- `prior_status`: string drift outcome.
- `action`: string (`"noop"`, `"rewrite"`, or `"refuse"`).
- `preserved_user_bytes`: integer (present for mixed-ownership assets when user content was preserved).

**Refusal Semantics:**
- In dry-run mode, `violations` represent drift when `success` is false.
- In apply mode, `violations` are generated for assets with `action: "refuse"`.
- Refusal outcomes are represented both in `assets[].action == "refuse"` and in the `violations` array.

<!-- /MEMINIT_SECTION -->

<!-- MEMINIT_SECTION: capabilities_payload -->
### 5.5 `capabilities` Command Payload

For `command: capabilities`, the `data` object MUST contain:

Required:

- `capabilities_version`: string (e.g., "1.0")
- `cli_version`: string
- `commands`: Array of command capability objects.
- `features`: Object with boolean feature flags.
- `error_codes`: Array of strings (sorted error codes).

The command is repo-agnostic (`needs_root: false`), so `root` is omitted from the envelope.
Warnings, violations, and advice are always empty arrays.

<!-- /MEMINIT_SECTION -->

<!-- MEMINIT_SECTION: explain_payload -->
### 5.6 `explain` Command Payload

For `command: explain` (single code), the `data` object MUST contain:

Required:

- `code`: string (the error code explained)
- `category`: string
- `summary`: string
- `cause`: string
- `remediation`: Object containing `action` (string), `resolution_type` (string), `automatable` (boolean), and `relevant_commands` (array of strings)
- `spec_reference`: string

For `command: explain --list`, the `data` object MUST contain:

Required:

- `error_codes`: Array of objects, each containing `code`, `category`, and `summary`.

The command is repo-agnostic (`needs_root: false`), so `root` is omitted from the envelope.

<!-- /MEMINIT_SECTION -->

<!-- MEMINIT_SECTION: resolve_payload -->
### 5.7 `resolve` Command Payload

For `command: resolve`, the `data` object MUST contain on success:

Required:

- `document_id`: string
- `path`: string (repo-relative path)

On a miss (ID not found), the CLI emits a `FILE_NOT_FOUND` error envelope (`success: false`) with `data` as an empty object (`{}`).

<!-- /MEMINIT_SECTION -->

<!-- MEMINIT_SECTION: identify_payload -->
### 5.8 `identify` Command Payload

For `command: identify`, the `data` object MUST contain on success:

Required:

- `path`: string (repo-relative path)
- `document_id`: string

On a miss (path not found), the CLI emits a `FILE_NOT_FOUND` error envelope (`success: false`) with `data` as an empty object (`{}`).

<!-- /MEMINIT_SECTION -->

<!-- MEMINIT_SECTION: link_payload -->
### 5.9 `link` Command Payload

For `command: link`, the `data` object MUST contain on success:

Required:

- `document_id`: string
- `link`: string (Markdown-formatted link)

On a miss (ID not found), the CLI emits a `FILE_NOT_FOUND` error envelope (`success: false`) with `data` as an empty object (`{}`).

<!-- /MEMINIT_SECTION -->

<!-- MEMINIT_SECTION: protocol_check_payload -->
### 5.10 `protocol check` Command Payload

For `command: protocol check`, the `data` object MUST contain:

Required:

- `summary`: Object containing `total`, `aligned`, `drifted`, and `unparseable` counts.
- `assets`: Array of asset status objects.

Asset status fields:

- `id`: string asset ID.
- `target_path`: string relative path.
- `status`: string (e.g., "aligned", "missing", "tampered", "legacy", "unparseable").
- `auto_fixable`: boolean.

**Warnings/Violations:**
- A `success: false` result indicates drift.
- Violations are emitted for all drifted assets (status other than "aligned").

<!-- /MEMINIT_SECTION -->

## 6. Determinism Rules

Same as [MEMINIT-SPEC-004](spec-004-agent-output-contract.md).

## 7. JSON Schema

The normative schema is `docs/20-specs/agent-output.schema.v3.json`.

## 8. Version History

| Version | Date       | Author   | Changes |
| ------- | ---------- | -------- | ------- |
| 1.0     | 2026-03-05 | Product Team | Initial agent output contract for `check` and `new`. |
| 1.1     | 2026-04-16 | GitCmurf | Updated conditional root semantics and broadened command scope. |
| 1.2     | 2026-04-21 | Codex    | Added Phase 4 queue command payload profiles (`state next`, `state blockers`) and clarified merged `state list` expectations. |
| 1.3     | 2026-04-30 | Codex    | Added payload profiles for all Phase 1-3 commands and clarified protocol sync dry-run/apply semantics. |
| 1.4     | 2026-04-30 | Codex    | Remediation: Updated index command CLI payload fields, corrected resolve/identify/link to remove 'found', and documented protocol sync 'dry_run'. |
