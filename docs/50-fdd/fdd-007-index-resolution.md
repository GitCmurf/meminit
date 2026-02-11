---
document_id: MEMINIT-FDD-007
type: FDD
title: Index + Resolution Helpers (meminit index/resolve/identify/link)
status: Draft
version: 0.3
last_updated: 2025-12-29
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

## Non-goals (v0.1)

- Deduplication or conflict resolution for duplicate IDs.
- Index-based link validation inside `meminit check` (future).
- Custom index formats or multiple index files.
- Migrating legacy document IDs (handled by `meminit migrate-ids`).

## Implementation Notes

- Use case: `src/meminit/core/use_cases/index_repository.py`
- Use cases: `resolve_document.py`, `identify_document.py`
- CLI: `meminit index|resolve|identify|link` in `src/meminit/cli/main.py`

## Tests

- Index generation includes governed docs and excludes WIP.
- Resolve returns correct path for known IDs.
- Identify returns correct ID for known paths.
