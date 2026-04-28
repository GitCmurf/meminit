---
document_id: MEMINIT-PLAN-013
type: PLAN
title: Phase 4 Detailed Implementation Plan
status: Draft
version: '0.10'
last_updated: '2026-04-28'
owner: GitCmurf
docops_version: '2.0'
area: AGENT
description: Detailed implementation plan for MEMINIT-PLAN-008 Phase 4 work queue
  layer.
keywords:
- phase-4
- planning
- state
- work-queue
related_ids:
- MEMINIT-PLAN-008
- MEMINIT-PLAN-003
- MEMINIT-PLAN-011
- MEMINIT-PRD-005
- MEMINIT-PRD-007
- MEMINIT-SPEC-006
- MEMINIT-SPEC-008
- MEMINIT-RUNBOOK-006
---

> **Document ID:** MEMINIT-PLAN-013
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.10
> **Last Updated:** 2026-04-28
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Detailed implementation plan for MEMINIT-PLAN-008 Phase 4 work queue layer.

# PLAN: Phase 4 Detailed Implementation Plan

## Context

MEMINIT-PLAN-008 defines Phase 4 as the point where Meminit moves from
dashboard-oriented state reporting toward an actionable work-queue layer for
agentic coding agents.

This phase depends on Phase 2 (Repository Graph) because readiness, blockers,
and next-work queries become much more valuable once the index exposes
document-to-document edges. The goal is to let an agent ask deterministic
questions such as "what is ready next?" or "what is blocked and by what?"
without inventing its own local planning model.

Phase 2 status:

- Phase 2 shipped a graph artifact at `index_version: "1.0"` with separate
  `nodes` and `edges` arrays, deterministic extraction, and `GRAPH_*`
  integrity diagnostics (MEMINIT-PLAN-011 v0.6).
- Phase 4 consumes the `nodes` array to resolve planning dependencies to
  known documents and reuses the graph integrity vocabulary where it
  applies to state.

Definition:

- The **work queue** is the subset of governed documents whose implementation
  is tracked in `project-state.yaml` together with the planning fields
  introduced by this phase.
- A work item is **ready** when it is not done, has no open hard
  dependencies, and carries no runtime blockers.
- The **next action** is the single deterministically-selected ready item
  an agent should pick up, given the current state and a documented
  selection rule set.

Adoption note:

- The installed base outside Meminit remains only one explicit testbed.
- That makes it reasonable to evolve `project-state.yaml` more directly than
  a broadly distributed stable product would, provided upgrade impact is
  documented explicitly.

Backward-compatibility posture:

- MEMINIT-PLAN-008 waives the blanket compatibility requirement for
  pre-alpha vNext work. For Phase 4, this means the state file may be
  bumped to a new schema version (`state_schema_version: "2.0"`) and the
  on-disk shape may change.
- Legacy state files (no `state_schema_version` field) are accepted on
  read and mapped to `2.0` with default values for the new planning
  fields. There is no tooling requirement to back-port writes to the
  legacy shape.
- No v1 compatibility is promised for read callers that consume the raw
  YAML directly. Callers that read state through the CLI (`state get`,
  `state list`, `state next`, `state blockers`) see the documented v2
  shape regardless of the on-disk version.

Determinism requirement:

- Every query surface introduced by this phase must produce byte-identical
  output for identical inputs: sorted entry arrays, stable tie-breaking in
  the `next` selector, canonical UTC normalization for stored timestamps,
  no wall-clock timestamps in hashed payloads, and no reliance on
  filesystem mtime.
- Determinism is what makes the work queue safe for agent repair loops: a
  second `state next` call with no intervening mutation must return the
  same result.

Repository initialization boundary:

- All `meminit state*` query and mutation commands require an initialized
  repository config. They MUST fail fast with `CONFIG_MISSING` when
  `docops.config.yaml` is missing, malformed, or not a regular file instead
  of guessing defaults.
- Missing `project-state.yaml` is not an error by itself. In that case the
  query commands return the documented empty-state payloads.

Non-goal framing:

- Phase 4 does not introduce autonomous scheduling. It provides the
  primitives an orchestrator needs to schedule deterministically.
- Phase 4 does not replace external issue trackers. It defines a
  repo-local queue that agents can consult without round-tripping through
  a tracker API.

Quality bar:

- Phase 4 must land as small, reviewable slices that each carry code,
  docs, and tests together.
- The default development loop is test-first: write the regression,
  implement the minimal fix, and then run the relevant unit, contract,
  and doc-validation checks before merge.
- Every slice must pass the targeted unit suite, `meminit check` on all
  touched governed docs, and the contract matrix before it can be
  considered done.

## 1. Purpose

Define the detailed implementation steps for Phase 4 of MEMINIT-PLAN-008 so
that Meminit can provide a deterministic, queryable work-queue layer over
`project-state.yaml` and the Phase 2 repository graph.

## 2. Scope

In scope:

- a v2 schema for `project-state.yaml` with optional planning fields
- deterministic readiness, blocker, and next-action selection rules
- new read-only query commands (`state next`, `state blockers`, and
  `state list` filter extensions)
- extensions to the existing `state set` mutation surface to write the
  new fields
- targeted validation rules expressed as `STATE_*` error codes with
  matching `explain` entries
- index, catalog, and kanban alignment for the enriched state
- fixture-driven determinism tests
- migration guidance from the v1 state shape

Out of scope:

- protocol governance (Phase 3)
- semantic search
- streaming and NDJSON delivery (Phase 5)
- non-deterministic prioritization, ranking heuristics, or autonomous
  scheduling
- issue tracker integration outside the repo-owned state model
- cross-repo or cross-namespace queue aggregation
- automatic dependency inference from `related_ids` (declared explicitly as
  a non-goal because `related_ids` are advisory; see §3.4.1)

### 2.1 Engineering Constraints

The implementation must follow the current Meminit codebase conventions
rather than inventing a parallel pattern:

- keep the shared v3 agent envelope stable and place query-specific
  payloads under `data` unless a shared-envelope change is truly
  required; any envelope change triggers the v4 bump rules in
  MEMINIT-PLAN-010
- reuse `agent_output_options`, `agent_repo_options`,
  `command_output_handler`, `ErrorCode`, `ERROR_EXPLANATIONS`, and the
  capabilities registry (`register_capability` in
  `src/meminit/cli/shared_flags.py`) rather than introducing
  command-local contract logic
- resolve repo metadata through the standard repo-config loader for
  initialized repos; do not guess `project_name`/`repo_prefix` from
  filesystem names or malformed config files
