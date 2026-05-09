# Technical Debt Register

This register tracks known technical debt and open implementation gaps that
are intentionally deferred from the current delivery slice. It is not a place
for vague ideas or feature wishes: each entry must be evidence-backed,
owned, prioritized, and closed only when code, tests, and documentation are
updated together.

## Governance

- **Canonical register:** `TECH_DEBT.md`
- **Scope:** Cross-cutting implementation debt, plan closeout gaps, and
  maintainability work that should survive beyond a single PR.
- **Out of scope:** New product ideas, speculative refactors, duplicate issue
  tracker content, or work already completed by a later implementation.
- **Closure rule:** An item can move to `Closed` only when its definition of
  done is satisfied and verification evidence is recorded.
- **Update rule:** When a debt item is implemented, update this file in the
  same PR as the code, tests, and governed docs.
- **Ordering:** Open items are ordered by priority, then by delivery sequence.

## Status Model

| Status | Meaning |
| ------ | ------- |
| `Open` | Accepted debt that is not yet being worked. |
| `In Progress` | Assigned work is active on a branch or sprint. |
| `Blocked` | Work is accepted but cannot proceed until a named blocker clears. |
| `Closed` | Code, tests, and docs are complete and verified. |
| `Superseded` | A later implementation or plan made the item obsolete. |
| `Rejected` | Reassessment found the item invalid or not worth carrying. |

## Priority Model

| Priority | Meaning |
| -------- | ------- |
| `P0` | Blocks correctness, security, release readiness, or data integrity. |
| `P1` | Significant user-facing, agent-facing, or architectural risk. |
| `P2` | Maintainability, scalability, or traceability issue with bounded impact. |
| `P3` | Cleanup or polish that should not distract from higher-priority work. |

## Open Backlog

### TD-001: Multi-namespace index cache can skip files in overlapping docs roots

| Field | Value |
| ----- | ----- |
| Priority | P2 |
| Status | Closed |
| Owner | Core indexing maintainers |
| Source | Review follow-up from Phase 4/5 index work |
| Related plans | `MEMINIT-PLAN-011`, `MEMINIT-PLAN-013`, `MEMINIT-PLAN-014` |
| Evidence | `src/meminit/core/use_cases/index_repository.py` now deduplicates discovered paths across configured namespaces, resolves ambiguous ownership with `document_id` prefixes when multiple namespaces share a docs root, and invalidates cached nodes whose stored namespace no longer matches the current resolver. |
| Impact | Multi-namespace repositories with overlapping or same-root docs roots can now be indexed deterministically instead of dropping the second namespace or reusing stale namespace ownership from cache. |
| Remediation | Keep namespace resolution doc-id-aware for ambiguous paths, and invalidate cached index nodes whenever the resolved namespace changes. |
| Definition of done | Add an overlapping-namespace regression fixture; prove both namespaces' files are indexed; update index behavior docs if the lookup algorithm changes; run the focused index tests and `meminit check --format json`. |
| Verification commands | `./.venv/bin/pytest -q tests/core/use_cases/test_index_repository.py tests/core/services/test_repo_layout.py` |
| Closure evidence | Closed on 2026-05-09 by adding document-id-aware namespace resolution for ambiguous multi-namespace paths, invalidating stale cached node namespaces, and covering same-root namespaces in `tests/core/use_cases/test_index_repository.py` and `tests/core/services/test_repo_layout.py`; focused verification passed. |

### TD-002: Streaming producers still materialize use-case results before emitting

| Field | Value |
| ----- | ----- |
| Priority | P2 |
| Status | Narrowed |
| Owner | CLI/Core maintainers |
| Source | MEMINIT-PLAN-014 Phase 5 constant-memory objective |
| Related plans | `MEMINIT-PLAN-008`, `MEMINIT-PLAN-014` |
| Evidence | `src/meminit/cli/streaming.py` keeps `CallableStreamingProducer` as a temporary adapter, and `src/meminit/cli/main.py` wraps already-materialized `index`, `scan`, and `context --deep` results before emitting NDJSON. |
| Narrowing evidence | Core-owned stream payload types now live in `src/meminit/core/services/stream_events.py`; `IndexRepositoryUseCase`, `ScanRepositoryUseCase`, and `ContextRepositoryUseCase` expose `iter_stream()` producers; production CLI adapters drain `CoreStreamingProducer`; and `rg "CallableStreamingProducer" src/meminit/cli` returns no matches. |
| Impact | The shipped NDJSON contract is usable, but the implementation does not yet provide the strongest planned producer-side constant-memory architecture for large repos. |
| Remediation | Refactor the producer internals so JSON and NDJSON share traversal iterators and add instrumentation proving the first `StreamItem` is yielded before complete result materialization. |
| Definition of done | `CallableStreamingProducer` is no longer used by production command adapters; regression tests fail if `index`, `scan`, or `context --deep` builds the full command payload before the first item record; SPEC-011/FDD-014 wording is updated if the API shape changes. |
| Verification commands | `./.venv/bin/pytest -q tests/cli/test_stream_emitter.py tests/adapters/test_streaming_cli.py tests/cli/test_streaming_equivalence.py tests/cli/test_streaming_determinism.py` |

