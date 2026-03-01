---
document_id: MEMINIT-PRD-004
type: PRD
title: Brownfield Adoption Hardening
status: Approved
version: "1.0"
last_updated: 2026-03-01
owner: GitCmurf
docops_version: "2.0"
area: Adoption
description: "Harden scan and fix workflows to bring existing repos to first-green quickly and safely."
keywords:
  - brownfield
  - scan
  - fix
  - migration
  - adoption
  - safety
related_ids:
  - MEMINIT-PLAN-003
  - MEMINIT-STRAT-001
  - MEMINIT-PRD-003
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PRD-004
> **Owner:** GitCmurf
> **Status:** Implemented
> **Version:** 1.0
> **Last Updated:** 2026-03-01
> **Type:** PRD
> **Area:** Adoption

# PRD: Brownfield Adoption Hardening

## Executive Summary

Meminit already provides `scan`, `check`, and `fix`, but the brownfield adoption path still requires heavy manual interpretation and iteration. This PRD defines improvements to scanning accuracy, migration planning, and safe auto-remediation so existing repositories can reach first-green faster and with less risk. The epic is explicitly safety-first and never performs destructive actions without explicit user intent.

## Plain-English Overview

Today, `meminit scan` gives high-level hints, and `meminit fix` applies a limited set of changes. That leaves humans or agents to guess how to move, rename, and annotate many files. This epic turns the scan into a concrete migration plan and makes fixes more predictable. The end result is a guided, low-risk path from a messy docs folder to a compliant DocOps setup.

## Problem Statement

Brownfield repos often have hundreds of Markdown files, inconsistent layouts, partial frontmatter, and mixed naming conventions. Meminit's current scan lacks per-file recommendations and confidence, and fix lacks plan-driven remediation. This causes slow adoption, higher manual effort, and inconsistent outcomes that are hard for agents to automate.

## Goals

1. Improve scanning accuracy and provide per-file recommendations with rationale.
2. Generate a deterministic migration plan artifact for agents and humans.
3. Expand auto-fix coverage without breaking the safety invariants in MEMINIT-STRAT-001.
4. Reduce time-to-first-green for repos up to the declared size class.

## Non-Goals

1. Rewriting document content for style or tone.
2. Deleting files or directories.
3. Auto-approving documents or promoting status.
4. Implementing a full project management migration system.

## Target Users

- Human developers migrating an existing repo to Meminit.
- Agent orchestrators that need a deterministic migration plan and safe application.
- CI systems validating post-migration compliance.

## Scope

In scope:

- Scan improvements that produce per-file recommendations with confidence and rationale.
- A migration plan artifact that can be applied by `meminit fix`.
- Expanded `fix` coverage for common metadata and filename issues.
- Config guidance for `docops.config.yaml` based on observed repo structure.

Out of scope:

- Re-structuring non-Markdown content.
- Refactoring or splitting documents based on semantics.

## Success Metrics

- A repo with up to 200 governed Markdown files can reach first-green in under 120 minutes.
- `meminit scan` produces actionable recommendations for at least 90 percent of governed Markdown files.
- `meminit fix` can resolve at least 70 percent of violations without manual edits, while preserving safety invariants.

## Functional Requirements

### FR-1 Scan Report v2

Requirement: `meminit scan` MUST produce a per-file scan report that includes a recommended type, recommended target directory, and missing metadata fields. The report MUST include a confidence score and rationale for each recommendation.

Plain English: The scan should tell you what to do with each file and why it thinks that is correct.

Implementation notes: Use heuristics from path segments, existing frontmatter, filename patterns, and first heading text. Always record which heuristic triggered the recommendation.

### FR-2 Migration Plan Artifact

Requirement: `meminit scan` MUST be able to write a migration plan artifact to disk. The plan MUST be deterministic, machine-readable, and safe to re-run. It MUST include a list of actions, required metadata changes, and any file moves or renames.

Plain English: The scan should output a concrete plan that a human or agent can review and then apply.

Implementation notes: Add a `--plan <path>` flag that writes a JSON plan. The plan must not mutate the repo.

### FR-3 Plan-Driven Fixes

Requirement: `meminit fix` MUST accept a migration plan and apply it when `--no-dry-run` is set. In dry-run mode, it MUST report the actions it would take.

Plain English: Fix should be able to apply the scan plan, or at least show exactly what it would do.