- reuse the existing `ProjectState`, `ProjectStateEntry`, and
  `load_project_state` / `save_project_state` infrastructure in
  `src/meminit/core/services/project_state.py`; extend these rather than
  forking a parallel entity
- reuse `_resolve_document_id` in
  `src/meminit/core/use_cases/state_document.py` for shorthand handling
  on all new commands
- reuse the existing atomic write path already employed by
  `save_project_state` and validate every write target with
  `ensure_safe_write_path`
- keep derived fields (such as `ready`) computed on read, not persisted,
  so the on-disk artifact remains the single source of truth and
  reproducible from the raw inputs
- keep function size inside the repository's soft 40-line limit and
  prefer small, single-responsibility helpers over one large selector
  function

Security:

- State writes must validate that the target remains within the
  repository root.
- `state set` must reject inputs that violate the sanitization bounds
  already enforced on `notes` (see `sanitization.MAX_NOTES_LENGTH`) and
  apply the same bounds to `next_action`.
- State commands must use canonical UTC timestamps for comparison and
  serialization. `updated` should be normalized on load/save so the
  `state next` tie-break rule does not depend on local timezone offsets.

### 2.2 Governed Document Outputs

Phase 4 implementation is not done when the code lands. The following
governed-document updates are required for closeout, consistent with
MEMINIT-PLAN-008 Section 7:

| Action | Type | Document | Required update |
| ------ | ---- | -------- | --------------- |
| Update | PRD | `MEMINIT-PRD-005` | Add `state next`, `state blockers`, and the enriched `state list` filter set to the Agent Interface v2 command inventory |
| Update | PRD | `MEMINIT-PRD-007` | Document how the richer state surfaces in the project-state dashboard, catalog, and kanban views |
| Update | SPEC | `MEMINIT-SPEC-006` | Register the new `STATE_*` error codes and their normative `explain` semantics |
| Update | SPEC | `MEMINIT-SPEC-008` | Extend the repo-aware command enum in `agent-output.schema.v3.json` to include `state next` and `state blockers` |
| New | FDD | Agent Work Queue Queries | Define the v2 state schema, the readiness and selection algorithms, JSON payload shapes, and integration with the index graph |
| Update | RUNBOOK | `MEMINIT-RUNBOOK-006` | Document the upgrade from v1 state, operator recovery paths, and how agents should loop on the queue |
| Conditional update | PLAN | `MEMINIT-PLAN-003` | Only if Phase 4 sequencing or completion criteria move materially during delivery |

Every delivery slice in this phase must satisfy the repository's
atomic-unit rule: code, docs, and tests move together.

## 3. Work Breakdown

### 3.1 Workstream A: State Model v2 Schema Definition

Problem:

- The current state entries in `src/meminit/core/services/project_state.py`
  carry only `impl_state`, `updated`, `updated_by`, and `notes`. That shape
  supports implementation-state reporting but gives agents no way to ask
  structured planning questions.
- The `project-state.yaml` file has no version stamp, which would make any
  future schema change ambiguous to read.

#### 3.1.1 File-level metadata

Introduce a top-level `state_schema_version` key on `project-state.yaml`:

```yaml
state_schema_version: "2.0"
documents:
  MEMINIT-PRD-005:
    impl_state: In Progress
    updated: 2026-04-18T10:15:00+00:00
    updated_by: GitCmurf
    priority: P1
    depends_on:
      - MEMINIT-PLAN-011
    blocked_by: []
    assignee: agent:augment
    next_action: Wire capabilities registry entry for `state next`
    notes: Waiting on graph edges to stabilise
```

Rules:

- `state_schema_version` is mandatory on write for v2 files.
- On read, a missing `state_schema_version` is treated as `"1.0"` and
  automatically mapped to `2.0` in memory with default values for the new
  fields. The on-disk file is not silently rewritten; the caller receives
  the v2 shape.
- `updated` timestamps are normalized to UTC on load and persisted in
  canonical UTC form so comparison and serialization remain stable across
  time zones.
- The next mutation through `state set` persists the v2 shape, including
  the `state_schema_version: "2.0"` header. This makes the migration
  "write-triggered" rather than global, which matches existing conventions
  for mutable YAML artifacts in the repo.

#### 3.1.2 Entry-level planning fields

Extend `ProjectStateEntry` with five optional planning fields:

| Field         | Type     | Required | Default  | Validation                                                                                                            |
| ------------- | -------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| `priority`    | string   | no       | `P2`     | One of `P0`, `P1`, `P2`, `P3`. `P0` is highest. Omitted on disk when equal to the default.                            |
| `depends_on`  | string[] | no       | `[]`     | Each entry must be a valid document ID shape (`<PREFIX>-<TYPE>-<NNN>`). Duplicates collapsed. Sorted lexicographically on save. |
| `blocked_by`  | string[] | no       | `[]`     | Same shape as `depends_on`. Distinct list; see §3.1.4 for semantics.                                                  |
| `assignee`    | string   | no       | omitted  | Free-form string, max 120 characters. Recommended shapes: `agent:<name>`, `user:<login>`, `team:<slug>`.              |
| `next_action` | string   | no       | omitted  | Free-form string, max `sanitization.MAX_NOTES_LENGTH` characters. One line (no embedded newlines).                    |

Existing fields (`impl_state`, `updated`, `updated_by`, `notes`) are unchanged.

All five new fields are optional. Repos that do not use planning fields
see no change in the on-disk shape beyond the top-level
`state_schema_version` header, which satisfies MEMINIT-PLAN-008 §5.5
acceptance criterion 1 (state model remains optional for repos that do
not use advanced planning fields).

#### 3.1.3 Derived (read-only) fields

The following fields are computed on read and never persisted:

| Field           | Type     | Meaning                                                                                                                    |
| --------------- | -------- | -------------------------------------------------------------------------------------------------------------------------- |
| `ready`         | boolean  | `true` iff `impl_state` is `Not Started`, `depends_on` and `blocked_by` are empty or resolve to entries whose `impl_state` is `Done`. Always emitted. |
| `open_blockers` | string[] | Subset of `depends_on ∪ blocked_by` whose targets are not `Done`. Sorted lexicographically. Always emitted as an array, possibly empty. |
| `unblocks`      | string[] | Document IDs whose `depends_on` or `blocked_by` lists reference this entry. Sorted lexicographically. Always emitted as an array, possibly empty. |

Derivation rules are deterministic and purely a function of the stored
state plus the Phase 2 index. No wall-clock, filesystem mtime, or
randomness may be consulted.

#### 3.1.4 `depends_on` vs `blocked_by` semantics

Both fields block readiness. The distinction is intent and lifecycle:

- `depends_on` is a **declared structural** dependency: B depends on A's
  existence or completion because of the task definition. It is usually
  set once when the work item is added and rarely changes.
