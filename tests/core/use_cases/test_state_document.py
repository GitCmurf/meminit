"""Tests for state_document.py use case."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import yaml

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.sanitization import MAX_ASSIGNEE_LENGTH, MAX_NOTES_LENGTH
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


def test_set_default_priority_is_idempotent(tmp_path):
    """Setting P2 (the default) on an entry with no stored priority should be a no-op."""
    use_case = StateDocumentUseCase(str(tmp_path))
    r1 = use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    mtime1 = state_file.stat().st_mtime

    r2 = use_case.set_state("MEMINIT-ADR-001", priority="P2")
    assert r2.action == "set"
    mtime2 = state_file.stat().st_mtime
    assert mtime2 == mtime1


def test_set_different_actor_is_not_idempotent(tmp_path):
    """Re-running state set with a different --actor must update updated_by."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", actor="user-a")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    mtime1 = state_file.stat().st_mtime

    result = use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", actor="user-b")
    assert result.entry["updated_by"] == "user-b"
    import yaml as _yaml

    raw = _yaml.safe_load(state_file.read_text())
    assert raw["documents"]["MEMINIT-ADR-001"]["updated_by"] == "user-b"


def test_idempotent_set_migrates_legacy_v1(tmp_path):
    """Legacy v1 file is rewritten with state_schema_version 2.0 even on no-op set."""
    state_dir = tmp_path / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "project-state.yaml").write_text(
        "documents:\n"
        "  MEMINIT-ADR-001:\n"
        "    impl_state: Not Started\n"
        "    updated: '2026-01-01T00:00:00+00:00'\n"
        "    updated_by: test\n",
        encoding="utf-8",
    )
    state_file = state_dir / "project-state.yaml"
    assert "state_schema_version" not in state_file.read_text()

    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    assert result.action == "set"
    raw = yaml.safe_load(state_file.read_text())
    assert raw["state_schema_version"] == "2.0"


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


def test_set_canonicalizes_custom_impl_state_after_stripping_input(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: MEMINIT\n"
        "docs_root: docs\n"
        "valid_impl_states:\n"
        "  - Not Started\n"
        "  - Done\n"
        "  - On Hold\n",
        encoding="utf-8",
    )
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state=" on hold ")
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
    with mock.patch("meminit.core.services.repo_config.load_repo_layout", return_value=layout):
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

    with mock.patch("meminit.core.use_cases.state_document.subprocess.run", side_effect=fake_run):
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
        use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", next_action="line1\nline2")
    assert exc_info.value.code == ErrorCode.STATE_FIELD_INVALID_FORMAT


def test_set_aggregates_multiple_fatal_violations(tmp_path):
    """Multiple planning-field fatals are aggregated, not just the first."""
    use_case = StateDocumentUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.set_state(
            "MEMINIT-ADR-001",
            impl_state="Not Started",
            depends_on=["MEMINIT-ADR-001", "!!!invalid-id"],
        )
    assert "2 violation(s)" in exc_info.value.message
    assert exc_info.value.details is not None
    assert len(exc_info.value.details["violations"]) == 2


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


