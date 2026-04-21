---
document_id: MEMINIT-PLAN-012
type: PLAN
title: Phase 3 Detailed Implementation Plan
status: Draft
version: '0.5'
last_updated: '2026-04-19'
owner: GitCmurf
docops_version: '2.0'
area: AGENT
description: Detailed implementation plan for MEMINIT-PLAN-008 Phase 3 protocol governance
  work.
keywords:
- phase-3
- planning
- protocol
- governance
related_ids:
- MEMINIT-PLAN-008
- MEMINIT-PLAN-003
- MEMINIT-PRD-005
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PLAN-012
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.5
> **Last Updated:** 2026-04-19
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Detailed implementation plan for MEMINIT-PLAN-008 Phase 3 protocol governance work.

# PLAN: Phase 3 Detailed Implementation Plan

## Context

MEMINIT-PLAN-008 defines Phase 3 as the point where repo-local protocol files
such as `AGENTS.md` and the bundled skill assets stop being one-time scaffolds
and become governable clients of the Meminit contract.

This phase depends on Phase 1 because protocol governance without a
self-describing runtime contract would only codify drift. The goal is not to
turn protocol files into rigid generated artifacts with no room for local
judgment. The goal is to make supported sections verifiable and synchronizable.

Phase 1 status:

- Phase 1 (Agent Contract Core) is complete for the purposes of this phase.
- `meminit capabilities`, `meminit context`, and `meminit explain` are the
  runtime contract reference surfaces that Phase 3 must align protocol assets
  against.

Contract-reference note:

- MEMINIT-PLAN-008 requires bundled protocol assets to point to the runtime
  contract where possible rather than duplicating static command inventories.
- Phase 3 should therefore prefer durable references to `meminit capabilities`,
  `meminit context`, and `meminit explain` over prose that can only stay
  correct through manual editing.

Definition:

- The runtime contract is the behavior exposed by the installed Meminit CLI,
  specifically the commands, capabilities metadata, and error-code semantics
  discoverable via `meminit capabilities`, `meminit context`, and
  `meminit explain`.
- Protocol assets are the repo-local files such as `AGENTS.md` and bundled
  skill manifests that should align with that runtime contract.

Adoption note:

- The external usage footprint is still limited to one explicit testbed.
- That means this phase can choose a clean generated-versus-user-managed model
  without supporting many legacy protocol variants.

Backward-compatibility posture:

- For the duration of the pre-alpha vNext programme, backward compatibility on
  protocol assets is relaxed. This phase is free to introduce new region
  markers, version stamps, and asset-level metadata that older `meminit init`
  outputs will not contain.
- Brownfield repos are adopted via an additive sync path rather than a strict
  equality check. The check command must distinguish "missing stamp / legacy
  format" from "tampered generated region" so that legacy adopters see
  actionable upgrade guidance instead of hostile drift reports.

Determinism requirement:

- All drift diagnostics and sync diffs must be deterministic across machines:
  sorted asset lists, stable diff hunks, normalized line endings, and no
  timestamps in hashed payloads. Determinism is what lets agents reason about
  repeated invocations and close repair loops automatically.

## 1. Purpose

Define the detailed implementation steps for Phase 3 of MEMINIT-PLAN-008 so
that Meminit can detect and remediate drift in agent-facing protocol files.

## 2. Scope

In scope:

- a governable model for `AGENTS.md` and bundled protocol assets
- drift detection and reporting
- a safe sync path with preview-first behavior
- test coverage for generated and user-managed regions
- CI and operator guidance for ongoing enforcement

Out of scope:

- broad semantic rewriting of user-authored guidance
- work-queue state expansion
- streaming and scale work
- semantic search
- non-repo protocol targets outside the explicitly supported asset set

These non-goals are explicitly outside the Phase 3 boundary and remain covered
by existing Meminit paths (`init`, org-profile flows, or later programme
phases).

### 2.1 Engineering Constraints

The implementation must follow the current Meminit codebase conventions rather
than inventing a parallel pattern:

