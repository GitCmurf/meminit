---
document_id: MEMINIT-PLAN-016
type: PLAN
title: Adoption and Dogfooding Sequencing
status: Draft
version: "0.4"
last_updated: "2026-05-29"
owner: GitCmurf
docops_version: "2.0"
area: ADOPT
description:
  Defines the dogfood-first adoption sequence, engineering workstreams,
  verification gates, and release-readiness criteria for Meminit's first public
  package launch.
keywords:
  - adoption
  - dogfooding
  - release-readiness
  - templates-v2
  - agent-skill
  - brownfield
related_ids:
  - MEMINIT-PLAN-003
  - MEMINIT-STRAT-001
---

> **Document ID:** MEMINIT-PLAN-016
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.4
> **Last Updated:** 2026-05-29
> **Type:** PLAN
> **Area:** ADOPT
> **Description:** Defines the dogfood-first adoption sequence, engineering workstreams, verification gates, and release-readiness criteria for Meminit's first public package launch.

# PLAN: Adoption and Dogfooding Sequencing

<!-- MEMINIT_SECTION: executive_summary -->

## 0. Executive Summary

Meminit should not treat "published on PyPI" as the next unit of progress. The
next unit of progress is a repeatable adoption loop that proves the golden paths
on real repositories, produces actionable defects, and closes those defects with
code, tests, and governed documentation in sync.

This plan is subordinate to [MEMINIT-PLAN-003](plan-003-roadmap.md) for the
long-range roadmap and to
[MEMINIT-STRAT-001](../02-strategy/strat-001-project-meminit-vision.md) for
strategic constraints. Where near-term sequencing differs, this plan records the
newer decision: dogfood first, harden from evidence, then publish and promote as
a deliberate quality-gated launch.

**Definition of done for this plan:** engineering and testing teams can pick up
the work without reinterpreting intent. Every launch gate below has an owner
surface, a validation command or artifact, and an explicit evidence requirement.

<!-- MEMINIT_SECTION: current_state -->

## 1. Current Verification Snapshot

These findings were verified against the repository and dogfooding records on
2026-05-29. This document remains Draft pending peer review; the implementation
evidence is complete enough for review/handover, not for unreviewed external
launch claims.

- The core agent interface has the v3 JSON envelope and NDJSON streaming support.
  Adoption workflows should use `--format json` by default and opt into NDJSON
  only for advertised large-output commands.
- Local verification currently passes for `meminit doctor`, `meminit check`,
  `meminit protocol check`, full default `pytest`, and the configured secret
  scanner. The full test suite is fast by default, with slow scale and benchmark
  tests explicitly opt-in.
- Launch-critical templates are now present in repo and packaged assets for ADR,
  PRD, FDD, PLAN, SPEC, RUNBOOK, DESIGN, LOG, and TASK. Template placeholders use
  `{{variable}}` syntax and are covered by regression tests.
- `meminit init` and protocol governance use `.agents/skills/meminit-docops` as
  the canonical scaffolded skill path. Protocol assets are currently aligned.
- Release engineering exists through the tag-triggered workflow, package build
  checks, release-note checks, and secret scanning. Production PyPI release still
  requires maintainer approval and environment configuration.
- Adoption evidence exists for greenfield, brownfield, Architext, security scan,
  and README-only stranger simulation. Most evidence records remain Draft and
  require reviewer acceptance or status promotion before public launch claims.
- AIDHA exposed a dogfooding hygiene issue: rebuildable `.meminit/cache/` data
  triggered detect-secrets false positives when staged. The product and AIDHA
  test repo now treat `.meminit/cache/` and `.meminit.lock` as ignored runtime
  state.
- P2 architecture refactoring is intentionally deferred to MEMINIT-TASK-002. It
  remains important for maintainability, but it is not a launch gate for this
  adoption sequence.

<!-- MEMINIT_SECTION: decision -->

## 2. Decision

