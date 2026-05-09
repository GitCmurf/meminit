---
document_id: MEMINIT-FDD-014
type: FDD
title: Streaming Emitter and Incremental Index
status: Approved
version: "1.1"
last_updated: 2026-05-09
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

`scan` emits Markdown file records followed by suggestion records. The
summary includes scan counts and a configuration preview.

`context --deep` emits document type, namespace, and document metadata.
The non-deep mode remains bounded output and deliberately rejects
`--format ndjson`.

`scan` and `context --deep` use core-owned producers that can emit their
first stream item before the full JSON-equivalent report is assembled. The
`index` producer remains correctness-first: node and edge items are emitted
only after graph validation, state derivation, cache handling, and artifact
writes have produced a valid index result.

## 5. Cache Surface

Phase 5 reserves the repo-local cache root `.meminit/cache/index/`.
The user-facing index command exposes:

- `--no-cache`
- `--rebuild-cache`
- `--explain-cache`

`--no-cache` and `--rebuild-cache` are mutually exclusive and fail
with `INVALID_FLAG_COMBINATION`. When either cache-control flag is
used, Meminit clears `.meminit/cache/index/` before the current full
rebuild so stale fragments do not linger across runs.
`--explain-cache` reports the current manifest summary as a standard
v3 JSON envelope without rebuilding the index.
`--explain-cache` cannot be combined with `--no-cache` or
`--rebuild-cache`; those combinations fail with
`INVALID_FLAG_COMBINATION` before any cache mutation occurs.

The index cache now writes a deterministic manifest plus per-document
node fragments. `meminit index` uses that manifest by default:
unchanged files whose size and mtime match the previous manifest reuse
their cached node payload without rereading the governed document bytes;
edges are rebuilt deterministically from the merged node set; added and
changed files are recomputed; removed files are dropped.

The manifest records Meminit version, index version, config hash,
schema hash, project-state hash, and sorted file fingerprints. Any
global-context change falls back to a full rebuild and rewrites the
cache. Corrupt node entries emit `CACHE_ENTRY_INVALID` warnings and are
recomputed without failing the run.

`--no-cache` clears the repo-local index cache and performs a cold full
rebuild without repopulating the cache. `--rebuild-cache` clears the
cache, performs a full rebuild, and repopulates the cache. `meminit
index --explain-cache --format json` reports manifest status without
triggering a rebuild.

## 6. Safety Constraints

Output path writes go through the existing path-safety checks. Logs
remain stderr-only. NDJSON stdout is reserved exclusively for records
conforming to MEMINIT-SPEC-011.

Cache files must never be committed. Operators can delete
`.meminit/cache/` at any time to force a cold rebuild.

## 7. Version History

| Version | Date | Author | Notes |
| ------- | ---- | ------ | ----- |
| 0.1 | 2026-05-03 | Codex | Initial shared streaming emitter and cache-control surface design |
| 0.2 | 2026-05-03 | Codex | Clarified shipped cache boundary and documented that the incremental rebuild engine remains unimplemented |
| 1.0 | 2026-05-06 | Codex | Documented the shipped incremental index cache, manifest context, corruption recovery, and cache-control semantics |
| 1.1 | 2026-05-09 | Codex | Documented core-owned producer first-item laziness for scan and deep context, plus the remaining index limitation. |