- keep the shared v3 agent envelope stable and place protocol-specific payloads
  under `data` unless a shared-envelope change is truly required
- reuse `agent_output_options`, `agent_repo_options`, `command_output_handler`,
  `ErrorCode`, and the capabilities registry rather than introducing
  command-local contract logic
- load bundled assets via package resources, not repo-relative paths, so
  installed distributions behave the same as editable checkouts
- validate every write target with `ensure_safe_write_path` and use an atomic
  temp-file-then-replace write path for mutations
- keep parsing simple: a dedicated lightweight protocol-marker parser is
  preferred over forcing protocol semantics through the template section parser
  if that would increase complexity

Security:

- All protocol asset writes must validate that the target remains within the
  repository root.
- Mixed-ownership sync must never rewrite content outside the generated region
  markers.

### 2.2 Governed Document Outputs

Phase 3 implementation is not done when the code lands. The following governed
document updates are required for closeout, consistent with MEMINIT-PLAN-008
Section 7:

| Action | Type | Document | Required update |
| ------ | ---- | -------- | --------------- |
| Update | PRD | `MEMINIT-PRD-005` | Add `protocol check` / `protocol sync`, runtime-contract references, and supported protocol surface scope |
| Update | SPEC | `MEMINIT-SPEC-006` | Register the `PROTOCOL_*` error codes and normative explain semantics |
| New | FDD | Protocol Surface Governance | Define the asset registry, ownership model, marker grammar, check/sync logic, and JSON payload shapes |
| New or Update | RUNBOOK | Agent Integration and Upgrade Workflow | Document brownfield adoption, CI usage, and operator recovery paths |
| Conditional update | PLAN | `MEMINIT-PLAN-003` | Only if Phase 3 sequencing or completion criteria move materially during delivery |

Every delivery slice in this phase must satisfy the repository's atomic-unit
rule: code, docs, and tests move together.

## 3. Work Breakdown

### 3.1 Workstream A: Protocol Asset Boundary Definition

Problem:

- The current repo has protocol assets, but there is no explicit contract for
  which parts are generated, which parts are user-managed, and how drift is
  recognized.

#### 3.1.1 Supported protocol asset inventory

The Phase 3 asset set is explicitly enumerated. Assets outside this table are
out of scope for drift detection and sync.

| Asset | Target path in repo | Package source | Ownership model |
| ----- | ------------------- | -------------- | --------------- |
| AGENTS.md (top-level protocol) | `AGENTS.md` | `src/meminit/core/assets/AGENTS.md` | Mixed (see §3.1.2) |
| meminit-docops skill manifest | `.agents/skills/meminit-docops/SKILL.md` | `src/meminit/core/assets/meminit-docops-skill.md` | Fully generated |
| brownfield helper script | `.agents/skills/meminit-docops/scripts/meminit_brownfield_plan.sh` | `src/meminit/core/assets/scripts/meminit_brownfield_plan.sh` | Fully generated |

Non-goals for this phase:

- `docops.config.yaml`, `metadata.schema.json`, and document templates are not
  treated as protocol assets here; they are governed by the existing init /
  org-profile paths.
- Agent-host symlinks such as `.codex/skills/` are considered installation
  conveniences. Detection and repair of symlinks is explicitly out of scope.

#### 3.1.2 Ownership model and region markers

Every supported asset must declare its ownership in one of three shapes:

1. Fully generated. The entire file is owned by Meminit. Drift is detected by
   comparing the normalized whole-file content against the canonical render.
   No embedded region markers are required. Applies to skill manifests and
   bundled scripts.
2. Mixed (generated region + user region). The file starts with a generated
   region delimited by markers and followed by a free-form user section.
   Applies to `AGENTS.md`.
3. Fully user-managed. Not used in this phase, but reserved so that future
   assets can opt out of drift detection without a schema change.

Region markers are only used for mixed-ownership Markdown assets:

