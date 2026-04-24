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
    STATE_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION_LEGACY,
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


def test_load_project_state_non_string_doc_id(tmp_path):
    """Non-string document keys produce schema violations."""
    _write_state_file(
        tmp_path,
        'documents:\n  123:\n    impl_state: Done\n    updated: "2026-03-05T10:00:00Z"\n    updated_by: bot\n',
    )
    state = load_project_state(tmp_path)
    assert state is not None
    assert len(state.entries) == 0
    rules = [v.rule for v in state.schema_violations]
    assert ErrorCode.E_STATE_SCHEMA_VIOLATION.value in rules
    messages = [v.message for v in state.schema_violations]
    assert any("must be a string" in m for m in messages)


def test_load_project_state_missing_documents_key_with_other_keys(tmp_path):
    """Non-empty dict without 'documents' key raises MeminitError."""
    _write_state_file(tmp_path, 'version: "1.0"\nmetadata:\n  foo: bar\n')
    with pytest.raises(MeminitError) as exc_info:
        load_project_state(tmp_path)
    assert exc_info.value.code == ErrorCode.E_STATE_SCHEMA_VIOLATION
    assert "no 'documents' key" in exc_info.value.message


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


def test_validate_invalid_priority(tmp_path):
    """Emits STATE_INVALID_PRIORITY for entries with invalid priority."""
    state = ProjectState()
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="Not Started",
        updated=datetime.now(timezone.utc),
        updated_by="test",
        priority="P9",
    ))

    issues = validate_project_state(state, known_doc_ids={"MEMINIT-PRD-003"}, root_dir=tmp_path)
    codes = [v.rule for v in issues]
    assert ErrorCode.STATE_INVALID_PRIORITY.value in codes


def test_validate_valid_priority_no_warning(tmp_path):
    """Valid priority values do not produce STATE_INVALID_PRIORITY."""
    state = ProjectState()
    for p in ("P0", "P1", "P2", "P3"):
        state.set_entry(ProjectStateEntry(
            document_id=f"MEMINIT-PRD-{p[1]}",
            impl_state="Not Started",
            updated=datetime.now(timezone.utc),
            updated_by="test",
            priority=p,
        ))

    issues = validate_project_state(
        state,
        known_doc_ids={"MEMINIT-PRD-0", "MEMINIT-PRD-1", "MEMINIT-PRD-2", "MEMINIT-PRD-3"},
        root_dir=tmp_path,
    )
    codes = [v.rule for v in issues]
    assert ErrorCode.STATE_INVALID_PRIORITY.value not in codes


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


def test_validate_assignee_too_long(tmp_path):
    state = ProjectState()
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="Done",
        updated=datetime.now(timezone.utc),
        updated_by="test",
        assignee="a" * 121,
    ))

    issues = validate_project_state(state, known_doc_ids={"MEMINIT-PRD-003"}, root_dir=tmp_path)
    codes = [v.rule for v in issues]
    assert ErrorCode.STATE_FIELD_TOO_LONG.value in codes
    msgs = [v.message for v in issues if v.rule == ErrorCode.STATE_FIELD_TOO_LONG.value]
    assert any("assignee" in m and "exceeds" in m for m in msgs)


def test_validate_next_action_too_long(tmp_path):
    state = ProjectState()
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="Done",
        updated=datetime.now(timezone.utc),
        updated_by="test",
        next_action="x" * 501,
    ))

    issues = validate_project_state(state, known_doc_ids={"MEMINIT-PRD-003"}, root_dir=tmp_path)
    codes = [v.rule for v in issues]
    assert ErrorCode.STATE_FIELD_TOO_LONG.value in codes
    msgs = [v.message for v in issues if v.rule == ErrorCode.STATE_FIELD_TOO_LONG.value]
    assert any("next_action" in m and "exceeds" in m for m in msgs)


