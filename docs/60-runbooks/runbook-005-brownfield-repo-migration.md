---
document_id: MEMINIT-RUNBOOK-005
type: RUNBOOK
docops_version: 2.0
last_updated: 2025-12-30
status: Draft
title: Brownfield Repository Migration (Adopt Meminit)
owner: GitCmurf
version: 0.4
---

# Runbook: Brownfield Repository Migration (Adopt Meminit)

## Goal

Adopt Meminit in an existing repo by migrating documentation into a compliant state with minimal disruption.

## Safety principles

- Prefer **read-only analysis first** (`scan`, `check`).
- Use `fix --dry-run` before any write.
- Commit in small, reviewable steps.
- Keep WIP/scratch docs excluded from governance until promoted.

## Preconditions

- You have a clean git working tree (recommended).
- You can run `meminit` locally.
- If using Codex, the repo skill `meminit-docops` is available (see MEMINIT-RUNBOOK-006).

## Step-by-step procedure

### 0) Safety checkpoint (strongly recommended)

Before any write operations (especially `fix --no-dry-run`):

1. Create a new branch for migration.
2. Make a “safety commit” (or tag) so you can revert cleanly.

### 1) Decide governance boundary (what is governed vs WIP)

1. Decide if all of `docs/` should be governed.
2. Decide which prefixes or directories are excluded (defaults include `WIP-`).
3. Record the policy in `docops.config.yaml` (`excluded_paths`, `excluded_filename_prefixes`).

Notes:

- Current Meminit scope is **one docs root** (`docs_root`), defaulting to `docs/`.
- Markdown outside `docs_root/` (e.g., `specs/` at repo root) is not governed by `meminit check` unless you move it under `docs_root/` or change `docs_root`.

Monorepo note:

- If your repo has multiple documentation roots (e.g., `packages/*/docs` or `apps/*/docs`), configure **namespaces** so Meminit can govern them explicitly.
- Start small: govern central docs first, then add additional namespaces for package/app docs when ready.

### 1b) Monorepo adoption (namespaces) — high-DevEx “do this, not that”

If your repo is a monorepo, this is the part future-you will thank present-you for doing deliberately.

#### What a “namespace” means (Meminit model)

A namespace is a governed documentation root with:

- a `docs_root` (what gets scanned/governed)
- a `repo_prefix` (what IDs must start with in that docs_root)

Meminit is intentionally **tool-agnostic** here. It does not care whether you use `pnpm`, `nx`, `turbo`, etc. The repo layout is what matters.

#### What Meminit will enforce (important)

- In monorepo mode, `meminit check` enforces `ID_PREFIX`:
  - If a file lives under namespace docs root `X/`, its `document_id` MUST start with that namespace’s `repo_prefix-`.
- `meminit fix` and `meminit new` can be constrained with `--namespace` for safety.
- Each configured namespace docs root is part of the compliance boundary:
  - If you add `packages/<pkg>/docs` as a namespace, those docs must be able to validate against your schema.
  - Common failure mode in pilots: package docs roots exist, but the schema/templates are missing or not committed. Fix by vendoring org standards (`meminit org vendor`) or ensuring a committed `schema_path` is valid for all namespaces.
  - Another common failure mode: `packages/<pkg>/docs/README.md` exists (common in monorepos) but is not DocOps-compliant. Choose one:
    - Exclude it (treat as non-governed) via `excluded_paths` (or keep that subtree out of namespaces until ready), or
    - Make it governed by adding frontmatter and moving it into an appropriate type directory (e.g., `70-devex/` as `REF`), or
    - Convert it into a fully compliant doc in-place (add frontmatter; accept that it must pass schema).

If you don’t want separate prefixes per package/app, you can still use namespaces: just set the same `repo_prefix` for multiple namespaces.

#### Recommended staging strategy (avoid mass churn)

1. Add a single namespace for your central docs first (usually `docs/`).
2. Get `meminit doctor` and `meminit check` green for that namespace.
3. Add package/app namespaces **one at a time**:
   - run `scan` → inspect suggested namespaces
   - add one namespace block
   - run `doctor` / `check` / `fix --dry-run`
   - commit

This avoids “giant rename PR” trauma and makes it obvious which subtree introduced which violations.

#### Suggested config shape (template)

This is a safe baseline you can copy/paste and then edit:

```yaml
project_name: YOUR_REPO_NAME
docops_version: "2.0"

# Recommended in monorepos: keep the index out of any specific docs tree.
index_path: .meminit/meminit.index.json

# You may share a single schema across namespaces (recommended early) by pointing all namespaces at one schema_path.
schema_path: docs/00-governance/metadata.schema.json

namespaces:
  - name: root
    repo_prefix: YOURREPO
    docs_root: docs

  - name: some-package
    repo_prefix: SOMEPKG
    docs_root: packages/some-package/docs
```

#### “Codex prompt” template (delegate safely)

If you’re using Codex (or another agent) to implement the namespace config, give it a bounded, explicit task:

