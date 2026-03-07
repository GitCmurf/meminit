---
document_id: MEMINIT-PLAN-006A
owner: GitCmurf
status: Draft
version: "0.1"
last_updated: 2026-03-07
title: "P3.1 Scope Decision: Org-Level Config"
type: PLAN
docops_version: "2.0"
area: Planning
description: "Scope and architecture boundary for org-level config (P3.1 from MEMINIT-PLAN-006)"
keywords:
  - org-config
  - scope
  - deferred
  - architecture
related_ids:
  - MEMINIT-PLAN-006
  - MEMINIT-PRD-001
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-PLAN-006A
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Type:** Planning

# P3.1 Scope Decision: Org-Level Config

## 1. Background

This note documents the scope decision for P3.1 (Confirm scope and architecture boundary) from MEMINIT-PLAN-006. Org-level config is a valid deferred requirement from MEMINIT-PRD-001 (line 79: "Not Yet Implemented: Org-level config file (`org-docops.config.yaml`)").

## 2. Why This Is Being Deferred

The current repository operates primarily as a single-repo tool. The immediate priority is closing the PRD-006 contract gap (P1 in MEMINIT-PLAN-006) because:

1. Public contract drift already exists between PRD/spec and implementation
2. The Templates v2 feature set is incomplete without migration tooling (P2)
3. Multi-repo org-level config provides diminishing value until the single-repo experience is solid

Org-level config will become a higher priority when:

- Active multi-repo adoption begins
- Teams request shared defaults across repositories
- CI/CD pipelines need org-wide policy enforcement

## 3. Minimal Useful Product Shape for V1

### Option A: Shared Defaults (Recommended for V1)

The first implementation should support only **shared defaults** — org-level configuration that repositories can override. This provides immediate value:

- Organization-wide template defaults
- Standardized document type directories
- Default owner/approver metadata
- Schema validation rules

### Option B: Multi-repo Inventories (Deferred)

Multi-repo inventory tracking (org-wide document tracking, cross-repo linking) is explicitly deferred beyond v1. This requires:

- Network or filesystem-based org config discovery
- Cross-repo index aggregation
- Significant additional complexity

## 4. Precedence Rules

The following precedence hierarchy MUST govern the implementation:

```
CLI args > Repo config > Org config > Defaults
```

具体说明:

| Level       | Source                                      | Override Ability     |
| ----------- | ------------------------------------------- | -------------------- |
| 1 (highest) | CLI arguments                               | All other levels     |
| 2           | Repo-level config (`meminit.config.yaml`)   | Overrides org config |
| 3           | Org-level config (`org-docops.config.yaml`) | Provides defaults    |
| 4 (lowest)  | Built-in defaults                           | Fallback only        |

Implementation requirements:

- All config loading must fail gracefully if org config is absent
- Repo config MUST always take precedence over org config
- CLI args MUST always take precedence over all config files
- Precedence must be deterministic and testable

## 5. Explicit Non-Goals for V1

The following are explicitly NOT in scope for v1:

1. **Network-based config discovery** — org config is a local file, not fetched at runtime
2. **Cross-repo linking** — no aggregation of indices across repositories
3. **Multi-repo inventory** — no org-wide document tracking
4. **Runtime config refresh** — config is loaded once per command invocation
5. **Org-level template storage** — templates remain repo-local

## 6. File Location Convention

For v1, org-level config should be located at:

```
<org-root>/org-docops.config.yaml
```

Repositories reference org config via a path in their repo-level config:

```yaml
# repo meminit.config.yaml
org_config_path: ../org-docops.config.yaml # relative path
```

The relative path resolution is from the repo config file location.

## 7. Future Consideration: Option B Shape

If multi-repo inventories become a requirement, the architecture would need:

- A separate discovery mechanism for org-wide config location
- Caching layer for cross-repo index aggregation
- Permission handling for org-root access
- Network/filesystem hybrid resolution

This should be re-evaluated when actual multi-repo use cases are identified.

## 8. References

- Task: P3.1 in [MEMINIT-PLAN-006](./plan-006-atomic-task-list.md)
- Original requirement: [MEMINIT-PRD-001](../10-prd/prd-001-meminit-tooling-ecosystem.md) line 79
- Related: [MEMINIT-STRAT-001](../02-strategy/strat-001-project-meminit-vision.md)
