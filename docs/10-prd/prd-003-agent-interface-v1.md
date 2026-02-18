---
document_id: MEMINIT-PRD-003
type: PRD
title: Agent Interface v1
status: Draft
version: "0.1"
last_updated: 2026-02-18
owner: GitCmurf
docops_version: "2.0"
area: Agentic Integration
description: "Unified, deterministic CLI output contracts and agent protocol for meminit."
keywords:
  - agent
  - json
  - output
  - protocol
  - cli
  - contracts
related_ids:
  - MEMINIT-PLAN-003
  - MEMINIT-STRAT-001
  - MEMINIT-PRD-002
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PRD-003
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-02-18
> **Type:** PRD
> **Area:** Agentic Integration

# PRD: Agent Interface v1

## Executive Summary

Meminit already supports machine-readable output for some commands, but the contract is not consistent across the CLI, the error model is not uniform, and there is no published schema or protocol. This PRD defines a stable, deterministic agent interface for all Meminit commands, including a single output envelope, structured errors, and a documented versioned schema. The goal is to make Meminit safe and predictable for agent orchestrators while keeping outputs readable and helpful for humans.

## Plain-English Overview

Agents need a predictable, machine-readable response every time they run a Meminit command. Today, some commands print tables or colored text, others emit JSON, and errors can appear in a different shape. This epic makes every command return the same JSON envelope when `--format json` is used, with consistent fields, consistent error codes, and consistent ordering. It also adds a simple `meminit context` command to tell an agent what this repo looks like without guessing.

## Problem Statement

Meminit is designed for agentic workflows, but the CLI output contract is inconsistent and undocumented. Agents cannot reliably parse results across commands, cannot tell success from partial success in a consistent way, and cannot safely consume errors. Humans also lack a plain reference for what the JSON output means. This creates brittle agent integrations and slows adoption.

## Goals

1. Provide a single, documented JSON output envelope for every CLI command.
2. Guarantee structured, machine-parseable errors with stable error codes.
3. Publish a versioned JSON schema for outputs and keep it in sync with code.
4. Add a `meminit context` command that returns repo context in a deterministic format.
5. Ensure deterministic ordering and idempotent outputs to support testable, reliable agents.

## Non-Goals

1. Building a remote API or service.
2. Streaming logs or telemetry in real time.
3. Replacing human-readable text output.
4. Implementing semantic search or RAG in this epic.

## Target Users

- Agent orchestrators that need reliable machine-readable output.
- CI systems that parse Meminit output for reporting or gating.
- Human developers who need plain-English error messages and predictable flags.

## Scope

In scope:

- A CLI-wide output envelope for `--format json`.
- A published output schema file and versioning rules.
- Structured error responses for all commands, including validation failures before use case execution.
- A `meminit context` command for agent bootstrap.
- Deterministic output ordering and stable field names.

Out of scope:

- New repo scanning heuristics (covered by MEMINIT-PRD-004).
- UI, dashboards, or IDE integrations.

## Success Metrics

- 100 percent of CLI commands return a JSON envelope when `--format json` is set.
- 100 percent of error paths use the structured error envelope.
- Output schema version is declared and enforced via tests.
- Agents can parse results without command-specific logic.

## Functional Requirements

### FR-1 Unified Output Envelope

Requirement: All commands MUST emit a JSON output envelope when `--format json` is used. The envelope MUST include the fields listed in the Output Contract section and MUST be a single JSON object on one line.

Plain English: No matter which command an agent runs, it will always get the same shape back.

Implementation notes: Centralize JSON emission in a single formatter so all commands use the same logic. Avoid per-command JSON assembly in the CLI.

### FR-2 Structured Errors

Requirement: All errors MUST be returned using the structured error envelope, including argument validation errors before any use case executes. Each error MUST include a stable `code` and a human-readable `message`. Optional `details` MAY be included for structured context.

Plain English: Even when something fails early, the agent still gets a consistent JSON error to parse.

Implementation notes: Replace ad-hoc `click.echo` error JSON with a shared error formatter. Ensure `validate_root_path` and `validate_initialized` use the same envelope.

### FR-3 Output Schema and Versioning

Requirement: A JSON Schema file MUST be published in the repo to define the output envelope. The top-level field `output_schema_version` MUST be present in all JSON outputs. Any breaking change MUST bump the schema version.

Plain English: We publish the exact shape of outputs so agents can validate, and we only change it with version bumps.

Implementation notes: Maintain `docs/20-specs/spec-004-agent-output-contract.md` and add `docs/20-specs/agent-output.schema.v1.json`. Keep `OUTPUT_SCHEMA_VERSION` aligned with the published schema.

### FR-4 Command Coverage

Requirement: Every CLI command MUST support `--format json` and return the standard envelope. This includes `meminit fix`, `meminit init`, `meminit install-precommit`, and org profile commands.

Plain English: Agents should not need special-case logic for any command.

Implementation notes: Add `--format` where missing and route through a shared output function.

### FR-5 Determinism Rules

Requirement: All JSON outputs MUST be deterministic. Lists MUST be consistently ordered, and fields MUST use stable key names. Timestamps MUST be ISO 8601 in UTC when present.

Plain English: Running the same command twice should produce identical output except for fields that are explicitly time-based.

Implementation notes: Sort lists by stable keys and include `timestamp` only when required. Use `run_id` to correlate logs without altering content ordering.

### FR-6 `meminit context` Command

