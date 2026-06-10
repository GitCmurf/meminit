---
document_id: MEMINIT-TASK-005
type: TASK
title: PLAN-016 launch-gate closure
status: Draft
version: "0.4"
last_updated: "2026-06-10"
owner: GitCmurf
area: PLAN
docops_version: "2.0"
template_type: task-standard
template_version: "2.0"
description:
  "Track remaining PLAN-016 launch-gate actions: maintainer promotions
  (evidence LOGs, plan, PyPI) and record completed formatter/lint remediation."
keywords:
  - task
related_ids:
  - MEMINIT-PLAN-016
---

> **Document ID:** MEMINIT-TASK-005
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.4
> **Last Updated:** 2026-06-10
> **Type:** TASK
> **Area:** PLAN
> **Description:** Track remaining PLAN-016 launch-gate actions: maintainer promotions (evidence LOGs, plan, PyPI) and record completed formatter/lint remediation.

<!-- MEMINIT_SECTION: title -->
<!-- AGENT: The title should state the implementation objective clearly. -->

# TASK: PLAN-016 launch-gate closure

<!-- MEMINIT_SECTION: executive_summary -->
<!-- AGENT: Summarize the task, why it exists, and the intended completion state. -->

## 0. Executive Summary

[MEMINIT-PLAN-016](../plan-016-adoption-and-dogfooding-sequencing.md) §8 marks every
launch gate as having implementation evidence, but explicitly conditions publish/promote on
peer-review acceptance. Evidence and plan promotion are now accepted; the remaining closure
action is the production PyPI publish. This task captures the release handoff, plus records
the completed formatter/managed-artifact and `.codex`-lint remediation as closed evidence.
The first `v0.3.0a1` release trigger exposed installed-package verification bugs; this task
now also records the release workflow and version-discovery remediation.
The follow-up `v0.3.0a2` release trigger passed build and installed-wheel verification, then
stopped at TestPyPI trusted-publisher configuration.
**Definition of done:** production PyPI publish completes, public installation guidance is
updated if needed, and this task no longer surfaces from `meminit state next`.

<!-- MEMINIT_SECTION: review_basis -->
<!-- AGENT: List source reports, live commands, and evidence used to scope the task. -->

## 1. Review Basis

- [MEMINIT-PLAN-016](../plan-016-adoption-and-dogfooding-sequencing.md) §8 (Launch Gate
  Checklist) and §12 (Handover) — gates are engineering-complete and peer-reviewed.
- A completeness review of PLAN-016 against the live repo (2026-06-04) that found: the
  `meminit protocol check` regression (Prettier reformatting the hash-locked `AGENTS.md`
  managed block), the `README.md` legacy skill-path reference, and 4 evidence records plus
  the plan still in Draft.
- The formatter/managed-artifact remediation landed in the same session (`.prettierignore`,
  `meminit init` scaffolding, `.codex`-lint extension); recorded here as closure evidence.

<!-- MEMINIT_SECTION: current_state -->
<!-- AGENT: Distinguish live defects from stale or already-corrected findings. -->

## 2. Current State

**Done (engineering, with evidence) — this session:**

- Formatter ↔ Meminit-managed-artifact conflict resolved by disjoint ownership: repo
  `.prettierignore` added; `meminit init` scaffolds an idempotent `.prettierignore` into
  adopter repos (reusing the protocol-asset registry). `AGENTS.md` restored →
  `meminit protocol check` 3/3 aligned; `meminit.index.json` regenerated to the deterministic
  generator form.
- `README.md` legacy skill path → `.agents/skills/meminit-docops/`.
- `.codex` lint (`tests/test_legacy_path_lint.py`) extended to scan root Markdown (it
  previously covered only `src/` and `docs/`, so `README` escaped it).

**Done (maintainer/reviewer):**

- Evidence records LOG-002, LOG-003, LOG-005, DEVEX-001 and PLAN-016 are promoted to
  Approved after launch-gate review.

**Remaining (release execution):**

- Production PyPI publish + public promotion not done (gated on maintainer approval; §2/§8).
- First `v0.3.0a1` release workflow run failed before TestPyPI because it ran the
  installed-package pytest suite from a temp directory, breaking repo-relative fixture
  tests. The workflow now runs pytest from `GITHUB_WORKSPACE` with `-c /dev/null` so
  repo fixtures exist while the checkout `pythonpath` setting remains disabled.
