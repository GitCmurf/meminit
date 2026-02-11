---
document_id: MEMINIT-FDD-006
type: FDD
title: Pre-commit Installer (meminit install-precommit)
status: Draft
version: 0.1
last_updated: 2025-12-22
owner: GitCmurf
docops_version: 2.0
---

# FDD: Pre-commit Installer (meminit install-precommit)

## Feature Description

Provide a safe, idempotent installer that adds a local pre-commit hook to run `meminit check`.

## User Value

- Encourages local enforcement before CI.
- Reduces friction for teams adopting Meminit in existing repos.

## Functional Scope (v0.1)

- Command: `meminit install-precommit --root .`
- Behavior:
  - Creates `.pre-commit-config.yaml` if missing.
  - Appends a **local** hook if config exists.
  - Detects and skips if meminit hook is already present.
  - Refuses to modify invalid YAML.
- Hook defaults:
  - `entry`: `meminit check --root .`
  - `language`: `system`
  - `pass_filenames`: false
  - `always_run`: false (hook only runs when files match the docs root regex)
  - `files`: `^{docs_root}/`

## Non-goals (v0.1)

- Managing pre-commit installation (`pre-commit install`).
- Editing user comments or preserving YAML formatting.

## Implementation Notes

- Use case: `src/meminit/core/use_cases/install_precommit.py`
- CLI: `meminit install-precommit` in `src/meminit/cli/main.py`

## Tests

- Creates config when missing.
- Appends when config exists.
- Skips when hook already installed.
- Respects custom `docs_root` in `docops.config.yaml`.
