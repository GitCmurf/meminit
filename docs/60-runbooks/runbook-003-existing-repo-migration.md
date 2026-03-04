---
document_id: MEMINIT-RUNBOOK-003
type: RUNBOOK
docops_version: "2.0"
last_updated: "2026-03-01"
status: Approved
title: Existing Repository Migration
owner: GitCmurf
version: "1.0"
---

# Runbook: Existing Repository Migration

## Goal

Bring a legacy repository into compliance with DocOps standards using `meminit`.

## Steps

### 1. Assessment

Run the doctor command to verify schema/config readiness:

```bash
meminit doctor
```

Run the check command to see the current state:

```bash
meminit check
```

Review the list of violations (e.g., bad filenames, missing frontmatter).

If your repo uses a nonstandard docs layout (e.g., `docs/adrs/` instead of `docs/45-adr/`), adjust `docops.config.yaml` to match before you start migrating:

- `excluded_paths`: ignore template folders and other non-governed markdown
- `document_types`: map doc types to their directories and templates (e.g., `ADR: {directory: adrs}`)

Note: Legacy `type_directories` and `templates` config keys are no longer supported in Templates v2. Use `document_types` instead.

### 2. Initialization

Run `meminit init` to ensure the standard directory structure exists (`docs/`, `AGENTS.md`, etc.). Existing files will not be overwritten.

### 3. Automated Fixes

For brownfield repos, generate a deterministic migration plan first (recommended), then apply it with `fix`. This reduces guesswork and makes the remediation loop safer and more reviewable.

### 3a. Generate a Migration Plan (Recommended)

Run scan and write a plan artifact (this does not mutate the repo):

```bash
meminit scan --plan /tmp/meminit_migration_plan.json
```

Review the plan file and ensure the actions look correct and non-destructive.

### 3b. Apply Fixes (Plan-Driven)

Run the fix command in dry-run mode first:

```bash
meminit fix --plan /tmp/meminit_migration_plan.json --dry-run
```

If the changes look safe (e.g., renaming files, adding timestamps), apply them:

```bash
meminit fix --plan /tmp/meminit_migration_plan.json --no-dry-run
```

### 4. Manual Remediation

For violations that `fix` cannot handle (e.g., moving files to correct directories), edit the files manually. If `fix` initializes missing frontmatter fields, review and replace placeholder values like `owner: Unknown`.

### 4a. Template Migration (Templates v2)

If your repository uses legacy template placeholder syntax (`{title}`, `<REPO>`, `<SEQ>`, etc.), migrate to Templates v2:

```bash
meminit migrate-templates
```

This command:
- Converts legacy `type_directories` config to `document_types` format
- Converts legacy `templates` config to `document_types.<type>.template` format
- Renames template files from `template-001-*.md` to `*.template.md`
- Migrates placeholder syntax from `{title}` to `{{title}}` and `<REPO>` to `{{repo_prefix}}`

Review the changes and commit them.

### 5. Validation

Run `meminit check` again to ensure zero violations.

### 6. Commit

```bash
git add .
git commit -m "chore: Migrate documentation to DocOps standards"
```
