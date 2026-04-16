---
document_id: MEMINIT-PLAN-009
type: PLAN
title: Phase 0 Detailed Implementation Plan
status: Approved
version: '0.3'
last_updated: '2026-04-14'
owner: GitCmurf
docops_version: '2.0'
area: AGENT
description: Detailed implementation plan for MEMINIT-PLAN-008 Phase 0 foundation
  hardening.
keywords:
- phase-0
- planning
- testing
- determinism
related_ids:
- MEMINIT-PLAN-008
- MEMINIT-PLAN-003
- MEMINIT-PRD-003
---

> **Document ID:** MEMINIT-PLAN-009
> **Owner:** GitCmurf
> **Status:** Approved
> **Version:** 0.3
> **Last Updated:** 2026-04-14
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Detailed implementation plan for MEMINIT-PLAN-008 Phase 0 foundation hardening.

# PLAN: Phase 0 Detailed Implementation Plan

## Context

MEMINIT-PLAN-008 establishes Phase 0 as the mandatory entry point for the
next implementation wave. That phase exists to remove ambiguity and instability
from the current baseline before any new agent-platform features are added.

This document decomposes Phase 0 into concrete implementation tasks that are
small enough to deliver in focused PRs while still preserving the repo rule
that code, docs, and tests ship together.

The planning boundary for this document is deliberately narrow:

- remediation determinism in `fix`
- CLI JSON contract matrix coverage
- stderr isolation hardening for machine-consumed modes
- minimal governing-document alignment needed to close the phase

## 1. Purpose

Define the detailed implementation steps for Phase 0 of MEMINIT-PLAN-008 so
that the work can be executed without reopening scope questions already
resolved by the parent programme.

## 2. Scope

In scope:

- Normalize the date source used by `FixRepositoryUseCase`
- Add deterministic regression tests for the affected fix paths
- Add a CLI command-matrix test for JSON envelope conformance
- Add representative stderr-isolation tests for JSON mode
- Update the governing planning documents to reflect the detailed Phase 0
  breakdown and completion status

Out of scope:

- `capabilities`, `correlation_id`, or `explain`
- graph enrichment in `index`
- protocol drift tooling
- work-queue state expansion
- streaming or NDJSON support

## 3. Work Breakdown

### 3.1 Workstream A: Remediation Clock Hardening

Problem:

- `FixRepositoryUseCase` currently mixes `date.today()` and
  `datetime.now(timezone.utc)`.
- That creates date-boundary drift and has already produced a failing test.

Implementation tasks:

1. Introduce a single internal helper for the governed `last_updated` value in
   `FixRepositoryUseCase`.
2. Make the helper derive from one timezone-aware source.
3. Allow the source to be controlled in tests so the behavior is deterministic.
4. Route all `last_updated` autofill paths through that helper.

Acceptance criteria:

1. The affected remediation paths no longer mix date sources.
2. The fix behavior is deterministic under test.
3. The existing failing test is either fixed directly or replaced by stronger,
   explicit assertions against the chosen time source.

### 3.2 Workstream B: Deterministic Fix Regression Coverage

Problem:

- The current tests catch one visible failure, but the behavior should be
  locked down more directly.

Implementation tasks:

1. Add or update tests to assert the exact `last_updated` value when the clock
   is controlled.
2. Cover both the legacy message-based autofill path and the minimum-frontmatter
   autofill path if both remain live.
3. Ensure the tests verify string output in the schema-expected date form.

Acceptance criteria:

1. The tests do not depend on the wall-clock date of the machine running them.
2. The chosen date policy is explicit in the assertions.

### 3.3 Workstream C: CLI JSON Contract Matrix

Problem:

- PRD-003 requires broad command coverage, but the repository does not yet have
  one integration-style matrix that exercises the claimed JSON surface as a
  single contract.

Implementation tasks:

1. Build a fresh-repo helper fixture that can support the main command surface.
2. Enumerate the command paths that currently claim JSON support, including
   relevant group subcommands.
