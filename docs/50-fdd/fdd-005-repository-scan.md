---
document_id: MEMINIT-FDD-005
type: FDD
title: Repository Scan (meminit scan)
status: Draft
version: 0.1
last_updated: 2025-12-26
owner: GitCmurf
docops_version: 2.0
---

# FDD: Repository Scan (meminit scan)

## Feature Description

Provide a read-only “brownfield assessment” that inspects an existing repo and emits a machine-readable plan for DocOps adoption.

## User Value

- Reduces time-to-first-green by identifying existing docs layout and suggesting configuration overrides.
- Provides agent-friendly JSON output for migration tooling.

## Functional Scope (v0.1)

- Command: `meminit scan --root .`
- Output: JSON report to stdout; optional `--output` to write a report file.
- Detection:
  - Determine docs root from `docops.config.yaml` or infer `docs/` if present.
  - Count Markdown files under docs root.
  - Suggest `type_directories` overrides when common alternates are detected (e.g., `docs/adrs` for ADRs), using configured defaults when present.
  - Note potential ambiguity when multiple candidate directories are present.
- Safety: read-only; no file mutations.

## Non-goals (v0.1)

- Automatic config writes.
- Deep semantic analysis of document contents.
- Enforcement or fixing (handled by `meminit check`/`fix`).

## Implementation Notes

- Use case: `src/meminit/core/use_cases/scan_repository.py`
- CLI: `meminit scan` in `src/meminit/cli/main.py`

## Tests

- Suggests `ADR` directory override when `docs/adrs` exists.
- Reports missing docs root if no docs directory and no config.
- Reports ambiguous ADR directories when both `docs/adrs` and `docs/decisions` exist.