def test_get_state_includes_derived_fields(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-002", impl_state="In Progress")
    use_case.set_state(
        "MEMINIT-ADR-001",
        impl_state="Not Started",
        depends_on=["MEMINIT-ADR-002"],
    )

    blocked = use_case.get_state("MEMINIT-ADR-001").entry
    blocker = use_case.get_state("MEMINIT-ADR-002").entry

    assert blocked["ready"] is False
    assert blocked["open_blockers"] == ["MEMINIT-ADR-002"]
    assert blocked["unblocks"] == []
    assert blocker["ready"] is False
    assert blocker["open_blockers"] == []
    assert blocker["unblocks"] == ["MEMINIT-ADR-001"]


def test_list_states_includes_summary(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")

    result = use_case.list_states()
    assert result.summary is not None
    assert result.summary["total"] == 1
    assert result.summary["returned"] == 1


def test_list_states_summary_excludes_skipped_entries(tmp_path):
    """ready/blocked counts must exclude entries in skip_doc_ids (invalid priority)."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", priority="P1")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-002"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.list_states()
    returned_ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" in returned_ids
    assert "MEMINIT-ADR-002" not in returned_ids
    assert result.summary["ready"] == 1
    assert result.summary["blocked"] == 0


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
    use_case.set_state(
        "MEMINIT-ADR-001", impl_state="Not Started", add_depends_on=["MEMINIT-ADR-002"]
    )
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


def test_next_state_missing_file_returns_string_rule(tmp_path):
    """selection.rule must be a string even when state file is absent."""
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.next_state()
    assert result.reason == "state_missing"
    assert isinstance(result.selection["rule"], str)
    assert ">" in result.selection["rule"]


def test_next_state_skips_invalid_priority_in_state_file(tmp_path):
    """Entries with corrupted priority values are skipped with a warning."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

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
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

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
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-002"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.next_state()
    assert result.entry is not None
    assert result.entry["document_id"] == "MEMINIT-ADR-001"
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_INVALID_PRIORITY" in codes


def test_next_state_derivation_excludes_invalid_priority_entries(tmp_path):
    """Skipped corrupt rows must not influence valid candidates' unblocks counts."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", priority="P1")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started", priority="P1")
    use_case.set_state(
        "MEMINIT-ADR-003",
        impl_state="Not Started",
        priority="P1",
        depends_on=["MEMINIT-ADR-001"],
    )
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["updated"] = "2026-04-02T00:00:00Z"
    raw["documents"]["MEMINIT-ADR-002"]["updated"] = "2026-04-01T00:00:00Z"
    raw["documents"]["MEMINIT-ADR-003"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.next_state()

    assert result.entry is not None
    assert result.entry["document_id"] == "MEMINIT-ADR-002"
    assert result.entry["unblocks"] == []
    assert result.warnings is not None
    assert "STATE_INVALID_PRIORITY" in [w["code"] for w in result.warnings]


class TestMixedMutationModeRejection:
    """BV-1: Mixed mutation modes must be rejected, not silently applied."""

    @pytest.mark.parametrize(
        "field,args",
        [
            (
                "depends_on",
                {"depends_on": ["MEMINIT-ADR-001"], "add_depends_on": ["MEMINIT-ADR-002"]},
            ),
            (
                "depends_on",
                {"depends_on": ["MEMINIT-ADR-001"], "remove_depends_on": ["MEMINIT-ADR-002"]},
            ),
            ("depends_on", {"depends_on": ["MEMINIT-ADR-001"], "clear_depends_on": True}),
            ("depends_on", {"add_depends_on": ["MEMINIT-ADR-002"], "clear_depends_on": True}),
            ("depends_on", {"remove_depends_on": ["MEMINIT-ADR-002"], "clear_depends_on": True}),
            ("depends_on", {"depends_on": [], "clear_depends_on": True}),
            (
                "depends_on",
                {
                    "depends_on": ["MEMINIT-ADR-001"],
                    "add_depends_on": ["MEMINIT-ADR-002"],
                    "clear_depends_on": True,
                },
            ),
            (
                "blocked_by",
                {"blocked_by": ["MEMINIT-ADR-001"], "add_blocked_by": ["MEMINIT-ADR-002"]},
            ),
            (
                "blocked_by",
                {"blocked_by": ["MEMINIT-ADR-001"], "remove_blocked_by": ["MEMINIT-ADR-002"]},
            ),
            ("blocked_by", {"blocked_by": ["MEMINIT-ADR-001"], "clear_blocked_by": True}),
            ("blocked_by", {"add_blocked_by": ["MEMINIT-ADR-002"], "clear_blocked_by": True}),
            ("blocked_by", {"remove_blocked_by": ["MEMINIT-ADR-002"], "clear_blocked_by": True}),
            ("blocked_by", {"blocked_by": [], "clear_blocked_by": True}),
            (
                "blocked_by",
                {
                    "blocked_by": ["MEMINIT-ADR-001"],
                    "add_blocked_by": ["MEMINIT-ADR-002"],
                    "clear_blocked_by": True,
                },
            ),
        ],
    )
    def test_mixed_modes_raise(self, tmp_path, field, args):
        use_case = StateDocumentUseCase(str(tmp_path))
        with pytest.raises(MeminitError) as exc_info:
            use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", **args)
        assert exc_info.value.code == ErrorCode.STATE_MIXED_MUTATION_MODE

    @pytest.mark.parametrize(
        "args",
        [
            {"depends_on": ["MEMINIT-ADR-002"]},
            {"add_depends_on": ["MEMINIT-ADR-002"]},
            {"remove_depends_on": ["MEMINIT-ADR-002"]},
            {"clear_depends_on": True},
            {"blocked_by": ["MEMINIT-ADR-002"]},
            {"add_blocked_by": ["MEMINIT-ADR-002"]},
            {"remove_blocked_by": ["MEMINIT-ADR-002"]},
            {"clear_blocked_by": True},
        ],
    )
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
    state = ProjectState(
        schema_violations=[
            Violation(
                file="f", line=1, rule="E1", message="bad impl_state", severity=Severity.ERROR
            ),
            Violation(file="f", line=2, rule="E2", message="bad updated", severity=Severity.ERROR),
            Violation(
                file="f", line=3, rule="E3", message="bad updated_by", severity=Severity.ERROR
            ),
        ]
    )

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


def test_list_states_rejects_explicit_unknown_schema_version(tmp_path):
    state_dir = tmp_path / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "project-state.yaml").write_text(
        "state_schema_version: '3.0'\n"
        "documents:\n"
        "  MEMINIT-ADR-001:\n"
        "    impl_state: Not Started\n"
        "    updated: '2026-02-15T10:00:00Z'\n"
        "    updated_by: GitCmurf\n",
        encoding="utf-8",
    )

    use_case = StateDocumentUseCase(str(tmp_path))

    with pytest.raises(MeminitError) as exc_info:
        use_case.list_states()

    assert exc_info.value.code == ErrorCode.E_STATE_SCHEMA_VIOLATION
    assert "state_schema_version" in exc_info.value.message


# ---------------------------------------------------------------------------
# Read-path validation: shared validator wired into all query surfaces (PR-U)
# ---------------------------------------------------------------------------


def _write_state_with_corrupt_priority(
    tmp_path, doc_id="MEMINIT-ADR-001", impl_state="Not Started", priority="P9"
):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(doc_id, impl_state=impl_state)
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"][doc_id]["priority"] = priority
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )


def _write_state_with_oversized_assignee(tmp_path, doc_id="MEMINIT-ADR-001"):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(doc_id, impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"][doc_id]["assignee"] = "a" * (MAX_ASSIGNEE_LENGTH + 1)
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )


def _write_state_with_corrupt_scalar_planning_fields(tmp_path, doc_id="MEMINIT-ADR-001"):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(
        doc_id,
        impl_state="Not Started",
        priority="P1",
        assignee="agent-a",
        next_action="Review",
    )
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"][doc_id]["priority"] = "P9"
    raw["documents"][doc_id]["assignee"] = "a" * (MAX_ASSIGNEE_LENGTH + 1)
    raw["documents"][doc_id]["next_action"] = "line1\nline2"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )
    return state_file


def test_set_state_allows_unrelated_mutation_with_corrupt_existing_planning_fields(tmp_path):
    state_file = _write_state_with_corrupt_scalar_planning_fields(tmp_path)

    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state="Done")

    assert result.entry["impl_state"] == "Done"
    assert result.entry["priority"] == "P9"
    assert result.entry["assignee"] == "a" * (MAX_ASSIGNEE_LENGTH + 1)
    assert result.entry["next_action"] == "line1\nline2"
    raw = yaml.safe_load(state_file.read_text())
    assert raw["documents"]["MEMINIT-ADR-001"]["impl_state"] == "Done"
    assert raw["documents"]["MEMINIT-ADR-001"]["priority"] == "P9"


def test_set_state_valid_overwrite_repairs_corrupt_existing_planning_field(tmp_path):
    state_file = _write_state_with_corrupt_scalar_planning_fields(tmp_path)

    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state(
        "MEMINIT-ADR-001",
        priority="P2",
        assignee="agent-b",
        next_action="Ship fix",
    )

    assert "priority" not in result.entry
    assert result.entry["assignee"] == "agent-b"
    assert result.entry["next_action"] == "Ship fix"
    raw = yaml.safe_load(state_file.read_text())
    assert "priority" not in raw["documents"]["MEMINIT-ADR-001"]
    assert raw["documents"]["MEMINIT-ADR-001"]["assignee"] == "agent-b"
    assert raw["documents"]["MEMINIT-ADR-001"]["next_action"] == "Ship fix"


def test_set_state_explicit_invalid_values_still_fail_with_corrupt_existing_fields(tmp_path):
    _write_state_with_corrupt_scalar_planning_fields(tmp_path)
    use_case = StateDocumentUseCase(str(tmp_path))

    with pytest.raises(MeminitError) as exc_info:
        use_case.set_state("MEMINIT-ADR-001", priority="P9")
    assert exc_info.value.code == ErrorCode.STATE_INVALID_PRIORITY

    with pytest.raises(MeminitError) as exc_info:
        use_case.set_state(
            "MEMINIT-ADR-001",
            assignee="a" * (MAX_ASSIGNEE_LENGTH + 1),
        )
    assert exc_info.value.code == ErrorCode.STATE_FIELD_TOO_LONG

    with pytest.raises(MeminitError) as exc_info:
        use_case.set_state(
            "MEMINIT-ADR-001",
            next_action="n" * (MAX_NOTES_LENGTH + 1),
        )
    assert exc_info.value.code == ErrorCode.STATE_FIELD_TOO_LONG

    with pytest.raises(MeminitError) as exc_info:
        use_case.set_state("MEMINIT-ADR-001", next_action="line1\nline2")
    assert exc_info.value.code == ErrorCode.STATE_FIELD_INVALID_FORMAT


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
    use_case.set_state(
        "MEMINIT-ADR-001", impl_state="Not Started", add_depends_on=["MEMINIT-ADR-002"]
    )
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

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
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.list_states()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_INVALID_PRIORITY" in codes
    returned_ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" in returned_ids
    assert "MEMINIT-ADR-002" not in returned_ids


def test_blockers_state_excludes_invalid_priority_rows(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(
        "MEMINIT-ADR-001", impl_state="Not Started", add_depends_on=["MEMINIT-ADR-002"]
    )
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    use_case.set_state(
        "MEMINIT-ADR-003", impl_state="Not Started", add_depends_on=["MEMINIT-ADR-002"]
    )
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

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


def test_blockers_state_known_reflects_state_or_index_membership(tmp_path):
    """blocker_details['known'] is true when the target exists in state or the index."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(
        "MEMINIT-ADR-001", impl_state="Not Started", add_depends_on=["MEMINIT-ADR-002"]
    )
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")

    result = use_case.blockers_state()
    assert result.blocked
    blocker = result.blocked[0]
    state_only = [b for b in blocker["open_blockers"] if b["id"] == "MEMINIT-ADR-002"]
    assert state_only
    assert state_only[0]["known"] is True


def test_blockers_state_known_false_for_truly_unknown(tmp_path):
    """blocker_details['known'] is false when target exists neither in state nor on disk."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(
        "MEMINIT-ADR-001", impl_state="Not Started", add_depends_on=["MEMINIT-ADR-999"]
    )

    result = use_case.blockers_state()
    assert result.blocked
    blocker = result.blocked[0]
    unknown = [b for b in blocker["open_blockers"] if b["id"] == "MEMINIT-ADR-999"]
    assert unknown
    assert unknown[0]["known"] is False


def _write_state_with_self_dependency(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["depends_on"] = ["MEMINIT-ADR-001"]
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )


def test_list_states_warns_on_self_dependency(tmp_path):
    """Self-dependency in state produces a warning but entry remains visible."""
    _write_state_with_self_dependency(tmp_path)
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.list_states()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_SELF_DEPENDENCY" in codes
    ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" in ids


def test_next_state_warns_on_self_dependency(tmp_path):
    """Self-dependency in state produces a warning from state next."""
    _write_state_with_self_dependency(tmp_path)
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.next_state()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_SELF_DEPENDENCY" in codes


def test_blockers_state_warns_on_dependency_cycle(tmp_path):
    """Dependency cycle in state produces a warning from state blockers."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(
        "MEMINIT-ADR-001", impl_state="Not Started", add_depends_on=["MEMINIT-ADR-002"]
    )
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-002"]["depends_on"] = ["MEMINIT-ADR-001"]
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.blockers_state()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_DEPENDENCY_CYCLE" in codes


