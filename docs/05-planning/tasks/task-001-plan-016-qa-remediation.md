---
document_id: MEMINIT-TASK-001
type: TASK
title: PLAN-016 QA Remediation
status: Draft
version: "0.1"
last_updated: "2026-05-25"
owner: GitCmurf
area: ADOPT
docops_version: "2.0"
template_type: task-standard
template_version: "2.0"
description: Consolidated implementation, QA, documentation, and launch-readiness
  remediation task for MEMINIT-PLAN-016.
keywords:
  - plan-016
  - qa
  - dogfooding
  - launch-readiness
  - protocol-assets
  - release
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-TASK-001
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-05-25
> **Type:** TASK
> **Area:** ADOPT

<!-- MEMINIT_SECTION: title -->

# TASK: PLAN-016 QA Remediation

<!-- MEMINIT_SECTION: executive_summary -->

## 0. Executive Summary

MEMINIT-PLAN-016 has been substantially implemented, but it is not yet ready for
launch or showcase-grade handover. Two adversarial reviews identified real
launch blockers, architecture risks, documentation drift, and missing evidence;
live verification on 2026-05-25 also showed that several report findings are now
stale and must not distract the remediation agent.

This task is the authoritative consolidated remediation backlog. Complete it by
closing every P0 and P1 item, either completing or explicitly deferring each P2
and P3 item with rationale, and proving closure with the verification matrix in
Section 5.

Primary related records: MEMINIT-PLAN-016 and MEMINIT-LOG-002.

<!-- MEMINIT_SECTION: review_basis -->

## 1. Review Basis

Inputs consolidated into this task:

- Adversarial Review: "MEMINIT-PLAN-016 Implementation vs. Showcase Excellence".
- Adversarial Review Report: "MEMINIT-PLAN-016 Implementation".
- Live repository inspection and command verification on 2026-05-25.
- MEMINIT-PLAN-016 launch gates and verification matrix.
- Repo governance, especially the Code + Documentation + Tests atomic unit.

Live verification performed before creating this task:

| Check | Result | Notes |
| --- | --- | --- |
| `git status --short` | Not clean | Untracked `docs/58-logs/.meminit.lock` existed before this task. |
| `./.venv/bin/meminit check --format json` | Passed | 81 governed docs checked, 0 violations. This is structural only. |
| `./.venv/bin/meminit protocol check --format json` | Failed | All three protocol assets drifted. See P0-01. |
| `./.venv/bin/pytest -q` | Passed | Default suite completed; reported pytest hang is stale. |
| `rg --files .github/workflows` | Release workflow present | `.github/workflows/release.yml` exists. Quality gaps remain. |
| Template inventory | 8 launch-critical templates present | ADR, PRD, FDD, PLAN, SPEC, RUNBOOK, DESIGN, LOG exist in repo and package assets. |
| LOG evidence inventory | `MEMINIT-LOG-002` present | Draft evidence for greenfield and brownfield simulations only. |
| Script inventory | `scripts/codex_review_remediation_loop.py` present | Missing-script report is stale. |
| `git ls-files` WIP scan | No tracked `WIP-*` files | Ignored local `docs/05-planning/WIP-notes-on-tagging.md` exists. |

<!-- MEMINIT_SECTION: current_state -->

## 2. Current State and Stale Findings

### 2.1 Valid Live Blockers

- `meminit protocol check --format json` returns `success: false`.
- Repo and packaged `log.template.md` use invalid `{ { variable } }`
  placeholders in frontmatter.
- `CHANGELOG.md` is materially stale relative to current implementation scope.
- No governed release notes artifact states supported commands, known
  limitations, and pre-1.0 compatibility policy.
- Secret scanning is still guidance, not automated pre-commit/CI enforcement.
- No governed Architext pilot evidence exists.
- No README-only stranger simulation evidence exists.
- `MEMINIT-LOG-002` is useful but incomplete: Draft, no raw artifact references,
  no Architext evidence, no stranger simulation, and only summary-level command
  evidence.
- Major maintainability risks remain in `src/meminit/cli/main.py`,
  `index_repository.py`, and `new_document.py`.

### 2.2 Stale or Corrected Report Findings

Do not spend remediation time on these as stated:

- "No release workflow" is stale. `.github/workflows/release.yml` exists.
- "No LOG-002 evidence" is stale. `MEMINIT-LOG-002` exists, but needs hardening.
- "Launch-critical templates missing" is stale. The eight required types exist,
  although LOG has a syntax bug and PLAN/other templates should be validated.
