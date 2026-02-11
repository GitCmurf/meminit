---
document_id: MEMINIT-RUNBOOK-001
type: RUNBOOK
docops_version: "2.0"
last_updated: "2025-12-31"
status: Draft
title: Organization DocOps Setup
owner: GitCmurf
version: "0.2"
---

# Runbook: Organization DocOps Setup

## Goal

Establish organisation-level DocOps standards (“ORG standards”) that apply across repositories, while keeping every repository’s compliance baseline **deterministic** (no unintentional drift).

## Prerequisites

- You have `meminit` installed (locally and/or in CI).
- You have decided your organisation-wide doc conventions at a high level (doc types, statuses, required metadata).

## Concepts (read once; saves pain later)

- **Org profile:** a named bundle of standards assets (metadata schema + templates; optionally ORG governance Markdown docs).
- **Global install (XDG):** storing an org profile on a user machine so new repos can default to the org baseline.
- **Vendoring (repo-local pinning):** copying the org profile into a repo and writing a lock file so the repo’s baseline does not drift.

### Where org profiles live (XDG)

Meminit uses the XDG base directory spec by default:

- `XDG_DATA_HOME` (default `~/.local/share`) → profile files live under `meminit/org/profiles/<profile>/`
- `XDG_CONFIG_HOME` (default `~/.config`) is reserved for future configuration, but profiles are treated as data assets.

### “Vendor” (verb): what it means here

To **vendor** is to copy and pin a dependency into your repo so it is self-contained, reviewable, and deterministic in CI.

In Meminit, `meminit org vendor` copies the org profile into the repository (schema + templates, and optionally ORG docs) and writes:

- `.meminit/org-profile.lock.json` (digest + metadata) to make drift visible and updates explicit.

## Steps

### 1. Install org standards globally (optional, recommended)

Use this if you want new repos on _this machine_ to default to your org’s baseline.

Preview (default is dry-run):

- `meminit org install --profile default`

Install:

- `meminit org install --profile default --no-dry-run`

Notes:

- This writes into `XDG_DATA_HOME` (by default `~/.local/share/meminit/org/profiles/default/`).
- This is _machine state_, not a repo guarantee. Use vendoring for repo determinism.

### 2. Vendor org standards into each repository (recommended)

Use this when you want the repository’s compliance baseline to be deterministic across:

- different developer machines,
- agents, and
- CI environments.

Preview:

- `meminit org vendor --root .`

Apply:

- `meminit org vendor --root . --no-dry-run`

What it writes (by default):

- `docs/00-governance/metadata.schema.json`
- `docs/00-governance/templates/template-001-*.md`
- `docs/00-governance/org/org-gov-001-constitution.md`
- `docs/00-governance/org/org-gov-002-metadata-schema.md`
- `.meminit/org-profile.lock.json`

If you do not want the ORG markdown docs in the repo:

- `meminit org vendor --root . --no-include-org-docs --no-dry-run`

### 3. Verify drift status (recommended)

From the repository root:

- `meminit org status --root . --format text`
- `meminit org status --root . --format json` (for automation)

Interpretation:

- `global_installed=true` means your machine has an installed org profile.
- `repo_lock_present=true` means the repo is pinned (vendored).
- `repo_lock_matches_current=false` means **drift**: your machine’s current profile differs from what the repo pinned.

### 4. Upgrade policy (how to avoid unintentional drift)

Upgrades should be explicit and reviewable.

1. Update your machine’s global profile (optional):

- `meminit org install --profile default --force --no-dry-run`

2. Update a repo’s vendored baseline (explicit + reviewable):

- `meminit org vendor --root . --force --no-dry-run`

Then review the diff like any other standards change (ideally via PR).

## Dotfiles integration (optional)

If you manage dotfiles and want the global org profile governed/pinned:

- Store a copy of your org profile directory in your dotfiles repo, and
- sync or symlink it to `~/.local/share/meminit/org/profiles/default/` (platform-specific).

Meminit intentionally does not enforce _how_ you manage dotfiles; it only defines stable, conventional locations and deterministic repo vendoring.

## Common gotchas

- **YAML typing footguns:** YAML parsers may treat `docops_version: 2.0` as a float. Meminit normalizes known fields during schema validation, but it’s still best practice to write `docops_version: '2.0'` and `version: '0.1'` to keep files stable across tools.
- **Secrets/PII:** do not put secrets or personal data in governance docs or profiles (public repos and logs leak).
- **“Global installed” is not “repo pinned”:** if you care about CI determinism, vendor into the repo and use the lock file.