- `blocked_by` is a **discovered runtime** blocker: B was picked up but
  found to require A's completion first. It is expected to be added and
  cleared over the life of a work item.

This separation lets dashboards surface "planned dependencies" (stable,
structural) separately from "live blockers" (transient) without changing
the readiness semantics.

#### 3.1.5 Implementation tasks

1. Add `state_schema_version` constants (`STATE_SCHEMA_VERSION = "2.0"`,
   `STATE_SCHEMA_VERSION_LEGACY = "1.0"`) to
   `src/meminit/core/services/project_state.py`.
2. Extend the `ProjectStateEntry` dataclass with the five new optional
   fields. Keep it frozen.
3. Add a `DerivedStateView` helper (new module or co-located) that takes
   a `ProjectState` plus the index graph and produces `ready`,
   `open_blockers`, and `unblocks` for each entry.
4. Add a strict repo-config and state-path resolution helper for state
   commands so the queue layer fails fast on missing or malformed repo
   configuration instead of guessing defaults or falling back to the
   default docs path.
5. Update `save_project_state` to emit `state_schema_version` and to
   serialize the new fields only when they deviate from their default.
6. Update `load_project_state` to accept both legacy and v2 files and
   normalize to v2 in memory.
7. Document the v2 schema in the new FDD (§2.2) before any mutation or
   query code lands.

Acceptance criteria:

1. The v2 schema is published and reviewed before Workstreams B and C
   are finalized.
2. Legacy (v1) files round-trip through `load → v2 view → save` without
   losing information and without requiring operator intervention.
3. Defaults are omitted on write so files with no planning fields remain
   minimal and diff-friendly.
4. `DerivedStateView` is deterministic: two invocations on the same
   `ProjectState` and index produce equal results.
5. The v2 schema is expressible as JSON Schema (to be added to
   `docs/20-specs/` or the new FDD) and the schema is fixture-tested.

### 3.2 Workstream B: State Mutation, Migration, and Validation

Problem:

- A richer model is only useful if it can be updated safely and
  predictably, and if invalid planning inputs fail early with actionable
  diagnostics.

#### 3.2.1 Mutation surface decision

Extend `meminit state set` rather than introducing a parallel command
group. This keeps the mutation contract in one place and reuses the
existing `StateDocumentUseCase` path.

New optional flags on `state set`:

| Flag                                 | Behavior                                                                                                                                      |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `--priority <P0\|P1\|P2\|P3>`        | Set `priority`. Passing `--priority P2` with no prior value writes the default (no-op on serialized output).                                  |
| `--depends-on <ID>` (repeatable)     | Replace `depends_on` with the supplied list. Pass zero times with `--clear-depends-on` to empty the list.                                     |
| `--add-depends-on <ID>` (repeatable) | Additive; deduplicated against the existing list.                                                                                             |
| `--remove-depends-on <ID>`           | Remove the given ID if present. No-op otherwise.                                                                                              |
| `--clear-depends-on`                 | Empty the list.                                                                                                                               |
| `--blocked-by` family                | Same four-flag pattern for `blocked_by`.                                                                                                      |
| `--assignee <string>`                | Set `assignee`; pass the empty string to clear.                                                                                               |
| `--next-action <string>`             | Set `next_action`; pass the empty string to clear.                                                                                            |

Mutation rules:

- All mutations preserve the existing atomic-write behavior in
  `save_project_state`.
- `state set` is idempotent on the new fields: re-running the same
  command produces byte-identical file content.
- `state set` never reorders unrelated entries. The existing
  alphabetical `document_id` sort on save already guarantees this.
- Setting any planning field on a v1 file triggers the write-time
  migration to v2 (see §3.1.1).
- For each planning field family (`depends_on`, `blocked_by`), exactly
  one mutation mode is permitted per invocation: replace, additive, or
  clear/remove. Mixed modes on the same field must be rejected rather
  than inferred by flag order.

#### 3.2.2 Validation rules

Validation runs at mutation time and at read time. Fatal violations
return a non-zero exit code; non-fatal advisories are emitted through
`warnings[]` and `advice[]`.

Planning-field codes (`STATE_INVALID_PRIORITY`, `STATE_FIELD_TOO_LONG`,
`STATE_INVALID_DEPENDENCY_ID`, `STATE_SELF_DEPENDENCY`) use **dual
severity**: fatal when writing (mutation rejected by `state set`);
warning when reading (emitted through `warnings[]` by `state list`,
`state next`, `state blockers`, and `index` — command succeeds with
exit code 0). This is consistent with SPEC-006 and the
`ERROR_EXPLANATIONS` entries for these codes.

| Rule                                        | Code                            | Severity | Description                                                                                                                      |
| ------------------------------------------- | ------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Unknown priority value                      | `STATE_INVALID_PRIORITY`        | dual     | `priority` is not one of `P0..P3`. Fatal on write; warning on read.                                                              |
| Malformed dependency ID                     | `STATE_INVALID_DEPENDENCY_ID`   | fatal    | An entry in `depends_on` or `blocked_by` does not match `<PREFIX>-<TYPE>-<NNN>` shape.                                           |
| Self-dependency                             | `STATE_SELF_DEPENDENCY`         | fatal    | An entry references its own `document_id` in `depends_on` or `blocked_by`.                                                       |
| Dangling dependency target                  | `STATE_UNDEFINED_DEPENDENCY`    | warning  | A dependency target is not present in the index `nodes` array. The entry is still written; the warning is attached to the run. |
| Dependency cycle                            | `STATE_DEPENDENCY_CYCLE`        | fatal    | Following `depends_on ∪ blocked_by` edges from any entry produces a cycle.                                                       |
| Dependency with mismatched status           | `STATE_DEPENDENCY_STATUS_CONFLICT` | advice | Entry A is `Done` but lists B in `depends_on`/`blocked_by` where B is not `Done`. Advisory only; emitted through `advice[]`.   |
| `assignee` or `next_action` exceeds bounds  | `STATE_FIELD_TOO_LONG`          | dual     | Length exceeds 120 for `assignee` or `MAX_NOTES_LENGTH` for `next_action`. Fatal on write; warning on read.                      |
| Mixed mutation modes                        | `STATE_MIXED_MUTATION_MODE`     | fatal    | More than one mutation mode (replace/add-remove/clear) specified for the same field family.                                      |
| Invalid filter value                        | `E_INVALID_FILTER_VALUE`        | fatal    | An invalid value was supplied for `--impl-state`, `--priority`, or `--priority-at-least` filter flags.                            |

