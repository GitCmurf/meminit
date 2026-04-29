"""Manage project-state.yaml document entries.

Provides ``set``, ``get``, ``list``, ``next``, and ``blockers`` operations
for the centralized implementation state file.  Auto-populates ``updated``
(UTC) and ``updated_by`` via the actor chain:

1. ``MEMINIT_ACTOR_ID`` environment variable
2. ``git config user.name``
3. System username (``os.getlogin()``)
"""

from __future__ import annotations

import getpass
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.path_utils import load_index_documents
from meminit.core.services.project_state import (
    DEFAULT_PRIORITY,
    STATE_SCHEMA_VERSION,
    VALID_PRIORITIES,
    ImplState,
    ProjectState,
    ProjectStateEntry,
    _normalize_impl_state_value,
    get_state_file_rel_path,
    load_project_state,
    save_project_state,
)
from meminit.core.services.sanitization import MAX_ASSIGNEE_LENGTH, truncate_notes, validate_actor
from meminit.core.services.state_derived import (
    DerivedEntry,
    check_dependency_cycle,
    compute_derived_fields,
    next_selection_key,
    validate_planning_fields,
)


@dataclass(frozen=True)
class StateResult:
    """Result of a state operation."""

    document_id: str
    action: str
    entry: Optional[Dict[str, Any]] = None
    entries: Optional[List[Dict[str, Any]]] = None
    selection: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    blocked: Optional[List[Dict[str, Any]]] = None
    warnings: Optional[List[Dict[str, Any]]] = None
    advice: Optional[List[Dict[str, Any]]] = None


