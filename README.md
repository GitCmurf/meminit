# Meminit

DocOps for the Agentic Age: governed docs, compliance checks, and automation.

![CI](https://github.com/GitCmurf/meminit/actions/workflows/ci.yml/badge.svg)

## What it does

Meminit helps teams keep documentation **governed**, **consistent**, and **toolable**:

- Scaffolds a standard `docs/` tree and DocOps configuration (`meminit init`)
- Creates governed documents with stable IDs (`meminit new`)
- Enforces repo rules in CI / pre-commit (`meminit doctor`, `meminit check`)
- Auto-fixes common violations (`meminit fix`, dry-run by default)
- Builds an index for stable ID → path resolution (`meminit index`, `meminit resolve`)

See the project vision: `MEMINIT-STRAT-001` at `docs/02-strategy/strat-001-project-meminit-vision.md`.

## Quickstart

### Install

Meminit is not published on PyPI yet. Install from GitHub (or a local checkout):

```bash
pipx install git+https://github.com/GitCmurf/meminit.git@main
```

### New repository (greenfield)

```bash
meminit init
meminit new ADR "My Decision"
meminit check
```

Runbook: `docs/60-runbooks/runbook-002-greenfield-repo.md`.

### Existing repository (migration / brownfield)

```bash
meminit doctor
meminit scan
meminit check
meminit fix --dry-run
```

Runbook: `docs/60-runbooks/runbook-003-existing-repo-migration.md`.

## Documentation

- Org setup: `docs/60-runbooks/runbook-001-org-setup.md`
- CI/CD enforcement: `docs/60-runbooks/runbook-004-ci-cd-enforcement.md`
- Compliance specs: `docs/20-specs/spec-003-compliance-checker.md`

## Security

- Security policy: `SECURITY.md`
- Pre-public checklist: `MEMINIT-GOV-003` at `docs/00-governance/gov-003-security-practices.md`

## Contributing

Start with `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.

## License

Apache License 2.0 (see `LICENSE`).
