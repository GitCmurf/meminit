---
document_id: MEMINIT-SPEC-001
owner: Engineering Lead
approvers: GitCmurf
status: Draft
version: 0.1
last_updated: 2025-12-15
title: Meminit Architecture
type: SPEC
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-001
> **Owner:** Engineering Lead
> **Approvers:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Type:** SPEC

# 3. Design & Architecture

## 3.1 High-level components

**Core Library** (`meminit.core`)
Config loader/validator (org + repo).
Document model (frontmatter + body).
ID generator and validator.
Directory mapping logic.
Validation engine.

**CLI** (`meminit.cli`)
Arg parsing.
Delegates to core functions.
Handles output modes (human vs JSON).

**Templates module** (`meminit.templates`)
Loads templates from repo; falls back to org-level defaults.
Performs variable substitution.

**Index module** (`meminit.index`)
Scans docs/ and builds index JSON.

**Migration module** (`meminit.migration`)
Heuristics for mapping existing files to types/areas.
Generates YAML stubs.

**Integration helpers**
Pre-commit hook public script (`meminit-check`).
CI examples (GitHub Actions YAML).

## 3.2 Data structures

    `OrgConfig` (docops\_version, allowed\_types, default\_directories).
    `RepoConfig` (docops\_version, config\_version, repo\_prefix, areas, types, directories, kg\_tags).
    `Document`
        `document\_id`, `owner`, `approvers`, `status`, `last\_updated`, `version`, `type`, `docops\_version`, plus extra.
        parsed body as simple string (no need for AST initially).

## 3.3 ID generation algorithm (pseudo)

```pseudocode

inputs: repo\_prefix, area, type, repo\_config, existing\_docs

if type requires sequence (adr, fdd):
    candidates = all document\_ids starting with "<repo\_prefix>-<area>-<TYPE>-"
    seqs = parse trailing three-digit codes
    next\_seq = (max(seqs) or 0) + 1
    seq\_str = zero-pad(next\_seq, 3)
    id = f"{repo\_prefix}-{area}-{TYPE.upper()}-{seq\_str}"
else:
    id = f"{repo\_prefix}-{area}-{TYPE.upper()}"
    if id already exists:
        error unless user supplied explicit id

```

## 3.4 Validation engine

Checks for each file:
YAML frontmatter present.
Required keys present and valid.
`document\_id` matches `<REPO\_PREFIX>-<AREA>-<TYPE>\[-SEQ]`.
Area ∈ config.
Type ∈ config/org types.
Path matches directory mapping for type.
Optionally cross-check `docops\_version` consistency.
Collect violations per file; emit as structured data.
