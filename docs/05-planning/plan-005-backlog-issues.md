---
document_id: MEMINIT-PLAN-005
type: PLAN
title: "WIP Backlog & Issues Tracker"
status: Draft
version: "0.1"
last_updated: 2026-03-07
owner: GitCmurf
docops_version: "2.0"
area: Planning
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PLAN-005
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
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
| F4.1 `meminit check` linting                     | ✅ Met                 | Full schema validation                                                  |
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

---

## 2. Known Issues

### 2.1 UI/UX Improvements

| Issue                         | Severity | Description                                                | Status |
| ----------------------------- | -------- | ---------------------------------------------------------- | ------ |
| Empty violation table display | Low      | `meminit check` shows empty table when no violations found | Open   |

**Notes:**

- Consider conditionally rendering the violations table only when violations exist
- This is a cosmetic issue only; functionality is correct

---

## 3. Deferred Work

### 3.1 Org-Level Configuration

**Item:** Org-level config file (`org-docops.config.yaml`)

**Description:**
Implement organisation-level configuration that defines:

- Allowed document types
- Default directories
- Other org-wide parameters
- Multiple repository inheritance from org-level config

**Rationale for Deferral:**

- Current implementation satisfies single-organisation use cases
- Multi-tenant/org scenario is not a near-term requirement
- Can be added when demand materialises

**Priority:** Low

---

## 4. Technical Debt

| Item                       | Description                                      | Impact | Priority |
| -------------------------- | ------------------------------------------------ | ------ | -------- |
| CLI test coverage          | `src/meminit/cli/main.py` has ~20% coverage      | Low    | Medium   |
| Concurrency stress testing | N7 (locking) needs concurrent invocation testing | Medium | Medium   |

---

## 5. History

| Version | Date       | Author | Changes                                             |
| ------- | ---------- | ------ | --------------------------------------------------- |
| 0.1     | 2026-03-07 | Kilo   | Initial version; document PRD implementation status |