Cycle detection uses the same iterative-with-visited-set pattern used by
`GRAPH_SUPERSESSION_CYCLE` in Phase 2 (see MEMINIT-PLAN-011 §3.3.2). It
is O(n) in the number of entries with planning fields set.

All `STATE_*` codes are added to `ErrorCode` in
`src/meminit/core/services/error_codes.py`, and each ships a complete
`ERROR_EXPLANATIONS` entry so `meminit explain STATE_<CODE>` returns
actionable guidance. Fatal codes map to `EX_DATAERR` via
`exit_code_for_error` in `src/meminit/core/services/exit_codes.py`.
Malformed state YAML / schema violations that prevent parsing still
raise the existing `E_STATE_YAML_MALFORMED` and
`E_STATE_SCHEMA_VIOLATION` codes; query commands do not guess their way
through those cases.

#### 3.2.3 Migration posture

- No CLI migration command is introduced. Migration is implicit on the
  first mutating call after upgrade.
- `meminit state list` and `meminit state get` read legacy files without
  complaint. Their output already matches the v2 envelope because
  missing planning fields are simply omitted.
- Operators who want to force an eager migration can run
  `meminit state set <any-existing-id> --priority P2 --priority P2`
  (effectively a no-op that re-serializes the file as v2). This pattern
  does not warrant a dedicated command but is mentioned in the runbook
  (§3.6.3).

#### 3.2.4 Implementation tasks

1. Add the new flags to the `state set` Click command in
   `src/meminit/cli/main.py` using the additive/replace/remove pattern
   above.
2. Extend `StateDocumentUseCase` to apply the new fields with the
   deterministic ordering described in §3.1.2 (lexicographic sort,
   dedup, default omission).
3. Add the seven `STATE_*` error codes to `ErrorCode` and
   `ERROR_EXPLANATIONS`. Map the fatal ones in `exit_code_for_error`.
4. Implement validation as a pure function
   `validate_planning_fields(entry, known_ids) -> Violations`
   so it can be reused by mutation, read, and query paths.
5. Normalize `updated` to UTC at load/save boundaries and compare
   parsed datetimes in the selection path so ordering is stable across
   time zones.
6. Update the existing state unit tests in
   `tests/core/services/test_project_state.py` to cover: (a) v1→v2
   round-trip, (b) default omission on write, (c) each validation rule
   with one passing and one failing fixture, (d) deterministic sort of
   `depends_on` and `blocked_by`.
7. Extend the contract-matrix test so `state set` with the new flags
   emits a schema-valid v3 envelope.

Acceptance criteria:

1. `state set` accepts every new flag and rejects invalid combinations
   with a clear `STATE_*` code.
2. Running the same `state set` invocation twice produces a
   byte-identical `project-state.yaml`.
3. A v1 file becomes a v2 file on the first mutation, with no other
   diff beyond the header and any fields the caller actually changed.
4. Every fatal validation rule halts the mutation and leaves the
   on-disk file unchanged.
5. `meminit explain` returns a complete entry for each new
   `STATE_*` code.
6. The contract-matrix test passes for `state set` with the new flags
   without scenario-specific skip markers.

### 3.3 Workstream C: Query Commands for Ready, Blocked, and Next Work

Problem:

- The current `state get` and `state list` commands are too thin for
  agent execution planning.
- Agents currently have to load `project-state.yaml`, load the index,
  and implement the readiness / next-work algorithm themselves. That
  duplicates logic across consumers and drifts.

#### 3.3.1 Command surfaces

Three additions:

1. **`meminit state next`** — read-only. Returns the single
   deterministically-selected next work item, or a documented empty
   result when the queue has no ready entries.
2. **`meminit state blockers`** — read-only. Returns the set of entries
   that are currently blocked plus the specific open blockers for each.
3. **`meminit state list`** — extended with new filter flags.

All three commands use `agent_repo_options()` (thus inherit `--root`,
`--format`, `--output`, `--include-timestamp`, `--correlation-id`,
`--log-silence`) and never write to the filesystem. They require an
initialized repository config and fail fast with `CONFIG_MISSING` when
`docops.config.yaml` is missing or malformed. Missing
`project-state.yaml` is reported through `data` (not as an error) so
agents can distinguish "file missing" from "file present but empty".
Malformed YAML or schema violations in `project-state.yaml` remain
fatal and use the existing `E_STATE_*` codes rather than being guessed
through.

Additional flags per command:

| Command              | Flag                                  | Meaning                                                                                                       |
| -------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `state next`         | `--assignee <string>`                 | Restrict candidates to a specific assignee.                                                                   |
| `state next`         | `--priority-at-least <P0\|P1\|P2\|P3>` | Restrict candidates to priorities at or above the threshold (`P0` is highest).                               |
| `state blockers`     | `--assignee <string>`                 | Restrict blocked entries to a specific assignee.                                                              |
| `state list`         | `--ready / --no-ready`                | Filter to ready or not-ready entries. Absent = no filter.                                                     |
| `state list`         | `--blocked / --no-blocked`            | Filter to entries with at least one open blocker, or none.                                                    |
| `state list`         | `--assignee <string>` (repeatable)    | Filter to one or more assignees (union).                                                                      |
| `state list`         | `--priority <P0..P3>` (repeatable)    | Filter by priority (union).                                                                                   |
| `state list`         | `--impl-state <value>` (repeatable)   | Filter by `impl_state` (union). Already partially present; this workstream finalises the set.                 |

Mutually exclusive flag pairs (e.g. `--ready` with `--no-ready`) are
rejected with an `E_INVALID_FILTER_VALUE` usage error. `--ready` and
`--blocked` are also mutually exclusive with each other, because a
single entry cannot satisfy both predicates simultaneously.

#### 3.3.2 Readiness algorithm

An entry `E` is **ready** iff **all** of the following hold:

1. `E.impl_state == "Not Started"`.
2. Every `id` in `E.depends_on` satisfies one of:
   a. `id` resolves to a state entry with `impl_state == "Done"`; or
   b. `id` does not appear in either the state file or the index
      `nodes` array and the caller has explicitly consented to treat
      unknown targets as resolved (not the default; see below).
3. Every `id` in `E.blocked_by` satisfies §3.3.2 (2) above.

Default behavior on unknown dependency targets: treat the entry as
**not ready** and emit `STATE_UNDEFINED_DEPENDENCY` as a warning. This
is conservative and avoids false readiness. A future flag may relax
this; no such flag is introduced in Phase 4.

In-progress entries (`impl_state == "In Progress"`) are not "ready"
for selection — they are already picked up. They appear in
`state list` but never in `state next`.

