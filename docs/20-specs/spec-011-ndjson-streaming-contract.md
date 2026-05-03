---
document_id: MEMINIT-SPEC-011
type: SPEC
title: NDJSON Streaming Contract
status: Draft
version: "0.2"
last_updated: 2026-05-03
owner: GitCmurf
docops_version: "2.0"
area: AGENT
description: "Normative NDJSON record contract for streamed Meminit CLI output."
keywords:
  - streaming
  - ndjson
  - agent
  - output
related_ids:
  - MEMINIT-PLAN-014
  - MEMINIT-PRD-005
  - MEMINIT-SPEC-006
  - MEMINIT-SPEC-008
---

# SPEC: NDJSON Streaming Contract

## 1. Purpose

This specification defines the line-delimited JSON output contract used
when a Meminit command is invoked with `--format ndjson`.

The standard v3 envelope remains the contract for `--format json`.
Streaming uses a separate record schema because consumers need to parse
records incrementally without buffering a full envelope.

## 2. Stream Shape

An NDJSON stream is UTF-8 text where each line is one complete JSON
object terminated by `\n`. Streams never include progress text, logs,
or partial JSON on stdout.

Every stream starts with one `header` record and ends with either one
`summary` record or one `error` record.

The supported record types are:

| Record type | Required count | Purpose |
| ----------- | -------------- | ------- |
| `header` | exactly 1 | Stream metadata and run identity |
| `item` | 0..N | Command-specific entity payload |
| `progress` | 0..N | Deterministic coarse progress |
| `summary` | 0 or 1 terminal | Terminal summary with overall success state |
| `error` | 0 or 1 terminal | Failed terminal summary |

## 3. Common Fields

Every record MUST include:

| Field | Type | Requirement |
| ----- | ---- | ----------- |
| `stream_schema_version` | string | MUST be `"1.0"` |
| `record_type` | string | One of the five supported record types |
| `command` | string | Canonical Meminit command name |
| `sequence` | integer | Zero-based, contiguous, monotonically increasing |

`run_id` appears only on the `header` record. Optional
`correlation_id`, `root`, and `started_at` also appear only on
`header`.

`item` records include `kind` and `data`. `summary` records include
`success`, `data`, `warnings`, `violations`, `advice`, and `counts`.
The `success` field is boolean and MUST reflect the command's terminal
status. `error` records include `error.code`, `error.message`, and
optional `error.details`.

All records MUST be serialized with Meminit's canonical JSON writer:
UTF-8, one JSON object per line, stable key ordering, and no extra
stdout text. A repeated run over identical inputs MUST produce a
byte-identical stream after ignoring `header.run_id` and any requested
`header.started_at` timestamp.

`progress` records, when emitted, MUST use deterministic boundaries:
`index` and `scan` emit only after every 100 processed items, and
`context --deep` emits only after every 50 processed documents. A
producer MAY omit progress records entirely when the total work is
small or unknown.

## 4. Command Catalogues

Phase 5 defines streaming for these command shapes:

| Command | Supported invocation | Item kinds |
| ------- | -------------------- | ---------- |
| `index` | `meminit index --format ndjson` | `node`, `edge` |
| `scan` | `meminit scan --format ndjson` | `file`, `suggestion` |
| `context` | `meminit context --deep --format ndjson` | `namespace`, `document_type`, `document` |

For `scan`, each `file` item MUST correspond to one Markdown file discovered
under the active docs root. The item payload MUST include a repo-relative
`path`, and SHOULD include namespace and governance metadata when available.
Namespace summary rows are not valid `file` items.

Item ordering is part of the contract:

- `index` emits `node` records sorted by `document_id`, then `edge`
  records sorted by `source`, `target`, and `type`.
- `scan` emits `file` records sorted by `path`, then `suggestion`
  records sorted by `severity`, `code`, and `path`.
- `context --deep` emits `namespace` records sorted by `name`,
  `document_type` records sorted by `type`, and `document` records
  sorted by `document_id` and `path`.

`meminit index --explain-cache --format ndjson` MUST fail with
`STREAM_UNSUPPORTED_FORMAT`; the cache-explanation submode remains
JSON-only.

`meminit context --format ndjson` without `--deep` MUST fail with
`STREAM_UNSUPPORTED_FORMAT`.

Commands that do not advertise `supports_ndjson: true` in
`meminit capabilities --format json` MUST fail with
`STREAM_UNSUPPORTED_FORMAT` when invoked with `--format ndjson`.

## 5. Error Semantics

On operational failure after a stream has started, Meminit writes a
terminal `error` record, flushes stdout, and exits with the exit code
mapped from `error.code`.

Some commands may complete their stream with a terminal `summary`
record whose `success` field is `false`. This is reserved for cases
where the stream is fully materialized but the command's overall result
is unsuccessful, such as a graph index run with error-severity state
warnings.

`STREAM_PRODUCER_FAILED` is reserved for unexpected producer
exceptions. `STREAM_INTERRUPTED` is reserved for signal-driven
termination. Structured logs and tracebacks, when available, are
stderr-only and MUST NOT appear in stdout.

## 6. Schema Artifact

The normative schema is committed in two byte-identical copies:

- `src/meminit/core/assets/agent-output.stream.schema.v1.json`
- `docs/20-specs/agent-output.stream.schema.v1.json`

Both copies use `additionalProperties: false` on each concrete record
definition so agents can reject drift early.

## 7. Version History

| Version | Date | Author | Notes |
| ------- | ---- | ------ | ----- |
| 0.1 | 2026-05-03 | Codex | Initial NDJSON stream shape and supported command set |
| 0.2 | 2026-05-03 | Codex | Added deterministic serialization, progress boundaries, and command item ordering rules |
