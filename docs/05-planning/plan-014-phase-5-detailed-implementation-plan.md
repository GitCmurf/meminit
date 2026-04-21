---
document_id: MEMINIT-PLAN-014
type: PLAN
title: Phase 5 Detailed Implementation Plan
status: Draft
version: '0.3'
last_updated: '2026-04-19'
owner: GitCmurf
docops_version: '2.0'
area: AGENT
description: Detailed implementation plan for MEMINIT-PLAN-008 Phase 5 scale and streaming
  work.
keywords:
- phase-5
- planning
- streaming
- ndjson
- incremental
related_ids:
- MEMINIT-PLAN-008
- MEMINIT-PLAN-003
- MEMINIT-PLAN-011
- MEMINIT-PRD-005
- MEMINIT-SPEC-006
- MEMINIT-SPEC-008
---

> **Document ID:** MEMINIT-PLAN-014
> **Owner:** GitCmurf
> **Status:** Draft
> **Version:** 0.3
> **Last Updated:** 2026-04-19
> **Type:** PLAN
> **Area:** AGENT
> **Description:** Detailed implementation plan for MEMINIT-PLAN-008 Phase 5 scale and streaming work.

# PLAN: Phase 5 Detailed Implementation Plan

## Context

MEMINIT-PLAN-008 defines Phase 5 as the scale and streaming phase. By the
time this phase starts, the expectation is that the runtime contract is
stable enough that Meminit can expose large-output workflows cleanly
rather than forcing every consumer to buffer one large JSON object.

This phase depends on earlier phases in the following specific ways:

- Phase 1 (Agent Contract Core) established the v3 envelope, capabilities
  registry, and correlation-id semantics. Phase 5 extends those surfaces
  for streaming without reopening them.
- Phase 2 (Repository Graph) shipped the `nodes`/`edges` index artifact at
  `index_version: "1.0"`. Phase 5's streaming contract for `meminit index`
  emits those same node and edge records one at a time rather than as a
  single JSON object.
- Phase 4 (Work Queue) added derived state fields. Those fields remain
  internal to the query commands; they do not appear in streaming
  surfaces in this phase.

Phase 5 is intentionally about delivery ergonomics and large-repo
behaviour. It is not a license to reopen earlier contract ambiguity. The
standard non-streaming surfaces must already be settled by earlier
phases.

Definition:

- A **stream** is the stdout output of a CLI invocation run with
  `--format ndjson`. It is a sequence of line-delimited JSON records
  where each line is a complete, self-describing object.
- A **record** is a single line in the stream. Every record carries the
  minimum metadata required to be interpreted in isolation (see §3.1.2).
- The **summary record** is the terminal record of a successful stream
  and carries the same counters, warnings, violations, and advice that
  a non-streaming envelope would carry under `data` plus the envelope
  top-level arrays.
- An **incremental rebuild** is a subsequent `meminit index` invocation
  that produces a byte-identical index artifact to a full rebuild but
  recomputes only the portion of the graph affected by changed inputs.

Adoption note:

- Outside Meminit, only one explicit testbed repo currently exists.
- That low adoption makes it reasonable to choose the cleanest streaming
  shape rather than preserving awkward temporary compromises, provided
  the upgrade story is documented.

Backward-compatibility posture:

- MEMINIT-PLAN-008 waives the blanket compatibility requirement for
  pre-alpha vNext work. For Phase 5 this means:
  - Introducing a new `ndjson` value to the `--format` enum is additive
    and does not break existing `text`, `json`, or `md` consumers.
  - The persisted index artifact shape is unchanged by streaming; only
    the transient CLI output gains a new representation.
  - The incremental rebuild cache at `.meminit/cache/` is additive and
    can be deleted at any time to force a full rebuild.
- No backward-compatibility guarantee is offered for the NDJSON record
  shape until `stream_schema_version: "1.0"` ships. Pre-1.0 drafts may
  change.

Determinism requirement:

- Every stream must be byte-identical for identical inputs (same repo
  content, same flags, same Meminit version): same record order, same
  record payloads, same line separators, same final summary hash.
- `run_id` is the only per-invocation field allowed to vary, and it
  appears only in the header record (never in item records). The
  non-streaming equivalent already tolerates this; the streaming rules
  match.
- Byte-identity applies to both full and incremental rebuilds: an
  incremental `meminit index` must emit the same stream (and persist
  the same artifact) as a full rebuild on the same final repo state.

Memory-efficiency requirement:

- Streaming commands must emit records as they are produced, without
  first accumulating the full output in memory. The peak resident size
  during a streaming run must be O(one record + bounded buffers), not
  O(total output).
- This rules out "build the whole list in RAM, then iterate it". Each
  command must be refactored so its producer yields records via a
  generator or callback, and the emitter writes each record to stdout
  before producing the next.

Scale targets:

- Full `meminit index --format ndjson` must complete for a 5000-document
  repository within 60 seconds on commodity hardware (single-threaded,
  cold cache).
- Incremental `meminit index --format ndjson` on a 1000-document
  repository with a single changed file must complete within 2 seconds
  (warm cache).
- Peak resident memory must not exceed 256 MB on the 5000-doc run. This
  is a soft guardrail verified by a `@pytest.mark.slow` test, not a
  hard production SLA.

## 1. Purpose

Define the detailed implementation steps for Phase 5 of MEMINIT-PLAN-008
so that Meminit can handle large-output workflows with a deterministic
NDJSON streaming contract and an incremental index rebuild path,
without breaking any earlier contract surface.

## 2. Scope

In scope:

- a normative NDJSON streaming contract with versioned record schema
- streaming support for `meminit index`, `meminit scan`, and
  `meminit context --deep`
- shared emitter infrastructure so every streaming command obeys the
  same contract
- an incremental index rebuild design with explicit fingerprinting and
  cache-invalidation rules
- new `STREAM_*` and `CACHE_*` error codes with matching `explain`
  entries
- capabilities-registry extensions so streaming support is advertised
  per command
- fixture-driven determinism, correctness, and scale tests
- operator guidance for choosing standard JSON vs NDJSON and for
  diagnosing incremental-rebuild issues

Out of scope:

- semantic search
- protocol governance (Phase 3)
- work-queue semantics (Phase 4)
- non-deterministic background services
- arbitrary long-running daemons outside the supported CLI model
- parallel or multi-threaded rebuilds (explicit non-goal; may be
  revisited post-Phase 5)
