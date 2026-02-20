---
document_id: MEMINIT-FDD-001
type: FDD
title: Compliance Checker (meminit check)
status: Draft
version: 0.7
last_updated: 2026-02-19
owner: GitCmurf
docops_version: 2.0
---

# FDD: Compliance Checker (meminit check)

## Feature Description

Provide a deterministic repository scanner that validates DocOps compliance for governed markdown documents under `docs/`.

## User Value

- Enables CI gating and local hygiene checks.
- Provides machine-readable results for agents via JSON output.

## Functional Scope (v0.1)

- Scan `docs/` recursively for `*.md` (excluding `docs/00-governance/templates/`).
- Validate:
  - Frontmatter existence (error)
  - Frontmatter schema compliance against `docs/00-governance/metadata.schema.json` (error)
  - `document_id` regex and uniqueness (error)
  - Filename convention `^[a-z0-9-]+\\.md$` (warning)
  - Directory mapping for known types (warning)
  - Markdown inline links to files (error), ignoring fragments (`#...`) for existence checks

## Functional Scope (v0.4)

- Targeted validation: `meminit check [PATHS...]` accepts relative paths,
  absolute paths, and glob patterns (including `**`).
- `--strict` promotes warnings (e.g., OUTSIDE_DOCS_ROOT) to errors.
- Fatal errors (e.g., PATH_ESCAPE, CONFIG_MISSING) return the standard
  error envelope in JSON mode (see **Standard Error Envelope (JSON)**).
- JSON output uses `success` with counts and per-file groups for
  `violations`. `warnings` are emitted as a flat list with `code`, `path`,
  and `message` and are included as `[]` when none are present.
- Markdown output (`--format md`) includes a top-level summary with status and
  counts, followed by per-file sections listing violations or warnings with
  code, path, and message; `--strict` promotes warnings to errors consistently
  with JSON/text.
- Text output includes per-file summaries for clean, warning, and error files.
- Output format defaults to text. `--format text` is accepted; `--format json`
  and `--format md` select structured outputs.

### Standard Error Envelope (JSON)

Fatal errors in JSON mode use a stable envelope with required fields:

- `output_schema_version` (string)
- `success` (boolean, `false`)
- `run_id` (string correlation key)
- `error.code` (string)
- `error.message` (string)
- `error.details` (object, optional)

Example:

```json
{
  "output_schema_version": "2.0",
  "success": false,
  "run_id": "a1b2c3d4",
  "error": {
    "code": "PATH_ESCAPE",
    "message": "Path '/etc/passwd' is outside repository root",
    "details": { "path": "/etc/passwd" }
  }
}
```

### Output Formats (Examples)

Text (default):

```text
✓ docs/10-prd/prd-002-new-file-function.md
No violations found.
```

JSON (`--format json`):

```json
{
  "output_schema_version": "2.0",
  "success": true,
  "files_checked": 1,
  "files_passed": 1,
  "files_failed": 0,
  "missing_paths_count": 0,
  "schema_failures_count": 0,
  "warnings_count": 0,
  "violations_count": 0,
  "files_with_warnings": 0,
  "files_outside_docs_root_count": 0,
  "checked_paths_count": 1,
  "violations": [],
  "warnings": [],
  "run_id": "a1b2c3d4"
}
```

Markdown (`--format md`):

```md
# Meminit Compliance Check

- Status: success
- Violations: 0
```

### Schema Version Transition (v1 -> v2)

`meminit check --format json` now emits `output_schema_version: "2.0"`.

What changed vs v1 for `check` payloads:

- Breaking: `output_schema_version` changed from `"1.0"` to `"2.0"`.
- Added top-level counters: `missing_paths_count`, `schema_failures_count`, `warnings_count`, `violations_count`, `files_with_warnings`, `files_outside_docs_root_count`, `checked_paths_count`.
- Added `run_id` correlation key.
- Clarified `files_checked` semantics: only existing markdown files actually parsed/validated.
- `warnings` in check result payloads are emitted as a flat array and included as `[]` when none are present.

Support/deprecation policy:

- v2 is authoritative for `check` outputs.
- v1 remains in use for non-migrated commands only; it is not used for `check`.
- Migration of other commands is tracked in planning/spec docs; no fixed v1 retirement date is set in this FDD.

Migration guidance for agent consumers:

- Branch parser logic on `output_schema_version`.
- For `check` v2 responses, consume the explicit counters and grouped `violations`.
- Keep v1 parsing for non-migrated commands until those commands are explicitly migrated.

Minimal mapping example (`check` success):

```text
v1: {"output_schema_version":"1.0","success":true,"files_checked":1,"files_passed":1,"files_failed":0,"violations":[]}
v2: {"output_schema_version":"2.0","success":true,"files_checked":1,"files_passed":1,"files_failed":0,"missing_paths_count":0,"schema_failures_count":0,"warnings_count":0,"violations_count":0,"files_with_warnings":0,"files_outside_docs_root_count":0,"checked_paths_count":1,"violations":[],"warnings":[],"run_id":"a1b2c3d4"}
```

### JSON Output Field Definitions

| Field                           | Type    | Semantics                                                                                                     |
| ------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------- |
| `output_schema_version`         | string  | Contract version for parsing.                                                                                 |
| `success`                       | boolean | `true` when no error-level findings (including strict-mode promotion).                                        |
| `files_checked`                 | integer | Existing markdown files actually parsed and validated.                                                        |
| `files_passed`                  | integer | Checked files with no error-level findings.                                                                   |
| `files_failed`                  | integer | Checked files with one or more error-level findings.                                                          |
| `missing_paths_count`           | integer | Targeted path args that did not resolve to existing files.                                                    |
| `schema_failures_count`         | integer | Repository-level schema failures (`SCHEMA_MISSING` / `SCHEMA_INVALID`).                                       |
| `warnings_count`                | integer | Total warning count emitted in `warnings`.                                                                    |
| `violations_count`              | integer | Total violation count emitted in `violations` (file-level + missing-path + repository-level schema failures). |
| `files_with_warnings`           | integer | Number of files with one or more warnings.                                                                    |
| `files_outside_docs_root_count` | integer | Number of checked files outside configured `docs_root`.                                                       |
| `checked_paths_count`           | integer | Number of resolved path arguments considered by targeted check; equals `files_checked` in full-repo mode.     |
| `violations`                    | array   | Grouped violations by path; each group contains one or more violation entries.                                |
| `warnings`                      | array   | Flat warning list (`code`, `path`, `message`, optional `line`).                                               |
| `run_id`                        | string  | Correlation key for logs/output from the same invocation.                                                     |

Relationship notes:

- `files_checked` and `checked_paths_count` differ in targeted mode when missing paths exist (`checked_paths_count` includes resolved path args considered; `files_checked` counts only existing files validated).
- `warnings_count` is warning-entry count; `files_with_warnings` is file count.
- `files_outside_docs_root_count` is tracked separately and may contribute to `warnings_count` (or to violations under `--strict`).
- `violations_count` includes schema and missing-path violations in addition to file-content violations.

### Error Codes and Warnings

| Code                | Severity                        | Trigger                                      | Remediation                                                |
| ------------------- | ------------------------------- | -------------------------------------------- | ---------------------------------------------------------- |
| `PATH_ESCAPE`       | Fatal                           | A PATH resolves outside the repository root. | Use a path under the repo root.                            |
| `CONFIG_MISSING`    | Fatal                           | `docops.config.yaml` is missing.             | Run `meminit init` or add config.                          |
| `OUTSIDE_DOCS_ROOT` | Warning (error with `--strict`) | Targeted file is outside `docs_root`.        | Move the file under `docs_root` or use `--strict` to fail. |

## Non-goals (v0.4)

- ID-to-path resolution for links (requires indexing).
- Anchor validation (`#heading`) correctness.
- Pre-commit / CI integration scaffolding.

## Inputs / Outputs

- Input: repo root directory and optional PATHS for targeted validation.
- Output: list of violations. CLI supports text, `--format json`, and `--format md`.

## Edge Cases

- YAML scalar coercions: unquoted `last_updated` dates and numeric `version`/`docops_version` are normalized before schema validation.
- Schema errors include field path context when possible (e.g., `title: ...`).
- Schema load failures are repository-level and do not flood per-document:
  - `SCHEMA_MISSING` when the schema file is missing.
  - `SCHEMA_INVALID` when the schema file is unreadable/invalid JSON/invalid Draft 7 schema.

## Implementation Notes

- Use case: `src/meminit/core/use_cases/check_repository.py`
- Validators: `src/meminit/core/services/validators.py`

## Tests

- Unit tests for schema validator, link checker, and repository checking live under `tests/core/`.
