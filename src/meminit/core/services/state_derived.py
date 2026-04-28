"""Derived state computation and planning-field validation.

This module provides pure functions that compute readiness, blocker, and
unblock relationships from a ``ProjectState`` plus the set of known
document IDs (sourced from the Phase 2 index).  It also provides the
planning-field validation logic shared by mutation, read, and query paths.

All functions are deterministic: identical inputs produce identical outputs.
No wall-clock time, filesystem mtime, or randomness is consulted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from meminit.core.services.project_state import (
    DEFAULT_PRIORITY,
    DOCUMENT_ID_PATTERN,
    VALID_PRIORITIES,
    ImplState,
    ProjectState,
    ProjectStateEntry,
)
from meminit.core.services.sanitization import MAX_ASSIGNEE_LENGTH, MAX_NOTES_LENGTH


@dataclass(frozen=True)
class DerivedEntry:
    """Computed (never persisted) fields for a single state entry."""

    document_id: str
    ready: bool
    open_blockers: Tuple[str, ...]
    unblocks: Tuple[str, ...]


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation finding for a planning field."""

    code: str
    severity: str
    document_id: str
    message: str
    field: Optional[str] = None


def _is_dep_resolved(dep_id: str, state: ProjectState) -> bool:
    """Check whether a single dependency is resolved (target is Done)."""
    target = state.get(dep_id)
    if target is None:
        return False
    return _normalize_impl(target.impl_state) == "done"


def _normalize_impl(value: str) -> str:
    return value.strip().lower()


def _is_ready(
    entry: ProjectStateEntry,
    state: ProjectState,
) -> bool:
    """An entry is ready iff impl_state is Not Started and all deps/blockers resolve to Done."""
    if _normalize_impl(entry.impl_state) != "not started":
        return False
    for dep_id in entry.depends_on:
        if not _is_dep_resolved(dep_id, state):
            return False
    for dep_id in entry.blocked_by:
        if not _is_dep_resolved(dep_id, state):
            return False
    return True


def _open_blockers_for(
    entry: ProjectStateEntry,
    state: ProjectState,
) -> Tuple[str, ...]:
    """Return sorted IDs from depends_on ∪ blocked_by that are not Done."""
    all_deps = set(entry.depends_on) | set(entry.blocked_by)
    open_ids: List[str] = []
    for dep_id in sorted(all_deps):
        if not _is_dep_resolved(dep_id, state):
            open_ids.append(dep_id)
    return tuple(open_ids)


def _unblocks_for(
    doc_id: str,
    incoming_references: Dict[str, List[str]],
) -> Tuple[str, ...]:
    """Return sorted IDs whose depends_on or blocked_by lists reference this ID."""
    return tuple(incoming_references.get(doc_id, ()))


def _build_incoming_references(state: ProjectState) -> Dict[str, List[str]]:
    """Build a deterministic reverse-reference map from state dependency lists."""
    incoming: Dict[str, List[str]] = {}
    for other_id in sorted(state.entries.keys()):
        other = state.entries[other_id]
        for dep_id in sorted(set(other.depends_on) | set(other.blocked_by)):
            if dep_id == other_id:
                continue
            incoming.setdefault(dep_id, []).append(other_id)
    return incoming


def compute_derived_fields(
    state: ProjectState,
    known_ids: Set[str],
) -> Dict[str, DerivedEntry]:
    """Compute derived fields for every known state/index document ID.

    ``state`` contains the tracked mutable state entries. ``known_ids`` is the
    governed document universe from the index. The returned map includes both
    state-backed entries and index-only IDs so reverse relationships such as
    ``unblocks`` remain visible for governed documents that have no explicit
    ``project-state.yaml`` entry. Index-only IDs are never ready because the
    readiness predicate requires an explicit state entry with ``impl_state`` of
    ``Not Started``.
    """
    result: Dict[str, DerivedEntry] = {}
    incoming_references = _build_incoming_references(state)
    for doc_id in sorted(set(known_ids) | set(state.entries.keys())):
        entry = state.entries.get(doc_id)
        if entry is None:
            result[doc_id] = DerivedEntry(
                document_id=doc_id,
                ready=False,
                open_blockers=(),
                unblocks=_unblocks_for(doc_id, incoming_references),
            )
        else:
            result[doc_id] = DerivedEntry(
                document_id=doc_id,
                ready=_is_ready(entry, state),
                open_blockers=_open_blockers_for(entry, state),
                unblocks=_unblocks_for(doc_id, incoming_references),
            )
    return result