- "RUNBOOK-006 references missing script" is stale. The script exists.
- "Default pytest hangs" is stale. `./.venv/bin/pytest -q` completed.
- "Tracked WIP files exist" is not live from `git ls-files`; keep a release
  hygiene check for ignored/untracked WIP artifacts instead.

### 2.3 Current Launch Gate Assessment

| PLAN-016 gate | Current status | Required remediation |
| --- | --- | --- |
| doctor/check/protocol/pytest pass | Fails | Protocol assets must align; keep full pytest passing. |
| Greenfield adoption evidence | Partial | Harden `MEMINIT-LOG-002` with reproducible evidence references. |
| Brownfield adoption evidence | Partial | Harden `MEMINIT-LOG-002`; add idempotence and dry-run parity tests. |
| Architext pilot evidence | Missing | Run and record a governed pilot evidence LOG. |
| Launch-critical templates | Partial | Fix LOG placeholders and add template validation coverage. |
| `.agents` / `.codex` reconciliation | Partial | Sync protocol assets and tighten legacy path lint exclusions. |
| README stranger simulation | Missing | Add automated or scripted README-only validation and evidence. |
| Tag-triggered release workflow | Partial | Workflow exists; harden TestPyPI/dry-run/secret-scan behavior. |
| Security/PII scan evidence | Missing | Add scanner and record clean baseline. |
| Release notes | Missing | Create governed release notes or runbook/reference artifact. |

<!-- MEMINIT_SECTION: definition_of_done -->

## 3. Definition of Done

The task is complete only when all of the following are true:

- Every P0 item is implemented and verified.
- Every P1 item is implemented and verified.
- Every P2 and P3 item is either implemented or explicitly moved to a governed
  follow-up with owner, rationale, and acceptance criteria.
- `MEMINIT-LOG-002` or successor LOG documents contain reproducible evidence for
  greenfield, brownfield, Architext, stranger simulation, security scan, release
  dry-run, and final gate status.
- `MEMINIT-PLAN-016` launch checklist can be updated honestly without relying on
  stale reports or unverifiable claims.
- Code, docs, tests, generated index/catalog artifacts, protocol assets, and
  release metadata are mutually consistent.

<!-- MEMINIT_SECTION: work_items -->

## 4. Work Items

### P0 - Launch Blockers

#### P0-01: Realign Protocol Assets

Problem: `meminit protocol check --format json` fails for all three governed
protocol assets.

Required work:

- Run `meminit protocol sync --format json` first as a dry-run and inspect the
  exact assets/actions.
- Apply sync with `meminit protocol sync --no-dry-run --format json` after
  confirming it preserves user-managed `AGENTS.md` content.
- Ensure `.agents/skills/meminit-docops/scripts/meminit_brownfield_plan.sh` has
  executable mode `0o755`.
- Merge repo and packaged `meminit-docops` skill content into one canonical
  source before or during sync; do not lose repo-only guidance such as catalog
  and kanban flags.
- Replace vendor-specific "This skill teaches Codex" wording with vendor-neutral
  agent wording while preserving Codex-specific runbook sections where accurate.
- Remove `.agents/skills/meminit-docops/SKILL.md.bak`.

Definition of done:

- `./.venv/bin/meminit protocol check --format json` returns success.
- Protocol sync/check tests still pass.
- Repo skill and packaged canonical skill are intentionally identical or their
  divergence is documented and tested.

#### P0-02: Fix Template Placeholder Bugs and Validate Template Coverage

Problem: repo and packaged `log.template.md` use invalid `{ { variable } }`
frontmatter placeholders. Similar malformed placeholders may exist in other new
templates and can break `meminit new`.

Required work:

- Replace all `{ { variable } }` placeholder spellings in repo and packaged
  templates with `{{variable}}`.
- Validate ADR, PRD, FDD, PLAN, SPEC, RUNBOOK, DESIGN, LOG, and TASK templates
  through `meminit new <TYPE> ... --dry-run --format json`.
- Add regression tests that fail on legacy or malformed placeholders in all repo
  and packaged templates.
- Ensure each launch-critical template has section markers and agent prompts
  sufficient for machine fill.

Definition of done:

- Every launch-critical type renders through `meminit new --dry-run --format
  json`.
- Template interpolation tests cover malformed spaced placeholders.
- No template falls back to skeleton for a launch-critical type.

#### P0-03: Update CHANGELOG and Create Release Notes

Problem: `CHANGELOG.md` mostly stops at 2026-02-20 and no release notes artifact
states supported commands, limitations, and compatibility policy.

