---
document_id: MEMINIT-FDD-008
type: FDD
title: ID Migration Assistant (meminit migrate-ids)
status: Draft
version: 0.1
last_updated: 2025-12-26
owner: GitCmurf
docops_version: 2.0
---

# FDD: ID Migration Assistant (meminit migrate-ids)

## Feature Description
Provide a safe, deterministic assistant to migrate legacy `document_id` values into Meminit’s canonical `REPO-TYPE-SEQ` format.

## User Value
- Reduces error-prone manual edits during brownfield adoption.
- Produces a consistent ID scheme required for `meminit check` green.
- Can optionally rewrite internal references to old IDs.

## Functional Scope (v0.1)
- Command: `meminit migrate-ids`
- Default mode is **dry-run**.
- When applied (`--no-dry-run`):
  - rewrites frontmatter `document_id`
  - rewrites visible metadata block “Document ID” line when the `<!-- MEMINIT_METADATA_BLOCK -->` marker is present
  - updates the first H1 if it contains the old ID
- Optional: `--rewrite-references` to replace old IDs in the body text (conservative word-boundary replacement).

## Safety Guarantees
- Does not write by default.
- Only acts on governed Markdown under `docs_root/` (excluding WIP/excluded paths).
- Skips files missing frontmatter or missing `type`/`document_id` instead of guessing.

## Non-goals (v0.1)
- Rewriting Markdown filesystem links.
- Resolving ID conflicts automatically.
- Migrating IDs outside `docs_root/`.

## Implementation Notes
- Use case: `src/meminit/core/use_cases/migrate_ids.py`
- CLI: `meminit migrate-ids` in `src/meminit/cli/main.py`

## Tests
- Migrates a legacy ID and updates frontmatter + metadata block + H1.
- Optional body reference rewriting.
