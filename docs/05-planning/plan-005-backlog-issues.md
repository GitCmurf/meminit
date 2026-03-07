---
document_id: MEMINIT-PLAN-005
type: PLAN
title: "WIP Backlog & Issues Tracker"
status: Draft
version: "0.4"
last_updated: 2026-03-07
owner: GitCmurf
docops_version: "2.0"
area: Planning
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PLAN-005
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.4
> **Last Updated:** 2026-03-07
> **Type:** PLAN

# WIP Backlog & Issues Tracker

This document tracks work-in-progress items, known issues, and technical debt for the Meminit project.

---

## 1. PRD Implementation Status

### 1.1 PRD-001: Meminit Tooling Ecosystem

| Requirement                                      | Status                 | Notes                                                                   |
| ------------------------------------------------ | ---------------------- | ----------------------------------------------------------------------- |
| F1.1 DocOps Constitution in meminit repo         | ✅ Met                 | Implemented in `src/meminit/core/assets/org_profiles/default/org_docs/` |
| F1.2 Org-level config (`org-docops.config.yaml`) | 🔲 Not Yet Implemented | Single-org use case; org-level config deferred                          |
| F1.3 Constitution version tracking               | ✅ Met                 | Via `docops_version` field                                              |
| F2.1 `meminit init`                              | ✅ Met                 | Exceeds requirements                                                    |
| F3.1 `meminit new`                               | ✅ Met                 | Full implementation with metadata flags                                 |
| F3.2 JSON output for `meminit new`               | ✅ Met                 | Implemented via `--format json`                                         |
| F4.1 `meminit check`                             | ✅ Met                 | Full schema validation                                                  |
| F5.1 `meminit scan`                              | ✅ Met                 | Migration planning with dry-run support                                 |
| F5.2 Scan dry-run/patch mode                     | ✅ Met                 | Via `--plan` flag                                                       |
| F6.1 `meminit index`                             | ✅ Met                 | Generates `doc_index.json`                                              |
| F6.2 `meminit link`                              | ✅ Met                 | Markdown link generation                                                |
| F7.1 Pre-commit hooks                            | ✅ Met                 | Via `meminit install-precommit`                                         |
| F7.2 CI workflow examples                        | ✅ Met                 | `.github/workflows/ci.yml`                                              |

### 1.2 PRD-002: Enhanced Document Factory (meminit new)

| Requirement                   | Status | Notes                                                                           |
| ----------------------------- | ------ | ------------------------------------------------------------------------------- |
| F1 `--format json`            | ✅ Met | Full JSON envelope with schema versioning                                       |
| F2 Extended metadata flags    | ✅ Met | `--owner`, `--area`, `--description`, `--status`, `--keywords`, `--related-ids` |
| F3 `--dry-run` / `--verbose`  | ✅ Met | Preview mode and decision logging                                               |
| F4 `--list-types`             | ✅ Met | Type discovery with JSON output                                                 |
| F5 `--id` deterministic       | ✅ Met | Exact ID specification with validation                                          |
| F6 Visible metadata block     | ✅ Met | `<!-- MEMINIT_METADATA_BLOCK -->` replacement                                   |
| F7 Template enhancement       | ✅ Met | Frontmatter preservation, array placeholders                                    |
| F8 `--interactive` / `--edit` | ✅ Met | Interactive prompts and editor launch                                           |
| F9 Error codes                | ✅ Met | Full `ErrorCode` enum implementation                                            |
| F10 Targeted validation       | ✅ Met | `meminit check <paths>` with glob support                                       |

### 1.3 PRD-006: Document Templates v2

| Requirement                         | Status | Notes                                                    |
| ----------------------------------- | ------ | -------------------------------------------------------- |
| FR-1 Template Resolution Precedence | ✅ Met | Config → convention → builtin → skeleton                 |
| FR-3 {{variable}} interpolation     | ✅ Met | Only supported syntax; legacy rejected                   |
| FR-4 Agent Prompt Blocks            | ✅ Met | `<!-- AGENT: ... -->` preserved                          |
| FR-5 Stable Section IDs             | ✅ Met | `<!-- MEMINIT_SECTION: ... -->` markers                  |
| FR-6 document_types single source   | ✅ Met | Single source of truth in config                         |
| FR-7 JSON Output                    | ✅ Met | `rendered_content` field now implemented (P1.1 complete) |
| FR-8 Metadata Block Rule            | ✅ Met | Single metadata block, no duplicates                     |
| FR-9 Frontmatter Merging            | ✅ Met | Template frontmatter preserved                           |
| FR-10 Path Traversal Protection     | ✅ Met | Security checks implemented                              |
| FR-11 Convention Discovery          | ✅ Met | `<type>.template.md` convention                          |
| FR-12 Code Fence Protection         | ✅ Met | Markers in code fences ignored                           |
| FR-13 Duplicate Section ID Detect   | ✅ Met | Raises explicit error                                    |
| FR-14 Missing Required Sections     | ✅ Met | Warning emitted for unfilled required sections           |
| FR-15 Marker-to-Marker Boundaries   | ✅ Met | Section spans defined by markers                         |
| FR-16 check/fix uses document_types | ✅ Met | Both commands use document_types                         |
| FR-17 Invalid Template File         | ✅ Met | `INVALID_TEMPLATE_FILE` error                            |
| WP-3 Built-in Templates             | ✅ Met | ADR, PRD, FDD templates with sections                    |
| WP-7 Migration Tooling              | ✅ Met | `meminit migrate-templates` implemented (spec-010)       |