- streaming for non-selected commands (`check`, `fix`, state queries,
  protocol commands) — adding them later is additive once the
  contract is stable
- cross-host cache sharing (the cache is strictly repo-local and
  gitignored)

### 2.1 Engineering Constraints

The implementation must follow the current Meminit codebase conventions
rather than inventing a parallel pattern:

- reuse `agent_output_options`, `agent_repo_options`,
  `command_output_handler`, `register_capability`, `ErrorCode`, and
  `ERROR_EXPLANATIONS` rather than introducing command-local contract
  logic
- extend `format_option()` in `src/meminit/cli/shared_flags.py` to add
  `"ndjson"` to the `click.Choice` list; do not introduce a parallel
  `--stream` flag
- extend `command_output_handler` (or a dedicated
  `streaming_output_handler` living next to it in
  `src/meminit/cli/main.py`) so commands that support NDJSON can opt
  in with a single helper call rather than hand-rolling stream setup
- keep the v3 envelope and `format_envelope` untouched for non-streaming
  paths; streaming records live in a separate schema
  (`agent-output.stream.schema.v1.json`, §3.1.5)
- route all structured logging through the existing
  `log_operation()` contextmanager in
  `src/meminit/core/services/observability.py`, which already writes to
  `MEMINIT_LOG_FILE` (stderr by default) and never to stdout
- keep use-cases free of I/O side-effects for stdout: producers yield
  records via a generator; only the CLI adapter writes to stdout via
  the shared emitter
- validate every cache-file write target with `ensure_safe_write_path`
  and use the same atomic temp-file-plus-`os.replace` pattern already
  used by other mutable artifacts in the repo
- keep function size inside the repository's soft 40-line limit and
  prefer small, composable generators over one large streaming monolith

Performance and memory constraints:

- Streaming commands must use **constant-memory emission**: the producer
  must be a generator that yields one record at a time, and the emitter
  must flush after each record. Any existing code that accumulates
  results into a full list before returning must be refactored to a
  generator on the streaming path.
- Incremental rebuild cache reads must be O(1) per fingerprint lookup
  and O(changed-files) per rebuild, not O(total-files).
- The cache must never be loaded eagerly in the common `meminit index`
  path if streaming is not requested and no cache exists.

Security:

- The cache directory must live under `.meminit/cache/` at the repo
  root. Writes outside the repo root are forbidden and must be
  enforced by `ensure_safe_write_path`.
- NDJSON records must never carry secrets from the environment.
  Existing input-sanitisation rules apply unchanged.
- The cache manifest must not store absolute filesystem paths. All
  paths are repo-relative POSIX strings.

Stdout / stderr isolation:

- Stdout is reserved exclusively for NDJSON records when
  `--format ndjson` is active. No progress bars, no log lines, no
  human-readable status text.
- Stderr remains the sole channel for logs and is routed through
  `log_operation()`. The existing
  `tests/core/services/test_log_isolation.py` pattern must be extended
  to cover every new streaming command.
- On mid-stream failure, the emitter writes one final `error` record
  to stdout (see §3.1.3) and then closes the stream. No partial JSON
  objects, no truncated records.

### 2.2 Governed Document Outputs

Phase 5 implementation is not done when the code lands. The following
governed-document updates are required for closeout, consistent with
MEMINIT-PLAN-008 Section 7:

| Action | Type | Document | Required update |
| ------ | ---- | -------- | --------------- |
| Update | PRD | `MEMINIT-PRD-005` | Promote streaming from SHOULD/optional to normative, document the shipped record types, and reference the new streaming spec |
| Update | SPEC | `MEMINIT-SPEC-008` | Extend the agent-output contract spec to define how streaming relates to the v3 envelope (same command names, different output shape) |
| Update | SPEC | `MEMINIT-SPEC-006` | Register the new `STREAM_*` and `CACHE_*` error codes with normative `explain` semantics |
| New | SPEC | `MEMINIT-SPEC-011` NDJSON Streaming Contract | Normative record schema, ordering rules, error semantics, and version policy |
| New | FDD | Streaming Emitter and Incremental Index | Implementation boundary for the shared emitter, the incremental rebuild algorithm, and the cache format |
| Update | RUNBOOK | Agent Integration and Upgrade Workflow | Document when to use NDJSON vs standard JSON, how to invalidate the cache, and how to debug a truncated stream |
| Conditional update | PLAN | `MEMINIT-PLAN-003` | Only if Phase 5 sequencing or completion criteria move materially during delivery |

Note on SPEC numbering: existing specs run 001–008 plus 010, so 011 is
the next free number. If SPEC-009 is already reserved by other work at
the time of delivery, the new streaming spec takes the next free
number and this plan is updated in-place to match.

Every delivery slice in this phase must satisfy the repository's
atomic-unit rule: code, docs, and tests move together.

## 3. Work Breakdown

### 3.1 Workstream A: Streaming Contract Definition

Problem:

- MEMINIT-PRD-005 §FR-3 currently describes NDJSON as a SHOULD-level
  option with no normative record schema. Without a locked contract,
  every implementing command will drift.
- Consumers need to know exactly how a stream begins, progresses, and
  ends, and how mid-stream failures are signalled, before any command
  can be implemented safely.

#### 3.1.1 Interface shape

Streaming is opt-in per invocation via the existing `--format` flag:

- `--format ndjson` enables streaming.
- `--format json` continues to produce the single-object v3 envelope
  (unchanged).
- `--format text` and `--format md` remain unchanged.

No new top-level flag is introduced. This keeps the CLI surface small
and lets `command_output_handler` dispatch on the existing `format`
parameter.

Commands that do not support streaming raise a usage error
(`STREAM_UNSUPPORTED_FORMAT` with a specific message pointing to the
capabilities entry) when invoked with `--format ndjson`. This is
deterministic and matches the pattern used throughout this workstream.
`E_INVALID_FILTER_VALUE` remains reserved for genuinely incompatible
flag combinations (e.g., `--no-cache` with `--rebuild-cache`).

#### 3.1.2 Record schema

Every record is a single line of UTF-8-encoded JSON terminated by a
single `\n` (LF). No `\r\n`, no trailing empty lines, no leading BOM.
Records are sorted-key serialised using the same canonicalisation
helper that `format_envelope` uses, so identical logical records
produce identical bytes.

The stream carries exactly five record types:

| `record_type` | When emitted                                                | Count per stream          |
| ------------- | ----------------------------------------------------------- | ------------------------- |
| `header`      | First record of every stream                                | exactly 1                 |
| `item`        | Per-entity payload (node, edge, action, namespace)          | 0..N                      |
| `progress`    | Optional coarse-grained progress update                     | 0..N                      |
| `error`       | Terminal record on operational failure                      | 0 or 1 (terminal)         |
| `summary`     | Terminal record on successful completion                    | exactly 1 (terminal)      |

Each stream ends with either a `summary` record (success) or an
`error` record (failure). A stream that ends without one of those
terminators is malformed.

Common required fields on every record:

| Field                      | Type   | Notes                                                                                                    |
| -------------------------- | ------ | -------------------------------------------------------------------------------------------------------- |
| `stream_schema_version`    | string | `"1.0"` for this phase. Locked once shipped.                                                             |
| `record_type`              | string | One of the five values above.                                                                            |
| `command`                  | string | Canonical command name (matches the non-streaming envelope `command` field).                             |
| `sequence`                 | int    | Zero-based monotonically increasing record index within the stream. The `header` record has `sequence: 0`. |

`header`-only fields: `run_id` (UUIDv4), optional `correlation_id`,
optional `root` (repo-aware commands), `started_at` (ISO-8601,
optional, gated by `--include-timestamp`).

`item`-only fields: `kind` (string — see per-command `kind` catalogues
in §3.3) and `data` (object — the entity payload).

`progress`-only fields: `processed` (int), optional `total` (int when
known in advance, else omitted), optional `stage` (short string).
Progress records are informational; consumers MAY ignore them.
Emitting progress records is OPTIONAL per command (see §3.3).

`error`-only fields: `error` (object with `code`, `message`, optional
`details`) mirroring the non-streaming error envelope. After an
`error` record, no further records may be emitted.

`summary`-only fields: `success` (boolean, always `true` for
`summary`), `data` (object — the summary payload equivalent to a
non-streaming `data`), `warnings` (array), `violations` (array),
`advice` (array), optional `counts` (object with per-`kind` counters
derived from the item records). The summary's `data` must contain the
same fields that the non-streaming `data` would contain, minus any
fields that were emitted as individual items.

Ordering rules:

1. `header` is always sequence 0.
2. `item` records are emitted in command-specific deterministic order
   (per §3.3 per-command rules). Reordering produces a malformed
   stream.
3. `progress` records may be interleaved with `item` records but never
   before `header` or after `summary`/`error`.
4. `summary` or `error` is always the last record.
5. `sequence` increases monotonically with no gaps.

Determinism:

- Given identical inputs, the full sequence of records (including
  their `sequence` numbers) is byte-identical across runs on the same
  machine and across machines. The only varying field is `run_id` in
  the header.
- `progress` records, if emitted, are deterministic in position (they
  fire at fixed processed-count boundaries, not wall-clock
  boundaries).

#### 3.1.3 Error signalling

Mid-stream failures are signalled by a terminal `error` record:

- The emitter catches `MeminitError` and unexpected exceptions in the
  producer loop.
- It writes a single `error` record with the canonical `ErrorCode`
  value in `error.code`, a stable message, and structured `details`
  where applicable.
- No further records are written; the command exits with the exit
  code mapped by `exit_code_for_error`.
- Records emitted before the failure remain valid and parseable.

New error codes introduced by streaming (see §3.3.6 and §3.4.5 for
command-level additions):

| Code                       | Emitted by           | `resolution_type` |
| -------------------------- | -------------------- | ----------------- |
| `STREAM_UNSUPPORTED_FORMAT` | any command with `--format ndjson` where the capability is not advertised | `manual` |
| `STREAM_PRODUCER_FAILED`   | emitter wrapping an unexpected producer exception | `manual` |
| `STREAM_INTERRUPTED`       | signal handler on SIGINT/SIGTERM during emission | `manual` |

#### 3.1.4 Capability advertisement

The capabilities registry gains one new per-command field:

- `supports_ndjson: bool` — default `False`. Only commands that
  actually implement the streaming contract set it to `True`.

The global `features.streaming` flag in `capabilities.py` flips from
`False` to `True` when at least one command reports
`supports_ndjson: True`. Agents MUST consult the per-command flag
before invoking `--format ndjson`.

#### 3.1.5 Schema artifacts

Two schema artifacts are introduced, mirroring the pattern used for
the v3 envelope:

- `src/meminit/core/assets/agent-output.stream.schema.v1.json` —
  bundled schema used by tests and consumable at runtime.
- `docs/20-specs/agent-output.stream.schema.v1.json` — the docs-tree
  copy referenced by MEMINIT-SPEC-011.

Both copies are kept byte-identical by a contract test.

#### 3.1.6 Implementation tasks

1. Draft MEMINIT-SPEC-011 defining the record schema, ordering rules,
   and error semantics.
2. Add `"ndjson"` to the `--format` choice list in
   `src/meminit/cli/shared_flags.py`.
3. Author the two JSON Schema artifacts in §3.1.5.
4. Add `supports_ndjson` to `register_capability` as a keyword
   argument with default `False`.
5. Wire the global `features.streaming` flag in
   `src/meminit/core/use_cases/capabilities.py` to derive from the
   registry rather than being hardcoded.
6. Add the three `STREAM_*` error codes to `ErrorCode`,
   `ERROR_EXPLANATIONS`, and `exit_code_for_error`.

Acceptance criteria:

1. MEMINIT-SPEC-011 is drafted and reviewed before Workstreams B and C
   are finalised.
2. Both schema copies validate each of the five record types using a
   fixture-based contract test.
3. `meminit capabilities --format json` reports `supports_ndjson` per
   command and `features.streaming: true` once at least one command
   has opted in.
4. `meminit index --format ndjson` on a command that has not opted in
   fails with `STREAM_UNSUPPORTED_FORMAT` and exit code 64 (usage).
5. The schema disallows unknown top-level fields
   (`additionalProperties: false` on the per-record-type definitions).

### 3.2 Workstream B: Shared Streaming Emitter Infrastructure

Problem:

- If each command hand-rolls its own streaming behaviour, the contract
  will drift immediately. The shared emitter is what keeps every
  streaming command byte-compatible with the SPEC-011 record schema.
- The existing `command_output_handler` is single-object oriented: it
  assumes a use-case returns a single `data` payload and then builds
  one envelope. Streaming requires a producer/consumer shape where
  the CLI adapter walks a generator and writes as it goes.

#### 3.2.1 Module boundary

New module: `src/meminit/cli/streaming.py`.

Public surface:

- `class StreamEmitter` \u2014 a small, stateful helper owned by the CLI
  adapter for the lifetime of one command invocation.
- `def streaming_output_handler(...) -> None` \u2014 parallel to the
  existing `command_output_handler`. Callers pass a producer callable
  plus the same flag-bundle (`format`, `output`, `correlation_id`,
  etc.) they would have passed to the non-streaming handler.
- `class StreamingProducer(Protocol)` \u2014 typed protocol describing
  what a streaming use case must expose (see \u00a73.2.3).

Nothing from this module is imported by use cases. Use cases remain
pure producers; the CLI layer is the only place that writes to
stdout.

#### 3.2.2 `StreamEmitter` responsibilities

`StreamEmitter` encapsulates:

- Opening the output channel. For `--output -` (default) it holds a
  reference to `sys.stdout`. For `--output <path>` it opens the file
  with `ensure_safe_write_path` and writes records to it instead of
  stdout, preserving the same byte layout.
- Maintaining the monotonic `sequence` counter (starts at 0).
- Serialising records with the canonical sorted-key helper already
  used by `format_envelope`, followed by a single `\n`.
- Calling `stream.flush()` after every record so that consumers see
  the record before the producer yields the next one. This is the
  mechanism that delivers the constant-memory guarantee in \u00a72.1.
- Emitting the `header` record at construction time from the
  envelope-builder's run metadata (`run_id`, optional
  `correlation_id`, optional `root`, optional `started_at`).
- Providing `emit_item(kind, data)`, `emit_progress(processed, total,
  stage)`, `emit_error(error_code, message, details)`, and
  `emit_summary(data, warnings, violations, advice, counts)` methods
  that build the appropriate record shape and delegate to the shared
  serialiser.
- Enforcing ordering invariants as asserts so mis-sequenced calls
  fail loudly in tests (e.g. `emit_item` after `emit_summary` raises
  `AssertionError` in test builds).
- Computing per-`kind` counters automatically from `emit_item` calls
  so the producer does not have to track them itself.

`StreamEmitter` is not re-entrant. A given command invocation uses
exactly one instance.

#### 3.2.3 Producer protocol

```python
class StreamingProducer(Protocol):
    def produce(self, emit: StreamEmitter) -> SummaryPayload: ...
```

- The producer receives a ready-to-use emitter and pushes items via
  `emit.emit_item(kind, data)` (and optionally `emit.emit_progress`).
- It returns a typed `SummaryPayload` describing the final summary
  (`data`, `warnings`, `violations`, `advice`). The emitter then
  wraps that in a `summary` record and writes it.
- Raising `MeminitError` or any exception inside `produce` triggers
  the emitter's terminal `error` record path (\u00a73.2.4).

This shape keeps use cases testable without the CLI layer: a unit
test can pass a fake emitter that records calls into a list and
assert on the sequence.

#### 3.2.4 Error path

- `streaming_output_handler` wraps `produce()` in a try/except.
- `MeminitError` subclasses: emit an `error` record using the
  exception's `code` and `message`, then exit with
  `exit_code_for_error`.
- Unexpected exceptions: emit an `error` record with
  `STREAM_PRODUCER_FAILED` and the exception class name plus a
  stable message (never the traceback on stdout). Log the traceback
  on stderr via `log_operation` and exit with `EXIT_INTERNAL_ERROR`.
- `SIGINT`/`SIGTERM` caught by a signal handler registered by the
  handler: emit a `STREAM_INTERRUPTED` error record and exit with
  the platform's default signal exit code. The handler is deregistered
  on normal exit.
- On any error path, the emitter must flush the `error` record before
  the process exits so consumers see a terminal record.

#### 3.2.5 Stdout / stderr isolation

- `streaming_output_handler` binds the emitter to `sys.stdout` (or
  the `--output` target) and never writes anything else there.
- All diagnostics go through `log_operation`, which already writes
  to the configured log destination (stderr or `MEMINIT_LOG_FILE`).
- A dedicated contract test
  (`tests/cli/test_streaming_stdout_isolation.py`) runs each
  streaming command with a populated `MEMINIT_LOG_FILE=-`
  environment variable and asserts that every line on stdout parses
  as JSON and matches SPEC-011, while stderr is allowed to contain
  arbitrary text.

#### 3.2.6 Implementation tasks

1. Create `src/meminit/cli/streaming.py` with `StreamEmitter`,
   `StreamingProducer`, and `streaming_output_handler`.
2. Extract the sorted-key JSON serialiser used by `format_envelope`
   into a shared helper (if not already shared) so the emitter and
   the envelope builder use the same canonicalisation path.
3. Add a signal handler that wires `SIGINT`/`SIGTERM` to a clean
   `STREAM_INTERRUPTED` emission.
4. Add `tests/cli/test_stream_emitter.py` covering: sequence
   monotonicity, header-first ordering, summary-terminal ordering,
   error-terminal ordering, counters accuracy, and byte-identity
   across repeated runs on the same fixture input.
5. Add `tests/cli/test_streaming_stdout_isolation.py` covering every
   opted-in command.

Acceptance criteria:

1. `StreamEmitter` is the only place in the codebase that writes
   NDJSON records to stdout; grep for `json.dumps` plus a write to
   `sys.stdout` in streaming code paths returns zero hits outside
   this module.
2. The emitter test suite demonstrates byte-identical output for
   identical inputs across two runs (with `run_id` stripped).
3. Mid-producer exceptions always produce a terminal `error` record
   and never a truncated `item` line.
4. `log_operation` emissions never appear on stdout during a
   streaming run.
5. Counters reported in the `summary` record match the count of
   `item` records per `kind`.

### 3.3 Workstream C: Command Rollout for Large-Output Surfaces

Problem:

- Streaming must land where it materially helps rather than being added
  indiscriminately. Three commands dominate large-output behaviour in
  Meminit today: `index`, `scan`, and `context --deep`. Each has a
  different natural record shape, but all three must obey the SPEC-011
  contract.

#### 3.3.1 Command matrix

| Command         | `kind` catalogue                          | Item ordering rule                                                                                   | Summary payload                                                                 |
| --------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `index`         | `node`, `edge`                            | `node` records sorted by `document_id` ascending; `edge` records grouped after all nodes, sorted by `(source, target, type)` | `{"index_version", "node_count", "edge_count", "artifact_path"}`                |
| `scan`          | `file`, `suggestion`                      | `file` records sorted by repo-relative path; `suggestion` records grouped after all files, sorted by `(severity, code, path)` | `{"files_scanned", "suggestion_count", "config_preview"}`                       |
| `context --deep` | `namespace`, `document_type`, `document` | `namespace` records first (sorted by `namespace.name`), `document_type` next (sorted by `type`), `document` last (sorted by `document_id`) | `{"repo_prefix", "namespace_count", "document_type_count", "document_count"}`  |