def validate_planning_fields(
    entry: ProjectStateEntry,
    known_ids: Set[str],
) -> List[ValidationIssue]:
    """Validate planning fields for a single entry.

    Returns a list of issues.  Fatal issues have severity ``"fatal"`` and
    should block the mutation.  Warning issues have severity ``"warning"``.
    Advisory issues have severity ``"advisory"``.
    """
    issues: List[ValidationIssue] = []
    doc_id = entry.document_id

    if entry.priority is not None and entry.priority not in VALID_PRIORITIES:
        issues.append(
            ValidationIssue(
                code="STATE_INVALID_PRIORITY",
                severity="fatal",
                document_id=doc_id,
                message=f"Priority '{entry.priority}' is not valid. Must be one of: {', '.join(VALID_PRIORITIES)}.",
                field="priority",
            )
        )

    for dep_id in entry.depends_on:
        _validate_single_dep(dep_id, doc_id, known_ids, issues, "depends_on")

    for dep_id in entry.blocked_by:
        _validate_single_dep(dep_id, doc_id, known_ids, issues, "blocked_by")

    has_self = doc_id in entry.depends_on or doc_id in entry.blocked_by
    if has_self:
        issues.append(
            ValidationIssue(
                code="STATE_SELF_DEPENDENCY",
                severity="fatal",
                document_id=doc_id,
                message=f"Entry '{doc_id}' references itself in depends_on or blocked_by.",
                field="dependencies",
            )
        )

    if entry.assignee is not None and len(entry.assignee) > MAX_ASSIGNEE_LENGTH:
        issues.append(
            ValidationIssue(
                code="STATE_FIELD_TOO_LONG",
                severity="fatal",
                document_id=doc_id,
                message=f"assignee exceeds {MAX_ASSIGNEE_LENGTH} characters ({len(entry.assignee)} chars).",
                field="assignee",
            )
        )

    if entry.next_action is not None and len(entry.next_action) > MAX_NOTES_LENGTH:
        issues.append(
            ValidationIssue(
                code="STATE_FIELD_TOO_LONG",
                severity="fatal",
                document_id=doc_id,
                message=f"next_action exceeds {MAX_NOTES_LENGTH} characters ({len(entry.next_action)} chars).",
                field="next_action",
            )
        )

    return issues


def _validate_single_dep(
    dep_id: str,
    doc_id: str,
    known_ids: Set[str],
    issues: List[ValidationIssue],
    field_name: str,
) -> None:
    """Validate a single dependency ID for format and existence."""
    if not DOCUMENT_ID_PATTERN.match(dep_id):
        issues.append(
            ValidationIssue(
                code="STATE_INVALID_DEPENDENCY_ID",
                severity="fatal",
                document_id=doc_id,
                message=f"Dependency '{dep_id}' in {field_name} does not match document ID pattern (PREFIX-TYPE-NNN).",
                field=field_name,
            )
        )
    elif dep_id not in known_ids:
        issues.append(
            ValidationIssue(
                code="STATE_UNDEFINED_DEPENDENCY",
                severity="warning",
                document_id=doc_id,
                message=f"Dependency '{dep_id}' in {field_name} is not present in the index.",
                field=field_name,
            )
        )


