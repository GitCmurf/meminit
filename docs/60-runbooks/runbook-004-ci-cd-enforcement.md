---
document_id: MEMINIT-RUNBOOK-004
type: RUNBOOK
docops_version: 2.0
last_updated: 2025-12-30
status: Draft
title: CI/CD Enforcement for Meminit Compliance
owner: GitCmurf
version: 0.4
---

# Runbook: CI/CD Enforcement for Meminit Compliance

## Goal

Block merges when governed documentation is non-compliant, using `meminit check` as a CI gate.

## Non-goals

- Running `meminit fix` in CI (CI should not mutate repositories).
- Enforcing compliance for explicitly excluded WIP docs (e.g., `WIP-*`).

## Preconditions

- Repository has `docops.config.yaml` (or accepts defaults) and a valid metadata schema file at `schema_path`.
- The CI environment can install Python dependencies (network access typical for hosted CI).

## Recommended GitHub Actions workflow (enforcement gate)

In `.github/workflows/ci.yml`:

- Install using packaging metadata (`pip install -e ".[dev]"` or `pip install ".[dev]"`) so installed-package behavior is tested.
- Run:
  - `meminit doctor --root .` (preflight; fails on repo-level errors)
  - `meminit check --root .` (enforcement; fails on any violations; scans all configured namespaces if `namespaces` is set)
- Set explicit minimal permissions:
  - `permissions: read-all` at workflow level

## Pre-commit enforcement (local)

Use `meminit install-precommit` to add a local pre-commit hook that runs `meminit check`.

What it does:

- Creates or updates `.pre-commit-config.yaml`.
- Adds a **local** hook that runs `meminit check --root .`.
- Limits hook triggering to files under the configured docs root.

Command:

```bash
meminit install-precommit --root .
```

Notes:

- If you already have a `.pre-commit-config.yaml`, the installer appends a local hook.
- If the file is invalid YAML, the installer will refuse to modify it.

## Index + resolution helpers (local)

These commands build and use the DocOps index artifact to resolve IDs and paths.

Commands:

```bash
meminit index --root . --format md
meminit resolve MEMINIT-ADR-001 --root .
meminit identify docs/45-adr/adr-001-example.md --root .
meminit link MEMINIT-ADR-001 --root .
```

Notes:

- `meminit index` writes the index to `index_path` (default: `docs/01-indices/meminit.index.json`).
- `resolve` and `identify` require the index to exist; run `meminit index` first.
  - For orchestration, `meminit index --format json` includes `output_schema_version`.

### Trigger policy (recommended)

- Default to PR-only enforcement (avoid duplicate runs and unexpected compute cost).
- Add a `push` trigger for `main` only if your workflow includes direct pushes or automation that bypasses PRs.

## Existing AGENTS.md merge guidance (brownfield)

If your repo already has an `AGENTS.md`, avoid replacing it. Merge by **adding** a Meminit section:

1. Keep existing repo-specific guidance intact.
2. Add a “Meminit DocOps” subsection that links to:
   - `docops.config.yaml` (config)
   - `docs/00-governance/metadata.schema.json` (schema)
   - Local commands: `meminit doctor`, `meminit check`, `meminit fix --dry-run`
3. If there are conflicts between local rules and Meminit rules, document the precedence and update `docops.config.yaml` so Meminit matches reality.

Minimal merge snippet (example):

```md
## Meminit DocOps

- Follow `docops.config.yaml` for docs layout and schema.
- Before PR: run `meminit doctor --root .` and `meminit check --root .`.
- Use `meminit fix --root . --dry-run` to preview safe auto-fixes.
```

## Branch protection (GitHub)

Configure branch protection rules for `main`:

- Require status checks to pass before merging.
- Select the CI job(s) that run enforcement.

### Step-by-step (GitHub UI)

1. Repo → **Settings** → **Branches**.
2. Under **Branch protection rules**, click **Add rule**.
3. **Branch name pattern**: `main`.
4. Enable **Require a pull request before merging**.
5. Enable **Require status checks to pass before merging**.
6. In the checklist of status checks, select:
   - `docops` (runs `meminit doctor` and `meminit check`)
   - `python` (lint + tests)
7. Save.

Notes:

- The selectable check names come from the workflow job `name:` fields (in `.github/workflows/ci.yml`).
- If the check names don’t show up yet, trigger a PR/push once so GitHub learns the available checks.

## Fork PR policy (security-first)

- Use the `pull_request` event (not `pull_request_target`) for enforcement jobs.
- Do not expose secrets to forked PRs.
- Keep token permissions minimal (read-only is enough for `meminit` and tests).
- If a privileged job is ever needed (e.g., release publish), run it only on trusted branches or manual approval.

## Local developer workflow

When CI fails:

1. Run `meminit doctor --root .` to confirm the repo is configured correctly.
2. Run `meminit check --root .` to list violations.
3. Optionally run `meminit fix --root . --dry-run` to preview safe auto-fixes.

## Brownfield adoption checklist (existing repo)

1. Add `meminit` to the toolchain (package install and/or CI install step).
2. Add/adjust `docops.config.yaml` to match existing `docs/` layout (especially `docs_root`, `schema_path`, and any type directory mappings).
3. Run `meminit scan --root .` to get a migration plan and suggested `type_directories` overrides.
4. Decide how to handle temporary documents:
   - Default behavior excludes `WIP-` prefixed docs under `docs/` via `excluded_filename_prefixes`.
   - Add additional prefixes via `excluded_filename_prefixes` if needed.
5. Introduce CI enforcement only after a baseline clean-up (or after intentionally excluding legacy docs until they’re migrated).
