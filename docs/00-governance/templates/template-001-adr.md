---
document_id: <REPO>-ADR-<SEQ>
type: ADR
title: <Decision Title>
status: Draft
version: 0.1
last_updated: <YYYY-MM-DD>
owner: <Team or Person>
area: <AREA>
docops_version: 2.0
template_type: adr-standard
template_version: 1.1
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** <REPO>-ADR-<SEQ> > **Owner:** <Team or Person> > **Status:** Draft
> **Version:** 0.1
> **Last Updated:** <YYYY-MM-DD> > **Type:** ADR

# <REPO>-ADR-<SEQ>: <Decision Title>

- **Date decided:** <YYYY-MM-DD>
- **Status:** Draft | In Review | Approved | Superseded
- **Deciders:** <names/roles>
- **Consulted:** <stakeholders consulted>
- **Informed:** <who must be notified>
- **References:** <issues/PRs/spikes/incidents/benchmarks>

## 1. Context & Problem Statement

Describe the motivating problem, constraints, and forces. State the scope and what is explicitly out of scope.

## 2. Decision Drivers

List the key forces that influence the decision (e.g., latency, cost, safety, operability, compliance, UX, delivery risk).

## 3. Options Considered

For each option, capture summary, evidence, pros, cons, and risks.

- **Option A:** <name>
  - Pros:
  - Cons:
  - Evidence / benchmarks:
  - Risks / unknowns:
- **Option B:** <name>
  - Pros:
  - Cons:
  - Evidence / benchmarks:
  - Risks / unknowns:
- **Option C:** <name>
  - Pros:
  - Cons:
  - Evidence / benchmarks:
  - Risks / unknowns:

## 4. Decision Outcome

- **Chosen option:** <Option A/B/C>
- **Why this option:** <brief rationale tied to drivers>
- **Scope/Applicability:** <where this applies; boundaries>
- **Status gates:** what must be true to move from Draft -> In Review -> Approved.

## 5. Consequences

- Positive:
- Negative / trade-offs:
- Follow-up migrations / cleanups:

## 6. Implementation Notes

- Plan / milestones:
- Owners:
- Backward compatibility / rollout strategy:
- Telemetry / monitoring to add:

## 7. Validation & Compliance

- Tests required (unit/integration/e2e):
- Tooling checks (lint/format/static analysis):
- Operational checks (dashboards/alerts/runbooks):
- Success metrics or acceptance criteria:

## 8. Alternatives Rejected

List rejected options with one-line reason each.

## 9. Supersession

- Supersedes: <ID or none>
- Superseded by: <ID or none>

## 10. Notes for Agents

- Key entities/terms for RAG:
- Code anchors (paths, modules, APIs) this ADR governs:
- Known gaps / TODOs:

---

### DocOps Compliance (for tools)

- Frontmatter MUST satisfy `docs/00-governance/metadata.schema.json` (including `docops_version`).
- H1 MUST match `^# [A-Z]+-ADR-\d+: .+`.
- Sections required (case-insensitive, in this order):
  1. Context & Problem Statement
  2. Decision Drivers
  3. Options Considered
  4. Decision Outcome
  5. Consequences
  6. Implementation Notes
  7. Validation & Compliance
  8. Alternatives Rejected
  9. Supersession
  10. Notes for Agents
- Status values MUST be one of: Draft | In Review | Approved | Superseded.
- The `superseded_by` frontmatter field must be present when status is "Superseded".
- If `Supersedes` is set, link to the prior ADR in the body.
- For LLM/tooling ease, each list item should begin with a bold label where provided (e.g., `- **Status:** ...`).
- Optional machine-readable rules live in `docs/00-governance/templates/adr.compliance.json` for validator tooling.