Validate Meminit through dogfooding before any promoted public package launch.
Treat PyPI publish, release notes, README/storefront polish, and public
promotion as one launch event gated by evidence, not as independent checklist
items that can drift apart.

Rejected alternative: publish immediately because installability compounds.
That is only true when the package already has reachable adopters or a proven
golden path. For Meminit's current state, an installable but under-validated
package mainly creates a weak first impression and a larger support surface.

Important distinction:

- Local editable install and git install are acceptable for dogfooding.
- Build artifacts and TestPyPI are acceptable for release-engineering rehearsal.
- Testing and building should be performed using `uv`, which is our standardized environment manager.
- Production PyPI publish is launch-surface work and should wait for the gate in
  Section 8.
- Public promotion should not happen separately from the production package
  becoming installable.

<!-- MEMINIT_SECTION: architecture -->

## 3. Adoption Architecture

The adoption system has five cooperating surfaces. Each must stay independently
testable and loosely coupled.

| Surface           | Responsibility                                                                                       | Launch-quality contract                                                                                                              |
| ----------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| CLI core          | `init`, `context`, `new`, `scan`, `fix`, `check`, `index`, `resolve`, `identify`, `link`, `protocol` | Deterministic output, repo-root safety, no runtime network dependency, strict v3 JSON envelope compliance (`check_all_envelopes.py`) |
| Template system   | Type-specific document scaffolds and section inventory                                               | No skeleton fallback for launch-critical types; section markers and agent prompts are parseable                                      |
| Protocol assets   | `AGENTS.md`, `meminit-docops` skill, brownfield helper script                                        | Registry-owned canonical content, drift detection, safe sync, no stale `.codex`/`.agents` contradiction                              |
| Adoption evidence | Logs, command transcripts, defect list, closure notes                                                | Every dogfood repo has baseline, fixes, final check, and residual-risk notes                                                         |
| Release surface   | README, packaging metadata, tag workflow, release notes, PyPI page                                   | Install commands work from a clean environment and match documented support boundaries                                               |

Engineering guidance:

- Keep Meminit as a small Unix-like CLI. Do not add dashboard, IDE, or hosted
  service dependencies to solve launch blockers.
- Prefer shared services for path safety, JSON envelopes, protocol assets,
  template resolution, and index writes. Do not duplicate command-specific
  parsers or filesystem rules.
- Any behavioral hardening found through dogfooding must land as Code +
  Documentation + Tests in the same PR.
- Do not create a new PRD/spec for every dogfooding defect. Use this plan, a
  governed LOG evidence record, and narrow implementation tasks unless the defect
  changes a cross-cutting contract.

<!-- MEMINIT_SECTION: sequence -->

## 4. Execution Sequence

### Phase 0 - Baseline and Instrumentation

Goal: create a clean measurement point before changing adoption behavior.

- Run `uv run meminit context --format json`, `uv run meminit doctor --format json`,
  `uv run meminit check --format json`, and `uv run pytest -q` in this repo.
- Run `uv run python check_all_envelopes.py` to ensure all endpoints emit valid v3 JSON payloads.
- Run `uv run pre-commit run --all-files` to baseline code hygiene.
- Run `uv run meminit protocol check --format json` to confirm protocol asset state.
- Record current template coverage with `uv run meminit new --list-types --format json`
  and a file inventory of `docs/00-governance/templates/` plus packaged
  templates.
- Create or update a governed LOG record for dogfooding evidence. Use `uv run meminit
new LOG ... --format json`; do not hand-roll metadata.

Exit criteria:

- Baseline commands and their pass/fail status are captured.
- Known pre-existing failures are classified as blockers, accepted residual
  risk, or out of scope.
- The evidence record links back to MEMINIT-PLAN-016 by document ID.

### Phase 1 - Greenfield Adoption

Goal: prove the cold-start experience.

Target: `../bedtime-alexa/` or another genuinely low-history greenfield repo.

Required scenario:

