---
document_id: MEMINIT-FDD-013
type: FDD
title: Agent Work Queue Queries
status: Draft
version: '0.1'
last_updated: '2026-04-21'
owner: GitCmurf
docops_version: '2.0'
template_type: fdd-standard
template_version: '2.0'
description: Work queue query surface for agentic coding agents over project-state.yaml v2 schema.
keywords:
  - work-queue
  - state
  - readiness
  - selection
  - blockers
related_ids:
  - MEMINIT-PLAN-013
  - MEMINIT-PRD-005
  - MEMINIT-PRD-007
  - MEMINIT-SPEC-006
  - MEMINIT-SPEC-008
---

> **Document ID:** MEMINIT-FDD-013
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.1
> **Last Updated:** 2026-04-21
> **Type:** FDD

# MEMINIT-FDD-013: Agent Work Queue Queries

## 1. Executive Summary

This FDD defines the v2 state schema, deterministic readiness and selection algorithms, JSON payload shapes, and CLI command surfaces that allow agentic coding agents to query and manage a repo-local work queue derived from `project-state.yaml` and the Phase 2 index graph.

## 2. Feature Overview

Phase 4 introduces a deterministic work-queue layer over `project-state.yaml`. Agents can ask "what is ready next?", "what is blocked and by what?", and "list entries filtered by readiness/priority/assignee" — all producing byte-identical output for identical inputs.

The queue is built on three pillars:
- A **v2 state schema** with five optional planning fields per entry
- **Derived fields** (`ready`, `open_blockers`, `unblocks`) computed on read, never persisted
- **Deterministic selection and filtering** algorithms with total ordering

## 3. User Stories

| Story | As a | I want to | So that | Acceptance Criteria |
|-------|------|-----------|---------|---------------------|
| US-1 | Agent | Call `state next` | I know which item to pick up | Returns one entry or documented empty reason |
| US-2 | Agent | Call `state blockers` | I understand why nothing is ready | Returns blocked entries with one-level blocker resolution |
| US-3 | Agent | Filter `state list` by ready/blocked/assignee/priority | I get a targeted view | Filter never expands result set beyond unfiltered |
| US-4 | Operator | Set priority, depends_on, blocked_by on entries | Planning fields are tracked | `state set` persists v2 fields with default omission |

## 4. Functional Requirements

### v2 State Schema

- **FR-1**: `project-state.yaml` MUST carry `state_schema_version: "2.0"` on write.
- **FR-2**: Legacy (v1) files MUST load with default values for all new fields.
- **FR-3**: Defaults MUST be omitted on write (`P2` priority, empty lists, unset assignee/next_action).

### Planning Fields

- **FR-4**: `priority` MUST be one of `P0`, `P1`, `P2`, `P3`. Default `P2` omitted on write.
- **FR-5**: `depends_on` and `blocked_by` MUST be sorted lexicographically on save.
- **FR-6**: `assignee` MUST not exceed 120 characters.
- **FR-7**: `next_action` MUST not exceed `MAX_NOTES_LENGTH` (500) characters and MUST not contain newlines.

### Derived Fields

- **FR-8**: `ready` MUST be `true` iff `impl_state == "Not Started"` and all `depends_on` and `blocked_by` targets resolve to entries with `impl_state == "Done"`.
- **FR-9**: `open_blockers` MUST be the sorted subset of `depends_on ∪ blocked_by` whose targets are not `Done`.
- **FR-10**: `unblocks` MUST list document IDs whose `depends_on` or `blocked_by` reference the entry.

### Selection Algorithm

- **FR-11**: `state next` MUST select the ready entry winning the ordered comparison: priority ascending, unblocks count descending, updated ascending, document_id ascending.
- **FR-12**: When no entry is ready, `state next` MUST return `data.entry = null` with `data.reason = "queue_empty"` or `"state_missing"`.

### Error Codes

- **FR-13**: Seven `STATE_*` error codes MUST be registered in `ErrorCode` with complete `ERROR_EXPLANATIONS` entries.

## 5. Technical Design

### Architecture

```
project-state.yaml (v2)
        ↓ load
ProjectState + ProjectStateEntry (5 planning fields)
        ↓ compute_derived_fields()
DerivedEntry (ready, open_blockers, unblocks)
        ↓
state next / state blockers / state list
```

### Data Models

**ProjectStateEntry** extended fields:

| Field | Type | Default | On-disk |
|-------|------|---------|---------|
| `priority` | `Optional[str]` | `None` (P2) | Omitted when P2 |
| `depends_on` | `Tuple[str, ...]` | `()` | Omitted when empty |
| `blocked_by` | `Tuple[str, ...]` | `()` | Omitted when empty |
| `assignee` | `Optional[str]` | `None` | Omitted when None |
| `next_action` | `Optional[str]` | `None` | Omitted when None |

**DerivedEntry** (never persisted):

| Field | Type | Always emitted |
|-------|------|----------------|
| `ready` | `bool` | Yes |
| `open_blockers` | `Tuple[str, ...]` | Yes |
| `unblocks` | `Tuple[str, ...]` | Yes |

### JSON Payload Shapes

**state next** `data`:
- `entry`: selected item (with planning + derived fields) or `null`
- `selection`: `{rule, candidates_considered, filter}`
- `reason`: `null` or `"queue_empty"` / `"state_missing"`

**state blockers** `data`:
- `blocked`: array of `{document_id, impl_state, priority, assignee, open_blockers: [{id, impl_state, known}]}`
- `summary`: `{total_entries, blocked, ready}`

### Validation

Planning fields are validated at mutation time via `validate_planning_fields()`. Fatal issues halt the write; warnings are attached to the response.

Cycle detection uses iterative DFS, same pattern as `_check_supersession_cycle`.

## 6. Dependencies

- Phase 2 index graph: `known_ids` sourced from index `nodes` array
- `ErrorCode` / `ERROR_EXPLANATIONS` / `exit_code_for_error`: four-location sync
- `sanitization.MAX_NOTES_LENGTH` and `MAX_ASSIGNEE_LENGTH`: field bounds
- `atomic_write` + `ensure_safe_write_path`: state file persistence safety

## 7. Open Questions

None — all design decisions resolved in MEMINIT-PLAN-013.

## 8. Version History

| Version | Date       | Author   | Changes       |
| ------- | ---------- | -------- | ------------- |
| 0.1     | 2026-04-21 | Codex    | Initial draft |