`progress` records are OPTIONAL for all three commands in this phase.
If emitted, they fire every 100 processed items for `index` and
`scan`, and every 50 processed documents for `context --deep`.

#### 3.3.2 `meminit index` streaming

Producer refactor:

- `IndexRepositoryUseCase.execute()` currently returns a fully
  materialised artifact dict. Add
  `IndexRepositoryUseCase.stream(emit: StreamEmitter) -> SummaryPayload`.
- `stream()` delegates to a private generator
  `_iter_nodes_and_edges()` that yields `(kind, payload)` tuples in
  the ordering rule above. The generator must not accumulate the
  full node or edge list in memory beyond what the discovery step
  already requires.
- `stream()` still writes the persisted index artifact to disk
  (`.meminit/index.json`) atomically using the existing write helper.
  The persisted artifact is the canonical output and remains
  byte-identical between streaming and non-streaming modes.
- The `summary` payload carries the artifact's absolute-to-repo path
  as a repo-relative POSIX string in `artifact_path`, plus the final
  `node_count` and `edge_count` matching the persisted file.

CLI wiring:

- `src/meminit/cli/commands/index.py` (or wherever the `index`
  command is declared) branches on `format`: `ndjson` calls
  `streaming_output_handler(...)`; anything else keeps the existing
  path.
- `register_capability("index", supports_ndjson=True, ...)`.

#### 3.3.3 `meminit scan` streaming

Producer refactor:

- The scanner currently builds a full report object before
  serialisation. Introduce a `ScanReportProducer.stream(emit)`
  method that yields per-file `file` records as each file is
  classified, then emits `suggestion` records in a single sorted
  pass over the aggregated suggestions.
- The summary payload reuses the existing `config_preview` object
  shape so downstream consumers can read the proposed
  `docops.config.yaml` snippet from the summary without re-running
  scan.

CLI wiring:

- `src/meminit/cli/commands/scan.py` branches on `format` and calls
  the streaming handler for `ndjson`.
- `register_capability("scan", supports_ndjson=True, ...)`.

#### 3.3.4 `meminit context --deep` streaming

Producer refactor:

- The existing `context` command has two modes: default (summary
  only) and `--deep` (includes every document). Streaming is only
  opted in for `--deep`; default mode has bounded output and gains
  no meaningful benefit from streaming.
- `ContextUseCase.stream_deep(emit)` yields namespaces, then
  document types, then per-document entries in the ordering rule
  above.
- A call of `meminit context --format ndjson` without `--deep`
  fails with `STREAM_UNSUPPORTED_FORMAT` and the explain entry
  points operators to add `--deep`.

CLI wiring:

- Capability registration is conditional: the command advertises
  `supports_ndjson=True` but gates it on `--deep` at runtime.

#### 3.3.5 Shared concerns

- Every opted-in command extends the same non-streaming
  integration test: a `--format json` run produces a v3 envelope
  whose `data` matches the aggregated records from a
  `--format ndjson` run on the same fixture, proving output
  equivalence.
- Every opted-in command adds a golden-stream fixture under
  `tests/fixtures/streaming/<command>/` containing the expected
  line-by-line NDJSON for a small but representative repo.

#### 3.3.6 Implementation tasks

1. Add streaming producers for `index`, `scan`, and `context --deep`
   (one PR slice per command, sequenced per \u00a74.1).
2. Wire each CLI command to dispatch on `format`.
3. Register each command's `supports_ndjson` capability.
4. Author golden-stream fixtures plus byte-equality tests.
5. Add the equivalence test between `--format json` and aggregated
   `--format ndjson` output for each command.
6. Update MEMINIT-PRD-005 \u00a7FR-3 to promote NDJSON from SHOULD to
   MUST for these three commands.

Acceptance criteria:

1. `meminit index --format ndjson`, `meminit scan --format ndjson`,
   and `meminit context --deep --format ndjson` each produce a
   SPEC-011-conformant stream on a 50-doc fixture.
2. The persisted index artifact is byte-identical between
   `--format json` and `--format ndjson` modes.
3. `meminit capabilities --format json` lists all three commands
   with `supports_ndjson: true` and the global
   `features.streaming: true`.
4. Each command's golden-stream fixture is byte-identical on
   repeated runs (with `run_id` normalised).
5. `meminit context --format ndjson` (without `--deep`) fails with
   `STREAM_UNSUPPORTED_FORMAT` and exit code 64.

### 3.4 Workstream D: Incremental Index Rebuilds

Problem:

- Streaming helps with output size but does not by itself reduce
  redundant recomputation in larger repositories. On a 5000-document
  repo, rebuilding the full index from scratch on every invocation
  is the dominant cost and defeats the scale targets in \u00a7Context.
- Incremental rebuilds must remain deterministic: the artifact
  produced by an incremental rebuild must be byte-identical to a
  full rebuild on the same final repo state, with no hidden mutable
  global state and no ordering drift.

#### 3.4.1 Fingerprint model

A file fingerprint is the tuple
`(path, size, mtime_ns, content_sha256)` serialised as a JSON object.
`content_sha256` is the lowercase hex digest of the file's byte
content computed with `hashlib.sha256`. `mtime_ns` is included only
as a fast-path optimisation (see \u00a73.4.3); the authoritative
invalidation signal is `content_sha256`.

A manifest fingerprint covers the inputs to the index as a whole:

```json
{
  "manifest_schema_version": "1.0",
  "meminit_version": "<package version>",
  "index_version": "1.0",
  "config_sha256": "<sha256 of docops.config.yaml>",
  "schema_sha256": "<sha256 of docs/00-governance/metadata.schema.json>",
  "files": [
    {"path": "docs/...", "size": 1234, "mtime_ns": 17..., "sha256": "..."}
  ]
}
```

- `files` is sorted by `path` ascending for deterministic on-disk
  ordering.
- Any change to `meminit_version`, `index_version`, `config_sha256`,
  or `schema_sha256` invalidates the entire cache and forces a full
  rebuild. This is the safe default: bumping any of those values
  can alter discovery or parsing rules in ways the cache cannot
  reason about.