Governed documents that are present in the index but absent from
`project-state.yaml` are emitted with derived fields for index/catalog
parity, including reverse `unblocks` relationships, but they are **not**
ready. The explicit `impl_state == "Not Started"` state entry remains a
required part of the readiness predicate.

#### 3.3.3 Next-selection algorithm

`state next` returns the ready entry that wins the following ordered
comparison. The comparison is total: any two distinct entries have a
well-defined winner.

1. **Priority rank ascending.** `P0` beats `P1` beats `P2` beats `P3`.
2. **`unblocks` count descending.** The entry that would unblock more
   currently-blocked entries wins. `unblocks` is the derived field from
   §3.1.3.
3. **`updated` ascending.** The entry with the oldest `updated`
   timestamp wins (stalest first). Timestamps are compared after
   normalizing to UTC datetime values, and the serializer persists
   canonical UTC values to keep ordering stable across time zones.
4. **`document_id` ascending.** Final lexicographic tie-breaker.

Rule (2) is a pure function of the stored `depends_on` and `blocked_by`
lists and requires no wall-clock input. Rule (3) depends only on the
stored `updated` field, not on the current time.

If no entry is ready, `state next` returns `data.entry = null` and
`data.reason = "queue_empty"`. If the state file does not exist,
`data.entry = null` and `data.reason = "state_missing"`.

#### 3.3.4 Blockers algorithm

`state blockers` returns every entry `E` for which
`open_blockers(E)` is non-empty. Each reported entry includes:

- `document_id`, `impl_state`, `priority`, `assignee` (if set)
- `open_blockers` — the sorted list of unresolved dependency IDs
- for each open blocker, a one-level-deep resolution:
  `{id, impl_state, known}` where `known` is `true` iff the ID resolves
  to a state entry or index node

The command does not traverse transitive chains; it reports direct
blockers only. Agents that need transitive reasoning call the command
iteratively.

#### 3.3.5 JSON payload shapes

`state next` `data`:

```json
{
  "entry": {
    "document_id": "MEMINIT-FDD-011",
    "impl_state": "Not Started",
    "priority": "P1",
    "assignee": "agent:augment",
    "next_action": "Draft the FDD skeleton",
    "updated": "2026-04-17T09:12:00+00:00",
    "updated_by": "GitCmurf",
    "depends_on": [],
    "blocked_by": [],
    "unblocks": ["MEMINIT-PRD-009"]
  },
  "selection": {
    "rule": "priority > unblocks > updated > document_id",
    "candidates_considered": 7,
    "filter": {
      "assignee": "agent:augment",
      "priority_at_least": "P2"
    }
  },
  "reason": null
}
```

`state blockers` `data`:

```json
{
  "blocked": [
    {
      "document_id": "MEMINIT-PRD-009",
      "impl_state": "Not Started",
      "priority": "P1",
      "assignee": null,
      "open_blockers": [
        {"id": "MEMINIT-FDD-011", "impl_state": "Not Started", "known": true},
        {"id": "MEMINIT-ADR-042", "impl_state": null, "known": false}
      ]
    }
  ],
  "summary": {
    "total_entries": 12,
    "blocked": 1,
    "ready": 4
  }
}
```

`state list` extended `data`: the existing `entries[]` array gains
`ready`, `open_blockers`, and `unblocks` derived fields on every
entry. `valid_impl_states` and `valid_doc_statuses` remain unchanged.
A new `summary` block mirrors the one above.

All arrays are sorted deterministically (lexicographic by
`document_id`, then lexicographic by sub-id).

#### 3.3.6 Error codes and explain entries

New agent-facing error codes and their `explain` remediation targets:

| Code                              | Emitted by                       | `resolution_type` |
| --------------------------------- | -------------------------------- | ----------------- |
| `STATE_INVALID_PRIORITY`          | `state set`, `state next` filter | `manual`          |
| `STATE_INVALID_DEPENDENCY_ID`     | `state set`                      | `manual`          |
| `STATE_SELF_DEPENDENCY`           | `state set`                      | `manual`          |
| `STATE_UNDEFINED_DEPENDENCY`      | `state set`, query commands      | `manual`          |
| `STATE_DEPENDENCY_CYCLE`          | `state set`, `state list`        | `manual`          |
| `STATE_DEPENDENCY_STATUS_CONFLICT` | query commands                  | advisory          |
| `STATE_FIELD_TOO_LONG`            | `state set`                      | `manual`          |

Each ships a complete `ERROR_EXPLANATIONS` entry.

#### 3.3.7 Implementation tasks

1. Add `state next` and `state blockers` Click subcommands in
   `src/meminit/cli/main.py`, wired through `command_output_handler`.
2. Extend the existing `state list` Click command with the new filter
   flags. Reject conflicting flag pairs with
   `E_INVALID_FILTER_VALUE`, including contradictory ready/blocked
   combinations.
3. Add a shared repo-initialization guard to the query commands so they
   fail fast on missing or malformed repo config instead of guessing
   defaults.
4. Implement the readiness, next-selection, and blockers algorithms as
   pure functions on `DerivedStateView`. Keep each function under the
   40-line soft limit.
5. Register `state next` and `state blockers` with
   `register_capability(needs_root=True, agent_facing=True)` in
   `src/meminit/cli/shared_flags.py`. Update the contract-matrix test
   to cover the new commands.
6. Add both commands to the repo-aware enum in
   `src/meminit/core/assets/agent-output.schema.v3.json` and its
   docs-tree copy at `docs/20-specs/agent-output.schema.v3.json`.
7. Add the `STATE_*` codes (those not already added in Workstream B)
   to `ErrorCode`, `ERROR_EXPLANATIONS`, and the exit-code mapping.

Acceptance criteria:

1. `state next` returns one entry or a documented empty result in
   every case, with no non-determinism.
2. `state blockers` lists every entry with at least one open blocker
   and reports each blocker's current status and known/unknown flag.
3. `state list` with new filters behaves as a pure filter on the
   existing entry array; removing a filter never shrinks the result
   set.
4. All three commands pass the contract-matrix envelope validator
   with `additionalProperties: false`.
5. JSON output for identical repo states is byte-identical across
   runs.
6. `meminit explain` returns a complete entry for every new
   `STATE_*` code.
7. `meminit capabilities --format json` includes `state next` and
   `state blockers` with `supports_json: true` and
   `supports_correlation_id: true`.

### 3.4 Workstream D: Index, Catalog, and Kanban Alignment

Problem:

- `IndexRepositoryUseCase` already merges `project-state.yaml` into
  `nodes` (see `src/meminit/core/use_cases/index_repository.py`). The
  richer state fields must flow through that merge so the index,
  catalog, and kanban views stay consistent with the CLI query
  surfaces.