### TD-003: Phase 5 cache scenario traceability is weaker than the plan matrix

| Field | Value |
| ----- | ----- |
| Priority | P2 |
| Status | Closed |
| Owner | Test maintainers |
| Source | MEMINIT-PLAN-014 fixture matrix S05-S14 |
| Related plans | `MEMINIT-PLAN-014` |
| Evidence | Cache behavior has unit and CLI coverage, but the plan names one scenario per cache case for changed, added, removed, cross-doc edge recomputation, global invalidation, version invalidation, corrupt node entry, missing manifest, and concurrent invocation. The current tests combine several concerns across lower-level tests. |
| Impact | Reviewers must manually map implementation coverage back to the plan matrix, increasing closeout ambiguity and future regression risk. |
| Remediation | Either add explicit scenario tests matching S05-S14 or revise MEMINIT-PLAN-014 to state that combined lower-level coverage is the accepted verification surface. |
| Definition of done | Every S05-S14 row has a named test or a documented supersession note; the plan/FDD/test names agree; cache and streaming tests remain green. |
| Verification commands | `./.venv/bin/pytest -q tests/core/use_cases/test_index_repository.py tests/core/services/test_index_cache.py tests/adapters/test_cli.py tests/adapters/test_streaming_cli.py` |
| Closure evidence | Closed on 2026-05-08 by adding named S08, S09/S10/S11, S13, and S14 regressions, preserving existing S05-S07 and S12 coverage, and recording the scenario-to-test mapping in `MEMINIT-PLAN-015`. |

### TD-004: Phase 5 external testbed closeout evidence is not committed

| Field | Value |
| ----- | ----- |
| Priority | P3 |
| Status | Blocked |
| Owner | Release owner |
| Source | MEMINIT-PLAN-014 exit criterion 11 and MEMINIT-RUNBOOK-006 closeout checklist |
| Related plans | `MEMINIT-PLAN-014`, `MEMINIT-LOG-001` |
| Evidence | Earlier phases record external testbed evidence in governed FDDs, but Phase 5 does not have an in-repo non-PII record showing which external testbed was used, which commands ran, and what sanitized result was observed. |
| Prepared artifact | `MEMINIT-LOG-001` provides the governed attestation template and required command list. It is intentionally not closure evidence until a human operator fills it with sanitized run results. |
| Impact | Release reviewers cannot independently verify the external-testbed criterion from committed artifacts. |
| Remediation | Add a governed closeout note, runbook appendix, or release checklist entry that records the external testbed date, repository class, commands, and sanitized summary. |
| Definition of done | The evidence artifact contains no secrets or PII, references the exact commands from MEMINIT-RUNBOOK-006, and passes `meminit check --format json`. |
| Verification commands | `./.venv/bin/meminit check --format json` |

### TD-005: Streaming CLI fixture setup is duplicated

| Field | Value |
| ----- | ----- |
| Priority | P3 |
| Status | Closed |
| Owner | Test maintainers |
| Source | Phase 5 test maintainability review |
| Related plans | `MEMINIT-PLAN-014` |
| Evidence | `tests/adapters/test_streaming_cli.py` has local setup helpers while newer streaming tests use shared fixture infrastructure under `tests/fixtures/streaming`. |
| Impact | Minor maintainability cost and higher risk of fixture drift between CLI-level and equivalence/determinism tests. |
| Remediation | Refactor the CLI streaming tests to reuse the shared initialized repository and streaming fixture helpers without weakening command-specific assertions. |
| Definition of done | Duplicate setup is removed or explicitly justified; shared helpers remain deterministic; existing streaming CLI assertions still cover unsupported formats, stdout isolation, schema conformance, and correlation behavior. |
| Verification commands | `./.venv/bin/pytest -q tests/adapters/test_streaming_cli.py tests/fixtures/test_streaming_fixtures.py tests/cli` |
| Closure evidence | Closed on 2026-05-09 by moving NDJSON record parsing and stream schema validator construction into `tests/cli/streaming_helpers.py`, reusing those helpers from adapter and CLI streaming tests, and passing the focused streaming verification suite. |

