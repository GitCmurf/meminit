# PRD: Meminit Greenfield Setup vNext

## Framing

**Interpretation:** this is a product/engineering PRD for the **greenfield bootstrap experience** of Meminit in a new repository, not just a repo review or a list of setup tasks.  
**Confidence:** high.

## Repository review: what exists now, and what is missing

The current repo already contains the core ingredients of a greenfield initializer:

- `README.md` positions Meminit as a CLI that scaffolds governed docs, `AGENTS.md`, compliance checks, pre-commit hooks, and CI support. fileciteturn5file0L1-L1
- `InitRepositoryUseCase` creates a substantial `docs/` tree, `docops.config.yaml`, schema, templates, protocol assets, and a governance constitution. fileciteturn20file0L1-L1
- tests verify idempotent init, protocol-marked `AGENTS.md`, installation of a generated skill, and an executable brownfield helper script. fileciteturn21file0L1-L1
- the repo has a **protocol asset registry** with mixed/generated ownership and drift classification (`aligned`, `missing`, `legacy`, `stale`, `tampered`, `unparseable`). fileciteturn18file0L1-L1 fileciteturn19file0L1-L1
- the current CI and pre-commit setups are functional but still baseline rather than “highest-quality greenfield”. `.github/workflows/ci.yml` has a minimal two-job pipeline, and `.pre-commit-config.yaml` enforces a narrow hook set. fileciteturn8file0L1-L1 fileciteturn9file0L1-L1

The main product problem is not absence of machinery. It is **incomplete normalization of the setup contract**:

1. **Protocol surface drift:** the repo’s actual generated skill path is `.agents/skills/...`, but `README.md`, `AGENTS.md`, and the Codex runbook still describe `.codex/skills/...` as if it were canonical. fileciteturn10file0L1-L1 fileciteturn13file0L1-L1 fileciteturn22file0L1-L1
2. **Toolchain drift:** `pyproject.toml`, CI, and `CONTRIBUTING.md` imply slightly different lint/test/tool expectations. fileciteturn6file0L1-L1 fileciteturn8file0L1-L1 fileciteturn25file0L1-L1
3. **Greenfield scope ambiguity:** current `init` installs some protocol assets, but the product boundary between “core DocOps bootstrap”, “agent protocol files”, “pre-commit”, “CI/CD”, “GitHub hygiene”, and “tool-specific projections” is not yet sharply defined. fileciteturn15file0L1-L1

That means the right next step is not “add more files”. It is to turn greenfield setup into a **first-class configurable product surface**.

---

## PRD

### 1. Title

**Meminit Greenfield Setup vNext**

### 2. Status

Draft

### 3. Owner

Meminit maintainers

### 4. Summary

Meminit shall provide a **high-quality, idempotent, configurable greenfield bootstrap** for new repositories. The bootstrap shall create a governed documentation foundation, install protocol assets for AI agents, configure local quality gates and CI/CD, and emit a machine-readable manifest of what was installed.

The bootstrap shall support **user-selectable setup profiles** and **targeted protocol options**, especially for:

- `AGENTS.md` managed sections
- vendor-neutral and tool-specific skill assets
- pre-commit hooks
- CI/CD workflows
- optional repository governance files and GitHub hygiene assets

The resulting repository shall be **usable immediately**, **safe to re-run**, **drift-detectable**, and **upgradeable without clobbering user-authored content**.

### 5. Problem statement

Today Meminit can initialize a repo, but the greenfield experience is still closer to “scaffolding plus conventions” than to a **production-grade setup product**.

That creates five concrete problems:

1. **Ambiguous canonical paths.** The system mixes vendor-neutral and tool-specific protocol paths, which creates documentation drift and upgrade friction.
2. **Inconsistent setup outcomes.** There is no single explicit contract for which optional assets are installed under which profile.
3. **Weak quality-gate bundling.** Pre-commit, CI, protocol drift checking, and packaging smoke tests are not yet composed into a coherent bootstrap standard.
4. **Poor update semantics.** Without explicit ownership and projection rules, future updates risk either clobbering user edits or leaving stale generated assets in place.
5. **Under-specified greenfield UX.** A new user cannot easily choose between minimal, standard, strict, OSS, internal, or agent-heavy setups in a deterministic way.

### 6. Product thesis

