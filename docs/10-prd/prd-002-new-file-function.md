---
document_id: MEMINIT-PRD-002
type: PRD
title: "Enhanced Document Factory (meminit new)"
status: Draft
version: "0.11"
last_updated: 2026-02-13
owner: GitCmurf
docops_version: "2.0"
area: CLI
---

# PRD: Enhanced Document Factory (meminit new)

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PRD-002
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.11
> **Last Updated:** 2026-02-13
> **Type:** PRD

## 1. Executive Summary

This PRD defines requirements for enhancing and hardening the `meminit new` command to serve two distinct user personas with high-performance UX:

1. **Human users** creating governed documents interactively
2. **Agentic AI coding assistants** creating documentation synchronously with code

The current implementation provides basic functionality but lacks the observability, error recovery, and structured output required for production-grade agent integration. It also lacks the interactive features that would improve human developer experience.

---

## 2. Current State Analysis

### 2.1 Current Implementation

**Entry Point:** `src/meminit/cli/main.py:771-795`

**Core Logic:** `src/meminit/core/use_cases/new_document.py`

**Current CLI Signature:**

```bash
meminit new <TYPE> <TITLE> [--root .] [--namespace <name>]
```

**Current Flow:**

1. Validate root path exists
2. Normalize doc type (e.g., `adr` → `ADR`, `GOVERNANCE` → `GOV`)
3. Load repository config from `docops.config.yaml`
4. Resolve namespace (default or specified)
5. Determine target directory via type-to-directory mapping
6. Generate document ID by scanning existing files (filename regex + frontmatter fallback)
7. Generate filename as `{type}-{seq}-{slug}.md`
8. Load template and apply placeholder substitutions
9. Create frontmatter with required fields
10. Write file with symlink escape protection

### 2.2 Current Strengths

| Feature                   | Implementation                                       |
| ------------------------- | ---------------------------------------------------- |
| Auto-incrementing IDs     | ✅ Scans filenames and frontmatter                   |
| Symlink escape protection | ✅ `ensure_safe_write_path()`                        |
| Template support          | ✅ Case-insensitive lookup, placeholder substitution |
| Monorepo namespaces       | ✅ `--namespace` flag                                |
| File overwrite protection | ✅ Raises `FileExistsError`                          |
| Custom type directories   | ✅ Via `docops.config.yaml:type_directories`         |

### 2.3 Current Limitations

| Limitation                           | Impact                                                  |
| ------------------------------------ | ------------------------------------------------------- |
| `owner` always `__TBD__`             | Human must edit manually; agent cannot set meaningfully |
| No JSON output                       | Agent cannot parse result programmatically              |
| No `--area` flag                     | Cannot set optional schema-allowed field                |
| No `--description` flag              | Cannot set optional schema-allowed field                |
| No `--status` flag                   | Always defaults to "Draft"                              |
| No `--owner` flag                    | Always defaults to `__TBD__`                            |
| Template strips existing frontmatter | Template frontmatter placeholders are ignored           |
| No dry-run mode                      | Cannot preview without side effects                     |
| No verbose mode                      | Limited visibility into decision-making                 |
| Error messages are text-only         | Not machine-parseable                                   |
| No related_ids support               | Cannot link to existing documents at creation           |
| Missing visible metadata block       | `<!-- MEMINIT_METADATA_BLOCK -->` not generated         |

---

## 3. User Personas & Expectations

### 3.1 Persona A: Human Developer

**Scenario:** A developer needs to create an ADR for a technical decision they just made.

**Expectations:**

- **Speed:** Complete document creation in < 10 seconds
- **Clarity:** Understand what will be created before committing
- **Flexibility:** Set all relevant metadata without post-editing
- **Guidance:** Discover valid types, areas, and templates
- **Recovery:** Easily correct mistakes (wrong type, typo in title)
- **Integration:** File opens in editor automatically

**Current Experience Gaps:**

1. Must run `meminit check` to see what types are valid
2. Cannot set `owner` without editing file
3. No preview of generated file before creation
4. No automatic editor launch
5. No confirmation prompts for destructive operations

### 3.2 Persona B: Agentic AI Coding Assistant

**Scenario:** An agent creates documentation synchronously with code changes (e.g., creating an ADR when changing architecture).

**Expectations:**

- **Structured Output:** JSON with created path, ID, and metadata
- **Idempotency:** Predictable behavior when re-run
- **Atomicity:** Clear success/failure with no partial state
- **Observability:** Understand why decisions were made
- **Programmability:** Set all metadata fields via flags
- **Error Recovery:** Machine-parseable errors with actionable codes
- **Linking:** Reference existing documents at creation time

**Current Experience Gaps:**

1. No `--format json` flag (noted as non-goal in FDD-004 but critical for agents)
2. No `--owner` flag — agent cannot set meaningful owner
3. No `--area`, `--description`, `--keywords`, `--related_ids` flags
4. Error messages are human text, not structured
5. Cannot specify exact ID (agent may need deterministic IDs)
6. No return of created document path in parseable format

---

## 4. Architecture & Design Principles

### 4.1 Library-First Architecture

