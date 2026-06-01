---
document_id: MEMINIT-DEVEX-001
type: DEVEX
title: Release Notes v0.3.0-alpha
status: Draft
version: "0.1"
last_updated: 2026-05-25
owner: GitCmurf
area: ADOPT
docops_version: "2.0"
description: Release notes for Meminit v0.3.0-alpha, covering protocol asset governance, Templates v2, NDJSON streaming, catalog/kanban generation, project state queue, and release automation.
keywords:
  - release
  - release-notes
  - 0.3.0
  - protocol
  - templates
  - streaming
  - state
  - release-workflow
---

> **Document ID:** MEMINIT-DEVEX-001
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1

# DEVEX: Release Notes v0.3.0-alpha

## Summary

Meminit v0.3.0-alpha introduces protocol asset governance, Templates v2, NDJSON streaming, catalog and kanban generation, project state queue, and automated release workflows. This release focuses on production readiness for AI agent workflows and launch infrastructure.

## Supported Commands

### Core Commands

- `meminit init` — scaffold governed docs tree
- `meminit doctor` — repo readiness diagnostics
- `meminit check` — validate doc compliance
- `meminit scan` — brownfield repo analysis
- `meminit scan --plan <PATH>` — generate deterministic migration plan
- `meminit fix` — auto-fix violations (dry-run by default)
- `meminit fix --plan <PATH>` — apply plan-driven changes
- `meminit index` — build index and optional catalog/kanban
- `meminit new <TYPE> <TITLE>` — create governed document
- `meminit adr new <TITLE>` — ADR shortcut

### Resolution Commands

- `meminit resolve <DOCUMENT_ID>` — ID → path lookup
- `meminit identify <PATH>` — path → ID lookup
- `meminit link <DOCUMENT_ID>` — check links

### State Management

- `meminit state set <DOCUMENT_ID> --impl-state <STATE>` — set implementation state
- `meminit state set <DOCUMENT_ID> --priority <P1|P2|P3>` — set priority
- `meminit state set <DOCUMENT_ID> --add-depends-on <ID>` — add dependency
- `meminit state set <DOCUMENT_ID> --add-blocked-by <ID>` — add blocker
- `meminit state get <DOCUMENT_ID>` — get state
- `meminit state list` — list all states
- `meminit state next` — deterministic next work item
- `meminit state blockers` — list blocked entries

### Protocol Governance

- `meminit protocol check` — detect drift in governed assets
- `meminit protocol sync` — remediate drift (dry-run by default)

### Discovery

- `meminit context` — discover repo shape and types
- `meminit new --list-types` — list configured document types

## Unsupported/Deferred Surfaces

The following surfaces are planned but not yet implemented:

- **Global state query:** Cross-repo state coordination (deferred)
- **Visual state board:** Kanban-style state visualization beyond HTML export (deferred)
- **Real-time sync:** Watch-mode for index rebuilds on file changes (deferred)

## Install Methods

### From GitHub (current, pre-PyPI)

```bash
# Install as a tool via uv
uv tool install git+https://github.com/GitCmurf/meminit.git@main

# From local clone
git clone https://github.com/GitCmurf/meminit.git
cd meminit
uv pip install -e .
```

### From PyPI (after v0.3.0 release)

```bash
# Standard pip install
pip install meminit

# Via uv
uv tool install meminit
```

## Pre-1.0 Compatibility Policy

**Breaking changes may occur without major version bumps** until v1.0. Specific commitments:

- **Template placeholder syntax:** Legacy `{title}`, `<REPO>`, `<SEQ>` syntax is **rejected**. Only `{{variable}}` is supported.
- **Output contract v3:** All JSON output uses `output_schema_version: "3.0"` envelope structure. v2 compatibility is not maintained.
- **Error codes:** Public error codes may be renamed or reorganized for consistency (e.g., state-related codes now use `STATE_*` prefix).
- **Config schema:** `docops.config.yaml` structure may evolve; `meminit migrate-templates` is available for migration assistance.

After v1.0, standard semantic versioning will be strictly observed.

## Known Limitations

1. **Protocol assets:** Only 3 standard assets are governed (AGENTS.md, SKILL.md, brownfield script). Custom protocol assets require code changes.
2. **Templates v2:** ADR, PRD, FDD, PLAN, SPEC, RUNBOOK, DESIGN, LOG, TASK, and STRAT have Templates v2 section markers. Other types use legacy templates.
3. **Secret scanning:** gitleaks must be installed locally for pre-commit enforcement. CI uses the GitHub Action. Meminit runtime state (`.meminit/cache/` and `.meminit.lock`) should be git-ignored and scanner-excluded, not committed or added to scanner baselines.
4. **State management:** `project-state.yaml` is file-based; concurrent writes from multiple agents may conflict (use agent routing).
5. **Index caching:** Cache is invalidated on schema/config changes but may require manual clearing (`docs/01-indices/.index_cache.json`) in rare edge cases.

## Known Risks

1. **Protocol sync force mode:** `meminit protocol sync --force` overwrites tampered assets without confirmation. Use only after manual inspection.
2. **Fix --plan mutation:** `meminit fix --plan <PATH>` writes directly to disk. Always run `fix --plan <PATH> --dry-run` first.
3. **State file corruption:** Malformed `project-state.yaml` is fatal. Validate edits before committing.
4. **Template interpolation:** Unicode normalization may differ between Python versions for non-ASCII variable values.

## Validation Evidence

See [MEMINIT-LOG-002](../58-logs/log-002-dogfooding-sequencing-evidence.md), [MEMINIT-LOG-003](../58-logs/log-003-architext-pilot-evidence.md), and [MEMINIT-LOG-005](../58-logs/log-005-stranger-simulation-evidence.md) for adoption evidence.

## Related Documents

- [MEMINIT-PLAN-016](../05-planning/plan-016-adoption-and-dogfooding-sequencing.md) — Adoption and dogfooding sequencing
- [MEMINIT-GOV-003](../00-governance/gov-003-security-practices.md) — Security practices (includes secret scanning)
- [MEMINIT-RUNBOOK-004](../60-runbooks/runbook-004-ci-cd-enforcement.md) — CI/CD enforcement setup
- [MEMINIT-SPEC-008](../20-specs/spec-008-agent-output-contract-v2.md) — Agent output contract v3

## Version History

| Version | Date       | Author   | Changes                                |
| ------- | ---------- | -------- | -------------------------------------- |
| 0.1     | 2026-05-25 | GitCmurf | Initial release notes for v0.3.0-alpha |
