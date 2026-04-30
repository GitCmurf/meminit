---
document_id: MEMINIT-RUNBOOK-006
type: RUNBOOK
docops_version: 2.0
last_updated: 2026-04-28
status: Draft
title: Codex Skills Setup for Meminit
owner: GitCmurf
version: "0.4"
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

- Provide a safe decision tree for `scan → context → doctor → check → fix → index`.
- Use the **Agent Interface v3** (output schema v3.0) for all commands.
- Emphasize deterministic, machine-safe JSON outputs via `--format json`.
- Support standardized agent flags: `--output`, `--include-timestamp`, and `--verbose`.

Does not:

- Decide repo governance policy (that belongs in `MEMINIT-GOV-001` / human decisions).
- Promote documents to `Approved` or assign owners without explicit user input.

## Agent Interface Compliance

The `meminit-docops` skill is designed to work with the **v3 output contract** (see MEMINIT-SPEC-008). When developing or modifying skills that consume Meminit:

1. **Always use `--format json`** for machine parsing.
2. **Expect exactly one JSON object on STDOUT**.
3. **Handle errors structuredly** via the `error` object in the envelope.
4. **Prefer `meminit context`** for discovering repository configuration instead of hardcoding paths.

## Bounded Codex Review-Remediation Loop

For a local proof-of-concept review loop, use the repository script:

```bash
./.venv/bin/python scripts/codex_review_remediation_loop.py --base main --max-iterations 2
```

The loop uses Codex-native review rather than a third-party reviewer:

1. Run `codex review --base main`.
2. Stop if the review emits a recognized clear result. Codex review findings
   are detected from built-in `- [P1]`/`- [P2]`/`- [P3]` comment markers.
   The script also understands `REVIEW_STATUS: clear` for synthetic tests or
   future Codex builds that allow custom review prompts with `--base`.
3. Otherwise run `codex exec` in `workspace-write` sandbox mode to remediate
   the actionable findings.
4. Optionally run each `--check` command after the remediation pass.
5. Repeat until the review is clear or `--max-iterations` remediation passes
   have completed.
6. Run one final review by default so the operator can see whether the capped
   loop ended cleanly.

Useful proof-of-concept command with explicit verification:

```bash
./.venv/bin/python scripts/codex_review_remediation_loop.py \
  --base main \
  --max-iterations 2 \
  --initial-review-file latest \
  --check "./.venv/bin/pytest -q" \
  --check "./.venv/bin/meminit check docs/60-runbooks/runbook-006-codex-skills-setup.md --format json"
```

Safety notes:

- `--max-iterations` is a remediation-pass cap. With the default final review,
  `--max-iterations 2` may run three reviews: initial review, second-cycle
  review, and a final status review after the second remediation.
- A failing `--check` is fed into the next remediation pass while iteration
  budget remains. If the final allowed pass still leaves a failing check, the
  loop reports `pending_check_failures: true` and does not report clear.
  This remains true even if the next `codex review` output reports clear.
- Transcripts are written under `tmp/codex-review-remediation-loop/` by
  default, which is ignored by git. Iteration review transcripts are named
  `review-<N>.txt` and the capped final review is named `review-final.txt`, so
  failure summaries can surface the latest actionable review artifact.
- This Codex CLI build rejects `codex review --base <branch> -`, so the review
  step does not pass a custom prompt. If the output is ambiguous, the loop
  treats the review as not clear.
- Remediation prompts are sent via stdin (`-`) so large prompts do not become
  shell arguments.
- Only the actionable review text is passed to the remediation agent. Verbose
  Codex review transcripts and tool logs are kept in artifact files but are not
  replayed into the next prompt.
- Remediation prompt input is capped by `--max-remediation-input-chars`
  (default `200000`) to avoid nested Codex input-limit failures.
- Remediation output defaults to `--color never` for stable transcripts and
  writes each final remediation message to
  `remediation-<N>-last-message.txt` under the artifact directory.
- `summary.json` includes direct artifact paths for reviews, remediation
  transcripts, final messages, and check outputs. If a remediation subprocess
  fails, the loop writes a failure summary before exiting non-zero.
- The terminal output defaults to a concise text summary with iteration status,
  latest artifact paths, and the latest actionable review excerpt. Use
  `--summary-format json` for the previous JSON stdout shape, or
  `--summary-format both` when both are useful.
- During the loop, compact progress logs are written to stderr when each
  review, remediation, or check starts and finishes. The compact format is
  `HH:MM:SS|rev|1   |event`, with phase codes `rev`, `rem`, and `chk`,
  four-character labels (`init`, `fin`, iteration numbers, or check IDs), and
  the remaining text reserved for commands, review summary prose, or finding
  details. Compact progress wraps to the current terminal width when stderr is
  attached to a TTY, with a 120-column fallback for redirected or captured
  output. Continuation lines align under the event text instead of repeating
  the timestamp and phase columns. Review progress prints the review's leading
  prose summary and up to five `[P#]` finding blocks (title plus the first
  detail lines). Use `--progress-style verbose` for the older timestamped
  sentence format, or `--quiet-progress` to suppress live progress logs.
- A capped loop ends with a final review. If that review reports findings, a
  later invocation should pass the final review artifact back in with
  `--initial-review-file <artifact-dir>/review-final.txt`; this prevents
  non-deterministic future reviews from losing the previous run's final
  findings. Use `--initial-review-file latest` to load the newest
  `tmp/codex-review-remediation-loop/*/review-final.txt` automatically, or the
  newest `<custom-artifact-dir>/*/review-final.txt` when `--artifact-dir` is
  supplied.