def test_list_states_warns_on_undefined_dependency(tmp_path):
    """Dangling dependency produces a warning but entry remains visible."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(
        "MEMINIT-ADR-001", impl_state="Not Started", add_depends_on=["MEMINIT-ADR-999"]
    )
    result = use_case.list_states()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_UNDEFINED_DEPENDENCY" in codes
    ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" in ids


def test_list_states_preserves_per_document_invalid_priority_warnings(tmp_path):
    """Multiple docs with STATE_INVALID_PRIORITY each produce their own warning."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    raw["documents"]["MEMINIT-ADR-002"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.list_states()
    assert result.warnings is not None
    pip_warnings = [w for w in result.warnings if w["code"] == "STATE_INVALID_PRIORITY"]
    assert (
        len(pip_warnings) >= 2
    ), f"Expected >= 2 STATE_INVALID_PRIORITY warnings, got {len(pip_warnings)}"
    messages = " ".join(w["message"] for w in pip_warnings)
    assert "MEMINIT-ADR-001" in messages
    assert "MEMINIT-ADR-002" in messages


def test_list_states_invalid_impl_state_raises(tmp_path):
    """Invalid impl_state filter value raises E_INVALID_FILTER_VALUE."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")

    with pytest.raises(MeminitError) as exc_info:
        use_case.list_states(impl_state=["NonExistent"])
    assert exc_info.value.code == ErrorCode.E_INVALID_FILTER_VALUE


def test_list_states_valid_impl_state_filter_succeeds(tmp_path):
    """Valid impl_state filter value returns matching entries."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Done")

    result = use_case.list_states(impl_state=["Done"])
    ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-002" in ids
    assert "MEMINIT-ADR-001" not in ids


