---
document_id: MEMINIT-ADR-011
type: ADR
title: Support Monorepo Namespaces
status: Draft
version: '0.1'
last_updated: '2025-12-29'
owner: GitCmurf
docops_version: '2.0'
---

<!-- MEMINIT_METADATA_BLOCK -->
> **Document ID:** MEMINIT-ADR-011
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2025-12-29
> **Type:** ADR

# MEMINIT-ADR-011: Support Monorepo Namespaces

- **Date decided:** 2025-12-29
- **Status:** Draft
- **Deciders:** GitCmurf (repo owner/maintainer)
- **Consulted:** (none)
- **Informed:** Contributors / downstream orchestrators
- **References:** AIDHA, Architext, Odyverse monorepo layouts (local pilots)

## 1. Context & Problem Statement
Meminit was initially designed around a **single governed docs root** (default `docs/`) and a **single repository prefix**
for `document_id` generation and validation. That model works well for single-package repos, but breaks down for common
monorepo structures that have both “central docs” and “package-local docs”.

Observed examples:
- `AIDHA`: central `docs/` plus package-local docs at `packages/*/docs/`
- `Odyverse`: central `docs/` plus app-local docs at `apps/*/docs/`
- `Architext`: central `docs/` with subtrees like `docs/adrs/` (folder overrides; still a single docs root)

Without first-class namespaces, adopting Meminit in a monorepo forces awkward choices:
- move/merge all docs into a single tree (high churn), or
- leave package docs ungoverned/unindexed (reduces utility), or
- invent wrapper scripts per repo (violates Meminit’s “unix-like tool” goal).

Scope:
- Provide an explicit way to define **multiple governed docs roots** and (optionally) **multiple ID namespaces**
  (distinct `repo_prefix` values) within a single repo.
- Keep behavior deterministic and **opt-in** via `docops.config.yaml`.

Out of scope (for v0.1 of this feature):
- Auto-detecting namespaces in `meminit check` based on `pnpm-workspace.yaml` / other tooling.
- Cross-namespace refactoring of links or content.
- Multi-schema “DocOps version negotiation” across namespaces (supported via configuration, not automatic policy).

## 2. Decision Drivers
- Determinism: avoid “magic detection” during enforcement.
- Tool-agnostic: work for `pnpm`, `yarn`, `npm workspaces`, `nx`, `turbo`, etc. without coupling to a build system.
- Brownfield adoption: allow incremental opt-in (govern central docs first, then package docs).
- Orchestrator friendliness: keep artifacts machine-readable and contract-versioned.
- Backward compatibility: existing single-root repos should behave exactly as before.
- Safety: keep `fix` conservative; avoid writing outside configured docs roots.

## 3. Options Considered
For each option, capture summary, evidence, pros, cons, and risks.

- **Option A: Single docs root only**
  - Pros: simplest model.
  - Cons: forces churn (moving docs) or leaves package docs ungoverned.
  - Evidence: AIDHA and Odyverse both have meaningful docs under package/app subtrees.
  - Risks / unknowns: adoption fails or becomes repo-specific duct tape.

- **Option B: Path-based `repo_prefix` overrides only**
  - Pros: could keep one schema and one set of rules.
  - Cons: still assumes one docs root; package-local docs usually live *outside* central `docs/`.
  - Risks / unknowns: ends up re-implementing “multiple docs roots” implicitly (harder to reason about).

- **Option C: Explicit namespaces (multiple governed docs roots)**
  - Pros: clear opt-in boundary; tool-agnostic; aligns with real-world monorepo layouts.
  - Cons: config surface expands; needs careful precedence rules and tests.

## 4. Decision Outcome
- **Chosen option:** Option C (explicit namespaces)
- **Why this option:** It models real monorepo layouts directly while keeping enforcement deterministic and opt-in.
- **Scope/Applicability:**
  - `meminit check` scans all configured namespaces.
  - `meminit fix` operates only on violations within configured namespaces.
  - `meminit migrate-ids` allocates IDs per namespace’s `repo_prefix`.
  - `meminit index` produces a repository-level index using a configurable `index_path`.
- **Status gates:** Approved when (a) end-to-end monorepo fixture tests pass, and (b) docs specify the config surface clearly.

## 5. Consequences
- Positive:
- Monorepos can adopt Meminit incrementally without moving documentation trees.
- Package/app docs can be governed and indexed with their own ID namespace when desired.
- Index artifacts can represent multiple namespaces explicitly (useful for orchestrators/agents).
- Negative / trade-offs:
- Config becomes more complex than single-root mode.
- Performance may be slightly slower in large repos (multiple directory walks).
- Overlapping docs roots can create ambiguity; Meminit will pick the most specific match.
- Follow-up migrations / cleanups:
- Add a “review packet” workflow so humans can override namespace/type decisions deterministically during migration.
- Consider adding an optional validation that `document_id` prefix matches the namespace `repo_prefix` (policy decision).

## 6. Implementation Notes
- Plan / milestones:
  1. Add namespace-aware repo config loader (`load_repo_layout`).
  2. Update core use cases to iterate namespaces (check/fix/index/migrate-ids/resolve/identify).
  3. Add tests for monorepo fixtures (multiple docs roots, shared schema, custom index path).
- Owners: GitCmurf
- Backward compatibility / rollout strategy:
  - If `docops.config.yaml` does not define `namespaces`, Meminit behaves as a single-root repo (as before).
  - If `namespaces` is present, it defines the governed roots explicitly.
- Telemetry / monitoring to add: none (CLI tool; rely on tests + CI gates).

Config sketch:
```yaml
schema_path: docs/00-governance/metadata.schema.json
index_path: .meminit/meminit.index.json
namespaces:
  - name: root
    repo_prefix: AIDHA
    docs_root: docs
  - name: phyla
    repo_prefix: PHYLA
    docs_root: packages/phyla/docs
```

## 7. Validation & Compliance
- Tests required:
  - Unit tests for `load_repo_layout` + multi-namespace behavior.
  - E2E-ish fixture that builds index and resolves IDs across namespaces.
- Tooling checks: `pytest -q`, `meminit check --root .`
- Success metrics:
  - A repo with multiple configured docs roots can go “time-to-first-green” using the brownfield runbook.

## 8. Alternatives Rejected
- Option A rejected: blocks practical monorepo adoption.
- Option B rejected: insufficient because it doesn’t naturally model multiple docs roots.

## 9. Supersession
- Supersedes: none
- Superseded by: none

## 10. Notes for Agents
- Key entities/terms: namespace, docs_root, repo_prefix, index_path, monorepo, workspace
- Code anchors:
  - `src/meminit/core/services/repo_config.py` (`load_repo_layout`, `RepoLayout`)
  - `src/meminit/core/use_cases/check_repository.py`
  - `src/meminit/core/use_cases/index_repository.py`
  - `src/meminit/core/use_cases/migrate_ids.py`
  - `src/meminit/core/use_cases/resolve_document.py`
  - `src/meminit/core/use_cases/identify_document.py`
  - `tests/core/services/test_repo_layout.py`
- Known gaps / TODOs:
  - Add a “review packet” workflow for human overrides during migration.
  - Add optional `--namespace` targeting for `new` (and possibly `fix`) to reduce accidental writes in large monorepos.

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