```html
<!-- MEMINIT_PROTOCOL: begin id=<asset-id> version=<semver> sha256=<hex> -->
...generated content...
<!-- MEMINIT_PROTOCOL: end id=<asset-id> -->
```

Rules:

- `id` is an asset identifier drawn from the inventory table (`agents-md`,
  `meminit-docops-skill`, `meminit-brownfield-script`).
- `version` is the Meminit protocol-asset schema version, independent of the
  Meminit package version. It only bumps when the generated content contract
  changes in a way that invalidates prior drift diagnostics.
- `sha256` is computed over the normalized generated payload between the
  markers (LF line endings, single trailing newline). The hash is what makes
  drift detection deterministic regardless of editor behavior.
- Fully generated assets use registry-declared whole-file normalization plus a
  registry-declared target mode (for example executable shell scripts).
- Content outside the region in a mixed-ownership file is user-managed and
  must never be rewritten by sync. Content inside the region is fully owned by
  Meminit.

Cross-platform note:

- File-mode metadata applies to Unix-like systems. On Windows, the mode field
  is ignored, but sync must still produce byte-identical managed content.

#### 3.1.3 Implementation tasks

1. Add the asset inventory table above to a shared module
   (`core/services/protocol_assets.py`) so check, sync, and init all consume
   the same list.
2. Introduce a `ProtocolAsset` dataclass with `id`, `target_path`,
   `package_resource`, `ownership` (`"generated" | "mixed"`), declared file
   mode metadata, and a `render()` method that returns the canonical payload.
3. Extend the bundled `AGENTS.md` template to wrap its generated prelude in
   the `MEMINIT_PROTOCOL: begin/end` markers. Leave the trailing free-form
   region untouched for user content.
4. Add a normalization helper (`normalize_protocol_payload`) that strips
   trailing whitespace, forces LF line endings, and ensures a single trailing
   newline before hashing.
5. Keep bundled asset loading package-resource based so the registry is valid
   in installed distributions as well as local source checkouts.
6. Document the ownership model and marker grammar in the new FDD referenced
   by MEMINIT-PLAN-008.

Acceptance criteria:

1. Every supported protocol file has an explicit ownership entry in
   `protocol_assets.py` and a matching inventory row in the FDD.
2. Mixed-ownership files have a syntactically parseable `MEMINIT_PROTOCOL`
   region; user content outside the region is never read by sync logic.
3. Normalization produces a stable hash: identical logical content with
   different line endings or trailing whitespace yields the same `sha256`.
4. The `ProtocolAsset` registry is the single source of truth consumed by
   `init`, `protocol check`, and `protocol sync`.
5. The registry also declares file-mode expectations for fully generated
   executable assets.

### 3.2 Workstream B: Protocol Check Command

Problem:

- Operators and agents need a read-only way to know whether protocol assets are
  aligned with the live Meminit contract.

#### 3.2.1 Command surface

Command: `meminit protocol check`.

Flags:

- `--root PATH` (via `agent_repo_options`, same as other repo-aware commands).
- `--asset <id>` (repeatable). Restricts the check to one or more inventory
  entries by asset id. Defaults to the full inventory.
- Standard agent output options (`--format`, `--output`, `--include-timestamp`,
  `--correlation-id`) via `agent_output_options`.

The command must never write to the filesystem. It must succeed with exit
code 0 when no drift is detected, and with `EXIT_VIOLATIONS` (matching other
read-only governance commands) when drift is present. Usage errors use the
shared Click exit code 2.

JSON success semantics must match existing Meminit conventions:

- `success: true` only when every requested asset is `aligned`
- `success: false` when any requested asset is drifted or malformed
- drift findings are emitted through `violations[]`; informational notes stay in
  `warnings[]`

#### 3.2.2 Drift classification

Each asset check yields exactly one of the following outcomes. These map
directly to the new `ErrorCode` values listed in §3.2.4.

