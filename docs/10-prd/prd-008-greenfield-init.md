---
document_id: MEMINIT-PRD-008
type: PRD
title: Greenfield Repository Bootstrap
status: Draft
version: "0.3"
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
  - bootstrap-plan
  - installer-contract
  - brownfield-reuse
related_ids:
  - MEMINIT-STRAT-001
  - MEMINIT-PRD-003
  - MEMINIT-PRD-004
  - MEMINIT-PRD-005
  - MEMINIT-PRD-007
  - MEMINIT-SPEC-005
  - MEMINIT-SPEC-006
  - MEMINIT-SPEC-007
  - MEMINIT-SPEC-008
  - MEMINIT-FDD-003
  - MEMINIT-FDD-006
  - MEMINIT-FDD-012
  - MEMINIT-GOV-001
  - MEMINIT-GOV-003
  - MEMINIT-ADR-012
  - MEMINIT-ADR-009
  - MEMINIT-ADR-013
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PRD-008
> **Owner:** Meminit maintainers
> **Status:** Draft
> **Version:** 0.3
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

Meminit's `meminit init` already creates a baseline DocOps tree, a `docops.config.yaml`, and a small set of governed protocol assets via `ProtocolAssetRegistry`. It is, however, an opinionated scaffolder rather than a production-grade setup product: it has no profile system, no persisted record of what was installed, no separation between vendor-neutral and tool-specific protocol surfaces, and no profile-aware installers for the quality gates (pre-commit bundles, CI, GitHub hygiene) that mature repositories rely on.

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
| Pre-commit installer | `meminit install-precommit` | `src/meminit/core/use_cases/install_precommit.py`; [MEMINIT-FDD-006](../50-fdd/fdd-006-precommit-installer.md) |
| Capabilities and explain surface | `meminit capabilities`, `meminit explain` | `src/meminit/core/use_cases/capabilities.py`; [MEMINIT-PRD-005](./prd-005-agent-interface-v2.md) |

The shipped `ProtocolAssetRegistry.default()` registers exactly three assets: `agents-md` (mixed), `meminit-docops-skill` (generated), and `meminit-brownfield-script` (generated, mode `0o755`). `AssetOwnership` currently has only two members: `GENERATED` and `MIXED`. There is **no** `PROJECTED` ownership class today; introducing it is part of the work this PRD authorises.

### 2.2 Gaps relative to a production-grade bootstrap

1. **No profile abstraction.** `init` accepts no `--profile` flag and has no concept of per-profile asset bundles.
2. **No persisted setup manifest.** Nothing on disk records which profile, projections, or installers were applied; upgrades have to rediscover state.
3. **Mixed canonical/projected paths.** `.codex/skills/meminit-docops` exists in the repo today as an ad-hoc tool-specific path separate from `.agents/skills/meminit-docops`. There is no governed projection model.
4. **Incomplete quality-gate installation.** `install-precommit` exists, but it is a standalone command with one hook bundle. There is no profile-aware installer contract, no CI workflow installer, and no holistic contract for the gate set installed by each profile.
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
5. **Dry-run by default for destructive operations.** Any command that mutates user-authored files (e.g., `upgrade-setup` touching `.pre-commit-config.yaml`) MUST be dry-run by default, consistent with [MEMINIT-ADR-006](../45-adr/adr-006-design-auto-fix-workflow-dry-run-by-default.md).
6. **Reuse, do not duplicate, the protocol asset machinery.** `ProtocolAssetRegistry`, marker grammar, and `classify_drift` are the single source of truth for protocol asset payloads. Greenfield installers are clients of this registry, not parallel implementations.
7. **Cross-platform parity.** Linux and Windows are first-class; macOS is supported. File modes are advisory on Windows but MUST not crash. No POSIX-only shell snippets in canonical assets.
8. **Existing command reuse.** New bootstrap installers MUST wrap or refactor existing use cases where they exist (`InitRepositoryUseCase`, `InstallPrecommitUseCase`, protocol check/sync) instead of duplicating behavior behind a second implementation.
9. **Pre-alpha compatibility posture.** Meminit is not yet v1.0. Existing documented CLI invocations SHOULD remain ergonomic, but architectural quality and deterministic contracts take priority over preserving undocumented internal shapes.

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
5. Re-implementing brownfield migration in this PRD; this PRD provides the substrate, brownfield hardening (MEMINIT-PRD-004) is a separate, sequenced workstream.
6. A plugin system for third-party installers in v1. The installer contract is internal-only until at least v2.

### 5.3 Success Metrics

| Metric | Target | Measurement |
| --- | --- | --- |
| **Time to first green** | < 60 s on Ubuntu CI | `meminit init --profile standard` to passing `meminit check && meminit doctor && meminit protocol check`. |
| **Idempotency** | 0 changes | `init` followed by a second `init` with identical inputs produces zero `created`/`updated` entries. |
| **Drift correctness** | 100 % | Fixture matrix of intentionally-corrupted assets (per drift outcome) is correctly classified by `protocol check` and remediated by `protocol sync` / `upgrade-setup`. |
| **Cross-platform parity** | green on Linux + Windows | Greenfield smoke job in CI passes on both. |
| **Manifest fidelity** | 100 % | For any sequence of `init` + `upgrade-setup`, `.meminit/setup.yaml` accurately describes the on-disk state (verified by contract tests). |
| **Brownfield reuse** | ≥ 80 % shared code | At MEMINIT-PRD-004 implementation time, brownfield installers reuse ≥ 80 % of the apply-path code by line count. |
| **Contract coverage** | 100 % | Each concrete installer has schema, unit, contract, and integration coverage for `plan`, `apply`, `verify`, dry-run, idempotency, and conflict paths. |
| **User-authored preservation** | 0 destructive rewrites | Existing user-authored files are preserved unless an explicit generated or projection marker permits replacement, or the user passes an apply/force flag documented by the relevant command. |

