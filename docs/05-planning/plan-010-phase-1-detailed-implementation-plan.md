---
document_id: MEMINIT-PLAN-010
type: PLAN
title: Phase 1 Detailed Implementation Plan
status: Approved
version: '0.5'
last_updated: '2026-04-15'
owner: GitCmurf
docops_version: '2.0'
area: AGENT
description: Detailed implementation plan for MEMINIT-PLAN-008 Phase 1 agent contract
  core.
keywords:
- phase-1
- planning
- capabilities
- contract
related_ids:
- MEMINIT-PLAN-008
- MEMINIT-PLAN-003
- MEMINIT-PRD-005
---

> **Document ID:** MEMINIT-PLAN-010
> **Owner:** GitCmurf
> **Status:** Approved
> **Version:** 0.5
> **Last Updated:** 2026-04-14
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Detailed implementation plan for MEMINIT-PLAN-008 Phase 1 agent contract core.

# PLAN: Phase 1 Detailed Implementation Plan

## Context

MEMINIT-PLAN-008 defines Phase 1 as the first feature-delivery phase after
foundation hardening. Phase 0 is complete, so this phase is now the next
implementation entry point.

The purpose of Phase 1 is to make Meminit self-describing at runtime instead
of requiring agents to rely on repo-local wrappers, stale docs, or implicit
knowledge of the CLI surface.

Adoption note:

- Outside the Meminit repo itself, only one additional repository currently has
  Meminit installed, and that repository exists as an explicit testbed.
- That low installed base means this phase can optimize for a clean contract
  shape rather than carrying broad backward-compatibility baggage.
- Upgrade notes must still be explicit because the testbed is serving as an
  early integration signal.

Breaking-change posture:

- MEMINIT-PLAN-008 established backward compatibility as a general planning
  principle. For Phase 1, that constraint is **relaxed**: the tool is
  pre-alpha with a limited internal user base, and the agent output envelope
  has no external stability promise yet. This plan is free to propose
  breaking changes to the JSON envelope schema (e.g., adding required
  top-level fields, restructuring the `_ENVELOPE_KEY_ORDER`, or bumping
  `output_schema_version`) where it produces a cleaner orchestration
  contract.

## 1. Purpose

Define the detailed implementation steps for Phase 1 of MEMINIT-PLAN-008 so
that the agent contract core can be delivered in a small number of coherent,
reviewable slices.

## 2. Scope

In scope:

- `meminit capabilities --format json`
- optional `--correlation-id` support for agent-facing commands
- `meminit explain <ERROR_CODE> --format json`
- contract and schema updates needed to describe the new runtime surface
- testbed validation against the one external pilot repo

Out of scope:

- index graph enrichment
- protocol drift detection and sync
- work-queue state expansion
- NDJSON streaming or incremental indexing
- semantic search

## 3. Work Breakdown

### 3.1 Workstream A: Contract and Schema Alignment

Problem:

- Phase 1 changes the agent interface surface, but the normative source set is
  currently split across PRD-005, SPEC-006, and the output-contract docs.
- The repo needs one explicit contract decision for whether the current JSON
  envelope is extended in place or versioned forward.
- The current envelope schema (`agent-output.schema.v2.json`) does not define
  `correlation_id` and allows `additionalProperties: true` at the top level,
  which means unknown fields pass validation silently. This weakens the
  contract for agents that depend on strict field discovery.
- The current schema only explicitly declares some command-specific top-level
  keys. Other commands already emit additional top-level fields such as
  `document_count`, so tightening the top-level schema without a full audit
  would create avoidable breakage.

#### 3.1.1 Envelope evolution decision

**Implementation outcome:** Phase 1 shipped `output_schema_version: "3.0"` via a new
`agent-output.schema.v3.json` artifact. The v3 bump was required because the
`root` field became conditional (present for repo-aware commands, absent for
repo-agnostic commands like `capabilities`, `explain`, and `org install`). This was
not anticipated in the original plan below, which proposed extending v2 in place.

