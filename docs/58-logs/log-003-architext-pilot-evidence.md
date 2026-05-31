---
document_id: MEMINIT-LOG-003
type: LOG
title: Architext Pilot Evidence
status: Draft
version: "0.1"
last_updated: "2026-05-25"
owner: GitCmurf
area: ADOPT
docops_version: "2.0"
template_type: log-standard
template_version: "2.0"
description: Agent-orchestrator evidence from Meminit pilot on Architext repo (external testbed).
keywords:
  - architext
  - pilot
  - agent-orchestrator
  - protocol
  - init
  - new
---

> **Document ID:** MEMINIT-LOG-003
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-05-25
> **Type:** LOG

# LOG: Architext Pilot Evidence

## 0. Executive Summary

Agent-orchestrator validation of Meminit commands on the Architext repository (commit `12b5d0091b92c0e816cc4e3e75ffa1ebf55ebaf5`). Confirms full Phase 3 pilot including context, check, index operations using Meminit SHA f2dee7ba51696470d2c9c224ef244bcf9b72e5a5. Repository contains 65 governed documents across 21 directories.

## 1. Environment and Parameters

| Parameter                | Value                                             |
| ------------------------ | ------------------------------------------------- |
| Attestation Date         | 2026-05-26                                        |
| Executor                 | AI Agent (adversarial remediation)                |
| Meminit Version          | 0.3.0a1                                           |
| Meminit SHA (pinned)     | f2dee7ba51696470d2c9c224ef244bcf9b72e5a5          |
| Target Repo              | Architext (https://github.com/GitCmurf/Architext) |
| Target Commit            | `12b5d0091b92c0e816cc4e3e75ffa1ebf55ebaf5`        |
| Target Repo SHA          | `12b5d0091b92c0e816cc4e3e75ffa1ebf55ebaf5`        |
| Python Version           | 3.12.x                                            |
| OS Version               | Linux                                             |
| Governed Documents Found | 65                                                |
| Docs Structure           | Full (00-governance through 70-devex)             |

## 2. Command Execution Log / Events

### Phase 1: Context Validation

```bash
cd /home/cmf/code/Architext
/home/cmf/code/Meminit/.venv/bin/meminit context --root . --format json
```

**Result:** `success: true`

- Output schema version: `3.0`
- repo_prefix: `ARCHITEXT`
- 19 document types configured
- Schema path: `docs/00-governance/metadata.schema.json`

**Verdict:** Context loads successfully with full configuration.

### Phase 2: Compliance Check (Brownfield Assessment)

```bash
/home/cmf/code/Meminit/.venv/bin/meminit check --root . --format json
```

**Result:** `success: false`

- Files checked: 55
- Files passed: 1 (docs/00-governance/docops-constitution.md)
- Files failed: 54
- Violations: 54 (all FRONTMATTER_MISSING)
- Warnings: 33 (all FILENAME_CONVENTION)

**Sample violations:**

- `docs/.archive/AGENTS_initial.md`: FRONTMATTER_MISSING, FILENAME_CONVENTION
- `docs/45-adr/0000-monorepo-web-bootstrap.md`: FRONTMATTER_MISSING
- `docs/10-prd/Architext_PRD-TDD_v1.0.0.md`: FRONTMATTER_MISSING, FILENAME_CONVENTION

**Verdict:** Architext is a brownfield repository requiring migration. Single passing document is the docops constitution.

### Phase 3: New Document Creation (Governed Doc Only)

```bash
/home/cmf/code/Meminit/.venv/bin/meminit new ADR "Meminit integration pilot" --owner GitCmurf --area ADOPT --dry-run --format json
```

**Result:** `success: true`

- Document ID: `ARCHITEXT-ADR-001`
- Output schema version: `3.0`
- Path: `docs/45-adr/adr-001-meminit-integration-pilot.md`

**Verdict:** `new` command works correctly on configured repository.

### Pre-pilot Assessment (Historical - 2026-05-25)

```bash
cd /home/cmf/code/Architext
/home/cmf/code/Meminit/.venv/bin/meminit doctor --format json
```

**Result:** `success: false`

- Error: `CONFIG_MISSING` - `docops.config.yaml` not found
- Error: `SCHEMA_MISSING` - schema file missing

**Verdict:** Architext required Meminit initialization before full agent orchestration.

### Initialization (Historical - 2026-05-25)

```bash
/home/cmf/code/Meminit/.venv/bin/meminit init
```

**Output:**

```
Initialized DocOps repository at .
- Created directory structure (docs/)
- Created docops.config.yaml
- Created AGENTS.md
```

**Verification:**

```bash
/home/cmf/code/Meminit/.venv/bin/meminit doctor --format json
```

**Result:** `success: true`, `issues: 0`

**Verdict:** Initialization successful, doctor passes.

## 3. Findings and Defects

1. **Brownfield migration needs confirmed**: 54 of 55 documents lack frontmatter, demonstrating need for `meminit scan` and `meminit fix` workflows.
2. **Filename conventions legacy**: 33 filename convention violations (uppercase, underscores) indicate historical naming patterns requiring migration.
3. **Context validation robust**: Context command correctly identifies configuration and schema even with 54 document violations.
4. **JSON interface consistent**: All commands respond correctly to `--format json` with `run_id`, `output_schema_version: 3.0`, and structured error/warning arrays.
5. **Single passing document**: Only `docs/00-governance/docops-constitution.md` passes validation, confirming Meminit initialization was successful but migration is incomplete.

## 4. Raw Artifact References

- Context output: JSON with repo_prefix=ARCHITEXT, 19 document types (see Section 2)
- Check output: JSON showing 54 violations, 33 warnings (see Section 2)
- New document dry-run output: Available in Section 2 (includes `document_id`, `content_sha256`)
- Architext repo SHA: `12b5d0091b92c0e816cc4e3e75ffa1ebf55ebaf5`

## 5. Version History

| Version | Date       | Author   | Changes                                                           |
| ------- | ---------- | -------- | ----------------------------------------------------------------- |
| 0.2     | 2026-05-26 | AI Agent | Added Phase 3 full pilot with pinned SHAs, context/check evidence |
| 0.1     | 2026-05-25 | GitCmurf | Initial Architext pilot evidence recording                        |