**Opinion, high confidence:** the correct abstraction is **not** “write an AGENTS file and a skills directory”. The correct abstraction is:

- a **canonical protocol asset registry**
- plus **selectable projections/adapters** into repo-visible locations
- plus **quality-gate installers**
- plus **upgrade/drift management**

In other words: greenfield setup should behave like a **configuration-driven repo bootstrap system**, not a pile of templates.

### 7. Goals

1. Make `meminit init` capable of producing a repo that is immediately usable and policy-consistent.
2. Make every installed asset traceable to a declared profile or option.
3. Support mixed-ownership assets safely, preserving user-authored content.
4. Normalize protocol asset handling across generic and tool-specific agent surfaces.
5. Provide deterministic local and CI quality gates out of the box.
6. Make setup repeatable, idempotent, and upgradeable.
7. Expose all setup results through a machine-readable JSON envelope and a persisted setup manifest.

### 8. Non-goals

1. Automatic mutation of remote GitHub branch protection rules in v1.
2. Full support for every possible agent host on day one.
3. Live vendor API integrations or hosted control planes.
4. Managing application code scaffolding beyond repo-governance and protocol assets.
5. Solving brownfield migration in this PRD except where shared machinery is reused.

### 9. Primary users

- **Solo developer using AI agents** who wants one clean bootstrap.
- **Team maintainer** who wants opinionated but selectable defaults.
- **Open-source maintainer** who needs safe public-repo defaults.
- **Agent orchestrator / automation** that wants deterministic, machine-readable setup behavior.

### 10. Design principles

1. **Canonical-before-projection:** there must be one source of truth for each generated protocol asset.
2. **Profile-driven, not ad hoc flags everywhere:** support flags, but organize them around named profiles and a persisted manifest.
3. **Idempotent by default:** re-running setup should converge, not drift.
4. **Mixed ownership where humans matter, generated ownership where machines matter.**
5. **Dry-run first for any write that could surprise the user.**
6. **Repo-local truth:** checked-in files must be sufficient to understand the configured setup.
7. **Contract tests over promises:** every generated asset must be covered by snapshot or semantic tests.

---

## 11. Scope

### 11.1 In scope

#### Core DocOps bootstrap
- `docs/` tree
- `docops.config.yaml`
- schema, templates, constitution, initial index locations

#### Protocol assets
- `AGENTS.md`
- vendor-neutral skills directory
- tool-specific projections/adapters
- generated helper scripts
- drift detection and sync for all of the above

#### Quality gates
- `.pre-commit-config.yaml`
- CI workflow(s)
- protocol drift checking
- packaging/build smoke tests
- docs compliance checks

#### Repository hygiene assets
- `.editorconfig`
- `.gitattributes`
- `.gitignore` additions where needed
- `.github/PULL_REQUEST_TEMPLATE.md`
- issue templates
- `CODEOWNERS`
- Dependabot/Renovate config
- release workflow stubs
- security scanning config where appropriate

#### Setup UX
- interactive and non-interactive setup
- setup profiles
- machine-readable setup manifest
- upgrade/sync path

### 11.2 Out of scope
- SaaS dashboards
- centralized org policy distribution service
- hosted secrets scanning backend
- IDE plugin development

---

## 12. Information architecture

### 12.1 Canonical asset layout

The bootstrap shall define a **canonical vendor-neutral protocol root**. Recommended default:

```text
.agents/
  registry.yaml
  skills/
    meminit-docops/
      SKILL.md
      scripts/
        meminit_brownfield_plan.sh
      manifests/
        openai.yaml
        anthropic.yaml
        google.yaml
```

`AGENTS.md` remains top-level because that surface is repo-global and human-visible.

### 12.2 Projection model

Tool-specific locations, if selected, shall be **projections** from the canonical asset set, not separate sources of truth.

Examples:
- `.codex/...`
- `.claude/...`
- `.gemini/...`
- future tool-specific paths

The exact target paths shall be stored in a **versioned adapter registry**, not hardcoded across docs and templates.

### 12.3 Ownership classes

Assets shall have one of three ownership modes:

1. **generated**  
   Meminit fully owns file content; sync may replace wholesale.

2. **mixed**  
   Meminit owns one managed region; user content outside that region is preserved byte-identically.

