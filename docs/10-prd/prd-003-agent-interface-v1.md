---
document_id: MEMINIT-PRD-003
type: PRD
title: Agent Interface v1
status: Draft
version: "0.3"
last_updated: 2026-02-21
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
> **Version:** 0.3
> **Last Updated:** 2026-02-21
> **Type:** PRD
> **Area:** Agentic Integration

# PRD: Agent Interface v1

## Executive Summary

Meminit is a DocOps compliance tool designed to be used by humans and agents inside real development repositories (including monorepos). For agents to reliably build, maintain, and evolve governed documentation, Meminit must present a deterministic, machine-parseable interface with uniform semantics across all CLI commands.

This PRD defines Agent Interface v1: a unified CLI contract (flags, stdout/stderr behavior, exit code semantics) and a versioned JSON output contract (single-line envelopes, structured errors, deterministic ordering) that allows agent orchestrators to integrate Meminit safely, with low friction and without brittle command-specific parsing.

Value in production: this interface makes Meminit an "agent-safe" guardrail for the AI SDLC. Agents can (1) discover repo DocOps constraints via `meminit context`, (2) create/update docs using Meminit templates and metadata rules, (3) validate with `meminit check`, and (4) remediate via `meminit fix` or targeted edits, all while maintaining traceability (`document_id`), schema-valid metadata, and predictable outcomes suitable for CI gating and automation.

Current rollout status (as of 2026-02-21): delivery is phased. `meminit check` is migrated to output schema v2 (normative definitions live in `MEMINIT-SPEC-004`). Non-migrated commands either remain on legacy v1 envelopes or are currently text-only until migrated.

## Plain-English Overview

Agents need to treat Meminit like a deterministic library: same inputs, same outputs, no surprises. Today, output shapes vary across commands and error paths, which forces orchestration code to special-case behavior. That brittleness is unacceptable in production, especially in CI and in agent loops where correctness and stability are more important than pretty text output.

Agent Interface v1 makes Meminit predictable:

- Every command supports `--format json` (once migrated).
- JSON output is a single object on one line and uses a stable envelope.
- Operational errors are structured (stable codes, consistent fields).
- Validation findings are represented consistently (so agents can decide to fix vs abort).
- `meminit context` returns repo DocOps configuration deterministically, so an agent does not guess directory layouts, prefixes, or schema paths.

## Problem Statement

Meminit’s purpose is to keep governed documentation consistent, schema-valid, and low-friction over time. In an agentic SDLC, Meminit is invoked programmatically and repeatedly (local loops, CI, and orchestrators). Without a deterministic interface:

- Agent integrations become fragile and expensive to maintain.
- Agents misinterpret failures (operational vs compliance findings), causing unsafe automated actions.
- CI reporting is inconsistent, reducing trust in gating.
- Humans lose time diagnosing parse issues instead of fixing real documentation problems.

This PRD treats the agent interface as a first-class product surface: stable contracts, versioned schemas, and strict determinism rules.

## Why This Adds Production Value

Meminit facilitates better agentic building, development, and maintenance in a project repo/monorepo by making DocOps the "path of least resistance" for both humans and agents:

- Consistency: schema-valid frontmatter and stable `document_id` references make documentation maintainable at scale.
- Predictability: deterministic machine-readable output enables reliable agent loops and CI gating.
- Low friction: agents can bootstrap context and operate safely without bespoke repo heuristics.
- Safety: structured errors and safe-path rules reduce the risk of agents writing outside intended boundaries or leaking sensitive data.
- Traceability: stable IDs + deterministic formatting make long-running maintenance and refactors (status changes, supersession, ownership updates) auditable and automatable.

In short: the agent interface turns Meminit from "a CLI that prints stuff" into a dependable orchestration primitive for DocOps in the AI SDLC.

## Goals

1. Provide a single, documented JSON output envelope for every CLI command (migrated commands).
2. Guarantee structured, machine-parseable operational errors with stable error codes.
3. Publish and maintain versioned JSON Schemas for agent outputs; keep them in sync with implementation via tests.
4. Add `meminit context` for deterministic agent bootstrap in repos and monorepos (namespaces, docs roots, schema path, templates).
5. Ensure determinism (ordering, normalization, stable semantics) so agent orchestration can be tested, diffed, and trusted.
6. Preserve human workflows: existing text output remains the default and stays stable.

## Non-Goals

1. Building a remote API or service.
2. Streaming logs or telemetry in real time.
3. Replacing human-readable text output.
4. Implementing semantic search or RAG in this epic.
5. Changing DocOps rules or governance policy (owned by `docs/00-governance/` and `MEMINIT-STRAT-001`).

## Target Users

