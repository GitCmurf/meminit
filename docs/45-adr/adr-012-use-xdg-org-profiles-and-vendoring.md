---
document_id: MEMINIT-ADR-012
type: ADR
title: Use XDG Org Profiles and Vendoring
status: Draft
version: '0.2'
last_updated: '2025-12-31'
owner: GitCmurf
docops_version: '2.0'
---

<!-- MEMINIT_METADATA_BLOCK -->
> **Document ID:** MEMINIT-ADR-012
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.2
> **Last Updated:** 2025-12-31
> **Type:** ADR

# MEMINIT-ADR-012: Use XDG Org Profiles and Vendoring

- **Date decided:** 2025-12-31
- **Status:** Draft
- **Deciders:** GitCmurf
- **Consulted:** N/A
- **Informed:** Contributors; downstream repos adopting Meminit
- **References:**
  - `docs/60-runbooks/runbook-001-org-setup.md`
  - `src/meminit/core/services/org_profiles.py`
  - `src/meminit/core/use_cases/install_org_profile.py`
  - `src/meminit/core/use_cases/vendor_org_profile.py`
  - `src/meminit/core/use_cases/org_status.py`

## 1. Context & Problem Statement
Meminit is a DocOps enforcement tool. It needs a practical way to apply **organisation-level standards** across many repositories while keeping repository compliance **deterministic** (no “it passed on my machine, failed in CI” because of drift).

Organisations (or solo developers acting as “an org of one”) want:
- a single “default baseline” that applies across repos;
- a predictable place to store that baseline locally so new repos default correctly; and
- an explicit mechanism to prevent **unintentional drift** (standards changing silently due to tool updates, remote references, or machine state).

This ADR introduces **Org Profiles** as a first-class concept and defines where they live (global) and how they are made deterministic inside a repo (vendoring + lockfile).

Terminology note: **to vendor** (verb) means “copy and pin a dependency into your repository so it is self-contained and deterministic”. In this ADR, “vendoring org standards” means copying the org profile’s schema/templates (and optionally its ORG governance Markdown docs) into the repository and recording a digest in a lock file.

**In scope**
- Global (user-machine) storage and selection of org standards using XDG base directories.
- Repo-local vendoring to make standards deterministic and reviewable in PRs.
- A safe upgrade story (explicit action, no background auto-upgrades).

**Out of scope**
- A hosted service for distributing organisation standards.
- Automatically rewriting existing repositories without explicit user action.

## 2. Decision Drivers
- **Determinism / “no unintentional drift”:** a repo’s compliance baseline must not change silently.
- **Security:** avoid adding network and credential requirements to CI/agents.
- **Portability:** works cross-platform; follows established filesystem conventions.
- **DX/UX:** new repos should “just work”; org setup should be clear and low-friction.
- **Composability:** other tooling (e.g., Architext) should be able to call Meminit as a stable, Unix-like primitive.

## 3. Options Considered
For each option: summary, evidence, pros, cons, risks.

- **Option A: Central “governance repo” referenced by URL**
  - Summary: org standards live in a dedicated repository; repos reference it via URL/submodule/release.
  - Pros:
    - single “source of truth” (conceptually)
    - central updates are straightforward
  - Cons:
    - introduces drift unless pinned to an exact commit/tag everywhere
    - adds network + credentials to CI and agent environments
    - complicates offline / air-gapped usage
  - Risks / unknowns:
    - operational/security complexity tends to grow over time.

- **Option B: XDG global org profile + repo vendoring (lockfile)**
  - Summary: Meminit ships a packaged default profile; users can install an org profile to XDG; repos can vendor that profile and lock its digest.
  - Pros:
    - new repos default to org baseline if installed globally
    - vendoring makes repo compliance deterministic and reviewable
    - avoids background network dependency
    - explicit, safe upgrades (`--force` required to overwrite lock)
  - Cons:
    - adds commands and concepts (“install vs vendor”) that must be documented well
  - Risks / unknowns:
    - without clear runbooks, users may confuse global machine state with repo state.