def _resolve_actor(root_dir: Optional[Path] = None) -> str:
    """Resolve the actor ID via the environment chain."""
    from meminit.core.services.sanitization import sanitize_actor

    actor = os.environ.get("MEMINIT_ACTOR_ID")
    if actor and actor.strip():
        return sanitize_actor(actor)

    try:
        cwd = str(root_dir) if root_dir else None
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0 and result.stdout.strip():
            return sanitize_actor(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        return sanitize_actor(getpass.getuser())
    except Exception:
        return "unknown"


def _resolve_document_id(root_dir: Path, document_id: str) -> str:
    """Resolve an unambiguous shorthand document ID to its canonical form."""
    document_id = document_id.strip().upper()
    if "-" not in document_id:
        return document_id

    from meminit.core.services.repo_config import load_repo_layout

    try:
        layout = load_repo_layout(root_dir)
        prefixes = {ns.repo_prefix for ns in layout.namespaces}
    except Exception:
        return document_id

    for prefix in prefixes:
        if document_id.startswith(f"{prefix}-"):
            return document_id

    if document_id.count("-") > 1:
        return document_id

    index_path = layout.index_file
    matched_ids = set()

    if index_path.exists():
        try:
            docs = load_index_documents(index_path)
            for doc in docs:
                doc_id = doc.get("document_id")
                if isinstance(doc_id, str) and doc_id.endswith(f"-{document_id}"):
                    matched_ids.add(doc_id)
        except (FileNotFoundError, ValueError):
            pass

        if len(matched_ids) == 1:
            return matched_ids.pop()
        elif len(matched_ids) > 1:
            raise MeminitError(
                code=ErrorCode.E_STATE_SCHEMA_VIOLATION,
                message=f"Ambiguous shorthand document ID '{document_id}'. "
                f"Multiple existing documents match this shorthand ({', '.join(sorted(matched_ids))}). "
                "Please provide the full document ID.",
            )

    if not matched_ids:
        if len(layout.namespaces) == 1:
            prefix = layout.namespaces[0].repo_prefix
            return f"{prefix}-{document_id}"

        raise MeminitError(
            code=ErrorCode.E_STATE_SCHEMA_VIOLATION,
            message=f"Ambiguous shorthand document ID '{document_id}' in multi-namespace repository. "
            "Please provide the full document ID or run 'meminit index' to enable shorthand resolution.",
        )

    return matched_ids.pop()


def _get_known_ids(root_dir: Path) -> Set[str]:
    """Get the set of known document IDs from the index."""
    from meminit.core.services.repo_config import load_repo_layout

    try:
        layout = load_repo_layout(root_dir)
        index_path = layout.index_file
        if not index_path.exists():
            return set()
        docs = load_index_documents(index_path)
        return {d["document_id"] for d in docs if "document_id" in d}
    except Exception:
        return set()


def _collect_read_validation_warnings(
    state: Optional[ProjectState],
    root_dir: Path,
) -> Tuple[List[Dict[str, Any]], Set[str]]:
    if state is None or not state.entries:
        return [], set()
    from meminit.core.services.project_state import validate_project_state
    from meminit.core.services.state_derived import (
        check_dependency_cycle,
        validate_planning_fields,
    )

    fs_known = _get_known_ids(root_dir)

    from meminit.core.services.repo_config import load_repo_layout

    try:
        layout = load_repo_layout(root_dir)
        valid_impl_states: Optional[List[str]] = []
        for ns in layout.namespaces:
            valid_impl_states.extend(ns.valid_impl_states)
    except Exception:
        valid_impl_states = None

    issues = validate_project_state(state, fs_known, root_dir, valid_impl_states=valid_impl_states)
    state_path = get_state_file_rel_path(root_dir)
    warnings: List[Dict[str, Any]] = []
    skip_doc_ids: Set[str] = set()

    for v in issues:
        w: Dict[str, Any] = {
            "code": v.rule,
            "message": v.message,
            "path": v.file or state_path,
        }
        if v.line:
            w["line"] = v.line
        warnings.append(w)

    for doc_id, entry in state.entries.items():
        if entry.priority is not None and entry.priority not in VALID_PRIORITIES:
            skip_doc_ids.add(doc_id)

    _COVERED_BY_ENTRY_VALIDATORS = {"STATE_INVALID_PRIORITY", "STATE_FIELD_TOO_LONG"}

    for doc_id, entry in state.entries.items():
        planning_issues = validate_planning_fields(entry, fs_known)
        for pi in planning_issues:
            if pi.code in _COVERED_BY_ENTRY_VALIDATORS:
                continue
            warnings.append(
                {
                    "code": pi.code,
                    "message": pi.message,
                    "path": state_path,
                }
            )

    cycle_issues = check_dependency_cycle(state.entries)
    for ci in cycle_issues:
        warnings.append(
            {
                "code": ci.code,
                "message": ci.message,
                "path": state_path,
            }
        )

    if not warnings:
        return [], skip_doc_ids
    return warnings, skip_doc_ids


def _state_excluding_entries(
    state: ProjectState,
    skip_doc_ids: Set[str],
) -> ProjectState:
    if not skip_doc_ids:
        return state
    return ProjectState(
        entries={
            doc_id: entry for doc_id, entry in state.entries.items() if doc_id not in skip_doc_ids
        },
        schema_violations=state.schema_violations,
        schema_version=state.schema_version,
    )


def _resolve_impl_state(root_dir: Path, impl_state: str) -> str:
    from meminit.core.services.repo_config import load_repo_layout

    impl_state = impl_state.strip()
    resolved = ImplState.from_string(impl_state)
    canonical_values = ImplState.canonical_values()
    canonical_lower = {v.lower() for v in canonical_values}
    try:
        layout = load_repo_layout(root_dir)
        seen_custom: Dict[str, str] = {}
        for ns in layout.namespaces:
            for state_name in ns.valid_impl_states:
                lower = state_name.lower()
                if lower not in canonical_lower:
                    seen_custom.setdefault(lower, state_name)
        extra_states = list(seen_custom.values())
    except Exception:
        extra_states = []
    all_valid = canonical_values + extra_states
    custom_canonical_map = {s.lower(): s for s in extra_states}

    if resolved is None and impl_state.lower() not in [v.lower() for v in all_valid]:
        raise MeminitError(
            code=ErrorCode.E_INVALID_FILTER_VALUE,
            message=f"Unknown impl_state: '{impl_state}'",
            details={"value": impl_state, "valid_values": all_valid},
        )
    if resolved is not None:
        return resolved.value
    custom_canonical = custom_canonical_map.get(impl_state.lower())
    return custom_canonical if custom_canonical else impl_state


def _resolve_final_priority(
    priority: Optional[str],
    existing: Optional[ProjectStateEntry],
) -> Optional[str]:
    if priority is not None and priority not in VALID_PRIORITIES:
        raise MeminitError(
            code=ErrorCode.STATE_INVALID_PRIORITY,
            message=f"Priority '{priority}' is not valid. Must be one of: {', '.join(VALID_PRIORITIES)}.",
            details={"value": priority, "valid_values": list(VALID_PRIORITIES)},
        )
    return priority if priority is not None else (existing.priority if existing else None)


def _resolve_assignee(
    assignee: Optional[str],
    existing: Optional[ProjectStateEntry],
) -> Optional[str]:
    if assignee == "":
        return None
    if assignee is not None and len(assignee) > MAX_ASSIGNEE_LENGTH:
        raise MeminitError(
            code=ErrorCode.STATE_FIELD_TOO_LONG,
            message=f"assignee exceeds {MAX_ASSIGNEE_LENGTH} characters ({len(assignee)} chars).",
        )
    return assignee if assignee is not None else (existing.assignee if existing else None)


def _resolve_next_action(
    next_action: Optional[str],
    existing: Optional[ProjectStateEntry],
) -> Optional[str]:
    from meminit.core.services.sanitization import MAX_NOTES_LENGTH

    if next_action == "":
        return None
    if next_action is not None and "\n" in next_action:
        raise MeminitError(
            code=ErrorCode.STATE_FIELD_INVALID_FORMAT,
            message="next_action must not contain embedded newlines.",
        )
    if next_action is not None and len(next_action) > MAX_NOTES_LENGTH:
        raise MeminitError(
            code=ErrorCode.STATE_FIELD_TOO_LONG,
            message=f"next_action exceeds {MAX_NOTES_LENGTH} characters ({len(next_action)} chars).",
        )
    return next_action if next_action is not None else (existing.next_action if existing else None)


def _changed_planning_fields(
    *,
    priority: Optional[str],
    depends_on: Optional[List[str]],
    add_depends_on: Optional[List[str]],
    remove_depends_on: Optional[List[str]],
    clear_depends_on: bool,
    blocked_by: Optional[List[str]],
    add_blocked_by: Optional[List[str]],
    remove_blocked_by: Optional[List[str]],
    clear_blocked_by: bool,
    assignee: Optional[str],
    next_action: Optional[str],
) -> Set[str]:
    fields: Set[str] = set()
    if priority is not None:
        fields.add("priority")
    if depends_on is not None or add_depends_on or remove_depends_on or clear_depends_on:
        fields.add("depends_on")
    if blocked_by is not None or add_blocked_by or remove_blocked_by or clear_blocked_by:
        fields.add("blocked_by")
    if assignee is not None:
        fields.add("assignee")
    if next_action is not None:
        fields.add("next_action")
    return fields


def _issue_applies_to_changed_field(issue: Any, changed_fields: Set[str]) -> bool:
    field = getattr(issue, "field", None)
    if field is None:
        return True
    if field == "dependencies":
        return bool({"depends_on", "blocked_by"} & changed_fields)
    return field in changed_fields


def _resolve_actor_for_set(actor: Optional[str], root_dir: Path) -> str:
    if actor:
        if not validate_actor(actor):
            raise MeminitError(
                code=ErrorCode.E_INVALID_FILTER_VALUE,
                message=f"Invalid actor override: '{actor}'. Must match ^[a-zA-Z0-9._-]+$",
            )
        return actor
    return _resolve_actor(root_dir)


class StateDocumentUseCase:
    """Use case for managing project-state.yaml entries."""

    def __init__(self, root_dir: str):
        self._root_dir = Path(root_dir).resolve()

    def _validate_state(self, state: Optional[ProjectState]) -> None:
        """Raise MeminitError if state has schema violations.

        Aggregates *all* schema violations into a single error so the
        caller sees the full corruption set in one diagnostic rather
        than needing multiple fix-and-retry cycles.
        """
        if not state or not state.schema_violations:
            return
        violations = state.schema_violations
        summary = "; ".join(v.message for v in violations)
        details = [
            {"file": v.file, "line": v.line, "rule": v.rule, "message": v.message}
            for v in violations
        ]
        raise MeminitError(
            code=ErrorCode.E_STATE_SCHEMA_VIOLATION,
            message=(
                f"Invalid project-state.yaml schema " f"({len(violations)} violation(s)): {summary}"
            ),
            details={"violations": details},
        )

    def set_state(
        self,
        document_id: str,
        *,
        impl_state: Optional[str] = None,
        notes: Optional[str] = None,
        actor: Optional[str] = None,
        clear: bool = False,
        priority: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
        add_depends_on: Optional[List[str]] = None,
        remove_depends_on: Optional[List[str]] = None,
        clear_depends_on: bool = False,
        blocked_by: Optional[List[str]] = None,
        add_blocked_by: Optional[List[str]] = None,
        remove_blocked_by: Optional[List[str]] = None,
        clear_blocked_by: bool = False,
        assignee: Optional[str] = None,
        next_action: Optional[str] = None,
    ) -> StateResult:
        """Set or update a document's implementation state."""
        document_id = _resolve_document_id(self._root_dir, document_id)
        state = load_project_state(self._root_dir)
        self._validate_state(state)

        if state is None:
            state = ProjectState()

        if clear:
            has_other = any(
                [
                    impl_state is not None,
                    notes is not None,
                    priority is not None,
                    depends_on is not None,
                    add_depends_on is not None,
                    remove_depends_on is not None,
                    clear_depends_on,
                    blocked_by is not None,
                    add_blocked_by is not None,
                    remove_blocked_by is not None,
                    clear_blocked_by,
                    assignee is not None,
                    next_action is not None,
                ]
            )
            if has_other:
                raise MeminitError(
                    ErrorCode.STATE_CLEAR_MUTATION_CONFLICT,
                    "--clear is mutually exclusive with all other mutation flags.",
                )
            if document_id in state.entries:
                del state.entries[document_id]
                save_project_state(self._root_dir, state)
            return StateResult(
                document_id=document_id,
                action="clear",
                entry=None,
            )

        if impl_state:
            impl_state = _resolve_impl_state(self._root_dir, impl_state)

        existing = state.get(document_id)
        changed_planning_fields = _changed_planning_fields(
            priority=priority,
            depends_on=depends_on,
            add_depends_on=add_depends_on,
            remove_depends_on=remove_depends_on,
            clear_depends_on=clear_depends_on,
            blocked_by=blocked_by,
            add_blocked_by=add_blocked_by,
            remove_blocked_by=remove_blocked_by,
            clear_blocked_by=clear_blocked_by,
            assignee=assignee,
            next_action=next_action,
        )
        final_priority = _resolve_final_priority(priority, existing)
        final_depends_on = _apply_list_mutation(
            existing.depends_on if existing else (),
            replace=depends_on,
            add=add_depends_on,
            remove=remove_depends_on,
            clear=clear_depends_on,
            field_name="depends_on",
        )
        final_blocked_by = _apply_list_mutation(
            existing.blocked_by if existing else (),
            replace=blocked_by,
            add=add_blocked_by,
            remove=remove_blocked_by,
            clear=clear_blocked_by,
            field_name="blocked_by",
        )
        final_assignee = _resolve_assignee(assignee, existing)
        final_next_action = _resolve_next_action(next_action, existing)
        final_impl_state = impl_state or (
            (
                ImplState.from_string(existing.impl_state).value
                if ImplState.from_string(existing.impl_state)
                else existing.impl_state
            )
            if existing
            else "Not Started"
        )
        final_notes = (
            truncate_notes(notes) if notes is not None else (existing.notes if existing else None)
        )
        resolved_actor = _resolve_actor_for_set(actor, self._root_dir)
        entry = ProjectStateEntry(
            document_id=document_id,
            impl_state=final_impl_state,
            updated=datetime.now(timezone.utc),
            updated_by=resolved_actor,
            notes=final_notes,
            priority=final_priority,
            depends_on=final_depends_on,
            blocked_by=final_blocked_by,
            assignee=final_assignee,
            next_action=final_next_action,
        )
        return self._validate_and_persist(
            document_id,
            entry,
            existing,
            state,
            changed_planning_fields,
        )

    def _validate_and_persist(
        self,
        document_id: str,
        entry: ProjectStateEntry,
        existing: Optional[ProjectStateEntry],
        state: ProjectState,
        changed_planning_fields: Set[str],
    ) -> StateResult:
        validation_issues = validate_planning_fields(entry, _get_known_ids(self._root_dir))
        fatal_issues = [
            i
            for i in validation_issues
            if i.severity == "fatal"
            and (existing is None or _issue_applies_to_changed_field(i, changed_planning_fields))
        ]
        if fatal_issues:
            summary = "; ".join(i.message for i in fatal_issues)
            details = [{"code": i.code, "message": i.message} for i in fatal_issues]
            try:
                error_code = ErrorCode(fatal_issues[0].code)
            except ValueError:
                error_code = ErrorCode.E_STATE_SCHEMA_VIOLATION
            raise MeminitError(
                code=error_code,
                message=f"({len(fatal_issues)} violation(s)): {summary}",
                details={"violations": details},
            )

        temp_state = ProjectState(entries=dict(state.entries))
        temp_state.set_entry(entry)
        cycle_issues = check_dependency_cycle(temp_state.entries)
        if cycle_issues:
            summary = "; ".join(i.message for i in cycle_issues)
            details = [{"code": i.code, "message": i.message} for i in cycle_issues]
            raise MeminitError(
                code=ErrorCode.STATE_DEPENDENCY_CYCLE,
                message=f"({len(cycle_issues)} cycle(s)): {summary}",
                details={"violations": details},
            )

        if existing and _entry_is_idempotent(existing, entry):
            if state.schema_version != STATE_SCHEMA_VERSION:
                save_project_state(self._root_dir, state)
            result_warnings = _build_result_warnings(validation_issues, self._root_dir)
            return StateResult(
                document_id=document_id,
                action="set",
                entry=_entry_to_dict(existing),
                warnings=result_warnings or None,
            )

        state.set_entry(entry)
        save_project_state(self._root_dir, state)

        result_warnings = _build_result_warnings(validation_issues, self._root_dir)

        return StateResult(
            document_id=document_id,
            action="set",
            entry=_entry_to_dict(entry),
            warnings=result_warnings or None,
        )

    def get_state(self, document_id: str) -> StateResult:
        """Get a document's implementation state."""
        document_id = _resolve_document_id(self._root_dir, document_id)
        state = load_project_state(self._root_dir)
        self._validate_state(state)

        if state is None:
            raise MeminitError(
                code=ErrorCode.FILE_NOT_FOUND,
                message="project-state.yaml does not exist.",
            )

        validation_warnings, skip_doc_ids = _collect_read_validation_warnings(state, self._root_dir)

        if document_id in skip_doc_ids:
            entry = state.get(document_id)
            priority_value = entry.priority if entry else "unknown"
            raise MeminitError(
                code=ErrorCode.STATE_INVALID_PRIORITY,
                message=(
                    f"State entry for document '{document_id}' exists but has invalid priority "
                    f"'{priority_value}' and is excluded from all read surfaces. "
                    f"Fix or remove the priority field (valid values: {', '.join(VALID_PRIORITIES)})."
                ),
            )

        entry = state.get(document_id)
        if entry is None:
            raise MeminitError(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"No state entry for document '{document_id}'.",
            )

        derivation_state = _state_excluding_entries(state, skip_doc_ids)
        known_ids = _get_known_ids(self._root_dir) | set(derivation_state.entries.keys())
        derived = compute_derived_fields(derivation_state, known_ids)

        return StateResult(
            document_id=document_id,
            action="get",
            entry=_entry_to_dict(entry, derived[document_id]),
            warnings=validation_warnings if validation_warnings else None,
        )

    def list_states(
        self,
        *,
        ready: Optional[bool] = None,
        blocked: Optional[bool] = None,
        assignee: Optional[List[str]] = None,
        priority: Optional[List[str]] = None,
        impl_state: Optional[List[str]] = None,
    ) -> StateResult:
        """List entries in project-state.yaml with optional filters and derived fields."""
        if priority is not None:
            invalid = [p for p in priority if p not in VALID_PRIORITIES]
            if invalid:
                raise MeminitError(
                    code=ErrorCode.E_INVALID_FILTER_VALUE,
                    message=(
                        f"Priority filter value(s) {invalid!r} not valid. "
                        f"Must be one of: {', '.join(VALID_PRIORITIES)}."
                    ),
                    details={"value": invalid, "valid_values": list(VALID_PRIORITIES)},
                )

        if impl_state is not None:
            from meminit.core.services.repo_config import load_repo_layout

            canonical_values = ImplState.canonical_values()
            canonical_lower = {v.lower() for v in canonical_values}
            try:
                layout = load_repo_layout(self._root_dir)
                seen_custom: Dict[str, str] = {}
                for ns in layout.namespaces:
                    for state_name in ns.valid_impl_states:
                        lower = state_name.lower()
                        if lower not in canonical_lower:
                            seen_custom.setdefault(lower, state_name)
                extra_states = list(seen_custom.values())
            except Exception:
                extra_states = []
            all_valid_lower = canonical_lower | {s.lower() for s in extra_states}
            invalid_impl = [
                v for v in impl_state if _normalize_impl_state_value(v) not in all_valid_lower
            ]
            if invalid_impl:
                all_valid_display = canonical_values + extra_states
                raise MeminitError(
                    code=ErrorCode.E_INVALID_FILTER_VALUE,
                    message=(
                        f"Impl-state filter value(s) {invalid_impl!r} not valid. "
                        f"Must be one of: {', '.join(all_valid_display)}."
                    ),
                    details={"value": invalid_impl, "valid_values": all_valid_display},
                )

        state = load_project_state(self._root_dir)
        self._validate_state(state)

        if state is None:
            return StateResult(
                document_id="*",
                action="list",
                entries=[],
                summary={"total": 0, "returned": 0, "ready": 0, "blocked": 0},
            )

        from meminit.core.services.state_derived import check_status_conflicts

        advisory = _build_status_advisory(state, check_status_conflicts, self._root_dir)

        validation_warnings, skip_doc_ids = _collect_read_validation_warnings(state, self._root_dir)
        derivation_state = _state_excluding_entries(state, skip_doc_ids)
        known_ids = _get_known_ids(self._root_dir) | set(derivation_state.entries.keys())
        derived = compute_derived_fields(derivation_state, known_ids)

        entries_list, ready_count, blocked_count = _build_entries_with_derived(
            state,
            derived,
            ready,
            blocked,
            assignee,
            priority,
            impl_state,
            skip_doc_ids=skip_doc_ids,
        )

        return StateResult(
            document_id="*",
            action="list",
            entries=entries_list,
            summary=_compute_list_summary(
                state, entries_list, ready_count, blocked_count, skip_doc_ids
            ),
            advice=advisory if advisory else None,
            warnings=validation_warnings if validation_warnings else None,
        )

    def next_state(
        self,
        *,
        assignee: Optional[str] = None,
        priority_at_least: Optional[str] = None,
    ) -> StateResult:
        """Return the deterministically-selected next work item."""
        if priority_at_least is not None and priority_at_least not in VALID_PRIORITIES:
            raise MeminitError(
                code=ErrorCode.E_INVALID_FILTER_VALUE,
                message=(
                    f"Priority filter '{priority_at_least}' is not valid. "
                    f"Must be one of: {', '.join(VALID_PRIORITIES)}."
                ),
                details={"value": priority_at_least, "valid_values": list(VALID_PRIORITIES)},
            )

        state = load_project_state(self._root_dir)
        self._validate_state(state)

        if state is None:
            return StateResult(
                document_id="*",
                action="next",
                entry=None,
                reason="state_missing",
                selection={
                    "rule": "priority > unblocks > updated > document_id",
                    "candidates_considered": 0,
                    "filter": _build_filter_dict(assignee, priority_at_least),
                },
            )

        from meminit.core.services.state_derived import PRIORITY_RANK

        validation_warnings, skip_doc_ids = _collect_read_validation_warnings(state, self._root_dir)
        derivation_state = _state_excluding_entries(state, skip_doc_ids)
        known_ids = _get_known_ids(self._root_dir) | set(derivation_state.entries.keys())
        derived = compute_derived_fields(derivation_state, known_ids)

        candidates = _select_next_candidate(
            state,
            derived,
            PRIORITY_RANK,
            assignee,
            priority_at_least,
            skip_doc_ids,
        )

        return _build_next_result(
            candidates,
            validation_warnings,
            assignee,
            priority_at_least,
        )

    def blockers_state(
        self,
        *,
        assignee: Optional[str] = None,
    ) -> StateResult:
        """Return entries with open blockers and one-level-deep resolution."""
        state = load_project_state(self._root_dir)
        self._validate_state(state)

        if state is None:
            return StateResult(
                document_id="*",
                action="blockers",
                blocked=[],
                summary={"total_entries": 0, "blocked": 0, "ready": 0},
            )

        fs_known = _get_known_ids(self._root_dir)
        validation_warnings, skip_doc_ids = _collect_read_validation_warnings(state, self._root_dir)
        derivation_state = _state_excluding_entries(state, skip_doc_ids)
        known_ids = fs_known | set(derivation_state.entries.keys())
        derived = compute_derived_fields(derivation_state, known_ids)

        blocked_list: List[Dict[str, Any]] = []
        for doc_id in sorted(state.entries.keys()):
            if skip_doc_ids and doc_id in skip_doc_ids:
                continue
            entry = state.entries[doc_id]
            d = derived[doc_id]
            if not d.open_blockers:
                continue
            if assignee is not None and (entry.assignee or "") != assignee:
                continue
            blocker_details = []
            for blocker_id in d.open_blockers:
                blocker_entry = derivation_state.get(blocker_id)
                blocker_details.append(
                    {
                        "id": blocker_id,
                        "impl_state": blocker_entry.impl_state if blocker_entry else None,
                        "known": blocker_entry is not None or blocker_id in fs_known,
                    }
                )
            blocked_list.append(
                {
                    "document_id": doc_id,
                    "impl_state": entry.impl_state,
                    "priority": entry.priority,
                    "assignee": entry.assignee,
                    "open_blockers": blocker_details,
                }
            )

        non_skip_ids = [d for d in state.entries if d not in skip_doc_ids]
        if assignee is not None:
            non_skip_ids = [
                d for d in non_skip_ids if (state.entries[d].assignee or "") == assignee
            ]
        ready_count = sum(1 for doc_id in non_skip_ids if derived[doc_id].ready)
        return StateResult(
            document_id="*",
            action="blockers",
            blocked=blocked_list,
            summary={
                "total_entries": len(non_skip_ids),
                "blocked": len(blocked_list),
                "ready": ready_count,
            },
            warnings=validation_warnings if validation_warnings else None,
        )


def _assert_single_mutation_mode(
    field_name: str,
    replace: Any,
    add: Any,
    remove: Any,
    clear: bool,
) -> None:
    modes = [replace is not None, bool(add or remove), bool(clear)]
    if sum(modes) <= 1:
        return
    raise MeminitError(
        ErrorCode.STATE_MIXED_MUTATION_MODE,
        f"Conflicting mutation modes for {field_name}. "
        f"Use exactly one mode: replace, add/remove, or clear.",
        details={"field": field_name, "conflicting_modes": sum(modes)},
    )


def _apply_list_mutation(
    current: Tuple[str, ...],
    *,
    replace: Optional[List[str]] = None,
    add: Optional[List[str]] = None,
    remove: Optional[List[str]] = None,
    clear: bool = False,
    field_name: str = "dependency list",
) -> Tuple[str, ...]:
    """Apply a mutation to a dependency list and return a sorted tuple."""
    _assert_single_mutation_mode(field_name, replace, add, remove, clear)
    if clear:
        return ()
    if replace is not None:
        return tuple(sorted(set(replace)))
    result = set(current)
    if add:
        result.update(add)
    if remove:
        result -= set(remove)
    return tuple(sorted(result))


def _build_entries_with_derived(
    state: ProjectState,
    derived: Dict[str, DerivedEntry],
    ready: Optional[bool],
    blocked: Optional[bool],
    assignee: Optional[List[str]],
    priority: Optional[List[str]],
    impl_state: Optional[List[str]],
    skip_doc_ids: Optional[Set[str]] = None,
) -> Tuple[List[Dict[str, Any]], int, int]:
    assignee_set = set(assignee) if assignee else None
    priority_set = set(priority) if priority else None
    impl_state_set = set(_normalize_impl_state_value(v) for v in impl_state) if impl_state else None

    entries_list: List[Dict[str, Any]] = []
    ready_count = 0
    blocked_count = 0
    for doc_id in sorted(state.entries.keys()):
        if skip_doc_ids and doc_id in skip_doc_ids:
            continue

        entry = state.entries[doc_id]
        d = derived[doc_id]

        if d.ready:
            ready_count += 1
        if d.open_blockers:
            blocked_count += 1
        if ready is not None and d.ready != ready:
            continue
        if blocked is not None and bool(d.open_blockers) != blocked:
            continue
        if assignee_set is not None and (entry.assignee or "") not in assignee_set:
            continue
        if priority_set is not None and (entry.priority or DEFAULT_PRIORITY) not in priority_set:
            continue
        if (
            impl_state_set is not None
            and _normalize_impl_state_value(entry.impl_state) not in impl_state_set
        ):
            continue

        entries_list.append(_entry_to_dict(entry, d))

    return entries_list, ready_count, blocked_count


def _compute_list_summary(
    state: ProjectState,
    entries_list: List[Dict[str, Any]],
    ready_count: int,
    blocked_count: int,
    skip_doc_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    total = len(state.entries) - len(skip_doc_ids or set())
    return {
        "total": total,
        "returned": len(entries_list),
        "ready": ready_count,
        "blocked": blocked_count,
    }


def _build_status_advisory(
    state: ProjectState,
    check_status_conflicts: Any,
    root_dir: Path,
) -> List[Dict[str, Any]]:
    status_conflicts = check_status_conflicts(state.entries)
    state_file_rel = get_state_file_rel_path(root_dir)
    advisory: List[Dict[str, Any]] = []
    for issue in status_conflicts:
        advisory.append(
            {
                "code": issue.code,
                "document_id": issue.document_id,
                "path": state_file_rel,
                "message": issue.message,
            }
        )
    return advisory


def _select_next_candidate(
    state: ProjectState,
    derived: Dict[str, DerivedEntry],
    priority_rank: Dict[str, int],
    assignee: Optional[str],
    priority_at_least: Optional[str],
    skip_doc_ids: Optional[Set[str]] = None,
) -> List[Tuple[ProjectStateEntry, DerivedEntry]]:
    candidates: List[Tuple[ProjectStateEntry, DerivedEntry]] = []
    for doc_id, entry in state.entries.items():
        if skip_doc_ids and doc_id in skip_doc_ids:
            continue
        d = derived[doc_id]
        if not d.ready:
            continue
        if assignee is not None and (entry.assignee or "") != assignee:
            continue
        effective_priority = entry.priority or DEFAULT_PRIORITY
        if effective_priority not in priority_rank:
            continue
        if priority_at_least is not None:
            entry_rank = priority_rank[effective_priority]
            threshold_rank = priority_rank[priority_at_least]
            if entry_rank > threshold_rank:
                continue
        candidates.append((entry, d))
    return candidates


def _build_next_result(
    candidates: List[Tuple[ProjectStateEntry, DerivedEntry]],
    validation_warnings: List[Dict[str, Any]],
    assignee: Optional[str],
    priority_at_least: Optional[str],
) -> StateResult:
    selection_base: Dict[str, Any] = {
        "rule": "priority > unblocks > updated > document_id",
        "filter": _build_filter_dict(assignee, priority_at_least),
    }
    if not candidates:
        return StateResult(
            document_id="*",
            action="next",
            entry=None,
            reason="queue_empty",
            selection={**selection_base, "candidates_considered": 0},
            warnings=validation_warnings if validation_warnings else None,
        )

    candidates.sort(key=lambda pair: next_selection_key(pair[0], pair[1]))
    winner_entry, winner_derived = candidates[0]

    return StateResult(
        document_id="*",
        action="next",
        entry=_entry_to_dict(winner_entry, winner_derived),
        reason=None,
        selection={**selection_base, "candidates_considered": len(candidates)},
        warnings=validation_warnings if validation_warnings else None,
    )


def _build_filter_dict(
    assignee: Optional[str],
    priority_at_least: Optional[str],
) -> Dict[str, Any]:
    f: Dict[str, Any] = {}
    if assignee is not None:
        f["assignee"] = assignee
    if priority_at_least is not None:
        f["priority_at_least"] = priority_at_least
    return f


def _build_result_warnings(
    validation_issues: list,
    root_dir: Path,
) -> List[Dict[str, Any]]:
    state_file_rel = get_state_file_rel_path(root_dir)
    return [
        _build_state_warning(code=issue.code, message=issue.message, path=state_file_rel)
        for issue in validation_issues
        if issue.severity == "warning"
    ]


def _build_state_warning(
    code: str,
    message: str,
    path: str,
) -> Dict[str, Any]:
    return {"code": code, "message": message, "path": path}


def _entry_is_idempotent(
    existing: ProjectStateEntry,
    new: ProjectStateEntry,
) -> bool:
    return (
        existing.impl_state == new.impl_state
        and existing.updated_by == new.updated_by
        and existing.notes == new.notes
        and (existing.priority or DEFAULT_PRIORITY) == (new.priority or DEFAULT_PRIORITY)
        and existing.depends_on == new.depends_on
        and existing.blocked_by == new.blocked_by
        and existing.assignee == new.assignee
        and existing.next_action == new.next_action
    )


def _entry_to_dict(
    entry: ProjectStateEntry,
    derived: Optional[DerivedEntry] = None,
) -> Dict[str, Any]:
    """Convert an entry to a dict suitable for JSON output."""
    result: Dict[str, Any] = {
        "document_id": entry.document_id,
        "impl_state": entry.impl_state,
        "updated": entry.updated.isoformat(),
        "updated_by": entry.updated_by,
    }
    if entry.notes is not None:
        result["notes"] = entry.notes
    if entry.priority is not None and entry.priority != DEFAULT_PRIORITY:
        result["priority"] = entry.priority
    result["depends_on"] = list(entry.depends_on)
    result["blocked_by"] = list(entry.blocked_by)
    if entry.assignee is not None:
        result["assignee"] = entry.assignee
    if entry.next_action is not None:
        result["next_action"] = entry.next_action
    if derived is not None:
        result["ready"] = derived.ready
        result["open_blockers"] = list(derived.open_blockers)
        result["unblocks"] = list(derived.unblocks)
    return result