```bash
uv venv
uv pip install -e ../Meminit # Or path to local source/sdist
uv run meminit init --root . --format json
uv run meminit context --root . --format json
uv run meminit new ADR "Use Meminit for governed docs" --root . --format json
uv run meminit check --root . --format json
uv run meminit index --root . --format json
uv run meminit resolve <CREATED_DOCUMENT_ID> --root . --format json
```

Exit criteria:

- A new user can run the README quickstart without private maintainer context.
- The generated `AGENTS.md`, templates, schema, and skill assets are coherent.
- The repo reaches zero DocOps violations without manual metadata surgery.
- Any generated placeholder owner or metadata value is either absent or
  documented as a deliberate migration placeholder with clear remediation.

### Phase 2 - Brownfield Adoption

Goal: prove migration from imperfect existing docs.

Target: one messy repo with ad-hoc docs, selected for highest migration signal
from RevRem, QualFreq, LeClerc, or an equivalent local repo.

Required scenario (after installing Meminit via `uv`):

```bash
uv run meminit scan --root . --format json
uv run meminit scan --root . --plan .meminit/adoption-plan.json --format json
uv run meminit fix --root . --plan .meminit/adoption-plan.json --format json
uv run meminit fix --root . --plan .meminit/adoption-plan.json --no-dry-run --format json
uv run meminit check --root . --format json
uv run meminit index --root . --format json
```

Exit criteria:

- Dry-run output is understandable enough for an agent or maintainer to approve.
- Applied changes are deterministic and reviewable.
- No deletes occur unless a future explicit delete feature is designed and
  approved.
- Link validation failures are either fixed or captured as explicit migration
  backlog with document IDs and paths.

### Phase 3 - Architext Pilot

Goal: prove the agent-orchestrator design center from
[MEMINIT-STRAT-001](../02-strategy/strat-001-project-meminit-vision.md).

Required scenario:

- Pin Meminit to a commit SHA or exact tag; never float `main` in pilot CI.
- Run `init`, `context`, `new`, `check`, `index`, `resolve`, and protocol
  checks from Architext automation or an agent-driven script via `uv run meminit`.
- Verify section-ID and template behavior against Architext's document
  archetypes.

Exit criteria:

- Architext can consume Meminit outputs without heading-regex heuristics or
  undocumented file reads.
- Section markers, template provenance, and index artifacts are sufficient for
  the orchestrator workflow.
- Any Architext-specific customization is represented as config or templates,
  not hardcoded into Meminit core.

### Phase 4 - Launch Hardening

Goal: close defects from Phases 1-3 and remove avoidable first-impression risk.

Required work:

- Expand launch-critical templates or explicitly narrow the launch claim.
- Reconcile `.agents` versus `.codex` wording across README, runbooks, bundled
  skill, tests, and protocol assets. Add a lint/grep check in CI to prevent regressions.
- Add tag-triggered release automation for build (`uv build`), test, package validation, and
  publish dry-run.
- Run `uv run pre-commit run --all-files` to ensure all formatting and linting rules are strictly enforced.
- Run the full local verification matrix in Section 9 and capture results.

Exit criteria:

- All Section 8 gates are satisfied.
- Release notes identify supported commands, unsupported surfaces, and known
  limitations.
- Promotion copy points to tested workflows only.

<!-- MEMINIT_SECTION: workstreams -->

## 5. Engineering Workstreams