#### 3.4.2 Cache storage layout

Cache root: `.meminit/cache/index/` under the repo root. Layout:

```text
.meminit/
  cache/
    index/
      manifest.json          # serialised manifest fingerprint
      nodes/<document_id>.json   # per-document parsed node payload
      edges/<document_id>.json   # per-document extracted edge list
```

- All writes go through `ensure_safe_write_path` and the atomic
  temp-file-plus-`os.replace` pattern.
- `.meminit/cache/` is added to the generated `.gitignore` scaffold
  written by `meminit init` so the cache never enters version
  control.
- The cache is single-writer: `meminit index` takes a file lock at
  `.meminit/cache/index/.lock` for the duration of a rebuild.
  Concurrent invocations either block on the lock or exit with
  `CACHE_LOCK_HELD` and exit code 73.
- Corrupted cache entries (malformed JSON, missing keys, mismatched
  hash) are treated as cache misses for that specific document and
  the document is fully recomputed. A `CACHE_ENTRY_INVALID` warning
  is added to the summary record.

#### 3.4.3 Incremental algorithm

Inputs to a rebuild: the current repo contents plus the cache
manifest from the previous run.

Deterministic algorithm, executed top-to-bottom:

1. Load the existing `manifest.json`. If missing, proceed as a full
   rebuild with an empty previous manifest.
2. If `meminit_version`, `index_version`, `config_sha256`, or
   `schema_sha256` differ from the current run's values, discard
   the entire cache and fall through to full rebuild. Emit a
   `progress` record with `stage: "cache_invalidated_global"` when
   streaming.
3. Enumerate governed docs using the existing discovery code to
   produce the new candidate file list.
4. For each candidate file compute its new fingerprint. Two-stage
   comparison against the previous manifest:
   - Fast path: if `(size, mtime_ns)` match the previous manifest
     entry, reuse the previous `sha256` without reading file bytes.
   - Slow path: compute `sha256` from bytes; if it matches the
     previous entry, mark the file as unchanged.
5. Classify each file into one of four buckets:
   - `added` \u2014 present now, absent in previous manifest.
   - `removed` \u2014 absent now, present in previous manifest.
   - `changed` \u2014 fingerprint differs.
   - `unchanged` \u2014 fingerprint matches.
6. Reuse cached node and edge payloads for `unchanged` files.
   Recompute for `added` and `changed` files. Drop cache entries
   for `removed` files.
7. Because edges can cross document boundaries, any edge whose
   source document is in `changed` or whose target document is in
   `added`/`removed` is recomputed. Remaining edges from
   `unchanged` sources keep their cached payloads.
8. Merge the recomputed and cached fragments in the canonical
   sorted order defined in \u00a73.3.1. Serialise the final artifact.
9. Write per-document cache entries for all `added`/`changed`
   files. Rewrite `manifest.json` atomically as the last step.

The algorithm is a pure function of the inputs. There is no hidden
mutable state.

#### 3.4.4 Cache-control flags

`meminit index` gains two new flags:

- `--no-cache` \u2014 skip the incremental path entirely. The cache is
  neither read nor written. Equivalent to a cold full rebuild.
- `--rebuild-cache` \u2014 delete the cache directory and perform a
  full rebuild, repopulating the cache at the end. Use when the
  cache is suspected of corruption.

Both flags are mutually exclusive; combining them raises
`E_INVALID_FILTER_VALUE`.

#### 3.4.5 New error codes

| Code                   | Emitted when                                                         | `resolution_type` |
| ---------------------- | -------------------------------------------------------------------- | ----------------- |
| `CACHE_LOCK_HELD`      | Another `meminit index` holds the cache lock                         | `manual`          |
| `CACHE_ENTRY_INVALID`  | A cache entry fails schema or hash validation (warning-level)        | `auto`            |
| `CACHE_WRITE_FAILED`   | Atomic rewrite of `manifest.json` or any cache entry fails           | `manual`          |

`CACHE_ENTRY_INVALID` is warning-level and surfaces in the
`warnings` array of the summary record; it does not fail the run.
The other two are error-level.

#### 3.4.6 Observability

- Every rebuild emits one `log_operation` block at completion with
  counts for `added`, `removed`, `changed`, `unchanged`, plus
  elapsed wall time.
- When streaming, these counters also appear in the summary
  record's `data` under a `rebuild` key:
  `{"rebuild": {"mode": "incremental" | "full", "added": N, ...}}`.
- The `meminit index --explain-cache` diagnostic flag prints the
  current manifest summary (counts and SHAs only, not the full
  file list) to stdout as a standard v3 envelope, for debugging
  without invoking a rebuild.

#### 3.4.7 Implementation tasks

1. Add `src/meminit/core/services/index_cache.py` implementing the
   manifest model, cache I/O, and fingerprint comparison.
2. Refactor `IndexRepositoryUseCase` to consume the cache service
   and classify files per \u00a73.4.3.
3. Add the three `CACHE_*` error codes, their explanations, and
   exit-code mappings.
4. Add `--no-cache`, `--rebuild-cache`, and `--explain-cache` flags
   to the `index` command.
5. Update `meminit init` to include `.meminit/cache/` in the
   generated `.gitignore` scaffold.
6. Add unit tests for the cache service (hash collisions are not a
   concern for this phase; tests cover algorithmic correctness).
7. Add end-to-end tests covering cold full rebuild, warm no-change
   rebuild, single-file-changed rebuild, added-file rebuild,
   removed-file rebuild, global-invalidation rebuild, and cache
   corruption recovery.

Acceptance criteria:

1. A warm no-change rebuild on a 1000-doc fixture reads zero file
   bytes for content (only manifest plus mtime/size checks) and
   completes within the 2-second scale target.
2. An incremental rebuild produces a `.meminit/index.json` artifact
   that is byte-identical to a full rebuild on the same final repo
   state, verified by SHA-256 comparison across all seven E2E
   scenarios.
3. Deleting `.meminit/cache/` and re-running `meminit index`
   produces the same artifact as before deletion.
4. Cache corruption (manually truncating a cache entry) produces a
   `CACHE_ENTRY_INVALID` warning and a correct artifact.
5. Concurrent `meminit index` invocations on the same repo either
   serialise on the lock or fail with `CACHE_LOCK_HELD`; they
   never corrupt the cache.
6. `meminit index --explain-cache` reports the manifest summary
   without triggering a rebuild.

### 3.5 Workstream E: Scale and Streaming Fixture Matrix