| Outcome | Meaning | Sync remediation |
| ------- | ------- | ---------------- |
| `aligned` | Asset exists; normalized managed content matches the canonical render. | No-op. |
| `missing` | Asset file does not exist at target path. | Write canonical render. |
| `legacy` | Mixed asset exists but has no `MEMINIT_PROTOCOL` markers (pre-v0.4 install, before protocol markers were introduced). | Wrap + refresh; preserve user content below the region for mixed assets. |
| `stale` | Asset is self-consistent on disk, but the canonical render has changed. For mixed assets, the recorded marker metadata matches the managed region but differs from the current canonical render; for fully generated assets, the whole file differs from the current canonical render. | Replace the managed content with the current canonical render. |
| `tampered` | Mixed asset markers parse, but the recorded `sha256` does not match the normalized managed payload currently on disk. | Refuse sync unless `--force` is passed; always reportable. |
| `unparseable` | Mixed asset markers are malformed, duplicated, or unterminated. | Refuse sync; require manual fix. |

Classification must be deterministic and ownership-aware:

1. `missing`: target path absent.
2. For fully generated assets: normalize whole file and compare against the
   canonical render; return `aligned` or `stale`.
3. For mixed assets: if no markers exist, return `legacy`.
4. For mixed assets with markers: parse structure; malformed structure is
   `unparseable`.
5. For mixed assets with parseable markers: recompute the normalized managed
   payload hash. If it does not match the recorded `sha256`, return
   `tampered`.
6. For mixed assets whose recorded metadata is self-consistent: compare the
   recorded `version` and canonical render hash against the current canonical
   render. Any mismatch is `stale`; otherwise the asset is `aligned`.

#### 3.2.3 Check output shape

The `data` payload in the v3 agent envelope follows this schema:

```json
{
  "root": "/abs/path/to/repo",
  "summary": {
    "total": 3,
    "aligned": 2,
    "drifted": 1,
    "unparseable": 0
  },
  "assets": [
    {
      "id": "agents-md",
      "target_path": "AGENTS.md",
      "ownership": "mixed",
      "status": "stale",
      "expected_version": "1.0",
      "recorded_version": "0.9",
      "expected_sha256": "…",
      "recorded_sha256": "…",
      "actual_sha256": "…",
      "auto_fixable": true
    }
  ]
}
```

Rules:

- `assets[]` is sorted lexicographically by `id` to guarantee determinism.
- `expected_*`, `recorded_*`, and `actual_*` fields are omitted when not
  meaningful.
- `actual_sha256` means the recomputed normalized hash of the managed content
  on disk; for mixed assets it is distinct from `recorded_sha256`.
- `auto_fixable` is `true` for `missing`, `legacy`, and `stale` outcomes and
  `false` for `tampered` and `unparseable`. This drives the `remediation`
  block emitted via `explain` (see §3.2.4).

#### 3.2.4 Error code and explain entries

Add the following codes to `ErrorCode` (namespace: `PROTOCOL_*`, no collision
with existing codes per the context gathered):

| Code | Outcome | `resolution_type` |
| ---- | ------- | ----------------- |
| `PROTOCOL_ASSET_MISSING` | `missing` | `auto_fixable` |
| `PROTOCOL_ASSET_LEGACY` | `legacy` | `auto_fixable` |
| `PROTOCOL_ASSET_STALE` | `stale` | `auto_fixable` |
| `PROTOCOL_ASSET_TAMPERED` | `tampered` | `manual` |
| `PROTOCOL_ASSET_UNPARSEABLE` | `unparseable` | `manual` |

Each code ships a matching `ERROR_EXPLANATIONS` entry emitted by
`meminit explain`, with `remediation.action` pointing to the appropriate
`meminit protocol sync` invocation or manual repair instruction. `automatable`
is `true` only for the three `auto_fixable` codes.

#### 3.2.5 Implementation tasks

1. Implement `ProtocolChecker` in `core/use_cases/protocol_check.py`. It takes
   a `ProtocolAssetRegistry`, iterates the inventory, and returns a sorted
   list of `ProtocolAssetStatus` records.