#### 3.4.1 Index node enrichment

`meminit index` writes one node per governed document to
`meminit.index.json`. After Phase 2, node entries carry
state-derived fields (`impl_state`, `updated`, `updated_by`, `notes`).
Phase 4 adds the new planning fields and the `ready` derived flag:

| Added node field | Source         | Notes                                                                                       |
| ---------------- | -------------- | ------------------------------------------------------------------------------------------- |
| `priority`       | project-state  | Omitted when `P2` (default) to keep the artifact minimal.                                   |
| `depends_on`     | project-state  | Sorted lexicographically. Omitted when empty.                                               |
| `blocked_by`     | project-state  | Same rule.                                                                                  |
| `assignee`       | project-state  | Omitted when unset.                                                                         |
| `next_action`    | project-state  | Omitted when unset.                                                                         |
| `ready`          | derived        | Boolean. Always emitted.                                                                    |
| `open_blockers`  | derived        | Sorted list. Always emitted as an array, possibly empty.                                     |
| `unblocks`       | derived        | Sorted list. Always emitted as an array, possibly empty.                                     |

Determinism rules:

- The persisted index remains byte-identical for identical inputs.
- The derived fields are recomputed on every build; they are never
  persisted back into `project-state.yaml`.

Non-goal (explicit): `related_ids` from frontmatter are **not**
promoted to `depends_on` automatically. The two fields have different
semantics; conflating them would make the readiness algorithm
non-deterministic on legacy repos. Operators who want related-id
documents treated as dependencies must set `depends_on` explicitly via
`state set`.

#### 3.4.2 Catalog view

The catalog table (`_generate_catalog` in
`core/use_cases/index_repository.py`) adds two columns after
`Impl State`:

- **Priority** — `P0`..`P3`, or `—` when the default `P2` is in use
  and the field is not explicitly set.
- **Ready** — `✅`, `⏳`, or `—`. `✅` when ready, `⏳` when blocked,
  `—` when not applicable (e.g., `In Progress` or `Done`).

The existing sort order (activity recency) is preserved. An additional
row group header is emitted when `--group-by` is set to `priority` or
`ready` (new enum values on an existing flag, not a new flag).

#### 3.4.3 Kanban view

The kanban view (`kanban.md`) already organises entries by column
(`Not Started`, `In Progress`, etc.). Phase 4 adds:

- **In-column ordering**: within each column, entries are sorted by
  priority ascending (`P0` first), then by `unblocks` count descending
  (most-unblocking first), then by `updated` ascending, then by
  `document_id` ascending. This matches the `state next` selection
  order for the `Not Started` column.
- **Badges**: each card gains a priority badge (`P0..P3`) and a
  blocker badge when `open_blockers` is non-empty. Badges use the
  existing CSS class hook pattern from MEMINIT-PRD-007.
- **Plain-text fallback**: the Markdown fallback carries the same
  information as bracketed prefixes (for example
  `[P1][blocked]`), so plain-text viewers see a complete picture.

No new files are introduced. The existing `kanban.md` and
`kanban.css` assets are updated in place.

#### 3.4.4 Implementation tasks

1. Extend `IndexRepositoryUseCase` to consume the v2 state entries and
   compute the derived fields via `DerivedStateView` from §3.1.3.
2. Update `_build_persisted_index_payload` to emit the new node
   fields with the documented default-omission rules.
3. Update `_generate_catalog` to add the two new columns and the new
   `--group-by` enum values.
4. Update the kanban renderer to apply the in-column ordering and
   emit badges plus plain-text prefixes.
5. Update or add fixture repos under `tests/fixtures/` that exercise
   priority-ordered kanban and ready-flagged catalog output.
6. Update MEMINIT-PRD-007 to describe the new columns, badges, and
   ordering rules.

Acceptance criteria:

1. The index artifact gains the new node fields with default-omission
   behavior and remains byte-identical for identical inputs.
2. The catalog and kanban views render the new data without breaking
   existing plain-text or HTML fallbacks.
3. Kanban `Not Started` column ordering matches the `state next`
   selection order for the same state.
4. MEMINIT-PRD-007 is updated to describe the shipped behavior.

### 3.5 Workstream E: Query Fixtures and Determinism Tests

Problem:

- Without an enumerated fixture strategy, readiness and selection
  regressions can ship unnoticed, especially for the ordering and
  cycle-detection branches.

Fixture strategy:

- Use deterministic, code-generated fixture builders in the test tree
  rather than large checked-in synthetic repos.
- Keep the scenario definitions compact and self-documenting; a short
  note per scenario is enough to explain what behavior it covers.
- Prefer the same render and normalization paths as production code so
  fixture output matches the actual runtime contract.
- Only reach for checked-in file trees when a scenario genuinely needs
  byte-level preservation of a specific file layout.

#### 3.5.1 Required fixture scenarios

Each fixture is a self-contained repo state materialized by the fixture
builder under `tests/fixtures/state/` (or the equivalent workstream
test module). Every scenario exercises at least `state list` (summary
shape) and, where relevant, `state next`, `state blockers`, and
`meminit index` (for Workstream D integration).

| ID  | Scenario                                                                                          | Expected outcome                                                                                              |
| --- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Q01 | Legacy v1 state file; no planning fields                                                          | All reads succeed; no migration warning; `state next` uses `impl_state` only                                 |
| Q02 | Mixed repo: three `Not Started`, no dependencies                                                  | `state next` returns the lexicographically first one; all three are `ready`                                  |
| Q03 | Two `Not Started` entries, one with `priority: P0`                                                | `P0` wins                                                                                                    |
| Q04 | Two `Not Started` entries, same priority, different `updated`                                     | Older `updated` wins                                                                                          |
| Q05 | Two `Not Started` entries, same priority and `updated`, one with higher `unblocks` count          | Higher `unblocks` wins                                                                                       |
| Q06 | Two `Not Started` entries, identical on all keys except `document_id`                              | Lexicographically first `document_id` wins                                                                   |
| Q07 | Entry with `depends_on: [X]`, X is `Done`                                                         | Entry is `ready`                                                                                              |
| Q08 | Entry with `depends_on: [X]`, X is `In Progress`                                                  | Entry is not `ready`; X appears in `open_blockers`                                                            |
| Q09 | Entry with `depends_on: [X]`, X is not in state or index                                          | `STATE_UNDEFINED_DEPENDENCY` warning; entry is not `ready`                                                   |
| Q10 | Dependency cycle A → B → A                                                                        | `state set` for either entry emits `STATE_DEPENDENCY_CYCLE` and halts                                         |
| Q11 | Self-dependency                                                                                   | `state set --add-depends-on <self>` emits `STATE_SELF_DEPENDENCY` and halts                                   |
| Q12 | Invalid priority (`P9`)                                                                           | `state set --priority P9` emits `STATE_INVALID_PRIORITY`                                                      |
| Q13 | `next_action` exceeds `MAX_NOTES_LENGTH`                                                          | `state set --next-action <too-long>` emits `STATE_FIELD_TOO_LONG`                                             |
| Q14 | `state next --assignee agent:augment --priority-at-least P1` on a mixed queue                     | Filter reduces candidates deterministically; `selection.filter` echoes the input                              |
| Q15 | Empty ready set                                                                                   | `state next` returns `data.entry = null`, `data.reason = "queue_empty"`, exit 0                              |
| Q16 | Missing state file                                                                                | `state next` returns `data.entry = null`, `data.reason = "state_missing"`, exit 0                            |
| Q17 | Advisory-only case: entry `Done` but `depends_on` target is `In Progress`                         | `state list` emits `STATE_DEPENDENCY_STATUS_CONFLICT` through `advice[]`; no violation                        |
| Q18 | Idempotency: two consecutive `state set` calls with the same flags                                | Second run writes zero bytes; file mtime may update but content hash is unchanged                             |
| Q19 | Determinism: two independent fixture materializations of the same logical state                   | `state list` JSON output is byte-identical after sorted-key serialization                                     |
| Q20 | `meminit index` on a v2 state repo                                                                | Catalog and kanban views emit priority columns/badges; node entries carry the new fields; artifact byte-stable |

