---
document_id: MEMINIT-TASK-003
type: TASK
title: Mypy typing hygiene
status: Draft
version: "0.1"
last_updated: "2026-05-30"
owner: __TBD__
area: PLAN
docops_version: "2.0"
template_type: task-standard
template_version: "2.0"
description: Task implementation record.
keywords:
  - task
---

> **Document ID:** MEMINIT-TASK-003
> **Owner:** **TBD** > **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-05-30
> **Type:** TASK
> **Area:** PLAN
> **Description:** Task implementation record.

<!-- MEMINIT_SECTION: title -->
<!-- AGENT: The title should state the implementation objective clearly. -->

# TASK: Mypy typing hygiene

<!-- MEMINIT_SECTION: executive_summary -->
<!-- AGENT: Summarize the task, why it exists, and the intended completion state. -->

## 0. Executive Summary

`mypy src` reported a large failure set after strict missing-import and `Any`
checks were enabled. This task records the cleanup needed to keep type checking
as a useful code-quality gate while removing third-party typing noise.

<!-- MEMINIT_SECTION: review_basis -->
<!-- AGENT: List source reports, live commands, and evidence used to scope the task. -->

## 1. Review Basis

- User report from `mypy src` showing 91 errors across 24 files.
- Local confirmation with `./.venv/bin/mypy src`.
- Local comparison with `./.venv/bin/mypy src --ignore-missing-imports`, which
  reduced third-party import noise but still exposed local typing defects.

<!-- MEMINIT_SECTION: current_state -->
<!-- AGENT: Distinguish live defects from stale or already-corrected findings. -->

## 2. Current State

- The mypy settings are intentionally strict enough to catch local defects:
  `warn_return_any`, `check_untyped_defs`, and `ignore_missing_imports = false`
  should remain enabled.
- PyYAML and jsonschema have published stub packages and should be represented
  in development dependencies.
- `python-frontmatter` has no bundled typing marker, so Meminit needs a narrow
  local stub for the API surface it uses.

<!-- MEMINIT_SECTION: work_items -->
<!-- AGENT: Break the work into prioritized, implementable items with definitions of done. -->

## 3. Work Items

- Add development typing dependencies and configure mypy to read local stubs.
- Add a local `frontmatter` stub covering the used `Post`, handler, load, loads,
  dump, and dumps APIs.
- Fix local nullability, collection inference, `Any` return, and variable reuse
  issues without broad mypy ignores.
- Keep behavior unchanged except where a type error reveals a genuine validation
  gap.

<!-- MEMINIT_SECTION: verification_matrix -->
<!-- AGENT: List the exact commands and evidence required before closure. -->

## 4. Verification Matrix

- `./.venv/bin/mypy src`
- Focused tests for touched services, use cases, and CLI behavior.
- Full `./.venv/bin/pytest -q` when focused checks pass.
- `./.venv/bin/meminit check --format json`

<!-- MEMINIT_SECTION: version_history -->
<!-- AGENT: Track version changes with dates, authors, and change summaries. -->

## 5. Version History

| Version | Date       | Author  | Changes       |
| ------- | ---------- | ------- | ------------- |
| 0.1     | 2026-05-30 | **TBD** | Initial draft |