- **Option C: Repo-only vendoring (no global profile)**
  - Summary: no global profile; every repo carries its own schema/templates and updates them manually.
  - Pros:
    - maximum determinism per repo
    - simplest runtime model
  - Cons:
    - fails the “new repo defaults to org baseline” goal
    - higher overhead: every repo must bootstrap or copy standards manually
  - Risks / unknowns:
    - organisations will reinvent a global distribution mechanism anyway.

## 4. Decision Outcome
- **Chosen option:** Option B (XDG global org profile + vendoring with lockfile).
- **Why this option:** It meets the “no unintentional drift” requirement via vendoring + lockfile while still enabling “org defaults” via a global, XDG-located install.
- **Scope/Applicability:** Applies to all Meminit users who want consistent standards across multiple repos; vendoring is the deterministic contract used for CI and collaboration.
- **Status gates:** Move Draft → In Review once the org flows are tested and documented; move In Review → Approved after a pilot confirms deterministic behavior across machines/CI.

## 5. Consequences
- Positive:
- **Deterministic repos:** vendoring + lock file makes baseline standards auditable in PRs and stable in CI.
- **Good defaults:** global profile provides “new repo defaults to org standards” without copy/paste.
- **Safe upgrades:** no silent drift; updates require an explicit action (`meminit org vendor --force`).
- Negative / trade-offs:
- Adds a small new surface area (commands, docs, lock file).
- Two layers exist (global profile vs vendored profile), which must be communicated clearly.
- Follow-up migrations / cleanups:
- Improve profile versioning and multi-profile support beyond `default`.
- Provide helper docs for users who manage dotfiles and want to pin/sync the global profile directory.

## 6. Implementation Notes
- Plan / milestones:
  - Ship a packaged default org profile under `meminit.core.assets`.
  - Provide XDG path resolution and profile loading.
  - Add CLI entrypoints:
    - `meminit org install` (packaged → XDG)
    - `meminit org vendor` (XDG/packaged → repo + lock file)
    - `meminit org status` (drift visibility)
  - Ensure `meminit init` writes schema/templates from the resolved org profile.
- Owners: GitCmurf
- Backward compatibility / rollout strategy:
  - Global install is optional; packaged default works without it.
  - Vendoring is opt-in and refuses to overwrite `.meminit/org-profile.lock.json` unless `--force` is set.
- Telemetry / monitoring to add: None (Meminit favors deterministic artefacts over telemetry).

## 7. Validation & Compliance
- Tests required (unit/integration/e2e):
  - Profile resolution prefers global profile when installed; otherwise uses packaged default.
  - Install and vendor flows honor `--dry-run`.
  - Vendor flow writes expected files and lock file; refuses overwrite without `--force`.
  - Status reports drift when the lock digest differs from the resolved profile.
- Tooling checks:
  - `pytest`
  - `meminit check --root .`
- Operational checks (runbooks):
  - `docs/60-runbooks/runbook-001-org-setup.md` documents install/vendor/status and the upgrade policy.
- Success metrics / acceptance criteria:
  - A freshly initialized repo passes `meminit doctor` + `meminit check` without manual schema/template copying.
  - A repo with vendored profile produces identical check results across machines and CI.

## 8. Alternatives Rejected
- Option A: forces network/credential/pinning complexity that vendoring already solves more simply.
- Option C: loses “org defaults” and pushes every repo to manually bootstrap standards.

## 9. Supersession
- Supersedes: none
- Superseded by: none

## 10. Notes for Agents
- Key entities/terms for RAG: org profile, XDG, vendoring, lockfile, drift, determinism
- Code anchors (paths, modules, APIs) this ADR governs:
  - `src/meminit/core/services/xdg_paths.py`
  - `src/meminit/core/services/org_profiles.py`
  - `src/meminit/core/use_cases/install_org_profile.py`
  - `src/meminit/core/use_cases/vendor_org_profile.py`
  - `src/meminit/core/use_cases/org_status.py`
  - `src/meminit/core/use_cases/init_repository.py`
  - `src/meminit/cli/main.py` (`meminit org ...`)
- Known gaps / TODOs:
  - Multi-profile selection and a well-documented upgrade cadence.
  - “Review packet” workflow for brownfield repos (human approval loop).

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