<!-- MEMINIT_SECTION: solution -->

## 6. Proposed Solution

### 6.1 Core Abstractions

The bootstrap is built from a small set of named abstractions. Each is independently testable and lives in a clear module.

| Abstraction | Module | Responsibility |
| --- | --- | --- |
| `BootstrapInstaller` (Protocol/ABC) | `core/services/bootstrap/installer.py` | Defines `id`, `plan()`, `apply()`, `verify()` for each concern. |
| `InstallerRegistry` | `core/services/bootstrap/installer_registry.py` | Maintains the catalog of available installers and enforces dependency topological sorting. (Extensibility) |
| `BootstrapPlan` | `core/services/bootstrap/plan.py` | Deterministic, serialisable list of `PlanAction` items per installer. |
| `PlanAction` | `core/services/bootstrap/actions.py` | Versioned action model for create/update/merge/chmod/delete-warning operations; the only object `apply()` may execute. |
| `SafeFileWriter` | `core/services/bootstrap/writer.py` | Centralises `ensure_safe_write_path`, atomic LF writes, file-mode handling, marker preservation, and diff generation. |
| `Profile` | `core/services/bootstrap/profile.py` | Declarative bundle: which installers to run, their parameters, and which add-ons to layer on top. |
| `ProfileRegistry` | `core/services/bootstrap/profile_registry.py` | Resolves profile names to `Profile` instances; layered (built-in → org overlay → repo overlay). |
| `ProjectionAdapter` | `core/services/bootstrap/projections.py` | Defines how a canonical asset is reflected into a tool-specific path. Introduces the `PROJECTED` ownership class. |
| `SetupManifest` | `core/services/bootstrap/manifest.py` | Read/write of `.meminit/setup.yaml`. Single source of truth for "what is configured here". |
| `BootstrapOrchestrator` | `core/use_cases/bootstrap_repository.py` | Orchestrates installer ordering, dry-run, JSON envelope assembly. |
| Bootstrap schemas | `src/meminit/core/assets/bootstrap/*.schema.json` mirrored to `docs/20-specs/` | Machine-readable contracts for manifest, profile, plan, action, and command payloads. |

### 6.2 Installer Contract

Installers operate within a `BootstrapContext`, which isolates the environment and ensures compartmentalisation.

```python
@dataclass(frozen=True)
class BootstrapContext:
    root: Path                       # repository root (absolute)
    manifest: SetupManifest          # the active setup manifest
    profile: Profile                 # fully resolved profile after overlays
    options: Mapping[str, Any]       # additional CLI/profile options
    writer: SafeFileWriter           # single write/diff boundary
```

Every installer implements:

```python
class BootstrapInstaller(Protocol):
    id: str                           # stable, kebab-case identifier
    version: str                      # semver of the installer's contract
    depends_on: tuple[str, ...]       # ids of installers that must run first

    def plan(self, ctx: BootstrapContext) -> BootstrapPlan:
        """
        Read-only inspection of the repository. Returns the actions needed to
        reach the desired state. Identical logic for greenfield and brownfield.
        """
        ...

    def apply(self, plan: BootstrapPlan, ctx: BootstrapContext, *, dry_run: bool) -> ApplyReport: ...
    def verify(self, ctx: BootstrapContext) -> VerifyReport: ...
```

- `plan()` is **read-only**. It inspects the repo and returns the actions needed to reach the desired state. This is the brownfield primitive: MEMINIT-PRD-004's `meminit scan` will produce equivalent plans for existing repos.
- `apply()` is **idempotent** and executes only typed `PlanAction` instances through `SafeFileWriter`. If the desired state already holds, it returns an empty `ApplyReport` and does not touch disk.
- `verify()` is **side-effect-free**. It re-derives whether the installer's contract holds; it is the engine for `meminit doctor` and the post-apply assertion in CI.

Installer ids in v1: `docops-tree`, `docops-config`, `governance-templates`, `protocol-assets`, `projections`, `editorconfig`, `gitignore`, `pre-commit`, `ci-github`, `github-meta`, `manifest`. Each lives in its own submodule under `src/meminit/core/services/bootstrap/installers/`.

`BootstrapPlan` MUST be deterministic and schema-valid. A plan contains:

- `plan_schema_version`
- `profile` and resolved add-ons
- sorted `installers[]`
- sorted `actions[]` with `id`, `installer_id`, `action_type`, `target_path`, `ownership`, `current_hash`, `desired_hash`, `requires_confirmation`, and `reason`
- `warnings[]`, `violations[]`, and `advice[]` in the same issue shape as SPEC-008 envelopes

