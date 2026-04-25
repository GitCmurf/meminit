---
document_id: MEMINIT-PRD-008
type: PRD
title: Greenfield Repository Bootstrap
status: Draft
version: "0.2"
last_updated: 2026-04-25
owner: Meminit maintainers
area: INIT
docops_version: "2.0"
template_type: prd-standard
template_version: "2.0"
description: "Production-grade, profile-driven, idempotent greenfield bootstrap for Meminit-governed repositories. Defines a registry-backed installer architecture (DocOps tree, protocol assets, pre-commit, CI, GitHub hygiene), a persisted setup manifest, deterministic upgrade semantics, and a reusable installer contract that the planned brownfield hardening will consume."
keywords:
  - init
  - bootstrap
  - greenfield
  - profiles
  - protocol-assets
  - projections
  - pre-commit
  - ci
  - manifest
  - idempotency
  - upgrade
related_ids:
  - MEMINIT-STRAT-001
  - MEMINIT-PRD-003
  - MEMINIT-PRD-004
  - MEMINIT-PRD-005
  - MEMINIT-PRD-007
  - MEMINIT-SPEC-006
  - MEMINIT-SPEC-007
  - MEMINIT-SPEC-008
  - MEMINIT-FDD-003
  - MEMINIT-FDD-012
  - MEMINIT-GOV-001
  - MEMINIT-GOV-003
  - MEMINIT-ADR-009
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PRD-008
> **Owner:** Meminit maintainers
> **Status:** Draft
> **Version:** 0.2
> **Last Updated:** 2026-04-25
> **Type:** PRD
> **Area:** INIT

<!-- MEMINIT_SECTION: title -->

# PRD: Greenfield Repository Bootstrap