Meminit MUST maintain a strict separation between CLI and core logic:

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Layer (thin)                        │
│  - Argument parsing (click)                                 │
│  - Output formatting (text/json)                            │
│  - Exit code mapping                                        │
│  - Editor invocation                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Layer (thick)                       │
│  - Use Cases (NewDocumentUseCase, CheckUseCase)            │
│  - Domain models (Document, Metadata)                       │
│  - Validation services                                      │
│  - Repository abstractions                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                       │
│  - File system access (through Repository pattern)          │
│  - Schema loading                                           │
│  - Template rendering                                       │
│  - Logging/observability                                    │
└─────────────────────────────────────────────────────────────┘
```

**Rationale:** Agents, CI hooks, and other tools MUST be able to invoke meminit programmatically without subprocess overhead. The CLI is a thin adapter over a reusable library.

### 4.2 Single Responsibility

| Component            | Single Responsibility                      |
| -------------------- | ------------------------------------------ |
| `NewDocumentUseCase` | Orchestrate document creation workflow     |
| `IdGenerator`        | Generate unique, sequential document IDs   |
| `MetadataBuilder`    | Construct schema-valid frontmatter         |
| `TemplateRenderer`   | Load and substitute template placeholders  |
| `PathResolver`       | Determine target paths from type/namespace |
| `OutputFormatter`    | Format results as text or JSON             |
| `ErrorHandler`       | Map exceptions to structured errors        |

### 4.3 Dependency Injection

All external dependencies MUST be injected for testability:

```python
class NewDocumentUseCase:
    def __init__(
        self,
        config_loader: ConfigLoader,
        id_generator: IdGenerator,
        template_renderer: TemplateRenderer,
        file_repository: FileRepository,
        validator: SchemaValidator,
    ):
        ...
```

**Rationale:** Enables unit testing with mocks; supports future extensions (e.g., database-backed storage, remote templates).

### 4.4 Interface Segregation

Define narrow, purpose-specific interfaces:

```python
class IdGenerator(Protocol):
    def generate(self, doc_type: str, target_dir: Path) -> str: ...

class FileRepository(Protocol):
    def exists(self, path: Path) -> bool: ...
    def read(self, path: Path) -> str: ...
    def write(self, path: Path, content: str) -> None: ...
    def glob(self, pattern: str) -> list[Path]: ...
```

### 4.5 Battle-Tested Standard Libraries

| Concern         | Standard/Battle-Tested Library             |
| --------------- | ------------------------------------------ |
| CLI framework   | `click` (used)                             |
| JSON schema     | `jsonschema` (used)                        |
| YAML parsing    | `pyyaml` (used)                            |
| Frontmatter     | `python-frontmatter` (used)                |
| Path handling   | `pathlib` (stdlib)                         |
| Glob patterns   | `pathlib.Path.glob()` or `glob` (stdlib)   |
| Regex           | `re` (stdlib)                              |
| Data validation | `pydantic` or `dataclasses` (stdlib)       |
| Logging         | `logging` (stdlib) with structlog optional |
| Testing         | `pytest` with `pytest-mock`                |
| Exit codes      | `os.EX_*` constants (stdlib)               |

---

## 5. API Contract

### 5.1 Programmatic API

Agents and tools MUST be able to use meminit as a library:

> **Note — Scope:** `MeminitClient` is an aspirational convenience wrapper and is NOT a deliverable of this PRD. The current programmatic entry point is `NewDocumentUseCase(root_dir).execute(doc_type, title)`. This PRD extends `NewDocumentUseCase` with additional parameters. A future PRD may introduce `MeminitClient` as a unified facade.

```python
from meminit import MeminitClient

client = MeminitClient(root_dir="/path/to/repo")

result = client.new_document(
    doc_type="ADR",
    title="Use Redis as Cache",
    owner="agent-orchestrator",
    area="INGEST",
    output_format="dict",  # or 'path' for just the Path object
)

# result:
# {
#     "success": True,
#     "path": Path("docs/45-adr/adr-042-use-redis-cache.md"),
#     "document_id": "MEMINIT-ADR-042",
#     ...
# }
```

### 5.2 JSON Output Schema Versioning

JSON output MUST include a schema version for forward compatibility.

> **Note — Field Naming:** The existing codebase uses `output_schema_version` (see `output_contracts.py`). This PRD adopts the same field name for consistency. All new JSON output MUST use `output_schema_version`, not `schema_version`.

```json
{
  "output_schema_version": "1.0",
  "success": true,
  "path": "docs/45-adr/adr-042-use-redis-cache.md",
  "document_id": "MEMINIT-ADR-042",
  ...
}
```

**Contract:** Breaking changes to JSON output increment major version. Additive changes increment minor version.

### 5.3 Exit Code Contract

Exit codes MUST follow `sysexits.h` conventions:

| Code | Constant       | Meaning                         |
| ---- | -------------- | ------------------------------- |
| 0    | `EX_OK`        | Success                         |
| 64   | `EX_USAGE`     | Invalid command/argument        |
| 65   | `EX_DATAERR`   | Input data error (invalid type) |
| 66   | `EX_NOINPUT`   | Input file not found            |
| 73   | `EX_CANTCREAT` | Cannot create output file       |
| 77   | `EX_NOPERM`    | Permission denied / path escape |

### 5.4 Error Code Enumeration

Error codes MUST be defined as a single CLI-wide enum (not ad-hoc strings). The enum covers all `meminit` subcommands; individual commands use a subset (see F9.1 for `meminit new`-specific codes, Section 11.5 for `meminit check`-specific codes).

```python
from enum import Enum

class ErrorCode(str, Enum):
    # Shared (meminit new + meminit check)
    DUPLICATE_ID = "DUPLICATE_ID"
    INVALID_ID_FORMAT = "INVALID_ID_FORMAT"
    INVALID_FLAG_COMBINATION = "INVALID_FLAG_COMBINATION"
    CONFIG_MISSING = "CONFIG_MISSING"       # docops.config.yaml not found
    PATH_ESCAPE = "PATH_ESCAPE"
    # meminit new only (F9.1)
    UNKNOWN_TYPE = "UNKNOWN_TYPE"
    UNKNOWN_NAMESPACE = "UNKNOWN_NAMESPACE"
    FILE_EXISTS = "FILE_EXISTS"
    INVALID_STATUS = "INVALID_STATUS"
    INVALID_RELATED_ID = "INVALID_RELATED_ID"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    LOCK_TIMEOUT = "LOCK_TIMEOUT"           # N7.3: concurrent ID generation lock failure
    # meminit check only (Section 11.5)
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    MISSING_FRONTMATTER = "MISSING_FRONTMATTER"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_FIELD = "INVALID_FIELD"
    OUTSIDE_DOCS_ROOT = "OUTSIDE_DOCS_ROOT"
    DIRECTORY_MISMATCH = "DIRECTORY_MISMATCH"