Allowed v1 action types are `create_file`, `create_directory`, `update_generated_file`, `merge_managed_region`, `merge_yaml_mapping`, `set_file_mode`, `record_manifest`, `warn_orphan`, and `delete_orphan`. `delete_orphan` MUST be emitted only when the user explicitly requests orphan removal.

### 6.3 Architectural Principles

The bootstrap architecture is built to demonstration-class excellence, ensuring long-term maintainability and readiness for brownfield adoption.

- **Modularisation & Compartmentalisation:** Each concern is isolated in a standalone `BootstrapInstaller`. Installers communicate only via the orchestrator and are passed a `BootstrapContext` that limits their scope. They cannot access global state or each other's internal data.
- **Reusability (The Brownfield Bridge):** The `plan()` phase is the core of our reusability strategy. It generates a deterministic `BootstrapPlan` that is identical in format whether derived from a clean directory (greenfield) or an existing repository (brownfield/upgrade). MEMINIT-PRD-004's "scan" logic will reuse these same installer plans.
- **Maintainability & Extensibility:** New installers and profiles can be added to their respective registries (`InstallerRegistry`, `ProfileRegistry`) without modifying the core `BootstrapOrchestrator`. This pluggable architecture allows Meminit to grow with new tool projections and governance rules.
- **Robustness through Schema Validation:** All critical artifacts (`SetupManifest`, `BootstrapPlan`, CLI Envelopes) are governed by strict versioned schemas, ensuring robust data boundaries across different Meminit versions.
- **Single Write Boundary:** Installers do not call `Path.write_text`, `chmod`, or YAML dumpers directly. They emit actions, and `SafeFileWriter` performs guarded atomic writes, managed-region merges, mode updates, and dry-run diffs.
- **Explicit Ownership Boundaries:** `GENERATED` files can be replaced when their hash differs; `MIXED` files can update only managed regions or structurally safe YAML mappings; `PROJECTED` files can be regenerated from canonical source but are never treated as canonical input.
- **Dependency Inversion:** The CLI layer depends on use cases, use cases depend on installer interfaces, and installers depend on small services (`repo_config`, `protocol_assets`, `safe_fs`, `output_formatter`). No installer imports Click, Rich, or process-global CLI state.

### 6.4 Profile Model

Profiles are declarative YAML bundles, packaged with Meminit (under `meminit.core.assets.bootstrap_profiles`), and overridable by org or repo policy. Profile overlays are data only; they MUST NOT execute code.

```yaml
# packaged: meminit/core/assets/bootstrap_profiles/standard.yaml
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

Resolution precedence (highest wins): explicit CLI flags → repo overlay (`docops.config.yaml: bootstrap.profile_overlay`) → vendored org profile (MEMINIT-ADR-012 local profile source) → packaged built-in. Resolution and merge rules live in `ProfileRegistry.resolve()` and MUST be deterministic and pure. Runtime network fetches are forbidden.


### 6.5 Setup Manifest

`.meminit/setup.yaml` is the persisted record of the bootstrap. It is validated by Meminit (`meminit doctor` and `upgrade-setup`) but is **not** a governed documentation artifact under `docs/`; it carries operational state, not narrative. It MUST be safe to commit: no secrets, no local absolute paths, no usernames, and no machine-specific temp paths.

```yaml
# .meminit/setup.yaml
manifest_schema_version: "1.0"
created_at: "2026-04-25T10:00:00Z"
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

The manifest is updated only after successful apply and verify. Re-running `init` with no material changes MUST NOT rewrite it merely to refresh timestamps. Future telemetry-like fields (for example `last_checked_at`) are out of scope because they would break idempotency.

### 6.6 Projection Model

Projections are how a single canonical asset reaches multiple tool-specific paths without duplication. Each `ProjectionAdapter` declares:

- `source_asset_id`: an id known to `ProtocolAssetRegistry`.
- `target_path_template`: a parameterised path (e.g., `.codex/skills/{asset_id}/SKILL.md`).
- `transform`: an optional pure function from canonical payload to projected payload (default: identity).

A new `AssetOwnership.PROJECTED` value is introduced in `protocol_assets.py`. Today, `GENERATED` assets are whole-file hash compared and `MIXED` assets use `MEMINIT_PROTOCOL` managed-region markers. Projected assets MUST have their own parseable protocol metadata so `classify_drift` can distinguish a stale projection from a tampered or orphaned copy. The v1 marker shape is:

```markdown
<!-- MEMINIT_PROTOCOL: begin id=<projection-id> source=<source-asset-id> version=<version> sha256=<sha> -->
...
<!-- MEMINIT_PROTOCOL: end id=<projection-id> -->
```

`protocol check` and `protocol sync` extend their reporting to include projection-specific outcomes (`projection_aligned`, `projection_stale`, `projection_orphaned`, `projection_tampered`, `projection_unparseable`). A projected file is always derived output; the canonical payload remains the source `ProtocolAsset`.

Built-in adapters in v1: `codex`, `claude`. Each is a small, declarative dataclass; adding a new adapter is a single-file change with paired tests.


<!-- MEMINIT_SECTION: requirements -->

## 7. Functional Requirements