def test_validate_next_action_contains_newline(tmp_path):
    state = ProjectState()
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="Done",
        updated=datetime.now(timezone.utc),
        updated_by="test",
        next_action="line one\nline two",
    ))

    issues = validate_project_state(state, known_doc_ids={"MEMINIT-PRD-003"}, root_dir=tmp_path)
    codes = [v.rule for v in issues]
    assert ErrorCode.STATE_FIELD_TOO_LONG.value in codes
    msgs = [v.message for v in issues if v.rule == ErrorCode.STATE_FIELD_TOO_LONG.value]
    assert any("next_action" in m and "newline" in m for m in msgs)


def test_validate_assignee_and_next_action_within_bounds(tmp_path):
    state = ProjectState()
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-PRD-003",
        impl_state="Done",
        updated=datetime.now(timezone.utc),
        updated_by="test",
        assignee="a" * 120,
        next_action="x" * 500,
    ))

    issues = validate_project_state(state, known_doc_ids={"MEMINIT-PRD-003"}, root_dir=tmp_path)
    codes = [v.rule for v in issues]
    assert ErrorCode.STATE_FIELD_TOO_LONG.value not in codes

def test_get_state_file_rel_path_custom_docs_root(tmp_path):
    (tmp_path / "docops.config.yaml").write_text("docs_root: handbook\n")
    from meminit.core.services.project_state import get_state_file_rel_path
    assert get_state_file_rel_path(tmp_path) == "handbook/01-indices/project-state.yaml"


def test_get_state_file_rel_path_default(tmp_path):
    from meminit.core.services.project_state import get_state_file_rel_path
    assert get_state_file_rel_path(tmp_path) == "docs/01-indices/project-state.yaml"


# ---------------------------------------------------------------------------
# v2 schema: load, save, round-trip
# ---------------------------------------------------------------------------

V2_STATE_YAML = """\
state_schema_version: '2.0'
documents:
  MEMINIT-ADR-010:
    impl_state: Not Started
    updated: '2026-04-17T09:12:00+00:00'
    updated_by: GitCmurf
    priority: P1
    depends_on:
      - MEMINIT-PLAN-011
    blocked_by: []
    assignee: agent:augment
    next_action: Draft the FDD skeleton
  MEMINIT-PRD-005:
    impl_state: In Progress
    updated: '2026-04-18T10:15:00+00:00'
    updated_by: GitCmurf
"""

V1_LEGACY_YAML = """\
documents:
  MEMINIT-ADR-010:
    impl_state: Done
    updated: '2026-02-15T10:00:00Z'
    updated_by: GitCmurf
    notes: Legacy entry
"""


def test_load_v2_with_planning_fields(tmp_path):
    _write_state_file(tmp_path, V2_STATE_YAML)
    state = load_project_state(tmp_path)

    assert state is not None
    assert state.schema_version == STATE_SCHEMA_VERSION

    entry = state.get("MEMINIT-ADR-010")
    assert entry is not None
    assert entry.priority == "P1"
    assert entry.depends_on == ("MEMINIT-PLAN-011",)
    assert entry.blocked_by == ()
    assert entry.assignee == "agent:augment"
    assert entry.next_action == "Draft the FDD skeleton"

    entry2 = state.get("MEMINIT-PRD-005")
    assert entry2 is not None
    assert entry2.priority is None
    assert entry2.depends_on == ()
    assert entry2.blocked_by == ()
    assert entry2.assignee is None
    assert entry2.next_action is None


def test_load_legacy_v1_maps_to_v2_defaults(tmp_path):
    _write_state_file(tmp_path, V1_LEGACY_YAML)
    state = load_project_state(tmp_path)

    assert state is not None
    assert state.schema_version == STATE_SCHEMA_VERSION_LEGACY

    entry = state.get("MEMINIT-ADR-010")
    assert entry is not None
    assert entry.priority is None
    assert entry.depends_on == ()
    assert entry.blocked_by == ()
    assert entry.assignee is None
    assert entry.next_action is None
    assert entry.notes == "Legacy entry"