```

---

## 6. Requirements

### 6.1 Functional Requirements

#### F1. Structured Output for Agent Integration

> **Note — Flag Naming:** The existing `meminit` CLI uses `--format` for output format selection (`check`, `doctor`, `scan`, `fix`, `migrate-ids`). For consistency, `meminit new` MUST also use `--format json` (not `--output json`). All references in this PRD to `--output json` should be read as `--format json`.

**F1.1** `--format json` flag MUST return a JSON object with:

```json
{
  "output_schema_version": "1.0",
  "success": true,
  "path": "docs/45-adr/adr-001-use-redis-cache.md",
  "document_id": "MEMINIT-ADR-001",
  "type": "ADR",
  "title": "Use Redis as Cache",
  "status": "Draft",
  "version": "0.1",
  "owner": "agent-orchestrator",
  "area": "INGEST",
  "last_updated": "2026-02-12",
  "docops_version": "2.0",
  "description": null,
  "keywords": [],
  "related_ids": []
}
```

> **Note:** All fields set by metadata flags (F2) MUST be included in the JSON response, even if null/empty.

**F1.2** JSON output MUST be valid single-line JSON for easy parsing (no pretty-printing).

**F1.3** JSON errors MUST include error code and message:

```json
{
  "output_schema_version": "1.0",
  "success": false,
  "error": {
    "code": "UNKNOWN_TYPE",
    "message": "Unknown document type: XYZ. Valid types: ADR, PRD, FDD, ...",
    "details": {
      "valid_types": ["ADR", "PRD", "FDD", ...]
    }
  }
}
```

**F1.4** JSON output envelope MUST be explicit and stable:

- Success responses **for document creation** MUST include: `output_schema_version`, `success`, `path`, `document_id`, `type`, `title`, `status`, `version`, `owner`, `area`, `last_updated`, `docops_version`, `description`, `keywords`, `related_ids`. Other operations (`--dry-run`, `--list-types`, `meminit check`) define their own response shapes (see F3.2, F4.2, F10.7); all responses share the `output_schema_version` and `success` fields.
- Error responses MUST include: `output_schema_version`, `success`, and `error` with `code` + `message`.
- Optional error diagnostics MUST be nested under `error.details` to avoid top-level contract drift.

**F1.5** When `--format json` is used, stdout MUST contain exactly one JSON object and no additional text. Any logs, warnings, or verbose output MUST be written to stderr (or captured in structured logging via `MEMINIT_LOG_FORMAT=json`).

#### F2. Extended Metadata Flags

**F2.1** `--owner <owner>` flag MUST set the `owner` frontmatter field.

**F2.2** `--area <area>` flag MUST set the optional `area` frontmatter field.

**F2.3** `--description <text>` flag MUST set the optional `description` frontmatter field.

**F2.4** `--status <status>` flag MUST set status (default: "Draft"). MUST validate against the canonical status vocabulary (`Draft`, `In Review`, `Approved`, `Superseded`) as defined in `metadata.schema.json`. Application-level validation MUST fail fast with `INVALID_STATUS` so users receive a clear error before schema validation. Setting `--status "Superseded"` on a new document without a corresponding `superseded_by` field SHOULD emit a warning but MUST NOT be rejected (the user may set `superseded_by` via manual edit).

**F2.5** `--keywords <word>` flag MUST be repeatable and set `keywords` array. Each flag occurrence accepts exactly one value (e.g., `--keywords cache --keywords redis --keywords performance`).

**F2.6** `--related-ids <id>` flag MUST be repeatable and set `related_ids` array. Each flag occurrence accepts exactly one ID. MUST validate ID format (`^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$`). Referenced documents are NOT required to exist (agents may create documents in planned order with forward references). Duplicate values SHOULD be de-duplicated while preserving first-seen order.

**F2.7** All flag-set values MUST be validated against `metadata.schema.json`.

**F2.8** When `--owner` is not provided, the `owner` field MUST be resolved using the following precedence chain (first non-empty value wins):

1. `--owner <owner>` CLI flag (highest priority)
2. `MEMINIT_DEFAULT_OWNER` environment variable
3. `default_owner` field in `docops.config.yaml`
4. `__TBD__` (sentinel fallback)

`--verbose` MUST log which resolution layer provided the `owner` value. This chain mirrors standard configuration precedence (cf. `git config` layering). The `__TBD__` sentinel ensures `meminit check` flags documents where no owner has been configured.

#### F3. Preview and Dry-Run Modes

**F3.1** `--dry-run` flag MUST output what would be created without writing file.

**F3.2** `--dry-run --format json` MUST return JSON with `would_create` object:

```json
{
  "output_schema_version": "1.0",
  "success": true,
  "dry_run": true,
  "would_create": {
    "path": "docs/10-prd/prd-003-new-feature.md",
    "document_id": "MEMINIT-PRD-003",
    "type": "PRD",
    "title": "New Feature"
  }
}
```

> **Note:** The `would_create` object above shows the minimum required fields. When metadata flags are provided (e.g., `--owner`, `--area`), the `would_create` object SHOULD include those fields to give a complete preview of the document that would be created.

**F3.3** `--verbose` flag MUST output decision reasoning (directory chosen, ID sequence found, template used). When combined with `--format json`, verbose output MUST be written to stderr (see F1.5).

#### F4. Type Discovery

**F4.1** `--list-types` flag MUST output valid document types with their target directories.

**F4.2** `--list-types --format json` MUST return structured type mapping:

```json
{
  "output_schema_version": "1.0",
  "success": true,
  "types": [
    { "type": "ADR", "directory": "docs/45-adr/" },
    { "type": "PRD", "directory": "docs/10-prd/" }
  ]
}
```

**F4.3** `--list-types` is a no-side-effect discovery mode. If `<TYPE>`/`<TITLE>` positional arguments are also provided, command MUST fail with `EX_USAGE` and `INVALID_FLAG_COMBINATION`.

#### F5. Deterministic ID Mode

**F5.1** `--id <id>` flag MUST allow specifying exact document ID (with collision check). The full ID (e.g., `MEMINIT-ADR-099`) MUST be provided. The type segment in the ID MUST match the positional `<TYPE>` argument (e.g., `meminit new ADR "Title" --id MEMINIT-ADR-099` is valid; `meminit new ADR "Title" --id MEMINIT-PRD-099` MUST error with `INVALID_ID_FORMAT`).

**F5.2** If `--id` conflicts with existing, MUST error with `DUPLICATE_ID` code.

#### F6. Visible Metadata Block Generation

**F6.1** When template contains `<!-- MEMINIT_METADATA_BLOCK -->`, MUST replace it with a generated visible metadata block.

**F6.2** Visible block MUST use blockquote format matching existing conventions:

```markdown
> **Document ID:** MEMINIT-ADR-042
> **Owner:** agent-orchestrator
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-02-12
> **Type:** ADR
```

#### F7. Template Enhancement

**F7.1** Template frontmatter fields (beyond placeholders) MUST be preserved if not overridden by generated frontmatter. This is a behaviour change from current implementation which strips all template frontmatter.

**F7.2** Templates MUST support `{area}`, `{owner}`, `{description}` placeholders.

**F7.3** Templates MUST support `{keywords}` and `{related_ids}` as array placeholders. Arrays MUST be rendered as comma-separated strings in template body text (e.g., `cache, redis, performance`) and as YAML lists in frontmatter.

#### F8. Interactive Mode (Human-Focused)

**F8.1** `--interactive` flag MUST prompt for missing required metadata (at minimum: `owner`; optionally: `area`, `description`).

**F8.2** Interactive mode MUST support shell-level tab-completion for document types via `click.shell_complete` (Bash/Zsh/Fish). In-prompt tab-completion is out of scope for Phase 3.

**F8.3** `--edit` flag MUST open created file in `$EDITOR` (or `$VISUAL`) after creation. If neither is set, MUST emit a warning and skip editor launch (not error).

**F8.4** `--interactive` and `--format json` MUST be treated as incompatible modes in this PRD scope. Combining them MUST fail with `INVALID_FLAG_COMBINATION` (future work may add a non-interactive JSON prompts protocol).

**F8.5** `--edit` MUST be incompatible with `--dry-run` and `--format json`. Combining them MUST fail with `INVALID_FLAG_COMBINATION`. When `--edit` is provided and creation succeeds (including idempotent success for an identical existing file), the editor MUST open the resolved path; on failure, no editor launch occurs.

#### F9. Error Codes

**F9.1** `meminit new` MUST use the following error codes (subset of the CLI-wide `ErrorCode` enum defined in Section 5.4):

| Code                       | Meaning                            | HTTP Analogue |
| -------------------------- | ---------------------------------- | ------------- |
| `UNKNOWN_TYPE`             | Document type not configured       | 400           |
| `UNKNOWN_NAMESPACE`        | Namespace not found                | 400           |
| `DUPLICATE_ID`             | Document ID already exists         | 409           |
| `FILE_EXISTS`              | Target file already exists         | 409           |
| `INVALID_ID_FORMAT`        | Provided ID doesn't match pattern  | 400           |
| `INVALID_STATUS`           | Status not in enum                 | 400           |
| `INVALID_RELATED_ID`       | Related ID format invalid          | 400           |
| `TEMPLATE_NOT_FOUND`       | Template file missing              | 500           |
| `SCHEMA_INVALID`           | Generated frontmatter fails schema | 500           |
| `PATH_ESCAPE`              | Symlink escape detected            | 403           |
| `INVALID_FLAG_COMBINATION` | Invalid flag/argument combination  | 400           |
| `LOCK_TIMEOUT`             | Concurrent lock acquisition failed | 503           |
| `CONFIG_MISSING`           | `docops.config.yaml` not found     | 500           |

**F9.2** JSON output MUST include `error.code` field.

**F9.3** Text output MUST include error code in brackets: `[ERROR UNKNOWN_TYPE] Unknown document type...`

### 6.2 Non-Functional Requirements

#### N1. Performance

**N1.1** ID generation MUST complete in < 100ms for directories with < 1000 documents.

**N1.2** Full command execution MUST complete in < 500ms for standard cases.

#### N2. Reliability

**N2.1** Command MUST be atomic — either file is created completely or not at all.

**N2.2** Partial writes MUST NOT occur on failure.

**N2.3** Generated frontmatter MUST pass `meminit check` immediately after creation.

#### N3. Compatibility

**N3.1** Existing CLI signature MUST remain valid (backward compatible).

**N3.2** New flags MUST be optional with sensible defaults.

**N3.3** JSON output MUST NOT change existing text output behavior unless `--format json` is specified.

#### N4. Testability

**N4.1** All new flags MUST have unit tests.

**N4.2** JSON output MUST have integration tests.

**N4.3** Error code paths MUST have test coverage.

#### N5. Observability (Infrastructure Requirement)

**N5.1** All operations MUST emit structured logs (JSON) when `MEMINIT_LOG_FORMAT=json`.

**N5.2** Logs MUST include: operation, duration_ms, success, error_code (if failed).

**N5.3** Debug mode (`MEMINIT_DEBUG=1`) MUST emit trace-level information including:

- Config file paths loaded
- Template resolution steps
- ID generation algorithm decisions

> **Note:** `--debug` is NOT a separate CLI flag. Debug-level logging is activated solely via the `MEMINIT_DEBUG=1` environment variable. The `--verbose` flag (F3.3) provides user-facing decision reasoning; `MEMINIT_DEBUG=1` provides developer-facing trace-level detail.

**N5.4** Logs MUST NOT include file contents (PII/security concern).

**N5.5** Logs SHOULD include a correlation key (`run_id`) so CI systems and agent orchestrators can trace one invocation across multiple log lines.

#### N6. Idempotency (Infrastructure Requirement)

**N6.1** `meminit new --id <id>` with the same ID MUST be idempotent: if the target file already exists with byte-identical content, the command MUST return success (exit code 0) and the same JSON output as a fresh creation. If the file exists but content differs, the command MUST error with `FILE_EXISTS`. This reconciles with F9.1: `FILE_EXISTS` applies only when content differs.

> **Note:** Since `last_updated` is date-granular (`YYYY-MM-DD`), the byte-identical comparison holds for same-day re-runs. Cross-day re-runs with the same `--id` will differ in `last_updated` and correctly return `FILE_EXISTS`. Agents requiring cross-day idempotency SHOULD check for file existence before invoking `meminit new`.

**N6.2** `meminit new --dry-run` MUST be idempotent (no side effects).

**N6.3** `meminit check` MUST be idempotent (read-only, deterministic results).

**N6.4** `meminit new` without `--id` is intentionally non-idempotent (it allocates the next sequence). This behavior MUST be documented in CLI help and JSON output docs to prevent agent misuse.

#### N7. Concurrency Safety (Infrastructure Requirement)

**N7.1** Multiple concurrent `meminit new` invocations MUST NOT create duplicate IDs.

**N7.2** ID generation MUST use file locking or atomic operations:

- Prefer `O_EXCL` (exclusive create) for file writes
- Or use directory-level locking via `fcntl.flock()` (stdlib, Unix-only)

> **Note — Dependency:** This PRD uses stdlib-only approaches (`O_EXCL`, `fcntl.flock()`) to avoid new runtime dependencies. Windows portability is out of scope for this PRD. If Windows support is needed in future, `portalocker` may be introduced as an optional dependency in a separate PRD.

**N7.3** On lock acquisition failure, MUST error with `LOCK_TIMEOUT` code (not silent failure or race condition).

**N7.4** Lock acquisition timeout MUST default to 3000ms and be configurable via `MEMINIT_LOCK_TIMEOUT_MS` for CI tuning.

**N7.5** Lock scope MUST be per target type directory (e.g., one lock for `docs/45-adr/`, another for `docs/10-prd/`) to reduce unnecessary contention.

#### N8. Error Recovery (Infrastructure Requirement)

**N8.1** On any failure, the system MUST leave no partial artifacts (no orphan files, no corrupted frontmatter).

**N8.2** If file creation fails after ID allocation, the atomic `O_EXCL` file creation ensures no orphan ID reservation is needed. If the file write itself fails (e.g., disk full), the partial file MUST be removed during cleanup (N8.3). There is no separate ID reservation mechanism — the filesystem IS the reservation.

**N8.3** Cleanup MUST be automatic — no manual intervention required.

**N8.4** If cleanup itself fails, command MUST return non-zero and emit structured error details including both the original failure and cleanup failure.

---

## 7. Target User Experience Flows

### 7.1 Human Developer Flow (Enhanced)

```bash
# Discover types
$ meminit new --list-types
Valid types: ADR, PRD, FDD, GOV, STRAT, PLAN, TASK, GUIDE, REF
  ADR     → docs/45-adr/
  PRD     → docs/10-prd/
  FDD     → docs/50-fdd/
  ...

