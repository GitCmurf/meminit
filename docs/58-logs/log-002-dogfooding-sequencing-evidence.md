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

This log document records real execution evidence for Meminit greenfield adoption on the bedtime-alexa repository (2026-05-26). The repository was initialized with Meminit DocOps and confirmed to have zero compliance violations using Meminit SHA 395f4e7.

<!-- MEMINIT_SECTION: context -->
<!-- AGENT: Describe the context, target system/repository, and environment details. -->

## 1. Environment and Parameters

| Parameter           | Value                              |
| ------------------- | ---------------------------------- |
| Attestation Date    | 2026-05-26                         |
| Executor / Operator | AI Agent (adversarial remediation) |
| Meminit Version     | 0.3.0a1                            |
| Meminit SHA (pinned) | 395f4e77ef51383ae830bf1fb1223e95e69c5747 |
| Python Version      | 3.12.x                             |
| OS Version          | Linux                              |
| Greenfield Path     | `/home/cmf/code/bedtime-alexa`     |
| Greenfield Repo SHA | dc5d30e404226b08c414ddd71fe34b23d46891f7 |

<!-- MEMINIT_SECTION: decision -->
<!-- AGENT: List the commands run and key decision points or events. -->

## 2. Command execution log / events

### Greenfield Run: bedtime-alexa Repository

Target: `/home/cmf/code/bedtime-alexa` (external production repository)

**Initial State (2026-05-26)**
- Repository already contained full docs structure (00-governance, 02-strategy, 45-adr, etc.)
- Repository SHA: dc5d30e404226b08c414ddd71fe34b23d46891f7
- Configured with docops.config.yaml (repo_prefix: BEDTIME)

**Evidence Collection (Meminit SHA 395f4e77ef51383ae830bf1fb1223e95e69c5747)**

```bash
# Context validation
meminit context --root . --format json
# Result: success=true, repo_prefix=BEDTIME, 21 document types, 21 directories

# Compliance check
meminit check --root . --format json
# Result: success=true, files_checked=4, files_passed=4, violations=0

# Sample JSON output (check):
{
  "output_schema_version": "3.0",
  "success": true,
  "command": "check",
  "files_checked": 4,
  "files_passed": 4,
  "files_failed": 0,
  "violations_count": 0
}

# Governed documents found:
# - docs/00-governance/docops-constitution.md
# - docs/02-strategy/strat-001-bedtime-alexa-skill-concept.md
# - docs/10-prd/prd-001-bedtime-alexa-mvp-feature-set.md
# - docs/45-adr/adr-001-use-an-alexa-hosted-custom-skill.md
```

**Results**

- All 4 governed documents pass schema validation
- Zero violations
- Output schema version confirmed at 3.0
- Repo prefix correctly configured as BEDTIME

### Brownfield Simulation (Historical - 2026-05-22)

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

1. **Real Greenfield Success**: bedtime-alexa repository at SHA dc5d30e404226b08c414ddd71fe34b23d46891f7 passes all Meminit compliance checks using Meminit SHA 395f4e77ef51383ae830bf1fb1223e95e69c5747.
2. **Configuration Validation**: Configuration context loading is strict. Missing `docops_version` in `docops.config.yaml` is flagged correctly with exit code `66` (`CONFIG_MISSING`).
3. **Deterministic Scan/Fix**: `meminit scan` and `meminit fix` accurately correct directory mismatches, filename formatting, and inject missing frontmatter blocks automatically.
4. **ID Prefix Compliance**: Document IDs must match the configured prefix (`repo_prefix` field) for their namespace. `migrate-ids` command currently handles legacy ID structures but expects general canonical formats to be corrected matching prefix policies.

<!-- MEMINIT_SECTION: version_history -->
<!-- AGENT: Track version changes with dates, authors, and change summaries. -->

## 4. Version History

| Version | Date       | Author        | Changes                                                                   |
| ------- | ---------- | ------------- | ------------------------------------------------------------------------- |
| 0.2     | 2026-05-26 | AI Agent      | Added real bedtime-alexa evidence with commit SHAs and pinned Meminit SHA |
| 0.1     | 2026-05-22 | Antigravity   | Recorded Greenfield and Brownfield simulation execution logs and results. |
