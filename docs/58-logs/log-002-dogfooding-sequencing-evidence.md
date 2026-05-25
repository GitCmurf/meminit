---
document_id: MEMINIT-LOG-002
type: LOG
title: Dogfooding Sequencing Evidence
status: Draft
version: "0.1"
last_updated: "2026-05-22"
owner: GitCmurf
docops_version: "2.0"
template_type: log-standard
template_version: "2.0"
---

> **Document ID:** MEMINIT-LOG-002
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-05-22
> **Type:** LOG

<!-- MEMINIT_SECTION: title -->
<!-- AGENT: The title should be concise and descriptive of the log record. -->

# LOG: Dogfooding Sequencing Evidence

<!-- MEMINIT_SECTION: executive_summary -->
<!-- AGENT: Write a 2-3 sentence overview of this log record and what evidence it documents. -->

## 0. Executive Summary

This log document records the execution evidence for the Greenfield and Brownfield adoption simulations performed on 2026-05-22. It confirms the correct behavior of the Meminit CLI tool suite (`init`, `context`, `new`, `check`, `index`, `scan`, `fix`, `resolve`) in isolated environment testbeds and asserts zero compliance violations at sequence completion.

<!-- MEMINIT_SECTION: context -->
<!-- AGENT: Describe the context, target system/repository, and environment details. -->

## 1. Environment and Parameters

| Parameter           | Value                    |
| ------------------- | ------------------------ |
| Attestation Date    | 2026-05-22               |
| Executor / Operator | Antigravity AI Agent     |
| Meminit Version     | 0.2.0                    |
| Python Version      | 3.12.x / 3.13.x          |
| OS Version          | Linux                    |
| Greenfield Path     | `tmp/dogfood-greenfield` |
| Brownfield Path     | `tmp/dogfood-brownfield` |

<!-- MEMINIT_SECTION: decision -->
<!-- AGENT: List the commands run and key decision points or events. -->

## 2. Command execution log / events

### Greenfield Simulation Run

The following sequence was executed on a clean directory initialized with Git:

```bash
git init
meminit init --root . --format json
meminit context --root . --format json
meminit new ADR "Use Meminit for governed docs" --root . --format json
meminit check --root . --format json
meminit index --root . --format json
meminit resolve DOGFOOD-ADR-001 --root . --format json
```

All commands returned status `0` (success). The JSON outputs were confirmed to match output schema version `3.0`.

### Brownfield Simulation Run

The following sequence was executed on a directory containing pre-existing violating files:

```bash
# Initial state: docs/adr-001.md (no frontmatter), docs/45-adr/my_poorly named_adr.md (misnamed), docs/prds/prd-001.md (misplaced ADR)
meminit scan --root . --format json
meminit scan --root . --plan .meminit/adoption-plan.json --format json
meminit fix --root . --plan .meminit/adoption-plan.json --dry-run --format json
meminit fix --root . --plan .meminit/adoption-plan.json --no-dry-run --format json
# Manual step: resolve prefix mismatch to match config.repo_prefix (DOGFOOD)
meminit check --root . --format json
meminit index --root . --format json
```

Results:

- `scan` successfully identified 3 violating files and generated a deterministic `.meminit/adoption-plan.json` containing 4 actions (rename, metadata patch, move files).
- `fix --dry-run` successfully reported the simulated fixes (fixed: 4, remaining: 5, status: false/exit code 1 as expected since dry-run does not write to disk).
- `fix --no-dry-run` successfully applied the 4 plan actions, writing/moving the files correctly.
- `check` and `index` returned status `0` (success) with zero remaining violations.

<!-- MEMINIT_SECTION: validation -->
<!-- AGENT: Summarize findings, validation outputs, or defect lists. -->

## 3. Findings and Defects

1. **Incremental Configuration Validation**: Configuration context loading is strict. Missing `docops_version` in `docops.config.yaml` is flagged correctly with exit code `66` (`CONFIG_MISSING`).
2. **Deterministic Scan/Fix**: `meminit scan` and `meminit fix` accurately correct directory mismatches, filename formatting, and inject missing frontmatter blocks automatically.
3. **ID Prefix Compliance**: Document IDs must match the configured prefix (`repo_prefix` field) for their namespace. `migrate-ids` command currently handles legacy ID structures but expects general canonical formats to be corrected matching prefix policies.

<!-- MEMINIT_SECTION: version_history -->
<!-- AGENT: Track version changes with dates, authors, and change summaries. -->

## 4. Version History

| Version | Date       | Author      | Changes                                                                   |
| ------- | ---------- | ----------- | ------------------------------------------------------------------------- |
| 0.1     | 2026-05-22 | Antigravity | Recorded Greenfield and Brownfield simulation execution logs and results. |
