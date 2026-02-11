---
document_id: MEMINIT-PLAN-001
owner: Product Team
status: Draft
version: 0.1
last_updated: 2025-12-26
title: MVP Tasklist
type: PLAN
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PLAN-001
> **Owner:** Product Team
> **Status:** Draft
> **Version:** 0.1
> **Type:** PLAN

# 5. TDD & Atomic Task Breakdown

## 5.0 Implementation Status (As of 2025-12-26)

This tasklist predates the current MVP scope. For traceability, each epic/task below is now annotated as:

- **Met**: Implemented and covered by tests.
- **Exceeded**: Implemented with additional safeguards beyond this tasklist.
- **Not Yet Implemented**: Still outstanding work; no equivalent/superior replacement exists in the current MVP.
- **Superseded**: Replaced by an equivalent or superior implementation that covers the same utility.

Summary:

- **Met**: Repo initialization (`meminit init`), document creation (`meminit new`), repository checking (`meminit check`), auto-fix (`meminit fix`) for common issues.
- **Exceeded**: Auto-fix now sanitizes filenames and can fully initialize missing frontmatter to pass schema validation.
- **Not Yet Implemented**: OrgConfig layer, Document_Standards.md generation, JSON output for `meminit new`/`fix`, agent interface & automation.

## 5.0.1 Consolidation Note (As of 2025-12-26)

`MEMINIT-PLAN-004` (“Epics Breakdown”) is redundant with this tasklist and `MEMINIT-PLAN-003` (“Project Roadmap”). Any still-relevant, not-yet-implemented items have been consolidated into:

- this tasklist (atomic work items), and/or
- `MEMINIT-PLAN-003` (sequencing/roadmap).

  5.1 Epics

E1: Core configuration \& models
**Not Yet Implemented** (OrgConfig layer not yet present; current RepoConfig loader is in place)

E2: New document creation
**Met** (implemented as `meminit new <TYPE> <TITLE>` with repo-prefix ID generation and template support)

E3: Validation (check)
**Met / Exceeded** (`meminit check` implements schema validation, ID validation, filename warnings, directory mapping warnings, link checking with fragment support; includes YAML scalar normalization to avoid false positives)

E4: Repo initialisation (init-repo)
**Met** (implemented as `meminit init`)

E5: Index \& linking (index, link)
**Met** (index/resolve/identify/link implemented with JSON index artifact)

E6: Migration tools (scan)
**Met** (read-only scan with JSON output and type directory suggestions)

E7: Integration (hooks, CI, templates)
**Met** (pre-commit installer + CI examples + templates)

5.2 Example atomic tasks (per epic)

I’ll outline them at “agent-executable” granularity.

E1: Core configuration \& models

T1.1: Implement OrgConfig dataclass and YAML loader; tests for happy path + bad fields. **Not Yet Implemented**

T1.2: Implement RepoConfig dataclass and loader with validation against OrgConfig. **Not Yet Implemented**

T1.3: Implement Document model with frontmatter + body parse; unit tests with minimal and extended metadata. **Met** (core parsing uses `python-frontmatter`)

T1.4: Implement ID validator; tests for valid/invalid IDs, sequence edge cases. **Met**

E2: New document creation

T2.1: Implement ID generator given RepoConfig + existing docs; tests cover seq/no-seq cases. **Met**

T2.2: Implement template loader (repo-local, then org-level fallback). **Met / Superseded**
Superseded detail: repo-local template loading is **Met**; org-level fallback is **Not Yet Implemented**.

T2.3: Implement create_document() (library) that:

generates ID

fills template

writes file. **Met**

Test with tmp repo. **Met**

T2.4: Implement CLI command meminit new that calls create_document(); tests via CliRunner (click/typer) including JSON output. **Met / Superseded**
Superseded detail: CLI is **Met**; JSON output for `meminit new` is **Not Yet Implemented**.

E3: Validation

T3.1: Implement validate_document() returning list of violation objects. **Met**

T3.2: Implement validate_repo() scanning docs/ and aggregating violations. **Met**

T3.3: CLI meminit check returning appropriate exit code, text or JSON; tests for “valid repo” and “violations present”. **Met**

