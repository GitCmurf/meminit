---
document_id: MEMINIT-RUNBOOK-007
type: RUNBOOK
docops_version: "2.0"
last_updated: "2026-03-05"
status: Approved
title: Existing Repository Migration (Templates v2)
owner: GitCmurf
version: "1.0"
---

# Runbook: Existing Repository Migration (Templates v2)

## Goal

Bring a legacy repository into compliance with DocOps standards using `meminit`, including Templates v2 migration.

This is the v2 evolution of [MEMINIT-RUNBOOK-003](runbook-003-existing-repo-migration.md).

## Steps

### 1-4. Baseline Migration

Follow steps 1-4 in [MEMINIT-RUNBOOK-003](runbook-003-existing-repo-migration.md) to assess, initialize, and apply automated fixes.

### 5. Template Migration (Templates v2)

If your repository uses legacy template placeholder syntax (`{title}`, `<REPO>`, `<SEQ>`, etc.), migrate to Templates v2:

```bash
meminit migrate-templates --dry-run
```

This command:

- Converts legacy `type_directories` config to `document_types` format
- Converts legacy `templates` config to `document_types.<type>.template` format
- Renames template files from `template-001-*.md` to `*.template.md`
- Migrates placeholder syntax from `{title}` to `{{title}}` and `<REPO>` to `{{repo_prefix}}`

Review the changes. To apply the changes (rename files, update config, replace placeholders), run:

```bash
meminit migrate-templates --no-dry-run
```

Then review and commit the changes.