- Model selection can be tuned with `--model <MODEL>` for both review and
  remediation, or `--review-model <MODEL>` / `--remediation-model <MODEL>` for
  phase-specific overrides. Reasoning effort can be tuned with
  `--reasoning-effort minimal|low|medium|high`, which maps to Codex
  `model_reasoning_effort`.
- `--exec-json` is available when a machine-readable Codex event stream is
  useful, but it is not the default because JSONL is noisier for operator
  review than the normal transcript.
- Use separate git worktrees for simultaneous loop experiments. Multiple local
  Codex processes writing to the same checkout can race on the working tree.

## Protocol Asset Governance

As of Phase 3, repo-local protocol files (AGENTS.md, skill manifests, bundled scripts) are governed clients of the Meminit runtime contract. Two commands manage them:

### Checking for drift

```bash
meminit protocol check --root . --format json
```

This detects six drift outcomes: aligned, missing, legacy, stale, tampered, and unparseable. Exit code is 0 only when all assets are aligned.

### Syncing to canonical

```bash
# Preview changes (default — no writes)
meminit protocol sync --root . --format json

# Apply changes
meminit protocol sync --root . --no-dry-run --format json

# Force-overwrite tampered assets
meminit protocol sync --root . --no-dry-run --force --format json
```

Key safety defaults:

- `--dry-run` is on by default; you must pass `--no-dry-run` to write.
- Tampered assets require `--force`; unparseable assets always refuse.
- User content in mixed-ownership files (e.g., custom sections in AGENTS.md) is preserved byte-identical.

### CI integration

Add to your CI pipeline to catch protocol drift on PRs:

```bash
meminit protocol check --root . --format json
```

This fails (exit 1) if any asset is drifted or unparseable, blocking the merge until the developer runs `meminit protocol sync --no-dry-run`.

### Upgrading Meminit

After upgrading the Meminit package, protocol assets may become stale (new version/hash). Run:

```bash
meminit protocol check --root .
meminit protocol sync --root . --no-dry-run
meminit protocol check --root .
```

The last command confirms alignment. See MEMINIT-FDD-012 for the full specification.

## Project State Queue

As of Phase 4, repo-local project state is also a governed agent surface.
The queue commands are intended for deterministic work selection, not
heuristic planning.

### Inspecting the queue

```bash
meminit state next --root . --format json
meminit state blockers --root . --format json
meminit state list --root . --format json
```

Use `state next` when you need a single next action. Use `state blockers`
to understand why an item is not ready. Use `state list` when you need the
full merged view.

### Safe loop pattern

1. Run `meminit state next --root . --format json`.
2. If `data.reason == "queue_empty"` or `data.reason == "state_missing"`, stop and report that the queue is empty (or missing).
3. If `data.entry` is present, do the work deterministically.
4. Persist the change with `meminit state set` or the appropriate writer.
5. Re-run `meminit state next --root . --format json` and continue until the queue is empty.

### Configuration rule

Queue commands require an initialized repository configuration. If
`docops.config.yaml` is missing or malformed, fix initialization before
trying to inspect or mutate queue state. Missing `project-state.yaml` is
treated as an empty queue, not as an error.

### `data.reason` semantics

The `state next` JSON response includes `data.reason` when no entry is
selected:

| Reason | Meaning |
|---|---|
| `state_missing` | No `project-state.yaml` exists. The queue is empty. |
| `queue_empty` | State file exists but no entries are ready. All candidates are blocked, in progress, or the filters excluded everyone. |

When `data.entry` is present, `data.reason` is `null`.

### v1 to v2 state file migration

Legacy `project-state.yaml` files (no `state_schema_version` key) are
automatically migrated to v2 on the first mutation. No separate command
is required. The migration preserves all existing entries and adds the
five planning fields (`priority`, `depends_on`, `blocked_by`,
`assignee`, `next_action`) with their default values.

To force eager migration with a minimal mutation (adds a notes field):

```bash
meminit state set <ID> --notes "migrate to v2" --root . --format json
```

The `state_schema_version: "2.0"` key will appear in the rewritten file.

### Operator recovery

**Malformed `project-state.yaml`:** `meminit state` commands will raise
`E_STATE_YAML_MALFORMED`. Fix the YAML syntax manually or delete the
file and let the queue start empty.

**Dependency cycle (`STATE_DEPENDENCY_CYCLE`):** Clear one edge of the
cycle using `meminit state set <ID> --clear-depends-on --root .` or
`meminit state set <ID> --clear-blocked-by --root .`.

**Self-dependency (`STATE_SELF_DEPENDENCY`):** Remove the self-reference
with `meminit state set <ID> --remove-depends-on <ID> --root .` (or the
equivalent `--remove-blocked-by` flag).

**Undefined dependency (`STATE_UNDEFINED_DEPENDENCY`):** This is a
warning, not an error. The entry is still saved but marked as not ready.
Create the target document or correct the dependency ID.

**Field too long (`STATE_FIELD_TOO_LONG`):** Shorten the `assignee` or
`next_action` value to within the allowed limit.

### Multi-agent `--assignee` routing

Use the `--assignee` flag to partition work across agents:

```bash
meminit state next --assignee agent:codex --root . --format json
meminit state next --assignee agent:claude --root . --format json
```

Each agent should set `--assignee` when claiming work:

```bash
meminit state set <ID> --impl-state "In Progress" --assignee agent:codex --root .
```

This creates a deterministic routing layer without requiring a central
coordinator. Agents can filter `state list` by assignee to see their
current workload.