- Agent orchestrators that need reliable machine-readable output.
- CI systems that parse Meminit output for reporting or gating.
- Human developers who need plain-English error messages and predictable flags.
- Maintainers of monorepos who need namespace-aware DocOps enforcement (`docops.config.yaml` namespaces).

## Scope

In scope:

- CLI-wide machine interface rules: stdout/stderr contract, exit code semantics, and consistent `--format` handling.
- JSON output envelopes and schema versioning rules.
- Structured operational error responses for all commands, including argument validation and initialization checks.
- `meminit context` for agent bootstrap and monorepo namespace discovery.
- Deterministic output ordering, stable field names, and stable semantics.

Out of scope:

- New repo scanning heuristics (covered by MEMINIT-PRD-004).
- UI, dashboards, or IDE integrations.

## Success Metrics

- Coverage: 100 percent of CLI commands support `--format json` and emit a conforming envelope.
- Error hygiene: 100 percent of operational error paths emit a structured error object with stable codes.
- Determinism: repeated invocations with identical inputs yield identical JSON (modulo explicitly time-based fields).
- Schema discipline: output schema version is declared and validated by tests for migrated commands.
- Orchestration usability: an agent can implement a generic runner that only depends on the shared envelope, not per-command parsing hacks.

## Delivery Status (Phased Rollout)

- Phase complete:
  - `check --format json` emits output schema v2, with normative semantics defined in `docs/20-specs/spec-004-agent-output-contract.md` and `docs/20-specs/agent-output.schema.v2.json`.
- Phase pending (remain on `output_schema_version: "1.0"` or text-only until migrated):
  - `scan`, `index`, `new`, `doctor`, `org` subcommands (`install`, `vendor`, `status`), `migrate-ids`, `fix`, `resolve`, `identify`, `link`, and planned `context`.
- Contract source of truth:
  - v2 (`check`): `docs/20-specs/agent-output.schema.v2.json` + `docs/20-specs/spec-004-agent-output-contract.md`
  - v1 (non-migrated): `docs/20-specs/agent-output.schema.v1.json`

### Compatibility Matrix (Current vs Target)

This matrix exists to help reviewers and implementers understand what an agent can rely on today, and what changes as migration proceeds.

| Command                | Today                              | Target                                  |
| ---------------------- | ---------------------------------- | --------------------------------------- |
| `check`                | `--format json` output schema v2   | v2 for all repos                        |
| `new`                  | text output                        | `--format json` v1 (then migrate to v2) |
| `fix`                  | text output                        | `--format json` v1 (then migrate to v2) |
| `scan`                 | implemented; JSON contract pending | `--format json` v1 (then migrate to v2) |
| `index`                | implemented; JSON contract pending | `--format json` v1 (then migrate to v2) |
| `resolve` / `identify` | implemented; JSON contract pending | `--format json` v1 (then migrate to v2) |
| `doctor`               | implemented; JSON contract pending | `--format json` v1 (then migrate to v2) |
| `context`              | not yet implemented                | `--format json` v1 (then migrate to v2) |

## Key Agent Workflows (Production)

These workflows explain how this interface enables high-quality, low-friction DocOps in real repos.

### Workflow A: Agent Bootstrap (Repo or Monorepo)

1. Agent runs `meminit context --format json`.
2. Agent reads DocOps constraints (namespaces, docs roots, schema path, templates, repo prefixes).
3. Agent caches this context for the session and uses it to decide where to create docs and how to validate.

Outcome: agents stop guessing repo structure and stop hardcoding paths, which reduces breakage and makes orchestration portable across repos.

### Workflow B: Agent Creates a New Governed Doc Safely

1. Agent runs `meminit new <TYPE> <TITLE> --format json` (once migrated).
2. Agent receives the created `document_id` and path in a stable envelope.
3. Agent makes content edits inside that file only, preserving the metadata contract.
4. Agent runs `meminit check --format json` to verify compliance before proposing a PR.

Outcome: new docs are created with correct IDs, correct metadata, correct location, and are validated consistently.

### Workflow C: CI Gating and PR Feedback

1. CI runs `meminit check --format json` (or targeted mode once supported).
2. CI parses a stable output contract, summarizes violations/warnings, and fails deterministically.
3. Optional: CI uses `run_id` to correlate logs and artifacts.

Outcome: DocOps becomes a reliable gate. The whole team trusts that failures mean real violations, not parse flakiness.

### Workflow D: Remediation Loop (Human or Agent)

1. Developer or agent runs `meminit check --format json`.
2. If failures are compliance findings (no operational `error`), the loop proceeds:
   - agent edits docs or invokes `meminit fix --format json` (once migrated) in dry-run to preview.