2. Add the `protocol` Click group and the `check` subcommand in
   `src/meminit/cli/main.py`, wired through `command_output_handler` like
   other agent-facing commands.
3. Extend `ErrorCode` and `ERROR_EXPLANATIONS` with the five codes above.
4. Add the drift summary exit-code mapping to `exit_codes.py` if a new code
   is needed, otherwise reuse the existing violations exit code.
5. Register `protocol check` and `protocol sync` in the capabilities registry
   with `needs_root: true`, `supports_json: true`, and
   `supports_correlation_id: true`. Both commands must pass the existing
   contract-matrix envelope validator with `additionalProperties: false`
   without scenario-specific skip markers.
6. Update the bundled and docs copies of `agent-output.schema.v3.json` so the
   repo-aware command enum includes `protocol check` and `protocol sync`.
7. Add contract-matrix coverage: `protocol check` must appear in
   `capabilities` output with `supports_json: true`.

Acceptance criteria:

1. `protocol check` never writes to the filesystem and passes the
   contract-matrix schema test automatically.
2. Every asset produces exactly one outcome; the classification order is
   fixed and unit-tested.
3. JSON output for identical repo states is byte-stable across runs.
4. `explain` returns a complete entry for each of the five new codes.
5. The shared envelope schema accepts the new command names without requiring a
   top-level contract redesign.

### 3.3 Workstream C: Protocol Sync Command

Problem:

- Drift detection without a supported repair path leaves operators doing manual,
  error-prone copy-editing.

#### 3.3.1 Command surface

Command: `meminit protocol sync`.

Flags:

- `--root PATH`, `--asset <id>` (repeatable) and all `agent_output_options`,
  matching `protocol check`.
- `--dry-run / --no-dry-run` with `--dry-run` as the default. Dry-run emits
  the same envelope shape as a real run but never writes, and `data.applied`
  is `false`.
- `--force / --no-force`, default `false`. Required to rewrite assets
  classified as `tampered`. Never allows rewriting `unparseable` assets;
  those must be repaired manually.

Exit behavior:

- `0` on a clean dry-run with no drift, on a successful write, or on a
  no-op write when already aligned.
- `EXIT_VIOLATIONS` when unsupported drift (`tampered` without `--force`,
  or any `unparseable`) remains after the sync pass.

JSON success semantics must also follow existing Meminit conventions:

- `success: true` only when the requested asset set is fully aligned after the
  command completes
- `success: false` when any requested asset ends in `refuse`

#### 3.3.2 Sync algorithm

Sync reuses the checker and then acts on each outcome deterministically:

1. Collect statuses via `ProtocolChecker` (same inputs, same ordering).
2. For each asset, decide an action:
   - `aligned` → `noop`.
   - `missing` / `legacy` / `stale` → `rewrite`.
   - `tampered` → `rewrite` only if `--force`; otherwise `refuse`.
   - `unparseable` → always `refuse`.
3. For each `rewrite`:
   a. Compute the canonical payload via `ProtocolAsset.render()`.
   b. For mixed-ownership files, read the existing file, extract any content
      after `MEMINIT_PROTOCOL: end`, and concatenate it unchanged after the
      newly rendered region. If no end marker is found (legacy), the entire
      existing content is treated as user-owned and appended after the new
      region. Files that never existed get only the generated region plus a
      trailing newline.
      If the end marker exists but no user content follows it, the rendered
      output still ends with a trailing newline so the Markdown file remains
      well-formed.
   c. Validate the write target with `ensure_safe_write_path`, normalize line
      endings to LF, write atomically via a dedicated `safe_fs` helper
      (temp-file + `os.replace`), and apply the registry-declared file mode on
      Unix.
4. Do not touch the filesystem in dry-run mode; only report the planned
   action per asset.

The algorithm is idempotent: running sync twice on a clean repo produces no
writes and returns `aligned` for every asset.

#### 3.3.3 Sync output shape

