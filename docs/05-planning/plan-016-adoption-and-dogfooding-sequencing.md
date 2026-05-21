---
document_id: MEMINIT-PLAN-016
type: PLAN
title: Adoption and Dogfooding Sequencing
status: Draft
version: '0.1'
last_updated: '2026-05-20'
owner: GitCmurf
docops_version: '2.0'
area: STRATEGY
description: Re-sequences Meminit delivery around dogfood-first validation before
  public distribution; gates the one-shot public launch on quality.
related_ids:
- MEMINIT-PLAN-003
- MEMINIT-STRAT-001
---

> **Document ID:** MEMINIT-PLAN-016
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-05-20
> **Type:** PLAN
> **Area:** STRATEGY
> **Description:** Re-sequences Meminit delivery around dogfood-first validation before public distribution; gates the one-shot public launch on quality.

# PLAN: Adoption and Dogfooding Sequencing

This plan re-sequences near-term delivery. It is subordinate to
[MEMINIT-PLAN-003](plan-003-roadmap.md) as the sequencing source of truth and to
[MEMINIT-STRAT-001](../02-strategy/strat-001-project-meminit-vision.md) for
constraints. Where this plan and PLAN-003 disagree on near-term ordering, this
plan is the more recent decision (2026-05-20) and should be reconciled into
PLAN-003.

## 1. Context & Diagnosis

<!-- MEMINIT_SECTION: context -->

Meminit has deep internal engineering and near-zero distribution. Shipped: v3
JSON envelope, NDJSON streaming, project-state work-queue, protocol governance,
contract-matrix tests; all tech debt (TD-001..009) closed. Not shipped: a PyPI
release (git-install only), release automation, or any external adopters. The
spec/plan corpus (PRD-006 ~3,900 lines; PLAN-008..015; 8 PRDs) far outweighs the
adoption surface.

Two facts drive the re-sequencing:

- **There is exactly one user — the maintainer.** For a one-user tool the binding
  constraint is *validation*, not *distribution*.
- **The first public impression is one-shot.** A too-pre-alpha public release (or
  even an unpromoted-but-sparse PyPI page, which still reads as a storefront)
  causes early adopters to bounce permanently.

## 2. Decision

<!-- MEMINIT_SECTION: decision -->

**Validate by dogfooding the maintainer's own repos before any public
distribution. Treat publish + promotion as a single, quality-gated launch
event — not an early button-press.**

- **Alternative rejected — "PyPI-first":** publish v0.2.0 immediately because
  "nothing compounds until it's installable." Rejected because that logic assumes
  reachable external adopters, which do not exist yet. With one user, an
  installable-but-unvalidated package buys nothing and risks the one-shot
  impression.
- **Decoupling:** the *mechanical* act of `pip install` existing is reversible;
  *promotion* (HN/Show/marketplace/social) is not. Since dogfooding needs no PyPI
  (editable/git install suffices), there is no cost to deferring the publish until
  the storefront is good.
- **Guard:** the launch gate is a **checklist (Section 5), not a feeling** —
  "defer PyPI" must not become "polish forever."

## 3. Sequence

<!-- MEMINIT_SECTION: sequence -->

0. **Dogfood** real repos (Section 4).
1. **Harden** the golden path (`init → new → check`) and the bundled agent skill
   from what actually breaks; fill template breadth (Section 6) as gaps surface.
2. **Launch**: PyPI publish + tag-triggered release workflow + promotion, as one
   deliberate event, only when Section 5 is satisfied.

## 4. Dogfooding Scope

<!-- MEMINIT_SECTION: dogfooding_scope -->

Pick ~3 repos for signal diversity, not all of them (solo-dev bandwidth):

- **1 greenfield** repo — cleanest test of `init` → golden path (cold start, no
  muscle memory). First run: `../bedtime-alexa/`.
- **Architext** — the sibling project whose archetype / section-ID alignment is
  baked into the vision; tests the hardest integration claim, not just the happy
  path.