- The same installed-package path also proved the source-tree version fallback should
  consider the current working tree when package metadata is unavailable, while rejecting
  unrelated `pyproject.toml` files whose `project.name` is not `meminit`.
- Because the `v0.3.0a1` tag has already triggered a failed GitHub Actions run, release
  execution should continue with `v0.3.0a2` rather than rewriting the pushed tag.
- `v0.3.0a2` release run 27285356168 passed Build and Verify Packages, including package
  metadata validation and installed-wheel pytest. It failed in Publish to TestPyPI (Staging)
  because TestPyPI returned `invalid-publisher`: no trusted publisher matches the GitHub OIDC
  claims for repo `GitCmurf/meminit`, workflow `release.yml`, environment `testpypi`.

<!-- MEMINIT_SECTION: work_items -->
<!-- AGENT: Break the work into prioritized, implementable items with definitions of done. -->

## 3. Work Items

| ID   | Owner                | Work item                                                                                                                                                   | Definition of done                                                                                        |
| ---- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| WI-1 | Done                 | Peer-review and promote evidence LOGs LOG-002 (greenfield), LOG-003 (Architext), LOG-005 (stranger) Draft → Approved                                        | LOG-002, LOG-003, and LOG-005 are Approved                                                                |
| WI-2 | Done                 | Peer-review and promote DEVEX-001 (release notes) Draft → Approved                                                                                          | DEVEX-001 is Approved and matches supported commands/limitations                                          |
| WI-3 | Done                 | Promote PLAN-016 Draft → Approved                                                                                                                           | PLAN-016 §8 gates accepted; `status: Approved` set under maintainer instruction                           |
| WI-4 | Maintainer/Release   | Production PyPI publish + public promotion as one gated event                                                                                               | `release.yml` run to production after TestPyPI rehearsal; README/promotion point only to tested workflows |
| WI-5 | Done (evidence)      | Formatter/managed-artifact disjoint ownership (`.prettierignore` repo + `init` scaffolding); `README` `.codex` fix; `.codex` lint extended to root Markdown | Triple-green verified (see §4); adopter simulation passes; recorded as closed                             |
| WI-6 | Optional (recommend) | ADR for the disjoint-ownership decision ("formatter-managed vs Meminit-managed files"), consistent with ADR-017                                             | ADR authored and accepted, or explicitly declined with rationale                                          |

<!-- MEMINIT_SECTION: verification_matrix -->
<!-- AGENT: List the exact commands and evidence required before closure. -->

## 4. Verification Matrix

WI-5 (done) is verified by the "triple-green" acceptance test — all must pass on the same tree:

```bash
uv run pre-commit run --all-files                     # all hooks Pass (Prettier skips managed files)
uv run meminit protocol check --format json           # 3/3 aligned, 0 drifted
uv run meminit index --root . && \
  git diff --exit-code docs/01-indices/meminit.index.json   # no diff (committed == generator output)
uv run pytest -q                                       # green (extended legacy-path lint + init .prettierignore tests)
```

Adopter simulation (proves the `init` scaffolding):

```bash
TMP=$(mktemp -d); uv run meminit init --root "$TMP" --format json
( cd "$TMP" && npx --yes prettier@3.1.0 --write . )   # AGENTS.md must be unchanged
uv run meminit protocol check --root "$TMP" --format json   # 3/3 aligned
```

WI-1..WI-3 are closed by governed document promotion. WI-4 remains accepted by the named
maintainer/release owner and must close only after the release workflow completes.

<!-- MEMINIT_SECTION: version_history -->
<!-- AGENT: Track version changes with dates, authors, and change summaries. -->

## 5. Version History

| Version | Date       | Author   | Changes                                                                                                          |
| ------- | ---------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| 0.4     | 2026-06-10 | GitCmurf | Recorded v0.3.0a2 build/verify success and TestPyPI trusted-publisher blocker                                    |
| 0.3     | 2026-06-10 | GitCmurf | Recorded failed release trigger and fixed installed-package workflow/version fallback verification               |
| 0.2     | 2026-06-10 | GitCmurf | Closed WI-1..WI-3 through evidence, release notes, and PLAN-016 approval; WI-4 remains pending release execution |
| 0.1     | 2026-06-04 | GitCmurf | Initial draft                                                                                                    |