### TD-006: Unused `known_ids` parameter obscures dependency semantics

| Field | Value |
| ----- | ----- |
| Priority | P3 |
| Status | Closed |
| Owner | State/queue maintainers |
| Source | Review follow-up from Phase 4 state derivation |
| Related plans | `MEMINIT-PLAN-013` |
| Evidence | `_is_dep_resolved(dep_id, state, known_ids)` and related helpers accept `known_ids`, but dependency readiness is intentionally based on explicit `project-state.yaml` entries with `impl_state: Done`. |
| Impact | No functional bug, but the unused parameter suggests that indexed-but-untracked documents may count as resolved dependencies. |
| Remediation | Remove `known_ids` from helper signatures and update callers/tests to make the explicit-state semantics obvious. |
| Definition of done | Helper signatures match the actual algorithm; state derivation tests still cover known, unknown, missing-state, and explicit-done dependencies; FDD-013 remains accurate. |
| Verification commands | `./.venv/bin/pytest -q tests/core/services/test_state_derived.py tests/integration/test_state_queries.py` |
| Closure evidence | Closed on 2026-05-08 after verifying `src/meminit/core/services/state_derived.py` helper signatures no longer carry unused `known_ids`; focused verification passed. |

### TD-007: `compute_derived_fields` uses quadratic unblocks derivation

| Field | Value |
| ----- | ----- |
| Priority | P3 |
| Status | Closed |
| Owner | State/queue maintainers |
| Source | Review follow-up from Phase 4 state derivation |
| Related plans | `MEMINIT-PLAN-013` |
| Evidence | `_unblocks_for` scans all state entries for each entry when calculating derived fields. |
| Impact | Acceptable at current scale, but queue derivation cost grows quadratically as state entries increase. |
| Remediation | Build a dependency inverse adjacency map once per `compute_derived_fields` call and answer `unblocks` from that map. |
| Definition of done | Derived output is byte-identical for existing fixtures; a scale-oriented unit test demonstrates linear-style behavior or at least prevents accidental extra full scans; docs do not need updating unless payload semantics change. |
| Verification commands | `./.venv/bin/pytest -q tests/core/services/test_state_derived.py tests/integration/test_state_queries.py` |
| Closure evidence | Closed on 2026-05-08 after verifying `_build_incoming_references` is used once per derivation and adding a 1000-entry reverse-lookup regression; focused verification passed. |

### TD-008: State error-code prefix convention is inconsistent

| Field | Value |
| ----- | ----- |
| Priority | P3 |
| Status | Closed |
| Owner | Contract maintainers |
| Source | Review follow-up from Phase 4 error-code work |
| Related plans | `MEMINIT-PLAN-010`, `MEMINIT-PLAN-013`, `MEMINIT-PLAN-015`, `MEMINIT-SPEC-006` |
| Evidence | The public `ErrorCode` enum mixed old `E_*` state names with unprefixed `STATE_*` codes. |
| Impact | No runtime bug, but the public contract is less regular for agents and documentation. Renaming is cross-cutting and should be deliberate. |
| Remediation | Choose a single state-code convention, update code, docs, explain metadata, tests, and any migration notes in SPEC-006. |
| Definition of done | SPEC-006, `ErrorCode`, `ERROR_EXPLANATIONS`, exit-code mappings, contract matrix tests, and state tests agree on the final names. If compatibility is intentionally preserved, document aliases explicitly. |
| Verification commands | `./.venv/bin/pytest -q tests/core/services/test_error_explainer.py tests/core/services/test_exit_codes.py tests/integration/test_contract_matrix.py tests/adapters/test_cli_state.py` |
| Closure evidence | Closed on 2026-05-09 after product/contract owner confirmation that no external consumers depend on the old names. The runtime enum, explain metadata, exit-code mapping, contract tests, state tests, `MEMINIT-SPEC-006`, and changelog now use `STATE_YAML_MALFORMED`, `STATE_SCHEMA_VIOLATION`, and `STATE_INVALID_FILTER_VALUE` without aliases. |

