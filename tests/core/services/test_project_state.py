"""Tests for project_state module (PRD-007 Phase 1).

Covers: load, save, validate, ImplState enum semantics.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.project_state import (
    ImplState,
    ProjectState,
    ProjectStateEntry,
    load_project_state,
    save_project_state,
    validate_project_state,
)
from meminit.core.services.warning_codes import WarningCode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_state_file(root: Path, content: str) -> Path:
    """Write a project-state.yaml under the expected path."""
    state_path = root / "docs" / "01-indices" / "project-state.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(content, encoding="utf-8")
    return state_path


VALID_STATE_YAML = """\
documents:
  MEMINIT-ADR-010:
    impl_state: Done
    updated: "2026-02-15T10:00:00Z"
    updated_by: GitCmurf
  MEMINIT-PRD-003:
    impl_state: In Progress
    updated: "2026-03-04T14:30:00Z"
    updated_by: GitCmurf
    notes: Phase 2 underway
"""


# ---------------------------------------------------------------------------
# ImplState enum
# ---------------------------------------------------------------------------

def test_impl_state_canonical_values():
    """Canonical display names match PRD-007 FR-1 enum."""
    assert ImplState.canonical_values() == [
        "Not Started", "In Progress", "Blocked", "QA Required", "Done",
    ]


def test_impl_state_from_string_case_insensitive():
    """Case-insensitive lookup returns canonical enum."""
    assert ImplState.from_string("in progress") == ImplState.IN_PROGRESS
    assert ImplState.from_string("IN PROGRESS") == ImplState.IN_PROGRESS
    assert ImplState.from_string("  Done  ") == ImplState.DONE


def test_impl_state_from_string_unknown():
    """Unknown value returns None."""
    assert ImplState.from_string("Unknown Value") is None
    assert ImplState.from_string("") is None


# ---------------------------------------------------------------------------
# load_project_state
# ---------------------------------------------------------------------------

def test_load_project_state_valid(tmp_path):
    """Parse well-formed YAML and assert entries."""
    _write_state_file(tmp_path, VALID_STATE_YAML)
    state = load_project_state(tmp_path)

    assert state is not None
    assert len(state.entries) == 2
    assert "MEMINIT-ADR-010" in state.entries
    assert "MEMINIT-PRD-003" in state.entries

    entry = state.get("MEMINIT-PRD-003")
    assert entry is not None
    assert entry.impl_state == "In Progress"
    assert entry.updated_by == "GitCmurf"
    assert entry.notes == "Phase 2 underway"
    assert entry.updated.tzinfo is not None  # timezone-aware


def test_load_project_state_missing_file(tmp_path):
    """Returns None when file does not exist (gracefully optional)."""
    result = load_project_state(tmp_path)
    assert result is None


def test_load_project_state_malformed_yaml(tmp_path):
    """Raises MeminitError with E_STATE_YAML_MALFORMED for invalid YAML."""
    _write_state_file(tmp_path, "documents:\n  - bad: yaml: invalid: [\n")

    with pytest.raises(MeminitError) as exc_info:
        load_project_state(tmp_path)

    assert exc_info.value.code == ErrorCode.E_STATE_YAML_MALFORMED


def test_load_project_state_empty_file(tmp_path):
    """Empty file returns an empty ProjectState (not None)."""
    _write_state_file(tmp_path, "")
    state = load_project_state(tmp_path)
    assert state is not None
    assert len(state.entries) == 0


def test_load_project_state_invalid_documents_shape(tmp_path):
    _write_state_file(tmp_path, "documents: []\n")
    state = load_project_state(tmp_path)
    assert state is not None
    assert ErrorCode.E_STATE_SCHEMA_VIOLATION.value in [v.rule for v in state.schema_violations]


def test_load_project_state_invalid_updated_defaults_with_warning(tmp_path):
    _write_state_file(
        tmp_path,
        "documents:\n  MEMINIT-PRD-003:\n    impl_state: Done\n    updated: not-a-timestamp\n    updated_by: GitCmurf\n",
    )
    now = datetime(2026, 3, 5, 14, 30, 0, tzinfo=timezone.utc)
    state = load_project_state(tmp_path, default_now=now)
    assert state is not None
    assert "MEMINIT-PRD-003" not in state.entries
    assert ErrorCode.E_STATE_SCHEMA_VIOLATION.value in [v.rule for v in state.schema_violations]


def test_load_project_state_missing_updated_defaults_with_warning(tmp_path):
    """Test that default_now populates missing updated fields without violations."""
    _write_state_file(
        tmp_path,
        "documents:\n  MEMINIT-PRD-003:\n    impl_state: Done\n    updated_by: GitCmurf\n",
    )
    now = datetime(2026, 3, 5, 14, 30, 0, tzinfo=timezone.utc)
    state = load_project_state(tmp_path, default_now=now)
    assert state is not None
    # When default_now is provided, missing updated fields are populated (not skipped)
    assert "MEMINIT-PRD-003" in state.entries
    assert state.entries["MEMINIT-PRD-003"].updated == now
    # No schema violations - default_now allows graceful handling of missing fields
    assert len(state.schema_violations) == 0


# ---------------------------------------------------------------------------
# save_project_state
# ---------------------------------------------------------------------------

def test_save_project_state_sorted_keys(tmp_path):
    """Entries are written in alphabetical order by document_id."""
    state = ProjectState()
    now = datetime.now(timezone.utc)
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="In Progress",
        updated=now,
        updated_by="GitCmurf",
    ))
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-ADR-010",
        impl_state="Done",
        updated=now,
        updated_by="GitCmurf",
    ))

    path = save_project_state(tmp_path, state)
    assert path.exists()

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc_ids = list(raw["documents"].keys())
    assert doc_ids == sorted(doc_ids), "Entries must be alphabetically sorted"


def test_save_project_state_roundtrip(tmp_path):
    """Save then load produces equivalent state."""
    state = ProjectState()
    now = datetime(2026, 3, 5, 14, 30, 0, tzinfo=timezone.utc)
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-007",
        impl_state="QA Required",
        updated=now,
        updated_by="GitCmurf",
        notes="Testing roundtrip",
    ))

    save_project_state(tmp_path, state)
    loaded = load_project_state(tmp_path)

    assert loaded is not None
    entry = loaded.get("MEMINIT-PRD-007")
    assert entry is not None
    assert entry.impl_state == "QA Required"
    assert entry.updated_by == "GitCmurf"
    assert entry.notes == "Testing roundtrip"


# ---------------------------------------------------------------------------
# validate_project_state
# ---------------------------------------------------------------------------

def test_validate_unknown_doc_id(tmp_path):
    """Emits W_STATE_UNKNOWN_DOC_ID for doc ID not in governed set."""
    state = ProjectState()
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-FAKE-999",
        impl_state="Done",
        updated=datetime.now(timezone.utc),
        updated_by="test",
    ))

    issues = validate_project_state(state, known_doc_ids={"MEMINIT-PRD-003"}, root_dir=tmp_path)
    codes = [v.rule for v in issues]
    assert WarningCode.W_STATE_UNKNOWN_DOC_ID in codes


def test_validate_unknown_impl_state(tmp_path):
    """Emits W_STATE_UNKNOWN_IMPL_STATE for unrecognised impl_state value."""
    state = ProjectState()
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="Totally Made Up",
        updated=datetime.now(timezone.utc),
        updated_by="test",
    ))

    issues = validate_project_state(state, known_doc_ids={"MEMINIT-PRD-003"}, root_dir=tmp_path)
    codes = [v.rule for v in issues]
    assert WarningCode.W_STATE_UNKNOWN_IMPL_STATE in codes


def test_validate_impl_state_is_case_insensitive(tmp_path):
    """Built-in impl_state values should not warn when casing differs."""
    state = ProjectState()
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="done",
        updated=datetime.now(timezone.utc),
        updated_by="test",
    ))

    issues = validate_project_state(
        state, known_doc_ids={"MEMINIT-PRD-003"}, root_dir=tmp_path
    )
    codes = [v.rule for v in issues]
    assert WarningCode.W_STATE_UNKNOWN_IMPL_STATE not in codes


def test_validate_unsorted_keys(tmp_path):
    """Emits W_STATE_UNSORTED_KEYS when entries are not alphabetical."""
    # Build a state with out-of-order keys by directly manipulating dict.
    state = ProjectState()
    now = datetime.now(timezone.utc)
    state.entries["MEMINIT-PRD-003"] = ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="In Progress",
        updated=now,
        updated_by="test",
    )
    state.entries["MEMINIT-ADR-010"] = ProjectStateEntry(
        document_id="MEMINIT-ADR-010",
        impl_state="Done",
        updated=now,
        updated_by="test",
    )

    issues = validate_project_state(
        state, known_doc_ids={"MEMINIT-PRD-003", "MEMINIT-ADR-010"}, root_dir=tmp_path
    )
    codes = [v.rule for v in issues]
    assert WarningCode.W_STATE_UNSORTED_KEYS in codes


def test_validate_invalid_actor(tmp_path):
    """Emits W_FIELD_SANITIZATION_FAILED for invalid updated_by value."""
    state = ProjectState()
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="Done",
        updated=datetime.now(timezone.utc),
        updated_by="bad<actor>",
    ))

    issues = validate_project_state(state, known_doc_ids={"MEMINIT-PRD-003"}, root_dir=tmp_path)
    codes = [v.rule for v in issues]
    assert WarningCode.W_FIELD_SANITIZATION_FAILED in codes


def test_validate_notes_too_long(tmp_path):
    """Emits W_FIELD_SANITIZATION_FAILED for notes exceeding MAX_NOTES_LENGTH."""
    state = ProjectState()
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="Done",
        updated=datetime.now(timezone.utc),
        updated_by="test",
        notes="x" * 501,
    ))

    issues = validate_project_state(state, known_doc_ids={"MEMINIT-PRD-003"}, root_dir=tmp_path)
    codes = [v.rule for v in issues]
    assert WarningCode.W_FIELD_SANITIZATION_FAILED in codes


# ---------------------------------------------------------------------------
# get_state_file_rel_path
# ---------------------------------------------------------------------------

def test_get_state_file_rel_path_custom_docs_root(tmp_path):
    (tmp_path / "docops.config.yaml").write_text("docs_root: handbook\n")
    from meminit.core.services.project_state import get_state_file_rel_path
    assert get_state_file_rel_path(tmp_path) == "handbook/01-indices/project-state.yaml"


def test_get_state_file_rel_path_default(tmp_path):
    from meminit.core.services.project_state import get_state_file_rel_path
    assert get_state_file_rel_path(tmp_path) == "docs/01-indices/project-state.yaml"
