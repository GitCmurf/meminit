---
document_id: MEMINIT-SPEC-006
type: SPEC
title: ErrorCode Enum Specification
status: Draft
version: "0.1"
last_updated: 2026-02-24
owner: Product Team
docops_version: "2.0"
area: Agentic Integration
description: "Canonical ErrorCode inventory, extensibility process, and governance rules for the meminit CLI error code enum."
keywords:
  - error
  - enum
  - agent
  - contract
related_ids:
  - MEMINIT-PRD-003
  - MEMINIT-SPEC-004
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** MEMINIT-SPEC-006
> **Owner:** Product Team
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-02-24
> **Type:** SPEC
> **Area:** Agentic Integration

# SPEC: ErrorCode Enum

## 1. Purpose

This document defines the canonical `ErrorCode` enum for the Meminit CLI, the process for adding new codes, and the governance rules that keep the enum stable for agent consumers.

Plain English: This is the single list of all error codes that agents can encounter, plus the rules for adding new ones.

## 2. Scope

In scope:

- The full `ErrorCode` enum inventory.
- The process for proposing, reviewing, and adding new error codes.
- Stability guarantees for consumers.

Out of scope:

- Warning and violation codes (those are rule codes, not operational error codes).
- Runtime error recovery strategies.

## 3. Canonical ErrorCode Inventory

The canonical implementation is `src/meminit/core/services/error_codes.py`. The table below mirrors the current enum values.

| Code                       | Category   | Description                                                     |
| -------------------------- | ---------- | --------------------------------------------------------------- |
| `DUPLICATE_ID`             | Shared     | A document_id already exists in the index or namespace.         |
| `INVALID_ID_FORMAT`        | Shared     | The document_id does not match the `PREFIX-TYPE-SEQ` pattern.   |
| `INVALID_FLAG_COMBINATION` | Shared     | Mutually exclusive or invalid CLI flags were provided.          |
| `CONFIG_MISSING`           | Shared     | `docops.config.yaml` is missing or the repo is not initialized. |
| `PATH_ESCAPE`              | Shared     | A path argument resolves outside the repo root or docs root.    |
| `UNKNOWN_TYPE`             | New-only   | The requested document type is not in the type directory map.   |
| `UNKNOWN_NAMESPACE`        | New-only   | The requested namespace is not configured.                      |
| `FILE_EXISTS`              | New-only   | The target file already exists (non-idempotent create).         |
| `INVALID_STATUS`           | New-only   | The provided status value is not valid.                         |
| `INVALID_RELATED_ID`       | New-only   | A related_id references a non-existent document.                |
| `TEMPLATE_NOT_FOUND`       | New-only   | No template found for the requested document type.              |
| `SCHEMA_INVALID`           | Check-only | The metadata schema JSON is malformed or unreadable.            |
| `LOCK_TIMEOUT`             | Shared     | A file lock could not be acquired within the timeout period.    |
| `FILE_NOT_FOUND`           | Check-only | A targeted file path does not exist.                            |
| `MISSING_FRONTMATTER`      | Check-only | A governed markdown file has no YAML frontmatter block.         |
| `MISSING_FIELD`            | Check-only | A required frontmatter field is absent.                         |
| `INVALID_FIELD`            | Check-only | A frontmatter field has an invalid value or type.               |
| `OUTSIDE_DOCS_ROOT`        | Check-only | A file is outside the configured docs root.                     |
| `DIRECTORY_MISMATCH`       | Check-only | A file is in the wrong type directory for its declared type.    |
| `UNKNOWN_ERROR`            | Shared     | An unexpected error not covered by a specific code.             |

## 4. Adding a New Error Code

1. **Open a PR** with the proposed code added to the `ErrorCode` enum in `error_codes.py`.
2. **Update this spec** by adding the code to the table in §3 with its category and description.
3. **Add tests** that exercise the new error code path and verify the JSON error envelope includes the new code.
4. **PR review** must confirm the code is not a duplicate or synonym of an existing code.

## 5. Stability Guarantees

- Error codes MUST NOT be removed or renamed once released. They may be deprecated with a notice in this spec.
- The `code` string value MUST remain stable across versions. Agents can safely match on these strings.
- The `message` string is for human consumption and MAY change between versions.

## 6. Compliance Checklist

1. All operational errors emitted by the CLI use a code from this enum.
2. New error codes follow the addition process in §4.
3. No error code is removed or renamed without a deprecation period.

Plain English: If these are true, error codes are governed correctly.
