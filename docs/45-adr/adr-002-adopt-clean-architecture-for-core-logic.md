---
document_id: MEMINIT-ADR-002
type: ADR
title: Adopt Clean Architecture for core logic
status: Draft
version: 0.1
last_updated: 2025-12-14
owner: GitCmurf
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-ADR-002
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2025-12-14
> **Type:** ADR

# MEMINIT-ADR-002: Adopt Clean Architecture for core logic

- **Date decided:** 2025-12-14
- **Deciders:** Repo maintainers
- **Status:** Draft

## 1. Context & Problem Statement

Meminit needs to support multiple “interfaces” over time (CLI now, CI integrations and agent/tooling later). The core compliance logic must be testable and not entangled with terminal I/O.

## 2. Decision Drivers

- Separation of concerns between UI/CLI and domain logic.
- Strong unit testability of core behavior.
- Avoid framework lock-in (e.g., Click specifics should not leak into business logic).

## 3. Options Considered

- **Clean Architecture / use-case centric core**
  - Pros: explicit use cases, clear dependencies, easier refactoring and testing.
  - Cons: a bit more scaffolding early on.
- **CLI-first “script”**
  - Pros: fastest initial iteration.
  - Cons: quickly becomes hard to test/extend; encourages coupling.

## 4. Decision Outcome

- **Chosen option:** Use-case centric design (“Clean Architecture” style)
- **Scope/Applicability:** `CheckRepositoryUseCase`, `FixRepositoryUseCase`, `InitRepositoryUseCase`, `NewDocumentUseCase` under `src/meminit/core/use_cases/`; adapters in `src/meminit/cli/`.

### 4.1 Implementation Timeline & Rollout

- **Phase 1 (completed by 2025-12-14):** Establish pattern for the initial MVP use cases (`init`, `new`, `check`, `fix`) and tests.
- **Phase 2 (next sprint):** Enforce boundaries consistently as new commands/features land (e.g., `index`, `link`, `scan`), and tighten architectural tests.
- **Phase 3 (future):** Introduce additional adapters (CI helpers, agent-facing tool wrappers) without leaking adapter concerns into the core.

### 4.2 Enforcement Policy

- **Mandatory for new core behavior:** New compliance/business logic MUST land in `src/meminit/core/use_cases/` and `src/meminit/core/services/` and MUST NOT depend on CLI or terminal formatting libraries.
- **Adapters remain thin:** CLI code MUST only orchestrate use cases and render output.
- **Exceptions:** Any exception to this pattern requires an explicit ADR amendment or a new ADR.

## 5. Consequences

- Positive: tests can drive core behavior without invoking the CLI.
- Negative: a little extra structure compared to a single-script CLI.

## 6. Implementation Notes

- Core entities: `src/meminit/core/domain/entities.py`
- Use cases: `src/meminit/core/use_cases/`
- CLI adapter: `src/meminit/cli/main.py`

## 7. Validation & Compliance

- **Testability:** All use cases MUST be unit-testable without importing CLI modules.
- **Dependency rule:** Domain/entities MUST NOT import adapters (CLI) or perform I/O.
- **Testing expectations:** New use-case behavior must include unit tests; adapter behavior belongs in `tests/adapters/`.
- **Migration guidance (if legacy code exists):**
  1. Identify mixed concerns (I/O + logic) and extract pure logic into `core/use_cases` or `core/services`.
  2. Add unit tests around the extracted logic first.
  3. Keep CLI changes minimal: parse args → call use case → render output.
  4. Remove/deprecate old paths once parity is proven by tests.

### 7.1 Acceptance Criteria

- Use cases run under tests without importing `meminit.cli.*`.
- No filesystem writes occur in `check` paths; all writes are confined to `init/new/fix` flows and are tested with temp directories.

## 8. Alternatives Rejected

- CLI-first script approach: rejected due to anticipated growth and the need for reliable testing.

## 9. Supersession

- Supersedes: none
- Superseded by: none

## 10. Notes for Agents

- Keywords: use case, entities, adapters
- Code anchors: `src/meminit/core/use_cases/`, `src/meminit/cli/main.py`