# Create with metadata
$ meminit new ADR "Use Redis as Cache" \
    --owner "alice@example.com" \
    --area INGEST \
    --related-ids MEMINIT-PRD-001 \
    --edit
Created ADR: docs/45-adr/adr-042-use-redis-cache.md
Opening in editor...

# Preview before creating
$ meminit new PRD "New Feature" --dry-run --verbose
Would create: docs/10-prd/prd-003-new-feature.md
  ID: MEMINIT-PRD-003 (next in sequence)
  Type: PRD
  Directory: docs/10-prd/
  Template: docs/00-governance/templates/template-001-prd.md
```

### 7.2 Agent Flow (Enhanced)

```bash
# Structured creation
$ meminit new ADR "Use Redis as Cache" \
    --owner "agent-orchestrator" \
    --area INGEST \
    --description "Caching layer for API responses" \
    --keywords cache --keywords redis --keywords performance \
    --related-ids MEMINIT-PRD-001 \
    --format json
{"output_schema_version":"1.0","success":true,"path":"docs/45-adr/adr-042-use-redis-cache.md","document_id":"MEMINIT-ADR-042",...}

# Error handling
$ meminit new XYZ "Invalid Type" --format json
{"output_schema_version":"1.0","success":false,"error":{"code":"UNKNOWN_TYPE","message":"Unknown document type: XYZ","details":{"valid_types":["ADR","PRD",...]}}}