def check_dependency_cycle(
    all_entries: Dict[str, ProjectStateEntry],
) -> List[ValidationIssue]:
    """Check all entries for dependency cycles in depends_on ∪ blocked_by.

    Uses iterative DFS with a visited set.  Returns one issue per unique
    cycle detected.
    """
    adj: Dict[str, List[str]] = {}
    for doc_id, entry in all_entries.items():
        neighbors: List[str] = []
        for dep_id in entry.depends_on:
            if dep_id in all_entries:
                neighbors.append(dep_id)
        for dep_id in entry.blocked_by:
            if dep_id in all_entries:
                neighbors.append(dep_id)
        if neighbors:
            adj[doc_id] = neighbors

    seen_cycles: List[Tuple[str, ...]] = []
    issues: List[ValidationIssue] = []

    for start in sorted(adj):
        stack: List[Tuple[str, List[str], int]] = [(start, [start], 0)]
        rec_stack: Set[str] = {start}

        while stack:
            node, path, idx = stack[-1]
            neighbors = adj.get(node, [])

            if idx >= len(neighbors):
                rec_stack.discard(node)
                stack.pop()
                continue

            stack[-1] = (node, path, idx + 1)
            neighbor = neighbors[idx]

            if neighbor in rec_stack:
                cycle_start = path.index(neighbor) if neighbor in path else -1
                if cycle_start >= 0:
                    cycle_nodes = tuple(path[cycle_start:])
                    rotated = _canonical_cycle_key(cycle_nodes)
                    if rotated not in seen_cycles:
                        seen_cycles.append(rotated)
                        cycle_path = list(rotated) + [rotated[0]]
                        issues.append(
                            ValidationIssue(
                                code="STATE_DEPENDENCY_CYCLE",
                                severity="fatal",
                                document_id=rotated[0],
                                message=f"Dependency cycle detected: {' -> '.join(cycle_path)}",
                                field="dependencies",
                            )
                        )
                continue

            if neighbor in adj:
                stack.append((neighbor, path + [neighbor], 0))
                rec_stack.add(neighbor)

    return issues


def check_status_conflicts(
    all_entries: Dict[str, ProjectStateEntry],
) -> List[ValidationIssue]:
    """Check for advisory status conflicts: Done entry with non-Done dependency."""
    issues: List[ValidationIssue] = []
    for doc_id in sorted(all_entries):
        entry = all_entries[doc_id]
        if _normalize_impl(entry.impl_state) != "done":
            continue
        all_deps = set(entry.depends_on) | set(entry.blocked_by)
        for dep_id in sorted(all_deps):
            dep_entry = all_entries.get(dep_id)
            if dep_entry is not None and _normalize_impl(dep_entry.impl_state) != "done":
                issues.append(
                    ValidationIssue(
                        code="STATE_DEPENDENCY_STATUS_CONFLICT",
                        severity="advisory",
                        document_id=doc_id,
                        message=(
                            f"Entry '{doc_id}' is Done but depends on '{dep_id}' "
                            f"which is '{dep_entry.impl_state}'."
                        ),
                        field="dependencies",
                    )
                )
    return issues


def _canonical_cycle_key(cycle_nodes: Tuple[str, ...]) -> Tuple[str, ...]:
    """Return the lexicographically smallest rotation of a cycle.

    Empty input is returned unchanged so defensive callers get a
    deterministic value instead of a ``min()`` failure.
    """
    if not cycle_nodes:
        return cycle_nodes
    rotations = [cycle_nodes[i:] + cycle_nodes[:i] for i in range(len(cycle_nodes))]
    return min(rotations)


PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def next_selection_key(
    entry: ProjectStateEntry,
    derived: DerivedEntry,
) -> Tuple[int, int, Any, str]:
    """Return the sort key for the next-selection algorithm.

    Order: priority ascending, unblocks count descending, updated ascending,
    document_id ascending.  This produces a total ordering over all entries.
    """
    priority = entry.priority or DEFAULT_PRIORITY
    if priority not in PRIORITY_RANK:
        priority = DEFAULT_PRIORITY
    priority_rank = PRIORITY_RANK[priority]
    unblocks_count = -len(derived.unblocks)
    updated = entry.updated
    return (priority_rank, unblocks_count, updated, entry.document_id)