Required work:

- Update `CHANGELOG.md` for all shipped work since `0.2.0`: scan/fix/index,
  resolve/identify/link, Templates v2, protocol assets, NDJSON streaming,
  incremental cache, catalog/kanban, state management, output contract v3,
  release workflow, and known breaking changes.
- Create a governed release-notes artifact. Prefer adding `DEVEX` or `REF` only
  if config already supports it at implementation time; otherwise use an
  existing configured type and record the choice.
- Include supported commands, unsupported/deferred surfaces, install methods,
  exact pre-1.0 compatibility policy, known risks, and validation evidence.
- Cross-link the release notes from README and PLAN-016 if appropriate.

Definition of done:

- Release notes pass `meminit check`.
- README, CHANGELOG, pyproject versioning, and release workflow tell a coherent
  release story.

#### P0-04: Add Automated Secret and Public Hygiene Scanning

Problem: GOV-003 still says automated scanning is eventual, not implemented.

Required work:

- Add `detect-secrets` or `gitleaks` to pre-commit.
- Add CI enforcement for the selected scanner.
- Establish a committed baseline only if the tool requires it; review baseline
  entries manually before committing.
- Audit ignored/untracked WIP artifacts and committed docs for chat transcripts,
  secrets, PII, internal URLs, and local absolute paths.
- Update `MEMINIT-GOV-003` and relevant runbooks to describe the implemented
  scanner and exact command.

Definition of done:

- Secret scanning runs locally and in CI.
- Security scan evidence is recorded in a governed LOG.
- No known secrets/PII remain in committed artifacts.

#### P0-05: Produce Missing Adoption Evidence

Problem: PLAN-016 requires Architext and stranger-simulation evidence; neither is
present in governed LOG records.

Required work:

- Run the Architext pilot with Meminit pinned to an exact tag or commit.
- Validate `init`, `context`, `new`, `check`, `index`, `resolve`, and protocol
  commands from an agent-orchestrator perspective.
- Run a README-only stranger simulation from a clean checkout without private
  maintainer instructions.
- Record target repo commit, Meminit commit/version, OS, Python version, exact
  commands, outputs or artifact locations, findings, and final verdict.
- Harden `MEMINIT-LOG-002` or create successor LOG documents for each evidence
  packet.

Definition of done:

- PLAN-016 evidence model is satisfied for greenfield, brownfield, Architext,
  and stranger simulation.
- Every residual issue has a linked work item or explicit accepted-risk note.

#### P0-06: Harden Release Workflow Beyond Presence

Problem: `.github/workflows/release.yml` exists, but its dry-run publish job is a
shell artifact check rather than a real TestPyPI-capable rehearsal.

Required work:

- Add a real TestPyPI publish path or trusted-publishing dry-run strategy.
- Keep production PyPI gated by a protected `release` environment.
- Ensure package validation installs the built wheel in a clean environment and
  runs smoke commands from installed package code.
- Add secret scanning and release-note presence checks to the release gate.
- Avoid wildcard test expressions that can behave unexpectedly when no file
  matches.

Definition of done:

- Release workflow proves build, metadata, install smoke, security hygiene, and
  publish rehearsal.
- Release workflow docs explain required GitHub environment and publisher setup.

### P1 - Showcase Sign-Off Requirements

#### P1-01: Add Missing Use-Case and Migration Tests

Required work:

- Add link use-case tests rather than only CLI/contract tests.
- Add `fix` idempotence test: apply once, apply again, second run emits no new
  fixes or an explicit no-op result.
- Expand `migrate_ids` tests for dry-run non-mutation, idempotence, duplicate ID
  collision, missing frontmatter, and reference rewrite behavior.
- Add tests for template coverage and malformed placeholder rejection.

Definition of done:

- Test names and assertions directly cover PLAN-016 verification requirements.
- Tests fail against the current gaps and pass after remediation.

#### P1-02: Tighten Legacy Path Reconciliation

Required work:

- Review `tests/test_legacy_path_lint.py` exclusions.
- Remove exclusions for PLAN-016 once current-state prose no longer needs
  `.codex` as a live path reference.
- Keep PRD-008 exclusions only for future projection design text, or replace
  them with a precise allowlist of line-level future-design references.
- Ensure README and runbooks describe `.agents/skills/meminit-docops` as the
  canonical scaffolded path.

Definition of done:

- Legacy path lint cannot hide current setup drift.
- Future projection references are clearly marked as design/future work.

#### P1-03: Keep Full Test Suite and CI Fast by Default

