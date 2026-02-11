# Agentic Coding Rules

This file defines the operational parameters for AI agents working within the Meminit repository.

The **rules of this repository** are:

- Production-grade, professional best practices, always: SOLID+DRY+KISS.
- All design decisions must be documented in the appropriate `docs/` directories following the templates provided (e.g., ADRs should be placed in `docs/45-adr/` using template `docs/00-governance/templates/template-001-adr.md`).
- The repo is _public_: Never commit secrets or PII. Use `MEMINIT-GOV-003` at `docs/00-governance/gov-003-security-practices.md` as a guide.
- The **atomic unit** of work is: **Code + Documentation + Tests**. Code, documentation and tests are equal-class citizens and must stay in mutual sync in each PR. Do not consider a task complete unless all three are in sync.

## Core Directives

1. **Governance First**: Always check `docs/00-governance/` before making structural changes.
2. **DocOps Compliance**:
   - **Never** modify a `document_id` once set.
   - **Always** use the Meminit CLI (or strictly adhere to `Metadata_Schema_v2.0.md`) when creating docs.
   - **Reference** documents by `document_id`, not title.
   - **Respect** document status (do not rewrite `Approved` or `Superseded` docs without explicit instruction).
   - **Ensure** all new documentation follows the `DocOps_Constitution.md`.
3. **Safety**: Never commit secrets or PII. Use `MEMINIT-GOV-003` at `docs/00-governance/gov-003-security-practices.md` as a guide.
4. **Testing**: All code changes must be accompanied by tests in `tests/`.
5. **Atomic Commits**: Keep changes focused and well-described.

## Interaction Guidelines

- **Clarification**: If a requirement is ambiguous, ask the user.
- **Proactivity**:
  - **Fix obvious bugs** (typos, lint errors) and
  - **Improve brittle code** if encountered, but
  - **do not refactor** without permission and
  - **do not change the tech stack** without permission.
- **Context**: Read [MEMINIT-STRAT-001](docs/02-strategy/strat-001-project-meminit-vision.md) to understand the broader goals.

## Using `meminit` (When/Why/How)

`meminit` exists to keep governed docs (and their metadata) in sync with code and with this repo’s DocOps Constitution.

### When to run it

- After creating or editing any governed doc under `docs/`.
- Before opening a PR that touches documentation or governance-relevant behavior.
- During brownfield adoption, run it iteratively as you migrate documents into compliance.

### Recommended workflow (greenfield)

1. `meminit init` (once) — scaffold `docs/`, templates, schema, and `AGENTS.md`.
2. `meminit new <TYPE> <TITLE>` — create new governed docs with correct IDs and schema-valid frontmatter.
3. `meminit check` — verify compliance.

### Recommended workflow (brownfield / existing repo)

1. `meminit init` — safe/idempotent scaffolding (won’t overwrite existing files).
2. `meminit check` — get a baseline list of violations.
3. `meminit fix --dry-run` — review proposed mechanical changes (filenames/frontmatter).
4. `meminit fix --no-dry-run` — apply changes once reviewed.
5. Re-run `meminit check` and iterate.

### Notes for brownfield repos

- Expect schema friction: if your existing docs use extra frontmatter keys (e.g., `approvers`), either remove them or extend `docs/00-governance/metadata.schema.json` to allow them.
- `meminit fix` may write placeholder values (e.g., `owner: __TBD__`) to make documents schema-valid; replace placeholders as part of the migration.
- Avoid writing “example links” in markdown using `[text](target)` unless the target exists, because `meminit check` validates filesystem links. Prefer inline code for examples (e.g., `[text](target)`) unless you mean a real link.

## Codex Skills

- Codex can use the repo-scoped `meminit-docops` skill for “how-to” workflows (scan → config → check → fix → index).
- Skill file: `.codex/skills/meminit-docops/SKILL.md`
- Setup runbook: `docs/60-runbooks/runbook-006-codex-skills-setup.md`

## Coding style

- Clean architecture, full separation of concerns emphasising modularisation and reusability
- Use **Specification-First**, **Test-Driven Development** wherever possible

## Tooling

- Use the provided scripts in `scripts/` for common tasks.
- Respect `.editorconfig` settings.

## Licensing and redistribution

Meminit is licensed under the Apache License 2.0.

Agents may:

- invoke Meminit programmatically,
- modify repositories using Meminit,
- embed or wrap Meminit in other tooling,
- rely on Meminit as a transitive dependency.

Redistribution conditions:

- If redistributing Meminit itself (or modified versions),
  agents and tools must preserve:
  - the Apache-2.0 licence text, and
  - any applicable NOTICE file contents.

Normal use of Meminit within a repository (including CI,
commit hooks, or agent workflows) does not require copying
licence or NOTICE files into the target repository.