def test_blockers_state_summary_excludes_skipped_entries(tmp_path):
    """ready_count and total_entries exclude entries with invalid priority."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(
        "MEMINIT-ADR-001",
        impl_state="Not Started",
        add_depends_on=["MEMINIT-ADR-002"],
    )
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")

    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-002"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.blockers_state()
    assert result.summary["total_entries"] == 1
    assert result.summary["ready"] == 0


def test_blockers_state_recomputes_after_skipping_invalid_priority_targets(tmp_path):
    """A skipped invalid-priority dependency target must not make dependents ready."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(
        "MEMINIT-ADR-001",
        impl_state="Not Started",
        add_depends_on=["MEMINIT-ADR-002"],
    )
    use_case.set_state("MEMINIT-ADR-002", impl_state="Done")

    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-002"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.blockers_state()

    assert result.warnings is not None
    assert "STATE_INVALID_PRIORITY" in [w["code"] for w in result.warnings]
    assert result.summary["total_entries"] == 1
    assert result.summary["blocked"] == 1
    assert result.summary["ready"] == 0
    assert result.blocked == [
        {
            "document_id": "MEMINIT-ADR-001",
            "impl_state": "Not Started",
            "priority": None,
            "assignee": None,
            "open_blockers": [
                {
                    "id": "MEMINIT-ADR-002",
                    "impl_state": None,
                    "known": False,
                }
            ],
        }
    ]


