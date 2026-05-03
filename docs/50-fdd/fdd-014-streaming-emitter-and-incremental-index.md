---
document_id: MEMINIT-FDD-014
type: FDD
title: Streaming Emitter and Incremental Index
status: Draft
version: "0.1"
last_updated: 2026-05-03
owner: GitCmurf
docops_version: "2.0"
area: AGENT
description: "Feature design for Phase 5 NDJSON streaming and repo-local index cache surfaces."
keywords:
  - streaming
  - ndjson
  - index
  - cache
related_ids:
  - MEMINIT-PLAN-014
  - MEMINIT-SPEC-011
  - MEMINIT-SPEC-006
---

# FDD: Streaming Emitter and Incremental Index

## 1. Feature Summary

Phase 5 adds an opt-in NDJSON output path for large Meminit command
outputs. The implementation keeps stdout writes in a dedicated CLI
adapter module, while command use cases continue to produce structured
data.

The first shipped streaming commands are:

- `meminit index --format ndjson`
- `meminit scan --format ndjson`
- `meminit context --deep --format ndjson`

## 2. Module Boundary

`src/meminit/cli/streaming.py` owns:

- `StreamEmitter`
- `SummaryPayload`
- `StreamingProducer`
- `streaming_output_handler`

No core use case writes NDJSON directly. The CLI command gathers or
produces command data, passes entity records to `StreamEmitter`, and
returns a `SummaryPayload` for the terminal `summary` record.

## 3. Record Emission

The emitter is stateful for one command invocation only. It maintains
the `sequence` counter, writes canonical sorted-key JSON, appends a
single LF, and flushes after every record.

The emitter enforces terminal-record ordering. Calling `emit_item`,
`emit_progress`, or `emit_summary` after a terminal record raises in
tests and prevents silent stream drift.

## 4. Command Producers

`index` emits document nodes before graph edges. The summary includes
the persisted artifact path, index version, and node/edge counts.

`scan` emits configured namespace/file-like inventory records followed
by suggestion records. The summary includes scan counts and a
configuration preview.

`context --deep` emits namespaces and document type metadata. The
non-deep mode remains bounded output and deliberately rejects
`--format ndjson`.

## 5. Cache Surface

Phase 5 reserves the repo-local cache root `.meminit/cache/index/`.
The user-facing index command exposes:

- `--no-cache`
- `--rebuild-cache`
- `--explain-cache`

`--no-cache` and `--rebuild-cache` are mutually exclusive and fail
with `E_INVALID_FILTER_VALUE`. When either cache-control flag is
used, Meminit clears `.meminit/cache/index/` before the current full
rebuild so stale fragments do not linger across runs.
`--explain-cache` reports the current manifest summary as a standard
v3 JSON envelope without rebuilding the index.

The initial cache reporting contract is intentionally conservative:
the persisted index artifact remains the source of truth, and the
stream summary exposes rebuild metadata without changing the artifact
schema.

## 6. Safety Constraints

Output path writes go through the existing path-safety checks. Logs
remain stderr-only. NDJSON stdout is reserved exclusively for records
conforming to MEMINIT-SPEC-011.

Cache files must never be committed. Operators can delete
`.meminit/cache/` at any time to force a cold rebuild.
