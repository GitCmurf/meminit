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
from typing import Any, Dict, List, Optional

import yaml

from meminit.core.domain.entities import Severity, Violation
from meminit.core.services.error_codes import ErrorCode
from meminit.core.services.sanitization import (
    ACTOR_REGEX,
    MAX_NOTES_LENGTH,
    validate_actor,
)
from meminit.core.services.warning_codes import WarningCode


def get_state_file_rel_path(root_dir: Path) -> str:
    """Resolve the project-state.yaml path dynamically from RepoConfig."""
    from meminit.core.services.repo_config import load_repo_config

    try:
        config = load_repo_config(root_dir)
        docs_root = config.docs_root if config.docs_root else "docs"
        return f"{docs_root}/01-indices/project-state.yaml"
    except Exception:
        # Fallback if config is malformed or missing
        return "docs/01-indices/project-state.yaml"


class ImplState(str, Enum):
    """Implementation state values.

    Display names match the canonical enum values.
    Extensible per-repo via ``docops.config.yaml`` in a future iteration;
    these are the shipped defaults.
    """

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


@dataclass
class ProjectState:
    """Wrapper around the full project-state.yaml contents."""

    entries: Dict[str, ProjectStateEntry] = field(default_factory=dict)
    schema_violations: List[Violation] = field(default_factory=list)

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

    if raw is None:
        return ProjectState()
    if not isinstance(raw, dict):
        return ProjectState(
            schema_violations=[
                Violation(
                    file=state_file_rel,
                    line=0,
                    rule=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
                    message="Top-level project-state.yaml value must be a mapping.",
                    severity=Severity.ERROR,
                )
            ]
        )

    if "documents" not in raw:
        return ProjectState()
    documents = raw.get("documents")
    if not isinstance(documents, dict):
        return ProjectState(
            schema_violations=[
                Violation(
                    file=state_file_rel,
                    line=0,
                    rule=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
                    message="Field 'documents' must be a mapping.",
                    severity=Severity.ERROR,
                )
            ]
        )

    entries: Dict[str, ProjectStateEntry] = {}
    schema_violations: List[Violation] = []

    for doc_id, fields in documents.items():
        if not isinstance(doc_id, str):
            continue

        if not isinstance(fields, dict):
            schema_violations.append(
                Violation(
                    file=state_file_rel,
                    line=0,
                    rule=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
                    message=f"Entry for '{doc_id}' must be a dictionary.",
                    severity=Severity.ERROR,
                )
            )
            continue

        impl_state = fields.get("impl_state")
        if not isinstance(impl_state, str):
            schema_violations.append(
                Violation(
                    file=state_file_rel,
                    line=0,
                    rule=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
                    message=f"Field 'impl_state' for '{doc_id}' must be a string.",
                    severity=Severity.ERROR,
                )
            )
            continue

        updated_raw = fields.get("updated")
        updated_by = fields.get("updated_by", "")
        notes = fields.get("notes")

        # Parse updated — accept both datetime and date objects from YAML.
        updated: datetime
        if isinstance(updated_raw, date) and not isinstance(updated_raw, datetime):
            schema_violations.append(
                Violation(
                    file=state_file_rel,
                    line=0,
                    rule=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
                    message=f"Field 'updated' for '{doc_id}' must be a full datetime, not a date.",
                    severity=Severity.ERROR,
                )
            )
            continue
        elif isinstance(updated_raw, datetime):
            updated = (
                updated_raw
                if updated_raw.tzinfo
                else updated_raw.replace(tzinfo=timezone.utc)
            )
        elif isinstance(updated_raw, str):
            try:
                updated = datetime.fromisoformat(updated_raw)
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
            except ValueError:
                schema_violations.append(
                    Violation(
                        file=state_file_rel,
                        line=0,
                        rule=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
                        message=f"Field 'updated' for '{doc_id}' has an invalid format and cannot be parsed.",
                        severity=Severity.ERROR,
                    )
                )
                continue
        else:
            # Use early exit pattern for clarity
            if default_now is None:
                schema_violations.append(
                    Violation(
                        file=state_file_rel,
                        line=0,
                        rule=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
                        message=f"Field 'updated' for '{doc_id}' is missing or not a valid datetime.",
                        severity=Severity.ERROR,
                    )
                )
                continue
            updated = default_now

        # Validate updated_by is a string if provided.
        if not isinstance(updated_by, str):
            schema_violations.append(
                Violation(
                    file=state_file_rel,
                    line=0,
                    rule=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
                    message=f"Field 'updated_by' for '{doc_id}' must be a string.",
                    severity=Severity.ERROR,
                )
            )
            updated_by = ""

        # Validate notes is a string if provided.
        if notes is not None and not isinstance(notes, str):
            schema_violations.append(
                Violation(
                    file=state_file_rel,
                    line=0,
                    rule=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
                    message=f"Field 'notes' for '{doc_id}' must be a string.",
                    severity=Severity.ERROR,
                )
            )
            notes = None

        entries[str(doc_id)] = ProjectStateEntry(
            document_id=str(doc_id),
            impl_state=str(impl_state),
            updated=updated,
            updated_by=updated_by,
            notes=notes,
        )

    return ProjectState(entries=entries, schema_violations=schema_violations)


def save_project_state(root_dir: Path, state: ProjectState) -> Path:
    """Write ``project-state.yaml`` with entries sorted alphabetically.

    Returns the path to the written file.
    """
    state_file_rel = get_state_file_rel_path(root_dir)
    state_path = root_dir / state_file_rel
    state_path.parent.mkdir(parents=True, exist_ok=True)

    # Build the YAML structure with alphabetical ordering.
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
        documents[doc_id] = record

    payload: Dict[str, Any] = {"documents": documents}
    content = yaml.dump(
        payload, default_flow_style=False, sort_keys=False, allow_unicode=True
    )

    state_path.write_text(content, encoding="utf-8")
    return state_path


def validate_project_state(
    state: ProjectState,
    known_doc_ids: set[str],
    root_dir: Path,
    valid_impl_states: Optional[List[str]] = None,
) -> List[Violation]:
    """Validate a parsed project state against known governed document IDs.

    Returns a list of advisory violations (warnings), plus any schema
    violations (errors) captured during parsing. This is used by both
    ``meminit doctor`` and ``meminit index``.
    """
    issues: List[Violation] = list(state.schema_violations)
    state_file_rel = get_state_file_rel_path(root_dir)

    if valid_impl_states is None:
        all_valid_states = set(ImplState.canonical_values())
    else:
        all_valid_states = set(ImplState.canonical_values()) | set(valid_impl_states)

    # Check alphabetical ordering.
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
        # Check document ID exists in governed docs.
        if doc_id not in known_doc_ids:
            issues.append(
                Violation(
                    file=state_file_rel,
                    line=0,
                    rule=WarningCode.W_STATE_UNKNOWN_DOC_ID,
                    message=f"Document ID '{doc_id}' in project-state.yaml has no corresponding governed document.",
                    severity=Severity.WARNING,
                )
            )

        # Check impl_state is a known enum value or valid custom state.
        if entry.impl_state not in all_valid_states:
            issues.append(
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
            )

        # Check updated_by format.
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

        # Check notes length.
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

    return issues