Problem:

- Streaming and incremental rebuilds cannot be trusted without
  fixtures that exercise large-output behaviour, partial updates,
  and interruption paths. Those fixtures must be deterministic and
  cheap enough to run in CI.

#### 3.5.1 Required fixture scenarios

| ID  | Name                             | Shape                                                  | Purpose                                                                      |
| --- | -------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------- |
| S01 | `tiny`                           | 5 docs                                                 | Smoke test the NDJSON contract against every opted-in command                |
| S02 | `medium`                         | 50 docs, mixed types                                   | Golden-stream parity between `--format json` and `--format ndjson`           |
| S03 | `large`                          | 1000 generated docs                                    | Incremental warm-no-change 2-second target; memory ceiling check             |
| S04 | `scale`                          | 5000 generated docs (`@pytest.mark.slow`)              | Full-rebuild 60-second and 256 MB ceiling targets                            |
| S05 | `single_file_changed`            | `large` + 1 edited doc                                 | Incremental recomputes only the changed file                                 |
| S06 | `single_file_added`              | `large` + 1 new doc                                    | Added-file bucket exercise                                                   |
| S07 | `single_file_removed`            | `large` minus 1 doc                                    | Removed-file bucket exercise                                                 |
| S08 | `edge_crosses_changed`           | Two docs, one edits its `related_ids` to add the other | Cross-doc edge recomputation correctness                                     |
| S09 | `config_changed`                 | `medium` + `docops.config.yaml` mutation               | Global cache invalidation via `config_sha256` bump                           |
| S10 | `schema_changed`                 | `medium` + `metadata.schema.json` mutation             | Global cache invalidation via `schema_sha256` bump                           |
| S11 | `version_bump`                   | `medium` with simulated version change                 | Global cache invalidation via `meminit_version` bump                         |
| S12 | `corrupt_cache_entry`            | `medium` + one truncated cache file                    | `CACHE_ENTRY_INVALID` warning path                                           |
| S13 | `missing_manifest`               | `medium` + manifest file deleted                       | Graceful degradation to full rebuild                                         |
| S14 | `concurrent_index`               | Two processes invoking `meminit index` simultaneously  | `CACHE_LOCK_HELD` path                                                       |
| S15 | `stream_sigint`                  | `large` interrupted mid-stream                         | `STREAM_INTERRUPTED` terminal record                                         |
| S16 | `stream_producer_failure`        | `medium` with one document crafted to raise            | `STREAM_PRODUCER_FAILED` terminal record                                     |
| S17 | `context_deep_only`              | `medium`                                               | `context --format ndjson` without `--deep` fails with `STREAM_UNSUPPORTED_FORMAT` |
| S18 | `scan_large_suggestions`         | Repo with 200+ scan suggestions                        | Ordering and per-kind counter correctness                                    |
| S19 | `stdout_isolation`               | `medium` with `MEMINIT_LOG_FILE=-`                     | Every stdout line parses as JSON; stderr receives logs                       |
| S20 | `determinism_two_runs`           | `medium` run twice                                     | Byte-identical streams modulo `run_id`                                       |

Scenarios S03 and S04 are gated behind `@pytest.mark.slow` and skipped
in the default CI matrix but run on demand and in the nightly suite.
All other scenarios are part of the default suite.

Generated fixtures (S03, S04, S05, S06, S07) are produced by a
deterministic fixture-builder function in
`tests/fixtures/streaming/generators.py` that accepts a seed and
emits byte-identical trees across runs.

#### 3.5.2 Determinism and isolation test surfaces

- `tests/cli/test_streaming_determinism.py` asserts S20 byte-identity
  for every opted-in command (ignoring `run_id` and timestamps).
- `tests/cli/test_streaming_stdout_isolation.py` covers S19 for every
  opted-in command.
- `tests/cli/test_streaming_equivalence.py` covers the
  json-vs-ndjson equivalence check from \u00a73.3.5 for every opted-in
  command.
- `tests/core/services/test_index_cache.py` covers S05\u2013S14 against
  the cache service directly without the CLI layer.

#### 3.5.3 Implementation tasks

1. Author the fixture-builder generator and commit the tiny and
   medium fixtures as static trees under `tests/fixtures/streaming/`.
2. Add the four new test modules listed in \u00a73.5.2.
3. Mark the 1000-doc and 5000-doc scenarios with
   `@pytest.mark.slow` and ensure they are wired into the nightly
   job via an existing or new Makefile/CI target.
4. Add a memory-ceiling check using `tracemalloc.get_traced_memory()`
   snapshots in the S04 test (soft assertion logging the peak, hard
   assertion only on the 256 MB ceiling).

Acceptance criteria:

1. All scenarios S01\u2013S20 have a corresponding test that passes on
   a clean checkout.
2. S03 and S04 complete within their scale targets when run in
   nightly CI.
3. S20 demonstrates byte-identical streams for every opted-in
   command.
4. The fixture-builder generator produces identical trees for
   identical seeds across two runs (golden-tree hash test).

### 3.6 Workstream F: Documentation, Upgrade Notes, and Operator Guidance

Problem:

- Streaming and incremental rebuilds are only successful if the
  operator guidance is as clear as the implementation. Without
  docs, agents and human operators cannot tell when NDJSON is
  appropriate or how to recover from cache issues.

Documentation scope (maps to \u00a72.2 outputs):

1. **MEMINIT-PRD-005 update** \u2014 promote NDJSON from SHOULD to MUST
   for `index`, `scan`, and `context --deep`; record the
   incremental-rebuild requirement; cross-reference MEMINIT-SPEC-011
   and the new FDD.
2. **MEMINIT-SPEC-008 update** \u2014 add a section titled "Streaming
   and the v3 envelope" that states: streaming records live in a
   separate schema (SPEC-011); the `command`, `run_id`, and
   `correlation_id` semantics are shared; a stream's terminal
   `summary` record is logically equivalent to the `data` of the
   non-streaming envelope for the same inputs.
3. **MEMINIT-SPEC-006 update** \u2014 register the three `STREAM_*`
   and three `CACHE_*` codes with normative `explain` entries.
4. **MEMINIT-SPEC-011 new** \u2014 full streaming contract spec per
   \u00a73.1.
5. **New FDD** \u2014 implementation-side doc covering the emitter,
   producer protocol, cache format, and rebuild algorithm. Lives
   under `docs/50-fdd/` following the FDD template.