E4: Repo initialisation

T4.1: Implement init_repo() that creates basic docs/ tree + docops.config.yaml. **Met**

T4.2: Add generation of Document_Standards.md from config + template. **Not Yet Implemented**

T4.3: Tests: run init_repo() in empty tmp dir and assert structure and contents. **Met**

E5: Index \& linking

T5.1: Implement build_index() reading all docs → JSON index file. **Met**
**Met** (index artifact `docs/01-indices/meminit.index.json`)

T5.2: CLI meminit index and tests. **Met**
**Met**

T5.3: CLI meminit link <ID> that looks up index (or direct scan) and prints Markdown; tests. **Met** (plus resolve/identify)
**Met** (plus `resolve` and `identify` commands)

E6: Migration tools

T6.1: Implement heuristic classifier: guess type from filename/keywords (very simple at first). **Partially Met** (directory-based inference only)
**Partially Met** (directory-based inference + ambiguity detection; no content heuristics yet)

T6.2: Implement scan_repo_for_migration() that lists non-compliant files and proposed type/area. **Partially Met** (reports docs root, markdown count, type directory suggestions, ambiguities)
**Partially Met** (scan reports docs root, markdown count, type directory suggestions, ambiguities)

T6.3: CLI meminit scan --output json; tests. **Met**
**Met**

E7: Integration

T7.1: Provide pre-commit config snippet in meminit repo that runs meminit check. **Met** (`meminit install-precommit`)
**Met** (`meminit install-precommit` generates config)

T7.2: Provide GitHub Actions YAML example that runs meminit check. **Met**
**Met** (CI workflow with `meminit doctor` + `meminit check`)

T7.3: Provide template files in docs/00-governance/templates/ for ADR, PRD, Spec. **Met**

E8: Agent interface & automation
**Not Yet Implemented** (agent protocol and “context dump” command are deferred to a later phase)

T8.1: Define JSON Schema for CLI JSON outputs (at least `meminit check`, `meminit doctor`, `meminit fix`). **Not Yet Implemented**

T8.2: Create `docs/20-specs/spec-00x-agent-protocol.md` defining the agent-facing interface contract (format + semantics). **Not Yet Implemented**

T8.3: Implement `meminit context` to output a token-optimized repo summary for agents (config + key doc IDs + violations). **Not Yet Implemented**

5.3 Testing strategy

Unit tests for:

config parsing

ID generation

document parsing

validation rules

Integration tests:

create a fake repo, run init-repo, new, check, index; assert correct outputs.
**Met**: init/new/check/fix/index/resolve/identify/link covered by unit tests.

No version-history tables → no tests needed for that.

6. Definition of Done

For the CLI core (meminit package)

All core commands (init-repo, new, check, fix, index, resolve, identify, link) implemented as per spec. **Met**

Unit + integration tests for each command; minimum 80% coverage of core library.

Commands accept --output json and produce well-structured objects. **Met / Superseded**
Met: `meminit check --format json`. Not yet implemented: JSON output for `meminit new`/`meminit fix`.

Repo-level config and org config schemas validated; invalid configs are surfaced with clear errors. **Not Yet Implemented**

For integration

Sample docops.config.yaml checked into Meminit with tests covering expected values.
**Met** (init creates a baseline config; `meminit new` reads it in tests)

## 7. Next Sprint Candidates (Work Remaining)

1. Expand `scan` heuristics (content-based type inference, collisions, suggested mapping confidence).
2. Decide/configure OrgConfig + RepoConfig layering, or explicitly defer in a new ADR.
3. Add JSON output mode for `meminit new` and `meminit fix`.
4. Implement Document_Standards.md generation (or explicitly defer).

Sample Document_Standards.md generated and validated by meminit check as a dogfood test.

Pre-commit and GitHub Actions examples committed and documented.

For documentation

Meminit’s own repo uses Meminit’s DocOps rules (self-dogfooding).

README explains installation and basic usage (init-repo, new, check).

Document_Standards.md in Meminit repo references ORG-DOCOPS-CONSTITUTION by ID and link (demonstrating cross-repo linking).