def test_list_states_recomputes_after_skipping_invalid_priority_targets(tmp_path):
    """A skipped invalid-priority dependency target must not make dependents ready."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(
        "MEMINIT-ADR-001",
        impl_state="Not Started",
        add_depends_on=["MEMINIT-ADR-002"],
    )
    use_case.set_state("MEMINIT-ADR-002", impl_state="Done")

    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-002"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.list_states()

    assert result.warnings is not None
    assert "STATE_INVALID_PRIORITY" in [w["code"] for w in result.warnings]
    assert result.summary["total"] == 1
    assert result.summary["blocked"] == 1
    assert result.summary["ready"] == 0
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry["document_id"] == "MEMINIT-ADR-001"
    assert entry["ready"] is False
    assert entry["open_blockers"] == ["MEMINIT-ADR-002"]
    assert entry["unblocks"] == []


def test_list_states_warns_for_state_only_dependency_target(tmp_path):
    """State-only dependency targets remain dangling when absent from the index."""
    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps({"data": {"nodes": [{"document_id": "MEMINIT-ADR-001"}]}}),
        encoding="utf-8",
    )
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    use_case.set_state(
        "MEMINIT-ADR-001", impl_state="Not Started", add_depends_on=["MEMINIT-ADR-002"]
    )

    result = use_case.list_states()
    assert result.warnings is not None
    assert "STATE_UNDEFINED_DEPENDENCY" in [w["code"] for w in result.warnings]


def test_list_states_secondary_warnings_for_invalid_priority_entry(tmp_path):
    """Entry with invalid priority still surfaces self-dependency warning."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")

    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    raw["documents"]["MEMINIT-ADR-001"]["depends_on"] = ["MEMINIT-ADR-001"]
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.list_states()
    assert result.warnings is not None
    codes = [w["code"] for w in result.warnings]
    assert "STATE_INVALID_PRIORITY" in codes
    assert "STATE_SELF_DEPENDENCY" in codes