#### 3.5.2 Implementation tasks

1. Add a fixture loader helper under
   `tests/integration/test_state_queries.py` that materialises
   scenarios into `tmp_path` from the fixture builder.
2. Parametrize `test_state_next_selection` over Q02–Q16 and assert:
   `data.entry.document_id`, `data.reason`, `data.selection.rule`, and
   exit code.
3. Parametrize `test_state_blockers` over Q08, Q09, Q10 and assert
   sorted output and correct `known` flags.
4. Parametrize `test_state_set_validation` over Q10–Q13 and assert the
   fatal code, non-zero exit, and unchanged on-disk file.
5. Q17 is a dedicated advisory test: assert `advice[]` contains the
   code and `violations[]` does not.
6. Q18 and Q19 are dedicated determinism tests: Q18 asserts
   hash-equal file content after repeated mutations; Q19 asserts
   byte-equal JSON envelopes after sorted-key serialisation.
7. Q20 asserts the index artifact includes the new node fields and
   the catalog/kanban Markdown contains the documented badges.
8. Extend the contract-matrix so `state next` and `state blockers`
   are automatically exercised for envelope compliance, stdout/stderr
   isolation, and `additionalProperties: false` conformance.

Acceptance criteria:

1. All 20 fixture scenarios are defined in deterministic builders and
   documented with short scenario notes on what each demonstrates.
2. Every `STATE_*` error code introduced by this phase is exercised
   by at least one fixture.
3. The contract-matrix includes `state next` and `state blockers`
   without any scenario-specific skip markers.
4. The determinism tests (Q18, Q19) assert byte-equal output, not
   just field-wise equivalence.

### 3.6 Workstream F: Documentation and Rollout Boundaries

Problem:

- A work-queue layer changes how maintainers and agents manage repo
  planning data. Undocumented rollout boundaries are how agentic
  systems drift into de facto project management.

Implementation tasks:

1. Create the new FDD "Agent Work Queue Queries" listed in §2.2 and
   reference it from MEMINIT-PLAN-008 Section 7.
2. Update MEMINIT-PRD-005 to list the new commands and their contract
   expectations.
3. Update MEMINIT-PRD-007 per §3.4.2–§3.4.3.
4. Update MEMINIT-SPEC-006 with the new `STATE_*` codes and the
   normative `explain` semantics.
5. Extend `MEMINIT-SPEC-008` so the repo-aware command enum covers
   `state next` and `state blockers`. Mirror the change in both
   `src/meminit/core/assets/agent-output.schema.v3.json` and the
   docs-tree copy.
6. Create or extend the "Agent Integration and Upgrade Workflow"
   runbook:
   - how to migrate a v1 state file (first mutation triggers
     migration; no separate command required)
   - how an agent should loop on `state next` and what
     `data.reason == "queue_empty"` means
   - how operators should use `--assignee` to route work across
     multiple agents
7. Update the bundled `meminit-docops-skill.md` to reference the new
   commands and the work-queue loop pattern.
8. Update planning docs if the phase boundary shifts materially during
   delivery.
9. Use the fixture builder approach by default; add checked-in file
   trees only for scenarios that require byte-level path preservation.

Acceptance criteria:

1. The governed document outputs listed in §2.2 are complete and
   aligned with the shipped behavior.
2. The runbook explains the agent loop pattern, the migration model,
   and the `--assignee` routing pattern with runnable examples.
3. The bundled skill references the new commands.
4. Code, docs, and tests remain synchronized for every merged PR.

## 4. Recommended Delivery Sequence

1. Workstream A: State Model v2 Schema Definition
2. Workstream B: State Mutation, Migration, and Validation
3. Workstream E: Query Fixtures and Determinism Tests (scaffold in
   parallel with A/B; fixtures drive the unit tests for Workstream C)
4. Workstream C: Query Commands for Ready, Blocked, and Next Work
5. Workstream D: Index, Catalog, and Kanban Alignment
6. Workstream F: Documentation and Rollout Boundaries

Reason:

- The schema must be stable before mutation and query code lands on top
  of it.
- Mutation lands before queries so query fixtures can be constructed
  through the CLI rather than by hand-editing YAML.
- Fixture scaffolding comes online alongside the mutation work so each
  classification branch ships with a regression guard.
- Index, catalog, and kanban integration lands last among code
  workstreams because it depends on the stable node-level shape.
- Documentation and rollout boundaries close the phase once behavior
  is settled.

### 4.1 Recommended PR Slices

To preserve the repository's atomic-unit rule and keep reviewable
scope small, Phase 4 should land as small PRs:

1. **Schema + v1→v2 read path** — `state_schema_version`, extended
   `ProjectStateEntry`, canonical UTC timestamp handling,
   `DerivedStateView`, v1 acceptance on read, unit tests for round-trip
   and defaults. FDD scaffold.
2. **`state set` extensions + `STATE_*` codes** — new flags,
   validation (`STATE_INVALID_PRIORITY`, `STATE_INVALID_DEPENDENCY_ID`,
   `STATE_SELF_DEPENDENCY`, `STATE_DEPENDENCY_CYCLE`,
   `STATE_FIELD_TOO_LONG`), explain entries, exit-code mapping,
   contract-matrix pass for `state set`.