3. For each command path, invoke a minimal valid JSON-mode call and validate the
   resulting envelope against the v2 schema.
4. Check that the `command` field matches the canonical command name for that
   path.

Acceptance criteria:

1. Every command path in scope emits schema-valid JSON.
2. The matrix is deterministic and maintainable.
3. The test fails clearly when a future command claims JSON support but breaks
   the envelope contract.

### 3.4 Workstream D: stderr Isolation Hardening

Problem:

- There is already targeted coverage for JSON-mode logging behavior, but the
  command surface would benefit from representative coverage outside the
  `new` path.

Implementation tasks:

1. Select a small representative set of commands from different command families
   such as read-only repo inspection and stateful operations.
2. Run them with `--verbose --format json`.
3. Assert that STDOUT still contains a machine-parseable JSON object and that
   any debug or reasoning output is routed away from the JSON payload.

Acceptance criteria:

1. Representative commands beyond `new` prove the stdout and stderr contract.
2. The tests remain stable across Click versions with and without
   `mix_stderr=False`.

### 3.5 Workstream E: Documentation Alignment

Problem:

- Phase 0 is a contract-hardening phase. Its closeout must be visible in the
  planning layer, not just in code and tests.

Implementation tasks:

1. Update MEMINIT-PLAN-008 to reference this detailed breakdown.
2. Record the detailed planning artifact in MEMINIT-PLAN-003 if needed for
   discoverability.
3. Update this document and the parent plan if implementation materially changes
   the planned scope.

Acceptance criteria:

1. The planning chain is explicit: roadmap -> programme -> detailed phase plan.
2. The detailed plan remains aligned with what was actually implemented.

## 4. Recommended Delivery Sequence

1. Workstream A: Remediation Clock Hardening
2. Workstream B: Deterministic Fix Regression Coverage
3. Workstream C: CLI JSON Contract Matrix
4. Workstream D: stderr Isolation Hardening
5. Workstream E: Documentation Alignment

Reason:

- A and B remove the known red test first.
- C and D then harden the broader contract surface.
- E closes the phase properly under Meminit DocOps rules.

## 5. Exit Criteria for Phase 0

Phase 0 can be considered complete when all of the following are true:

1. The repository test suite is green.
2. The known `fix` date nondeterminism issue is resolved.
3. The CLI JSON command matrix exists and passes.
4. Representative stderr-isolation tests exist and pass.
5. The governed planning documents are aligned with the shipped work.

## 6. Implementation Outcome

Implementation completed on 2026-04-14.

Delivered changes:

- `FixRepositoryUseCase` now uses a single controlled datetime source for
  governed `last_updated` autofill behavior.
- Regression tests pin the remediation date deterministically instead of
  depending on wall-clock time.
- A JSON command-matrix adapter test now exercises the main CLI JSON surface
  and validates envelopes against the v3 schema.
- Representative verbose JSON tests now prove the actual runtime contract:
  stdout remains machine-safe while debug logs are emitted on stderr.

Verification:

- `./.venv/bin/pytest -q tests/core/use_cases/test_fix_repository.py tests/adapters/test_cli_phase0.py`
- `./.venv/bin/pytest -q`

Outcome against exit criteria:

1. Repository test suite green: satisfied.
2. Known `fix` date nondeterminism resolved: satisfied.
3. CLI JSON command matrix exists and passes: satisfied.
4. Representative stderr-isolation tests exist and pass: satisfied.
5. Governed planning documents aligned with shipped work: satisfied by this
   document update and the corresponding parent-plan update.

## 7. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-14 | GitCmurf | Initial draft created via `meminit new` |
| 0.2 | 2026-04-14 | Codex | Replaced stub with detailed Phase 0 workstreams, acceptance criteria, and delivery sequence |
| 0.3 | 2026-04-14 | Codex | Recorded Phase 0 implementation outcome, verification commands, and exit-criteria closeout |
