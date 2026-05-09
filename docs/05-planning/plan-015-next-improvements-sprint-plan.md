---
document_id: MEMINIT-PLAN-015
type: PLAN
title: Next Improvements Sprint Plan
status: Draft
version: '0.4'
last_updated: '2026-05-08'
owner: GitCmurf
docops_version: '2.0'
area: AGENT
description: Agent-orchestrator-ready sprint plan for closing live technical debt
  and hardening the post-Phase-5 Meminit agent interface.
keywords:
- next-steps
- technical-debt
- sprint-plan
- streaming
- state
- index
---

> **Document ID:** MEMINIT-PLAN-015
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 1.0
> **Last Updated:** 2026-05-08
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Agent-orchestrator-ready sprint plan for closing live technical debt and hardening the post-Phase-5 Meminit agent interface.

# PLAN: Next Improvements Sprint Plan

## Context

MEMINIT-PLAN-008 through MEMINIT-PLAN-014 delivered the agent-facing
programme from foundation hardening through scale and streaming. The core
runtime surfaces now exist: v3 JSON envelopes, capabilities, explain,
correlation IDs, graph index artifacts, protocol asset governance, state
queue queries, NDJSON streaming, and incremental index caching.

This plan does not reopen those phases. It captures the next practical
improvement set: close live unsuperseded technical debt, remove ambiguity
between planned and implemented behavior, and leave the codebase easier for
agents to extend safely.

Primary backlog source:

- `TECH_DEBT.md`

Planning constraints:

- Treat Code + Documentation + Tests as the atomic unit of work.
- Preserve document IDs.
- Do not rewrite Approved or Superseded governed docs except for narrow,
  explicitly authorized alignment notes.
- Prefer focused PR slices that an agentic orchestrator can schedule and
  verify independently.
- Keep public contract changes explicit in MEMINIT-SPEC-006,
  MEMINIT-SPEC-008, MEMINIT-SPEC-011, and the relevant FDDs.
- A human maintainer must authorize edits to Approved or Superseded governed
  docs before an agent starts the affected PR. Without that authorization, the
  agent must record the needed alignment in `TECH_DEBT.md` or a new Draft
  closeout note instead of changing the protected document.
- Any user-visible behavior, CLI contract, error-code, schema, or documented
  performance guarantee change must include a changelog or release-note entry
  in the same PR.
- `meminit check --format json` is a gate only when it exits 0 and reports
  zero violations, zero warnings, and no increase in warnings or advice versus
  the branch baseline.

## 1. Purpose

Define the next sprint set after Phase 5, with actionable tasks and
verifiable definitions of done. The plan is suitable for an agentic coding
orchestrator to decompose into PRs, assign to agents, and verify without
re-reading every prior phase plan.

## 2. Scope

In scope:

- Streaming producer architecture hardening.
- Phase 5 cache and streaming test traceability.
- Phase 5 external-testbed evidence capture.
- Multi-namespace index correctness hardening.
- State queue maintainability improvements.
- Error-code contract cleanup, if accepted for the sprint.
- Documentation alignment for all implemented changes.

Out of scope:

- New product features unrelated to the recorded backlog.
- Broad CLI redesign.
- New storage backends.
- Breaking public contract changes without a SPEC update and migration note.
- Retrospective edits that merely reword old plans without changing current
  behavior or closeout evidence.

## 3. Current Assessment

The recent phase plans were assessed on 2026-05-08 against live code,
tests, and governed docs.

| Plan | Current assessment |
| ---- | ------------------ |
| MEMINIT-PLAN-009 | Complete; no live unsuperseded backlog found. |
| MEMINIT-PLAN-010 | Complete for runtime surfaces; no live unsuperseded backlog found. |
| MEMINIT-PLAN-011 | Complete for graph artifact and helpers; TD-001 is closed. |
| MEMINIT-PLAN-012 | Complete for protocol governance; no live unsuperseded backlog found. |
| MEMINIT-PLAN-013 | Complete for queue surfaces; TD-006, TD-007, and TD-009 are closed, while TD-008 remains open. |
| MEMINIT-PLAN-014 | Core implementation complete; TD-003 and TD-005 are closed, while producer architecture and external testbed evidence remain TD-002 and TD-004. |