The rationale for v2 in place was:
`correlation_id` is additive/optional and wouldn't break existing consumers.
However, the conditional `root` omission changes the envelope shape
meaningfully enough to warrant a version bump so agents can detect the
contract change via `output_schema_version`.

Other Phase 1 changes shipped under v3:
- `correlation_id` added as optional property
- `additionalProperties: false` enforced at top level
- All command-specific top-level fields explicitly declared (check counters, etc.)
- Conditional root omission enforced via schema `if/then` rules

#### 3.1.2 Canonical key ordering update

The `_ENVELOPE_KEY_ORDER` list in `output_formatter.py` must be updated to
include `correlation_id` in a stable position. The proposed order is:

```
output_schema_version, success, command, run_id, correlation_id, timestamp,
root, [command-specific counters], data, warnings, violations, advice, error
```

`correlation_id` appears immediately after `run_id` because they are both
invocation-scoped tracing metadata and should be visually and structurally
adjacent.

Implementation tasks:

1. Update MEMINIT-PRD-005 to confirm Phase 1 scope and sequencing.
2. Audit every JSON-supporting command output and enumerate all
   command-specific top-level fields currently emitted outside the common
   envelope.
3. Add `correlation_id` to `agent-output.schema.v3.json` as an optional
   string property.
4. After the audit is complete, change top-level `additionalProperties` to
   `false` and ensure all command-specific fields are explicitly declared in
   the schema.
5. If the audit reveals unresolved command-surface ambiguity, keep top-level
   strictness permissive for the current release and document the deferment
   explicitly rather than shipping a partially enumerated schema.
6. Update `_ENVELOPE_KEY_ORDER` to include `correlation_id`.
7. Define deterministic ordering rules for all new command payloads.

Acceptance criteria:

1. The normative document set names every new field and command introduced by
   this phase.
2. `agent-output.schema.v3.json` validates `correlation_id` when present
   and either rejects unknown top-level fields after a complete surface audit
   or records an explicit deferment for that tightening step.
3. The `_ENVELOPE_KEY_ORDER` places `correlation_id` after `run_id`.
4. The output ordering rules are explicit enough to be tested directly.

### 3.2 Workstream B: Shared Flag and Envelope Plumbing

Problem:

- `run_id` already exists (generated per-invocation by `get_current_run_id()`
  in `observability.py`, cached in `_current_run_id`), but there is no
  caller-supplied orchestration token.
- Without shared plumbing, individual commands will drift in how they accept
  and echo correlation metadata.

#### 3.2.1 Correlation ID vs Run ID — semantic contract

| Property | `run_id` | `correlation_id` |
| -------- | -------- | ----------------- |
| Owner | Meminit (generated internally) | Caller (passed in externally) |
| Uniqueness | Per CLI invocation | Per orchestration session (may span N invocations) |
| Format | UUIDv4 (validated) | Opaque string, max 128 chars, no whitespace |
| Presence | Always present | Present only when `--correlation-id` is supplied |
| Purpose | Correlate a single Meminit run with its logs | Correlate multiple Meminit runs within an agent workflow |
| Overridable | Yes, via `MEMINIT_RUN_ID` env var | Yes, via `--correlation-id` flag or `MEMINIT_CORRELATION_ID` env var |

#### 3.2.2 Integration into `format_envelope`

- Add `correlation_id: str | None = None` parameter to `format_envelope()`.
- When non-None, include `"correlation_id": value` in the envelope after
  `run_id`.
- When None (caller did not supply it), the key is **omitted entirely** — not
  set to `null`. This preserves envelope compactness for non-orchestrated
  use.
- The same applies to `format_error_envelope()`.

#### 3.2.3 Shared flag registration

- Add `--correlation-id` to the `agent_output_options()` composite decorator
  in `shared_flags.py`. This ensures every command that opts into agent
  output automatically gets the flag.