6. **Runbook update** \u2014 extend the Agent Integration and Upgrade
   Workflow runbook with: a decision table for JSON vs NDJSON; a
   troubleshooting section for truncated streams, stale cache,
   lock contention, and corruption warnings; upgrade notes for
   consumers moving from Phase 4 to Phase 5.

Cross-repo rollout:

- The external testbed repository must be exercised with the new
  `--format ndjson` and incremental-rebuild paths before Phase 5
  closeout. An explicit testbed checklist is added to the runbook.

Implementation tasks:

1. Draft or update the six governed documents above in step with
   the code PRs (atomic-unit rule).
2. Add a short cross-link from the README `meminit` CLI overview
   to MEMINIT-SPEC-011 so agents discovering the CLI can find the
   streaming contract.
3. Run `meminit check` after each doc update and resolve any new
   violations before the PR is marked ready.

Acceptance criteria:

1. All six governed documents are updated or created and pass
   `meminit check`.
2. The runbook contains a decision table that maps agent use
   cases to the recommended `--format` value.
3. The README references MEMINIT-SPEC-011 from the CLI overview
   section.
4. Phase 5 closeout requires the testbed checklist to be marked
   complete on the closing PR.

## 4. Recommended Delivery Sequence

1. Workstream A: Streaming Contract Definition
2. Workstream B: Shared Streaming Emitter Infrastructure
3. Workstream C: Command Rollout for Large-Output Surfaces
4. Workstream D: Incremental Index Rebuilds
5. Workstream E: Scale and Streaming Fixture Matrix
6. Workstream F: Documentation, Upgrade Notes, and Operator Guidance

Reason:

- The streaming contract (A) must be decided and spec'd before any
  command can safely implement streaming.
- Shared infrastructure (B) must land before per-command rollout (C)
  to prevent immediate drift.
- Incremental rebuilds (D) land on top of the stable output model in
  (C); the cache design depends on the finalised producer shape.
- Fixtures (E) are sized to cover both streaming (C) and incremental
  rebuilds (D), so they land once both producers exist.
- Documentation (F) runs continuously with the code PRs per the
  atomic-unit rule; the separate workstream captures the closeout
  docs rather than deferring documentation to the end.

### 4.1 Recommended PR Slices

Each slice is independently reviewable and independently green under
`meminit check` and the test suite.

| PR | Slice                                              | Surfaces touched                                                                                   |
| -- | -------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| 1  | Streaming contract spec and schema artifacts       | MEMINIT-SPEC-011, `agent-output.stream.schema.v1.json` (both copies), SPEC-006 error-code entries  |
| 2  | `--format ndjson` flag and capabilities plumbing   | `shared_flags.py`, `capabilities.py`, `register_capability`, `supports_ndjson` field               |
| 3  | Shared streaming emitter                          | `src/meminit/cli/streaming.py`, emitter tests, stdout isolation test harness                       |
| 4  | `meminit index --format ndjson`                   | Index streaming producer, golden-stream fixture, json/ndjson equivalence test                      |
| 5  | `meminit scan --format ndjson`                    | Scan streaming producer, golden-stream fixture                                                     |
| 6  | `meminit context --deep --format ndjson`          | Context streaming producer, golden-stream fixture, unsupported-format error path                   |
| 7  | Incremental rebuild cache service                 | `index_cache.py`, cache unit tests, `CACHE_*` error codes, `.gitignore` scaffold update            |
| 8  | Incremental rebuild wiring into `meminit index`   | `IndexRepositoryUseCase` refactor, `--no-cache`/`--rebuild-cache`/`--explain-cache` flags, E2E tests |
| 9  | Scale fixtures and nightly job wiring             | Fixture-builder generator, slow-test markers, nightly CI target                                    |
| 10 | PRD-005 / SPEC-008 / FDD / runbook updates        | Governed document closeout; testbed checklist                                                      |

## 5. Exit Criteria for Phase 5

Phase 5 can be considered complete when all of the following are
true:

1. MEMINIT-SPEC-011 is approved and the two schema copies are
   byte-identical.
2. `meminit capabilities --format json` lists `index`, `scan`, and
   `context` with `supports_ndjson` and advertises
   `features.streaming: true`.
3. `meminit index --format ndjson`, `meminit scan --format ndjson`,
   and `meminit context --deep --format ndjson` each pass their
   SPEC-011 conformance, determinism, and json/ndjson equivalence
   tests on the medium fixture.
4. `meminit index` performs incremental rebuilds by default, with
   `--no-cache` and `--rebuild-cache` escape hatches, and produces
   byte-identical artifacts to full rebuilds across all seven
   cache E2E scenarios.
5. `meminit index --explain-cache` reports the current manifest
   summary without triggering a rebuild.
6. The nightly slow test job runs the 1000-doc and 5000-doc scale
   fixtures and enforces the 2-second warm-incremental, 60-second
   full-rebuild, and 256 MB memory ceilings.
7. All three `STREAM_*` and three `CACHE_*` error codes are
   registered in SPEC-006 with `explain` entries and wired into
   `exit_code_for_error`.
8. Stdout isolation tests pass for every opted-in command: every
   stdout line during `--format ndjson` is a valid SPEC-011 record;
   all logs appear on stderr only.
9. MEMINIT-PRD-005, MEMINIT-SPEC-008, MEMINIT-SPEC-006, the new FDD,
   and the operator runbook are updated or created and pass
   `meminit check`.
10. The external testbed has been exercised with `--format ndjson`
    and with incremental rebuilds; the testbed checklist is marked
    complete on the closing PR.
11. All code added in this phase respects the repository engineering
    principles: no function exceeds the soft 40-line limit; no
    `eval`, no `shell=True`, no hidden global mutable state in the
    cache path.
12. `meminit check --format json` reports zero new violations and
    zero new warnings attributable to Phase 5 changes.

## 6. Version History

| Version | Date | Author | Changes |
| ------- | ---- | ------ | ------- |
| 0.1 | 2026-04-14 | GitCmurf | Initial draft created via `meminit new` |
| 0.2 | 2026-04-14 | Codex | Replaced stub with detailed Phase 5 workstreams, sequencing, and exit criteria |
| 0.3 | 2026-04-19 | Augment Agent | Expanded plan to implementation-ready detail matching PLAN-011/012/013: normative NDJSON record schema, shared emitter design, per-command rollout specifics for index/scan/context, incremental rebuild algorithm with cache service and fingerprinting, 20-scenario fixture matrix, PR slicing, and 12 concrete exit criteria |