3. Re-run `meminit check` until green.

Outcome: a stable, deterministic compliance loop suitable for both human iteration and automated agent remediation.

## Functional Requirements (FR)

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

Implementation notes:

- v2 normative contract lives in `docs/20-specs/spec-004-agent-output-contract.md` and `docs/20-specs/agent-output.schema.v2.json`.
- Non-migrated commands remain on v1 until migrated and MUST validate against `docs/20-specs/agent-output.schema.v1.json`.
- During the phased rollout, the implementation MUST declare the correct `output_schema_version` per command and MUST be test-verified.

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

## CLI Contract (Agent Interface Rules)

This section defines behavior that is independent of the JSON envelope shape.

### STDOUT/STDERR

- When `--format json` is used, the JSON envelope MUST be written to STDOUT.
- Human-readable logs, debug output, and tracebacks (if any) MUST be written to STDERR.
- The `--format json` mode MUST NOT emit any additional non-JSON text on STDOUT.

Rationale: agent parsers should be able to treat STDOUT as JSON without heuristics.

### Exit Codes

- Exit code `0` indicates operational success and no gating failures (for commands that gate).
- Exit codes MUST be deterministic.
- For `meminit check`, `success: false` and non-zero exit are valid outcomes when compliance violations exist; this is not an operational error.
- Operational failures (invalid args, unsafe paths, missing config) MUST result in non-zero exit and a structured `error` object in JSON mode.

Note: `MEMINIT-SPEC-004` defines v2 behavior for distinguishing operational errors vs validation-failure outputs for `check`.

### Flag Normalization (Minimum)

- `--format` MUST accept at least: `text` (default), `json`, `md` (if markdown output exists for the command).
- `--no-color` (or equivalent) MUST suppress ANSI formatting in text output and MUST be a no-op for `json`.
- If `--output <path>` is supported, it MUST write the same bytes that would have been emitted to STDOUT.

## Output Contract (Legacy v1 and Migrated v2)

This PRD defines the product requirement; the normative v2 contract lives in `MEMINIT-SPEC-004`. For clarity, this section includes a legacy v1 baseline envelope shape and a migration note for v2.

### JSON Envelope

Legacy v1 (non-migrated commands) MUST return a single JSON object with the following baseline shape when `--format json` is used.

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

### Migrated v2 Note (Current: `check`)

For `meminit check`, v2 output rules are normative and defined by `docs/20-specs/spec-004-agent-output-contract.md`. Key differences from legacy v1 that agents must accommodate during rollout:

- v2 requires `output_schema_version`, `success`, and `run_id` at minimum.
- For `check`, counters and findings are emitted at the top level (not necessarily under `data`).
- `success: false` with populated `violations` is a valid "validation-failure" outcome and does not require a top-level `error` object.

## Command Output Profiles

Each command MUST map its internal result to the standard envelope. The following payloads are required at minimum.

| Command    | Required `data` fields                                                                  |
| ---------- | --------------------------------------------------------------------------------------- |
| `check`    | v1 legacy: `files_checked`, `files_failed`, `violations`, `warnings`                    |
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

Note: during the v2 rollout, `check` is v2-shaped and is governed by `MEMINIT-SPEC-004`. The table above remains the product target for other commands once migrated (with final shapes documented in specs).

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

## `meminit context` (Detailed Requirements)

`meminit context` exists to eliminate agent guesswork. In a monorepo, especially, hardcoding `docs/` and a single prefix leads to incorrect behavior.

### Minimal Payload (Non-Deep)

The minimal context MUST be derived from `docops.config.yaml` and MUST include:

- `docops_version`
- `project_name` (if present)
- `repo_prefix` (top-level default)
- `schema_path`
- `namespaces` (name, docs_root, repo_prefix, and any type-directory mappings)
- `templates` (type -> template path)

### Optional Derived Fields

If inexpensive and deterministic, context MAY also include:

- computed absolute `root` (repo root path)
- resolved absolute paths for schema/templates (in addition to relative paths)
- `initialized` boolean (whether required baseline files exist)

### Deep Mode (`--deep`)

Deep mode MAY add:

- index presence and index path (if index feature exists)
- counts (document count per namespace) if computing them does not require full content parsing

Recommendation: default to non-deep and keep `--deep` explicit to avoid surprising cost and to avoid inadvertently enumerating sensitive paths.

## Implementation Details

### Code Changes