3. **projected**  
   A generated or mixed canonical asset is copied/rendered into a tool-specific location from a canonical source; user edits are either forbidden or explicitly unsupported unless the projection is marked mixed.

This extends the current generated/mixed model rather than replacing it.

---

## 13. Setup profiles

### 13.1 Top-level profiles

Meminit shall offer named profiles:

- `minimal`
- `standard`
- `strict`
- `oss`
- `internal`
- `monorepo`

Each profile expands to defaults for docs, protocol assets, hooks, CI, and repo hygiene.

### 13.2 Agent profiles

Meminit shall offer targeted instruction bundles for `AGENTS.md`:

- `minimal`
- `docops-only`
- `security-first`
- `testing-first`
- `research-heavy`
- `product-delivery`
- `oss-maintainer`
- `custom`

These are not full file replacements. They are **section bundles** within a mixed-ownership `AGENTS.md`.

### 13.3 Hook profiles

- `minimal`
- `standard`
- `strict`

### 13.4 CI profiles

- `minimal`
- `standard`
- `strict`

### 13.5 Repository hygiene profiles

- `none`
- `basic`
- `oss`
- `strict`

---

## 14. Functional requirements

### FR-1: Configurable init entrypoint

`meminit init` shall accept:
- a named profile
- explicit overrides
- an optional setup manifest file
- dry-run mode
- JSON output mode

Example shape:

```bash
meminit init \
  --profile standard \
  --agents-profile security-first \
  --agent-target codex \
  --agent-target claude \
  --hooks-profile standard \
  --ci-provider github \
  --ci-profile standard \
  --repo-hygiene oss \
  --dry-run \
  --format json
```

### FR-2: Persisted setup manifest

After a successful write, Meminit shall write a repo-local setup manifest, for example:

```text
.meminit/setup.yaml
```

It shall record:
- selected profiles
- enabled targets
- asset versions
- projection mappings
- install timestamps
- Meminit version
- upgrade policy flags

This becomes the source of truth for later `protocol sync`, `install-precommit`, `install-ci`, and `doctor` checks.

### FR-3: `AGENTS.md` as mixed-ownership assembled document

`AGENTS.md` shall be built from:
- a canonical managed header
- selected managed sections
- optional user-authored custom section(s)

The user must be able to opt into targeted sections such as:
- architecture rules
- code+docs+tests atomicity
- security/no secrets
- dependency-change policy
- testing expectations
- release/change-log policy
- performance guidance
- front-end guidance
- data/schema migration guidance
- brownfield migration behavior
- agent bootstrap instructions for Meminit itself

The generated output shall clearly separate:
- repo-global rules
- Meminit-specific workflow guidance
- selected targeted instructions
- user-authored project-specific additions

### FR-4: Vendor-neutral skills core

Meminit shall generate a **canonical skill bundle** in the vendor-neutral skill directory.

Each skill bundle shall support:
- `SKILL.md`
- optional scripts
- optional per-vendor manifests
- protocol markers or equivalent versioned management metadata

This answers the “SKILLS.md directory” requirement in a durable way: the product should manage a **skills directory containing `SKILL.md` bundles**, not a single flat file.

### FR-5: Tool-specific skill projections

The user shall be able to select which tool ecosystems receive projections:
- generic only
- Codex
- Claude
- Gemini
- other future adapters
- all supported

Projection rules:
- the projection target must be declared in the adapter registry
- drift checks must understand whether the projection is canonical or derived
- docs must not claim a projection path that is not currently installed

### FR-6: Protocol asset drift governance

The existing protocol-check/sync machinery shall be extended so greenfield setup can validate:
- canonical `AGENTS.md`
- canonical skills bundle(s)
- generated helper scripts
- all selected projections/adapters

A repo shall be able to run:

```bash
meminit protocol check --root . --format json
meminit protocol sync --root . --format json
```

and get meaningful results for greenfield-installed assets.

### FR-7: Pre-commit installer profiles

Meminit shall provide:

```bash
meminit install-precommit --profile <PROFILE>
```

Recommended hook bundles:

#### minimal
- trailing whitespace
- EOF fixer
- YAML validation
- `meminit check`

#### standard
- minimal +
- Python format/lint/type hooks aligned with project toolchain
- Markdown formatting/linting
- JSON/TOML sanity checks
- shell script linting if scripts are installed