### 3.1 Implementation Progress

Progress is marked only after code, tests, and relevant docs are aligned and
the listed verification commands pass.

| Workstream | Backlog item | Status | Verification evidence |
| ---------- | ------------ | ------ | --------------------- |
| D: Multi-Namespace Index Correctness | TD-001 | Completed | Removed parent-directory namespace ownership caching, added same-parent multi-namespace regression, and passed `./.venv/bin/pytest -q tests/core/use_cases/test_index_repository.py tests/core/services/test_repo_layout.py`. |
| E1: State Derivation Signature Cleanup | TD-006 | Completed | Verified helper signatures no longer carry unused `known_ids` and passed `./.venv/bin/pytest -q tests/core/services/test_state_derived.py tests/integration/test_state_queries.py`. |
| E2: State Derivation Complexity | TD-007 | Completed | Verified reverse-reference map implementation with a 1000-entry regression fixture and passed `./.venv/bin/pytest -q tests/core/services/test_state_derived.py tests/integration/test_state_queries.py`. |
| E3: State-File Path Strictness | TD-009 | Completed | Added explicit strict/fallback helpers, routed CLI state command use cases through strict mode after initialization validation, preserved diagnostic fallback behavior, and passed focused state verification. |
| A: Streaming Producer Architecture | TD-002 | Narrowed | Added core stream payload types, use-case `iter_stream()` producers, and production CLI `CoreStreamingProducer` drainage. Remaining work is traversal-level laziness instrumentation and shared JSON/NDJSON traversal. |
| B: Phase 5 Cache Scenario Traceability | TD-003 | Completed | Added named S08, S09/S10/S11, S13, and S14 regressions, mapped S05-S14 to concrete tests, and passed focused cache verification. |
| C: Phase 5 External Testbed Evidence | TD-004 | Blocked | Prepared `MEMINIT-LOG-001` as the governed operator attestation template; closure remains blocked on human execution and sanitized evidence. |
| G: Streaming Test Fixture Consolidation | TD-005 | Completed | Shared NDJSON parsing and schema-validator construction through `tests/cli/streaming_helpers.py`, preserved command-specific assertions, and passed the focused streaming test suite. |
| F: Error-Code Contract Cleanup | TD-008 | Open | Blocked on GATE-003. |

## 4. Pre-Sprint Decisions and Gates

These gates must be resolved before dispatching the affected workstream.

| Gate | Applies to | Decider | Required outcome |
| ---- | ---------- | ------- | ---------------- |
| GATE-001: streaming producer API shape | Workstream A | Core maintainer | Confirm the synchronous generator-based producer contract in §5.1 or approve a replacement design note before implementation. |
| GATE-002: external testbed evidence | Workstream C | Release owner | Name the human operator who will run the external repo commands and attest to sanitized evidence. Agents may prepare templates but must not fabricate evidence. |
| GATE-003: state error-code convention | Workstream F | Product/contract owner | Decide whether to preserve current names, add aliases, or rename public error codes before any code changes are scheduled. |
| GATE-004: Approved-doc edit authorization | Any workstream editing Approved/Superseded docs | Repository maintainer | Authorize exact protected documents and sections, or require a Draft follow-up note instead. |

## 5. Sprint Workstreams

### 5.1 Workstream A: Streaming Producer Architecture

Backlog item:

- TD-002

Goal:

- Replace CLI-local NDJSON closure adapters with use-case-owned streaming
  producers for `index`, `scan`, and `context --deep`.

Size:

- L

Design contract:

- Producer API is synchronous and generator-based, not callback-based.
- Shared stream payload types live in a core-owned module, for example
  `src/meminit/core/services/stream_events.py`, so use cases do not import
  CLI output classes.