- Also support `MEMINIT_CORRELATION_ID` as an environment variable fallback,
  following the same precedence pattern as `MEMINIT_RUN_ID`.
- Validation: reject values longer than 128 characters or containing
  whitespace. Emit a structured error if invalid.

Implementation tasks:

1. Add `--correlation-id` option to `agent_output_options()` in
   `shared_flags.py`.
2. Add `MEMINIT_CORRELATION_ID` env var support with CLI flag taking
   precedence.
3. Add `correlation_id` parameter to `format_envelope()` and
   `format_error_envelope()`.
4. Thread the value through all command handlers that use
   `agent_output_options()`.
5. Add input validation (max 128 chars, no whitespace).
6. Ensure JSON-mode stdout remains machine-safe when the flag is used
   alongside `--verbose`.

Acceptance criteria:

1. All commands using `agent_output_options()` accept `--correlation-id`.
2. JSON envelopes include `correlation_id` only when supplied; the key is
   absent otherwise.
3. `MEMINIT_CORRELATION_ID` env var works as a fallback.
4. Invalid correlation IDs produce a structured error envelope.
5. Existing `run_id` behavior remains intact and tested.

### 3.3 Workstream C: Capabilities Command

Problem:

- Agents currently need documentation scraping or repo-specific assumptions to
  discover supported commands, flags, and contract features.
- The `context` command discovers repo-level configuration but not the CLI's
  own feature surface.

#### 3.3.1 Proposed `data` payload schema

`meminit capabilities --format json` returns the standard envelope with a
`data` object containing:

```json
{
  "capabilities_version": "1.0",
  "cli_version": "<semver>",
  "output_schema_version": "2.0",
  "commands": [
    {
      "name": "check",
      "description": "Validate DocOps compliance",
      "supports_json": true,
      "supports_correlation_id": true,
      "agent_facing": true
    }
  ],
  "output_formats": ["text", "json", "md"],
  "global_flags": [
    {
      "flag": "--format",
      "type": "choice",
      "values": ["text", "json", "md"],
      "default": "text",
      "description": "Output format"
    },
    {
      "flag": "--correlation-id",
      "type": "string",
      "description": "Caller-supplied orchestration trace token"
    },
    {
      "flag": "--include-timestamp",
      "type": "boolean",
      "default": false,
      "description": "Include ISO 8601 UTC timestamp in JSON output"
    },
    {
      "flag": "--root",
      "type": "string",
      "description": "Repository root path"
    },
    {
      "flag": "--output",
      "type": "string",
      "description": "Write output to file instead of stdout"
    }
  ],
  "features": {
    "capabilities": true,
    "correlation_id": true,
    "explain": true,
    "graph_index": false,
    "include_timestamp": true,
    "streaming": false,
    "structured_output": true
  },
  "error_codes": ["DUPLICATE_ID", "INVALID_ID_FORMAT", "..."]
}
```

#### 3.3.2 Design constraints

- **Deterministic**: the payload is derived entirely from code-level
  registrations, not from runtime repo state. Two invocations on different
  repos produce identical output (except for `run_id` and `timestamp`).
- **Lightweight**: no filesystem scan, no frontmatter parsing, no index
  load. The command should complete in <100ms.
- **Versioned**: `capabilities_version` is a semver-style string. Agents
  can cache the result and invalidate when `cli_version` changes.
- **Ordered**: `commands` sorted by `name`; `global_flags` sorted by
  `flag`; `output_formats` sorted lexicographically; `error_codes` sorted
  lexicographically; `features` keys sorted lexicographically.
- **Feature flags**: the `features` object uses boolean values to indicate
  whether a contract feature is available in this CLI version. Agents
  can check `features.correlation_id` before attempting to use
  `--correlation-id`. Experimental or future features (e.g., `streaming`,
  `graph_index`) are listed as `false` until shipped.

#### 3.3.3 Per-command metadata

