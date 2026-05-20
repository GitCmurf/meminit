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
| `Narrowed` | Accepted debt whose scope has been reduced and re-baselined. |
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
| Status | Closed |
| Owner | CLI/Core maintainers |
| Source | MEMINIT-PLAN-014 Phase 5 constant-memory objective |
| Related plans | `MEMINIT-PLAN-008`, `MEMINIT-PLAN-014`, `MEMINIT-PLAN-015`, `MEMINIT-SPEC-011`, `MEMINIT-FDD-014` |
| Evidence | `src/meminit/core/services/stream_events.py` owns `StreamItem`, `StreamProgress`, `StreamSummary`, and `StreamingResult`; `src/meminit/cli/main.py` drains `iter_stream()` results through `CoreStreamingProducer` for `index`, `scan`, and `context --deep`. |
| Narrowing evidence | `rg "CallableStreamingProducer" src/meminit/cli` returns no matches; the remaining `CallableStreamingProducer` helper is confined to `tests/cli/test_stream_emitter.py` for test coverage. |
| Impact | Closed: the production NDJSON path no longer depends on CLI-local closure adapters or public result-object materialization before the first stream item. |
| Remediation | Completed by moving streaming payload types into core, routing production CLI streaming through `CoreStreamingProducer`, adding core `iter_stream()` producers, and sharing index build artifacts between JSON and NDJSON paths. |
| Definition of done | Shared iterator plumbing is in place for JSON and NDJSON; regression tests fail if `index`, `scan`, or `context --deep` cannot yield the first item before fully materializing the command payload; SPEC-011/FDD-014 wording is updated if the API shape changes. |
| Verification commands | `./.venv/bin/pytest -q tests/core/use_cases/test_streaming_laziness.py tests/cli/test_stream_emitter.py tests/adapters/test_streaming_cli.py tests/cli/test_streaming_equivalence.py tests/cli/test_streaming_determinism.py` |
| Closure evidence | Closed on 2026-05-10 after `scan`, `context --deep`, and `index` gained instrumentation regressions for first-item emission before public result materialization. SPEC-011 and FDD-014 document the command-level guarantees, including the index correctness boundary that validation and artifact writes complete before public node/edge items are emitted. |

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
| Status | Closed |
| Owner | Repository owner |
| Source | MEMINIT-PLAN-014 exit criterion 11 and MEMINIT-RUNBOOK-006 closeout checklist |
| Related plans | `MEMINIT-PLAN-014`, `MEMINIT-LOG-001` |
| Evidence | The sanitized external testbed run is recorded in `MEMINIT-LOG-001`, including the command list, provenance, cache evidence, and sanitized summary. |
| Prepared artifact | `MEMINIT-LOG-001` is the governed closure evidence for TD-004. |
| Impact | External-testbed criterion is now verifiable from committed artifacts. |
| Remediation | None. TD-004 is closed. |
| Definition of done | The evidence artifact contains no secrets or PII, references the exact commands from MEMINIT-RUNBOOK-006, records the sanitized operator summary, and passes `meminit check --format json`. |
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

### TD-010: Built-in templates exist for only ADR/PRD/FDD despite ~20 configured types

| Field | Value |
| ----- | ----- |
| Priority | P1 |
| Status | Open |
| Owner | Templates maintainers |
| Source | Greenfield dogfood run #0 (bedtime-alexa), 2026-05-20; see `MEMINIT-PLAN-016` |
| Related plans | `MEMINIT-PLAN-016`, `MEMINIT-PRD-006` |
| Evidence | `meminit new STRAT` (and `meminit new PLAN`) return `data.template.applied=false`, `source=none` and emit a markerless skeleton. `init` scaffolds templates for only ADR/PRD/FDD (`src/meminit/core/assets/org_profiles/default/templates/`) while the default config defines ~20 `document_types`. |
| Impact | Foundational doc types (STRAT, PLAN, SPEC, RUNBOOK, DESIGN, etc.) get a hollow scaffold, undermining the AI-first authoring contract (agents have no section markers/prompts to fill). Directly weakens greenfield value. |
| Remediation | Ship built-in templates with section markers, agent prompts, `required` flags, and `initial_content` for all first-class types; surface them through `meminit new --format json`. |
| Definition of done | `meminit new <TYPE>` returns `template.applied=true` for ADR/PRD/FDD/SPEC/RUNBOOK/PLAN/STRAT/DESIGN at minimum; built-in templates carry section markers; tests cover resolution for the new types. |
| Verification commands | `./.venv/bin/pytest -q tests/core/services/test_template_resolver.py tests/core/use_cases/test_new_document.py` |