```json
{
  "root": "/abs/path/to/repo",
  "dry_run": true,
  "applied": false,
  "summary": {
    "total": 3,
    "rewritten": 1,
    "refused": 0,
    "noop": 2
  },
  "assets": [
    {
      "id": "agents-md",
      "target_path": "AGENTS.md",
      "prior_status": "stale",
      "action": "rewrite",
      "preserved_user_bytes": 1843
    }
  ]
}
```

`preserved_user_bytes` is only populated for mixed-ownership files and
exists so agents can reason about whether user content was carried across
the rewrite. Assets ordering is lexicographic by `id`.

#### 3.3.4 Implementation tasks

1. Implement `ProtocolSync` in `core/use_cases/protocol_sync.py` consuming
   the same registry as the checker.
2. Add the `protocol sync` Click subcommand under the `protocol` group.
3. Introduce a small `safe_fs` atomic-write helper if the existing service
   does not already provide one; never write directly to the target path.
4. Emit warnings (not violations) when `--force` is used, so that orchestrators
   have visibility into non-default repair behavior.
5. Make `init` consume the same asset registry so freshly initialized repos
   get the same canonical protocol assets that `protocol sync` would render.
6. Update the skill manifest bundled at `meminit-docops-skill.md` to mention
   the new `protocol check` / `protocol sync` commands and the preview-first
   default, so fresh installs teach the right workflow.

Acceptance criteria:

1. Supported drift can be repaired without manual copy-paste.
2. User-managed content in mixed-ownership files is preserved byte-for-byte
   after sync.
3. Re-running sync on an already aligned repo writes zero bytes and returns
   all-`noop`.
4. `tampered` assets are never rewritten without explicit `--force`.
5. `unparseable` assets are never rewritten regardless of flags.
6. All protocol writes stay inside the repository root and preserve declared
   executable mode where required.

### 3.4 Workstream D: CI and Bundled Skill Alignment

Problem:

- Even a good local sync/check flow will drift again if enforcement is not
  wired into normal repo workflows.

Implementation tasks:

1. Add a reference CI step that runs `meminit protocol check --format json`
   after the existing DocOps validation path.
2. Update bundled skill and setup guidance if the supported protocol model
   changes.
3. Ensure bundled protocol assets point readers back to the runtime contract
   where possible, instead of duplicating static command inventories.
4. Add coverage showing that capabilities output and protocol generation remain
   aligned.
5. Validate the resulting workflow in the external testbed.

Acceptance criteria:

1. The supported enforcement path is documented and testable.
2. Bundled protocol assets remain aligned with live CLI behavior.
3. The external testbed can use the new check and sync workflow cleanly.
4. Generated protocol text references runtime contract surfaces where that
   reduces duplication and drift.

### 3.5 Workstream E: Documentation and Rollout Boundaries

Problem:

- Protocol governance can become intrusive if rollout boundaries are not stated
  explicitly.

Implementation tasks:

1. Create the new FDD for protocol surface governance.
2. Update `MEMINIT-PRD-005` and `MEMINIT-SPEC-006` as listed in §2.2.
3. Create or update the runbook covering adoption, CI, and recovery paths.
4. Document the supported asset set, non-goals, and what Meminit will and will
   not rewrite.
5. Record how early adopters should handle local customizations.
6. Update planning docs if the phase boundary shifts materially.

Acceptance criteria:

1. The rollout model is explicit and bounded.
2. Local customization guidance exists.
3. The governed document set required by MEMINIT-PLAN-008 for Phase 3 is in
   place.
4. Code, docs, and tests remain synchronized.

### 3.6 Workstream F: Drift Fixtures and Determinism Tests

Problem:

- Without an enumerated fixture set, check and sync regressions can ship
  unnoticed, especially for the rarer classification paths.

#### 3.6.1 Required fixture scenarios

Each fixture is a self-contained repo state under
`tests/fixtures/protocol/<scenario-id>/`. Every scenario must have a
test case exercising both `protocol check` (outcome + JSON shape) and,
where applicable, `protocol sync` (planned vs. applied behavior).

