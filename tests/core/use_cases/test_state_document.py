"""Tests for state_document.py use case."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import yaml

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.use_cases.state_document import StateDocumentUseCase


def test_set_new_document_creates_state_file(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state="In Progress", notes="Testing")

    assert result.document_id == "MEMINIT-ADR-001"
    assert result.action == "set"
    assert result.entry["impl_state"] == "In Progress"
    assert result.entry["notes"] == "Testing"
    assert result.entry["updated_by"] is not None

    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    assert state_file.exists()


def test_set_existing_document_updates_fields(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="In Progress", notes="V1")
    
    # Update state only
    result2 = use_case.set_state("MEMINIT-ADR-001", impl_state="Blocked")
    assert result2.entry["impl_state"] == "Blocked"
    assert result2.entry["notes"] == "V1"  # Retained
    
    # Update notes only
    result3 = use_case.set_state("MEMINIT-ADR-001", notes="V2")
    assert result3.entry["impl_state"] == "Blocked"  # Retained
    assert result3.entry["notes"] == "V2"


def test_set_canonicalizes_impl_state(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state="qa required")
    # PRD-007: impl_state is normalized
    assert result.entry["impl_state"] == "QA Required"


def test_set_canonicalizes_custom_impl_state_from_config(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: MEMINIT\n"
        "docs_root: docs\n"
        "valid_impl_states:\n"
        "  - Not Started\n"
        "  - In Progress\n"
        "  - Blocked\n"
        "  - QA Required\n"
        "  - Done\n"
        "  - On Hold\n",
        encoding="utf-8",
    )
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state="on hold")
    assert result.entry["impl_state"] == "On Hold"


def test_set_accepts_namespace_custom_impl_state_from_layout(tmp_path):
    layout = SimpleNamespace(
        namespaces=[
            SimpleNamespace(
                repo_prefix="MEMINIT",
                valid_impl_states=[
                    "Not Started",
                    "In Progress",
                    "Blocked",
                    "QA Required",
                    "Done",
                ],
            ),
            SimpleNamespace(repo_prefix="ORG", valid_impl_states=["On Hold"]),
        ]
    )
    with mock.patch(
        "meminit.core.services.repo_config.load_repo_layout", return_value=layout
    ):
        use_case = StateDocumentUseCase(str(tmp_path))
        result = use_case.set_state("MEMINIT-ADR-001", impl_state="on hold")
    assert result.entry["impl_state"] == "On Hold"


def test_set_prefers_repo_root_git_actor(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs.get("cwd"))
        return SimpleNamespace(returncode=0, stdout="repo-user\n")

    with mock.patch(
        "meminit.core.use_cases.state_document.subprocess.run", side_effect=fake_run
    ):
        use_case = StateDocumentUseCase(str(repo_root))
        result = use_case.set_state("MEMINIT-ADR-001", impl_state="Done")

    assert calls[-1] == str(repo_root)
    assert result.entry["updated_by"] == "repo-user"

def test_set_invalid_impl_state_raises(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.set_state("MEMINIT-ADR-001", impl_state="Bogus")
    assert exc_info.value.code == ErrorCode.E_INVALID_FILTER_VALUE


def test_set_next_action_newline_raises_invalid_format(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started",
                           next_action="line1\nline2")
    assert exc_info.value.code == ErrorCode.STATE_FIELD_INVALID_FORMAT


def test_get_document_state(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Done")

    result = use_case.get_state("MEMINIT-ADR-001")
    assert result.action == "get"
    assert result.entry["impl_state"] == "Done"


def test_get_document_state_shorthand(tmp_path):
    """Test that set and get both resolve shorthands."""
    # Write a dummy config to provide a prefix
    (tmp_path / "docops.config.yaml").write_text("repo_prefix: TESTPRE\ndocs_root: docs\n")
    
    use_case = StateDocumentUseCase(str(tmp_path))
    # Set using shorthand
    set_result = use_case.set_state("ADR-005", impl_state="Done")
    assert set_result.document_id == "TESTPRE-ADR-005"
    
    # Get using shorthand
    get_result = use_case.get_state("ADR-005")
    assert get_result.document_id == "TESTPRE-ADR-005"
    assert get_result.entry["impl_state"] == "Done"


def test_get_missing_document_raises(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Done")

    with pytest.raises(MeminitError) as exc_info:
        use_case.get_state("MEMINIT-ADR-002")
    assert exc_info.value.code == ErrorCode.FILE_NOT_FOUND


def test_list_states_sorted(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    # Use full IDs with namespace prefix to avoid shorthand resolution
    # (the test environment creates TESTLISTST namespace)
    use_case.set_state("TESTLISTST-C-002", impl_state="Done")
    use_case.set_state("TESTLISTST-A-001", impl_state="In Progress")
    use_case.set_state("TESTLISTST-B-003", impl_state="Blocked")

    result = use_case.list_states()
    assert result.action == "list"
    assert len(result.entries) == 3

    ids = [e["document_id"] for e in result.entries]
    assert ids == ["TESTLISTST-A-001", "TESTLISTST-B-003", "TESTLISTST-C-002"]  # Alphabetical 


def test_list_states_includes_derived_fields(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")

    result = use_case.list_states()
    assert result.action == "list"
    entry = result.entries[0]
    assert "ready" in entry
    assert "open_blockers" in entry
    assert "unblocks" in entry


def test_list_states_includes_summary(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")

    result = use_case.list_states()
    assert result.summary is not None
    assert result.summary["total"] == 1
    assert result.summary["returned"] == 1


def test_list_states_ready_filter(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    use_case.set_state("MEMINIT-ADR-002", impl_state="In Progress")

    result = use_case.list_states(ready=True)
    ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" in ids
    assert "MEMINIT-ADR-002" not in ids


def test_list_states_blocked_filter(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started",
                        add_depends_on=["MEMINIT-ADR-002"])
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")

    result = use_case.list_states(blocked=True)
    ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" in ids
    assert "MEMINIT-ADR-002" not in ids


def test_list_states_priority_filter(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", priority="P0")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started", priority="P3")

    result = use_case.list_states(priority=["P0"])
    ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" in ids
    assert "MEMINIT-ADR-002" not in ids


def test_list_states_invalid_priority_raises(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")

    with pytest.raises(MeminitError) as exc_info:
        use_case.list_states(priority=["P9"])
    assert exc_info.value.code == ErrorCode.E_INVALID_FILTER_VALUE


def test_list_states_assignee_filter(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", assignee="agent:codex")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started", assignee="human:alice")

    result = use_case.list_states(assignee=["agent:codex"])
    ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" in ids
    assert "MEMINIT-ADR-002" not in ids


def test_list_states_impl_state_filter(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="In Progress")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Done")

    result = use_case.list_states(impl_state=["In Progress"])
    ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" in ids
    assert "MEMINIT-ADR-002" not in ids


def test_list_states_impl_state_filter_case_insensitive(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="In Progress")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Done")

    result = use_case.list_states(impl_state=["done"])
    ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-002" in ids
    assert "MEMINIT-ADR-001" not in ids


def test_list_states_impl_state_repeatable(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="In Progress")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Blocked")

    result = use_case.list_states(impl_state=["In Progress", "Blocked"])
    ids = [e["document_id"] for e in result.entries]
    assert len(ids) == 2


@mock.patch.dict("os.environ", {"MEMINIT_ACTOR_ID": "ci-bot"})
def test_actor_resolution_env_var(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state="Done")
    assert result.entry["updated_by"] == "ci-bot"


def test_next_state_skips_invalid_priority_in_state_file(tmp_path):
    """Entries with corrupted priority values are skipped with a warning."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    import yaml
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True))

    result = use_case.next_state()
    assert result.entry is None
    assert result.reason == "queue_empty"
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_INVALID_PRIORITY" in codes
    pip_w = [w for w in result.warnings if w["code"] == "STATE_INVALID_PRIORITY"]
    assert "MEMINIT-ADR-001" in pip_w[0]["message"]
    assert pip_w[0]["path"] == "docs/01-indices/project-state.yaml"