<!-- MEMINIT_SECTION: toc -->

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Context: What Exists Today](#2-context-what-exists-today)
3. [Problem Statement](#3-problem-statement)
4. [Design Constraints](#4-design-constraints)
5. [Goals and Non-Goals](#5-goals-and-non-goals)
6. [Proposed Solution](#6-proposed-solution)
7. [Functional Requirements](#7-functional-requirements)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [CLI Surface](#9-cli-surface)
10. [JSON Envelope Profiles](#10-json-envelope-profiles)
11. [Profiles Catalog](#11-profiles-catalog)
12. [Phased Implementation Plan](#12-phased-implementation-plan)
13. [Acceptance Criteria](#13-acceptance-criteria)
14. [Alternatives Considered](#14-alternatives-considered)
15. [Risks and Mitigations](#15-risks-and-mitigations)
16. [Resolved Decisions and Open Questions](#16-resolved-decisions-and-open-questions)
17. [Related Documents](#17-related-documents)
18. [Version History](#18-version-history)

<!-- MEMINIT_SECTION: executive_summary -->

## 1. Executive Summary

Meminit's `meminit init` already creates a baseline DocOps tree, a `docops.config.yaml`, and a small set of governed protocol assets via `ProtocolAssetRegistry`. It is, however, an opinionated scaffolder rather than a production-grade setup product: it has no profile system, no persisted record of what was installed, no separation between vendor-neutral and tool-specific protocol surfaces, and no first-class installers for the quality gates (pre-commit, CI, GitHub hygiene) that mature repositories rely on.

This PRD specifies the next iteration: a **registry-backed, profile-driven, idempotent greenfield bootstrap** built from small, composable installer modules with a uniform `plan → apply → verify` contract. Each installer is independently testable and reusable; together they produce a repository that passes its own `meminit check`, `meminit doctor`, and `meminit protocol check` on first attempt, records its configuration in `.meminit/setup.yaml`, and can be deterministically upgraded.

The architecture is explicitly designed to be **the substrate for the next-step brownfield hardening** described in [MEMINIT-PRD-004](./prd-004-brownfield-adoption-hardening.md). Greenfield is the simpler case (empty input, full apply); brownfield reuses the same installers but feeds them a different `plan()` produced from `meminit scan`. Solidifying greenfield first lets us harden every installer's apply path against a known starting state before exposing it to the much larger surface area of arbitrary existing repositories.

<!-- MEMINIT_SECTION: context -->

## 2. Context: What Exists Today

This section anchors the proposal in the current codebase so engineering does not need to rediscover it.

### 2.1 Implemented today

| Capability | Implementation | Location |
| --- | --- | --- |
| `meminit init` use case | `InitRepositoryUseCase` | `src/meminit/core/use_cases/init_repository.py` |
| Protocol asset registry | `ProtocolAssetRegistry`, `ProtocolAsset`, `AssetOwnership` | `src/meminit/core/services/protocol_assets.py` |
| Drift detection | `classify_drift`, `DriftOutcome` | `src/meminit/core/services/protocol_assets.py` |
| Drift CLI | `meminit protocol check`, `meminit protocol sync` | `src/meminit/cli/main.py`; use cases `protocol_check.py`, `protocol_sync.py` |
| Output envelope (v3) | `output_schema_version: "3.0"` | [MEMINIT-SPEC-008](../20-specs/spec-008-agent-output-contract-v2.md) |
| Templates v2 | `meminit new` template resolution | [MEMINIT-SPEC-007](../20-specs/spec-007-templates-v2.md) |
| Repo discovery | `meminit context --format json` | `src/meminit/cli/main.py` |

The shipped `ProtocolAssetRegistry.default()` registers exactly three assets: `agents-md` (mixed), `meminit-docops-skill` (generated), and `meminit-brownfield-script` (generated, mode `0o755`). `AssetOwnership` currently has only two members: `GENERATED` and `MIXED`. There is **no** `PROJECTED` ownership class today; introducing it is part of the work this PRD authorises.

### 2.2 Gaps relative to a production-grade bootstrap

1. **No profile abstraction.** `init` accepts no `--profile` flag and has no concept of per-profile asset bundles.
2. **No persisted setup manifest.** Nothing on disk records which profile, projections, or installers were applied; upgrades have to rediscover state.
3. **Mixed canonical/projected paths.** `.codex/skills/meminit-docops` exists in the repo today as an ad-hoc symlink to `.agents/skills/meminit-docops`. There is no governed projection model.
4. **No installer commands for quality gates.** Pre-commit and CI workflows are crafted by hand per repo; there is no `install-precommit` or `install-ci` use case, and no contract for what they install per profile.
5. **No upgrade entrypoint.** `protocol sync` updates protocol assets but does not re-evaluate profiles, projections, hook bundles, or CI workflows holistically.
6. **No greenfield smoke test.** CI does not assert that `meminit init` on a clean directory produces a self-consistent repo on Linux **and** Windows.

### 2.3 Existing related work referenced by this PRD

- [MEMINIT-FDD-003 — Repository Scaffolding (`meminit init`)](../50-fdd/fdd-003-repository-scaffolding-meminit-init.md): current init feature design; this PRD supersedes its scope rather than its mechanism.
- [MEMINIT-FDD-012 — Protocol Asset Governance](../50-fdd/fdd-012-protocol-asset-governance.md): the registry, marker grammar, and drift classification this PRD extends.
- [MEMINIT-PRD-004 — Brownfield Adoption Hardening](./prd-004-brownfield-adoption-hardening.md): the consumer of the installer contract this PRD defines.
- [MEMINIT-PRD-003 — Agent Interface v1](./prd-003-agent-interface-v1.md), [MEMINIT-PRD-005 — Agent Interface v2](./prd-005-agent-interface-v2.md), [MEMINIT-SPEC-008](../20-specs/spec-008-agent-output-contract-v2.md): the JSON envelope and capability model that bootstrap commands must conform to.
- [MEMINIT-ADR-009 — Minimal Repo Configuration for Brownfield Adoption](../45-adr/adr-009-add-minimal-repo-configuration-for-brownfield-adoption.md): grounding for `docops.config.yaml` minimalism.

<!-- MEMINIT_SECTION: problem_statement -->

## 3. Problem Statement

A user adopting Meminit on a new repository today must:

- run `meminit init` (and accept whatever it produces),
- hand-write `.pre-commit-config.yaml`, `.editorconfig`, `.github/workflows/*.yml`, `CODEOWNERS`, PR templates, and issue templates,
- decide independently whether to expose skills via `.agents/`, `.codex/`, `.claude/`, or some combination, and keep them in sync,
- and discover after the fact, by running `meminit check` and `meminit protocol check`, whether the result is policy-consistent.

This produces three failure modes:

1. **Configuration drift between repos.** Two repos following the same internal "Meminit standard" diverge within weeks because there is no single declarative source of what "standard" means.
2. **Unsafe upgrades.** Without a manifest, future Meminit releases cannot know which assets to refresh, which to leave alone, or which projections the user opted into.
3. **Brittle agent surfaces.** Tool-specific paths (`.codex/`, `.claude/`) are maintained as ad-hoc copies or symlinks of `.agents/` content, so they silently rot when the canonical source updates.

The strategic problem is therefore not "improve `init`" but "define a small, composable installer architecture so that greenfield, brownfield, and upgrade are three different drivers of the same engine."


<!-- MEMINIT_SECTION: design_constraints -->

## 4. Design Constraints

These constraints are non-negotiable and derive from existing governance.

1. **Output envelope v3 (SPEC-008).** Every new and modified command MUST emit `output_schema_version: "3.0"` envelopes. Repo-aware commands MUST include `root`; repo-agnostic commands MUST omit it. See [MEMINIT-SPEC-008](../20-specs/spec-008-agent-output-contract-v2.md).
2. **Byte-invariance of governed documents (STRAT-001, GOV-001).** Bootstrap MUST NOT silently rewrite Approved governed documents. Mutable per-asset state lives in `.meminit/setup.yaml`, never in governed frontmatter.
3. **No writes outside the repo root.** All filesystem operations MUST go through `ensure_safe_write_path` (or equivalent) with symlink-escape protection. Existing tests (`test_init_refuses_symlink_escape`) MUST continue to pass.
4. **No secrets or PII (GOV-003).** No installer may emit secrets, credentials, or user PII. Generated workflows MUST use the standard `${{ secrets.* }}` indirection only.
5. **Dry-run by default for destructive operations.** Any command that mutates user-authored files (e.g., `upgrade-setup` touching `.pre-commit-config.yaml`) MUST be dry-run by default, consistent with [ADR-006](../45-adr/adr-006-design-auto-fix-workflow-dry-run-by-default.md).
6. **Reuse, do not duplicate, the protocol asset machinery.** `ProtocolAssetRegistry`, marker grammar, and `classify_drift` are the single source of truth for protocol asset payloads. Greenfield installers are clients of this registry, not parallel implementations.
7. **Cross-platform parity.** Linux and Windows are first-class; macOS is supported. File modes are advisory on Windows but MUST not crash. No POSIX-only shell snippets in canonical assets.

<!-- MEMINIT_SECTION: goals -->

## 5. Goals and Non-Goals

### 5.1 Goals

1. **Production-grade bootstrap.** A single `meminit init --profile standard` produces a repository that immediately passes `meminit check`, `meminit doctor`, and `meminit protocol check` with zero violations.
2. **Profile-driven configuration.** Top-level profiles (`minimal`, `standard`, `strict`) compose with optional add-ons (e.g., `agents:security-first`, `ci:github`, `projection:codex`).
3. **Persisted setup manifest.** `.meminit/setup.yaml` records the profile, add-ons, asset versions, and projection adapters in effect, so upgrades are deterministic.
4. **Modular installer architecture.** Each concern (DocOps tree, protocol assets, projections, pre-commit, CI, GitHub hygiene, editor settings) is an independent installer implementing a uniform contract.
5. **Brownfield-ready substrate.** Every installer exposes a `plan()` step that returns a deterministic plan compatible with the format defined in [MEMINIT-PRD-004 §FR-2](./prd-004-brownfield-adoption-hardening.md#fr-2-migration-plan-artifact); brownfield uses these plans without forking the apply path.
6. **Deterministic upgrade.** `meminit upgrade-setup` re-runs all installers from the recorded manifest and reports per-installer drift, with explicit dry-run and `--force` semantics matching `protocol sync`.
7. **Machine-readable everywhere.** All bootstrap commands emit SPEC-008 envelopes; all internal status passes through structured warnings/violations with stable error codes.

### 5.2 Non-Goals

1. Auto-mutating remote GitHub branch protection or organisation policies.
2. Live API integrations with vendor agent platforms (Codex, Claude, Gemini hosts). Projections write static repo-local files only.
3. Application-code scaffolding (no language-specific project bootstrapping beyond `.editorconfig` and basic ignore files).
4. A SaaS dashboard or hosted control plane.
5. Re-implementing brownfield migration in this PRD; this PRD provides the substrate, brownfield hardening (PRD-004) is a separate, sequenced workstream.
6. A plugin system for third-party installers in v1. The installer contract is internal-only until at least v2.

### 5.3 Success Metrics

| Metric | Target | Measurement |
| --- | --- | --- |
| **Time to first green** | < 60 s on Ubuntu CI | `meminit init --profile standard` to passing `meminit check && meminit doctor && meminit protocol check`. |
| **Idempotency** | 0 changes | `init` followed by a second `init` with identical inputs produces zero `created`/`updated` entries. |
| **Drift correctness** | 100 % | Fixture matrix of intentionally-corrupted assets (per drift outcome) is correctly classified by `protocol check` and remediated by `protocol sync` / `upgrade-setup`. |
| **Cross-platform parity** | green on Linux + Windows | Greenfield smoke job in CI passes on both. |
| **Manifest fidelity** | 100 % | For any sequence of `init` + `upgrade-setup`, `.meminit/setup.yaml` accurately describes the on-disk state (verified by contract tests). |
| **Brownfield reuse** | ≥ 80 % shared code | At PRD-004 implementation time, brownfield installers reuse ≥ 80 % of the apply-path code by line count. |

<!-- MEMINIT_SECTION: solution -->

## 6. Proposed Solution

### 6.1 Core Abstractions

The bootstrap is built from a small set of named abstractions. Each is independently testable and lives in a clear module.

| Abstraction | Module | Responsibility |
| --- | --- | --- |
| `BootstrapInstaller` (Protocol/ABC) | `core/services/bootstrap/installer.py` | Defines `id`, `plan()`, `apply()`, `verify()` for each concern. |
| `BootstrapPlan` | `core/services/bootstrap/plan.py` | Deterministic, serialisable list of `PlanAction` items per installer. |
| `Profile` | `core/services/bootstrap/profile.py` | Declarative bundle: which installers to run, their parameters, and which add-ons to layer on top. |
| `ProfileRegistry` | `core/services/bootstrap/profile_registry.py` | Resolves profile names to `Profile` instances; layered (built-in → org overlay → repo overlay). |
| `ProjectionAdapter` | `core/services/bootstrap/projections.py` | Defines how a canonical asset is reflected into a tool-specific path. Introduces the `PROJECTED` ownership class. |
| `SetupManifest` | `core/services/bootstrap/manifest.py` | Read/write of `.meminit/setup.yaml`. Single source of truth for "what is configured here". |
| `BootstrapOrchestrator` | `core/use_cases/bootstrap_repository.py` | Orchestrates installer ordering, dry-run, JSON envelope assembly. |

### 6.2 Installer Contract

Every installer implements:

```python
class BootstrapInstaller(Protocol):
    id: str                           # stable, kebab-case identifier
    version: str                      # semver of the installer's contract
    depends_on: tuple[str, ...]       # ids of installers that must run first

    def plan(self, ctx: BootstrapContext) -> BootstrapPlan: ...
    def apply(self, plan: BootstrapPlan, *, dry_run: bool) -> ApplyReport: ...
    def verify(self, ctx: BootstrapContext) -> VerifyReport: ...
```

- `plan()` is **read-only**. It inspects the repo and returns the actions needed to reach the desired state. This is the brownfield primitive: PRD-004's `meminit scan` will produce equivalent plans for existing repos.
- `apply()` is **idempotent**. If the desired state already holds, it returns an empty `ApplyReport` and does not touch disk.
- `verify()` is **side-effect-free**. It re-derives whether the installer's contract holds; it is the engine for `meminit doctor` and the post-apply assertion in CI.

Installer ids in v1: `docops-tree`, `docops-config`, `governance-templates`, `protocol-assets`, `projections`, `editorconfig`, `gitignore`, `pre-commit`, `ci-github`, `github-meta`, `manifest`. Each lives in its own submodule under `src/meminit/core/services/bootstrap/installers/`.

### 6.3 Profile Model

Profiles are declarative YAML bundles, packaged with Meminit (under `meminit.core.assets.profiles`) and overridable per-org or per-repo.

```yaml
# packaged: meminit/core/assets/profiles/standard.yaml
id: standard
version: "1.0"
extends: minimal
installers:
  docops-tree: {}
  docops-config: {}
  governance-templates: {}
  protocol-assets:
    bundle: meminit-docops
  projections:
    enabled: [codex]
  editorconfig: {}
  gitignore: {}
  pre-commit:
    bundle: standard
  ci-github:
    workflows: [docops, protocol-check, greenfield-smoke]
  github-meta:
    assets: [pr-template, issue-templates]
  manifest: {}
add_ons:
  available: [security-first, testing-first, monorepo]
```

Resolution precedence (highest wins): explicit CLI flags → repo overlay (`docops.config.yaml: bootstrap.profile_overlay`) → org overlay (XDG profile) → packaged built-in. Resolution and merge rules live in `ProfileRegistry.resolve()` and MUST be deterministic and pure.


### 6.4 Setup Manifest

`.meminit/setup.yaml` is the persisted record of the bootstrap. It is governed by Meminit (validated by `meminit doctor`) but is **not** a documentation artifact under `docs/`; it carries operational state, not narrative.

```yaml
# .meminit/setup.yaml
manifest_version: "1.0"
generated_at: "2026-04-25T10:00:00Z"
meminit_version: "0.X.Y"
profile:
  id: standard
  version: "1.0"
  add_ons: [security-first]
installers:
  - id: protocol-assets
    version: "1.0"
    assets:
      - id: agents-md
        ownership: mixed
        sha256: "…"
      - id: meminit-docops-skill
        ownership: generated
        sha256: "…"
  - id: projections
    version: "1.0"
    enabled: [codex]
    targets:
      - source: .agents/skills/meminit-docops/SKILL.md
        target: .codex/skills/meminit-docops/SKILL.md
        ownership: projected
  - id: pre-commit
    version: "1.0"
    bundle: standard
  - id: ci-github
    version: "1.0"
    workflows: [docops, protocol-check, greenfield-smoke]
```

The manifest schema is versioned independently from Meminit itself; `SetupManifest.load()` performs forward-compatible parsing and emits a `MEMINIT-WARN-MANIFEST-FUTURE` warning when the on-disk version is newer than the running CLI.

### 6.5 Projection Model

Projections are how a single canonical asset reaches multiple tool-specific paths without duplication. Each `ProjectionAdapter` declares:

- `source_asset_id`: an id known to `ProtocolAssetRegistry`.
- `target_path_template`: a parameterised path (e.g., `.codex/skills/{asset_id}/SKILL.md`).
- `transform`: an optional pure function from canonical payload to projected payload (default: identity).

A new `AssetOwnership.PROJECTED` value is introduced in `protocol_assets.py`. Projected files are wrapped in the same marker grammar as `GENERATED` assets but additionally record the `source_asset_id` in the begin marker (`source=<id>`), so `classify_drift` can distinguish a stale projection from a tampered generated file. `protocol check` and `protocol sync` extend their reporting to include projection-specific outcomes (`projection_stale`, `projection_orphaned`).

Built-in adapters in v1: `codex`, `claude`. Each is a small, declarative dataclass; adding a new adapter is a single-file change with paired tests.


<!-- MEMINIT_SECTION: requirements -->

## 7. Functional Requirements

Each requirement is normative and is the unit of acceptance for engineering. Each maps to one installer or to the orchestrator. `MUST`, `SHOULD`, `MAY` are used per RFC 2119.

### FR-1 Profile-driven entrypoint

`meminit init` MUST accept `--profile <id>` (default: `standard`), `--add-on <id>` (repeatable), `--projection <id>` (repeatable), and `--dry-run`. It MUST reject unknown ids with `MEMINIT-ERROR-UNKNOWN-PROFILE` / `…-UNKNOWN-ADDON` / `…-UNKNOWN-PROJECTION` and a structured `advice` entry listing valid ids.

### FR-2 Installer contract

A `BootstrapInstaller` Protocol MUST be defined in `core/services/bootstrap/installer.py` with the methods specified in §6.2. Every installer MUST be unit-testable in isolation against a `tmp_path` fixture, with no I/O outside the supplied `BootstrapContext.root`.

### FR-3 Plan/apply/verify symmetry

For every installer: running `apply()` after `plan()` returned an empty action list MUST be a no-op (zero filesystem writes). `verify()` on a freshly applied installer MUST return `outcome=ok`. These two invariants MUST be exercised by contract tests for every concrete installer.

### FR-4 DocOps tree installer

`docops-tree` MUST create the directory layout declared by [MEMINIT-FDD-003](../50-fdd/fdd-003-repository-scaffolding-meminit-init.md), respecting `docs_root` from `docops.config.yaml`. It MUST NOT overwrite existing directories.

### FR-5 DocOps config installer

`docops-config` MUST create or update `docops.config.yaml` to a profile-defined shape. On an existing file, it MUST diff structurally and MUST NOT reorder or strip user-added keys; conflicting keys produce a `MEMINIT-VIOLATION-CONFIG-CONFLICT` violation that the user resolves.

### FR-6 Governance templates installer

`governance-templates` MUST install the Templates v2 set (PRD, ADR, FDD, SPEC, RUNBOOK) to `<docs_root>/00-governance/templates/` per [MEMINIT-SPEC-007](../20-specs/spec-007-templates-v2.md). Templates are `MIXED` ownership: header region is managed, body is user-editable.

### FR-7 Protocol assets installer

`protocol-assets` MUST install the canonical assets registered in `ProtocolAssetRegistry` for the selected bundle. It MUST reuse `ProtocolAsset.render()` and the existing marker grammar; it MUST NOT introduce a parallel asset writer.

### FR-8 Projections installer

`projections` MUST install the projection targets declared by the selected adapters and record them in the manifest. Disabling a previously-enabled projection in `upgrade-setup` MUST emit a `projection_orphaned` warning and, only when `--remove-orphans` is set, delete the projected file.

### FR-9 Pre-commit installer

`pre-commit` MUST install or update `.pre-commit-config.yaml` per the selected bundle (`minimal`, `standard`, `strict`). It MUST reuse `InstallPrecommitUseCase` (or a refactored equivalent) to avoid duplicating hook logic. Existing user hooks MUST be preserved.

### FR-10 CI installer

`ci-github` MUST install GitHub Actions workflows per the selected list. The `greenfield-smoke` workflow MUST run `meminit init` in a clean directory on Ubuntu and Windows runners and assert green `check`, `doctor`, and `protocol check`. Workflows are `GENERATED` ownership.

### FR-11 GitHub meta installer

`github-meta` MUST install requested assets (`pr-template`, `issue-templates`, `CODEOWNERS`) under `.github/`. `CODEOWNERS` is `MIXED`; templates are `GENERATED`.

### FR-12 Editor and ignore installers

`editorconfig` MUST install `.editorconfig` (`GENERATED`). `gitignore` MUST install or extend `.gitignore` (`MIXED`, with a managed Meminit region for `.meminit/`, `.venv/`, etc.).

### FR-13 Manifest installer

`manifest` MUST be the last installer in every plan. It writes `.meminit/setup.yaml` reflecting the actual outcome (post-apply hashes, not pre-apply intent). On `--dry-run`, it writes nothing and reports the manifest it *would* have written.

### FR-14 Idempotent re-run

`meminit init --profile <same>` MUST be idempotent: a second run on an unchanged repo yields a SPEC-008 envelope where `data.installers[*].apply.created == [] && updated == []`, and exits 0.

### FR-15 Upgrade entrypoint

`meminit upgrade-setup` MUST read `.meminit/setup.yaml`, re-run `plan()` for every recorded installer, and report drift per installer. By default it is dry-run; `--no-dry-run` applies. `--profile <new>` performs a profile migration and MUST emit a `profile_migration` warning per installer affected.

### FR-16 JSON envelope conformance

Every command introduced or modified by this PRD MUST emit SPEC-008 envelopes with the command-specific `data` payload defined in §10. Repo-aware commands MUST set `root`. STDOUT MUST contain exactly one JSON object when `--format json` is used; all human logs go to STDERR.

### FR-17 Capability advertisement

`meminit capabilities` MUST advertise the new commands (`init`, `upgrade-setup`, etc.) and their option matrices, per [MEMINIT-PRD-005](./prd-005-agent-interface-v2.md).

### FR-18 Brownfield-compatible plan format

`BootstrapPlan` JSON serialisation MUST be a superset of the migration-plan format defined in [MEMINIT-PRD-004 §FR-2](./prd-004-brownfield-adoption-hardening.md#fr-2-migration-plan-artifact), so that `meminit fix --plan` can consume installer plans unchanged. Conformance MUST be enforced by a shared schema test.


## 8. Non-Functional Requirements

### NFR-1 Determinism

For identical inputs (profile, add-ons, projections, repo state, Meminit version) the bootstrap MUST produce byte-identical outputs across runs and platforms, except where the file payload itself encodes platform-relative data (e.g., line endings normalised to LF on write).

### NFR-2 Safety

All filesystem writes MUST go through `ensure_safe_write_path`. Symlink-escape and absolute-path-escape attempts MUST raise `MeminitError` with a stable error code and exit non-zero. No installer may shell out for file mutation; all writes are in-process.

### NFR-3 Performance

`meminit init --profile standard` on an empty directory MUST complete in under 10 seconds wall-clock on a baseline GitHub-hosted Ubuntu runner. `meminit doctor` after `init` MUST complete in under 5 seconds. Profile resolution MUST be O(profiles + add-ons) and free of network I/O.

### NFR-4 Observability

Every command emits a SPEC-008 envelope with `run_id` (UUIDv4). Per-installer outcomes MUST appear as structured `data.installers[]` entries; warnings, violations, and advice use the envelope-level arrays. Stable error codes MUST be registered in `error_codes.py` and surfaced via `meminit explain-error`.

### NFR-5 Maintainability

Each installer module MUST stay under 300 source lines. The orchestrator MUST stay under 200 lines. Cyclomatic complexity per public function MUST stay ≤ 10 (enforced by `ruff` configuration). Public APIs MUST have docstrings; modules MUST have module docstrings.

### NFR-6 Test pyramid

Per installer: (a) ≥ 1 contract test (idempotency + verify), (b) ≥ 3 unit tests (happy path, dry-run, conflict), (c) integration coverage in the orchestrator suite. Greenfield smoke runs on Linux and Windows in CI on every PR.

### NFR-7 Documentation parity

For every new module under `core/services/bootstrap/`, an FDD entry under `docs/50-fdd/` MUST exist or be created in the same PR (atomic Code + Docs + Tests, per `AGENTS.md`). The Setup Manifest schema MUST be specified in a SPEC document.

### NFR-8 Backwards compatibility

Existing `meminit init` invocations without `--profile` MUST continue to work and MUST default to the `standard` profile. The current shipped `ProtocolAssetRegistry.default()` asset set MUST remain functional unchanged. The `output_schema_version` for `init` MUST stay at `"3.0"`; only `data` is extended additively.

## 9. CLI Surface

| Command | Purpose | Mutates? |
| --- | --- | --- |
| `meminit init [--profile ID] [--add-on ID]… [--projection ID]… [--dry-run] [--format json]` | Greenfield bootstrap; idempotent | yes (unless `--dry-run`) |
| `meminit upgrade-setup [--no-dry-run] [--profile ID] [--remove-orphans] [--format json]` | Re-run installers from manifest, optionally migrate profile | dry-run by default |
| `meminit doctor [--format json]` | Run all installer `verify()` plus existing checks | no |
| `meminit protocol check [--format json]` | Existing command, extended for projections | no |
| `meminit protocol sync [--no-dry-run] [--format json]` | Existing command, extended for projections | dry-run by default |
| `meminit profiles list [--format json]` | List available profiles, add-ons, projections | no |

`meminit profiles list` is a thin read-only command exposing `ProfileRegistry.list()`; agents use it to discover the option matrix without parsing CLI help.

## 10. JSON Envelope Profiles

All envelopes follow SPEC-008 (`output_schema_version: "3.0"`). The `data` payload for new/modified commands is specified below. Schemas live under `tests/contracts/bootstrap/` and are imported by tests.

### 10.1 `init` and `upgrade-setup`

```json
{
  "data": {
    "profile": {"id": "standard", "version": "1.0", "add_ons": ["security-first"]},
    "projections": ["codex"],
    "dry_run": false,
    "manifest_path": ".meminit/setup.yaml",
    "installers": [
      {
        "id": "protocol-assets",
        "version": "1.0",
        "plan": {"actions": [/* PlanAction[] */]},
        "apply": {
          "created": ["AGENTS.md"],
          "updated": [],
          "skipped": [".agents/skills/meminit-docops/SKILL.md"]
        },
        "verify": {"outcome": "ok"}
      }
    ]
  }
}
```

### 10.2 `profiles list`

```json
{
  "data": {
    "profiles": [{"id": "standard", "version": "1.0", "extends": "minimal"}],
    "add_ons":  [{"id": "security-first", "compatible_with": ["standard", "strict"]}],
    "projections": [{"id": "codex", "source_assets": ["meminit-docops-skill"]}]
  }
}
```

### 10.3 Error and warning codes

New codes registered in `error_codes.py`:

| Code | Severity | Meaning |
| --- | --- | --- |
| `MEMINIT-ERROR-UNKNOWN-PROFILE` | error | `--profile` id not in registry. |
| `MEMINIT-ERROR-UNKNOWN-ADDON` | error | `--add-on` id not compatible with selected profile. |
| `MEMINIT-ERROR-UNKNOWN-PROJECTION` | error | `--projection` id not registered. |
| `MEMINIT-VIOLATION-CONFIG-CONFLICT` | violation | `docops.config.yaml` has user-edited keys conflicting with the profile. |
| `MEMINIT-WARN-MANIFEST-FUTURE` | warning | On-disk manifest schema is newer than the running CLI. |
| `MEMINIT-WARN-PROJECTION-ORPHANED` | warning | Projection target exists on disk but is not enabled in the manifest. |
| `MEMINIT-WARN-PROFILE-MIGRATION` | warning | `upgrade-setup --profile` is changing the recorded profile id. |
