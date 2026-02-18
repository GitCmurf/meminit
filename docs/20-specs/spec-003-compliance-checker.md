---
document_id: MEMINIT-SPEC-003
owner: DocOps Working Group
status: Draft
version: 0.9
last_updated: 2026-02-18
title: Compliance Checker Specification
type: SPEC
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-003
> **Owner:** DocOps Working Group
> **Status:** Draft
> **Version:** 0.9
> **Type:** SPEC

# Compliance Checker Specification

## 1. Overview

The `meminit check` command is the primary enforcement mechanism for DocOps standards.

## 2. Inputs

- `root_dir`: Path to repository root (default: `.`).
- `docops.config.yaml` (required): `meminit check` reads it to determine:
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
- If missing, `meminit check` fails with `CONFIG_MISSING` using the standard
  error envelope for the selected output format.
  - **JSON:** `{"output_schema_version":"2.0","success":false,"error":{"code":"CONFIG_MISSING","message":"Repository not initialized: missing docops.config.yaml. Run 'meminit init' first.","details":{"missing_file":"docops.config.yaml"}}}`
  - **Text:** `[ERROR CONFIG_MISSING] Repository not initialized: missing docops.config.yaml. Run 'meminit init' first.`
  - **Markdown:** `# Meminit Error` with `Code: CONFIG_MISSING` and the message.
- `format`: Output format (`text`, `json`, or `md`).
- `--strict`: Boolean flag (default: false) that promotes warnings (e.g., files
  outside `docs_root`) to errors during validation.

## 2.1 Targeted Validation (PATHS)

`meminit check` accepts optional PATHS (files or glob patterns). When PATHS are
provided, only matched files are validated. Any path that escapes the repository
root fails with `PATH_ESCAPE`. For a single missing path, the error envelope is
returned with `FILE_NOT_FOUND` using the standard error envelope (no
`files_checked` counts). Files outside the configured `docs_root` are
warnings unless `--strict` is set, in which case they become errors.

Single-path semantics apply **only** when exactly one PATH argument is provided.
Multi-path semantics apply when two or more PATHS are provided, even if some
patterns match nothing. The mode is determined by the number of PATH arguments,
not by match results. When multiple PATHS are provided and some are missing,
each missing path is reported as a per-file violation with `FILE_NOT_FOUND`.

Single-path missing file example (JSON):

```json
{
  "output_schema_version": "2.0",
  "success": false,
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "File not found: docs/missing.md",
    "details": { "path": "docs/missing.md" }
  }
}
```

For multi-path invocations, missing files are reported as per-file violations
with `code: FILE_NOT_FOUND` (not a top-level error envelope). Example:

```json
{
  "output_schema_version": "2.0",
  "success": false,
  "files_checked": 0,
  "files_passed": 0,
  "files_failed": 0,
  "missing_paths_count": 2,
  "schema_failures_count": 0,
  "warnings_count": 0,
  "violations_count": 2,
  "files_with_warnings": 0,
  "files_outside_docs_root_count": 0,
  "checked_paths_count": 2,
  "violations": [
    {
      "path": "docs/missing-1.md",
      "violations": [
        { "code": "FILE_NOT_FOUND", "message": "File not found: docs/missing-1.md" }
      ]
    },
    {
      "path": "docs/missing-2.md",
      "violations": [
        { "code": "FILE_NOT_FOUND", "message": "File not found: docs/missing-2.md" }
      ]
    }
  ]
}
```

Counter semantics:

- `files_checked`: existing markdown files actually parsed and validated.
- `files_failed`: only existing files with error-level findings.
- `missing_paths_count`: unresolved targeted path arguments.
- `schema_failures_count`: repository-level schema failures.
- `violations_count`: all emitted violations (including repository-level and missing-path).
- `success`: false if file-level failures, missing paths, or schema failures exist, or strict mode promotes warnings.

## 3. Validation Rules

### 3.1 ID Validation

- **Regex:** Must match `^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$`.
- **Uniqueness:** ID must be unique within the scanned scope.
- **Namespace prefix (monorepo mode):** When `namespaces` are configured, `document_id` MUST start with the namespace `repo_prefix` (rule: `ID_PREFIX`).
- **Immutability:** (Future) Check against git history if possible, or index.

### 3.2 Frontmatter Validation