### TD-011: Skeleton fallback emits no section markers or agent prompts

| Field | Value |
| ----- | ----- |
| Priority | P2 |
| Status | Open |
| Owner | Document factory maintainers |
| Source | Greenfield dogfood run #0 (bedtime-alexa), 2026-05-20 |
| Related plans | `MEMINIT-PLAN-016`, `MEMINIT-PRD-006` |
| Evidence | When no template resolves, `meminit new` emits a body of only `# TYPE: Title` / `## Context` / `## Content` with no `<!-- MEMINIT_SECTION: -->` markers, `<!-- AGENT: -->` prompts, or `initial_content`. |
| Impact | Skeleton documents are not machine-fillable via the JSON section contract, so even the fallback path violates the AI-first principle. |
| Remediation | Have the skeleton emit at least one stable section marker with an agent prompt and `initial_content`, so orchestrators can fill it deterministically. |
| Definition of done | Skeleton output includes >=1 `MEMINIT_SECTION` marker surfaced in `data.template.sections`; tests assert markers and `initial_content` exist for a no-template type. |
| Verification commands | `./.venv/bin/pytest -q tests/core/use_cases/test_new_document.py` |

### TD-012: migrate-ids does not repair repo_prefix mismatches

| Field | Value |
| ----- | ----- |
| Priority | P3 |
| Status | Open |
| Owner | Migration maintainers |
| Source | Greenfield dogfood run #0 (bedtime-alexa), 2026-05-20 |
| Related plans | `MEMINIT-PLAN-016` |
| Evidence | After changing `repo_prefix` in `docops.config.yaml`, governed docs whose IDs use the old prefix fail `check` with `ID_PREFIX`, but `meminit migrate-ids --dry-run` reports zero actions (it only targets non-`REPO-TYPE-SEQ` legacy IDs). The new `init --repo-prefix` flag (TD: closed in this branch) reduces, but does not eliminate, the need: prefix changes after init still have no on-rails repair. |
| Impact | A user who renames their prefix post-init must hand-edit every governed `document_id` with no tooling support or guidance. |
| Remediation | Either extend `migrate-ids` to re-stamp IDs when the configured `repo_prefix` no longer matches existing IDs (with dry-run preview and `--rewrite-references`), or emit explicit advice pointing at the mismatch. |
| Definition of done | A prefix change followed by `migrate-ids --dry-run` previews the re-stamping (or emits actionable advice); applying it makes `check` green; cross-references are updated under `--rewrite-references`; tests cover the prefix-mismatch path. |
| Verification commands | `./.venv/bin/pytest -q tests/core/use_cases/test_migrate_ids.py` |

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
| `MEMINIT-PLAN-014` | Core Phase 5 features are present. TD-002, TD-003, TD-004, and TD-005 are closed. |

## Closed, Superseded, and Rejected Items

Closed items remain in the backlog table with closure evidence so their
original context and verification commands stay near the implementation
handoff. Current closed items: TD-001, TD-002, TD-003, TD-004, TD-005,
TD-006, TD-007, TD-008, and TD-009.

## Change History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-28 | Codex | Initial standalone review-debt register. |
| 0.2 | 2026-05-08 | Codex | Reworked into a structured professional debt register, assessed MEMINIT-PLAN-008 through MEMINIT-PLAN-014, and added live unsuperseded gaps from Phase 5 plus state/index hardening debt. |
| 0.3 | 2026-05-17 | CMF | Closed TD-004 after approving the sanitized external testbed evidence in MEMINIT-LOG-001. |
| 0.4 | 2026-05-20 | CMF | Added TD-010 (template breadth), TD-011 (skeleton has no section markers), and TD-012 (migrate-ids prefix mismatch) from greenfield dogfood run #0 (bedtime-alexa); see MEMINIT-PLAN-016. |