| ID   | Workstream                   | Primary files                                                                         | Required tests                                                                 | Done when                                                      |
| ---- | ---------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| WS-1 | Greenfield golden path       | `src/meminit/core/use_cases/init_repository.py`, `new_document.py`, templates, README | init/new/check/index use-case tests and `scripts/e2e_integration_test.py`      | Clean repo reaches first green from documented commands        |
| WS-2 | Brownfield migration         | `scan_repository.py`, `fix_repository.py`, `migrate_ids.py`, link checker             | plan-driven migration, dry-run/apply parity, idempotence tests                 | Messy repo reaches green or emits actionable residuals         |
| WS-3 | Template breadth             | `docs/00-governance/templates/`, packaged template assets, `template_resolver.py`     | resolver, interpolation, section parser, `meminit new` JSON tests              | Launch-critical types avoid skeleton fallback                  |
| WS-4 | Protocol and skill packaging | `protocol_assets.py`, `.agents/skills/meminit-docops/`, README, runbooks              | protocol check/sync tests, init asset tests, skill manifest tests              | Canonical skill path and generated assets agree everywhere     |
| WS-5 | Release engineering          | `.github/workflows/`, `pyproject.toml`, README, release notes                         | package build (`uv build`), install smoke, CI workflow dry-run where practical | Tag workflow can build and validate the package before publish |
| WS-6 | Security and public hygiene  | `LICENSE`, `NOTICE` if needed, `SECURITY.md`, docs/security guidance                  | secret scan output or documented manual scan, packaging metadata check         | No known secrets/PII or license mismatch before launch         |

Ownership rule: each workstream PR must update the relevant governed doc,
implementation, and tests together. Documentation-only exceptions are allowed
only for this plan, evidence LOGs, or release notes that do not alter behavior.

<!-- MEMINIT_SECTION: dogfooding_scope -->

## 6. Dogfooding Scope

Use a small portfolio for signal diversity instead of trying every maintainer
repo.

| Repo                                                | Why it matters                                   | Required signal                                                         |
| --------------------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------- |
| Greenfield repo (`../bedtime-alexa/` or equivalent) | Tests cold-start ergonomics and generated assets | No private context needed; README quickstart works                      |
| Architext                                           | Tests the agent-orchestrator design center       | Section IDs, templates, and index artifacts support orchestration       |
| Messy brownfield repo                               | Tests migration and defect reporting             | `scan -> plan -> fix -> check` is understandable and deterministic      |
| AIDHA                                               | Ongoing continuous testbed                       | Regression signal only; do not substitute for the three targeted pilots |

Over-fitting guard: after the README quickstart is updated, run a stranger
simulation where an agent starts from the README and runbooks only. The agent
must not receive hidden maintainer instructions beyond the repository's
committed docs and generated command output.

<!-- MEMINIT_SECTION: evidence_model -->

## 7. Evidence Model

Each dogfood run must produce an evidence packet with:

- target repo name, commit SHA, operating system, Python version, and Meminit
  version or commit SHA;
- exact command list;
- JSON or NDJSON output artifacts for failing commands and final passing gates;
- defect list with classification: product bug, docs bug, test gap, repo-specific
  migration issue, or accepted residual risk;
- closure link to the PR or commit that fixed each product bug;
- final verdict: pass, pass with residuals, or fail.

Store durable evidence in a governed LOG document under `docs/58-logs/`. Large
raw outputs may live in ignored local artifacts or CI logs, but the governed LOG
must contain enough summary detail for a reviewer to audit the decision without
rerunning everything.

<!-- MEMINIT_SECTION: launch_gate -->

## 8. Launch Gate Checklist

Implementation evidence is captured for every launch gate below. Publish and
promote only after peer reviewers accept the evidence, including whether Draft
evidence records are sufficient or must be promoted first.

- [x] This repo passes `uv run meminit doctor --format json`,
      `uv run meminit check --format json`,
      `uv run meminit protocol check --format json`, and `uv run pytest -q`.
      Evidence: local verification, protocol assets 3/3 aligned, full default pytest
      passing with opt-in slow/benchmark skips.
- [x] This repo passes `uv run python check_all_envelopes.py` and
      `uv run pre-commit run --all-files`. Evidence: completion log in
      [MEMINIT-TASK-001](tasks/task-001-plan-016-qa-remediation.md).
- [x] Greenfield adoption reaches first green from documented commands.
      Evidence: [MEMINIT-LOG-002](../58-logs/log-002-dogfooding-sequencing-evidence.md)
      (Draft).