#### strict
- standard +
- secret scanning
- actionlint
- dependency manifest validation
- link checking or doc reference validation where practical

Important requirement: the generated hook set must be **consistent with the repo’s chosen toolchain**, avoiding the current class of drift where docs, CI, and config imply different tools.

### FR-8: CI/CD installer

Meminit shall provide:

```bash
meminit install-ci --provider github --profile <PROFILE>
```

For GitHub Actions, the standard profile shall generate at least:

1. **docops**  
   `meminit doctor`, `meminit check`

2. **protocol**  
   `meminit protocol check`

3. **lint-and-test**  
   Python linting, typing, tests

4. **build-smoke**  
   build package, install package, run smoke commands

5. **greenfield-smoke**  
   create a temporary empty repo, run `meminit init` with the selected default profile, then verify:
   - `meminit doctor`
   - `meminit check`
   - `meminit protocol check`

Strict CI may add:
- OS matrix
- min/latest supported Python matrix
- dependency review
- secret scan
- SBOM/provenance generation
- release-on-tag

### FR-9: Cross-platform quality

Because Meminit claims cross-platform Python behavior, greenfield smoke tests shall run on at least:
- Ubuntu
- Windows

Mac support is desirable; Linux+Windows is the minimum bar if CI budget is constrained.

### FR-10: GitHub hygiene assets

Optional repo assets shall be installable as a coherent bundle:
- `CODEOWNERS`
- PR template
- issue templates
- Dependabot config
- security policy scaffold if absent
- release drafter or changelog workflow
- branch-protection guidance document

Remote branch protection changes are out of scope, but Meminit shall generate explicit post-init instructions.

### FR-11: Setup report and machine contract

`meminit init --format json` shall return:
- selected profiles
- installed assets
- skipped assets
- projections created
- warnings
- next recommended commands
- setup manifest path

It shall distinguish:
- created
- updated
- projected
- skipped
- drifted-but-not-overwritten

### FR-12: Idempotent reruns

Re-running `meminit init` with the same manifest shall converge with no semantic changes.

Re-running with a different profile shall:
- preview changes in dry-run
- classify which assets will change
- preserve mixed-ownership user content
- require explicit confirmation for destructive transitions

### FR-13: Upgrade path

After Meminit upgrades, the user shall be able to run:

```bash
meminit upgrade-setup --root . --format json
```

or equivalent `protocol sync` / `init --sync` flow that:
- updates generated assets to canonical
- reports newly available profile options
- flags incompatible or deprecated projection targets

### FR-14: Explicit deprecation policy for path changes

If Meminit changes canonical or projection paths, it must:
- support a migration window
- emit warnings
- generate migration actions
- update docs from the same registry that drives the implementation

This is essential to prevent a repeat of the current `.codex` vs `.agents` ambiguity.

---

## 15. Non-functional requirements

### NFR-1: Determinism
Two runs with the same inputs and repo state must produce byte-stable managed content.

### NFR-2: Safety
No writes outside repo root. Symlink escapes must be rejected.

### NFR-3: Mixed-content preservation
For mixed assets, user content outside the managed region must be preserved byte-identically.

### NFR-4: Observability
All setup/install/sync commands must produce machine-readable JSON envelopes.

### NFR-5: Testability
Every generated asset must have contract coverage.

### NFR-6: Documentation-consistency
Docs that mention protocol paths or setup outputs must be generated from, or validated against, the same registry data used by the runtime.

---

## 16. Proposed file outputs by profile

### 16.1 Minimal
- `docs/`
- `docops.config.yaml`
- schema/templates
- `AGENTS.md` with minimal sections
- canonical skill bundle only
- `.editorconfig`
- minimal `.pre-commit-config.yaml`

### 16.2 Standard
- minimal +
- tool-specific projections if selected
- GitHub Actions standard workflow
- PR template
- issue templates
- `CODEOWNERS` stub
- Dependabot config
- protocol helper scripts
- greenfield smoke tests in CI

### 16.3 Strict
- standard +
- stricter hooks
- stricter CI matrix
- secret scanning
- dependency review
- release workflow stubs
- explicit security workflow scaffolding
- branch protection instructions

---

## 17. CLI surface proposal

### 17.1 Commands

