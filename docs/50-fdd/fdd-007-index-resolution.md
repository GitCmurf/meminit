---
document_id: MEMINIT-FDD-007
type: FDD
title: Index + Resolution Helpers (meminit index/resolve/identify/link)
status: Draft
version: 0.6
last_updated: 2026-04-18
owner: GitCmurf
docops_version: 2.0
---

# FDD: Index + Resolution Helpers

## Feature Description

Provide a stable, machine-readable index artifact and a small set of commands to resolve IDs and paths.

## User Value

- Makes document IDs resolvable and linkable without scanning each time.
- Enables downstream tools (agents, pipelines) to consume a deterministic artifact.

## Functional Scope (v0.1)

- Command: `meminit index`
  - Builds a repository-level index artifact at `index_path` (defaults to `docs/01-indices/meminit.index.json`).
  - Index artifact includes `output_schema_version` for stable orchestration contracts.
  - Persisted index content is deterministic and excludes runtime-only metadata such as `run_id`, absolute `root`, and wall-clock generation timestamps.
  - Includes `document_id`, path, type, title, status for each governed doc.
  - In monorepo mode (`namespaces`), index entries also include `namespace` and `repo_prefix`.
  - Excludes WIP and explicitly excluded paths.
- Command: `meminit resolve <DOCUMENT_ID>`
  - Resolves a document_id to a repo-relative path.
  - Errors if the index is missing or ID not found.
- Command: `meminit identify <PATH>`
  - Resolves a repo-relative path to document_id.
  - Errors if the index is missing or path is not governed.
- Command: `meminit link <DOCUMENT_ID>`
  - Prints a Markdown link using the resolved path (example omitted to avoid fake links in docs).

## Phase 2 Graph Enhancement

The index artifact was upgraded from a flat document inventory to a graph-grade agent artifact.

### Artifact shape

- `index_version: "1.0"` with `graph_schema_version: "1.0"`.
- The persisted index artifact uses an envelope-like structure to maintain
  consistency with CLI outputs while ensuring a stable consumer contract.
  It includes:
  - `output_schema_version: "2.0"` (stable version for the persisted artifact)
  - `success: true`
  - `command: "index"`
  - `data`: containing `nodes`, `edges`, and counters.
  - `warnings`, `violations`, `advice`: diagnostic arrays.
- The normative schema for the persisted artifact is defined in
  `docs/20-specs/index-artifact.schema.json`.
- Generated-view choices such as catalog filenames are operational metadata
  and are not persisted in the canonical index artifact.
- The `documents` array was renamed to `nodes`. `document_count` is retained alongside new `node_count` and `edge_count`.
- New `edges` array containing directed relationships between documents.
- New `advice` array for non-binding recommendations (e.g., `GRAPH_RELATED_ID_ASYMMETRY`).
- `node_count` and `edge_count` are the authoritative counters going forward.
  `document_count` is retained only as a compatibility counter for older
  consumers and must always mirror `node_count` in generated indexes.

### Edge schema

| Field      | Type   | Required | Description |
| ---------- | ------ | -------- | ----------- |
| `source`   | string | yes      | Document ID of the source node |
| `target`   | string | yes      | Document ID of the target node |
| `edge_type`| string | yes      | `"related"`, `"supersedes"`, or `"references"` |
| `guaranteed`| bool  | yes      | `true` for frontmatter-derived edges, `false` for body-link scanned |
| `context`  | string | no       | Provenance: `"frontmatter.related_ids"`, `"frontmatter.superseded_by"`, `"body.markdown_link"` |

When the same logical edge `(source, target, edge_type)` is discovered from
multiple sources, Meminit persists a single edge and keeps the strongest
provenance deterministically: frontmatter-derived (`guaranteed: true`)
metadata wins over body-link scanned metadata.

Edge direction conventions:

- `related`: source = document declaring `related_ids`, target = related document.
- `supersedes`: source = successor document, target = superseded document.
- `references`: source = document containing the link, target = linked document.

### Graph integrity checks

Six checks run during `meminit index` build:

| Code | Severity | Channel | Description |
| ---- | -------- | ------- | ----------- |
| `GRAPH_DUPLICATE_DOCUMENT_ID` | fatal | violations | Same `document_id` in multiple files |
| `GRAPH_SUPERSESSION_CYCLE` | fatal | violations | Supersedes chain forms a cycle |
| `GRAPH_DANGLING_RELATED_ID` | warning | warnings | `related_ids` target not in index |
| `GRAPH_DANGLING_SUPERSEDED_BY` | warning | warnings | `superseded_by` target not in index |
| `GRAPH_SUPERSESSION_STATUS_MISMATCH` | warning | warnings | `superseded_by` set but status is not `Superseded` (or vice versa) |
| `GRAPH_RELATED_ID_ASYMMETRY` | info | advice | A lists B in `related_ids` but B does not list A |

Fatal errors halt the build and are surfaced in the CLI JSON envelope `violations` array. Non-fatal checks are skipped when fatal errors exist.

### CLI envelope

- Successful index: `nodes`, `edges`, `warnings`, and `advice` are all populated in the JSON envelope.
- Filtered output (`--status`, `--impl-state`): on-disk index remains canonical (unfiltered); stdout edges are filtered to the visible node subset.
- Fatal graph errors: surfaced in `violations` alongside `error` in the JSON envelope. When fatal violations are present, the `warnings` and `advice` arrays are not guaranteed complete (they may be omitted or partial) — downstream consumers must not assume completeness.

## Non-goals (v0.1)

- Deduplication or conflict resolution for duplicate IDs.
- Index-based link validation inside `meminit check` (future).
- Custom index formats or multiple index files.
- Migrating legacy document IDs (handled by `meminit migrate-ids`).
- Graph query helpers (traverse, shortest-path, neighborhood) — deferred to a future phase.

## Implementation Notes

- Use case: `src/meminit/core/use_cases/index_repository.py`
- Use cases: `resolve_document.py`, `identify_document.py`
- CLI: `meminit index|resolve|identify|link` in `src/meminit/cli/main.py`
- Runtime correlation metadata remains available in CLI JSON output (`meminit index --format json`) rather than the committed index artifact.
- Generated side views (`catalogue.md`, custom catalog names, `kanban.md`,
  `kanban.css`) are tracked operationally by Meminit-generated file markers and
  cleaned up outside the canonical index artifact.

## Tests

- Index generation includes governed docs and excludes WIP.
- Resolve returns correct path for known IDs.
- Identify returns correct ID for known paths.
- Edge extraction: `related`, `supersedes`, and `references` edges extracted correctly with `guaranteed` flag and `context` provenance.
- Graph validation: duplicate document IDs, supersession cycles, dangling targets, status mismatches, and related-id asymmetry all produce correct diagnostics.
- Byte identity: two index runs on the same content produce byte-identical JSON.
- Diagnostic arrays: persisted `warnings` and `advice` are canonically sorted before serialization, so discovery order does not change artifact bytes.
- Timing budget: a 500-document graph build stays within the Phase 2 bound.
- External testbed: the acceptance suite in `../AIDHA` passes against the current Meminit binary.
- Fatal errors halt build and surface in CLI JSON envelope `violations` array.
- Filtered output: stdout edges reference only visible nodes; on-disk index remains canonical.