- **1 messy brownfield** (RevRem / QualFreq / LeClerc — whichever has the most
  ad-hoc existing docs) — stresses `scan` / `fix` / `migrate-ids`.

AIDHA is already a continuous testbed. HypoGraph and the remainder add little new
signal until the first three teach us something.

**Over-fitting guard:** dogfooding only the maintainer's repos bakes in the
maintainer's assumptions. Mitigants: (a) include the true greenfield repo above;
(b) once the README quickstart exists, have an agent drive a cold run **from the
README alone**, no maintainer help — a stranger simulation.

**Discipline:** capture failures as a lightweight running fix-list fed straight
into fixes — **not** a new PRD/spec. See Section 7.

## 5. Launch Gate Checklist

<!-- MEMINIT_SECTION: launch_gate -->

Publish + promote only when all are true:

- [ ] Greenfield `init → new → check` runs clean and reads well (validated on
      `../bedtime-alexa/`).
- [ ] Brownfield `scan → fix → check` validated on at least one messy repo.
- [ ] Architext adoption validated (archetype / section-ID alignment holds).
- [ ] Built-in templates exist for all first-class types (no skeleton fallback for
      ADR/PRD/FDD/SPEC/RUNBOOK/PLAN/DESIGN at minimum).
- [ ] Bundled agent skill is current with the v3 contract and scaffolds cleanly.
- [ ] README quickstart passes the stranger-simulation cold run.
- [ ] Tag-triggered `release.yml` exists and a dry-run build succeeds.

## 6. AI-First Template Implication

<!-- MEMINIT_SECTION: template_implication -->

Meminit docs are AI-first: agents draft and consume them; humans read and lightly
edit, never draft. Consequences for template work:

- Do **not** lean templates out for "human blank-page friction" — no human faces
  the blank page.
- Optimize for machine-fill reliability: every section needs a stable
  `<!-- MEMINIT_SECTION: id -->` marker, an `<!-- AGENT: ... -->` prompt, a
  `required` flag, and `initial_content`, all surfaced in `meminit new --format
  json`.
- The real gap is **breadth**: today only ADR/PRD/FDD have built-ins; PLAN (this
  document included), SPEC, RUNBOOK, DESIGN, etc. fall back to a markerless
  skeleton that is *not* machine-fillable. Closing this is a launch-gate item.

## 7. Skill Packaging: One Artifact, Two Channels

<!-- MEMINIT_SECTION: skill_packaging -->

There is one canonical `meminit-docops` skill with two distribution channels:

- **Bundled + scaffolded** into adopter repos by `meminit init` (their
  `.codex` / `.agents` / `.claude`). Do this channel well first.
- **Published** to agent ecosystems (Claude Code plugin, etc.) so an agent that
  has never seen the repo can discover and load it. Optional polish; extra
  maintenance surface for a solo maintainer.

## 8. Explicitly Deferred

<!-- MEMINIT_SECTION: deferred -->

- VS Code extension / web dashboard (PRD-007) — defer until demand is proven.
- TypeScript parallel implementation — doubles surface for a solo maintainer with
  zero new users.
- Semantic search / RAG (Phase 4) — depth on an engine nobody uses yet.
- **Net-new spec/plan depth — frozen** until adopters exist whose feedback
  prioritizes for us. This is the project's primary failure mode.

## 9. Notes for Agents

<!-- MEMINIT_SECTION: agent_notes -->

- This plan was itself produced by dogfooding `meminit new PLAN`, which fell back
  to a markerless skeleton (`template.applied: false`, `source: none`) — direct
  evidence for Section 6.
- Code anchors: `src/meminit/core/services/template_resolver.py`,
  `src/meminit/core/assets/org_profiles/default/templates/` (only adr/prd/fdd).
- Reconcile near-term ordering in `MEMINIT-PLAN-003` against this plan's
  Section 3.