Implementation notes: Introduce a `--plan` option that reads the scan plan and enforces ordering. Ensure plans are validated before applying.

### FR-4 Expanded Auto-Fix Coverage

Requirement: `meminit fix` MUST expand beyond current behavior to address common brownfield issues, including missing frontmatter blocks, missing document IDs, non-conforming filenames, and simple type-directory mismatches.

Plain English: Fix should handle the most common issues automatically, without rewriting the document body.

Implementation notes: Use existing `FixRepositoryUseCase` and extend it with safe insertion of the MEMINIT metadata block and configurable filename normalization rules.

### FR-5 Safety Invariants

Requirement: No action in `scan` or `fix` may delete content. `fix` MUST remain dry-run by default. All moves and renames MUST be safe-path-validated.

Plain English: The tool should never destroy or silently rewrite content.

Implementation notes: Reuse `ensure_safe_write_path` and log all actions in the fix report. Prevent any operation that would overwrite an existing file without explicit confirmation.

### FR-6 Config Guidance

Requirement: The scan report MUST include recommended updates to `docops.config.yaml`, including `docs_root`, `type_directories`, and `namespaces` where relevant.

Plain English: The scan should tell you how to configure Meminit for the repo you already have.

Implementation notes: Extend the existing config suggestion logic in `ScanRepositoryUseCase` with confidence and reasoning fields.

### FR-7 Deterministic Outputs

Requirement: Scan and fix outputs MUST be deterministic and stable, aligning with the output contract defined in MEMINIT-PRD-003.

Plain English: Agents should not have to normalize outputs to understand what changed.

Implementation notes: Sort plan actions by path and action type. Use stable IDs for plan items.

### FR-8 Performance Targets

Requirement: For repos with up to 200 governed Markdown files, `meminit scan` MUST complete in under 10 seconds on a typical developer machine.

Plain English: Scans should be fast enough to run as part of a migration loop.

Implementation notes: Use lazy file reads and avoid full content parsing unless needed for heuristics.

## Migration Plan Format (Draft)

The migration plan is a standalone JSON document. It MUST be deterministic and safe to re-run.

```json
{
  "plan_version": "1.0",
  "generated_at": "2026-02-18T21:40:00Z",
  "root": "/path/to/repo",
  "actions": [
    {
      "id": "A001",
      "action": "add_frontmatter",
      "path": "docs/decisions/2020-foo.md",
      "confidence": 0.82,
      "rationale": ["path_segment:decisions", "title:Decision"],
      "metadata": {
        "document_id": "MEMINIT-ADR-042",
        "type": "ADR",
        "title": "Decision: Foo",
        "status": "Draft",
        "version": "0.1",
        "owner": "__TBD__",
        "docops_version": "2.0",
        "last_updated": "2026-02-18"
      }
    }
  ]
}
```

Plain English: The plan is a list of specific actions, like "add frontmatter" or "rename file," with explanations so humans can review it.

## Implementation Details

### Code Changes

- Extend `ScanRepositoryUseCase` in `src/meminit/core/use_cases/scan_repository.py` to produce per-file recommendations, confidence, and rationale.
- Add a new plan writer in `src/meminit/core/services/scan_plan.py` that serializes deterministic plans.
- Extend `FixRepositoryUseCase` in `src/meminit/core/use_cases/fix_repository.py` to accept a plan and apply actions safely.
- Add plan validation logic that rejects invalid or unsafe actions before applying.
- Extend CLI `meminit scan` with `--plan` and `meminit fix` with `--plan` and `--format json` if not already present.

### Documentation Changes

- Add a SPEC document describing the scan plan format and how to review it.
- Update migration runbooks to include the plan-based workflow.

### Testing Requirements

- Add unit tests for scan heuristics and confidence scoring.
- Add tests for plan serialization and validation.
- Add integration tests that apply a plan and confirm idempotent results.
- Add performance tests for scan time on a sample 200-doc fixture.

## Rollout Plan

1. Implement scan report v2 and plan export.
2. Add plan validation and dry-run application.
3. Add safe application mode behind `--no-dry-run`.
4. Update docs and runbooks.

## Open Questions

1. Should plan files be JSON only, or do we also support YAML?
2. Should `meminit fix` be able to generate a plan without running `scan` first?
3. Should scan confidence thresholds be configurable in `docops.config.yaml`?

## Related Documents

- MEMINIT-STRAT-001
- MEMINIT-PLAN-003
- MEMINIT-PRD-003
