---
document_id: MEMINIT-PLAN-011
type: PLAN
title: Phase 2 Detailed Implementation Plan
status: Approved
version: "0.5"
last_updated: "2026-04-14"
owner: GitCmurf
docops_version: "2.0"
area: AGENT
description:
  Detailed implementation plan for MEMINIT-PLAN-008 Phase 2 repository
  graph work.
keywords:
  - phase-2
  - planning
  - index
  - graph
related_ids:
  - MEMINIT-PLAN-008
  - MEMINIT-PLAN-003
  - MEMINIT-STRAT-001
---

> **Document ID:** MEMINIT-PLAN-011
> **Owner:** GitCmurf
> **Status:** Approved
> **Version:** 0.5
> **Last Updated:** 2026-04-14
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Detailed implementation plan for MEMINIT-PLAN-008 Phase 2 repository graph work.

# PLAN: Phase 2 Detailed Implementation Plan

## Context

MEMINIT-PLAN-008 defines Phase 2 as the point where the index stops being only
an inventory and becomes a graph-grade agent artifact. This phase should begin
only after Phase 1 has stabilized the core runtime contract.

Phase 2 matters because agentic coding workflows depend on navigation as much
as they depend on command invocation. Agents need to know what documents
reference each other, what supersedes what, and what should be inspected next
without repeatedly rescanning raw markdown.

Adoption note:

- The external installed base is still just one explicit testbed.
- That allows the index artifact to evolve cleanly under pre-1.0 rules, but
  the graph contract still needs deterministic structure and upgrade notes.

Breaking-change posture:

- MEMINIT-PLAN-008 established backward compatibility as a general planning
  principle. For Phase 2, that constraint is **relaxed**: the tool is
  pre-alpha with a limited internal user base, and the index artifact has no
  external stability promise yet. This plan is free to propose breaking
  changes to the `meminit index` JSON schema, document entry shape, or
  resolution helper behavior where it produces a more robust graph model.

## 1. Purpose

Define the detailed implementation steps for Phase 2 of MEMINIT-PLAN-008 so
that Meminit can ship a reliable, documented repository-graph artifact.

## 2. Scope

In scope:

- graph field design for `meminit index`
- extraction of links, `related_ids`, and supersession edges
- freshness and determinism rules for the graph artifact
- targeted graph-aware validation where the value is clear
- tests and fixture coverage for cross-document relationships

Out of scope:

- semantic search
- ad hoc graph-query helpers beyond existing `resolve`, `identify`, and `link`
- agent work-queue logic
- protocol drift tooling
- NDJSON streaming and incremental indexing
- non-deterministic similarity or heuristic ranking

## 3. Work Breakdown

### 3.1 Workstream A: Graph Contract Definition

Problem:

- MEMINIT-STRAT-001 commits Meminit to a stronger repository graph, but the
  current artifact does not yet define the concrete field set and guarantees.
- The current index embeds per-document metadata only. There is no top-level
  structure for cross-document relationships, no edge typing, and no way for
  an agent to traverse the graph without re-parsing every document.

#### 3.1.1 Proposed graph artifact structure

The persisted index artifact (`meminit.index.json`) is restructured from a
flat document list to a graph model with two top-level collections: **nodes**
(documents) and **edges** (relationships).

Top-level `data` shape (breaking change from `index_version: "0.2"`):