Requirement: Add a `meminit context` command that returns repo configuration, namespaces, docs root, schema path, and index location using the standard envelope.

Plain English: Agents can ask Meminit "what does this repo look like?" without guessing.

Implementation notes: Use existing config loaders and namespace models. Do not scan the entire repo by default. Provide a `--deep` flag if a full scan is needed.

### FR-7 Backward Compatible Text Output

Requirement: Existing text output MUST remain intact unless it conflicts with JSON requirements. New JSON support MUST NOT break current human workflows.

Plain English: Humans should not notice any changes unless they ask for JSON output.

Implementation notes: Keep current `text` and `md` outputs for existing commands where possible.

## Output Contract (v1)

### JSON Envelope

All commands MUST return a single JSON object with the following shape when `--format json` is used.

```json
{
  "output_schema_version": "1.0",
  "success": true,
  "command": "check",
  "run_id": "20260218-1f2c3a",
  "timestamp": "2026-02-18T21:40:00Z",
  "root": "/path/to/repo",
  "data": {},
  "warnings": [],
  "violations": [],
  "advice": []
}
```

### Error Envelope

```json
{
  "output_schema_version": "1.0",
  "success": false,
  "command": "new",
  "run_id": "20260218-1f2c3a",
  "timestamp": "2026-02-18T21:40:00Z",
  "error": {
    "code": "UNKNOWN_TYPE",
    "message": "Unknown document type: XYZ",
    "details": {
      "valid_types": ["ADR", "PRD", "FDD"]
    }
  }
}
```

### Command-Specific Payloads

- `data` MUST be a dictionary, even if empty.
- `warnings`, `violations`, and `advice` MUST be arrays, even if empty.
- `command` MUST match the invoked CLI subcommand name.

## Command Output Profiles

Each command MUST map its internal result to the standard envelope. The following payloads are required at minimum.

| Command    | Required `data` fields                                                                  |
| ---------- | --------------------------------------------------------------------------------------- |
| `check`    | `files_checked`, `files_failed`, `violations`, `warnings`                               |
| `fix`      | `fixed`, `remaining`, `dry_run`                                                         |
| `scan`     | `report`                                                                                |
| `new`      | `document_id`, `path`, `type`, `title`                                                  |
| `index`    | `index_path`, `document_count`                                                          |
| `resolve`  | `document_id`, `path`                                                                   |
| `identify` | `path`, `document_id`                                                                   |
| `link`     | `document_id`, `link`                                                                   |
| `doctor`   | `status`, `errors`, `warnings`                                                          |
| `context`  | `repo_prefix`, `docops_version`, `docs_root`, `namespaces`, `schema_path`, `index_path` |

Plain English: Each command has a minimum set of fields an agent can rely on without guessing.

## Error Codes and Exit Codes

Error codes MUST use the shared `ErrorCode` enum. Exit codes MUST be deterministic and documented. Successful commands MUST exit with `0`. Validation failures MUST exit with `1` unless a more specific code is mandated by existing behavior.

Plain English: An agent can rely on the error code for logic and still trust the process exit code.

## Determinism and Idempotency

- Output ordering MUST be stable and sorted where applicable.
- Fields MUST use consistent casing and naming across commands.
- For operations that can be re-run, the JSON output MUST be consistent if inputs do not change.

Plain English: Agents should not need to diff or normalize outputs just to know what happened.

## Security and Privacy

- No outputs should include secrets or full file contents.
- Paths MUST be relative where possible, except when absolute paths are explicitly requested.
- `meminit context` MUST avoid leaking excluded paths or ungoverned files unless `--deep` is set.

Plain English: The output gives agents what they need without leaking sensitive data.

## Implementation Details

### Code Changes

- Add a shared output formatter in `src/meminit/core/services/output_formatter.py` that builds the envelope and enforces ordering.
- Refactor CLI commands in `src/meminit/cli/main.py` to call the shared formatter for JSON output.
- Extend `src/meminit/core/services/output_contracts.py` to include schema constants and version assertions.
- Add a new use case and CLI command `meminit context` under `src/meminit/core/use_cases/context_repository.py` and `src/meminit/cli/main.py`.
- Ensure `meminit fix` supports `--format json` and emits the standard envelope.

### Documentation Changes

- Update `docs/20-specs/spec-004-agent-output-contract.md` to describe the contract and error taxonomy.
- Add `docs/20-specs/agent-output.schema.v1.json` and keep it in sync with code.
- Update any runbooks that describe agent usage to reference the new output contract.

### Testing Requirements

- Add unit tests for the output formatter with stable ordering.
- Add CLI integration tests to verify JSON outputs for every command.
- Add schema validation tests that ensure outputs conform to `agent-output.schema.v1.json`.
- Add regression tests for error paths that previously emitted ad-hoc JSON.

## Rollout Plan

1. Implement shared formatter and migrate one command at a time.
2. Add the schema and protocol docs.
3. Update all commands to comply.
4. Run `meminit check` and `pytest` in CI to confirm full compatibility.

## Open Questions

1. Should `output_schema_version` remain `1.0` with additive fields, or should it move to `1.1` for this epic?
2. Should `meminit context` include index data by default or require `--deep`?
3. Should `--output` be standardized as a file-path flag (distinct from `--format`), or remain optional for commands that already support it? `--format` remains the output format selector.

## Related Documents

- MEMINIT-STRAT-001
- MEMINIT-PLAN-003
- MEMINIT-PRD-002
