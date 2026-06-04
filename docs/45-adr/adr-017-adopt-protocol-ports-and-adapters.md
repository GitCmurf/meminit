---
document_id: MEMINIT-ADR-017
type: ADR
title: Adopt Protocol ports and adapters for dependency injection
status: Approved
version: 0.1
last_updated: 2026-06-02
owner: Codex
docops_version: 2.0
template_type: adr-standard
template_version: 2.0
description: Architectural decision to introduce typing.Protocol interfaces for
  filesystem, config, frontmatter, and safe storage operations.
keywords:
  - architecture
  - dependency-injection
  - ports-and-adapters
  - typing-protocol
---

> **Document ID:** MEMINIT-ADR-017
> **Owner:** Codex
> **Status:** Approved
> **Version:** 0.1
> **Last Updated:** 2026-06-02
> **Type:** ADR

# ADR: Adopt Protocol ports and adapters for dependency injection

## Status

Approved

## Context

The Meminit codebase has 22 use case classes (e.g., `CheckRepositoryUseCase`, `NewDocumentUseCase`, `IndexRepositoryUseCase`) that all directly couple to concrete filesystem, configuration, and parsing implementations. This coupling makes unit testing expensive (every test requires `tmp_path` fixtures and actual filesystem operations) and prevents future flexibility (e.g., virtual filesystems, remote storage backends).

Examples of direct coupling:

- `pathlib.Path.read_text()` / `.write_text()` throughout all use cases
- `frontmatter.load(path)` in 18 use cases
- `load_repo_layout(root_dir)` in 18 use cases
- `atomic_write()` from `safe_fs` in 5 use cases

MEMINIT-ADR-002 established clean architecture principles with use cases as the application core, but no formal dependency injection interface existed.

## Decision

Introduce `typing.Protocol` ports for the four most commonly used external dependencies, with concrete adapters and progressive adoption in use cases.

### Protocol Interfaces (`src/meminit/core/ports/`)

1. **FileSystemPort**: `read_text()`, `write_text()`, `exists()`, `is_file()`, `is_dir()`, `resolve()`, `mkdir()`, `iterdir()`, `read_bytes()`, `write_bytes()`
2. **ConfigPort**: `load_repo_layout()`, `load_repo_config()`
3. **FrontmatterPort**: `load()`, `loads()` — returns `(metadata_dict, content_str)` tuples
4. **SafeStoragePort**: `atomic_write()`, `ensure_safe_write_path()`

### Concrete Adapters (`src/meminit/adapters/`)

1. **LocalFileSystem**: Implements `FileSystemPort` using `pathlib.Path`
2. **YamlConfigAdapter**: Implements `ConfigPort` wrapping `load_repo_layout()` / `load_repo_config()`
3. **PythonFrontmatterAdapter**: Implements `FrontmatterPort` wrapping `python-frontmatter`
4. **LocalSafeStorage**: Implements `SafeStoragePort` wrapping `safe_fs` functions

### Progressive Adoption Pattern

Use case constructors accept optional Protocol-typed parameters with defaults that create the concrete implementations:

```python
class CheckRepositoryUseCase:
    def __init__(
        self,
        root_dir: str,
        *,
        filesystem: FileSystemPort | None = None,
        config: ConfigPort | None = None,
        frontmatter: FrontmatterPort | None = None,
    ):
        self._fs = filesystem or LocalFileSystem()
        self._config = config or YamlConfigAdapter()
        self._fm = frontmatter or PythonFrontmatterAdapter()
```

This preserves backward compatibility (existing CLI callers pass only `root_dir`) while enabling test injection of mock adapters.

### First Wave Adoption

Three use cases are refactored in this sprint to demonstrate the pattern:

- `CheckRepositoryUseCase`
- `NewDocumentUseCase`
- `IndexRepositoryUseCase`

The remaining 19 use cases retain TODO markers for progressive adoption.

## Consequences

### Positive

- **Testability**: Unit tests can inject mock adapters instead of `tmp_path` fixtures, reducing test setup complexity and improving test isolation
- **Clear contracts**: Protocol interfaces make dependency requirements explicit in type signatures
- **Future flexibility**: Alternative storage backends (e.g., S3, virtual filesystems) can be added without modifying use case logic
- **Senior-level codebase practices**: Aligns with established patterns in production Python codebases

### Negative

- **More boilerplate**: Each use case that adopts ports adds ~10 lines of default parameter boilerplate
- **Gradual migration cost**: Progressive adoption means some use cases will still use concrete dependencies during the transition period
- **Additional module complexity**: Two new packages (`core/ports/` and `adapters/`) increase codebase surface area

### Neutral

- **No behavior change**: Existing CLI and integration tests pass unchanged; defaults preserve current behavior
- **Performance negligible**: Adapter indirection adds no measurable overhead (all adapters are thin wrappers)

## Alternatives Considered

### Option A: Remove empty `adapters/` layer (simpler)

**Rejected**: ADR-002 establishes clean architecture intent; abandoning the adapters layer would contradict that strategic direction. While simpler for v0.3.x, it trades long-term architectural coherence for short-term convenience.

### Option C: Abstract Base Classes instead of Protocols

**Rejected**: `typing.Protocol` is preferred for duck-typing adapters without a shared inheritance hierarchy. It avoids the "is-a" constraint and matches Python's idiomatic structural subtyping approach.

## Related Documents

- MEMINIT-ADR-002: Adopt Clean Architecture for core logic
- MEMINIT-TASK-002: Architecture Refactoring (parent task)

## Version History

| Version | Date       | Author | Changes                                                     |
| ------- | ---------- | ------ | ----------------------------------------------------------- |
| 0.1     | 2026-06-02 | Codex  | Initial ADR: Protocol ports, adapters, progressive adoption |