def test_blockers_summary_respects_assignee_filter(tmp_path):
    """Summary counts reflect only the filtered assignee's entries."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state(
        "MEMINIT-ADR-001",
        impl_state="Not Started",
        add_depends_on=["MEMINIT-ADR-002"],
        assignee="agent:codex",
    )
    use_case.set_state(
        "MEMINIT-ADR-002",
        impl_state="Not Started",
        add_depends_on=["MEMINIT-ADR-003"],
        assignee="human:alice",
    )
    use_case.set_state("MEMINIT-ADR-003", impl_state="Done")

    result = use_case.blockers_state(assignee="agent:codex")
    assert result.summary["total_entries"] == 1
    assert len(result.blocked) == 1
    assert result.blocked[0]["document_id"] == "MEMINIT-ADR-001"


def test_entry_to_dict_always_includes_dependency_arrays(tmp_path):
    """depends_on and blocked_by are always present as arrays, even when empty."""
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    entry = result.entry
    assert "depends_on" in entry
    assert "blocked_by" in entry
    assert entry["depends_on"] == []
    assert entry["blocked_by"] == []


def test_list_states_no_warning_for_custom_impl_state_from_config(tmp_path):
    """Custom impl_state from docops.config.yaml does not produce W_STATE_UNKNOWN_IMPL_STATE."""
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
    use_case.set_state("MEMINIT-ADR-001", impl_state="On Hold")
    result = use_case.list_states()
    if result.warnings:
        codes = [w["code"] for w in result.warnings]
        assert "W_STATE_UNKNOWN_IMPL_STATE" not in codes


def test_set_state_warns_for_state_only_dependency_target(tmp_path):
    """set_state validates dependency targets against the index, not state entries."""
    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps({"data": {"nodes": [{"document_id": "MEMINIT-ADR-001"}]}}),
        encoding="utf-8",
    )
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    result = use_case.set_state(
        "MEMINIT-ADR-001",
        impl_state="Not Started",
        add_depends_on=["MEMINIT-ADR-002"],
    )
    assert result.warnings is not None
    assert "STATE_UNDEFINED_DEPENDENCY" in [w["code"] for w in result.warnings]


def test_blockers_state_marks_state_only_blocker_known(tmp_path):
    """Blocker knownness includes state-only entries even when absent from the index."""
    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps({"data": {"nodes": [{"document_id": "MEMINIT-ADR-001"}]}}),
        encoding="utf-8",
    )
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")
    use_case.set_state(
        "MEMINIT-ADR-001",
        impl_state="Not Started",
        add_blocked_by=["MEMINIT-ADR-002"],
    )

    result = use_case.blockers_state()

    assert result.blocked[0]["open_blockers"] == [
        {"id": "MEMINIT-ADR-002", "impl_state": "Not Started", "known": True}
    ]


def test_list_states_invalid_priority_raises_without_state_file(tmp_path):
    """Invalid priority filter raises even when no state file exists."""
    use_case = StateDocumentUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.list_states(priority=["P9"])
    assert exc_info.value.code == ErrorCode.E_INVALID_FILTER_VALUE


def test_list_states_invalid_impl_state_raises_without_state_file(tmp_path):
    """Invalid impl_state filter raises even when no state file exists."""
    use_case = StateDocumentUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.list_states(impl_state=["Bogus"])
    assert exc_info.value.code == ErrorCode.E_INVALID_FILTER_VALUE


def test_next_state_invalid_priority_raises_without_state_file(tmp_path):
    """Invalid priority_at_least filter raises even when no state file exists."""
    use_case = StateDocumentUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.next_state(priority_at_least="P9")
    assert exc_info.value.code == ErrorCode.E_INVALID_FILTER_VALUE


def test_list_states_skips_invalid_priority_even_with_no_other_warnings(tmp_path):
    """Invalid-priority entries are excluded even when no other warnings exist."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")

    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.list_states()
    ids = [e["document_id"] for e in result.entries]
    assert "MEMINIT-ADR-001" not in ids