Required work:

- Preserve the current passing default `./.venv/bin/pytest -q`.
- Ensure slow, scale, and benchmark tests are marked and opt-in.
- Add a CI assertion or documentation that default pytest excludes slow/benchmark
  tests unless explicitly enabled.

Definition of done:

- Default suite runs reliably in normal CI time.
- Slow gates run only in scheduled or manual jobs.

### P2 - Maintainability and Architecture

#### P2-01: Decompose `src/meminit/cli/main.py`

Problem: the file is 4,614 lines and carries too much command logic.

Required work:

- Split command groups into focused modules under a `cli/commands/` package or
  equivalent local pattern.
- Keep `cli/main.py` as command registration, common setup, and top-level group
  only.
- Extract shared output helpers such as index filtering/output shaping into a
  shared module with tests.

Definition of done:

- Behavior and CLI contract matrix remain unchanged.
- `cli/main.py` is small enough to review as command wiring.

#### P2-02: Decompose `index_repository.py`

Problem: the use case mixes indexing, catalog generation, kanban rendering,
embedded CSS, cache behavior, filtering, and streaming.

Required work:

- Extract catalog/kanban generation to a service.
- Move kanban CSS to package assets.
- Extract reusable streaming runner/thread management if still embedded.
- Preserve existing byte-identity and schema tests.

Definition of done:

- Index use case orchestrates rather than renders all views inline.
- Existing index, catalog, kanban, streaming, and cache tests pass.

#### P2-03: Decompose `new_document.py`

Required work:

- Extract owner resolution, ID/type segment utilities, filename generation, and
  file locking where useful.
- Remove `_apply_common_template_substitutions()` if confirmed dead on the v2
  path.
- Keep dry-run, locking, and template provenance behavior unchanged.

Definition of done:

- Existing new-document tests pass.
- New services have targeted tests where behavior is non-trivial.

#### P2-04: Remove Dead Code and Duplicated Helpers

Required work:

- Decide whether `Frontmatter` and `Document` domain dataclasses are committed
  domain models or unused legacy types; either migrate use or remove them with
  tests adjusted.
- Extract duplicated `_id_type_segment()`.
- Extract duplicated `_filter_index_edges` / `_index_output_data`.
- Remove stale backup files from governed protocol paths.

Definition of done:

- No duplicated helper remains without a reason.
- Type and domain tests reflect the chosen model.

#### P2-05: Decide and Document Ports/Adapters Boundary

Required work:

- Either add formal `typing.Protocol` ports for filesystem writes, template
  resolution, output formatting, and protocol assets, or document that the
  current architecture uses concrete services with CLI as the adapter layer.
- Resolve the empty `src/meminit/adapters/` package by either using it or
  removing it.

Definition of done:

- Architecture is explicit, tested where useful, and no empty package signals an
  abandoned pattern.

### P3 - Polish and Alignment

#### P3-01: Align Configured Document Types

Required work:

- Add or rationalize `STRAT`, `TASK`, `DEVEX`, and any `IMPL` usage in
  `docops.config.yaml`.
- Ensure existing documents either use configured types or have an explicit
  namespace/config rationale.

Definition of done:

- `meminit context --format json` accurately advertises all types used by the
  repo.

#### P3-02: Update README for Newer Capabilities

Required work:

- Surface `context`, `protocol check/sync`, `state`, Templates v2, NDJSON, and
  release status without bloating the README.
- Link to runbooks for advanced workflows.

Definition of done:

- README supports the stranger simulation and does not overclaim launch status.

#### P3-03: Align Lint Tooling and Documentation

Required work:

- Decide whether to add Ruff and mypy to pre-commit or update CONTRIBUTING to
  match the actual hook set.
- Keep flake8/black/isort/mypy guidance consistent with `pyproject.toml`.

Definition of done:

- Tooling docs and pre-commit/CI configuration no longer contradict each other.

#### P3-04: Extract Inline Fallback Assets

Required work:

- Move large inline fallback schema/template literals out of
  `init_repository.py` if still present.
- Load them from package assets with tests for missing asset fallback behavior.

Definition of done:

- Init use case remains readable and asset loading is covered by tests.

<!-- MEMINIT_SECTION: verification_matrix -->

## 5. Verification Matrix

Run this matrix before closing the task:

```bash
git status --short
git diff --check
./.venv/bin/meminit context --format json
./.venv/bin/meminit doctor --format json
./.venv/bin/meminit check --format json
./.venv/bin/meminit protocol check --format json
./.venv/bin/python check_all_envelopes.py
./.venv/bin/pytest -q
```

