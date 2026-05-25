---
document_id: MEMINIT-TASK-002
type: TASK
title: Architecture Refactoring
status: Draft
version: "0.1"
last_updated: "2026-05-25"
owner: GitCmurf
area: ADOPT
docops_version: "2.0"
template_type: task-standard
template_version: "2.0"
description: Decompose large files and establish ports/adapters architecture
keywords:
  - architecture
  - refactoring
  - p2
  - plan-016
---

> **Document ID:** MEMINIT-TASK-002
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1

# TASK: Architecture Refactoring

## 0. Executive Summary

This task consolidates the P2 architecture items from MEMINIT-TASK-001 (PLAN-016 QA Remediation) into a focused follow-up. The scope includes decomposing large files, removing dead code, and establishing explicit ports/adapters boundaries. These items were deferred from TASK-001 because they do not block launch and carry significant regression risk.

## 1. Review Basis

These items were identified as P2 in MEMINIT-TASK-001 ("PLAN-016 QA Remediation") with the following rationale:

- They do not block the v0.3.0-alpha launch
- They carry significant regression risk if not done carefully
- Better suited for a dedicated refactoring sprint post-launch
- Can be completed without impacting user workflows or the core feature set

Source inputs:
- MEMINIT-TASK-001 Section 4 "Work Items" (P2 items)
- Live repository inspection showing file sizes and duplication patterns
- Adversarial review feedback recommending "showcase excellence" over speed

## 2. Current State

### Large Files (Maintainability Risk)

| File | Lines | % of Package | Issue |
|------|-------|--------------|-------|
| `src/meminit/cli/main.py` | 4,614 | 87.9% | Entire CLI surface in one file, command logic mixed with wiring |
| `src/meminit/core/use_cases/index_repository.py` | 1,867 | - | Mixing indexing, catalog generation, kanban rendering, CSS, cache, filtering |
| `src/meminit/core/use_cases/new_document.py` | 1,314 | - | Template loading, ID resolution, filename generation, locking all inline |

### Dead Code

| Function | Location | Status |
|----------|----------|--------|
| `_apply_common_template_substitutions()` | `new_document.py:1030` | Never called, v1 legacy, should be removed |

### Duplicated Helpers

| Helper | Duplicate Locations | Impact |
|--------|---------------------|--------|
| `_id_type_segment()` | `new_document.py:1004`, `fix_repository.py:711` | Same ID type segment extraction logic |
| `_filter_index_edges` | `index_repository.py:121`, `main.py:389` | Same edge filtering for status/impl_state filtering |
| `_index_output_data` | `main.py:401` mirrors `_index_stream_data` | `index_repository.py:136` | Same index data structure building |

### Architecture Gaps

| Issue | Location | Observation |
|-------|----------|-------------|
| Empty adapters layer | `src/meminit/adapters/` (only `__init__.py`) | Package exists but unused |
| No explicit ports | Throughout | Filesystem, template, output use concrete services, not protocols |
| CLI direct coupling | `main.py` | Direct calls to use cases without port abstraction |

### Code Quality Metrics

- 3 files over 1,300 lines each
- Empty package signaling abandoned pattern
- No typed interfaces for external dependencies
- Mixed concerns in single files (UI + business logic + data formatting)

## 3. Work Items

### P2-01: Decompose `src/meminit/cli/main.py`

**Problem:** 4,614 lines in a single file makes review difficult and suggests poor separation of concerns. The file contains:
- Click command definitions (50+ commands)
- Command-specific flag handlers
- Common setup and output formatting
- Direct use case instantiation

**Proposed structure:**

```
src/meminit/cli/
  main.py                 (Command registration, common setup, ~300 lines)
  commands/
    __init__.py
    docops.py              (doctor, check, init)
    migration.py           (scan, fix, migrate-ids)
    creation.py            (new, adr new)
    resolution.py          (index, resolve, identify, link)
    state.py               (state set/list/next/blockers)
    protocol.py            (protocol check/sync)
    context.py             (context, org status/vendor)
  shared/
    __init__.py
    output_helpers.py      (Shared formatting for JSON/MD/text)
    correlation_id.py      (Run ID and timestamp management)
```

**Specific migrations:**

1. **Docops commands** → `cli/commands/docops.py`
   - `doctor`
   - `check`
   - `init`
   - Flag handlers for `--root`, `--strict`, `--output`

2. **Migration commands** → `cli/commands/migration.py`
   - `scan` (including `--plan`)
   - `fix` (including `--plan`, `--namespace`)
   - `migrate-ids` (including `--rewrite-references`)

3. **Creation commands** → `cli/commands/creation.py`
   - `new` (including all flags: `--owner`, `--area`, `--description`, `--status`, `--keywords`, `--related-ids`, `--id`, `--dry-run`, `--namespace`, `--list-types`)
   - `adr new`

