# Meminit

**DocOps for the Agentic Age:** governed docs, compliance checks, and automation.

[![CI](https://github.com/GitCmurf/meminit/actions/workflows/ci.yml/badge.svg)](https://github.com/GitCmurf/meminit/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/GitCmurf/meminit)](LICENSE)
![Python](https://img.shields.io/badge/python-≥3.11-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)

**Quick links:** [Docs](docs/) · [Runbooks](docs/60-runbooks/) · [Issues](https://github.com/GitCmurf/meminit/issues) ·
[Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

## Why Meminit?

Documentation in modern, AI-assisted codebases drifts fast. Docs lose their
governance metadata, go stale, break naming conventions, and fall out of sync
with the code they describe. Manual reviews don't scale, and most linting tools
ignore docs entirely.

**Meminit fixes that.** It is a CLI that scaffolds, governs, and validates
documentation — so your docs stay machine-readable, policy-compliant, and in
sync with your code.

### Built for the Agentic Age

Meminit is designed to work _with_ AI coding agents, not just alongside them:

- **Stable IDs** (`MEMINIT-ADR-001`) let agents reference docs without
  guessing filenames.
- **JSON Schema-validated frontmatter** gives agents structured metadata they
  can parse and trust.
- **`meminit init` scaffolds an `AGENTS.md`** — a ready-made agentic coding
  rules file that teaches agents how to create, validate, and maintain governed
  docs in your repo.
- **Ships with a Codex/Claude-compatible skill** (`.codex/skills/meminit-docops/`)
  that agents can load to run the full DocOps workflow autonomously.

## What It Does

- **Scaffold a governed docs tree in seconds** — `meminit init`
- **Create documents with stable, traceable IDs** — `meminit new`
- **Enforce repo rules in CI and pre-commit** — `meminit doctor`, `meminit check`
- **Auto-fix common violations** (dry-run by default) — `meminit fix`
- **Build an index for stable ID → path resolution** — `meminit index`, `meminit resolve`

See the full project vision:
[MEMINIT-STRAT-001](docs/02-strategy/strat-001-project-meminit-vision.md).

## Quickstart

### Prerequisites

- Python ≥ 3.11
- [pipx](https://pipx.pypa.io/) (recommended) or pip

### Install

Meminit is not published on PyPI yet. Install from GitHub (or a local
checkout):

```bash
# Via pipx (recommended)
pipx install git+https://github.com/GitCmurf/meminit.git@main
meminit --version

# Or from a local clone
git clone https://github.com/GitCmurf/meminit.git
cd meminit
pip install -e .
```

Note: `@main` is the latest development version. Use a tagged release once tags are published.

### New repository (greenfield)

```bash
meminit init        # scaffold docs/ tree and config
meminit new ADR "My Decision"   # create a governed document
meminit check       # validate everything
```

Runbook: [Greenfield setup](docs/60-runbooks/runbook-002-greenfield-repo.md).

### Existing repository (brownfield)

```bash
meminit doctor      # diagnose current state
meminit scan        # discover existing docs
meminit check       # validate against rules
meminit fix --dry-run   # preview auto-fixes
```

Runbook: [Existing repo migration](docs/60-runbooks/runbook-003-existing-repo-migration.md).

### Coming from `adr-tools`?

Meminit extends the ideas pioneered by
[adr-tools](https://github.com/npryce/adr-tools) — lightweight, plain-text
Architecture Decision Records — and generalizes them to _all_ governed document
types (PRDs, FDDs, specs, runbooks, and more).

Your muscle memory still works:

```bash
meminit adr new "Use Postgres for persistence"
```

Under the hood you get structured governance, JSON Schema validation, stable
IDs, and cross-platform Python — no Bash required.

> **Note:** Meminit is an independent project licensed under Apache 2.0. It was
> developed without reference to `adr-tools` source code (which is GPL-3.0).

## Key Concepts

- **Governed docs**: Markdown with required YAML frontmatter, validated by JSON Schema.
- **Stable IDs**: documents are referenced by `REPO-TYPE-SEQ` identifiers (e.g., `MEMINIT-ADR-001`), not filenames.
- **Namespaces**: support monorepos by defining multiple governed doc roots.

Example frontmatter (simplified):

```yaml
document_id: MEMINIT-ADR-001
type: ADR
title: Use Apache-2.0 License
status: Approved
version: 1.0
last_updated: 2025-12-30
owner: Repo Maintainers
docops_version: 2.0
```

## How It Works

Meminit follows a simple loop: **scaffold → author → check → fix → index**.

1. `meminit init` creates a standard `docs/` directory tree and a
   `docops.config.yaml` that defines your project's naming conventions,
   namespaces, and templates.
2. Authors create governed documents via `meminit new`, which stamps each file
   with YAML frontmatter (stable ID, type, status, dates).
3. `meminit check` and `meminit doctor` validate every doc against the
   project's governance rules — in CI, in pre-commit hooks, or on demand.
4. `meminit fix` auto-corrects common violations (dry-run first, so nothing
   changes until you say so).
5. `meminit index` builds a lookup table from stable IDs to file paths, making
   docs machine-resolvable.

## Documentation

**Governance & Runbooks**

- [Org setup](docs/60-runbooks/runbook-001-org-setup.md)
- [Greenfield repo](docs/60-runbooks/runbook-002-greenfield-repo.md)
- [Existing repo migration](docs/60-runbooks/runbook-003-existing-repo-migration.md)
- [CI/CD enforcement](docs/60-runbooks/runbook-004-ci-cd-enforcement.md)

**Specs & Decisions**

- [Compliance checker spec](docs/20-specs/spec-003-compliance-checker.md)
- [Architecture decisions](docs/45-adr/)

Browse the full [docs/](docs/) tree for governance, specs, ADRs, feature
designs, and runbooks.

## Getting Help

- Ask questions / report bugs: [GitHub Issues](https://github.com/GitCmurf/meminit/issues)
- Security issues: see [SECURITY.md](SECURITY.md)
- Contact: `maintainers@meminit.io`

## Roadmap & Changelog

- Roadmap: [MEMINIT-PLAN-003](docs/05-planning/plan-003-roadmap.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## Project Status

> **Alpha (v0.2.0)** — the CLI is functional and under active development. It
> is not yet published on PyPI. Expect breaking changes before v1.0.

## Non-goals

Meminit is intentionally narrow in scope:

- Not a documentation CMS (we govern Markdown in git)
- Not a project management tool
- No Node.js requirement for the core CLI (a `package.json` may exist for adjacent tooling)

## Automation

- **Pre-commit**: `meminit install-precommit` can install a local `meminit check` hook into `.pre-commit-config.yaml`.
- **GitHub Actions**: see `.github/workflows/ci.yml` for a minimal setup running `meminit doctor` and `meminit check`.

## Security

- Security policy: [SECURITY.md](SECURITY.md)
- Pre-public checklist: [MEMINIT-GOV-003](docs/00-governance/gov-003-security-practices.md)

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
meminit doctor --root .
meminit check --root .
```

## Contributing

Start with [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

Found a bug or have an idea?
[Open an issue](https://github.com/GitCmurf/meminit/issues).

## License

Apache License 2.0 — see [LICENSE](LICENSE).
