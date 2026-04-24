"""Project state file management.

This module provides the domain model, parsing, validation, and persistence
logic for ``project-state.yaml`` — the centralized mutable state file that
tracks implementation progress of governed documents.

The state file is explicitly excluded from ``meminit check`` governance
validation.  It is validated by ``meminit doctor`` (advisory) and
``meminit index`` (per-entry validation with warnings).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from meminit.core.domain.entities import Severity, Violation
from meminit.core.services.error_codes import ErrorCode
from meminit.core.services.safe_fs import atomic_write, ensure_safe_write_path
from meminit.core.services.sanitization import (
    ACTOR_REGEX,
    MAX_ASSIGNEE_LENGTH,
    MAX_NOTES_LENGTH,
    validate_actor,
)
from meminit.core.services.warning_codes import WarningCode

STATE_SCHEMA_VERSION = "2.0"
STATE_SCHEMA_VERSION_LEGACY = "1.0"
VALID_PRIORITIES: Tuple[str, ...] = ("P0", "P1", "P2", "P3")
DEFAULT_PRIORITY = "P2"
DOCUMENT_ID_PATTERN = re.compile(r"^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$")


def get_state_file_rel_path(root_dir: Path) -> str:
    """Resolve the project-state.yaml path dynamically from RepoConfig."""
    from meminit.core.services.repo_config import load_repo_config

    try:
        config = load_repo_config(root_dir)
        docs_root = config.docs_root if config.docs_root else "docs"
        return f"{docs_root}/01-indices/project-state.yaml"
    except Exception:
        return "docs/01-indices/project-state.yaml"


def _schema_violation(file: str, message: str) -> Violation:
    """Build a schema violation for project-state.yaml structural issues."""
    return Violation(
        file=file,
        line=0,
        rule=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
        message=message,
        severity=Severity.ERROR,
    )


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware, defaulting to UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _normalize_impl_state_value(value: str) -> str:
    """Normalize impl_state comparisons without changing the stored value."""
    return value.strip().lower()


class ImplState(str, Enum):
    """Implementation state values."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    BLOCKED = "Blocked"
    QA_REQUIRED = "QA Required"
    DONE = "Done"

    @classmethod
    def from_string(cls, value: str) -> Optional["ImplState"]:
        """Case-insensitive lookup returning canonical enum or None."""
        normalised = value.strip().lower()
        for member in cls:
            if member.value.lower() == normalised:
                return member
        return None

    @classmethod
    def canonical_values(cls) -> List[str]:
        """Return the list of canonical display values."""
        return [m.value for m in cls]


@dataclass(frozen=True)
class ProjectStateEntry:
    """A single document's implementation state record."""

    document_id: str
    impl_state: str
    updated: datetime
    updated_by: str
    notes: Optional[str] = None
    priority: Optional[str] = None
    depends_on: Tuple[str, ...] = ()
    blocked_by: Tuple[str, ...] = ()
    assignee: Optional[str] = None
    next_action: Optional[str] = None


@dataclass
class ProjectState:
    """Wrapper around the full project-state.yaml contents."""

    entries: Dict[str, ProjectStateEntry] = field(default_factory=dict)
    schema_violations: List[Violation] = field(default_factory=list)
    schema_version: str = STATE_SCHEMA_VERSION

    def get(self, document_id: str) -> Optional[ProjectStateEntry]:
        """Return the entry for *document_id*, or None."""
        return self.entries.get(document_id)

    def set_entry(self, entry: ProjectStateEntry) -> None:
        """Add or replace an entry."""
        self.entries[entry.document_id] = entry

    @property
    def document_ids(self) -> List[str]:
        """Return sorted list of tracked document IDs."""
        return sorted(self.entries.keys())