# Deterministic ID for known document
$ meminit new ADR "Known Decision" --id MEMINIT-ADR-099 --format json
{"output_schema_version":"1.0","success":true,"path":"docs/45-adr/adr-099-known-decision.md","document_id":"MEMINIT-ADR-099",...}
```

---

## 8. Comparison Matrix

| Feature                    | Current               | Human Target    | Agent Target |
| -------------------------- | --------------------- | --------------- | ------------ |
| `--format json`            | ❌                    | N/A             | ✅ Required  |
| `--owner`                  | ❌ (always `__TBD__`) | ✅ Nice-to-have | ✅ Required  |
| `--area`                   | ❌                    | ✅ Nice-to-have | ✅ Required  |
| `--description`            | ❌                    | N/A             | ✅ Required  |
| `--keywords`               | ❌                    | N/A             | ✅ Required  |
| `--related-ids`            | ❌                    | ✅ Nice-to-have | ✅ Required  |
| `--status`                 | ❌ (always Draft)     | ✅ Nice-to-have | ✅ Required  |
| `--dry-run`                | ❌                    | ✅ Required     | ✅ Required  |
| `--verbose`                | ❌                    | ✅ Required     | ✅ Required  |
| `--list-types`             | ❌                    | ✅ Required     | ✅ Required  |
| `--id`                     | ❌                    | N/A             | ✅ Required  |
| `--edit`                   | ❌                    | ✅ Required     | N/A          |
| `--interactive`            | ❌                    | ✅ Nice-to-have | N/A          |
| Error codes                | ❌                    | ✅ Nice-to-have | ✅ Required  |
| Visible metadata block     | ❌                    | ✅ Required     | N/A          |
| Template frontmatter merge | ❌                    | ✅ Required     | ✅ Required  |

---

## 9. Implementation Phases

### Phase 1: Agent Integration Essentials (P0)

Priority: Required for agent adoption

| Requirement                 | Effort |
| --------------------------- | ------ |
| F1: `--format json`         | M      |
| F2: Extended metadata flags | M      |
| F9: Error codes             | S      |

### Phase 2: Observability & Control (P1)

Priority: Required for production reliability

| Requirement                  | Effort |
| ---------------------------- | ------ |
| F3: `--dry-run`, `--verbose` | S      |
| F4: `--list-types`           | S      |
| F5: `--id` deterministic     | S      |
| N5: structured observability | S      |
| N7: concurrency safety       | M      |
| N8: error recovery           | S      |

### Phase 3: Human Experience (P2)

Priority: Improves developer experience

| Requirement                   | Effort |
| ----------------------------- | ------ |
| F6: Visible metadata block    | M      |
| F7: Template enhancement      | M      |
| F8: `--interactive`, `--edit` | M      |

### Phase 4: Validation Workflow Extension (P3)

Priority: Companion work for create-then-validate agent loops

| Requirement                   | Effort |
| ----------------------------- | ------ |
| F10: targeted `meminit check` | M      |

---

## 10. Success Metrics

| Metric                      | Target                                                                                       |
| --------------------------- | -------------------------------------------------------------------------------------------- |
| Agent creation completeness | 100% of F2 metadata fields settable via flags and reflected in JSON output                   |
| JSON contract reliability   | 100% of success/error responses validate against `output_schema_version: 1.0` contract tests |
| Dry-run safety              | 0 filesystem writes in `--dry-run` mode across integration tests                             |
| Type discoverability        | Human can list valid types/directories with one command (`meminit new --list-types`)         |
| Human workflow efficiency   | Human can create, open, and start editing in <= 10 seconds on local machine                  |
| Governance compliance       | 100% of generated documents pass `meminit check` in integration tests                        |
| Error contract quality      | 100% of failure paths emit stable machine-parseable `error.code`                             |
| New-path test coverage      | >= 90% line coverage for new/modified `meminit new` code paths                               |
| Concurrency correctness     | 0 duplicate IDs across stress test with >= 20 concurrent `meminit new` invocations           |

---

## 11. Extension: `meminit check` Targeted File Validation

> **Scope Note:** This section specifies enhancements to `meminit check` (a separate command from `meminit new`). These requirements (F10.x) are included here as companion work because they directly support the create-then-validate workflow (Section 7.2). Implementation MAY be tracked as a separate work item.

### 11.1 Problem Statement

Currently, `meminit check` validates the entire repository. When a user or agent wants to validate only specific files (e.g., a newly created document), they cannot do so. The command rejects extra arguments:

```bash
$ meminit check docs/10-prd/prd-002-new-file-function.md
Error: Got unexpected extra argument (docs/10-prd/prd-002-new-file-function.md)
```

This is inefficient for:

- **Agents** that create a single document and want immediate validation
- **Humans** iterating on a specific document
- **CI pipelines** running incremental validation on changed files only

### 11.2 Requirements

#### F10. Targeted File Validation

**F10.1** `meminit check` MUST accept optional file path arguments:

```bash
meminit check                          # Current behavior: validate all
meminit check docs/45-adr/adr-001.md   # Validate single file
meminit check docs/45-adr/*.md         # Validate files matching glob pattern
meminit check file1.md file2.md        # Validate multiple specific files
```

**F10.2** File paths MUST support:

- Relative paths (relative to `--root` or current working directory)
- Absolute paths
- Glob patterns (wildcards: `*`, `**`, `?`, `[...]`)
- Multiple paths in a single invocation

**F10.3** Glob expansion MUST follow shell conventions:

- `*.md` — match files in specified directory
- `**/*.md` — recursive match
- `docs/**/adr-*.md` — match files matching pattern in any subdirectory

**F10.4** When files are specified, `--root` MUST still be used to:

- Resolve relative paths
- Locate `docops.config.yaml` for schema and config
- Enforce path safety (no escape outside root). If a path escapes root, command MUST fail with `PATH_ESCAPE`.

**F10.5** Files outside the configured `docs_root` MUST generate a warning (not error) unless `--strict` is set:

```bash
$ meminit check README.md --format json
{"output_schema_version":"1.0","success":true,"warnings":[{"code":"OUTSIDE_DOCS_ROOT","path":"README.md","message":"File is outside configured docs_root"}]}
```

> **Note:** The `warnings` array is present only when warnings exist; it is omitted (not empty) on clean runs. Each warning object MUST include `code`, `path`, and `message`.

**F10.6** Non-existent files MUST be reported:

```bash
$ meminit check docs/nonexistent.md --format json
{"output_schema_version":"1.0","success":false,"error":{"code":"FILE_NOT_FOUND","message":"File not found: docs/nonexistent.md","details":{"path":"docs/nonexistent.md"}}}
```

> **Note:** For a single-path invocation, the error envelope above MUST be used. For multi-path invocations, each missing file MUST be reported as a per-file violation (see F10.7), with `code: FILE_NOT_FOUND` and `document_id: null` (or omitted).

**F10.7** `--format json` MUST return structured results for targeted validation:

```json
{
  "output_schema_version": "1.0",
  "success": false,
  "files_checked": 3,
  "files_passed": 2,
  "files_failed": 1,
  "violations": [
    {
      "path": "docs/45-adr/adr-003.md",
      "document_id": "MEMINIT-ADR-003",
      "violations": [
        {
          "field": "owner",
          "message": "owner is required",
          "code": "MISSING_FIELD"
        }
      ]
    }
  ]
}
```

> **Semantics:** `success` is `true` only when all checked files pass validation (i.e., `files_failed == 0`). The exit code mirrors this: `EX_OK` (0) for all-pass, `EX_DATAERR` (65) when violations are found.

> **Envelope conventions for `meminit check --format json`:**
>
> - **Fatal errors** (e.g., `CONFIG_MISSING`, `PATH_ESCAPE`) that prevent any validation return the standard error envelope: `{output_schema_version, success: false, error: {code, message, details}}` — same shape as F10.6. Per-file errors (e.g., `FILE_NOT_FOUND` for one file in a multi-file invocation) are reported as per-file violations within the result shape above; the F10.6 flat error shape is reserved for errors that prevent the command from running at all.
> - **Collection conventions:** The `violations` array is always present (empty `[]` when all files pass). The `warnings` array is present only when warnings exist; it is omitted on clean runs (see F10.5 note).
> - **Coexistence:** When a check run produces both warnings and violations, both arrays appear in the response. `success` reflects violations only — warnings do not affect `success` (unless `--strict` promotes them to errors per F10.5).
> - **Missing files:** When a missing file is reported as a per-file violation, `document_id` MUST be `null` (or omitted), and the violation code MUST be `FILE_NOT_FOUND`.

**F10.8** Text output for targeted validation MUST show per-file summary:

```bash
$ meminit check docs/45-adr/*.md
Checking 3 files...

✓ docs/45-adr/adr-001-use-redis.md
✓ docs/45-adr/adr-002-migrate-db.md
✗ docs/45-adr/adr-003-new-feature.md
  - Missing required field: owner

1 of 3 files have violations.
```

### 11.3 CLI Signature

```bash
meminit check [PATHS...] [OPTIONS]

Arguments:
  PATHS              One or more files or glob patterns to validate.
                     If omitted, validates all governed documents.

Options:
  --root PATH        Repository root directory [default: .]
  --format FORMAT    Output format: text, json [default: text]
  --strict           Treat warnings as errors
  --quiet            Only show failures (exit code indicates pass/fail)
```

### 11.4 Implementation Notes

- Use `pathlib.Path.glob()` or `glob.glob()` for pattern expansion
- Click's `@click.argument` with `nargs=-1` for multiple paths
- Reuse existing validation logic from `CheckUseCase`
- Add file filtering layer before validation loop

### 11.5 Error Codes for Check Command

| Code                       | Meaning                           |
| -------------------------- | --------------------------------- |
| `CONFIG_MISSING`           | `docops.config.yaml` not found    |
| `FILE_NOT_FOUND`           | Specified file does not exist     |
| `OUTSIDE_DOCS_ROOT`        | File outside configured docs root |
| `MISSING_FRONTMATTER`      | File lacks YAML frontmatter       |
| `MISSING_FIELD`            | Required field missing            |
| `INVALID_FIELD`            | Field value violates schema       |
| `INVALID_FLAG_COMBINATION` | Invalid flag/argument combination |
| `INVALID_ID_FORMAT`        | document_id doesn't match pattern |
| `DUPLICATE_ID`             | document_id not unique            |
| `DIRECTORY_MISMATCH`       | Type doesn't match directory      |
| `PATH_ESCAPE`              | Path escapes repository root      |

### 11.6 User Experience Flows

**Agent creating and validating a single document:**

```bash
$ meminit new ADR "Use Redis" --format json
{"output_schema_version":"1.0","success":true,"path":"docs/45-adr/adr-042-use-redis.md",...}

$ meminit check docs/45-adr/adr-042-use-redis.md --format json
{"output_schema_version":"1.0","success":true,"files_checked":1,"files_passed":1,"files_failed":0,"violations":[]}
```

**Human iterating on a specific document:**

```bash
$ meminit check docs/10-prd/prd-002-new-file-function.md
✓ docs/10-prd/prd-002-new-file-function.md
No violations found.
```

**CI running incremental validation on changed files:**

```bash
$ meminit check docs/45-adr/*.md docs/10-prd/*.md --quiet
✗ docs/45-adr/adr-003.md: Missing required field: owner
```

---

## 12. Out of Scope

- `--template` flag for custom template selection (use config)
- `--assignee` or `--approvers` workflow features
- Document content generation (LLM-assisted writing)
- Web UI or API server
- Database-backed document storage
- Real-time collaboration features

---

## 13. Dependencies

- Existing: `click`, `pyyaml`, `python-frontmatter`, `rich`
- No new runtime dependencies required (concurrency uses stdlib `fcntl`/`O_EXCL`)
- Test dependencies may need `pytest-json-report` for structured test output

---

## 14. References

- MEMINIT-FDD-004: Current feature design document. **Note:** This PRD supersedes FDD-004's scope for `meminit new`. FDD-004 explicitly listed `--output json` as a non-goal; this PRD makes structured output a P0 requirement. FDD-004 remains valid as a reference for the original design rationale.
- MEMINIT-PRD-001: Meminit Tooling Ecosystem PRD
- MEMINIT-STRAT-001: Project Meminit Vision (alignment: Pillar 3, Agentic Collaboration)
- MEMINIT-SPEC-002: Meminit Tech Stack (alignment: Python CLI stack and testing model)
- `docs/00-governance/metadata.schema.json`: Schema definition
- `docs/00-governance/templates/template-001-adr.md`: ADR template with placeholders

---

## 15. Implementation Readiness Gate

Engineering handoff is approved only when all gate criteria pass:

- P0/P1 requirements in Section 9 are implemented with tests.
- JSON output contract tests pass for success, dry-run, and error paths.
- Concurrency stress test proves no duplicate ID issuance.
- `meminit check` passes on generated fixture repositories.
- CLI help text reflects all flag precedence and incompatibility rules.

---

## 16. Revision History

| Version | Date       | Author         | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| :------ | :--------- | :------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 0.1     | 2026-02-12 | **TBD**        | Initial Draft                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 0.2     | 2026-02-12 | Gemini (Agent) | Refined for production readiness, added detailed engineering constraints.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 0.3     | 2026-02-12 | Augment Agent  | Engineering readiness review. Fixed 20 gaps: standardised `--format` flag naming, aligned `output_schema_version` field, added missing error codes (`LOCK_TIMEOUT`, `CONFIG_MISSING`), resolved `portalocker` dependency contradiction, clarified `MeminitClient` scope, completed JSON schema, specified F5/F6/F7/F8 edge cases, reconciled N6.1 idempotency with `FILE_EXISTS`, softened N8.2 ID reservation, clarified `--debug` vs `--verbose`, fixed section numbering (7→15), added FDD-004 supersession note. Verdict: Conditional GO.                                                                 |
| 0.4     | 2026-02-12 | Codex (GPT-5)  | Comprehensive implementation-handoff review. Clarified JSON envelope contracts (success/error/dry-run/list-types), disambiguated repeatable flag syntax (`--keywords`, `--related-ids`), added explicit flag incompatibility handling (`INVALID_FLAG_COMBINATION`), strengthened observability/idempotency/concurrency/error-recovery NFRs (N5.5, N6.4, N7.4-N7.5, N8.4), made success metrics measurable, added MEMINIT-SPEC-002 alignment reference, and added explicit implementation readiness gate. Verdict: Near-Ready GO (pending implementation execution).                                           |
| 0.5     | 2026-02-13 | Augment Agent  | Final quality review for showcase excellence. Added F2.8 owner resolution fallback chain (`--owner` → `MEMINIT_DEFAULT_OWNER` → `docops.config.yaml:default_owner` → `__TBD__`). Fixed F1.4 missing `area` in success envelope field list. Clarified F2.4 status validation wording (subsequently corrected in v0.6). Clarified §5.4 ErrorCode enum is CLI-wide with per-command subsets. Added §5.4/F9.1 cross-reference scope notes. Added F3.2 dry-run metadata preview note. Fixed run-on sentence in §1. Verdict: Showcase-Ready.                                                                        |
| 0.6     | 2026-02-13 | Codex (GPT-5)  | Production robustness pass. Added JSON stdout isolation requirement (F1.5), corrected F2.4 to align with schema-enforced status enum, expanded CLI-wide ErrorCode enum to cover check-specific codes, and aligned JSON examples in Section 7.2 with the `output_schema_version` contract. Verdict: Ready.                                                                                                                                                                                                                                                                                                     |
| 0.7     | 2026-02-13 | Augment Agent  | Contract consistency pass. Fixed F1.3/§7.2 error examples to nest `valid_types` under `error.details` (aligning with F1.4 rule). Scoped F1.4 success envelope to document-creation responses (dry-run, list-types, and check define their own shapes). Fixed F10.7 `success: true` → `false` when `files_failed > 0` and added semantics note. Added N6.1 date-granularity note for cross-day idempotency. Reorganised §5.4 ErrorCode enum comments into Shared/new-only/check-only groups. Added F10.5 `warnings` array contract note. Corrected v0.5 revision history entry.                                |
| 0.8     | 2026-02-13 | Codex (GPT-5)  | Robustness cleanup. Made PATH_ESCAPE a shared error code, specified PATH_ESCAPE for check path safety (F10.4), and expanded Section 11.5 to include shared error codes relevant to `meminit check` (CONFIG_MISSING, INVALID_FLAG_COMBINATION, PATH_ESCAPE).                                                                                                                                                                                                                                                                                                                                                   |
| 0.9     | 2026-02-13 | Codex (GPT-5)  | Added explicit incompatibility rules for `--edit` with `--dry-run` and `--format json` (F8.5), and clarified editor launch behavior on success vs failure.                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| 0.10    | 2026-02-13 | Augment Agent  | Final contract consistency and completeness pass (5 findings: 3 Substantive, 2 Minor). Fixed F10.6 error example to nest `path` under `error.details` (aligning with F1.4 rule — same class as v0.7 Finding 1). Added comprehensive check envelope conventions note after F10.7: documented fatal-error vs per-file-violation response shape distinction, `violations`/`warnings` collection conventions, and coexistence semantics. Fixed §11.6 all-pass example to include `files_failed:0` (matching F10.7 contract). Added F1.5 cross-reference to F3.3 for `--verbose` + `--format json` stderr routing. |
| 0.11    | 2026-02-13 | Codex (GPT-5)  | Clarified F10.6 and F10.7 missing-file handling: single-path uses error envelope; multi-path reports `FILE_NOT_FOUND` as per-file violations with `document_id` null/omitted. |