3. **`state next` + `state blockers`** — new commands, readiness and
   selection algorithms, JSON payload schemas, capability registry and
   envelope enum updates, repo-init guard, determinism tests
   (Q02–Q16).
4. **`state list` filter extensions + advisory code** — `--ready`,
   `--blocked`, `--assignee`, `--priority`, plus
   `STATE_DEPENDENCY_STATUS_CONFLICT` advisory and Q17.
5. **Index + catalog + kanban integration** — node-level enrichment,
   catalog columns, kanban ordering and badges, fixture Q20,
   MEMINIT-PRD-007 update.
6. **Runbook, skill, testbed validation, final doc reconciliation** —
   close §2.2 governed-doc outputs, refresh bundled skill, validate
   in the external testbed.

## 5. Exit Criteria for Phase 4

Phase 4 can be considered complete when all of the following are true:

1. `src/meminit/core/services/project_state.py` emits and accepts
   `state_schema_version: "2.0"`, and `ProjectStateEntry` carries the
   five planning fields defined in §3.1.2 (Workstream A).
2. Legacy (v1) state files round-trip through read → v2 view → write
   without operator intervention, and the first mutation after upgrade
   persists the v2 shape (Workstream A, B).
3. `meminit state set` accepts the new flag family in §3.2.1 with
   deterministic, idempotent writes and rejects every invalid input
   with a `STATE_*` code (Workstream B).
4. `meminit state next` implements the readiness filter and
   selection algorithm in §3.3.2–§3.3.3, returns the payload shape in
   §3.3.5, and is byte-stable across runs with canonical UTC timestamp
   ordering (Workstream C).
5. `meminit state blockers` returns the payload shape in §3.3.5 with
   sorted entries and one-level-deep blocker resolution (Workstream C).
6. `meminit state list` accepts the filter flags in §3.3.1 and
   surfaces `ready`, `open_blockers`, and `unblocks` on every entry
   (Workstream C).
7. The full state/queue error-code set is registered in
   `ErrorCode`: the eleven `STATE_*` values currently implemented,
   `E_STATE_YAML_MALFORMED`, `E_STATE_SCHEMA_VIOLATION`, and
   `E_INVALID_FILTER_VALUE` where used by §3.3.6. Each has a complete
   `ERROR_EXPLANATIONS` entry reachable via `meminit explain` and maps
   to the correct exit code (Workstreams B and C).
8. `meminit capabilities` lists `state next` and `state blockers`
   with `supports_json: true` and `supports_correlation_id: true`, and
   both pass the contract-matrix envelope validator with
   `additionalProperties: false` (Workstream C).
9. `meminit index` emits the enriched node fields in §3.4.1; catalog
   and kanban views render the new columns, badges, and ordering in
   §3.4.2–§3.4.3; the artifact remains byte-identical for identical
   inputs (Workstream D).
10. The 20 fixture scenarios in §3.5.1 are present, tested, and green
    (Workstream E).
11. Idempotency and determinism tests (Q18, Q19) pass on byte-equal
    output (Workstream E).
12. The governed document outputs listed in §2.2 are complete and
    aligned with the shipped behavior, including the bundled
    `meminit-docops` skill reference (Workstream F).
13. The queue cycle `state next → work → state set → state next` is verified
    deterministically by the Q01–Q20 fixture matrix (specifically Q08 and Q09)
    and by the `state next` example in MEMINIT-RUNBOOK-006 §3.
14. `meminit state*` commands fail fast with `CONFIG_MISSING` on
    missing or malformed repo config and do not guess defaults, while a
    missing `project-state.yaml` remains a documented empty-state case.

## 6. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-14 | GitCmurf | Initial draft created via `meminit new` |
| 0.2 | 2026-04-14 | Codex | Replaced stub with detailed Phase 4 workstreams, sequencing, and exit criteria |
| 0.3 | 2026-04-18 | Augment Agent | Rewrote against MEMINIT-PLAN-011 and MEMINIT-PLAN-012 quality bar: concrete v2 state schema with `state_schema_version`, five planning fields and three derived fields; explicit `state set` mutation surface with additive/remove/clear flag families; deterministic readiness and next-selection algorithms with total ordering; `STATE_*` error-code registry and exit-code mapping; JSON payload shapes for `state next`, `state blockers`, and extended `state list`; index, catalog, and kanban alignment rules; 20-scenario fixture matrix with explicit determinism tests; engineering constraints section anchoring the work to existing modules; governed-document outputs table for closeout; PR slicing guidance; and concrete exit criteria tied to specific files, classes, and commands |
| 0.4 | 2026-04-21 | Codex | Tightened Phase 4 for implementation safety and deliverability: explicit repo-initialization boundary for all state commands, canonical UTC handling for `updated` timestamps, mutually exclusive state mutation/filter modes, fatal handling for malformed state YAML/schema violations, always-emitted derived readiness fields, and clearer PR slicing and exit criteria for the queue workflow. |
| 0.5 | 2026-04-21 | Codex | Aligned the handoff with the shipped contract docs: added explicit TDD/QA gates, normalized the fixture strategy to deterministic builders, and pinned queue work references to MEMINIT-SPEC-008 and MEMINIT-RUNBOOK-006. |
| 0.6 | 2026-04-21 | Codex | Final wording pass: removed ambiguous contract/runbook alternatives and aligned the plan with the single canonical queue contract and runbook targets. |
| 0.7 | 2026-04-22 | Codex | Phase 4 gap remediation (round 1): BV-1 mixed-mode rejection, BV-2 warning envelope correctness, BV-3 fixture matrix Q01–Q20, AR-1 decomposition, AR-2 byte-stability, AR-3 kanban decomposition, GG-1–GG-4 docs closeout. *(test-count claim removed in v0.8)* |
| 0.8 | 2026-04-23 | Codex | Second audit remediation: BV-C XSS gate in kanban priority rendering, BV-A metadata drift corrected, BV-B exit criterion #13 scope correction (Q01–Q20 + RUNBOOK-006 §3), GG-A warning-code consolidation, GG-C stale test count removed. |
| 0.9 | 2026-04-23 | Codex | Third audit remediation: AR-new-2 double-emission dedup, AR-new-3 P2 index fidelity, GG-new-1 SPEC-008 advice shape, GG-new-2 line:0 omission, AR-new-1 decomposition, GG-new-3 error-code registry correction, AR-new-4 errata marker. |
| 0.10 | 2026-04-28 | Codex | Clarified that index-only governed documents receive derived fields but are not ready without an explicit `Not Started` project-state entry. |