def _parse_planning_fields(
    fields: dict, doc_id: str, state_file_rel: str,
) -> Tuple[dict, List[Violation]]:
    violations: List[Violation] = []

    priority = fields.get("priority")
    if priority is not None and not isinstance(priority, str):
        violations.append(_schema_violation(
            state_file_rel,
            f"Field 'priority' for '{doc_id}' must be a string, got {type(priority).__name__}.",
        ))
        priority = None

    raw_depends = fields.get("depends_on")
    depends_on: Tuple[str, ...] = ()
    if raw_depends is not None and not isinstance(raw_depends, list):
        violations.append(_schema_violation(
            state_file_rel,
            f"Field 'depends_on' for '{doc_id}' must be a list, got {type(raw_depends).__name__}.",
        ))
    elif isinstance(raw_depends, list):
        dropped = [d for d in raw_depends if not isinstance(d, str)]
        if dropped:
            violations.append(_schema_violation(
                state_file_rel,
                f"Field 'depends_on' for '{doc_id}' contains non-string items: {dropped}.",
            ))
        depends_on = tuple(sorted(str(d) for d in raw_depends if isinstance(d, str)))

    raw_blocked = fields.get("blocked_by")
    blocked_by: Tuple[str, ...] = ()
    if raw_blocked is not None and not isinstance(raw_blocked, list):
        violations.append(_schema_violation(
            state_file_rel,
            f"Field 'blocked_by' for '{doc_id}' must be a list, got {type(raw_blocked).__name__}.",
        ))
    elif isinstance(raw_blocked, list):
        dropped = [b for b in raw_blocked if not isinstance(b, str)]
        if dropped:
            violations.append(_schema_violation(
                state_file_rel,
                f"Field 'blocked_by' for '{doc_id}' contains non-string items: {dropped}.",
            ))
        blocked_by = tuple(sorted(str(b) for b in raw_blocked if isinstance(b, str)))

    assignee = fields.get("assignee")
    if assignee is not None and not isinstance(assignee, str):
        violations.append(_schema_violation(
            state_file_rel,
            f"Field 'assignee' for '{doc_id}' must be a string, got {type(assignee).__name__}.",
        ))
        assignee = None

    next_action = fields.get("next_action")
    if next_action is not None and not isinstance(next_action, str):
        violations.append(_schema_violation(
            state_file_rel,
            f"Field 'next_action' for '{doc_id}' must be a string, got {type(next_action).__name__}.",
        ))
        next_action = None

    return {
        "priority": priority,
        "depends_on": depends_on,
        "blocked_by": blocked_by,
        "assignee": assignee,
        "next_action": next_action,
    }, violations


def _validate_top_level_structure(
    raw: Any, state_file_rel: str
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[ProjectState]]:
    if raw is None:
        return None, None, ProjectState()
    if not isinstance(raw, dict):
        return None, None, ProjectState(
            schema_violations=[
                _schema_violation(state_file_rel, "Top-level project-state.yaml value must be a mapping.")
            ]
        )

    schema_version = str(raw.get("state_schema_version", STATE_SCHEMA_VERSION_LEGACY))

    if "documents" not in raw:
        if raw:
            from meminit.core.services.error_codes import MeminitError

            raise MeminitError(
                code=ErrorCode.E_STATE_SCHEMA_VIOLATION,
                message=(
                    f"project-state.yaml has no 'documents' key but contains "
                    f"other keys: {', '.join(raw.keys())}"
                ),
                details={"file": state_file_rel},
            )
        return None, None, ProjectState()

    documents = raw.get("documents")
    if not isinstance(documents, dict):
        return None, None, ProjectState(
            schema_violations=[
                _schema_violation(state_file_rel, "Field 'documents' must be a mapping.")
            ]
        )

    return schema_version, documents, None


def _parse_entry_identity(
    doc_id: Any,
    fields: Any,
    state_file_rel: str,
) -> Tuple[Optional[str], List[Violation]]:
    violations: List[Violation] = []

    if not isinstance(doc_id, str):
        violations.append(
            _schema_violation(state_file_rel, f"Document key must be a string, got {type(doc_id).__name__}.")
        )
        return None, violations

    if not isinstance(fields, dict):
        violations.append(
            _schema_violation(state_file_rel, f"Entry for '{doc_id}' must be a dictionary.")
        )
        return None, violations

    impl_state = fields.get("impl_state")
    if not isinstance(impl_state, str):
        violations.append(
            _schema_violation(state_file_rel, f"Field 'impl_state' for '{doc_id}' must be a string.")
        )
        return None, violations

    return impl_state, violations