```bash
meminit init
meminit init --interactive
meminit init --from .meminit/setup-template.yaml
meminit install-precommit
meminit install-ci
meminit install-github-meta
meminit protocol check
meminit protocol sync
meminit doctor
meminit upgrade-setup
```

### 17.2 Recommended simplification

Keep `init` as the umbrella orchestrator, but allow smaller installers for partial adoption.

That is better than overloading `init` with every lifecycle concern.

---

## 18. Acceptance criteria

1. A new empty repo can be bootstrapped with one command and pass local checks immediately.
2. A standard-profile repo can be created, committed, and opened as a PR with passing CI and no manual file editing required for baseline operation.
3. `AGENTS.md` targeted sections are user-selectable and preserved safely across syncs.
4. Canonical skills are generated once; tool-specific projections are derived from the same source.
5. `protocol check` detects drift across canonical and projected assets.
6. A generated GitHub Actions workflow includes protocol drift checking and greenfield smoke testing.
7. Pre-commit output is aligned with the configured toolchain; no contradiction between config, docs, and CI.
8. Re-running `meminit init` on an unchanged repo is idempotent.
9. Upgrading Meminit and running sync updates generated assets without damaging user-authored content.
10. Contract tests fail if docs advertise an asset path not present in the registry.

---

## 19. Success metrics

- **Setup time:** first successful greenfield bootstrap under 5 minutes of human effort.
- **Time to green:** standard profile passes local validation on first run in >95% of fixture cases.
- **Drift correctness:** protocol drift detection catches 100% of intentionally corrupted fixture assets.
- **Idempotency:** second identical init yields no created/updated assets.
- **Consistency:** zero contract-test mismatches between docs, registry, and generated assets.

---

## 20. Risks and mitigations

### Risk 1: Vendor-path churn
Tool vendors may change skill discovery paths.

**Mitigation:** adapter registry + projection model + deprecation policy.

### Risk 2: Too many flags
The surface may become unusably complex.

**Mitigation:** strong profile defaults + manifest-based overrides.

### Risk 3: Overwriting user intent
Users may customize `AGENTS.md` or projected files.

**Mitigation:** mixed ownership for user-edited surfaces, generated ownership only for canonical machine assets, dry-run previews for profile changes.

### Risk 4: Setup sprawl
Greenfield init may become a kitchen sink.

**Mitigation:** modular installers and clear profile boundaries.

### Risk 5: CI fragility
Strict profiles may be expensive or flaky.

**Mitigation:** minimal/standard/strict tiers and greenfield smoke tests separated from heavier jobs.

---

## 21. Recommended implementation sequence

### Phase 1: Normalize the contract
- introduce setup manifest
- formalize profile model
- make docs consume runtime registry data
- resolve canonical vs projected path model

### Phase 2: Upgrade protocol assets
- extend registry ownership modes if needed
- add vendor-neutral skill bundle model
- add projection adapters
- extend drift/sync logic

### Phase 3: Productize installers
- `install-precommit` profiles
- `install-ci` generator
- GitHub hygiene bundle
- JSON setup report improvements

### Phase 4: Contract and smoke testing
- greenfield fixture matrix
- docs-vs-registry contract tests
- OS/Python smoke tests
- upgrade/downgrade migration tests

---

## 22. Concrete opinionated recommendations

1. **Make `.agents/skills/` the canonical repo path.**  
   Keep `.codex/...` and other tool-specific paths as optional projections only.

2. **Treat `AGENTS.md` as an assembled mixed-ownership artifact, not a monolith.**  
   Section bundles are the right way to support targeted instructions.

3. **Do not treat “skills for Codex/Claude/Gemini” as separate products.**  
   Treat them as adapters over a shared canonical skill model.

4. **Add `protocol check` to CI by default.**  
   Current quality gates are incomplete without protocol drift enforcement.

5. **Add a greenfield smoke test job to CI.**  
   The initializer itself is part of the product and must be tested as such.

6. **Unify the lint/toolchain contract.**  
   Generated pre-commit, CI, docs, and contributing guidance should derive from one chosen tool profile.

---

## 23. Bottom line

The repo already proves the core idea. What is missing is a clean product boundary.

The next greenfield milestone should be:

> **Meminit as a configurable repo bootstrap system with canonical protocol assets, selectable projections, coherent quality gates, and explicit upgrade semantics.**

That is the difference between a useful alpha scaffold and a high-quality greenfield setup product.
