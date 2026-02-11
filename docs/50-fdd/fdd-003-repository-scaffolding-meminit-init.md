---
document_id: MEMINIT-FDD-003
type: FDD
title: Repository Scaffolding (meminit init)
status: Draft
version: 0.1
last_updated: 2025-12-14
owner: GitCmurf
docops_version: 2.0
---

# FDD: Repository Scaffolding (meminit init)

## Feature Description

Initialize a repository with the baseline DocOps directory structure, configuration, templates, and schema required for a “greenfield” repo to run `meminit check` successfully.

## User Value

- Makes bootstrapping new repos quick and consistent.
- Ensures baseline compliance assets exist before any docs are added.

## Functional Scope (v0.1)

- Create `docs/` directory structure (idempotent).
- Create root `docops.config.yaml` if missing, including:
  - `repo_prefix` (derived from directory name)
  - `docops_version`
  - `docs_root`, `schema_path`, `excluded_paths` (defaults that `meminit check/new/fix` will use)
  - `type_directories` (default type → directory mapping; user-tunable for brownfield repos)
  - template mappings
- Create minimal templates under `docs/00-governance/templates/` if missing.
- Create `docs/00-governance/metadata.schema.json` if missing.
- Create root `AGENTS.md` if missing (with correct template paths).

## Non-goals (v0.1)

- Generating repo-specific governance docs beyond the baseline schema/templates.
- Installing pre-commit hooks or CI workflows automatically.

## Implementation Notes

- Use case: `src/meminit/core/use_cases/init_repository.py`
- Idempotent behavior: does not overwrite existing files.

## Tests

- Unit tests assert directory and file scaffolding and idempotency.