### 1.4 PRD-007: Project State Dashboard

| Phase | Requirement                          | Status | Notes                                                                                      |
| ----- | ------------------------------------ | ------ | ------------------------------------------------------------------------------------------ |
| 1     | State file support                   | ✅ Met | `project-state.yaml` schema and validation in doctor                                       |
| 2     | Index merge                          | ✅ Met | `--impl-state` filtering, JSON output with impl_state                                      |
| 3     | Table view (catalogue.md)            | ✅ Met | Generated with grouping by Active Work/Governance Pending                                  |
| 4     | Kanban view (kanban.md + kanban.css) | ✅ Met | HTML board with semantic sections, accessible, CSS styling                                 |
| 5     | Integration (pre-commit/runbooks)    | ✅ Met | Pre-commit runs `meminit doctor` for state file; runbook-004 updated (P4.1, P4.2 complete) |

---

## 2. Known Issues

### 2.1 UI/UX Improvements

| Issue                         | Severity | Description                                                | Status |
| ----------------------------- | -------- | ---------------------------------------------------------- | ------ |
| Empty violation table display | Low      | `meminit check` shows empty table when no violations found | Open   |

---

## 3. Deferred Work

### 3.1 Org-Level Configuration (PRD-001)

**Item:** Org-level config file (`org-docops.config.yaml`)

**See:** [Plan-006: Atomic Task List](plan-006-atomic-task-list.md) - Tasks 3.1-3.4

**Priority:** Low

### 3.2 PRD-006: Missing JSON Field

**Item:** `rendered_content` field in `meminit new` JSON output

**Status:** ✅ Complete (P1.1, P1.2)

**See:** [Plan-006: Atomic Task List](plan-006-atomic-task-list.md) - Tasks 1.1-1.3

**Notes:** Field renamed from `content` to `rendered_content` in NewDocumentResult; JSON output now matches PRD-006 spec.

### 3.3 PRD-006: Migration Tooling

**Item:** `meminit migrate-templates` command

**Status:** ✅ Complete (P2)

**See:** [Plan-006: Atomic Task List](plan-006-atomic-task-list.md) - Tasks 2.1-2.5; [spec-010](docs/20-specs/spec-010-template-migration.md)

**Notes:** Command implemented with config migration, placeholder syntax migration, and dry-run support.

### 3.4 PRD-007: Integration

**Item:** Pre-commit hook for project-state.yaml

**Status:** ✅ Complete (P4.1, P4.2)

**See:** [Plan-006: Atomic Task List](plan-006-atomic-task-list.md) - Tasks 4.1-4.2; [runbook-004](docs/60-runbooks/runbook-004-ci-cd-enforcement.md)

**Notes:** `install-precommit` now runs `meminit doctor` for project-state.yaml; operator workflow documented in runbook.

---

## 4. Technical Debt

| Item                       | Description                                      | Priority |
| -------------------------- | ------------------------------------------------ | -------- |
| CLI test coverage          | `src/meminit/cli/main.py` has ~20% coverage      | Medium   |
| Concurrency stress testing | N7 (locking) needs concurrent invocation testing | Medium   |

**See:** [Plan-006: Atomic Task List](plan-006-atomic-task-list.md) - Tasks 5.1-5.2

---

## 5. History

| Version | Date       | Author | Changes                                                         |
| ------- | ---------- | ------ | --------------------------------------------------------------- |
| 0.1     | 2026-03-07 | Kilo   | Initial version; document PRD implementation status             |
| 0.2     | 2026-03-07 | Kilo   | Add PRD-006 implementation status                               |
| 0.3     | 2026-03-07 | Kilo   | Add PRD-007 status; reference task list                         |
| 0.4     | 2026-03-07 | Kilo   | Mark P1.1, P1.2, P2, P4.1, P4.2 complete; update deferred items |