4. **Resolution commands** → `cli/commands/resolution.py`
   - `index` (including `--output-catalog`, `--output-kanban`)
   - `resolve`, `identify`, `link`

5. **State commands** → `cli/commands/state.py`
   - `state set/list/next/blockers`

6. **Protocol commands** → `cli/commands/protocol.py`
   - `protocol check` / `protocol sync`

7. **Discovery commands** → `cli/commands/context.py`
   - `context`
   - `org status` / `org vendor`

**Shared extraction:**

8. **Output helpers** → `cli/shared/output_helpers.py`
   - JSON envelope formatting
   - MD table formatting
   - Text formatting
   - Streaming NDJSON handling

9. **Correlation ID** → `cli/shared/correlation_id.py`
   - `run_id` generation (UUIDv4)
   - `timestamp` handling
   - `--include-timestamp` flag logic

**Risk assessment:** Medium. This is a large file split, but Click's `@cli.group()` and `@command()` decorators are straightforward to move. The main risk is missing shared helpers or circular imports.

**Acceptance criteria:**
- `main.py` under 1,000 lines (only command registration)
- All existing tests in `tests/adapters/test_cli.py` pass
- No circular imports between command modules
- `run_id` and `timestamp` handling is consistent across commands
- Memory footprint and import time do not significantly increase

---

### P2-02: Decompose `src/meminit/core/use_cases/index_repository.py`

**Problem:** 1,867 lines mixing indexing, catalog generation, kanban rendering, embedded CSS, cache behavior, filtering, and streaming.

**Proposed services:**

1. **`IndexCatalogKanbanService`** → New service in `core/services/`
   - `build_catalog(nodes)` → markdown catalog generation
   - `build_kanban(nodes, columns)` → HTML kanban board generation
   - Extract kanban CSS to package asset (`src/meminit/core/assets/kanban.css`)

2. **`IndexStreamOrchestrator`** → New service in `core/services/` (if still needed)
   - Extract streaming runner/thread management from index_repository.py
   - Or deprecate if NDJSON streaming in adapters is sufficient

3. **Keep `IndexRepositoryUseCase` as orchestrator only** (~300-400 lines)
   - Determine incremental strategy (fresh, warm, stale, forced rebuild)
   - Delegate to `IndexCacheService` for caching
   - Delegate to `GraphService` for edge computation
   - Delegate to `IndexCatalogKanbanService` for catalog/kanban
   - Delegate to streaming for NDJSON output

**Kanban CSS extraction:**

```
src/meminit/core/assets/
  kanban.css              (Extracted from index_repository.py)
  meminit-docops-skill.md
  AGENTS.md
```

**Acceptance criteria:**
- `index_repository.py` under 600 lines (orchestrator only)
- `IndexCatalogKanbanService` unit tests added
- Catalog and kanban output byte-identical to current implementation
- 500-doc performance test (test_index_repository.py line 1583) still passes
- XSS sanitization tests still pass
- Cache invalidation tests still pass

---

### P2-03: Decompose `src/meminit/core/use_cases/new_document.py`

**Problem:** 1,314 lines with template loading, ID resolution, filename generation, locking, and provenance tracking all inline.

**Proposed services:**

1. **`DocumentIdGenerator`** → New service in `core/services/`
   - Extract `_id_type_segment()` logic (shared with fix_repository.py)
   - `generate_sequence(repo_prefix, doc_type)` → sequence number allocation
   - `validate_id_format(document_id)` → format validation

2. **`FilenameBuilder`** → New service in `core/services/`
   - Extract filename generation logic
   - `build_filename(title, doc_type)` → sanitized filename
   - `validate_filename(filename)` → ensure no path traversal

3. **`TemplateProvenanceService`** → New service in `core/services/`
   - Track template resolution history
   - Log which template source was used (config, convention, builtin, none)
   - For debugging and template migration tracking

4. **Keep `NewDocumentUseCase` as orchestrator** (~500-600 lines)
   - Parse input params
   - Delegate to `DocumentIdGenerator` for ID (if not provided)
   - Delegate to `FilenameBuilder` for filename
   - Delegate to `TemplateResolver` for template path
   - Delegate to `TemplateInterpolator` for rendering
   - Handle file locking
   - Track provenance via `TemplateProvenanceService`

**Dead code removal:**

- Remove `_apply_common_template_substitutions()` (line 1030) - confirmed dead on v2 path

**Acceptance criteria:**
- `new_document.py` under 600 lines (orchestrator only)
- `DocumentIdGenerator`, `FilenameBuilder`, `TemplateProvenanceService` unit tests added
- All existing tests in `test_new_document.py` pass (1,258 lines of tests)
- Frontend tests (CLI-level) pass
- Template provenance tracking works correctly
- ID type segment logic extracted and shared with fix_repository.py