- [x] Brownfield adoption validates `scan -> plan -> dry-run -> apply -> check`
      on one messy repo. Evidence:
      [MEMINIT-LOG-002](../58-logs/log-002-dogfooding-sequencing-evidence.md)
      (Draft).
- [x] Architext pilot validates the orchestrator-facing contract with Meminit
      pinned to an exact tag or commit. Evidence:
      [MEMINIT-LOG-003](../58-logs/log-003-architext-pilot-evidence.md) (Draft;
      pinned to f2dee7ba51696470d2c9c224ef244bcf9b72e5a5).
- [x] Launch-critical templates exist for ADR, PRD, FDD, PLAN, SPEC, RUNBOOK,
      DESIGN, LOG, and TASK; malformed placeholder regressions are covered by tests.
- [x] `meminit-docops` skill docs, protocol asset registry, README, runbooks, and
      tests agree on the canonical scaffolded path
      (`.agents/skills/meminit-docops`).
- [x] README quickstart passes the stranger simulation from a clean checkout.
      Evidence:
      [MEMINIT-LOG-005](../58-logs/log-005-stranger-simulation-evidence.md)
      (Draft).
- [x] Tag-triggered release workflow builds sdist/wheel using `uv build`, runs
      tests, validates metadata, and supports a dry-run publish path before
      production PyPI.
- [x] Security and public hygiene gate from
      [MEMINIT-GOV-003](../00-governance/gov-003-security-practices.md) is complete,
      including secrets/PII scan evidence. Evidence:
      [MEMINIT-LOG-004](../58-logs/log-004-security-scan-evidence.md) (Approved,
      gitleaks v8.18.4 verified).
- [x] Release notes state supported commands, known limitations, and the pre-1.0
      compatibility policy. Evidence:
      [MEMINIT-DEVEX-001](../70-devex/devex-001-release-notes.md) (Draft).

Additional dogfooding hygiene: AIDHA now ignores `.meminit/cache/` and
`.meminit.lock`, removes generated cache files from the git index, and passes
`pre-commit run detect-secrets --all-files`.

<!-- MEMINIT_SECTION: verification_matrix -->

## 9. Verification Matrix

Minimum local verification before a launch-candidate PR:

```bash
uv run pre-commit run --all-files
uv run meminit context --format json
uv run meminit doctor --format json
uv run meminit check --format json
uv run meminit protocol check --format json
uv run python scripts/e2e_integration_test.py
uv run python check_all_envelopes.py
uv run pytest -q
```

Focused verification when workstream code changes:

| Change area          | Additional checks                                                                                                                                                                                         |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Templates            | `uv run pytest -q tests/core/services/test_template_resolver.py tests/core/services/test_section_parser.py tests/core/use_cases/test_new_document.py`                                                     |
| Protocol assets      | `uv run pytest -q tests/core/services/test_protocol_assets.py tests/core/use_cases/test_protocol_check.py tests/core/use_cases/test_protocol_sync.py tests/core/use_cases/test_init_repository_assets.py` |
| Brownfield migration | `uv run pytest -q tests/core/use_cases/test_scan_repository.py tests/core/use_cases/test_plan_driven_migration.py tests/core/use_cases/test_fix_repository.py tests/core/use_cases/test_migrate_ids.py`   |
| Index and resolution | `uv run pytest -q tests/core/use_cases/test_index_repository.py tests/core/use_cases/test_resolve_identify.py tests/integration/test_index_schema.py`                                                     |
| CLI output contract  | `uv run pytest -q tests/adapters/test_cli.py tests/core/services/test_output_contract_schema.py tests/integration/test_contract_matrix.py` AND `uv run python check_all_envelopes.py`                     |
| Release packaging    | build sdist/wheel (`uv build`), install into a clean virtualenv, run `meminit --version`, `meminit doctor --format json`, and `meminit check --format json`                                               |

Test design requirements:

- Golden-path tests must assert both success and useful failure diagnostics.
- Migration tests must cover dry-run/apply parity and idempotence.
- JSON-mode tests must verify exactly one JSON object on STDOUT.
- Any NDJSON test must verify terminal `summary` or `error` records.
- Filesystem tests must use temporary repos and avoid network access.

<!-- MEMINIT_SECTION: risk_management -->

## 10. Risks and Mitigations

| Risk                                                 | Impact                                            | Mitigation                                                                                                                      |
| ---------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Dogfooding only maintainer repos overfits the UX     | Launch looks good locally but fails for strangers | Use greenfield, messy brownfield, Architext, and README-only stranger simulation                                                |
| Template breadth expands into a large design project | Launch slips into open-ended polish               | Define launch-critical types and defer non-critical archetype refinement                                                        |
| Skill path drift confuses agents                     | Generated instructions become untrustworthy       | Make protocol assets and tests the source of truth; reconcile docs before launch, add CI linting for legacy `.codex` references |
| PyPI publish happens without promotion readiness     | Weak storefront creates early bounce              | Couple production PyPI with release notes, README, and evidence gate                                                            |
| Release automation adds supply-chain risk            | Bad package or accidental secret exposure         | Use least-privilege workflow permissions, build validation (`uv`), exact tags, and security scan                                |
| Spec writing resumes instead of adoption fixes       | Product remains impressive but unused             | Freeze net-new specs unless a dogfood defect changes a cross-cutting contract                                                   |

<!-- MEMINIT_SECTION: deferred -->

## 11. Explicitly Deferred

- VS Code extension and web dashboard: defer until CLI adoption demand is proven.
- TypeScript implementation: defer; it doubles the maintenance surface for no
  launch-critical adoption signal.
- Semantic search/RAG expansion: defer until deterministic index and adoption
  evidence justify depth beyond current artifacts.
- Public ecosystem plugins beyond the scaffolded `meminit-docops` skill: defer
  until the bundled skill path and protocol sync are proven.
- Net-new broad PRDs/specs: frozen unless they resolve a dogfooding blocker that
  cannot be captured as a narrow task or evidence note.

<!-- MEMINIT_SECTION: handover -->

## 12. Handover Requirements

This plan is ready for peer review and engineering/testing handover when the
review packet includes:

- this plan and the current evidence LOG document ID;
- the target repo list and exact commits used for dogfooding;
- the workstream owner/scope table from Section 5 with current status;
- commands run, outputs captured, and residual risks accepted;
- a PR checklist proving Code + Documentation + Tests stayed aligned;
- rollback guidance for release workflow changes and package publication;
- a list of docs updated or intentionally left stale with rationale.

Peer review tracks:

| Track            | Reviewer focus                                                                                          |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| QA               | Rerun the Section 9 matrix and verify LOG evidence for greenfield, brownfield, Architext, and stranger  |
| Security/release | Verify MEMINIT-GOV-003, MEMINIT-LOG-004, release workflow gates, and scanner exclusions                 |
| Docs/devex       | Confirm README, runbooks, release notes, and supported-command claims agree                             |
| Architecture     | Confirm P2 deferral to MEMINIT-TASK-002 is acceptable for launch and has actionable acceptance criteria |

Testing teams should reject a handover that only says "green locally" without
command output, target repo commits, defect closure evidence, and reviewer
sign-off or accepted-risk notes.

<!-- MEMINIT_SECTION: agent_notes -->

## 13. Notes for Agents

- Preserve `document_id: MEMINIT-PLAN-016`. The ID is immutable.
- Do not promote this document to `Approved` without explicit maintainer
  instruction.
- Reference governed docs by document ID in prose and use relative links only
  when the target exists.
- Start a session with `uv run meminit context --format json`; do not hardcode type
  directories or prefixes.
- Use the repo-scoped `meminit-docops` skill for DocOps workflows.
- Treat `meminit check` as structural compliance, not semantic proof that launch
  readiness is true.
- When changing launch behavior, update code, tests, README/runbooks, and
  governed docs in the same PR.