def test_next_state_warns_invalid_priority_on_non_ready_entry(tmp_path):
    """Finding 1 regression: invalid priority on a blocked/in-progress entry
    still produces a warning even though the entry is not a candidate."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="In Progress")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    import yaml
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True))

    result = use_case.next_state()
    assert result.entry is None
    assert result.reason == "queue_empty"
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_INVALID_PRIORITY" in codes
    pip_w = [w for w in result.warnings if w["code"] == "STATE_INVALID_PRIORITY"]
    assert "MEMINIT-ADR-001" in pip_w[0]["message"]


def test_next_state_valid_entry_selected_despite_other_having_bad_priority(tmp_path):
    """Valid entries are still selected when another entry has a bad priority."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", priority="P1")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    import yaml
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-002"]["priority"] = "P9"
    state_file.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True))

    result = use_case.next_state()
    assert result.entry is not None
    assert result.entry["document_id"] == "MEMINIT-ADR-001"
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_INVALID_PRIORITY" in codes


class TestMixedMutationModeRejection:
    """BV-1: Mixed mutation modes must be rejected, not silently applied."""

    @pytest.mark.parametrize("field,args", [
        ("depends_on", {"depends_on": ["MEMINIT-ADR-001"], "add_depends_on": ["MEMINIT-ADR-002"]}),
        ("depends_on", {"depends_on": ["MEMINIT-ADR-001"], "remove_depends_on": ["MEMINIT-ADR-002"]}),
        ("depends_on", {"depends_on": ["MEMINIT-ADR-001"], "clear_depends_on": True}),
        ("depends_on", {"add_depends_on": ["MEMINIT-ADR-002"], "clear_depends_on": True}),
        ("depends_on", {"remove_depends_on": ["MEMINIT-ADR-002"], "clear_depends_on": True}),
        ("depends_on", {"depends_on": ["MEMINIT-ADR-001"], "add_depends_on": ["MEMINIT-ADR-002"], "clear_depends_on": True}),
        ("blocked_by", {"blocked_by": ["MEMINIT-ADR-001"], "add_blocked_by": ["MEMINIT-ADR-002"]}),
        ("blocked_by", {"blocked_by": ["MEMINIT-ADR-001"], "remove_blocked_by": ["MEMINIT-ADR-002"]}),
        ("blocked_by", {"blocked_by": ["MEMINIT-ADR-001"], "clear_blocked_by": True}),
        ("blocked_by", {"add_blocked_by": ["MEMINIT-ADR-002"], "clear_blocked_by": True}),
        ("blocked_by", {"remove_blocked_by": ["MEMINIT-ADR-002"], "clear_blocked_by": True}),
        ("blocked_by", {"blocked_by": ["MEMINIT-ADR-001"], "add_blocked_by": ["MEMINIT-ADR-002"], "clear_blocked_by": True}),
    ])
    def test_mixed_modes_raise(self, tmp_path, field, args):
        use_case = StateDocumentUseCase(str(tmp_path))
        with pytest.raises(MeminitError) as exc_info:
            use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", **args)
        assert exc_info.value.code == ErrorCode.STATE_MIXED_MUTATION_MODE

    @pytest.mark.parametrize("args", [
        {"depends_on": ["MEMINIT-ADR-002"]},
        {"add_depends_on": ["MEMINIT-ADR-002"]},
        {"remove_depends_on": ["MEMINIT-ADR-002"]},
        {"clear_depends_on": True},
        {"blocked_by": ["MEMINIT-ADR-002"]},
        {"add_blocked_by": ["MEMINIT-ADR-002"]},
        {"remove_blocked_by": ["MEMINIT-ADR-002"]},
        {"clear_blocked_by": True},
    ])
    def test_single_mode_succeeds(self, tmp_path, args):
        use_case = StateDocumentUseCase(str(tmp_path))
        result = use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", **args)
        assert result.action == "set"