Each entry in the `commands` array includes:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `name` | string | Canonical command name (e.g., `"check"`, `"state set"`) |
| `description` | string | One-line description |
| `supports_json` | boolean | Whether `--format json` is accepted |
| `supports_correlation_id` | boolean | Whether `--correlation-id` is threaded |
| `agent_facing` | boolean | Whether the command is intended for agent orchestration |

Commands that are purely human-oriented (e.g., `install-precommit`) are
still listed but with `agent_facing: false`, so agents know the full surface
without being encouraged to call non-agent commands.

Non-JSON formats:

- `capabilities --format text` may render as a compact table plus a feature
  summary.
- `capabilities --format md` may render as a deterministic Markdown table.
- These human-readable formats are secondary to the JSON contract and do not
  need a separate normative schema.

Implementation tasks:

1. Implement `meminit capabilities` as a new Click command using
   `agent_output_options()`.
2. Build the command registry from Click's own command introspection where
   possible; hardcode `agent_facing` and `description` where introspection
   is insufficient.
3. Derive `error_codes` from the `ErrorCode` enum members.
4. Derive `features` from a code-level feature-flag dict.
5. Add tests that lock down ordering, field presence, and machine-readability.
6. Add a contract test that fails if a new command is added to the CLI
   without a corresponding entry in the capabilities output.

Acceptance criteria:

1. The command is deterministic across repeated runs on different repos.
2. The payload includes every CLI command, all global flags, all error codes,
   and the feature-flag map.
3. Contract tests fail when a supported command or flag changes without the
   capabilities output being updated.
4. `capabilities_version` is present and follows semver.

### 3.4 Workstream D: Explain Command and Error Registry Integration

Problem:

- Error codes exist (31 codes across 5 categories in `ErrorCode` enum), but
  agents do not yet have a machine-readable way to ask what a given code
  means or what remediation is recommended.
- Without `explain`, an agent that receives `DIRECTORY_MISMATCH` must either
  hardcode knowledge of Meminit error semantics or ask the user.

#### 3.4.1 Proposed `data` payload schema

`meminit explain DUPLICATE_ID --format json` returns:

```json
{
  "code": "DUPLICATE_ID",
  "category": "shared",
  "summary": "Two or more documents share the same document_id value.",
  "cause": "A document was copied without updating its document_id, or meminit new was bypassed.",
  "remediation": {
    "action": "Assign a unique document_id to each document. Use meminit new to generate IDs safely.",
    "resolution_type": "manual",
    "automatable": false,
    "relevant_commands": ["meminit new", "meminit check"]
  },
  "spec_reference": "MEMINIT-SPEC-006"
}
```

#### 3.4.2 Explain payload field definitions

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `code` | string | yes | The error code being explained |
| `category` | string | yes | Error category (e.g., `"shared"`, `"check"`, `"new"`, `"templates"`, `"state"`, `"general"`) |
| `summary` | string | yes | One-sentence human-readable summary |
| `cause` | string | yes | Most likely root cause |
| `remediation.action` | string | yes | Recommended fix, written for both human and agent consumption |
| `remediation.resolution_type` | string | yes | One of: `"auto_fixable"` (meminit fix can resolve), `"manual"` (requires human judgment), `"retryable"` (transient; retry may succeed), `"config_change"` (requires configuration modification) |
| `remediation.automatable` | boolean | yes | Whether an agent can resolve this without human input |
| `remediation.relevant_commands` | string[] | yes | CLI commands relevant to diagnosing or fixing the issue |
| `spec_reference` | string | yes | Document ID of the governing spec |

#### 3.4.3 Error registry as single source of truth

The explain metadata is co-located with the `ErrorCode` enum definition in
`error_codes.py` to prevent drift. Each enum member is annotated with a
metadata dict (or a parallel registry dict keyed by enum value). The
`explain` command reads from this registry directly — it does not maintain a
separate data file.

