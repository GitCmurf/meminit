---
document_id: MEMINIT-PLAN-002
owner: DocOps Working Group
status: Draft
version: 0.1
last_updated: 2025-12-14
title: DocOps Compliance Testing Suite
type: PLAN
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PLAN-002
> **Owner:** DocOps Working Group
> **Status:** Draft
> **Version:** 0.1
> **Type:** PLAN

# DocOps Compliance Testing Suite

## 0. Implementation Status (As of 2025-12-14)

This plan is **partially implemented**. Items below are marked as:

- **Met**: Implemented in code + covered by tests.
- **Exceeded**: Implemented with additional safeguards beyond this plan.
- **Superseded**: Replaced by a different design/behavior; this plan is no longer the source of truth for that item.

## 1. Objective

To implement a robust, automated testing suite that verifies all governed documents within the repository comply with the **DocOps Constitution v2.0** and **Repository Standards**. This suite will serve as a gatekeeper for quality and consistency.

## 2. Scope

The compliance suite will validate:

1.  **Document IDs**: Format (`REPO-TYPE-SEQ`), uniqueness, and immutability.
2.  **Frontmatter**: Presence, schema validation (required fields, types, enums), and `docops_version` alignment.
3.  **File Naming**: ASCII characters, lowercase kebab-case convention.
4.  **Directory Structure**: Correct placement of documents based on their `Type`.
5.  **Referential Integrity**: Validity of `superseded_by`, `related_ids`, and inline markdown links to files (e.g., `[Link] (../path/to/doc.md)`).

### 2.1 Scope-to-Implementation Mapping

- **Met**: ID format + uniqueness via `meminit check` and `IdValidator` tests.
- **Met**: Frontmatter presence + JSON schema validation via `SchemaValidator` tests.
- **Exceeded**: Frontmatter validation normalizes YAML date/version scalars before schema checks to avoid false positives.
- **Met**: Filename convention warnings + `meminit fix` rename sanitization.
- **Met**: Directory mapping warnings for known types; type casing is tolerated (e.g., `adr`, `ADR`).
- **Superseded**: “Immutability” is not validated in v0.1 (git-history enforcement deferred).
- **Superseded**: “ID links” (e.g., `[X] (MEMINIT-ADR-001)`) are not resolved in v0.1; only filesystem-relative links are validated.

## 3. Implementation Strategy

### 3.1 Architecture (Clean + DCI)

We will follow **Clean Architecture** and **DCI (Data, Context, Interaction)** principles to ensure modularity and testability.

- **Data (Entities):** Anemic dataclasses representing `Document`, `Frontmatter`, `Violation`.
- **Context (Use Cases):** Orchestrators for specific goals (e.g., `ValidateRepoContext`, `CheckDocumentContext`).
- **Interaction (Roles):** Logic modules (e.g., `IdValidator`, `LinkChecker`) that operate on Data within a Context.
- **Interface Adapters:** CLI (`meminit.cli`), Pre-commit hooks.

### 3.2 Core Logic (`meminit.check`)

We will implement the `meminit check` command (CLI + core use case) that performs the following checks:

#### A. Static Analysis (Regex & Schema)

- **ID Regex:** `^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$` (e.g., `MEMINIT-ADR-001`, `MEMINIT-STRAT-001`).
- **Frontmatter Schema:** Validate against `docs/00-governance/metadata.schema.json`.

#### B. Contextual Analysis

- **Uniqueness:** Ensure no two files claim the same `document_id`.
- **Directory Mapping:** Verify `type: ADR` is in `docs/45-adr/`.
- **Filename Convention:** Warn if filenames contain spaces or uppercase letters.

#### C. Link Analysis (New)

- **Resolution:** Scan markdown bodies for `[Label] (Target)`-style links.
- **Validation:** Verify `Target` exists as a file path (relative to the source file). Fragments (`#section`) are ignored for existence checks.

### 3.3 Execution Modes

1.  **CLI Command:** `meminit check` (human table output or `--format json`).
2.  **Pre-commit Hook:** **Superseded** (not implemented in v0.1).

## 4. Documentation & TDD Plan

Following the "Meminit Way":

1.  **Design:** `docs/30-design/design-001-compliance-architecture.md` (High-level).
2.  **Spec:** `docs/20-specs/spec-003-compliance-checker.md` (Detailed behavior).
3.  **Tests:** `tests/unit/` (TDD first) and `tests/integration/`.
4.  **Runbooks:** `docs/60-runbooks/runbook-001-running-compliance.md`.

## 5. Test Cases (The "Suite")

| ID      | Test Name                       | Description                                                                      | Pass Condition                       | Fail Condition                                                |
| :------ | :------------------------------ | :------------------------------------------------------------------------------- | :----------------------------------- | :------------------------------------------------------------ |
| **T1**  | `test_id_format`                | Validates Document ID regex.                                                     | `MEMINIT-ADR-001`                    | `MEM-ADR-1`, `MEMINIT-Ingest-ADR-001`                         |
| **T2**  | `test_frontmatter_exists`       | Checks for YAML block.                                                           | File starts with `---`               | No frontmatter                                                |
| **T3**  | `test_required_fields`          | Checks for all required keys.                                                    | All keys present                     | Missing `owner` or `version`                                  |
| **T4**  | `test_type_enum`                | **Superseded** (type allowlisting is not enforced by schema in v0.1).            | —                                    | —                                                             |
| **T5**  | `test_status_enum`              | Validates `status` against allowlist.                                            | `status: Draft`                      | `status: Wip`                                                 |
| **T6**  | `test_directory_match`          | Checks file path vs Type.                                                        | `docs/45-adr/adr-001.md` (Type: ADR) | `docs/10-prd/adr-001.md` (Type: ADR)                          |
| **T7**  | `test_id_uniqueness`            | Checks for duplicate IDs.                                                        | Unique ID                            | Two files with `MEMINIT-ADR-001`                              |
| **T8**  | `test_filename_convention`      | Checks filename format.                                                          | `my-doc.md`                          | `My Doc.md`                                                   |
| **T9**  | `test_link_resolution`          | Checks internal links.                                                           | `[Link] (../foo.md)` (exists)        | `[Link] (../missing.md)`                                      |
| **T10** | `test_docops_version_alignment` | Ensures `docops_version` matches the repo-supported DocOps Constitution version. | `docops_version: 2.0`                | Missing `docops_version` or unsupported version (e.g., `1.0`) |

## 6. Roadmap

1.  **Approve Plan:** Review and sign off on this document.
2.  **Design & Spec:** Create `design-001` and `spec-003`.
3.  **Scaffold:** Create `src/meminit/` structure.
4.  **TDD Loop:** Write test -> Write code -> Refactor (DCI/Clean).
5.  **Configure Hook:** Add to `.pre-commit-config.yaml`.
6.  **Run & Fix:** Run against current repo.
