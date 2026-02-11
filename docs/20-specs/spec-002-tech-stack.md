---
document_id: MEMINIT-SPEC-002
owner: Engineering Lead
approvers: GitCmurf
status: Draft
version: 0.1
last_updated: 2026-01-29
title: Meminit Tech Stack
type: SPEC
docops_version: 2.0
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-002
> **Owner:** Engineering Lead
> **Approvers:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Type:** SPEC

# 4. Tech Stack

- **Language**: Python 3.11+ (good YAML & markdown libraries, easy cross-platform).

- **Core libs**:

  - `pyyaml` (YAML parsing).
  - `python-frontmatter` or custom for frontmatter parsing.
  - `click` or `typer` for CLI (typer gives nice type hints).
  - `pathlib` for file paths.

- **Packaging**:

  - Standard Python package (`meminit`).
  - Global CLI install via `pipx install /path/to/Meminit` (not published on PyPI yet).
  - Dev/test in this repo uses a local venv with editable install (`pip install -e .[dev]`).

- **Testing**:
  - `pytest`.
  - Use `tmp_path` to simulate repos in tests.