Each requirement is normative and is the unit of acceptance for engineering. Each maps to one installer or to the orchestrator. `MUST`, `SHOULD`, `MAY` are used per RFC 2119.

### FR-1 Profile-driven entrypoint

`meminit init` MUST accept `--profile <id>` (default: `standard`), `--add-on <id>` (repeatable), `--projection <id>` (repeatable), `--dry-run`, and the standard agent flags (`--root`, `--format`, `--output`, `--include-timestamp`, `--correlation-id`). It MUST reject unknown ids with `MEMINIT-ERROR-UNKNOWN-PROFILE` / `…-UNKNOWN-ADDON` / `…-UNKNOWN-PROJECTION` and a structured `advice` entry listing valid ids.

### FR-2 Installer contract

A `BootstrapInstaller` Protocol MUST be defined in `core/services/bootstrap/installer.py` with the methods specified in §6.2. Every installer MUST be unit-testable in isolation against a `tmp_path` fixture, with no I/O outside the supplied `BootstrapContext.root`. Concrete installers MUST NOT import the CLI package.

### FR-3 Plan/apply/verify symmetry

For every installer: running `apply()` after `plan()` returned an empty action list MUST be a no-op (zero filesystem writes). `verify()` on a freshly applied installer MUST return `outcome=ok`. These two invariants MUST be exercised by contract tests for every concrete installer.

### FR-4 DocOps tree installer

`docops-tree` MUST create the directory layout declared by [MEMINIT-FDD-003](../50-fdd/fdd-003-repository-scaffolding-meminit-init.md), respecting `docs_root` from `docops.config.yaml` or the resolved profile default when no config exists. It MUST NOT overwrite existing directories and MUST fail if a required directory path is occupied by a non-directory.

### FR-5 DocOps config installer

`docops-config` MUST create or update `docops.config.yaml` to a profile-defined shape. On an existing file, it MUST diff structurally and MUST NOT reorder or strip user-added keys; conflicting keys produce a `MEMINIT-VIOLATION-CONFIG-CONFLICT` violation that the user resolves. YAML output MUST be stable (`sort_keys=False`, LF line endings) and schema-valid.

### FR-6 Governance templates installer

`governance-templates` MUST install the Templates v2 set (PRD, ADR, FDD, SPEC, RUNBOOK) to `<docs_root>/00-governance/templates/` per [MEMINIT-SPEC-007](../20-specs/spec-007-templates-v2.md). Template files are `GENERATED` on first install unless they contain a managed region; existing local templates are treated as user-authored and produce a conflict unless the user explicitly opts into replacement.

### FR-7 Protocol assets installer

`protocol-assets` MUST install the canonical assets registered in `ProtocolAssetRegistry` for the selected bundle. It MUST reuse `ProtocolAsset.render()`, `normalize_protocol_payload()`, marker parsing, and drift classification; it MUST NOT introduce a parallel asset writer.

### FR-8 Projections installer

`projections` MUST install the projection targets declared by the selected adapters and record them in the manifest. Disabling a previously-enabled projection in `upgrade-setup` MUST emit a `projection_orphaned` warning and, only when `--remove-orphans` is set, delete the projected file.

### FR-9 Pre-commit installer

`pre-commit` MUST install or update `.pre-commit-config.yaml` per the selected bundle (`minimal`, `standard`, `strict`). It MUST reuse `InstallPrecommitUseCase` (or a refactored equivalent service) to avoid duplicating hook logic. Existing user hooks MUST be preserved; invalid YAML or incompatible hook structure is a violation, not a best-effort overwrite.

### FR-10 CI installer

`ci-github` MUST install GitHub Actions workflows per the selected list. The `greenfield-smoke` workflow MUST run `meminit init` in a clean directory on Ubuntu and Windows runners and assert green `check`, `doctor`, and `protocol check`. Workflows are `GENERATED` ownership, pin action versions to stable major versions or SHAs, request least-privilege permissions, and must not require network access beyond package/tool installation already required by the project.

### FR-11 GitHub meta installer

`github-meta` MUST install requested assets (`pr-template`, `issue-templates`, `CODEOWNERS`) under `.github/`. `CODEOWNERS` is `MIXED`; templates are `GENERATED`. Generated templates MUST contain no organisation-private defaults.

### FR-12 Editor and ignore installers

`editorconfig` MUST install `.editorconfig` (`GENERATED`). `gitignore` MUST install or extend `.gitignore` (`MIXED`, with a managed Meminit region for transient artifacts such as `.venv/`, `.pytest_cache/`, and local WIP docs). `.meminit/setup.yaml` MUST NOT be ignored by default.

### FR-13 Manifest installer

`manifest` MUST be the last installer in every plan. It writes `.meminit/setup.yaml` reflecting the actual outcome (post-apply hashes, not pre-apply intent). On `--dry-run`, it writes nothing and reports the manifest it *would* have written.

### FR-14 Idempotent re-run

`meminit init --profile <same>` MUST be idempotent: a second run on an unchanged repo yields a SPEC-008 envelope where `data.installers[*].apply.created == [] && updated == []`, and exits 0.

### FR-15 Upgrade entrypoint

`meminit upgrade-setup` MUST read `.meminit/setup.yaml`, re-run `plan()` for every recorded installer, and report drift per installer. By default it is dry-run; `--no-dry-run` applies. `--profile <new>` performs a profile migration and MUST emit a `profile_migration` warning per installer affected.

