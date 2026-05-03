---
document_id: MEMINIT-FDD-012
type: FDD
docops_version: "2.0"
last_updated: 2026-04-19
status: Draft
title: Protocol Asset Governance
owner: GitCmurf
version: "0.2"
area: GOVERNANCE
description: "Protocol asset registry, ownership model, marker grammar, drift detection (protocol check), and safe remediation (protocol sync)."
keywords:
  - protocol
  - governance
  - drift
  - sync
  - agents-md
related_ids:
  - MEMINIT-PRD-005
  - MEMINIT-SPEC-006
---

# FDD-012: Protocol Asset Governance

## Problem Statement

Repo-local protocol files (AGENTS.md, skill manifests, bundled scripts) can drift from the canonical contract shipped with each Meminit release. Without governance:

- Agents may follow outdated or conflicting protocol instructions.
- CI pipelines have no automated way to detect protocol drift.
- Manual remediation risks destroying user-managed content.

## Feature Description

### Protocol Asset Registry

A frozen dataclass registry (`ProtocolAssetRegistry`) serves as the single source of truth for all governable protocol assets. Each asset declares:

- `id`: Unique identifier used in marker grammar and CLI flags.
- `target_path`: Relative path within the repo root.
- `ownership`: Either `generated` (fully managed by Meminit) or `mixed` (managed region + user region).
- `file_mode`: Optional Unix permission mode (e.g., `0o755` for executable scripts).
- `render(project_name, repo_prefix)`: Produces the canonical payload with interpolated placeholders.

Three assets are registered by default:

| ID | Path | Ownership | File Mode |
|----|------|-----------|-----------|
| `agents-md` | `AGENTS.md` | mixed | None |
| `meminit-docops-skill` | `.agents/skills/meminit-docops/SKILL.md` | generated | None |
| `meminit-brownfield-script` | `.agents/skills/meminit-docops/scripts/meminit_brownfield_plan.sh` | generated | `0o755` |

### Marker Grammar

Mixed-ownership files use HTML comment markers to delimit the Meminit-managed region:

```html
<!-- MEMINIT_PROTOCOL: begin id=<asset_id> version=<semver> sha256=<hex64> -->
... managed content ...
<!-- MEMINIT_PROTOCOL: end id=<asset_id> -->
```

Validation rules (unparseable if violated):

- Begin marker must be the first non-blank line.
- Exactly one begin marker and one end marker.
- No protocol markers outside the managed region.

### Drift Classification

Six outcomes in classification order (matches `classify_drift` in
`protocol_assets.py`):

1. **Missing**: Target file absent.
2. **Aligned**: Content matches canonical (after normalization).
3. **Legacy**: No markers found (pre-protocol state).
4. **Unparseable**: Markers are malformed (preamble, duplicates,
   missing end, mismatched IDs). Detected before tampered/stale
   checks so that structural corruption is reported first.
5. **Tampered**: Managed region hash doesn't match recorded hash in
   begin marker.
6. **Stale**: Self-consistent markers but version or hash differs
   from canonical.

Any `<!-- MEMINIT_PROTOCOL:` comment outside the managed region is
rejected. Plain prose mentioning `MEMINIT_PROTOCOL` (without the HTML
comment syntax) is allowed.

### Commands

- `meminit protocol check [--asset ID...]`: Read-only drift detection.
- `meminit protocol sync [--asset ID...] [--no-dry-run] [--force]`: Safe remediation.

`--dry-run` is the default for sync. `--force` allows overwriting tampered assets.

**Dry-Run and Apply Semantics:**

- `data.assets[]` always includes an `action` (e.g., `"noop"`, `"rewrite"`, `"refuse"`).
- In dry-run mode, `violations` represent drift when `success` is false.
- In apply mode (`--no-dry-run`), `violations` are generated for assets that were refused.
- `data.applied` is true only when a write or file-mode repair actually occurred and the command is not a dry run.
- Refused assets are represented both in `assets[].action == "refuse"` and, when appropriate, in `violations`.

### User Content Preservation

For mixed-ownership assets, sync preserves user-managed bytes verbatim (byte-identical, no line-ending normalization). User content is extracted from after the end marker (or the entire file for legacy assets) and appended to the freshly rendered managed region.

### Atomic Writes

All writes use exclusive temp-file creation (`os.open` with `O_CREAT | O_EXCL`) followed by `os.replace` for atomic replacement, preventing partial writes from corrupting files.

### Non-Fatal Diagnostics

The protocol subsystem emits non-fatal warnings for operator awareness:

- `PROTOCOL_SYNC_FORCE_USED`: Emitted when `meminit protocol sync --force` is used. This warns the operator that tampered assets may have been overwritten. It is not an error and does not affect the `success` flag if all requested assets were successfully synced or refused according to the force policy.

## Acceptance Criteria

1. `meminit protocol check --format json` reports drift status for all governed assets.
2. `meminit protocol sync --no-dry-run --format json` rewrites drifted assets to canonical.
3. Tampered assets require `--force`; unparseable assets always refuse.
4. Second sync is idempotent (all noop).
5. User content in mixed-ownership files is preserved byte-identical.
6. Init consumes the registry as single source of truth for all three assets.
7. Contract-matrix tests auto-include both commands.
8. 5 PROTOCOL_* error codes registered in MEMINIT-SPEC-006.

## Testing

Fixture scenarios (F01-F17) are code-generated by `tests/fixtures/protocol/conftest.py` rather than stored as checked-in directory trees. This was an intentional deviation from plan-012 §3.6.1: code-generated fixtures avoid byte-level diff noise, stay deterministic via the same render/normalize paths as production code, and serve as executable documentation of each drift outcome.

## External Testbed Validation

Per plan-012 §3.4 acceptance criterion #3, the external testbed must validate that `protocol check` and `protocol sync` work cleanly on a real brownfield repo. Validation steps:

```bash
cd <AIDHA_REPO>
meminit protocol check --root . --format json
meminit protocol sync --root . --no-dry-run --format json
meminit protocol check --root . --format json
```

Expected: first check shows drift (missing or legacy assets), sync remediates, second check shows all aligned.

Status: **completed** on 2026-04-19 against `../AIDHA` using the acceptance suite in `scripts/acceptance/test_meminit_phase1_contract.py`. The validated flow was `meminit protocol check --root . --format json`, `meminit protocol sync --root . --no-dry-run --format json`, then `meminit protocol check --root . --format json`, with the final check reporting all governed assets aligned.

## References

- MEMINIT-PRD-005: Agent Interface v2 (FR-6)
- MEMINIT-SPEC-006: ErrorCode Enum (Protocol category)
- MEMINIT-PLAN-012: Phase 3 Detailed Implementation Plan