def test_set_state_clear_with_impl_state_rejected(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    with pytest.raises(MeminitError) as exc_info:
        use_case.set_state("MEMINIT-ADR-001", clear=True, impl_state="Done")
    assert exc_info.value.code == ErrorCode.STATE_CLEAR_MUTATION_CONFLICT


def test_set_state_clear_with_priority_rejected(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    with pytest.raises(MeminitError) as exc_info:
        use_case.set_state("MEMINIT-ADR-001", clear=True, priority="P0")
    assert exc_info.value.code == ErrorCode.STATE_CLEAR_MUTATION_CONFLICT


def test_set_state_clear_alone_succeeds(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    result = use_case.set_state("MEMINIT-ADR-001", clear=True)
    assert result.action == "clear"


# ---------------------------------------------------------------------------
# _validate_state: aggregate all schema violations (PR-T)
# ---------------------------------------------------------------------------

def test_validate_state_reports_all_schema_violations(tmp_path):
    from meminit.core.services.project_state import ProjectState
    from meminit.core.domain.entities import Severity, Violation

    use_case = StateDocumentUseCase(str(tmp_path))
    state = ProjectState(schema_violations=[
        Violation(file="f", line=1, rule="E1", message="bad impl_state", severity=Severity.ERROR),
        Violation(file="f", line=2, rule="E2", message="bad updated", severity=Severity.ERROR),
        Violation(file="f", line=3, rule="E3", message="bad updated_by", severity=Severity.ERROR),
    ])

    with pytest.raises(MeminitError) as exc_info:
        use_case._validate_state(state)

    err = exc_info.value
    assert err.code == ErrorCode.E_STATE_SCHEMA_VIOLATION
    assert "3 violation(s)" in err.message
    assert "bad impl_state" in err.message
    assert "bad updated" in err.message
    assert "bad updated_by" in err.message
    assert len(err.details["violations"]) == 3
    assert err.details["violations"][0]["rule"] == "E1"
    assert err.details["violations"][2]["message"] == "bad updated_by"


def test_validate_state_no_violations_passes(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case._validate_state(None)
    from meminit.core.services.project_state import ProjectState
    use_case._validate_state(ProjectState())


# ---------------------------------------------------------------------------
# Read-path validation: shared validator wired into all query surfaces (PR-U)
# ---------------------------------------------------------------------------

def _write_state_with_corrupt_priority(tmp_path, doc_id="MEMINIT-ADR-001",
                                       impl_state="Not Started", priority="P9"):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(doc_id, impl_state=impl_state)
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"][doc_id]["priority"] = priority
    state_file.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True))


def _write_state_with_oversized_assignee(tmp_path, doc_id="MEMINIT-ADR-001"):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(doc_id, impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"][doc_id]["assignee"] = "a" * 121
    state_file.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True))


def test_list_states_warns_on_invalid_priority(tmp_path):
    _write_state_with_corrupt_priority(tmp_path)
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.list_states()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_INVALID_PRIORITY" in codes


def test_list_states_warns_on_oversized_assignee(tmp_path):
    _write_state_with_oversized_assignee(tmp_path)
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.list_states()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_FIELD_TOO_LONG" in codes


def test_blockers_state_warns_on_invalid_priority(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started",
                       add_depends_on=["MEMINIT-ADR-002"])
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True))

    result = use_case.blockers_state()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_INVALID_PRIORITY" in codes


