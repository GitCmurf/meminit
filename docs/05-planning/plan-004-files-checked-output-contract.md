---
document_id: MEMINIT-PLAN-004
type: PLAN
title: files_checked output contract refactor
status: Draft
version: "0.2"
last_updated: 2026-02-18
owner: Product Team
docops_version: "2.0"
area: Agentic Integration
description: "Execution plan for redefining files_checked, adding counters, and bumping output_schema_version to 2.0."
keywords:
  - output
  - contract
  - files_checked
  - counters
  - json
related_ids:
  - MEMINIT-PRD-003
  - MEMINIT-SPEC-004
  - MEMINIT-SPEC-003
  - MEMINIT-PLAN-003
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PLAN-004
> **Owner:** Product Team
> **Status:** Draft
> **Version:** 0.2
> **Last Updated:** 2026-02-18
> **Type:** PLAN
> **Area:** Agentic Integration

# PLAN: files_checked output contract refactor

## Preamble: Objectives and Rationale

This plan implements a breaking change to Meminit's JSON output contract. The change is justified because the current `files_checked` semantics are ambiguous and mix distinct concepts (existing files, missing paths, schema failures). This refactor makes the output unambiguous for agent orchestration and enables reliable automated reasoning. The change also adds explicit counters for missing paths, schema failures, warnings, and violations, and bumps `output_schema_version` to 2.0 to make the breaking change explicit.

Primary objectives:
- Redefine `files_checked` to count only existing markdown files actually parsed and validated.
- Add explicit counters for missing paths, schema failures, warnings, violations, files with warnings, files outside docs root, and checked paths.
- Bump `output_schema_version` to 2.0 across all JSON outputs and artifacts.
- Keep the implementation modular, deterministic, and test-driven in line with MEMINIT-PRD-003 and MEMINIT-SPEC-004.

## Execution Plan Checklist

### 1) Spec-First Updates

- [x] Update `MEMINIT-SPEC-004` to reflect `output_schema_version: 2.0`, redefine `files_checked`, add new counters, and update examples to v2.0.
- [x] Update `MEMINIT-SPEC-003` with the new `files_checked` definition, counter semantics, and v2.0 example payloads.
- [x] Create or update the JSON schema artifact `docs/20-specs/agent-output.schema.v2.json` to match the v2 contract and link it from `MEMINIT-SPEC-004`.

### 2) Domain Model Changes

- [x] Extend `CheckResult` in `src/meminit/core/domain/entities.py` with the new counters.
- [x] Update the `CheckResult` docstring to define each counter precisely and reflect the new `files_checked` semantics.

### 3) Core Logic Changes

- [x] Redefine `files_checked` in `CheckRepositoryUseCase.execute_targeted` to count only existing markdown files validated.
- [x] Add and populate `missing_paths_count`, `schema_failures_count`, `warnings_count`, `violations_count`, `files_with_warnings`, `files_outside_docs_root_count`, and `checked_paths_count`.
- [x] Ensure `success` is computed using the new counters and strict-mode rules.
- [x] Keep `PATH_ESCAPE` and single missing path behavior as top-level error envelopes (unchanged).
- [x] Update full-repo `meminit check` (non-targeted mode) JSON output to include the same counters as targeted checks.

### 4) CLI Output and Contracts

- [x] Bump `OUTPUT_SCHEMA_VERSION` to `2.0` in `src/meminit/core/services/output_contracts.py`.
- [x] Replace hard-coded `"1.0"` in `src/meminit/core/services/error_codes.py` with the shared constant.
- [x] Update `meminit check --format json` to emit the new counters and v2.0 schema version.
- [x] Update any other JSON outputs that embed `output_schema_version` (including index generation output in `IndexRepositoryUseCase`).
- [x] Update `src/meminit/cli/main.py` text output summaries if they depend on the old `files_checked` meaning, to keep human output aligned.

### 5) Tests (TDD and Regression)

- [x] Update `tests/core/use_cases/test_check_repository.py` assertions for the new `files_checked` semantics and counters.
- [x] Update `tests/adapters/test_cli.py` for v2.0 schema version and new counters in JSON output.
- [x] Update index-related tests (`tests/core/use_cases/test_index_repository.py`, `tests/core/services/test_repo_layout.py`) for v2.0 schema version.
- [x] Add a schema validation test that validates a representative `check` JSON payload against `agent-output.schema.v2.json`.

### 6) Artifacts and Validation

- [x] Regenerate `docs/01-indices/meminit.index.json` using `meminit index` to reflect `output_schema_version: 2.0`.
- [x] Run `meminit check` to confirm doc compliance after spec updates.
- [x] Run `pytest` to validate all updated tests and new schema-validation tests.

### 7) Quality Gate and Acceptance Criteria

- [x] Confirm `files_checked` equals the count of existing, parsed markdown files only.
- [x] Confirm all new counters are present and correctly populated in JSON output.
- [x] Confirm `output_schema_version` is `2.0` in all JSON outputs and the index artifact.
- [x] Confirm examples in specs match actual output behavior.
- [x] Confirm `MEMINIT-SPEC-004` prose sections explicitly document the new counter semantics and success rules (not only examples).

## Definition of Done

- [x] Specs updated (MEMINIT-SPEC-003 and MEMINIT-SPEC-004) and aligned with schema v2.0.
- [x] Code updated with new counters and new `files_checked` semantics.
- [x] Tests updated and passing, including schema validation.
- [x] Index artifact regenerated to v2.0.
- [x] `meminit check` passes with no violations.

## Non-Goals (Explicitly Deferred)

- Runbook updates (per instruction).
- Full CLI output-envelope unification across all commands.