### TD-009: State-file path helper has fallback behavior where strictness is expected

| Field | Value |
| ----- | ----- |
| Priority | P3 |
| Status | Closed |
| Owner | State/doctor/index maintainers |
| Source | Review follow-up from Phase 4 configuration strictness |
| Related plans | `MEMINIT-PLAN-013` |
| Evidence | `get_state_file_rel_path` catches config-loading failures and returns `docs/01-indices/project-state.yaml`. State CLI paths call initialization validation first, but diagnostic/index paths can still observe the fallback. |
| Narrowing evidence | `get_state_file_rel_path_strict()` and `get_state_file_rel_path_fallback()` now separate strict config validation from diagnostic default-path behavior. `tests/core/services/test_project_state.py` covers missing config, malformed config, custom docs roots, and fallback behavior. |
| Closure evidence | Closed on 2026-05-09 by adding strict config plumbing to project-state load/save/validation, routing CLI state command use cases through strict mode after `validate_initialized`, and preserving fallback semantics for diagnostics and direct service use. |
| Impact | Diagnostics can be less precise in uninitialized or malformed repos, even though mutation paths fail earlier. |
| Remediation | Migrate command/use-case callers to the strict helper wherever repo config must be trusted. Keep fallback only for diagnostics that intentionally explain default paths. |
| Definition of done | Missing/malformed config produces `CONFIG_MISSING` or the documented diagnostic result in every affected command; doctor behavior remains useful for uninitialized repos; tests cover both strict and fallback callers. |
| Verification commands | `./.venv/bin/pytest -q tests/core/services/test_project_state.py tests/core/use_cases/test_doctor_repository.py tests/core/use_cases/test_index_repository.py tests/adapters/test_cli_state.py` |

## Recent Plan Assessment

Assessment date: 2026-05-08.

Reviewed source plans:

- `MEMINIT-PLAN-008` - Agentic Coding vNext Programme
- `MEMINIT-PLAN-009` - Phase 0 Detailed Implementation Plan
- `MEMINIT-PLAN-010` - Phase 1 Detailed Implementation Plan
- `MEMINIT-PLAN-011` - Phase 2 Detailed Implementation Plan
- `MEMINIT-PLAN-012` - Phase 3 Detailed Implementation Plan
- `MEMINIT-PLAN-013` - Phase 4 Detailed Implementation Plan
- `MEMINIT-PLAN-014` - Phase 5 Detailed Implementation Plan

Summary:

| Plan | Assessment |
| ---- | ---------- |
| `MEMINIT-PLAN-009` | No open backlog identified. The plan records completion, and the corresponding Phase 0 tests/docs are present. |
| `MEMINIT-PLAN-010` | No open runtime backlog identified. Capabilities, correlation IDs, explain, contract matrix coverage, and v3 schema docs are present. |
| `MEMINIT-PLAN-011` | No open runtime backlog identified. Graph index fields, schemas, resolve/identify/link updates, and external testbed note are present. TD-001 is closed. |
| `MEMINIT-PLAN-012` | No open backlog identified. Protocol registry, check/sync, fixture coverage, runbook guidance, and external testbed note are present. |
| `MEMINIT-PLAN-013` | Runtime surface appears implemented. TD-006, TD-007, TD-008, and TD-009 are closed. |
| `MEMINIT-PLAN-014` | Core Phase 5 features are present. TD-002 and TD-004 remain open because they are planned or recorded improvements not superseded by later implementation; TD-003 and TD-005 are closed. |

## Closed, Superseded, and Rejected Items

Closed items remain in the backlog table with closure evidence so their
original context and verification commands stay near the implementation
handoff. Current closed items: TD-001, TD-003, TD-005, TD-006, TD-007,
TD-008, and TD-009.

## Change History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-28 | Codex | Initial standalone review-debt register. |
| 0.2 | 2026-05-08 | Codex | Reworked into a structured professional debt register, assessed MEMINIT-PLAN-008 through MEMINIT-PLAN-014, and added live unsuperseded gaps from Phase 5 plus state/index hardening debt. |
