---
document_id: MEMINIT-TASK-004
type: TASK
title: Adoption DocOps Control Plane Remediation
status: Draft
version: "0.1"
last_updated: "2026-05-31"
owner: GitCmurf
area: ADOPT
docops_version: "2.0"
template_type: task-standard
template_version: "2.0"
description:
  Tracks protocol, state queue, template, skeleton, and migrate-ids remediation
  from PLAN-016 follow-up.
keywords:
  - adoption
  - docops
  - agent
related_ids:
  - MEMINIT-PLAN-016
---

> **Document ID:** MEMINIT-TASK-004
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-05-31
> **Type:** TASK
> **Area:** ADOPT
> **Description:** Tracks protocol, state queue, template, skeleton, and migrate-ids remediation from PLAN-016 follow-up.

<!-- MEMINIT_SECTION: title -->
<!-- AGENT: The title should state the implementation objective clearly. -->

# TASK: Adoption DocOps Control Plane Remediation

<!-- MEMINIT_SECTION: executive_summary -->
<!-- AGENT: Summarize the task, why it exists, and the intended completion state. -->

## 0. Executive Summary

Remediate the adoption control-plane gaps surfaced after MEMINIT-PLAN-016:
agent protocol alignment, project-state task selection, launch-critical template
coverage, marker-aware fallback documents, and prefix mismatch repair in
`migrate-ids`.

Completion means agents can orient through DocOps before patching, generate
useful governed docs during coding, and verify code/docs/tests alignment with a
deterministic local gate.

<!-- MEMINIT_SECTION: review_basis -->
<!-- AGENT: List source reports, live commands, and evidence used to scope the task. -->

## 1. Review Basis

- `./.venv/bin/meminit check --format json`
- `./.venv/bin/meminit protocol check --format json`
- `./.venv/bin/meminit protocol sync --format json` dry-run preview
- `./.venv/bin/meminit state list --root . --format json`
- [MEMINIT-PLAN-016](../plan-016-adoption-and-dogfooding-sequencing.md)
- [TECH_DEBT.md](../../../TECH_DEBT.md)

<!-- MEMINIT_SECTION: current_state -->
<!-- AGENT: Distinguish live defects from stale or already-corrected findings. -->

## 2. Current State

- `AGENTS.md` had a tampered protocol block because an extra blank line changed
  the managed payload hash even though the human-readable content was otherwise
  current.
- `project-state.yaml` was still a legacy state file and selected stale
  `MEMINIT-PRD-005` work instead of active adoption-control remediation.
- STRAT was a foundational document type but lacked first-class Templates v2
  coverage in repo templates, init scaffolding, and packaged assets.
- The no-template fallback emitted a markerless skeleton, so agents could not
  use section metadata or `initial_content` to fill a document deterministically.
- `migrate-ids` handled non-canonical and duplicate IDs, but did not restamp
  canonical-looking IDs whose prefix or type segment disagreed with the current
  namespace configuration.

<!-- MEMINIT_SECTION: work_items -->
<!-- AGENT: Break the work into prioritized, implementable items with definitions of done. -->

## 3. Work Items

| ID   | Work item                                      | Definition of done                                                                                                                                         |
| ---- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| WI-1 | Restore protocol asset alignment               | `AGENTS.md` managed payload matches the registry; `meminit protocol check --format json` passes.                                                           |
| WI-2 | Refresh project state queue                    | `project-state.yaml` uses schema v2 and points agents at real remaining work, not stale PRD implementation entries.                                        |
| WI-3 | Promote STRAT to first-class template coverage | `meminit new STRAT ... --dry-run --format json` applies a template with section markers; init writes the STRAT template and config mapping.                |
| WI-4 | Make fallback skeletons machine-fillable       | A no-template type returns parsed sections and agent prompts in JSON output.                                                                               |
| WI-5 | Repair repo-prefix ID drift                    | `migrate-ids` previews and applies restamping for canonical-looking IDs with wrong prefix/type segment, including reference rewrites.                      |
| WI-6 | Encode the canonical agent loop                | The Meminit skill/runbook tells agents to use `context`, `state next`, `resolve`, Code + Documentation + Tests, and DocOps gates as the standard workflow. |

<!-- MEMINIT_SECTION: verification_matrix -->
<!-- AGENT: List the exact commands and evidence required before closure. -->

## 4. Verification Matrix

| Surface     | Verification                                                                                                                                                                                                          |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Syntax      | `./.venv/bin/python -m py_compile src/meminit/core/use_cases/migrate_ids.py src/meminit/core/use_cases/new_document.py src/meminit/core/use_cases/init_repository.py src/meminit/core/services/repo_config.py`        |
| Templates   | `./.venv/bin/pytest -q -s tests/core/services/test_template_resolver.py tests/core/use_cases/test_new_document.py tests/core/use_cases/test_init_repository_assets.py tests/integration/test_template_regressions.py` |
| Migration   | `./.venv/bin/pytest -q -s tests/core/use_cases/test_migrate_ids.py`                                                                                                                                                   |
| STRAT smoke | `./.venv/bin/meminit new STRAT "Template Smoke" --dry-run --format json`                                                                                                                                              |
| DocOps      | `./.venv/bin/meminit check --format json` and `./.venv/bin/meminit protocol check --format json`                                                                                                                      |
| State queue | `./.venv/bin/meminit state next --root . --format json`                                                                                                                                                               |

<!-- MEMINIT_SECTION: version_history -->
<!-- AGENT: Track version changes with dates, authors, and change summaries. -->

## 5. Version History

| Version | Date       | Author   | Changes       |
| ------- | ---------- | -------- | ------------- |
| 0.1     | 2026-05-31 | GitCmurf | Initial draft |