def _parse_entry_timestamp(
    fields: dict,
    doc_id: str,
    state_file_rel: str,
    default_now: Optional[datetime],
) -> Tuple[Optional[datetime], List[Violation]]:
    violations: List[Violation] = []
    updated_raw = fields.get("updated")

    if isinstance(updated_raw, date) and not isinstance(updated_raw, datetime):
        violations.append(
            _schema_violation(state_file_rel, f"Field 'updated' for '{doc_id}' must be a full datetime, not a date.")
        )
        return None, violations
    elif isinstance(updated_raw, datetime):
        return _ensure_utc(updated_raw), violations
    elif isinstance(updated_raw, str):
        try:
            return _ensure_utc(datetime.fromisoformat(updated_raw)), violations
        except ValueError:
            violations.append(
                _schema_violation(state_file_rel, f"Field 'updated' for '{doc_id}' has an invalid format and cannot be parsed.")
            )
            return None, violations
    else:
        if default_now is None:
            violations.append(
                _schema_violation(state_file_rel, f"Field 'updated' for '{doc_id}' is missing or not a valid datetime.")
            )
            return None, violations
        return _ensure_utc(default_now), violations


def _parse_entry_text_fields(
    fields: dict,
    doc_id: str,
    state_file_rel: str,
) -> Tuple[str, Optional[str], List[Violation]]:
    violations: List[Violation] = []

    updated_by = fields.get("updated_by", "")
    if not isinstance(updated_by, str):
        violations.append(
            _schema_violation(state_file_rel, f"Field 'updated_by' for '{doc_id}' must be a string.")
        )
        updated_by = ""

    notes = fields.get("notes")
    if notes is not None and not isinstance(notes, str):
        violations.append(
            _schema_violation(state_file_rel, f"Field 'notes' for '{doc_id}' must be a string.")
        )
        notes = None

    return updated_by, notes, violations


def _parse_single_entry(
    doc_id: Any,
    fields: Any,
    state_file_rel: str,
    default_now: Optional[datetime],
) -> Tuple[Optional[ProjectStateEntry], List[Violation]]:
    impl_state, violations = _parse_entry_identity(doc_id, fields, state_file_rel)
    if impl_state is None:
        return None, violations

    updated, ts_violations = _parse_entry_timestamp(fields, doc_id, state_file_rel, default_now)
    violations.extend(ts_violations)
    if updated is None:
        return None, violations

    updated_by, notes, text_violations = _parse_entry_text_fields(fields, doc_id, state_file_rel)
    violations.extend(text_violations)

    planning, plan_violations = _parse_planning_fields(fields, doc_id, state_file_rel)
    violations.extend(plan_violations)

    entry = ProjectStateEntry(
        document_id=str(doc_id),
        impl_state=str(impl_state),
        updated=updated,
        updated_by=updated_by,
        notes=notes,
        priority=planning["priority"],
        depends_on=planning["depends_on"],
        blocked_by=planning["blocked_by"],
        assignee=planning["assignee"],
        next_action=planning["next_action"],
    )

    return entry, violations


def load_project_state(
    root_dir: Path, default_now: Optional[datetime] = None
) -> Optional[ProjectState]:
    """Load and parse ``project-state.yaml`` from the repo root.

    Returns ``None`` if the file does not exist (gracefully optional).
    Raises ``MeminitError`` with ``E_STATE_YAML_MALFORMED`` if the file
    exists but is not valid YAML.
    """
    state_file_rel = get_state_file_rel_path(root_dir)
    state_path = root_dir / state_file_rel
    if not state_path.exists():
        return None

    try:
        raw = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        from meminit.core.services.error_codes import MeminitError

        raise MeminitError(
            code=ErrorCode.E_STATE_YAML_MALFORMED,
            message=f"project-state.yaml is not valid YAML: {exc}",
            details={"path": str(state_path)},
        ) from exc

    schema_version, documents, early = _validate_top_level_structure(raw, state_file_rel)
    if early is not None:
        return early

    entries: Dict[str, ProjectStateEntry] = {}
    schema_violations: List[Violation] = []

    for doc_id, fields in documents.items():
        entry, violations = _parse_single_entry(doc_id, fields, state_file_rel, default_now)
        schema_violations.extend(violations)
        if entry is not None:
            entries[entry.document_id] = entry

    return ProjectState(
        entries=entries,
        schema_violations=schema_violations,
        schema_version=schema_version,
    )


