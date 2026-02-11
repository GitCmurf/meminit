---
document_id: MEMINIT-ADR-008
type: ADR
title: Exclude governance templates from compliance scanning
status: Draft
version: 0.1
last_updated: 2025-12-14
owner: GitCmurf
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-ADR-008
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2025-12-14
> **Type:** ADR

# MEMINIT-ADR-008: Exclude governance templates from compliance scanning

- **Date decided:** 2025-12-14
- **Deciders:** Repo maintainers
- **Status:** Draft

## 1. Context & Problem Statement

The repository includes template files intended as scaffolds. Templates are often incomplete and intentionally contain placeholders. Treating templates as “governed documents” produces noisy failures and undermines the usefulness of `meminit check`.

## 2. Decision Drivers

- Avoid false positives and “always failing” repos.
- Keep templates flexible and allow placeholders.
- Maintain a clear boundary between governed docs and scaffolding assets.

## 3. Options Considered

- **Scan templates like normal docs**
  - Pros: uniform behavior.
  - Cons: templates regularly violate schema (by design), making checks noisy and unhelpful.
- **Exclude templates subtree**
  - Pros: keeps compliance focused on real docs; allows placeholders.
  - Cons: templates aren’t automatically validated (future could add dedicated template linting).

## 4. Decision Outcome

- **Chosen option:** Exclude `docs/00-governance/templates/` from `meminit check` scanning.

## 5. Consequences

- Positive: compliance scanning remains actionable for repositories.
- Negative: template quality checks must be handled separately (future work).

## 6. Implementation Notes

- Exclusion implemented in `src/meminit/core/use_cases/check_repository.py` via an excluded subtree list.

## 7. Validation & Compliance

- Tests ensure template markdown does not generate frontmatter violations.

## 8. Alternatives Rejected

- Scanning templates as governed docs: rejected due to expected placeholder content.

## 9. Supersession

- Supersedes: none
- Superseded by: none

## 10. Notes for Agents

- Keywords: templates, exclusions, false positives
- Code anchors: `src/meminit/core/use_cases/check_repository.py`