### FR-16 JSON envelope conformance

Every command introduced or modified by this PRD MUST emit SPEC-008 envelopes with the command-specific `data` payload defined in §10. Repo-aware commands MUST set `root`. STDOUT MUST contain exactly one JSON object when `--format json` is used; all human logs go to STDERR.

### FR-17 Capability advertisement

`meminit capabilities` MUST advertise the new commands (`init`, `upgrade-setup`, `profiles list`) and their option matrices, per [MEMINIT-PRD-005](./prd-005-agent-interface-v2.md). It MUST remain repo-agnostic and fast.

### FR-18 Brownfield-compatible plan format

`BootstrapPlan` JSON serialisation MUST be a superset of the migration-plan format defined in [MEMINIT-PRD-004 §FR-2](./prd-004-brownfield-adoption-hardening.md#fr-2-migration-plan-artifact), so that `meminit fix --plan` can consume installer plans unchanged. Conformance MUST be enforced by a shared schema test.

### FR-19 Manifest and profile schemas

The manifest, profile, profile overlay, bootstrap plan, plan action, and command `data` payloads MUST have JSON Schemas stored as packaged assets and mirrored in `docs/20-specs/`. Tests MUST validate every emitted fixture against these schemas.

### FR-20 Conflict taxonomy

Every installer MUST map conflicts into one of: `safe_create`, `safe_update_generated`, `safe_merge_managed_region`, `manual_conflict`, `unsafe_path`, `invalid_existing_file`, or `orphaned_projection`. The taxonomy MUST be present in both `BootstrapPlan` actions and SPEC-008 warnings/violations so agents can route remediation deterministically.


<!-- MEMINIT_SECTION: non_functional_requirements -->
## 8. Non-Functional Requirements

### NFR-1 Determinism

For identical inputs (profile, add-ons, projections, repo state, Meminit version) the bootstrap MUST produce byte-identical outputs across runs and platforms, except where the file payload itself encodes platform-relative data (e.g., line endings normalised to LF on write).

### NFR-2 Safety

All filesystem writes MUST go through `ensure_safe_write_path`. Symlink-escape and absolute-path-escape attempts MUST raise `MeminitError` with a stable error code and exit non-zero. No installer may shell out for file mutation; all writes are in-process.

### NFR-3 Performance

`meminit init --profile standard` on an empty directory MUST complete in under 10 seconds wall-clock on a baseline GitHub-hosted Ubuntu runner. `meminit doctor` after `init` MUST complete in under 5 seconds. Profile resolution MUST be O(profiles + add-ons) and free of network I/O.

### NFR-4 Observability

Every command emits a SPEC-008 envelope with `run_id` (UUIDv4). Per-installer outcomes MUST appear as structured `data.installers[]` entries; warnings, violations, and advice use the envelope-level arrays. Stable error codes MUST be registered in `error_codes.py` and surfaced via `meminit explain`.

### NFR-5 Maintainability

Each installer module SHOULD stay under 300 source lines; if exceeded, split services before merging. The orchestrator SHOULD stay under 200 lines and MUST contain no installer-specific branching beyond registry resolution. Cyclomatic complexity per public function MUST stay ≤ 10 and be enforced by the active lint stack (`flake8`/mccabe today, or an explicitly adopted successor). Public APIs MUST have docstrings; modules MUST have module docstrings.

### NFR-6 Test pyramid

Per installer: (a) ≥ 1 contract test (idempotency + verify), (b) ≥ 3 unit tests (happy path, dry-run, conflict), (c) integration coverage in the orchestrator suite. Greenfield smoke runs on Linux and Windows in CI on every PR.

### NFR-7 Documentation parity

For every new module under `core/services/bootstrap/`, an FDD entry under `docs/50-fdd/` MUST exist or be created in the same PR (atomic Code + Docs + Tests, per `AGENTS.md`). The Setup Manifest schema MUST be specified in a SPEC document.

### NFR-8 Backwards compatibility

Existing `meminit init` invocations without `--profile` MUST continue to work and MUST default to the `standard` profile. The current shipped `ProtocolAssetRegistry.default()` asset set MUST remain functional unchanged. The `output_schema_version` for `init` MUST stay at `"3.0"`; only `data` is extended additively unless a pre-v1 breaking change is explicitly documented.

### NFR-9 Security and supply chain

Generated workflows and hook configs MUST pin external actions/tools, request least privilege, and avoid embedding repo-specific secrets. Generated files MUST be safe for a public repository under [MEMINIT-GOV-003](../00-governance/gov-003-security-practices.md). Profile overlays MUST be local data files; they MUST NOT run arbitrary code.

### NFR-10 Extensibility boundary

Adding a new built-in installer or projection MUST require registering one new module and one test fixture, not editing the orchestrator. Third-party plugin loading is explicitly out of scope for v1, but the internal boundaries must not block a future plugin registry.

<!-- MEMINIT_SECTION: cli_surface -->
## 9. CLI Surface

| Command | Purpose | Mutates? |
| --- | --- | --- |
| `meminit init [--root PATH] [--profile ID] [--add-on ID]… [--projection ID]… [--dry-run] [--format json]` | Greenfield bootstrap; idempotent | yes (unless `--dry-run`) |
| `meminit upgrade-setup [--root PATH] [--no-dry-run] [--profile ID] [--remove-orphans] [--force] [--format json]` | Re-run installers from manifest, optionally migrate profile | dry-run by default |
| `meminit doctor [--format json]` | Run all installer `verify()` plus existing checks | no |
| `meminit protocol check [--format json]` | Existing command, extended for projections | no |
| `meminit protocol sync [--no-dry-run] [--format json]` | Existing command, extended for projections | dry-run by default |
| `meminit profiles list [--format json]` | List available profiles, add-ons, projections | no |

`meminit profiles list` is a thin read-only command exposing `ProfileRegistry.list()`; agents use it to discover the option matrix without parsing CLI help.

`--force` is valid only for generated or projected assets with deterministic expected hashes. It MUST NOT overwrite unmarked user-authored files, invalid YAML, or mixed files outside managed regions.

<!-- MEMINIT_SECTION: json_envelope_profiles -->
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
        "plan": {
          "plan_schema_version": "1.0",
          "actions": [
            {
              "id": "protocol-assets:create:agents-md",
              "installer_id": "protocol-assets",
              "action_type": "create_file",
              "target_path": "AGENTS.md",
              "ownership": "mixed",
              "requires_confirmation": false,
              "reason": "required_by_profile"
            }
          ]
        },
        "apply": {
          "created": ["AGENTS.md"],
          "updated": [],
          "skipped": [".agents/skills/meminit-docops/SKILL.md"],
          "conflicts": []
        },
        "verify": {"outcome": "ok", "checked_paths": ["AGENTS.md"]}
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
| `MEMINIT-VIOLATION-MANIFEST-INVALID` | violation | `.meminit/setup.yaml` is missing, malformed, or schema-invalid for a command that requires it. |
| `MEMINIT-WARN-PROJECTION-ORPHANED` | warning | Projection target exists on disk but is not enabled in the manifest. |
| `MEMINIT-WARN-PROFILE-MIGRATION` | warning | `upgrade-setup --profile` is changing the recorded profile id. |
| `MEMINIT-VIOLATION-BOOTSTRAP-CONFLICT` | violation | An installer found an existing user-authored file or config structure it cannot safely merge. |
| `MEMINIT-ERROR-BOOTSTRAP-UNSAFE-PATH` | error | A plan action targets a path outside the repo root or escapes through a symlink. |

<!-- MEMINIT_SECTION: profiles_catalog -->
## 11. Profiles Catalog

Built-in profiles in v1. Each is a packaged YAML asset; the table below is the normative summary.

| Profile | Extends | Installers enabled | Default projections | Intended audience |
| --- | --- | --- | --- | --- |
| `minimal` | — | `docops-tree`, `docops-config`, `governance-templates`, `protocol-assets`, `manifest` | none | Library authors wanting DocOps only, no CI. |
| `standard` | `minimal` | + `projections`, `editorconfig`, `gitignore`, `pre-commit`, `ci-github` (docops + protocol-check + greenfield-smoke), `github-meta` (pr-template, issue-templates) | `codex` | Default for new repos. |
| `strict` | `standard` | + stricter pre-commit bundle, CI `meminit doctor --strict`, `github-meta` (+ CODEOWNERS) | `codex`, `claude` | Regulated / multi-contributor repos. |

Add-ons in v1: `security-first` (injects the `MEMINIT_AGENT_SECURITY` section into `AGENTS.md`), `testing-first` (adds a testing section and enables a `meminit test-smoke` CI job), `monorepo` (adjusts `docops.config.yaml` `namespaces` defaults).

Projections in v1: `codex` (projects `meminit-docops` skill into `.codex/skills/`), `claude` (projects the same skill into `.claude/skills/`).

<!-- MEMINIT_SECTION: phased_implementation_plan -->
## 12. Phased Implementation Plan

Each phase is an independently mergeable increment. Every phase MUST ship with updated FDDs and tests (atomic unit of work per `AGENTS.md`).

### Phase 1 — Installer substrate (no user-visible surface change)

- Introduce `core/services/bootstrap/` package with `installer.py`, `installer_registry.py`, `actions.py`, `plan.py`, `writer.py`, `manifest.py`, `profile.py`, `profile_registry.py`.
- Refactor `InitRepositoryUseCase` to delegate to `docops-tree`, `docops-config`, `governance-templates`, `protocol-assets`, `manifest` installers behind a feature flag (`MEMINIT_BOOTSTRAP_V2=1`).
- Ship contract tests for the installer Protocol and for every migrated installer.
- Create draft FDD(s) for the bootstrap engine and setup manifest schema SPEC.
- Deliverable: existing `meminit init` behaviour is byte-identical for default invocation, but implemented through the new engine.

### Phase 2 — Profiles and manifest

- Enable profile selection (`--profile`) and persist `.meminit/setup.yaml`.
- Add `meminit profiles list` and wire capabilities.
- Add packaged profile schemas and fixture validation.
- Deliverable: `meminit init --profile minimal|standard` works; manifest is written; idempotency test added.

### Phase 3 — Projections

- Introduce `AssetOwnership.PROJECTED`, extend marker grammar with `source=<id>`, extend `classify_drift`.
- Implement `codex` and `claude` adapters.
- Replace any existing ad-hoc `.codex/skills/meminit-docops` symlink/copy in this repo with a governed projection via an explicit migration runbook under `docs/60-runbooks/`.
- Deliverable: `--projection codex --projection claude` works; `protocol check` reports projection drift.

### Phase 4 — Quality gate installers

- Implement `pre-commit`, `ci-github`, `github-meta`, `editorconfig`, `gitignore` installers.
- Refactor `InstallPrecommitUseCase` into a shared service if needed so the standalone command and profile installer share hook-generation logic.
- Add `greenfield-smoke` workflow (Linux + Windows).
- Deliverable: `meminit init --profile standard` produces a repository that passes all its own gates on first attempt in CI.

### Phase 5 — Upgrade and orphan handling

- Implement `meminit upgrade-setup` (dry-run by default, `--no-dry-run`, `--profile`, `--remove-orphans`).
- Add profile-migration warnings and manifest-future warnings.
- Add invalid/corrupt manifest tests and `meminit explain` entries for new error codes.
- Deliverable: end-to-end upgrade path across profile versions with contract tests.

### Phase 6 — Brownfield hand-off preparation

- Freeze the `BootstrapPlan` JSON schema under `tests/contracts/bootstrap/plan.schema.json`.
- Confirm `meminit fix --plan` accepts installer plans (schema test).
- Update MEMINIT-PRD-004/MEMINIT-FDD-005 references only if their plan schema requires additive alignment.
- Deliverable: MEMINIT-PRD-004 work can begin against a stable installer contract.

<!-- MEMINIT_SECTION: acceptance_criteria -->
## 13. Acceptance Criteria

A phase is complete only when all criteria applicable to that phase hold:

1. All FRs assigned to the phase are implemented and covered by tests.
2. `meminit check`, `meminit doctor`, `meminit protocol check` all pass on the repo.
3. `meminit init` round-trips idempotently on a fresh `tmp_path`; once Phase 5 ships, `meminit upgrade-setup` also round-trips idempotently on a fresh `tmp_path` and on this repo.
4. The JSON envelope for every new/modified command validates against the `tests/contracts/bootstrap/` schemas.
5. Once Phase 4 ships, Linux and Windows CI are green for the greenfield smoke job.
6. Corresponding FDD(s) under `docs/50-fdd/` exist, status at least `Draft`, and are cross-referenced from this PRD's `related_ids`.
7. No existing test is deleted or skipped to achieve green; any behavioural change is reflected in an explicit test update.
8. New error/warning/violation codes are registered, covered by `meminit explain`, and represented in SPEC-008-compatible envelopes.
9. Every file write introduced by the phase is covered by an unsafe-path or symlink-escape regression test.
10. The brownfield reuse seam remains intact: installer `plan()` stays read-only, action schemas stay shared, and no greenfield-only shortcut bypasses `PlanAction`.

### 13.1 Engineering Handoff Checklist

Before implementation starts, engineering should create or update:

- `docs/20-specs/spec-011-bootstrap-setup-manifest.md` for manifest/profile/plan schemas.
- `docs/50-fdd/fdd-014-bootstrap-engine.md` for the orchestrator, installer registry, writer, and phased installer rollout.
- `docs/50-fdd/fdd-015-greenfield-profile-installers.md` for profile, projection, CI, GitHub metadata, editor, and ignore installers.
- Contract fixtures under `tests/contracts/bootstrap/` for profile resolution, setup manifest, plan actions, and SPEC-008 command payloads.
- Integration tests under `tests/integration/` that initialize a fresh repo, re-run idempotently, and verify `check`/`doctor`/`protocol check`.

<!-- MEMINIT_SECTION: alternatives_considered -->
## 14. Alternatives Considered

- **Keep a single `InitRepositoryUseCase` and grow it.** Rejected: violates SRP, makes brownfield reuse impossible, and defeats the MEMINIT-PRD-004 plan-driven fix workflow.
- **Per-tool first-class entrypoints (`meminit init-codex`, `meminit init-claude`).** Rejected: combinatorial explosion, drift between surfaces, and no vendor-neutral story for `.agents/`.
- **Hard-coded profile constants in Python.** Rejected: not overridable per-org, and couples profile evolution to Meminit releases. YAML bundles let orgs vendor profiles (see `install_org_profile.py`).
- **Symlinks for projections.** Rejected: broken on Windows by default, invisible to `protocol check`, and hostile to agents that read files without following links.
- **Store manifest in `docops.config.yaml`.** Rejected: `docops.config.yaml` is a user-authored policy file; the manifest is operational state. Mixing them breaks round-trip ergonomics and violates the byte-invariance goal for user-authored files.

<!-- MEMINIT_SECTION: risks_and_mitigations -->
## 15. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Profile/add-on combinatorial bugs | medium | medium | Contract tests across a matrix of `{profile} × {add_on}` combinations; `ProfileRegistry.resolve()` is pure and deterministically tested. |
| Projection adapters diverge from canonical asset | medium | high | Projected files must carry `source=<id>` in their marker; `protocol check` fails if projection hash does not match rendered source. |
| `upgrade-setup` silently breaks user-edited files | low | high | Dry-run by default, per-installer conflict reporting, structural diffs, and explicit `--force` gates. |
| Windows path/line-ending regressions | medium | medium | Windows job in greenfield smoke; all writes use `newline="\n"` with explicit LF mode. |
| Brownfield plan format drift | medium | high | Shared JSON schema under `tests/contracts/bootstrap/plan.schema.json` imported by both init and fix tests (FR-18). |
| Manifest corruption (user edit) | low | medium | `SetupManifest.load()` validates against schema and emits `MEMINIT-VIOLATION-MANIFEST-INVALID` rather than crashing; users repair by re-running `init`/`upgrade-setup` after moving the invalid manifest aside. |

<!-- MEMINIT_SECTION: resolved_decisions_and_open_questions -->
## 16. Resolved Decisions and Open Questions

### Resolved

- **Canonical root.** `.agents/` is the vendor-neutral canonical root; `.codex/` and `.claude/` are projections.
- **Default profile.** `standard`.
- **Manifest location.** `.meminit/setup.yaml` (operational state, not governed documentation).
- **Ownership taxonomy.** `GENERATED`, `MIXED`, `PROJECTED`. Extending `AssetOwnership` is in scope for this PRD.
- **Greenfield smoke cadence.** The Linux and Windows greenfield smoke job runs on every PR once Phase 4 ships; cost is controlled by keeping the job focused.
- **Projection scope.** v1 ships `codex` and `claude` adapters for the `meminit-docops` skill and designs `ProjectionAdapter` generically enough to support future canonical skill bundles.
- **Manifest sensitivity.** `.meminit/setup.yaml` is not sensitive by default and must be safe to commit; if future fields become sensitive, those fields require a new SPEC/ADR before shipping.

### Open

1. Should profile YAML support a machine-readable deprecation field so `upgrade-setup` can migrate users off retired profiles automatically?
2. Should profile overlays be allowed from both vendored org profiles and repo config in v1, or should repo overlays wait until brownfield hardening?

<!-- MEMINIT_SECTION: related_documents -->
## 17. Related Documents

- [MEMINIT-STRAT-001 — Project Meminit Vision](../02-strategy/strat-001-project-meminit-vision.md)
- [MEMINIT-PRD-003 — Agent Interface v1](./prd-003-agent-interface-v1.md)
- [MEMINIT-PRD-004 — Brownfield Adoption Hardening](./prd-004-brownfield-adoption-hardening.md)
- [MEMINIT-PRD-005 — Agent Interface v2](./prd-005-agent-interface-v2.md)
- [MEMINIT-PRD-006 — Document Templates](./prd-006-document-templates.md)
- [MEMINIT-PRD-007 — Project State Dashboard](./prd-007-project-state-dashboard.md)
- [MEMINIT-SPEC-005 — Scan Plan Format](../20-specs/spec-005-scan-plan-format.md)
- [MEMINIT-SPEC-006 — Error Code Enum](../20-specs/spec-006-errorcode-enum.md)
- [MEMINIT-SPEC-007 — Templates v2](../20-specs/spec-007-templates-v2.md)
- [MEMINIT-SPEC-008 — Agent Output Contract v2](../20-specs/spec-008-agent-output-contract-v2.md)
- [MEMINIT-FDD-003 — Repository Scaffolding (`meminit init`)](../50-fdd/fdd-003-repository-scaffolding-meminit-init.md)
- [MEMINIT-FDD-006 — Pre-commit Installer](../50-fdd/fdd-006-precommit-installer.md)
- [MEMINIT-FDD-012 — Protocol Asset Governance](../50-fdd/fdd-012-protocol-asset-governance.md)
- [MEMINIT-GOV-001 — Document Standards](../00-governance/gov-001-document-standards.md)
- [MEMINIT-GOV-003 — Security Practices](../00-governance/gov-003-security-practices.md)
- [MEMINIT-MEMINIT-ADR-012 — XDG Org Profiles and Vendoring](../45-adr/adr-012-use-xdg-org-profiles-and-vendoring.md)
- [MEMINIT-ADR-009 — Minimal Repo Configuration for Brownfield Adoption](../45-adr/adr-009-add-minimal-repo-configuration-for-brownfield-adoption.md)
- [MEMINIT-ADR-013 — Plan-driven Brownfield Adoption](../45-adr/adr-013-plan-driven-brownfield-adoption.md)

<!-- MEMINIT_SECTION: version_history -->

## 18. Version History

| Version | Date       | Author              | Changes                                                                                                                                               |
| ------- | ---------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0.1     | 2026-04-25 | Meminit maintainers | Initial draft (reformatted from earlier scaffolding notes).                                                                                          |
| 0.2     | 2026-04-25 | Meminit maintainers | Hardened to demonstration-class PRD: grounded in current code (`ProtocolAssetRegistry`, `AssetOwnership`), introduced modular installer contract, profile registry, setup manifest, projection model, phased plan, risks, and brownfield-ready plan schema. |
| 0.3     | 2026-04-25 | Codex              | Corrected current-state drift (`install-precommit`, capabilities, `explain`), tightened schema/action/write-boundary contracts, clarified projection markers, strengthened security and CI requirements, and added engineering handoff criteria for brownfield reuse. |
