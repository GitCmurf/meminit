---
document_id: MEMINIT-ADR-010
type: ADR
title: Use Apache-2.0 License
status: Approved
version: "1.0"
last_updated: "2025-12-18"
owner: GitCmurf
docops_version: "2.0"
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-ADR-010
> **Owner:** GitCmurf
> **Status:** Approved
> **Version:** 1.0
> **Last Updated:** 2025-12-18
> **Type:** ADR

# MEMINIT-ADR-010: Use Apache-2.0 License

- **Date decided:** 2025-12-18
- **Status:** Approved
- **Deciders:** GitCmurf

## 1. Context & Problem Statement

Meminit is a CLI tool and library for DocOps and repository compliance. We need to choose an open source license that encourages adoption and contribution while providing standard protections for contributors and maintainers. The license must support:

- Usage in commercial and non-commercial projects.
- Vendoring or embedding Meminit in other tools.
- A low-friction contribution process (ideally without a CLA).
- Clear attribution requirements.

## 2. Decision Drivers

- **Adoption:** We want Meminit to be widely used and integrated into various workflows and tools.
- **Contribution Friction:** We want to minimize barriers to entry for contributors (avoiding complex CLAs if possible).
- **Legal Clarity:** We need a well-understood, standard license.
- **Attribution:** We want to ensure that if Meminit is redistributed, credit is given (via NOTICE/LICENSE preservation).
- **Patent Protection:** Explicit patent grants are desirable for modern open source projects with an "infrastructure" footprint.

## 3. Options Considered

- **Option A:** Apache License 2.0

  - Pros: Permissive, includes patent grant, requires preservation of copyright and NOTICE file (good for attribution), widely accepted in enterprise.
  - Cons: Slightly more complex than MIT (due to NOTICE/patent clauses).
  - Risks: None significant for a standard OSS project.

- **Option B:** MIT License

  - Pros: Extremely simple, very permissive.
  - Cons: No explicit patent grant, attribution requirements are weaker (just license text).
  - Risks: Less protection against patent litigation.

- **Option C:** GPLv3 (Copyleft)
  - Pros: Ensures improvements remain open source.
  - Cons: "Viral" nature makes it difficult to embed in proprietary tools or for some corporate users to adopt.
  - Risks: Reduced adoption due to compatibility fears.

## 4. Decision Outcome

- **Chosen option:** Option A: Apache License 2.0
- **Why this option:**
  - It balances permissiveness with protection (patent grant).
  - It allows for wide adoption and embedding in other tools (commercial or not).
  - The NOTICE file requirement ensures proper attribution if Meminit is vendored, which is a likely use case for a CLI tool.
  - It supports a "No CLA" contribution model, as the license itself is sufficient for inbound contributions.
- **Scope/Applicability:** Applies to the Meminit codebase at first public open source release.

## 4.1 Effective Date

- **Decision date:** 2025-12-18 (this ADR).
- **Effective date:** first public OSS release (target tag: `v0.5.0`, immediately before “Agentic Integration” begins; see MEMINIT-STRAT-001 and MEMINIT-PLAN-003).
- **Until effective date:** the repository remains “All Rights Reserved” (see root `LICENSE` placeholder).

## 5. Consequences

- **Positive:**
  - Users can confidently use Meminit in almost any context.
  - Contributors have clear patent safety.
  - We do not need a CLA for standard contributions.
- **Negative / trade-offs:**
  - We must maintain a LICENSE and NOTICE file.
  - Redistributors must include these files.
- **Follow-up migrations / cleanups:**
  - Update root `LICENSE` to Apache-2.0 text at the public release cut.
  - Ensure `NOTICE` is present and accurate at the public release cut.
  - Align packaging metadata (`pyproject.toml`) with Apache-2.0 at the public release cut.

## 6. Implementation Notes

- Plan: At the public release cut, replace the placeholder root `LICENSE` with the Apache-2.0 license text, and ensure `NOTICE` is present.
- Owner: GitCmurf.

## 7. Validation & Compliance

- **Tests required:** None.
- **Tooling checks:** Compliance tools should verify the presence of the LICENSE file.

## 8. Alternatives Rejected

- **MIT:** Rejected due to lack of patent grant and weaker attribution assurance.
- **GPL:** Rejected to maximize adoption and embedding potential.

## 9. Supersession

- Supersedes: None
- Superseded by: None

## 10. Notes for Agents

- **Key entities:** Apache-2.0, LICENSE, NOTICE.
- **Usage:** Agents acting on this repo should respect the license terms.
- **Code anchors:** root `LICENSE` file.
