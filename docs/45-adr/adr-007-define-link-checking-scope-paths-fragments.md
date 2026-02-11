---
document_id: MEMINIT-ADR-007
type: ADR
title: Define link checking scope (paths, fragments)
status: Draft
version: 0.1
last_updated: 2025-12-14
owner: GitCmurf
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-ADR-007
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2025-12-14
> **Type:** ADR

# MEMINIT-ADR-007: Define link checking scope (paths, fragments)

- **Date decided:** 2025-12-14
- **Deciders:** Repo maintainers
- **Status:** Draft

## 1. Context & Problem Statement

Broken links degrade trust and make agent navigation unreliable. However, “link checking” can mean many things (filesystem paths, IDs, anchors, external URLs). We need a v0.1 scope that is useful and low-risk.

## 2. Decision Drivers

- Avoid false positives in common markdown usage (e.g., file links with `#fragment`).
- Keep link checking deterministic and local (no network).
- Keep scope small until indexing/ID-resolution exists.

## 3. Options Considered

- **Filesystem-only link checking**
  - Pros: simple, deterministic, local.
  - Cons: does not validate “ID links”.
- **Filesystem + anchor validation**
  - Pros: stronger correctness.
  - Cons: requires parsing markdown headings/IDs; more complexity.
- **ID resolution via index**
  - Pros: stable doc-to-doc references even when files move.
  - Cons: depends on `index` feature (not yet implemented).

## 4. Decision Outcome

- **Chosen option (v0.1):** Validate that file-path targets exist; ignore external targets and ignore fragments when checking existence.
- **Explicitly out of scope (v0.1):** resolving ID targets and validating anchors.

## 5. Consequences

- Positive: catches real broken file links; avoids fragment false positives.
- Negative: documents must avoid using markdown-link syntax for raw IDs until ID resolution exists.

## 6. Implementation Notes

- Link checker: `src/meminit/core/services/validators.py` (`LinkChecker`)
- Behavior: strips `#...` before file existence checks; ignores `http(s)://`, `mailto:`, and anchor-only links.

## 7. Validation & Compliance

- Tests cover: missing targets, existing targets, external links ignored, fragment links treated correctly.

## 8. Alternatives Rejected

- Anchor validation: deferred.
- ID resolution: deferred until `index` exists.

## 9. Supersession

- Supersedes: none
- Superseded by: none

## 10. Notes for Agents

- Keywords: link checker, fragment, local-only validation
- Code anchors: `src/meminit/core/services/validators.py`