- The core API shape is:
  `iter_stream() -> StreamingResult`, where `StreamingResult.records` is an
  `Iterator[StreamItem | StreamProgress]` and `StreamingResult.summary`
  exposes warnings, violations, advice, and summary data after the iterator is
  consumed.
- `StreamItem` carries `kind: str` and `data: dict[str, Any]`.
  `StreamProgress` carries optional progress metadata. Neither type contains
  JSON-line formatting concerns.
- The CLI owns command-line parsing, output destination handling, conversion
  from stream payloads into SPEC-011 NDJSON records, and conversion from
  `MeminitError` to structured terminal records.
- Use cases own traversal order, item payload construction, warnings,
  violations, advice, and summary payload construction.
- `execute()` remains the canonical JSON path. JSON and NDJSON must share
  traversal through internal iterators such as `_iter_index_items()` or
  `_iter_scan_items()` so their semantics cannot drift.
- Producers must be deterministic, synchronous, and back-pressure friendly:
  each item is yielded only when traversal reaches it, and producers must not
  build the complete item list before the first `yield`.
- Cancellation and broken-pipe behavior remain owned by
  `streaming_output_handler`; producers must not install signal handlers or
  swallow `MeminitError`.
- Operational errors after the stream starts must surface through the existing
  terminal `error` record path with the relevant `ErrorCode`.

Required instrumentation:

- Add a test-only iterator sentinel that records `first_yield_after`.
- Add a regression test that wraps the internal traversal iterator and raises
  if the producer requests total materialization before the first yielded
  `StreamItem`.
- Avoid timing-only or RSS-only assertions for this DoD; they are allowed as
  secondary evidence but not as the primary regression mechanism.

Implementation steps:

1. [x] Confirm GATE-001.
2. [x] Introduce the core stream payload types and generator producer API.
3. [x] Add producer implementations for `IndexRepositoryUseCase`,
   `ScanRepositoryUseCase`, and `ContextRepositoryUseCase`.
4. [x] Keep the existing JSON `execute()` methods stable unless a local refactor
   is required to share traversal logic.
5. [x] Update the CLI adapters to drain the use-case generators into
   `StreamEmitter`.
6. [x] Remove production use of `CallableStreamingProducer`; keep it only in
   tests if it remains useful for emitter unit tests.
7. [ ] Add instrumentation-based regression tests that prove the first yielded
   item can be produced before a complete result object is assembled.
8. [ ] Update MEMINIT-SPEC-011 and MEMINIT-FDD-014 if the producer semantics or
   guarantees become stricter.

Status:

- Narrowed on 2026-05-09. `src/meminit/core/services/stream_events.py` now
  owns `StreamItem`, `StreamProgress`, `StreamSummary`, and `StreamingResult`.
  The index, scan, and deep-context use cases expose `iter_stream()` producers,
  and production CLI adapters drain those through `CoreStreamingProducer`.
  `CallableStreamingProducer` has been removed from production code. The
  remaining open work is the deeper traversal refactor: JSON and NDJSON should
  share internal item iterators, with instrumentation proving that the first
  `StreamItem` is yielded before full result materialization.

Definition of done:

1. `rg "CallableStreamingProducer" src/meminit/cli` returns no production
   command adapter usage.
2. `index`, `scan`, and `context --deep` NDJSON outputs remain schema-valid
   and deterministic.
3. JSON and NDJSON equivalence tests still pass.
4. An instrumentation-based regression test fails if any opted-in command
   materializes its full item list before yielding the first stream item.
5. Relevant docs describe the shipped producer-side memory behavior.
6. If post-merge NDJSON equivalence or determinism tests regress on `main`,
   revert the producer refactor PR before continuing the workstream.

Suggested verification:

```bash
./.venv/bin/pytest -q tests/cli/test_stream_emitter.py tests/adapters/test_streaming_cli.py tests/cli/test_streaming_equivalence.py tests/cli/test_streaming_determinism.py tests/fixtures/test_streaming_fixtures.py
./.venv/bin/meminit check --format json
```

