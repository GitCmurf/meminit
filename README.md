# Meminit

**DocOps for the Agentic Age:** governed docs, compliance checks, and automation.

![CI](https://github.com/GitCmurf/meminit/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/github/license/GitCmurf/meminit)
![Python](https://img.shields.io/badge/python-≥3.11-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)

<!-- TODO: add a terminal GIF or screenshot here, e.g. via asciinema or charmbracelet/vhs -->

## Why Meminit?

Documentation in modern, AI-assisted codebases drifts fast. Docs lose their
governance metadata, go stale, break naming conventions, and fall out of sync
with the code they describe. Manual reviews don't scale, and most linting tools
ignore docs entirely.

**Meminit fixes that.** It is a CLI that scaffolds, governs, and validates
documentation — so your docs stay machine-readable, policy-compliant, and in
sync with your code.

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

# Or from a local clone
git clone https://github.com/GitCmurf/meminit.git
cd meminit
pip install -e .
```

Verify the installation:

```bash
meminit --version
```

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

## 📖 Documentation

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

## Project Status

> **Alpha (v0.1.0)** — the CLI is functional and under active development. It
> is not yet published on PyPI. Expect breaking changes before v1.0.

## 🔒 Security

- Security policy: [SECURITY.md](SECURITY.md)
- Pre-public checklist: [MEMINIT-GOV-003](docs/00-governance/gov-003-security-practices.md)

## 🤝 Contributing

Start with [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

Found a bug or have an idea?
[Open an issue](https://github.com/GitCmurf/meminit/issues).

## 📝 License

Apache License 2.0 — see [LICENSE](LICENSE).
