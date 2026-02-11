---
document_id: MEMINIT-SPEC-003
owner: DocOps Working Group
status: Draft
version: 0.4
last_updated: 2025-12-30
title: Compliance Checker Specification
type: SPEC
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-003
> **Owner:** DocOps Working Group
> **Status:** Draft
> **Version:** 0.4
> **Type:** SPEC

# Compliance Checker Specification

## 1. Overview

The `meminit check` command is the primary enforcement mechanism for DocOps standards.

## 2. Inputs

- `root_dir`: Path to repository root (default: `.`).
- `docops.config.yaml` (optional): When present, `meminit check` reads it to determine:
  - `namespaces` (optional): when provided, Meminit treats each namespace as a governed docs root. Each namespace may define:
    - `name` (identifier used in reports and index)
    - `docs_root` (where governed docs live)
    - `repo_prefix` (used for ID generation/migration workflows)
  - `docs_root` (single-root mode; default: `docs/`)
  - `schema_path` (default: `{docs_root}/00-governance/metadata.schema.json` in single-root mode)
  - `index_path` (optional): repository-level location of the index artifact, used by `index/resolve/identify/link`
  - `excluded_paths` (paths to skip during scanning; defaults include `{docs_root}/00-governance/templates/`)
- `excluded_filename_prefixes` (filename prefixes to skip within `{docs_root}`; defaults include `WIP-`)
  - `type_directories` (type → expected folder mapping used for directory warnings)
- `format`: Output format (`text`, `json`, or `md`).

## 3. Validation Rules

### 3.1 ID Validation

- **Regex:** Must match `^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$`.
- **Uniqueness:** ID must be unique within the scanned scope.
- **Namespace prefix (monorepo mode):** When `namespaces` are configured, `document_id` MUST start with the namespace `repo_prefix` (rule: `ID_PREFIX`).
- **Immutability:** (Future) Check against git history if possible, or index.

### 3.2 Frontmatter Validation

- **Parser:** Must parse standard YAML frontmatter (between `---`).
  _ **Schema:**
  _ Required fields are defined by `docs/00-governance/metadata.schema.json` (currently: `document_id`, `type`, `title`, `status`, `version`, `last_updated`, `owner`, `docops_version`).
  _ YAML scalars are normalized before schema validation for known fields that YAML commonly coerces (e.g., `last_updated`, `version`, `docops_version`).
  _ Schema load failures are repository-level:
  _ `SCHEMA_MISSING`: schema file is missing.
  _ `SCHEMA_INVALID`: schema file exists but is unreadable/invalid JSON/invalid Draft 7 schema.
  When schema is missing/invalid, `meminit check` reports the repository-level violation once and continues non-schema checks.

### 3.3 Link Validation

- **Scope:** Markdown inline links `[text] (target)` (**reference links are superseded/out of scope in v0.1**).
- **Internal Links:**
  - Must resolve to a file that exists.
  - Should use relative paths (e.g., `../folder/doc.md`).
  - Anchors are allowed (`#anchor`) and are ignored for file existence checks.
- **ID Links:** (Future) Support `[text] (MEM-ADR-001)` resolution via Index.

## 4. Output Format

### 4.1 JSON (Agent/CI)

```json
{
  "output_schema_version": "1.0",
  "status": "failed",
  "violations": [
    {
      "file": "docs/00-governance/bad-doc.md",
      "line": 1,
      "rule": "ID_FORMAT",
      "message": "ID 'BAD-1' does not match regex.",
      "severity": "error"
    }
  ]
}
```

### 4.2 Text (Human)

```text
[ERROR] docs/00-governance/bad-doc.md:1 - ID 'BAD-1' does not match regex.
...
Found 1 error(s) in 50 files.
```

### 4.3 Markdown (Human review in PRs)

```md
# Meminit Compliance Check

- Status: failed
- Violations: 1

## Violations

| Severity | Rule      | File                          | Line | Message                          |
| -------- | --------- | ----------------------------- | ---- | -------------------------------- |
| error    | ID_FORMAT | docs/00-governance/bad-doc.md | 1    | ID 'BAD-1' does not match regex. |
```

## 5. Error Handling & Severity

- **Error:** Blocks usage/CI (e.g., Invalid ID, Broken Link, Missing Schema).
- **Warning:** Non-blocking but requires attention (e.g., File read error, Deprecation).
- **Config Missing:** If `docops.config.yaml` is absent, defaults are used (the checker still runs).