> **Approved deviation (v0.5):** Fixtures are code-generated by
> `tests/fixtures/protocol/conftest.py` rather than stored as
> checked-in directory trees. This avoids byte-level diff noise and
> keeps fixtures deterministic via the same render/normalize paths as
> production code. See MEMINIT-FDD-012 §Testing.

| ID | Scenario | Expected check outcome | Expected sync action |
| -- | -------- | ---------------------- | -------------------- |
| F01 | Freshly-initialized repo | all `aligned` | `noop` across all assets |
| F02 | `AGENTS.md` missing | `missing` | `rewrite` (creates file) |
| F03 | Skill manifest missing | `missing` | `rewrite` (creates file) |
| F04 | Pre-v0.4 `AGENTS.md` without markers | `legacy` | `rewrite` wrapping existing content below |
| F05 | Mixed asset with stale recorded `version` | `stale` | `rewrite` |
| F06 | Mixed asset whose recorded marker metadata is self-consistent but whose canonical render hash has changed | `stale` | `rewrite` |
| F07 | Generated region edited in place (markers intact) | `tampered` | `refuse` without `--force`; `rewrite` with `--force` |
| F08 | Duplicate `MEMINIT_PROTOCOL: begin` | `unparseable` | always `refuse` |
| F09 | Missing `MEMINIT_PROTOCOL: end` marker | `unparseable` | always `refuse` |
| F10 | Mixed file with rich user content below region and stale generated content above it | `stale` | rewritten region plus byte-identical preserved user content |
| F11 | Line-ending variants (`CRLF`) in generated region | `aligned` after normalization | `noop` |
| F12 | Trailing whitespace or extra blank lines in generated region | `aligned` after normalization | `noop` |
| F13 | Asset filter (`--asset agents-md`) on multi-drift repo | only `agents-md` reported | only `agents-md` rewritten |
| F14 | Idempotency: run sync twice | second run produces `noop` everywhere, zero writes | -- |
| F15 | Byte-level determinism: two identical repo states on different machines | identical JSON envelopes (stable hash sort order) | -- |

#### 3.6.2 Implementation tasks

1. Add a fixture loader in `tests/fixtures/protocol/conftest.py`
   that materializes scenarios into `tmp_path` from code-generated
   definitions (not checked-in directory trees; see §3.6.1 deviation note).
2. Parametrize a single `test_protocol_check_outcomes` over F01–F13 and
   assert: `data.assets[].status`, sorted asset order, and (for drifted
   scenarios) the presence of the matching `PROTOCOL_*` violation code.
3. Parametrize `test_protocol_sync_actions` over F02–F10 asserting planned
   actions under `--dry-run`, applied actions under `--no-dry-run`, and
   byte-identical preservation of user regions.
4. Add F14 and F15 as dedicated tests: F14 runs sync twice and asserts the
   second run produces zero writes and all-`noop`; F15 serializes two check
   envelopes from independently-constructed fixtures and asserts strict
   byte equality after deterministic sorted-key JSON serialization.
5. Extend the contract-matrix so `protocol check` and `protocol sync` are
   automatically exercised for envelope compliance, stdout/stderr
   isolation, and `additionalProperties: false` conformance.
6. Add a fixture-driven JSON-schema test that runs `protocol check` and
   `protocol sync` on representative fixture states and asserts conformance to
   `agent-output.schema.v3.json`, including correct types and no unexpected
   fields.

Acceptance criteria:

1. All fixture scenarios (F01-F15 and extensions) are present as
   code-generated definitions in `tests/fixtures/protocol/conftest.py`
   and exercised by parametrized tests in `tests/fixtures/test_protocol_fixtures.py`.
2. Every `PROTOCOL_*` error code is exercised by at least one fixture.
3. The contract-matrix includes both new commands without any scenario-
   specific skip markers.
4. Determinism test (F15) asserts byte-equal envelopes, not just
   field-wise equivalence.

## 4. Recommended Delivery Sequence

