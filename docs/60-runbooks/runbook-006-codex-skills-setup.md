---
document_id: MEMINIT-RUNBOOK-006
type: RUNBOOK
docops_version: 2.0
last_updated: 2025-12-26
status: Draft
title: Codex Skills Setup for Meminit
owner: GitCmurf
version: 0.1
---

# Runbook: Codex Skills Setup for Meminit

## Goal

Make the Meminit Codex Skill available in your Codex environment, either:

- repo-scoped (recommended), or
- installation-wide (global).

This runbook targets **Codex CLI** usage first. Skills are also supported in IDE extensions, but the discovery UI may differ.

## Repo-scoped setup (recommended)

This repo already ships a Codex skill at:

- `.codex/skills/meminit-docops/SKILL.md`

Steps:

1. Start Codex from the repo (preferably the repo root).
2. In the Codex TUI, run `/skills` to list available skills.
3. Confirm `meminit-docops` appears in the list.
4. If it does not appear:
   - confirm the file exists: `.codex/skills/meminit-docops/SKILL.md`
   - restart Codex so it re-scans the repo skill directory

Self-check (before restart):

```bash
test -f .codex/skills/meminit-docops/SKILL.md && echo "OK: meminit-docops skill present"
```

Important: skills are typically loaded once per Codex session. If you add or edit skills, **restart Codex**.

How to invoke (Codex CLI):

- Explicit invocation: type `$` in the prompt and select `meminit-docops`, or reference it directly in your prompt text (e.g., “Use `$meminit-docops` to plan a brownfield migration.”).
- Implicit invocation: describe the DocOps task; Codex may choose the skill based on its name/description.

### Troubleshooting: `/skills` only shows system skills

If `/skills` only lists built-in skills (e.g., `skill-creator`, `skill-installer`) and not repo skills:

1. Confirm you launched Codex **inside the git repository**:
   - Start Codex from the repo root directory where `.git/` and `.codex/` exist.
   - If you launch from a different working directory, Codex may not discover repo-scoped skills.
2. Confirm the skill is in a supported repo location:
   - `$CWD/.codex/skills`
   - `$REPO_ROOT/.codex/skills`
3. Confirm `SKILL.md` is valid:
   - filename must be exactly `SKILL.md`
   - YAML frontmatter must parse
   - `name` and `description` must be single-line and within length limits
4. Confirm the skill directory is not a symlink (Codex may ignore symlinked skill dirs).
5. Restart Codex after adding/updating skills (skills are loaded once per session).
6. If skills still don’t appear, check your Codex version and configuration:
   - Update Codex CLI to a recent version that supports skills.
   - Ensure skills are enabled in `~/.codex/config.toml` (exact setting varies by build).

### Installing the skill into another repo (brownfield pilot)

If you are testing Meminit in another repo (e.g., `../AIDHA`) and want the same skill there:

1. Create the target skill directory: `<TARGET_REPO>/.codex/skills/`
2. Copy the skill folder from this repo:
   - source: `.codex/skills/meminit-docops/`
   - destination: `<TARGET_REPO>/.codex/skills/meminit-docops/`
3. Restart Codex from the target repo root and run `/skills`.

## Installation-wide setup (global)

If your Codex implementation supports global skills, install by copying the skill folder into the global skills directory.

Steps (conceptual):

1. Locate your Codex global skills directory (varies by OS/installation).
2. Copy the folder:
   - source: `.codex/skills/meminit-docops/`
   - destination: `~/.codex/skills/meminit-docops/` (Mac/Linux default per Codex docs)
3. Restart Codex and verify discovery.

Security note:

- Prefer repo-scoped skills for public repos to avoid accidental cross-project behavior drift.

## How to invoke the skill

Invocation UX varies by Codex host (CLI vs IDE extension). Typical patterns:

- Select the skill by name (`meminit-docops`) in the UI, then run its workflow.
- Or ask Codex explicitly: “Use the meminit-docops skill to plan a brownfield migration.”

Note: Codex ships built-in helper skills such as `$skill-creator` and `$skill-installer` for creating and installing skills.
Depending on the Codex build, these may appear with slightly different names in the `/skills` list.

## What the skill does (and does not do)

Does:

- Provide a safe decision tree for `scan → config → doctor → check → fix → index`.
- Emphasize dry-run first; require explicit confirmation before writes.

Does not:

- Decide repo governance policy (that belongs in `AGENTS.md` / human decisions).
- Promote documents to `Approved` or assign owners without explicit user input.