def test_save_emits_schema_version_header(tmp_path):
    state = ProjectState()
    now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-ADR-001",
        impl_state="Not Started",
        updated=now,
        updated_by="test",
    ))

    path = save_project_state(tmp_path, state)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["state_schema_version"] == STATE_SCHEMA_VERSION


def test_save_default_omission(tmp_path):
    state = ProjectState()
    now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-ADR-001",
        impl_state="Not Started",
        updated=now,
        updated_by="test",
    ))

    path = save_project_state(tmp_path, state)
    content = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(content)
    entry_data = raw["documents"]["MEMINIT-ADR-001"]
    assert "priority" not in entry_data
    assert "depends_on" not in entry_data
    assert "blocked_by" not in entry_data
    assert "assignee" not in entry_data
    assert "next_action" not in entry_data


def test_save_explicit_p2_omitted(tmp_path):
    state = ProjectState()
    now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-ADR-001",
        impl_state="Not Started",
        updated=now,
        updated_by="test",
        priority="P2",
    ))

    path = save_project_state(tmp_path, state)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "priority" not in raw["documents"]["MEMINIT-ADR-001"]


def test_save_non_default_priority_written(tmp_path):
    state = ProjectState()
    now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-ADR-001",
        impl_state="Not Started",
        updated=now,
        updated_by="test",
        priority="P0",
    ))

    path = save_project_state(tmp_path, state)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["documents"]["MEMINIT-ADR-001"]["priority"] == "P0"


def test_save_depends_on_sorted(tmp_path):
    state = ProjectState()
    now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-ADR-001",
        impl_state="Not Started",
        updated=now,
        updated_by="test",
        depends_on=("MEMINIT-PRD-009", "MEMINIT-ADR-042"),
    ))

    path = save_project_state(tmp_path, state)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["documents"]["MEMINIT-ADR-001"]["depends_on"] == [
        "MEMINIT-ADR-042", "MEMINIT-PRD-009"
    ]


def test_v2_roundtrip_preserves_planning_fields(tmp_path):
    state = ProjectState()
    now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
    state.set_entry(ProjectStateEntry(
        document_id="MEMINIT-ADR-001",
        impl_state="Not Started",
        updated=now,
        updated_by="test",
        priority="P0",
        depends_on=("MEMINIT-PLAN-011",),
        blocked_by=(),
        assignee="agent:codex",
        next_action="Implement schema",
    ))

    save_project_state(tmp_path, state)
    loaded = load_project_state(tmp_path)

    assert loaded is not None
    entry = loaded.get("MEMINIT-ADR-001")
    assert entry is not None
    assert entry.priority == "P0"
    assert entry.depends_on == ("MEMINIT-PLAN-011",)
    assert entry.assignee == "agent:codex"
    assert entry.next_action == "Implement schema"


def test_legacy_roundtrip_no_data_loss(tmp_path):
    _write_state_file(tmp_path, V1_LEGACY_YAML)
    original = load_project_state(tmp_path)

    assert original is not None
    original_notes = original.get("MEMINIT-ADR-010").notes

    save_project_state(tmp_path, original)
    loaded = load_project_state(tmp_path)

    assert loaded is not None
    entry = loaded.get("MEMINIT-ADR-010")
    assert entry is not None
    assert entry.notes == original_notes
    assert entry.impl_state == "Done"
    assert loaded.schema_version == STATE_SCHEMA_VERSION


def test_utc_normalization_on_load(tmp_path):
    _write_state_file(tmp_path, (
        "documents:\n  MEMINIT-ADR-001:\n    impl_state: Done\n"
        "    updated: '2026-04-21T10:00:00'\n    updated_by: test\n"
    ))
    state = load_project_state(tmp_path)
    assert state is not None
    entry = state.get("MEMINIT-ADR-001")
    assert entry is not None
    assert entry.updated.tzinfo is not None
    assert entry.updated.utcoffset().total_seconds() == 0