This means adding a new error code to the enum automatically requires
adding its explain metadata, enforced by a test that iterates all
`ErrorCode` members and asserts metadata completeness.

#### 3.4.4 Invalid code handling

When an unrecognized code is passed:

- The command returns `success: false` with error code
  `UNKNOWN_ERROR_CODE` (new code to add to the enum).
- The `data` object contains `{"requested_code": "<input>"}` so the agent
  can log what it attempted.
- The `error` object follows the standard envelope error shape.

#### 3.4.5 Listing all codes

`meminit explain --list --format json` returns a `data` payload containing:

```json
{
  "error_codes": [
    {"code": "CONFIG_MISSING", "category": "shared", "summary": "..."},
    {"code": "DUPLICATE_ID", "category": "shared", "summary": "..."}
  ]
}
```

This gives agents a discovery path for the full error surface, sorted by
`code` lexicographically.

Non-JSON formats:

- `explain --format text` may render as a short labeled block with code,
  category, cause, and remediation.
- `explain --format md` may render as a simple Markdown section or table.
- These formats are operator conveniences; the normative contract remains the
  JSON payload.

Implementation tasks:

1. Implement `meminit explain <ERROR_CODE> --format json` as a new Click
   command using `agent_output_options()`.
2. Build the explain metadata registry co-located with the `ErrorCode` enum.
3. Add `--list` flag for full error code enumeration.
4. Add `UNKNOWN_ERROR_CODE` to the `ErrorCode` enum and MEMINIT-SPEC-006.
5. Add a completeness test: every `ErrorCode` member must have explain
   metadata.
6. Add invalid-code handling that returns a structured error envelope.

Acceptance criteria:

1. Every `ErrorCode` enum member resolves to a complete explain payload.
2. Invalid error codes return `success: false` with `UNKNOWN_ERROR_CODE`.
3. `--list` returns all codes sorted by `code`.
4. The explain registry is the `ErrorCode` enum, not a parallel data file.
5. A test fails if a new `ErrorCode` member is added without explain
   metadata.

### 3.5 Workstream E: Contract-Matrix Tests, Testbed Validation, and Documentation

Problem:

- This phase changes the external contract. The implementation is not complete
  until both local tests and the explicit external testbed confirm the surface.
- There is currently no single test that asserts every JSON-supporting command
  emits a schema-valid envelope. Drift between commands is caught only if a
  command-specific test happens to cover it.

#### 3.5.1 Contract-matrix test specification

A **contract-matrix test** is a parametrized test that iterates over every
CLI command that claims JSON support and asserts:

1. **Envelope validity**: the JSON output validates against
   `agent-output.schema.v2.json`.
2. **Required fields**: `output_schema_version`, `success`, `command`,
   `run_id`, `root`, `data`, `warnings`, `violations`, `advice` are present.
3. **Key ordering**: the top-level keys follow `_ENVELOPE_KEY_ORDER`.
4. **Correlation echo**: when `--correlation-id test-123` is supplied, the
   output includes `"correlation_id": "test-123"`.
5. **Correlation omission**: when `--correlation-id` is not supplied, the
   output does not contain a `correlation_id` key.
6. **stdout/stderr isolation**: JSON output appears on stdout only; no
   interleaved log messages appear on stdout.
7. **Determinism**: two invocations with the same input (minus `run_id` and
   `timestamp`) produce identical output.

The command list is derived from the capabilities output itself: the test
calls `meminit capabilities --format json`, extracts all commands where
`supports_json` is `true`, and parametrizes over them. This creates a
self-enforcing loop — if a new command is added with `supports_json: true`
but fails the matrix, the test fails.

#### 3.5.2 Minimum fixture requirements

