"""Manage project-state.yaml document entries (PRD-007 FR-9).

Provides ``set``, ``get``, ``list`` operations for the centralized
implementation state file.  Auto-populates ``updated`` (UTC) and
``updated_by`` via the actor chain:

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
from typing import Any, Dict, List, Optional

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.project_state import (
    ImplState,
    ProjectState,
    ProjectStateEntry,
    load_project_state,
    save_project_state,
)
from meminit.core.services.sanitization import truncate_notes, validate_actor


@dataclass(frozen=True)
class StateResult:
    """Result of a state operation."""

    document_id: str
    action: str  # "set", "get", "list"
    entry: Optional[Dict[str, Any]] = None
    entries: Optional[List[Dict[str, Any]]] = None


def _resolve_actor() -> str:
    """Resolve the actor ID via the environment chain.

    Order: MEMINIT_ACTOR_ID → git config user.name → system username.
    """
    from meminit.core.services.sanitization import sanitize_actor

    # 1. Environment variable.
    actor = os.environ.get("MEMINIT_ACTOR_ID")
    if actor and actor.strip():
        return sanitize_actor(actor)

    # 2. Git user.name.
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return sanitize_actor(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 3. System username.
    try:
        return sanitize_actor(getpass.getuser())
    except Exception:
        return "unknown"


class StateDocumentUseCase:
    """Use case for managing project-state.yaml entries."""

    def __init__(self, root_dir: str):
        self._root_dir = Path(root_dir).resolve()

    def set_state(
        self,
        document_id: str,
        *,
        impl_state: Optional[str] = None,
        notes: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> StateResult:
        """Set or update a document's implementation state.

        Auto-populates ``updated`` (UTC now) and ``updated_by`` (actor chain).
        Re-sorts entries alphabetically after mutation.
        """
        # Validate impl_state if provided.
        if impl_state:
            resolved = ImplState.from_string(impl_state)
            if resolved is None:
                raise MeminitError(
                    code=ErrorCode.E_INVALID_FILTER_VALUE,
                    message=f"Unknown impl_state: '{impl_state}'",
                    details={
                        "value": impl_state,
                        "valid_values": ImplState.canonical_values(),
                    },
                )
            impl_state = resolved.value  # Canonicalize.

        # Load existing state (or create new).
        state = load_project_state(self._root_dir) or ProjectState()

        # Get existing entry if updating.
        existing = state.get(document_id)
        final_impl_state = impl_state or (existing.impl_state if existing else "Not Started")

        final_notes = truncate_notes(notes) if notes is not None else (existing.notes if existing else None)

        # Auto-populate timestamp and actor.
        now = datetime.now(timezone.utc)
        if actor:
            if not validate_actor(actor):
                raise MeminitError(
                    code=ErrorCode.E_INVALID_FILTER_VALUE,
                    message=f"Invalid actor override: '{actor}'. Must match ^[a-zA-Z0-9._-]+$",
                )
            resolved_actor = actor
        else:
            resolved_actor = _resolve_actor()

        entry = ProjectStateEntry(
            document_id=document_id,
            impl_state=final_impl_state,
            updated=now,
            updated_by=resolved_actor,
            notes=final_notes,
        )
        state.set_entry(entry)

        save_project_state(self._root_dir, state)

        return StateResult(
            document_id=document_id,
            action="set",
            entry=_entry_to_dict(entry),
        )

    def get_state(self, document_id: str) -> StateResult:
        """Get a document's implementation state."""
        state = load_project_state(self._root_dir)
        if state is None:
            raise MeminitError(
                code=ErrorCode.FILE_NOT_FOUND,
                message="project-state.yaml does not exist.",
            )

        entry = state.get(document_id)
        if entry is None:
            raise MeminitError(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"No state entry for document '{document_id}'.",
            )

        return StateResult(
            document_id=document_id,
            action="get",
            entry=_entry_to_dict(entry),
        )

    def list_states(self) -> StateResult:
        """List all entries in project-state.yaml."""
        state = load_project_state(self._root_dir)
        if state is None:
            return StateResult(
                document_id="*",
                action="list",
                entries=[],
            )

        entries_list = [
            _entry_to_dict(state.entries[doc_id])
            for doc_id in sorted(state.entries.keys())
        ]

        return StateResult(
            document_id="*",
            action="list",
            entries=entries_list,
        )


def _entry_to_dict(entry: ProjectStateEntry) -> Dict[str, Any]:
    """Convert an entry to a dict suitable for JSON output."""
    result: Dict[str, Any] = {
        "document_id": entry.document_id,
        "impl_state": entry.impl_state,
        "updated": entry.updated.isoformat(),
        "updated_by": entry.updated_by,
    }
    if entry.notes is not None:
        result["notes"] = entry.notes
    return result