---

### P2-04: Remove Dead Code and Duplicated Helpers

**Problem:** Duplicated helper functions create maintenance burden and potential inconsistencies.

**Specific actions:**

1. **Extract `_id_type_segment()` to shared `DocumentIdGenerator`** (already planned in P2-03)
   - Remove from `new_document.py:1004` after extraction
   - Remove from `fix_repository.py:711` after extraction

2. **Extract `_filter_index_edges` to shared `IndexHelper`** (or `GraphService` if it already handles this)
   - Check if `GraphService` already provides this functionality
   - If yes, use it; if no, create `IndexHelper` service
   - Remove from `index_repository.py:121` and `main.py:389`

3. **Merge `_index_output_data` and `_index_stream_data`**
   - These are nearly identical functions in `main.py` and `index_repository.py`
   - Consolidate into one helper in shared location
   - Update both call sites

4. **Remove stale backup files from governed protocol paths**
   - Search for `*.bak` in `.agents/` and `src/meminit/core/assets/`
   - Remove any found (already done: `SKILL.md.bak` was removed in TASK-001)

5. **Decide on `Frontmatter` and `Document` domain models**
   - Check if they are actively used throughout the codebase
   - If unused, remove them (update tests accordingly)
   - If used, ensure they're imported from `core/domain/entities.py`

**Acceptance criteria:**
- No duplicated helper remains without clear justification
- `_apply_common_template_substitutions()` removed
- Type and domain tests reflect chosen model
- All existing tests pass

---

### P2-05: Decide and Document Ports/Adapters Boundary

**Problem:** `src/meminit/adapters/` is empty, suggesting an abandoned ports/adapters pattern. Current architecture uses concrete services directly from CLI.

**Two options:**

**Option A: Remove the empty adapters layer (simpler, faster)**
- Delete `src/meminit/adapters/`
- Document that CLI is the adapter layer, calling use cases and services directly
- No changes to existing code structure
- Downside: No clean separation between application boundary and business logic

**Option B: Implement formal `typing.Protocol` ports (more principled, but higher risk)**
- Define ports for:
  - `FileSystemReader` → `read_text(path: str) -> str`
  - `FileSystemWriter` → `write_text(path: str, content: str)`
  - `TemplateResolver` → `resolve_template(doc_type: str) -> Path | None`
  - `OutputFormatter` → `format(data: dict, format_type: str) -> str`
  - `ProtocolAssetResolver` → `get_asset(asset_id: str) -> bytes`
- Implement adapters (concrete classes) for these ports
- Use dependency injection in use cases (accept port objects as constructor args)
- Update CLI to create adapters and pass to use cases
- Downside: Significant refactoring, may introduce bugs, increases code size

**Recommendation for v0.3.x timeframe:**

Go with **Option A (remove the empty layer)** and document the decision. Full ports/adapters is a larger architectural evolution that should be its own initiative, not mixed with P2 refactoring.

**Acceptance criteria:**
- `src/meminit/adapters/` either removed or actively used
- An ADR or design document records the decision (if choosing Option A, note why; if Option B, define the port interfaces)
- No empty packages signal abandoned patterns
- Tests for chosen path pass

## 4. Verification Matrix

Before closing this task, run:

```bash
# All default tests
./.venv/bin/pytest -q

# Template tests
./.venv/bin/pytest tests/core/services/test_template_interpolation.py tests/core/use_cases/test_new_document.py

# Index tests
./.venv/bin/pytest tests/core/use_cases/test_index_repository.py -k "not slow"

# Protocol tests
./.venv/bin/pytest tests/core/use_cases/test_protocol_check.py tests/core/use_cases/test_protocol_sync.py

# CLI tests
./.venv/bin/pytest tests/adapters/test_cli.py -q

# Lint
./.venv/bin/meminit check
./.venv/bin/meminit protocol check
```

File size verification:
```bash
# Before refactoring
wc -l src/meminit/cli/main.py
wc -l src/meminit/core/use_cases/index_repository.py
wc -l src/meminit/core/use_cases/new_document.py

# After refactoring (should be significantly smaller)
wc -l src/meminit/cli/main.py              # Target: < 1,000 lines
wc -l src/meminit/core/use_cases/index_repository.py  # Target: < 600 lines
wc -l src/meminit/core/use_cases/new_document.py       # Target: < 600 lines
```

Search for duplicates:
```bash
# Verify no duplicated helpers remain
rg "_id_type_segment" src/ --count-matches
rg "_filter_index_edges" src/ --count-matches
```

## 5. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-05-25 | GitCmurf | Initial consolidation of P2 items from TASK-001 with detailed work items and acceptance criteria |