### 5.2 Workstream B: Phase 5 Cache Scenario Traceability

Backlog item:

- TD-003

Goal:

- Make the cache acceptance surface directly traceable to MEMINIT-PLAN-014
  S05-S14.

Size:

- M

Scenario classification:

| Scenario class | Required evidence |
| -------------- | ----------------- |
| Changed file, added file, removed file | May map to existing focused use-case coverage if the mapping is recorded by scenario ID. |
| Cross-doc edge recomputation | Must have a named regression test because graph correctness is user-visible. |
| Global invalidation and version invalidation | Must have named tests or a single parametrized test whose cases include both scenario IDs. |
| Corrupt cache entry and missing manifest | Must have named tests because these are recovery paths. |
| Concurrent index invocation/cache lock | Must have a named test because it protects cache integrity. |

Implementation steps:

1. [x] Inventory the existing cache tests and map each to S05-S14.
2. [x] Add named E2E-style regression tests for every scenario class marked
   "must have named tests" above.
3. [x] For scenario classes allowed to map to existing coverage, record the
   exact test names and scenario IDs in MEMINIT-FDD-014 or a Draft closeout
   note.
4. [x] Prefer test names that include the scenario identifier when practical.
5. [x] Update MEMINIT-PLAN-014 only if explicit authorization is given to amend
   the Approved plan; otherwise record the mapping in MEMINIT-FDD-014 or a
   governed closeout note.
6. [x] Ensure cache behavior remains byte-identical between warm incremental and
   full rebuild paths.

Status:

- Completed and verified on 2026-05-08. `MEMINIT-PLAN-014` and
  `MEMINIT-FDD-014` are Approved, so the closeout mapping is recorded here
  rather than rewriting protected documents.

Scenario-to-test mapping:

| Scenario | Test evidence |
| -------- | ------------- |
| S05 `single_file_changed` | `test_index_repository_incremental_detects_changed_added_and_removed` |
| S06 `single_file_added` | `test_index_repository_incremental_detects_changed_added_and_removed` |
| S07 `single_file_removed` | `test_index_repository_incremental_detects_changed_added_and_removed` |
| S08 `edge_crosses_changed` | `test_s08_index_repository_incremental_recomputes_changed_related_edges` |
| S09 `config_changed` | `test_s09_s10_s11_index_cache_global_context_change_forces_full_rebuild[config_sha256]` |
| S10 `schema_changed` | `test_s09_s10_s11_index_cache_global_context_change_forces_full_rebuild[schema_sha256]` |
| S11 `version_bump` | `test_s09_s10_s11_index_cache_global_context_change_forces_full_rebuild[meminit_version]` |
| S12 `corrupt_cache_entry` | `test_index_repository_rebuild_cache_recovers_corrupt_node` |
| S13 `missing_manifest` | `test_s13_index_cache_missing_manifest_degrades_to_full_rebuild` |
| S14 `concurrent_index` | `test_s14_index_cache_concurrent_lock_reports_cache_lock_held` |

Definition of done:

1. Every S05-S14 row has either the required named test or a documented
   scenario-ID mapping to existing coverage where this plan permits mapping.
2. Changed, added, removed, cross-doc edge recomputation, global invalidation,
   version invalidation, corrupt cache entry, missing manifest, and concurrent
   lock behavior are all covered.
3. The cache-control CLI flag tests still prove invalid combinations do not
   mutate the cache.
4. The test-to-plan mapping lists concrete test names and scenario IDs.

Suggested verification:

```bash
./.venv/bin/pytest -q tests/core/use_cases/test_index_repository.py tests/core/services/test_index_cache.py tests/adapters/test_cli.py tests/adapters/test_streaming_cli.py
./.venv/bin/meminit check --format json
```

### 5.3 Workstream C: Phase 5 External Testbed Evidence

Backlog item:

- TD-004

Goal:

- Capture non-PII evidence that the Phase 5 NDJSON and incremental cache
  surfaces were exercised in at least one external testbed repo.

Size:

- S for agent-prepared artifacts; operator time varies.

Execution mode:

- Operator-only closeout. An agent may prepare the evidence template, update
  references after the operator supplies data, and run local DocOps checks.
  An agent must not claim the external commands ran unless a human operator
  supplies an attestation.

Implementation steps:

1. [ ] Confirm GATE-002.
2. [x] Choose an evidence location: a governed runbook appendix, a LOG document,
   or a release closeout note.
3. [ ] Record the date, Meminit command version, external repo class, commands
   run, sanitized success/failure summary, and any follow-up debt.
4. [x] Use the command set from MEMINIT-RUNBOOK-006:
   `meminit scan --format ndjson`,
   `meminit context --deep --format ndjson`,
   `meminit index --format ndjson`,
   `meminit index --format json`, and
   `meminit index --explain-cache --format json`.
5. [x] Keep repository names, paths, secrets, and proprietary content out of the
   artifact unless explicitly approved.
6. [x] Link or reference the evidence from this plan and from `TECH_DEBT.md`.

Status:

- Blocked on operator execution as of 2026-05-09. `MEMINIT-LOG-001` is a
  governed Draft evidence template with the required command list, sanitation
  requirements, and attestation fields. It is not closure evidence until a
  human operator records sanitized results and a release owner signs off.

Definition of done:

1. A governed doc records the testbed evidence without secrets or PII.
2. The evidence includes a named human attestation, date, command list, and
   sanitized result summary.
3. The evidence includes enough command output summary for release reviewers
   to verify the criterion was actually exercised.
4. `TECH_DEBT.md` TD-004 is marked `Closed` with a reference to the evidence.
5. `meminit check --format json` exits 0 with zero violations and zero
   warnings.

Suggested verification:

```bash
./.venv/bin/meminit check --format json
detect-secrets scan  # If installed; otherwise run the repository-approved secret scanner or record that no scanner is configured.
```

### 5.4 Workstream D: Multi-Namespace Index Correctness

Backlog item:

- TD-001

Status:

- Completed and verified on 2026-05-08.

Goal:

- Prevent namespace cache reuse from skipping documents when configured
  namespaces have overlapping docs roots.

Size:

- S

Implementation steps:

1. Add a failing regression fixture with two namespaces that can both inspect
   files under an overlapping parent directory.
2. Confirm the current cache behavior can skip a valid document or prove the
   risk is already removed.
3. If live, key the cache by namespace plus parent directory, or remove the
   optimization in multi-namespace mode.
4. Keep the single-namespace fast path deterministic.
5. Update index or monorepo docs only if observable semantics change.

Definition of done:

1. The overlapping-namespace fixture indexes the expected documents for each
   namespace.
2. Existing monorepo and graph tests remain green.
3. Path-to-namespace ownership decisions flow through
   `RepoLayout.namespace_for_path()` or a single documented helper; verify with
   `rg "namespace_for_path|_ns_cache" src/meminit/core/use_cases/index_repository.py`.
4. `TECH_DEBT.md` TD-001 is marked `Closed`.
5. If post-merge graph or monorepo index tests regress on `main`, revert the
   namespace-cache PR before continuing related indexing work.

Suggested verification:

```bash
./.venv/bin/pytest -q tests/core/use_cases/test_index_repository.py tests/core/services/test_repo_layout.py
./.venv/bin/meminit check --format json
```

### 5.5 Workstream E1: State Derivation Signature Cleanup

Backlog item:

- TD-006

Status:

- Completed and verified on 2026-05-08.

Goal:

- Remove misleading unused parameters from state derivation helpers without
  changing public queue semantics.

Size:

- S

Implementation steps:

1. Remove the unused `known_ids` parameter from `_is_dep_resolved`,
   `_is_ready`, `_open_blockers_for`, and their callers.
2. Preserve the explicit-state dependency semantics: dependencies count as
   resolved only when their state entry has `impl_state: Done`.
3. Update tests to make that semantic visible.

Definition of done:

1. `rg "known_ids" src/meminit/core/services/state_derived.py` returns no
   unused helper parameter.
2. State derivation tests still cover explicit done dependencies, missing
   state entries, and unknown dependencies.
3. Public `state list`, `state next`, and `state blockers` payloads are
   byte-identical for the existing fixture matrix.
4. TD-006 is closed or narrowed.

Suggested verification:

```bash
./.venv/bin/pytest -q tests/core/services/test_state_derived.py tests/integration/test_state_queries.py
./.venv/bin/meminit check --format json
```

### 5.6 Workstream E2: State Derivation Complexity

Backlog item:

- TD-007

Status:

- Completed and verified on 2026-05-08.

Goal:

- Replace quadratic `unblocks` derivation with a precomputed inverse
  adjacency map while preserving byte-identical output.

Size:

- M

Implementation steps:

1. Capture a before-change benchmark on a deterministic generated state
   fixture with at least 1000 entries.
2. Build an inverse adjacency map once per `compute_derived_fields` call.
3. Use that map for `unblocks` without changing output ordering.
4. Add a regression test that proves output equality against the old fixture
   expectations and records the benchmark shape.
5. Avoid public payload changes unless a SPEC/FDD update is included.

Definition of done:

1. Existing state query fixture outputs remain byte-identical.
2. A scale-oriented test or benchmark note demonstrates the before/after
   improvement on the deterministic fixture.
3. The algorithm is O(n + e) over state entries and dependency edges.
4. TD-007 is closed or narrowed.
5. If post-merge state ordering or readiness tests regress on `main`, revert
   the complexity PR before continuing state internals work.

Suggested verification:

```bash
./.venv/bin/pytest -q tests/core/services/test_state_derived.py tests/integration/test_state_queries.py
./.venv/bin/meminit check --format json
```

### 5.7 Workstream E3: State-File Path Strictness

Backlog item:

- TD-009

Goal:

- Split strict and fallback state-file path lookup so command behavior is
  explicit in missing or malformed config cases.

Size:

- M

Implementation steps:

1. [x] Identify every `get_state_file_rel_path` caller and classify it as strict
   or diagnostic.
2. [x] Split state-file path lookup into strict and fallback variants.
3. [x] Use the strict variant in command/use-case paths where missing config
   should fail.
4. [x] Preserve the documented empty-queue behavior for missing
   `project-state.yaml`.
5. [x] Add tests for strict vs fallback path behavior.
6. [x] Update MEMINIT-FDD-013 or MEMINIT-RUNBOOK-006 if user-visible diagnostics
   change.

Status:

- Completed and verified on 2026-05-09. `get_state_file_rel_path_strict()`
  emits `CONFIG_MISSING` for missing, malformed, or invalid repo config, while
  `get_state_file_rel_path_fallback()` preserves diagnostic default-path
  behavior. `load_project_state()`, `save_project_state()`, and
  `validate_project_state()` now expose explicit `strict_config` controls.
  CLI state command use cases pass `strict_config=True` after
  `validate_initialized`; direct service tests and diagnostics keep fallback
  behavior. No FDD/RUNBOOK update was required because user-visible CLI
  diagnostics remain aligned with the existing initialization guard.

Definition of done:

1. Missing or malformed repo config emits the documented error for strict
   callers.
2. Diagnostic callers that intentionally mention default paths keep doing so.
3. Missing `project-state.yaml` remains an empty-queue case, not a config
   error.
4. FDD-013 and MEMINIT-RUNBOOK-006 remain accurate.
5. TD-009 is closed or narrowed.

Suggested verification:

```bash
./.venv/bin/pytest -q tests/core/services/test_project_state.py tests/core/use_cases/test_doctor_repository.py tests/core/use_cases/test_index_repository.py tests/adapters/test_cli_state.py
./.venv/bin/meminit check --format json
```

### 5.8 Workstream F: Error-Code Contract Cleanup

Backlog item:

- TD-008

Goal:

- Implement the state error-code naming decision from GATE-003.

Size:

- Decision only if names are preserved; L if public names are changed.

Implementation steps:

1. Confirm GATE-003 before editing code.
2. If preserving compatibility, document the inconsistency as intentional and
   close TD-008 as `Superseded` or `Rejected`.
3. If renaming, update `ErrorCode`, `ERROR_EXPLANATIONS`, exit-code mapping,
   SPEC-006, contract matrix expectations, and every affected test.
4. Add migration notes for agents that consume the old names.
5. Verify `meminit explain --list --format json` covers the final set.

Definition of done:

1. SPEC-006 and runtime enum values agree.
2. `meminit explain` resolves every public error code.
3. Contract matrix and state CLI tests pass.
4. The decision is recorded in the change history of the affected governed
   docs.
5. TD-008 is closed, superseded, or rejected with a clear rationale.
6. Any public rename includes a changelog/release-note entry and migration
   note.

Suggested verification:

```bash
./.venv/bin/pytest -q tests/core/services/test_error_explainer.py tests/core/services/test_exit_codes.py tests/integration/test_contract_matrix.py tests/adapters/test_cli_state.py
./.venv/bin/meminit check --format json
```

### 5.9 Workstream G: Streaming Test Fixture Consolidation

Backlog item:

- TD-005

Goal:

- Reduce duplication between CLI streaming tests and shared streaming
  fixture helpers.

Size:

- S

Implementation steps:

1. [x] Inventory local helper functions in `tests/adapters/test_streaming_cli.py`.
2. [x] Move reusable setup into shared fixtures or reuse the existing streaming
   fixture generator.
3. [x] Keep command-specific assertions in the CLI test file.
4. [x] Ensure fixture generation remains deterministic and does not slow the
   default test suite materially.
5. [x] If Workstream B added cache scenario tests first, migrate only duplicated
   setup and keep those scenario test names stable.

Status:

- Completed and verified on 2026-05-09. `tests/cli/streaming_helpers.py` now
  owns shared NDJSON parsing and stream schema validator construction.
  `tests/adapters/test_streaming_cli.py` retains command-specific assertions
  while using the shared helpers. Existing slow-scale fixture tests remain
  opt-in and no new slow marker was introduced.

Definition of done:

1. Duplicate setup is removed or intentionally documented.
2. Shared fixture generation completes within the existing default-suite
   runtime envelope; no new slow marker is required for normal CLI streaming
   tests.
3. Streaming CLI, fixture, equivalence, and determinism tests remain green.
4. TD-005 is closed.

Suggested verification:

```bash
./.venv/bin/pytest -q tests/adapters/test_streaming_cli.py tests/fixtures/test_streaming_fixtures.py tests/cli
./.venv/bin/meminit check --format json
```

## 6. Risk and Rollback Rules

| Risk area | Applies to | Rollback rule |
| --------- | ---------- | ------------- |
| NDJSON equivalence or determinism regression | Workstream A | Revert the producer refactor PR before continuing A or G. |
| Graph/index correctness regression | Workstream D | Revert the namespace-cache PR before continuing index-adjacent work. |
| State readiness or ordering regression | Workstream E2/E3 | Revert the state internals PR before continuing E-series work. |
| Public contract rename fallout | Workstream F | Stop rollout, restore previous names or aliases, and update SPEC-006 migration notes before another release candidate. |
| External evidence uncertainty | Workstream C | Keep TD-004 open; do not close it from agent-generated evidence alone. |

## 7. Recommended Delivery Sequence

1. Workstream D: close correctness risk in multi-namespace indexing.
2. Workstream E1: remove misleading state derivation parameters.
3. Workstream E2: optimize state derivation complexity.
4. Workstream E3: split strict/fallback state path behavior.
5. Workstream A: replace streaming adapters with generator-backed producers.
6. Workstream B: make Phase 5 cache acceptance traceable.
7. Workstream C: commit external-testbed closeout evidence after operator
   attestation.
8. Workstream G: consolidate streaming test fixtures after A and B settle the
   test surface.