- Add a shared output formatter in `src/meminit/core/services/output_formatter.py` that builds the envelope and enforces ordering.
- Refactor CLI commands in `src/meminit/cli/main.py` to call the shared formatter for JSON output.
- Extend `src/meminit/core/services/output_contracts.py` to include schema constants and version assertions.
- Add a new use case and CLI command `meminit context` under `src/meminit/core/use_cases/context_repository.py` and `src/meminit/cli/main.py`.
- Ensure `meminit fix` supports `--format json` and emits the standard envelope.

### Documentation Changes

- Update `docs/20-specs/spec-004-agent-output-contract.md` to describe the contract and error taxonomy.
- Maintain `docs/20-specs/agent-output.schema.v1.json` and `docs/20-specs/agent-output.schema.v2.json` in sync with code.
- Update any runbooks that describe agent usage to reference the new output contract.

### Testing Requirements

- Add unit tests for the output formatter with stable ordering.
- Add CLI integration tests to verify JSON outputs for every command.
- Add schema validation tests that ensure outputs conform to the correct schema per command (`v1` for non-migrated commands, `v2` for migrated commands).
- Add regression tests for error paths that previously emitted ad-hoc JSON.

## Rollout Plan

1. Implement shared formatter and migrate one command at a time.
2. Add the schema and protocol docs.
3. Update all commands to comply.
4. Run `meminit check` and `pytest` in CI to confirm full compatibility.

## Acceptance Criteria (Ship-Ready Definition)

This PRD is considered implemented when:

1. Every CLI command accepts `--format json` and emits a single-line JSON envelope on STDOUT, with no extra STDOUT noise.
2. Every operational failure emits a structured `error` object with stable `code` and `message` in JSON mode.
3. All migrated commands validate their outputs against the published schema for their `output_schema_version`.
4. `meminit context` exists and returns a deterministic payload derived from `docops.config.yaml` including namespaces (monorepo support).
5. A single generic agent runner can interpret Meminit results using only the shared envelope and schema version.

## Risks and Mitigations

- Risk: mixed stdout output breaks parsers.
  - Mitigation: enforce "JSON on STDOUT only" in integration tests for every command.
- Risk: schema drift between docs and implementation.
  - Mitigation: schema validation tests in CI; treat schema as a contract artifact.
- Risk: monorepo complexity encourages agents to bypass Meminit and hardcode paths.
  - Mitigation: ship `meminit context` early and make it cheap (non-deep default).

## Clarifications Needed (Architect/Human Response Requested)

These questions affect whether the agent interface is maximally stable and low-friction. Options are provided with a recommended choice.

1. Should `command` be REQUIRED in all JSON envelopes?
   - Option A: Required for all commands (recommended).
   - Option B: Optional, infer by payload shape (current v2 allows omission for implicit `check`-shape).
   - Recommendation: make `command` required across all migrated commands in v2. Keep v2 backward compatibility for existing `check` behavior, but converge on always emitting `command` for clarity and tooling simplicity.

2. Should `root` be REQUIRED and always absolute?
   - Option A: Required and absolute (recommended for agent safety).
   - Option B: Optional; omit for privacy or portability.
   - Recommendation: include absolute `root` by default in JSON mode because agents frequently need to compute safe relative paths. If privacy is a concern in CI logs, add a `--redact-paths` flag later rather than removing `root`.

3. Should `timestamp` be present by default in JSON?
   - Option A: Always include (useful for logs).
   - Option B: Omit by default; include only with `--include-timestamp` (recommended).
   - Recommendation: omit by default to maximize determinism; rely on `run_id` for correlation.

4. Should `--output <path>` be standardized for all commands?
   - Option A: Standardize across the CLI (recommended).
   - Option B: Allow command-specific output flags.
   - Recommendation: standardize `--output` to write the same bytes as STDOUT for any format, enabling consistent CI artifacting.

5. What is the stable algorithm/format for `run_id`?
   - Option A: Timestamp-based prefix + random suffix (human-readable).
   - Option B: UUIDv4 (simple, standard).
   - Recommendation: UUIDv4 for simplicity and collision resistance; if human readability is desired, add a secondary `run_label` field later.

## Open Questions (Product/Engineering)

1. Resolved: use phased migration; `check` is v2 while non-migrated commands remain on v1 until migrated.
2. Should `meminit context` include index data by default or require `--deep`? Recommendation: require `--deep`.
3. For `check`, should "warning-only" results return `success: true` by default, with an opt-in strict mode that makes warnings fail? Recommendation: yes; keep strictness configurable to avoid noisy CI in early adoption.
4. Should the v1 legacy envelope be maintained indefinitely, or do we declare a deprecation window? Recommendation: declare a deprecation policy once at least 80 percent of commands are migrated.

## Related Documents

- MEMINIT-STRAT-001
- MEMINIT-PLAN-003
- MEMINIT-PRD-002
- MEMINIT-SPEC-004