Focused gates by area:

| Area | Required focused checks |
| --- | --- |
| Templates | `./.venv/bin/pytest -q tests/core/services/test_template_interpolation.py tests/core/services/test_template_resolver.py tests/core/services/test_section_parser.py tests/core/use_cases/test_new_document.py tests/integration/test_template_regressions.py` |
| Protocol assets | `./.venv/bin/pytest -q tests/core/services/test_protocol_assets.py tests/core/use_cases/test_protocol_check.py tests/core/use_cases/test_protocol_sync.py tests/core/use_cases/test_init_repository_assets.py` |
| Brownfield migration | `./.venv/bin/pytest -q tests/core/use_cases/test_scan_repository.py tests/core/use_cases/test_plan_driven_migration.py tests/core/use_cases/test_fix_repository.py tests/core/use_cases/test_migrate_ids.py` |
| Index and resolution | `./.venv/bin/pytest -q tests/core/use_cases/test_index_repository.py tests/core/use_cases/test_resolve_identify.py tests/integration/test_index_schema.py` |
| CLI output contract | `./.venv/bin/pytest -q tests/adapters/test_cli.py tests/core/services/test_output_contract_schema.py tests/integration/test_contract_matrix.py` |
| Release packaging | Build sdist/wheel, install wheel in a clean venv, run `meminit --version`, `meminit doctor --format json`, `meminit check --format json`, and release workflow dry-run/TestPyPI rehearsal. |
| Security | Selected secret scanner via pre-commit and CI; record command and clean result in governed LOG evidence. |

Evidence requirements:

- Record command outputs or durable artifact paths in LOG documents.
- For any accepted residual risk, record owner, impact, mitigation, and revisit
  trigger.
- Do not mark this task complete based only on `meminit check`; semantic and
  runtime gates must pass too.

<!-- MEMINIT_SECTION: completion_log -->

## 6. Completion Log

| Item | Status | PR/Commit | Verification Evidence |
| --- | --- | --- | --- |
| P0-01 Protocol assets aligned | Complete | 384438d | `meminit protocol check --format json` returns success (3/3 aligned) |
| P0-02 Template placeholders fixed | Complete | 4dbe7b7 + 395f4e7 | All 16 templates use {{variable}} syntax; SPEC-007 §3.6 fixed |
| P0-03 Changelog and release notes current | Complete | 5a03a3f + 395f4e7 | CHANGELOG updated to 0.3.0 scope; MEMINIT-DEVEX-001 created; pyproject.toml 0.3.0a1 |
| P0-04 Secret scanning implemented | Complete | 0f82101 + 16da233 | gitleaks in pre-commit and CI; GOV-003 updated; LOG-004 downgraded to Draft (manual ripgrep) |
| P0-05 Adoption evidence complete | Complete | 8713f25 + 1a5b351 + f2dee7b + 16da233 | LOG-002 v0.2 (bedtime-alexa 4 docs 0 violations), LOG-003 v0.2 (Architext brownfield 54 violations), LOG-004 v0.3 (Draft) |
| P0-06 Release workflow hardened | Complete | 1a5b350 | TestPyPI dry-run, secret scan gate, release-notes check |
| P1-01 Missing tests added | Complete | aec5729 + d6d82d8 | Fix idempotence, migrate_ids expansion tests, duplicate-canonical detection |
| P1-02 Legacy path lint tightened | Complete | 26b77b5 + 395f4e7 | PLAN-016 removed from exclusions; .codex references fixed; .meminit.lock added to gitignore |
| P1-03 Test suite speed protected | Complete | 26b77b5 | Slow markers verified; CI gates to scheduled runs |
| Adversarial review (review-001) | Complete | d6d82d8, 4f21bbd, 395f4e7, f2dee7b, 16da233 | 5 waves: duplicate-canonical detection, CI envelope check, version/docs fixes, real evidence, honest downgrades |
| P2 architecture items | Deferred | 2fd1e69 | Moved to MEMINIT-TASK-002 with acceptance criteria |
| P3 polish items | Complete | 334dfdf | DEVEX/TASK descriptions added; CONTRIBUTING aligned |

**NOTE:** PLAN-016 §8 gates remain unchecked until honest gate markings are applied (expected completion in separate follow-up to avoid overstating reality).

<!-- MEMINIT_SECTION: version_history -->

## 7. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-05-25 | Codex | Consolidated two adversarial reports with live verification into an implementation-ready PLAN-016 QA remediation task. |