def save_project_state(root_dir: Path, state: ProjectState) -> Path:
    """Write ``project-state.yaml`` with entries sorted alphabetically.

    Uses atomic write with path safety validation.
    Returns the path to the written file.
    """
    state_file_rel = get_state_file_rel_path(root_dir)
    state_path = root_dir / state_file_rel

    ensure_safe_write_path(root_dir=root_dir, target_path=state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    documents: Dict[str, Dict[str, Any]] = {}
    for doc_id in sorted(state.entries.keys()):
        entry = state.entries[doc_id]
        record: Dict[str, Any] = {
            "impl_state": entry.impl_state,
            "updated": entry.updated.isoformat(),
            "updated_by": entry.updated_by,
        }
        if entry.notes is not None:
            record["notes"] = entry.notes
        if entry.priority is not None and entry.priority != DEFAULT_PRIORITY:
            record["priority"] = entry.priority
        if entry.depends_on:
            record["depends_on"] = sorted(entry.depends_on)
        if entry.blocked_by:
            record["blocked_by"] = sorted(entry.blocked_by)
        if entry.assignee is not None:
            record["assignee"] = entry.assignee
        if entry.next_action is not None:
            record["next_action"] = entry.next_action
        documents[doc_id] = record

    payload: Dict[str, Any] = {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "documents": documents,
    }
    content = yaml.dump(
        payload, default_flow_style=False, sort_keys=False, allow_unicode=True
    )

    atomic_write(state_path, content, encoding="utf-8")
    return state_path


def _validate_entry_identity(
    doc_id: str,
    known_doc_ids: set[str],
    state_file_rel: str,
) -> List[Violation]:
    if doc_id in known_doc_ids:
        return []
    return [
        Violation(
            file=state_file_rel,
            line=0,
            rule=WarningCode.W_STATE_UNKNOWN_DOC_ID,
            message=f"Document ID '{doc_id}' in project-state.yaml has no corresponding governed document.",
            severity=Severity.WARNING,
        )
    ]


def _validate_entry_status(
    entry: "ProjectStateEntry",
    doc_id: str,
    normalized_valid_states: set[str],
    all_valid_states: set[str],
    state_file_rel: str,
) -> List[Violation]:
    if _normalize_impl_state_value(entry.impl_state) in normalized_valid_states:
        return []
    return [
        Violation(
            file=state_file_rel,
            line=0,
            rule=WarningCode.W_STATE_UNKNOWN_IMPL_STATE,
            message=(
                f"Unknown impl_state '{entry.impl_state}' for document '{doc_id}'. "
                f"Valid values: {', '.join(sorted(all_valid_states))}."
            ),
            severity=Severity.WARNING,
        )
    ]


def _validate_entry_planning(
    entry: "ProjectStateEntry",
    doc_id: str,
    state_file_rel: str,
) -> List[Violation]:
    if entry.priority is None or entry.priority in VALID_PRIORITIES:
        return []
    return [
        Violation(
            file=state_file_rel,
            line=0,
            rule=ErrorCode.STATE_INVALID_PRIORITY.value,
            message=(
                f"Invalid priority '{entry.priority}' for document '{doc_id}'. "
                f"Valid values: {', '.join(VALID_PRIORITIES)}."
            ),
            severity=Severity.WARNING,
        )
    ]


def _validate_entry_text_bounds(
    entry: "ProjectStateEntry",
    doc_id: str,
    state_file_rel: str,
) -> List[Violation]:
    issues: List[Violation] = []

    if entry.updated_by and not validate_actor(entry.updated_by):
        issues.append(
            Violation(
                file=state_file_rel,
                line=0,
                rule=WarningCode.W_FIELD_SANITIZATION_FAILED,
                message=(
                    f"updated_by '{entry.updated_by}' for document '{doc_id}' "
                    "does not match required pattern ^[a-zA-Z0-9._-]+$."
                ),
                severity=Severity.WARNING,
            )
        )

    if entry.notes is not None and len(entry.notes) > MAX_NOTES_LENGTH:
        issues.append(
            Violation(
                file=state_file_rel,
                line=0,
                rule=WarningCode.W_FIELD_SANITIZATION_FAILED,
                message=(
                    f"notes for document '{doc_id}' exceeds {MAX_NOTES_LENGTH} characters "
                    f"({len(entry.notes)} chars)."
                ),
                severity=Severity.WARNING,
            )
        )

    if entry.assignee is not None and len(entry.assignee) > MAX_ASSIGNEE_LENGTH:
        issues.append(
            Violation(
                file=state_file_rel,
                line=0,
                rule=ErrorCode.STATE_FIELD_TOO_LONG.value,
                message=(
                    f"assignee for document '{doc_id}' exceeds {MAX_ASSIGNEE_LENGTH} characters "
                    f"({len(entry.assignee)} chars)."
                ),
                severity=Severity.WARNING,
            )
        )

    if entry.next_action is not None and len(entry.next_action) > MAX_NOTES_LENGTH:
        issues.append(
            Violation(
                file=state_file_rel,
                line=0,
                rule=ErrorCode.STATE_FIELD_TOO_LONG.value,
                message=(
                    f"next_action for document '{doc_id}' exceeds {MAX_NOTES_LENGTH} characters "
                    f"({len(entry.next_action)} chars)."
                ),
                severity=Severity.WARNING,
            )
        )

    if entry.next_action is not None and "\n" in entry.next_action:
        issues.append(
            Violation(
                file=state_file_rel,
                line=0,
                rule=ErrorCode.STATE_FIELD_INVALID_FORMAT.value,
                message=f"next_action for document '{doc_id}' contains embedded newlines.",
                severity=Severity.WARNING,
            )
        )

    return issues


def _validate_entry_fields(
    entry: "ProjectStateEntry",
    doc_id: str,
    known_doc_ids: set[str],
    normalized_valid_states: set[str],
    all_valid_states: set[str],
    state_file_rel: str,
) -> List[Violation]:
    issues: List[Violation] = []
    issues.extend(_validate_entry_identity(doc_id, known_doc_ids, state_file_rel))
    issues.extend(_validate_entry_status(entry, doc_id, normalized_valid_states, all_valid_states, state_file_rel))
    issues.extend(_validate_entry_planning(entry, doc_id, state_file_rel))
    issues.extend(_validate_entry_text_bounds(entry, doc_id, state_file_rel))
    return issues


def validate_project_state(
    state: ProjectState,
    known_doc_ids: set[str],
    root_dir: Path,
    valid_impl_states: Optional[List[str]] = None,
) -> List[Violation]:
    """Validate a parsed project state against known governed document IDs.

    Returns a list of advisory violations (warnings), plus any schema
    violations (errors) captured during parsing.
    """
    issues: List[Violation] = list(state.schema_violations)
    state_file_rel = get_state_file_rel_path(root_dir)

    if valid_impl_states is None:
        all_valid_states = set(ImplState.canonical_values())
    else:
        all_valid_states = set(ImplState.canonical_values()) | set(valid_impl_states)
    normalized_valid_states = {_normalize_impl_state_value(s) for s in all_valid_states}

    doc_ids = list(state.entries.keys())
    if doc_ids != sorted(doc_ids):
        issues.append(
            Violation(
                file=state_file_rel,
                line=0,
                rule=WarningCode.W_STATE_UNSORTED_KEYS,
                message=(
                    "Entries in project-state.yaml are not sorted alphabetically "
                    "by document_id. Sort to minimize merge conflict radius."
                ),
                severity=Severity.WARNING,
            )
        )

    for doc_id, entry in state.entries.items():
        issues.extend(
            _validate_entry_fields(
                entry, doc_id, known_doc_ids, normalized_valid_states, all_valid_states, state_file_rel
            )
        )

    return issues