9. Workstream F: handle error-code naming after deciding whether compatibility
   or normalization matters more.

Rationale:

- Correctness and internal simplification should happen before broader
  streaming refactors.
- Producer refactoring should precede fixture consolidation so tests settle
  around the final architecture.
- Cache traceability should precede fixture consolidation so new scenario
  tests are not immediately rewritten.
- Error-code naming is intentionally last because it can be cross-cutting and
  may be closed by a documented decision rather than code.

## 8. Orchestrator Operating Rules

For each PR slice:

1. Start by selecting exactly one workstream unless dependencies require a
   paired change.
2. Update `TECH_DEBT.md` in the same PR when status changes.
3. Keep governed docs narrow and factual; do not rewrite prior Approved plans
   unless explicitly authorized.
4. Confirm that all applicable pre-sprint gates are resolved.
5. Run the workstream-specific verification commands.
6. Run the final common gates before marking the slice complete.
7. Record benchmark deltas for Workstreams A and E2 when performance or
   memory behavior is part of the claim.

Common final gates:

```bash
./.venv/bin/pytest -q
./.venv/bin/meminit check --format json
git diff --check
```

The `meminit check` gate means exit code 0, zero violations, zero warnings,
and no new graph advice attributable to the PR unless that advice is the
explicit subject of the PR and is recorded in `TECH_DEBT.md`.

## 9. Programme Definition of Done

This plan is complete when:

1. Every open item in `TECH_DEBT.md` is `Closed`, `Superseded`, or `Rejected`
   with evidence.
2. `CallableStreamingProducer` is absent from production command adapters or
   explicitly documented as test-only.
3. Phase 5 cache scenarios have direct test or governed-doc traceability.
4. External-testbed evidence for Phase 5 is committed without secrets or PII.
5. Multi-namespace index ownership is regression-tested.
6. State queue internals are simpler and public behavior is unchanged.
7. Error-code naming has either been normalized or accepted as an explicit
   compatibility decision.
8. Any user-visible contract changes have changelog/release-note and migration
   notes.
9. `./.venv/bin/pytest -q`, `./.venv/bin/meminit check --format json`, and
   `git diff --check` pass on the closing branch.

## 10. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-05-08 | Codex | Initial post-Phase-5 improvement sprint plan based on the live technical debt assessment of MEMINIT-PLAN-008 through MEMINIT-PLAN-014. |
| 0.2 | 2026-05-08 | Codex | Incorporated critical review feedback: added pre-sprint gates, specified the streaming producer architecture, marked external testbed evidence operator-only, split state workstreams, tightened cache scenario evidence, added rollback rules, and made definitions of done mechanically verifiable. |
| 0.3 | 2026-05-08 | Codex | Resolved the Workstream A producer-pattern ambiguity by standardizing on core-owned synchronous generator producers and CLI-owned NDJSON emission. |
| 0.4 | 2026-05-08 | Codex | Marked Workstreams D, E1, and E2 completed after implementation and focused verification; remaining workstreams stay open. |
| 0.5 | 2026-05-08 | Codex | Narrowed Workstream E3 by adding strict/fallback state-file path APIs and verification, leaving caller migration as the remaining behavior-changing step. |
| 0.6 | 2026-05-08 | Codex | Closed Workstream B by adding named cache scenario regressions and recording the S05-S14 test mapping without editing protected Approved docs. |
| 0.7 | 2026-05-09 | Codex | Closed Workstream G by consolidating reusable streaming test helpers and preserving the existing focused streaming verification suite. |
| 0.8 | 2026-05-09 | Codex | Closed Workstream E3 by routing state command use cases through strict config mode while preserving diagnostic fallback semantics. |
| 0.9 | 2026-05-09 | Codex | Narrowed Workstream A by introducing core stream payload types, use-case stream producers, and production CLI drainage through `CoreStreamingProducer`. |
| 1.0 | 2026-05-09 | Codex | Prepared the Workstream C governed operator evidence template and marked TD-004 blocked on human-attested external testbed execution. |