```json
{
  "index_version": "1.0",
  "graph_schema_version": "1.0",
  "namespaces": [ ... ],
  "node_count": 42,
  "edge_count": 17,
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

**Rationale for separating nodes and edges:** An agent that wants to answer
"what documents reference MEMINIT-PRD-005?" should not need to iterate every
node's nested field. A top-level `edges` array is a simple adjacency list
that supports O(n) filtering by source or target without nested traversal.
The `resolve` and `identify` helpers continue to work against `nodes`.

#### 3.1.2 Node schema

Each entry in `nodes` represents one governed document:

| Field           | Type     | Required | Source        | Notes                          |
| --------------- | -------- | -------- | ------------- | ------------------------------ |
| `document_id`   | string   | yes      | frontmatter   | Primary key                    |
| `path`          | string   | yes      | filesystem    | Repo-relative POSIX path       |
| `namespace`     | string   | yes      | config        | Owning namespace               |
| `repo_prefix`   | string   | yes      | config        | Namespace prefix               |
| `type`          | string   | yes      | frontmatter   | Document type (ADR, PRD, etc.) |
| `title`         | string   | yes      | frontmatter   | Sanitized title                |
| `status`        | string   | yes      | frontmatter   | Governance status              |
| `owner`         | string   | yes      | frontmatter   | Document owner                 |
| `last_updated`  | string   | yes      | frontmatter   | ISO 8601 date                  |
| `area`          | string   | no       | frontmatter   | Classification area            |
| `description`   | string   | no       | frontmatter   | Brief description              |
| `keywords`      | string[] | no       | frontmatter   | Search/categorization keywords |
| `superseded_by` | string   | no       | frontmatter   | Document ID of successor       |
| `related_ids`   | string[] | no       | frontmatter   | Declared related document IDs  |
| `impl_state`    | string   | no       | project-state | Implementation state           |
| `updated`       | string   | no       | project-state | ISO 8601 datetime              |
| `updated_by`    | string   | no       | project-state | Actor who last changed state   |
| `notes`         | string   | no       | project-state | Free-text notes                |

**Changes from current schema:** `area`, `description`, `keywords`,
`superseded_by`, and `related_ids` are newly extracted from frontmatter.
These fields already exist in the `Frontmatter` entity and
`metadata.schema.json` but are currently ignored during index build.

#### 3.1.3 Edge schema

Each entry in `edges` represents a directed relationship between two
document IDs:

| Field        | Type    | Required | Notes                                                       |
| ------------ | ------- | -------- | ----------------------------------------------------------- |
| `source`     | string  | yes      | Document ID of the referencing document                     |
| `target`     | string  | yes      | Document ID of the referenced document                      |
| `edge_type`  | string  | yes      | One of the defined edge types                               |
| `guaranteed` | boolean | yes      | Whether the edge is guaranteed-correct                      |
| `context`    | string  | no       | Human-readable provenance (e.g., "frontmatter.related_ids") |

#### 3.1.4 Edge types and guarantee levels

| Edge type    | Source                                        | Guaranteed  | Extraction rule                                                                                                                        |
| ------------ | --------------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `supersedes` | frontmatter `superseded_by` on the **target** | yes         | If document B has `superseded_by: A`, emit edge `{source: A, target: B, edge_type: "supersedes"}`. Direction is "A supersedes B".      |
| `related`    | frontmatter `related_ids`                     | yes         | For each ID in a document's `related_ids`, emit a directed edge from the declaring document to the referenced ID.                      |
| `references` | markdown body links                           | best-effort | Extract standard local markdown links whose target resolves to a governed document. Best-effort because link text and format can vary. |

**Guaranteed** means the edge is derived from schema-validated frontmatter
fields and the extraction is deterministic. **Best-effort** means the edge
is derived from heuristic body parsing and may miss non-standard link
formats.

#### 3.1.5 Freshness and determinism metadata

The persisted graph artifact must remain byte-identical for identical repo
content. For that reason, the artifact does **not** include a wall-clock
`built_at` field or any other runtime timestamp.

Freshness signals are handled outside the persisted artifact:

- the CLI JSON output envelope already carries per-run metadata such as
  `run_id` and optional timestamping
- consumers can compare the index file mtime with source file mtimes when they
  need a staleness decision

No per-node freshness stamp is added; the index is always built atomically.

#### 3.1.6 Deterministic ordering

- **Nodes**: sorted by `document_id` lexicographically (ascending, ordinal).
- **Edges**: sorted by `(source, target, edge_type)` lexicographically.
- Tie-breaking is unnecessary because each `(source, target, edge_type)`
  triple is unique by construction (duplicates are collapsed during
  extraction).

Implementation tasks:

1. Implement the node and edge schemas as described above.
2. Bump `index_version` to `"1.0"` and add `graph_schema_version: "1.0"`.
3. Keep the persisted payload free of wall-clock timestamps so repeated runs
   on identical content remain byte-identical.
4. Update `_build_persisted_index_payload` to emit `nodes` and `edges`
   instead of `documents`.
5. Update downstream consumers (`resolve`, `identify`, `link`, and shorthand
   resolution in `state_document.py`) to read from `nodes` instead of
   `documents`.

Acceptance criteria:

1. The graph fields are documented before implementation is finalized.
2. Consumers can distinguish guaranteed from best-effort edges via the
   `guaranteed` boolean.
3. Ordering is deterministic and tested: two runs on the same repo content
   produce byte-identical JSON.
4. `resolve`, `identify`, `link`, and shorthand state resolution work against
   the new `nodes` key.

### 3.2 Workstream B: Edge Extraction in Index Build

Problem:

- The current builder surfaces document metadata but not resolved relationships.
- The `Frontmatter` entity already parses `related_ids` and `superseded_by`,
  and `LinkChecker` already extracts markdown links via regex, but none of
  this is wired into index build.

#### 3.2.1 Extraction pipeline

Edge extraction runs as a second pass after all nodes are collected, so that
the set of known document IDs is complete before any edge resolution occurs.

Pipeline steps (executed in this order):

1. **Collect known IDs**: build a `Set[str]` of all `document_id` values
   from the node list. Also build a `Dict[str, str]` mapping repo-relative
   paths to document IDs (the reverse of what `identify` does).
2. **Extract `related` edges**: for each node with a non-empty `related_ids`
   list, emit one `related` edge per entry. Source is the declaring
   document. Target is the referenced ID.
3. **Extract `supersedes` edges**: for each node where `superseded_by` is
   set, emit one `supersedes` edge. Source is the value of `superseded_by`
   (the successor). Target is the current document (the superseded one).
   Direction encodes "A supersedes B".
4. **Extract `references` edges**: for each node, parse the markdown body
   using the existing `LinkChecker.LINK_REGEX` pattern. For each local
   (non-external, non-anchor) link target, resolve it to a repo-relative
   path, then look up the path in the path→ID map. If found, emit a
   `references` edge. If the same source→target pair appears multiple times
   in a single document, collapse to one edge.
5. **Deduplicate**: collapse any `(source, target, edge_type)` triples that
   appear more than once. A `related` edge from A→B and a `references` edge
   from A→B are **not** duplicates — they are distinct edge types.
6. **Sort**: sort the final edge list by `(source, target, edge_type)`.

#### 3.2.2 Determinism guarantees

- `related` and `supersedes` edges are derived from schema-validated YAML
  frontmatter parsed by `yaml.SafeLoader`. The extraction is fully
  deterministic: same input bytes → same edges.
- `references` edges use the same regex (`\[([^\]]+)\]\(([^)]+)\)`) already
  used by `LinkChecker`. The regex is applied to the markdown body after
  frontmatter stripping (via `python-frontmatter`). Extraction order follows
  document-order occurrence; deduplication and sorting make the final list
  input-order-independent.
- Edge extraction must never depend on filesystem modification times, git
  history, or mutable external state.

#### 3.2.3 Dangling edge handling

An edge whose `target` (or `source`, for `supersedes`) does not appear in
the known-ID set is a **dangling edge**. Dangling edges are:

- **Still emitted** in the `edges` array (agents need to know the
  relationship exists even if the target is missing or out-of-scope).
- **Marked** with `"guaranteed": true` or `false` per normal rules.
- **Flagged** with a warning in the top-level `warnings` array using a new
  warning-registry code such as `DANGLING_EDGE`.

This allows agents to distinguish "the relationship is declared but the
target is not in this index" from "no relationship exists".

Implementation tasks:

1. Add a post-node-collection extraction pass implementing steps 1–6 above.
2. Reuse `LinkChecker.LINK_REGEX` for body-link extraction; extract the
   resolve-to-path logic from `LinkChecker.validate_links` into a shared
   utility.
3. Build the path→ID reverse map from the collected nodes.
4. Emit `DANGLING_EDGE` warnings for unresolvable targets.
5. Wire the deduplication and sort step.

Acceptance criteria:

1. Index generation emits all three edge types consistently.
2. Edge extraction does not require a second pass by external tools.
3. Two runs on identical repo content produce identical edge arrays.
4. Dangling edges are emitted with a warning, not silently dropped.

### 3.3 Workstream C: Graph-Aware Integrity Checks

Problem:

- Once the graph exists, some integrity checks are more reliable when they are
  index-backed instead of raw-text-backed.
- The current `check` command validates links at the filesystem level but
  cannot reason about document-ID-level relationships.

#### 3.3.1 Validation rules

The following graph integrity checks are in scope for Phase 2. Each check
produces a deterministic fatal, warning, or advisory diagnostic using the
appropriate registry or output channel.

Diagnostic code convention for this phase:

- Use stable semantic codes with a domain prefix and keep severity out of the
  code itself.
- Fatal command-failure conditions remain in `ErrorCode`.
- Non-fatal graph diagnostics should use a graph-domain diagnostic naming
  scheme such as `GRAPH_DANGLING_RELATED_ID` rather than severity-prefixed
  names such as `W_*` or `E_*`.
- Severity is carried separately in the output channel and diagnostic object,
  so a future severity change does not require renaming the code.

| Rule                            | Code                                 | Severity | Description                                                                                                                                                                                          |
| ------------------------------- | ------------------------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dangling `related_ids` target   | `GRAPH_DANGLING_RELATED_ID`          | warning  | A document declares a `related_ids` entry that does not match any `document_id` in the index.                                                                                                        |
| Dangling `superseded_by` target | `GRAPH_DANGLING_SUPERSEDED_BY`       | warning  | A document declares `superseded_by: X` but `X` is not in the index.                                                                                                                                  |
| Supersession without status     | `GRAPH_SUPERSESSION_STATUS_MISMATCH` | warning  | A document has `superseded_by` set but its `status` is not `Superseded`, or vice versa (status is `Superseded` but `superseded_by` is absent).                                                       |
| Supersession cycle              | `GRAPH_SUPERSESSION_CYCLE`           | error    | Following `superseded_by` chains produces a cycle (A superseded by B, B superseded by C, C superseded by A).                                                                                         |
| Asymmetric `related_ids`        | `GRAPH_RELATED_ID_ASYMMETRY`         | info     | Document A lists B in `related_ids` but B does not list A. This is advisory, not an error — directional relationships are valid. Emit through the advisory channel rather than the fatal-error path. |
| Duplicate node ID               | `GRAPH_DUPLICATE_DOCUMENT_ID`        | error    | Two filesystem paths produce the same `document_id`. This is fatal for graph build because edges become ambiguous. The build must halt and no partial artifact may be written.                       |

#### 3.3.2 Implementation approach

Graph integrity checks run **during index build**, not as a separate
command. The index builder already has the full node and edge sets in memory
when it writes the artifact. Checks are applied after edge extraction and
before serialization. Fatal diagnostics are added to the top-level
`violations` array, warning-severity diagnostics are added to `warnings`, and
advisory diagnostics such as `GRAPH_RELATED_ID_ASYMMETRY` are added to `advice`.

This avoids the stale-artifact problem entirely: there is no separate
"validate the index" step that could consume an outdated file.

Supersession cycle detection uses iterative chain-following with a visited
set (not recursion), bounded by the node count. This is O(n) in the number
of nodes with `superseded_by` set.

Implementation tasks:

1. Implement the six validation rules listed above.
2. Register fatal diagnostics in `ErrorCode` and non-fatal warnings in the
   warning-code registry; document advisory diagnostics in the appropriate
   contract docs instead of treating them as fatal errors.
3. Apply the stable graph-domain naming convention consistently across the
   implementation and contract docs.
4. Make `GRAPH_DUPLICATE_DOCUMENT_ID` and `GRAPH_SUPERSESSION_CYCLE` fatal to
   index build:
   return a non-zero exit code and do not write a partial or ambiguous
   artifact.
5. Emit violations, warnings, and advice into the index build report.
6. Ensure all checks are deterministic: same input → same diagnostic set.

Acceptance criteria:

1. Each validation rule is covered by at least one passing and one failing
   fixture.
2. Validation runs during index build without requiring external state.
3. Fatal and non-fatal diagnostics are registered in the correct registry or
   output channel.
4. Duplicate IDs and supersession cycles halt build and prevent artifact write.
5. Supersession cycle detection terminates in bounded time.

### 3.4 Workstream D: Fixtures, Performance Boundaries, and Testbed Use

Problem:

- Graph extraction can expand quickly in complexity if fixtures and boundaries
  are not defined early.

#### 3.4.1 Required fixture scenarios

The following fixture cases must be covered by the test suite:

| Fixture                                                    | Tests                                                                         |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Two documents with mutual `related_ids`                    | Symmetric `related` edges emitted; `GRAPH_RELATED_ID_ASYMMETRY` not raised    |
| Document A lists B in `related_ids` but B does not list A  | Directed `related` edge A→B emitted; `GRAPH_RELATED_ID_ASYMMETRY` info raised |
| Document with `related_ids` pointing to non-existent ID    | `GRAPH_DANGLING_RELATED_ID` warning; dangling edge still emitted              |
| Document with `superseded_by` set and `status: Superseded` | `supersedes` edge emitted; no warnings                                        |
| Document with `superseded_by` set but `status: Draft`      | `GRAPH_SUPERSESSION_STATUS_MISMATCH` warning                                  |
| Document with `status: Superseded` but no `superseded_by`  | `GRAPH_SUPERSESSION_STATUS_MISMATCH` warning                                  |
| Three-document supersession chain (A→B→C)                  | Two `supersedes` edges; no cycle diagnostic                                   |
| Supersession cycle (A→B→A)                                 | `GRAPH_SUPERSESSION_CYCLE` error                                              |
| Markdown body with link to another governed doc            | `references` edge emitted                                                     |
| Markdown body with link to non-governed file               | No edge emitted                                                               |
| Markdown body with external URL                            | No edge emitted                                                               |
| Markdown body with multiple links to same governed doc     | Single `references` edge (deduplicated)                                       |
| Same source→target pair via `related_ids` AND body link    | Both `related` and `references` edges emitted (distinct types)                |
| Idempotency: two index runs on same content                | Byte-identical JSON output                                                    |
| Duplicate `document_id` across two files                   | `GRAPH_DUPLICATE_DOCUMENT_ID` error                                           |

#### 3.4.2 Performance boundaries

Phase 2 must not quietly become a scaling project. The following bounds
apply:

- Index build for a repo with ≤500 governed documents must complete in
  under 10 seconds on commodity hardware (single-threaded, no caching).
- Edge extraction must be single-pass per document (one frontmatter read +
  one body regex scan). No multi-pass or transitive-closure computation
  is in scope for Phase 2.
- The persisted artifact size must scale linearly with document and edge
  count. No embedded adjacency matrices or precomputed path structures.

If any of these bounds are at risk during implementation, the scope should
be reduced rather than introducing streaming or incremental rebuild (which
belong to Phase 5).

Implementation tasks:

1. Build the fixture set listed in §3.4.1.
2. Add a byte-identity regression test (two runs → same output).
3. Run the index builder against the external testbed and confirm the graph
   artifact is consumable.
4. Add a lightweight timing assertion or benchmark marker for the ≤500-doc
   bound.

Acceptance criteria:

1. All fixture scenarios in §3.4.1 are covered by automated tests.
2. The graph artifact is stable under repeated runs on the same content.
3. The testbed confirms the artifact is useful outside the Meminit repo.
4. Phase 2 stays bounded to deterministic graph delivery rather than scaling
   work.

### 3.5 Workstream E: Documentation and Upgrade Notes

Problem:

- A graph artifact is only valuable if agents and operators know what it
  guarantees and what it does not.

Implementation tasks:

1. Update the programme and roadmap docs if phase scope changes materially.
2. Draft or update the implementation-level document for index graph
   enrichment when the phase is approved to start.
3. Document how existing automation should interpret the new fields.
4. Capture any upgrade notes needed by the external testbed.

Acceptance criteria:

1. The graph semantics are documented alongside the code.
2. Early adopters can upgrade without reverse-engineering the artifact.
3. Code, docs, and tests remain synchronized.

## 4. Recommended Delivery Sequence

1. Workstream A: Graph Contract Definition
2. Workstream B: Edge Extraction in Index Build
3. Workstream C: Graph-Aware Integrity Checks
4. Workstream D: Fixtures, Performance Boundaries, and Testbed Use
5. Workstream E: Documentation and Upgrade Notes

Reason:

- The field contract must be stable before extraction logic lands.
- Extraction precedes validation because the checks depend on a trustworthy
  graph.
- Performance and testbed feedback should constrain the implementation before
  the phase is declared complete.

## 5. Exit Criteria for Phase 2

Phase 2 can be considered complete when all of the following are true:

1. `meminit index` emits a graph artifact at `index_version: "1.0"` with
   separate `nodes` and `edges` arrays.
2. `related`, `supersedes`, and `references` edges are extracted
   deterministically: two runs on the same content produce byte-identical
   output.
3. Each edge carries a `guaranteed` flag distinguishing schema-derived from
   body-parsed relationships.
4. Graph integrity checks (`GRAPH_DANGLING_RELATED_ID`,
   `GRAPH_DANGLING_SUPERSEDED_BY`, `GRAPH_SUPERSESSION_STATUS_MISMATCH`,
   `GRAPH_SUPERSESSION_CYCLE`, `GRAPH_DUPLICATE_DOCUMENT_ID`) run during
   index build.
5. All fixture scenarios listed in §3.4.1 have automated test coverage.
6. `resolve`, `identify`, `link`, and shorthand resolution in
   `state_document.py` work against the new `nodes` key.
7. The Meminit repo and the external testbed both validate the graph.
8. The governing docs and upgrade notes describe the shipped semantics.

## 6. Version History

| Version | Date       | Author        | Changes                                                                                                                                                                                                                                                                                                                                    |
| ------- | ---------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 0.1     | 2026-04-14 | GitCmurf      | Initial draft created via `meminit new`                                                                                                                                                                                                                                                                                                    |
| 0.2     | 2026-04-14 | Codex         | Replaced stub with detailed Phase 2 workstreams, sequencing, and exit criteria                                                                                                                                                                                                                                                             |
| 0.3     | 2026-04-14 | Augment Agent | Strengthened plan: added concrete graph schema (nodes and edges separation), typed edge schema with guarantee levels, deterministic extraction pipeline with 6-step specification, explicit graph integrity validation rules, comprehensive fixture coverage, performance boundaries, breaking-change posture, and tightened exit criteria |
| 0.4     | 2026-04-14 | GitCmurf      | Incorporated detailed reviewer feedback on schema, validation rules, fixture coverage, and breaking-change posture                                                                                                                                                                                                                         |
| 0.5     | 2026-04-14 | Codex         | Removed persisted wall-clock freshness metadata, clarified fatal duplicate-ID behavior, aligned diagnostic registries with severity, deferred graph-query helpers, added state shorthand resolution to downstream updates, and locked the graph diagnostic naming convention to stable domain-prefixed semantic codes                      |
| 0.6     | 2026-04-17 | GitCmurf      | Phase 2 implementation complete. Synchronized SPEC-006 (graph error codes), FDD-007 (graph artifact shape), and regenerated committed index artifact. Three review remediation rounds applied: edge direction fix, edge schema (guaranteed/context), severity-free naming, violations channel, advice channel, iterative cycle detection, filtered edge coherence. |
