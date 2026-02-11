---
document_id: MEMINIT-ADR-005
type: ADR
title: Define compliance checking rules and severities
status: Draft
version: 0.1
last_updated: 2025-12-14
owner: GitCmurf
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-ADR-005
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2025-12-14
> **Type:** ADR

# MEMINIT-ADR-005: Define compliance checking rules and severities

- **Date decided:** 2025-12-14
- **Deciders:** Repo maintainers
- **Status:** Draft

## 1. Context & Problem Statement

`meminit check` must provide predictable outputs that can block CI on true governance violations while still surfacing “nits” (like filenames) without forcing disruptive churn.

## 2. Decision Drivers

- Separate “blocking” governance issues from “advisory” hygiene issues.
- Keep rules stable and testable.
- Ensure errors are understandable (field context, file location).

## 3. Options Considered

- **Error/Warning severities**
  - Pros: clear CI semantics; supports incremental adoption.
  - Cons: requires a stable classification scheme.
- **All-or-nothing errors**
  - Pros: simple.
  - Cons: too disruptive for migrations; discourages adoption.

## 4. Decision Outcome

- **Chosen option:** Two severities:
  - **Error**: schema violations, invalid/missing schema, invalid IDs, duplicate IDs, broken links, unhandled exceptions.
  - **Warning**: filename convention and directory mapping mismatches.

## 5. Consequences

- Positive: teams can adopt gradually while still enforcing core invariants.
- Negative: warnings may be ignored; future policy can tighten warnings to errors as needed.

## 6. Implementation Notes

- Checker: `src/meminit/core/use_cases/check_repository.py`
- Severity enum: `src/meminit/core/domain/entities.py`
- Link checking: `src/meminit/core/services/validators.py` (`LinkChecker`)

## 7. Validation & Compliance

- CLI exits non-zero when any violations exist (including warnings) today; policy may evolve.
- Tests cover: schema errors, ID errors, filename warnings, directory mismatch warnings, link checking.

## 8. Alternatives Rejected

- All errors: rejected for migration/adoption ergonomics.

## 9. Supersession

- Supersedes: none
- Superseded by: none

## 10. Notes for Agents

- Keywords: severity, warning vs error, CI gating
- Code anchors: `src/meminit/core/use_cases/check_repository.py`, `src/meminit/cli/main.py`