```text
Task: configure Meminit monorepo namespaces for this repo.

Constraints:
- Do not modify document bodies unless required for compliance.
- Prefer staged adoption: central docs first, then package/app docs one namespace at a time.
- Use meminit read-only commands first (scan/check/doctor).

Steps:
1) Run `meminit scan --root . --format md` and capture `Suggested Namespaces`.
2) Propose a `docops.config.yaml` change that adds `namespaces` and (optionally) `index_path: .meminit/meminit.index.json`.
3) After config is updated, run:
   - `meminit doctor --root . --format md`
   - `meminit check --root . --format md`
4) If violations are large, run scoped previews:
   - `meminit fix --root . --dry-run --namespace <name>`
5) Report results and ask before applying any `--no-dry-run` writes.
```

#### Safety rails (commands to keep you out of trouble)

- Preview everything:
  - `meminit scan --root . --format md`
  - `meminit check --root . --format md`
  - `meminit fix --root . --dry-run --namespace root`
- Apply in a controlled subtree:
  - `meminit fix --root . --no-dry-run --namespace root`
- Create new governed docs in the intended subtree:
  - `meminit new ADR "Some decision" --root . --namespace some-package`

#### Reminder about WIP docs

If a package/app subtree is not ready to be governed:

- do **not** add it to `namespaces` yet.
- keep drafts as `WIP-*` (Meminit excludes them by default) until you’re ready to promote.

#### “Canonical filename” reminder

Meminit will not try to rename canonical repo files (even though they aren’t kebab-case):
`README.md`, `CHANGELOG.md`, `LICENSE*`, `LICENCE*`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `NOTICE*`.

### 2) Run scan to generate a migration plan

Run:

```bash
meminit scan --root . --format md
```

For scriptable pipelines, use JSON:

```bash
meminit scan --root . --format json
```

Interpretation:

- If `suggested_type_directories` is non-empty, your repo likely uses nonstandard doc folders (e.g., `docs/adrs`).
- If `ambiguous_types` is non-empty, a manual decision is required before migration can proceed cleanly.
- If `suggested_namespaces` is non-empty, Meminit found likely monorepo docs roots (e.g., `packages/*/docs`) and is recommending `namespaces` blocks.

### 3) Decide DocOps version (schema + frontmatter shape)

If you are upgrading from an older DocOps constitution/schema:

- Choose whether to migrate to `docops_version: '2.0'` now (recommended) or keep the older version temporarily.
- This choice determines the required frontmatter shape and the schema file used for validation.

### 4) Ensure baseline scaffolding exists (schema + config)

Options:

- **Option A (recommended for brownfield):** create or edit `docops.config.yaml` manually (minimal + targeted).
- **Option B:** run `meminit init` to scaffold directories/templates/schema (idempotent, but may create directories you don’t want yet).

Important:

- `docops.config.yaml` keys like `docs_root`, `schema_path`, and `type_directories` are **optional** (defaults exist), but you must set them if your repo differs from defaults.

### 5) Edit `docops.config.yaml` to match reality

Typical changes:

- Set `docs_root` if docs are not in `docs/`.
- Add `type_directories` overrides (e.g., `ADR: adrs`).
- Ensure `schema_path` points at the correct schema file.

For monorepos:

- Add `namespaces` (each namespace defines `docs_root` + `repo_prefix`).
- Optional: set `index_path` if you want the index outside `docs/` (e.g., `.meminit/meminit.index.json`).

### 6) Run doctor (repo readiness)

Run:

```bash
meminit doctor --root .
```

Fix any repo-level errors (missing schema, missing docs root, etc.) before continuing.

### 7) Run check to see the violations

Run:

```bash
meminit check --root . --format md
```

This gives the authoritative list of violations to resolve.

### 8) Run fix in dry-run mode (preview)

Run:

```bash
meminit fix --root . --dry-run
```

Review proposed actions; ensure renames and metadata injections are acceptable.

Monorepo safety:

- Prefer `meminit fix --root . --dry-run --namespace <name>` so you can review one subtree at a time.

### 9) Migrate legacy document IDs (if needed)

If your repo already has `document_id` values that do not match `REPO-TYPE-SEQ`, migrate them before expecting `check` to go green.

Run:

```bash
meminit migrate-ids --root . --dry-run --format md
```

If the proposed changes look correct:

```bash
meminit migrate-ids --root . --no-dry-run --format md
```

Note:

- If many docs are missing frontmatter or missing `type`, run `meminit fix --no-dry-run` first so `type` can be inferred, then rerun `migrate-ids`.

### 10) Apply mechanical fixes

Run:

```bash
meminit fix --root . --no-dry-run
```

Commit the changes (recommended).

Monorepo safety:

- Prefer `meminit fix --root . --no-dry-run --namespace <name>` to keep changes scoped and reviewable.

### 11) Re-run check until green

Run:

```bash
meminit check --root .
```

If violations remain, address manual items:

- Duplicate `document_id` (requires human choice).
- Meaningful metadata: `owner`, `area`, `status` promotion, approvers.

## Policy: handling existing docs with no frontmatter

Recommended:

- Add frontmatter and set `status: Draft`.
- Use `owner: __TBD__` until a human assigns ownership.
- Do not mark docs as `Approved` while placeholders remain.

## Expected manual work

- Duplicates: resolve conflicting IDs.
- Ownership and governance: assign `owner`, decide `status`, fill `superseded_by`.
- Content: headings and structure quality is out of scope for mechanical migration.