def test_next_state_preserves_filter_on_missing_state(tmp_path):
    """selection.filter echoes query parameters even when no state file exists."""
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.next_state(assignee="agent:codex", priority_at_least="P1")
    assert result.selection["filter"]["assignee"] == "agent:codex"
    assert result.selection["filter"]["priority_at_least"] == "P1"


def test_list_states_summary_total_excludes_skipped(tmp_path):
    """summary.total excludes invalid-priority entries."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")

    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.list_states()
    assert result.summary["total"] == 1


def test_list_states_no_duplicate_field_too_long_warnings(tmp_path):
    """STATE_FIELD_TOO_LONG appears once, not duplicated from both validators."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started")

    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["assignee"] = "x" * 500
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.list_states()
    assert result.warnings is not None
    too_long = [w for w in result.warnings if w["code"] == "STATE_FIELD_TOO_LONG"]
    assert len(too_long) == 1


def test_get_state_excludes_invalid_priority(tmp_path):
    """get_state raises STATE_INVALID_PRIORITY for documents with invalid priority."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", priority="P1")
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-001"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    with pytest.raises(MeminitError) as exc_info:
        use_case.get_state("MEMINIT-ADR-001")
    assert exc_info.value.code == ErrorCode.STATE_INVALID_PRIORITY
    assert "MEMINIT-ADR-001" in exc_info.value.message
    assert "invalid priority" in exc_info.value.message.lower()
    assert "P9" in exc_info.value.message


def test_get_state_includes_validation_warnings(tmp_path):
    """get_state includes validation warnings for valid documents."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", add_depends_on=["MEMINIT-ADR-002"])
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started")

    # Introduce a dependency cycle (ADR-002 depends on ADR-001)
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-002"]["depends_on"] = ["MEMINIT-ADR-001"]
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = use_case.get_state("MEMINIT-ADR-001")
    assert result.warnings is not None
    assert any(w["code"] == "STATE_DEPENDENCY_CYCLE" for w in result.warnings)


def test_get_state_consistent_with_list_states(tmp_path):
    """Entries excluded from list_states due to invalid priority also raise STATE_INVALID_PRIORITY in get_state."""
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Not Started", priority="P1")
    use_case.set_state("MEMINIT-ADR-002", impl_state="Not Started", priority="P2")

    # Corrupt priority for ADR-002
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["MEMINIT-ADR-002"]["priority"] = "P9"
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    # Verify list_states excludes ADR-002
    list_result = use_case.list_states()
    list_ids = [e["document_id"] for e in list_result.entries]
    assert "MEMINIT-ADR-002" not in list_ids

    # Verify get_state raises STATE_INVALID_PRIORITY for ADR-002
    with pytest.raises(MeminitError) as exc_info:
        use_case.get_state("MEMINIT-ADR-002")
    assert exc_info.value.code == ErrorCode.STATE_INVALID_PRIORITY

    # Verify get_state works for valid ADR-001
    get_result = use_case.get_state("MEMINIT-ADR-001")
    assert get_result.document_id == "MEMINIT-ADR-001"