| Test scenario | Commands covered | Assertion |
| ------------- | ---------------- | --------- |
| Valid envelope shape | All JSON-supporting commands | Schema validates |
| Correlation echo | All JSON-supporting commands | `correlation_id` present when flag supplied |
| Correlation omission | All JSON-supporting commands | Key absent when flag not supplied |
| Error envelope | At least `check`, `explain` | `success: false` + `error` object validates |
| Capabilities self-consistency | `capabilities` | Every command listed matches the CLI command registry |
| Explain completeness | `explain --list` | Every `ErrorCode` enum member has metadata |
| stdout isolation | All JSON-supporting commands | stdout is valid JSON; stderr is non-empty only for logs |

Implementation tasks:

1. Build the parametrized contract-matrix test as described above.
2. Add representative CLI adapter tests proving stdout and stderr isolation.
3. Validate the new surface in the external testbed repository and capture any
   mismatches before declaring the phase complete.
4. Update the roadmap and parent programme docs if sequencing or assumptions
   change materially during delivery.

Acceptance criteria:

1. The contract-matrix test covers every command where `supports_json` is
   `true` in the capabilities output.
2. The test is self-maintaining: adding a new JSON-supporting command
   automatically includes it in the matrix.
3. The single external testbed can consume the new interface without requiring
   undocumented wrapper behavior.
4. Code, docs, and tests land together.

## 4. Recommended Delivery Sequence

1. Workstream A: Contract and Schema Alignment
2. Workstream B: Shared Flag and Envelope Plumbing
3. Workstream C: Capabilities Command
4. Workstream D: Explain Command and Error Registry Integration
5. Workstream E: Acceptance, Testbed Validation, and Documentation

Reason:

- The contract boundary has to be explicit before command behavior is added.
- Shared plumbing should land before individual command surfaces.
- `capabilities` and `explain` then become additive features on stable
  plumbing.
- The testbed pass is the final readiness gate, not an optional afterthought.

## 5. Exit Criteria for Phase 1

Phase 1 can be considered complete when all of the following are true:

1. `meminit capabilities --format json` returns a versioned, deterministic
   payload including commands, flags, formats, error codes, and feature
   flags as defined in §3.3.1.
2. All commands using `agent_output_options()` accept `--correlation-id`;
   the value is echoed in the envelope when supplied and absent otherwise.
3. `correlation_id` is formally defined in `agent-output.schema.v2.json`
   and the schema rejects unknown top-level fields.
4. `meminit explain <ERROR_CODE> --format json` returns structured
   remediation metadata for every `ErrorCode` enum member; invalid codes
   return a structured error.
5. `meminit explain --list --format json` enumerates all error codes.
6. Every `ErrorCode` member has co-located explain metadata, enforced by a
   completeness test.
7. The contract-matrix test parametrically covers every JSON-supporting
   command for envelope validity, key ordering, correlation echo/omission,
   and stdout/stderr isolation.
8. The normative contract docs (MEMINIT-PRD-005, MEMINIT-SPEC-006) are
   aligned with the shipped behavior.
9. The Meminit repo and the explicit external testbed both validate the new
   contract successfully.

## 6. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-14 | GitCmurf | Initial draft created via `meminit new` |
| 0.2 | 2026-04-14 | Codex | Replaced stub with detailed Phase 1 workstreams, sequencing, and exit criteria |
| 0.3 | 2026-04-14 | Augment Agent | Strengthened plan: added breaking-change posture; specified envelope evolution strategy with `additionalProperties: false`; defined concrete capabilities JSON schema with per-command metadata, feature flags, and deterministic ordering; specified correlation_id vs run_id semantic contract with env var fallback and input validation; detailed explain command payload schema with resolution_type taxonomy and `--list` mode; added contract-matrix test specification with self-maintaining parametrization; tightened exit criteria from 5 generic to 9 specific testable criteria |
| 0.4 | 2026-04-14 | Codex | Added an audit-gated path for top-level schema tightening, documented safe deferment if the command surface is not fully enumerated, and clarified expected text and Markdown behavior for capabilities and explain |
| 0.5 | 2026-04-15 | GitCmurf | Recorded implementation complete: all 5 workstreams delivered; 8 review findings resolved; normative docs updated |