1. Workstream A: Protocol Asset Boundary Definition
2. Workstream B: Protocol Check Command
3. Workstream F: Drift Fixtures and Determinism Tests (scaffold in parallel
   with A/B; fixtures drive B's unit tests)
4. Workstream C: Protocol Sync Command
5. Workstream D: CI and Bundled Skill Alignment
6. Workstream E: Documentation and Rollout Boundaries

Reason:

- Generated-region ownership must be decided before any command can check or
  sync safely.
- Read-only check behavior should land before mutation behavior.
- Fixture scaffolding should come online alongside the checker so that each
  classification branch ships with a regression guard.
- CI and bundled-skill integration should follow once the local contract is
  stable.

### 4.1 Recommended PR Slices

To keep reviewable scope and preserve the repository's atomic-unit rule, Phase
3 should land as small PRs:

1. Asset registry + `AGENTS.md` mixed-region format + FDD scaffold + unit tests
   for parsing and normalization.
2. `protocol check` + `PROTOCOL_*` error codes + capabilities/schema updates +
   contract and fixture tests.
3. `protocol sync` + safe atomic-write helper + idempotency/preservation tests.
4. `init` integration + bundled skill updates + runbook and CI guidance.
5. External testbed validation, final doc reconciliation, and closeout.

## 5. Exit Criteria for Phase 3

Phase 3 can be considered complete when all of the following are true:

1. `core/services/protocol_assets.py` enumerates every supported asset
   (Workstream A), and `init`, `protocol check`, and `protocol sync` share
   that registry.
2. `AGENTS.md` ships with `MEMINIT_PROTOCOL: begin/end` markers and the
   mixed-ownership model is documented in an FDD (Workstreams A and E).
3. `meminit protocol check` returns the schema shape in §3.2.3, is
   deterministic across runs, and never writes to the filesystem
   (Workstream B).
4. `meminit protocol sync` defaults to `--dry-run`, preserves user bytes in
   mixed-ownership files, refuses `tampered` without `--force`, and always
   refuses `unparseable` (Workstream C).
5. The five new `PROTOCOL_*` error codes are registered in `ErrorCode` and
   have complete `ERROR_EXPLANATIONS` entries reachable via
   `meminit explain --list` (Workstream B).
6. Both new commands appear in `meminit capabilities` with
   `supports_json: true` and pass the contract-matrix envelope validator
   with `additionalProperties: false` (Workstreams B and F).
7. The 15 fixture scenarios in §3.6.1 are present, tested, and green
   (Workstream F).
8. Idempotency and determinism tests (F14, F15) pass (Workstream F).
9. Bundled `meminit-docops` skill references the new commands and the
   preview-first default (Workstream D).
10. The governed document outputs listed in §2.2 are complete and aligned with
    the shipped behavior (Workstream E).

## 6. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-14 | GitCmurf | Initial draft created via `meminit new` |
| 0.2 | 2026-04-14 | Codex | Replaced stub with detailed Phase 3 workstreams, sequencing, and exit criteria |
| 0.3 | 2026-04-17 | Augment | Concrete protocol-asset inventory and region-marker grammar (Workstream A); `protocol check` outcomes, output schema, and `PROTOCOL_*` error codes (Workstream B); deterministic sync algorithm with preview-first default and user-content preservation (Workstream C); added Workstream F with 15 fixture scenarios and determinism tests; tightened exit criteria |
| 0.4 | 2026-04-17 | Codex | Tightened engineering handoff quality: clarified runtime-contract references, codebase-fit constraints, and required governed-doc outputs; fixed drift-classification inconsistencies (`stale` vs `tampered`) and mixed-vs-generated asset rules; added schema/capabilities updates, `init`/safe-write integration, PR slicing guidance, and stronger rollout closeout criteria |
| 0.5 | 2026-04-19 | Augment | Amended §3.6.1 to record approved deviation from checked-in fixture directories to code-generated fixtures (see MEMINIT-FDD-012 §Testing) |