class TestProjectStateSchemaV2:
    """GG-2: Validate project-state.yaml against the published v2 JSON Schema."""

    @pytest.fixture
    def schema(self):
        import json as _json
        schema_path = (
            Path(__file__).resolve().parents[3]
            / "docs" / "20-specs" / "project-state.schema.v2.json"
        )
        return _json.loads(schema_path.read_text())

    def test_valid_v2_state_passes_schema(self, tmp_path, schema):
        import jsonschema
        state_dir = tmp_path / "docs" / "01-indices"
        state_dir.mkdir(parents=True)
        (state_dir / "project-state.yaml").write_text(
            "state_schema_version: '2.0'\n"
            "documents:\n"
            "  TEST-ADR-001:\n"
            "    impl_state: Not Started\n"
            "    updated: '2026-04-21T10:00:00+00:00'\n"
            "    updated_by: test\n"
            "    priority: P0\n"
            "    depends_on:\n"
            "      - TEST-ADR-002\n"
            "    assignee: agent:codex\n"
        )
        raw = yaml.safe_load((state_dir / "project-state.yaml").read_text())
        jsonschema.validate(raw, schema)

    def test_invalid_v2_state_fails_schema(self, tmp_path, schema):
        import jsonschema
        state_dir = tmp_path / "docs" / "01-indices"
        state_dir.mkdir(parents=True)
        (state_dir / "project-state.yaml").write_text(
            "state_schema_version: '2.0'\n"
            "documents:\n"
            "  TEST-ADR-001:\n"
            "    impl_state: Not Started\n"
        )
        raw = yaml.safe_load((state_dir / "project-state.yaml").read_text())
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(raw, schema)


# ---------------------------------------------------------------------------
# Malformed planning fields surface as schema violations (Issue 1)
# ---------------------------------------------------------------------------

def _write_state_raw(tmp_path: Path, documents: dict) -> Path:
    state_dir = tmp_path / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "project-state.yaml"
    state_path.write_text(
        yaml.dump(
            {"state_schema_version": "2.0", "documents": documents},
            default_flow_style=False, allow_unicode=True, sort_keys=True,
        ),
        encoding="utf-8",
    )
    return state_path


def test_non_string_priority_surfaces_violation(tmp_path):
    state = _make_state_with_entry(tmp_path, priority=123)
    assert state.entries["TEST-ADR-001"].priority is None
    codes = [v.rule for v in state.schema_violations]
    assert ErrorCode.E_STATE_SCHEMA_VIOLATION.value in codes
    messages = " ".join(v.message for v in state.schema_violations)
    assert "priority" in messages
    assert "int" in messages


def test_non_string_assignee_surfaces_violation(tmp_path):
    state = _make_state_with_entry(tmp_path, assignee=["agent", "codex"])
    assert state.entries["TEST-ADR-001"].assignee is None
    messages = " ".join(v.message for v in state.schema_violations)
    assert "assignee" in messages


def test_non_string_next_action_surfaces_violation(tmp_path):
    state = _make_state_with_entry(tmp_path, next_action=42)
    assert state.entries["TEST-ADR-001"].next_action is None
    messages = " ".join(v.message for v in state.schema_violations)
    assert "next_action" in messages


def test_depends_on_non_string_items_surfaces_violation(tmp_path):
    state = _make_state_with_entry(tmp_path, depends_on=["VALID-001", 42])
    assert state.entries["TEST-ADR-001"].depends_on == ("VALID-001",)
    messages = " ".join(v.message for v in state.schema_violations)
    assert "depends_on" in messages


def _make_state_with_entry(tmp_path: Path, **planning_overrides) -> ProjectState:
    _write_state_raw(tmp_path, {
        "TEST-ADR-001": {
            "impl_state": "Not Started",
            "updated_by": "test",
            "updated": "2026-01-01T00:00:00+00:00",
            **planning_overrides,
        }
    })
    return load_project_state(tmp_path)