def test_next_state_warns_via_shared_validator(tmp_path):
    _write_state_with_corrupt_priority(tmp_path)
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.next_state()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_INVALID_PRIORITY" in codes


def test_list_states_excludes_invalid_priority_rows(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", priority="P1")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-002"]["priority"] = "P9"
    state_file.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True))

    result = use_case.list_states()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_INVALID_PRIORITY" in codes
    returned_ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" in returned_ids
    assert "MEMINIT-ADR-002" not in returned_ids


def test_blockers_state_excludes_invalid_priority_rows(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started",
                       add_depends_on=["MEMINIT-ADR-002"])
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    use_case.set_state("MEMINIT-ADR-003", impl_state="Not Started",
                       add_depends_on=["MEMINIT-ADR-002"])
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True))

    result = use_case.blockers_state()
    assert result.warnings is not None
    blocked_ids = [b["document_id"] for b in result.blocked]
    assert "MEMINIT-ADR-001" not in blocked_ids
    assert "MEMINIT-ADR-003" in blocked_ids


def test_list_states_warns_on_unknown_doc_id_in_state(tmp_path):
    """Stale state entries for docs not on disk produce W_STATE_UNKNOWN_DOC_ID."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Done")

    result = use_case.list_states()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "W_STATE_UNKNOWN_DOC_ID" in codes