- **Parser:** Must parse standard YAML frontmatter (between `---`).
- **Schema:**
  - Required fields are defined by `docs/00-governance/metadata.schema.json` (currently: `document_id`, `type`, `title`, `status`, `version`, `last_updated`, `owner`, `docops_version`).
  - YAML scalars are normalized before schema validation for fields that YAML commonly coerces:
    - `last_updated`: `datetime`/`date` objects → ISO 8601 date string (`YYYY-MM-DD`).
    - `version`, `docops_version`, and any `*_version` fields: integers/floats → strings.
      Integers are normalized to a dotted form (`2` → `"2.0"`, `3` → `"3.0"`), and
      floats preserve their decimal form (`2.5` → `"2.5"`). Only numeric scalars are
      normalized; other scalar types (including booleans) are not valid inputs and will
      fail schema validation for these fields.
      Rationale: the schema expects a major.minor string, so integer inputs are padded
      with `.0` to retain semver-like structure.
  - Example normalization:
    - Input YAML: `last_updated: 2026-02-17`, `version: 2.0`, `docops_version: 2`
    - Normalized: `last_updated: "2026-02-17"`, `version: "2.0"`, `docops_version: "2.0"`
  - Schema load failures are repository-level:
    - `SCHEMA_MISSING`: schema file is missing.
    - `SCHEMA_INVALID`: schema file exists but is unreadable/invalid JSON/invalid Draft 7 schema.
- When schema is missing/invalid, `meminit check` reports the repository-level violation once and continues non-schema checks. In JSON output, this appears as a normal
  `violations` entry whose `path` is the schema file path and whose inner `violations`
  array contains `SCHEMA_MISSING` or `SCHEMA_INVALID`.

### 3.3 Link Validation

- **Scope:** Markdown inline links `[text] (target)` (**reference links are superseded/out of scope in v0.1**).
- **Internal Links:**
  - Must resolve to a file that exists.
  - Should use relative paths (e.g., `../folder/doc.md`).
- Anchors (`#anchor`) are stripped for file existence validation; anchor targets are not checked in v0.9.
- **ID Links:** (Future) Support `[text] (MEM-ADR-001)` resolution via Index.

### 3.4 Validation Warnings and `--strict`

The compliance checker can emit warnings for non-blocking issues. Current
warnings include:

- `OUTSIDE_DOCS_ROOT` (targeted path outside configured docs root)
- `FILENAME_CONVENTION` (filename not kebab-case)
- `DIRECTORY_MATCH` (document type not in expected directory)

When `--strict` is set, **all warnings are promoted to errors**: they are counted
in `files_failed`, included in `violations`, and cause a non-zero exit. The
`warnings_count` value therefore reflects post-promotion warnings.

## 4. Output Format

### 4.1 JSON (Agent/CI)

All JSON responses include `output_schema_version`; consumers should use this
field to select the correct parsing logic.

```json
{
  "output_schema_version": "2.0",
  "success": false,
  "files_checked": 1,
  "files_passed": 0,
  "files_failed": 1,
  "missing_paths_count": 0,
  "schema_failures_count": 0,
  "warnings_count": 0,
  "violations_count": 1,
  "files_with_warnings": 0,
  "files_outside_docs_root_count": 0,
  "checked_paths_count": 1,
  "violations": [
    {
      "path": "docs/00-governance/bad-doc.md",
      "document_id": "MEMINIT-ADR-001",
      "violations": [
        {
          "code": "ID_REGEX",
          "message": "ID 'BAD-1' does not match format 'REPO-TYPE-SEQ'."
        }
      ]
    }
  ]
}
```

Repository-level schema failure example (JSON):

```json
{
  "output_schema_version": "2.0",
  "success": false,
  "files_checked": 1,
  "files_passed": 1,
  "files_failed": 0,
  "missing_paths_count": 0,
  "schema_failures_count": 1,
  "warnings_count": 0,
  "violations_count": 1,
  "files_with_warnings": 0,
  "files_outside_docs_root_count": 0,
  "checked_paths_count": 2,
  "violations": [
    {
      "path": "docs/00-governance/metadata.schema.json",
      "violations": [
        {
          "code": "SCHEMA_MISSING",
          "message": "Schema file missing at 'docs/00-governance/metadata.schema.json'"
        }
      ]
    }
  ]
}
```

When warnings are present, `warnings` is emitted as a flat array. Each warning
object includes required fields `code`, `path`, and `message`, and may include
an optional integer `line`.

```json
{
  "output_schema_version": "2.0",
  "success": true,
  "files_checked": 1,
  "files_passed": 1,
  "files_failed": 0,
  "missing_paths_count": 0,
  "schema_failures_count": 0,
  "warnings_count": 1,
  "violations_count": 0,
  "files_with_warnings": 1,
  "files_outside_docs_root_count": 1,
  "checked_paths_count": 1,
  "violations": [],
  "warnings": [
    {
      "code": "OUTSIDE_DOCS_ROOT",
      "path": "README.md",
      "message": "File is outside configured docs_root",
      "line": 1
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
- **Warning:** Non-blocking but requires attention (e.g., `FILENAME_CONVENTION`, `DIRECTORY_MATCH`, `OUTSIDE_DOCS_ROOT`).
- **Config Missing:** If `docops.config.yaml` is absent, `meminit check` fails
  with `CONFIG_MISSING`.
