---
document_id: MEMINIT-FDD-001
type: FDD
title: Compliance Checker (meminit check)
status: Draft
version: 0.5
last_updated: 2026-02-18
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
  and `message` when present.
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
  "output_schema_version": "1.0",
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
{"output_schema_version":"1.0","success":true,"files_checked":1,"files_passed":1,"files_failed":0,"violations":[]}
```

Markdown (`--format md`):

```md
# Meminit Compliance Check

- Status: success
- Violations: 0
```

### Error Codes and Warnings

| Code | Severity | Trigger | Remediation |
| --- | --- | --- | --- |
| `PATH_ESCAPE` | Fatal | A PATH resolves outside the repository root. | Use a path under the repo root. |
| `CONFIG_MISSING` | Fatal | `docops.config.yaml` is missing. | Run `meminit init` or add config. |
| `OUTSIDE_DOCS_ROOT` | Warning (error with `--strict`) | Targeted file is outside `docs_root`. | Move the file under `docs_root` or use `--strict` to fail. |

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
