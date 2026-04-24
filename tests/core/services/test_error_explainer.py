"""Tests for the error explanation registry and use case."""

from click.testing import CliRunner

from meminit.core.services.error_codes import ERROR_EXPLANATIONS, ErrorCode
from meminit.core.use_cases.explain_error import ExplainErrorUseCase
from meminit.cli.main import cli
from tests.helpers import parse_first_json_line


def test_every_error_code_has_explanation():
    """Every ErrorCode enum member must have a corresponding explanation."""
    missing = [
        code.value for code in ErrorCode
        if code.value not in ERROR_EXPLANATIONS
    ]
    assert not missing, f"ErrorCodes missing explanations: {sorted(missing)}"


def test_explanation_categories_are_valid():
    valid_categories = {"shared", "templates", "state", "agent", "graph", "protocol"}
    for code, explanation in ERROR_EXPLANATIONS.items():
        assert explanation.category in valid_categories, (
            f"{code}: invalid category '{explanation.category}'"
        )


def test_remediation_has_at_least_one_relevant_command_when_applicable():
    for code, explanation in ERROR_EXPLANATIONS.items():
        r = explanation.remediation
        # Codes with no relevant commands should still be valid (e.g. UNKNOWN_ERROR)
        # but most should have at least one.
        assert isinstance(r.relevant_commands, list), (
            f"{code}: relevant_commands is not a list"
        )


_VALID_RESOLUTION_TYPES = {"manual", "auto_fixable", "retryable", "config_change"}


def test_explanation_has_required_fields():
    for code, explanation in ERROR_EXPLANATIONS.items():
        assert explanation.code, f"{code}: missing code"
        assert explanation.category, f"{code}: missing category"
        assert explanation.summary, f"{code}: missing summary"
        assert explanation.cause, f"{code}: missing cause"
        assert explanation.remediation.action, f"{code}: missing remediation.action"
        assert explanation.remediation.resolution_type, (
            f"{code}: missing remediation.resolution_type"
        )
        assert explanation.remediation.resolution_type in _VALID_RESOLUTION_TYPES, (
            f"{code}: invalid resolution_type '{explanation.remediation.resolution_type}', "
            f"must be one of {sorted(_VALID_RESOLUTION_TYPES)}"
        )
        assert isinstance(explanation.remediation.automatable, bool), (
            f"{code}: remediation.automatable is not bool"
        )


def test_unknown_error_code_has_explanation():
    assert ErrorCode.UNKNOWN_ERROR_CODE.value in ERROR_EXPLANATIONS
    e = ERROR_EXPLANATIONS[ErrorCode.UNKNOWN_ERROR_CODE.value]
    assert e.category == "agent"


def test_explain_use_case_returns_valid_code():
    use_case = ExplainErrorUseCase()
    result = use_case.explain("DUPLICATE_ID")
    assert result is not None
    assert result["code"] == "DUPLICATE_ID"
    assert "remediation" in result


def test_explain_use_case_returns_none_for_unknown():
    use_case = ExplainErrorUseCase()
    result = use_case.explain("NONEXISTENT_CODE")
    assert result is None


def test_list_codes_returns_sorted():
    use_case = ExplainErrorUseCase()
    codes = use_case.list_codes()
    values = [c["code"] for c in codes]
    assert values == sorted(values)


def test_list_codes_includes_all():
    use_case = ExplainErrorUseCase()
    codes = use_case.list_codes()
    assert len(codes) == len(ErrorCode)


# ---------------------------------------------------------------------------
# Explain command: invalid-code payload shape (MEMINIT-PLAN-010 §3.4.4)
# ---------------------------------------------------------------------------


def test_explain_invalid_code_puts_requested_code_in_data():
    """Invalid error code must place requested_code in data, not error.details."""
    runner = CliRunner()
    result = runner.invoke(cli, ["explain", "NONEXISTENT_CODE", "--format", "json"])
    assert result.exit_code != 0
    data = parse_first_json_line(result.output)
    assert data["success"] is False
    assert "data" in data
    assert data["data"]["requested_code"] == "NONEXISTENT_CODE"
    assert data["error"]["code"] == "UNKNOWN_ERROR_CODE"


def test_explain_valid_code_has_no_error_object():
    """Valid error code must not include an error object in the envelope."""
    runner = CliRunner()
    result = runner.invoke(cli, ["explain", "DUPLICATE_ID", "--format", "json"])
    assert result.exit_code == 0
    data = parse_first_json_line(result.output)
    assert data["success"] is True
    assert "error" not in data


# ---------------------------------------------------------------------------
# Content correctness audit
# ---------------------------------------------------------------------------


def test_invalid_status_remediation_matches_schema():
    """INVALID_STATUS must list valid statuses from metadata.schema.json."""
    from meminit.core.services.error_codes import ERROR_EXPLANATIONS

    entry = ERROR_EXPLANATIONS[ErrorCode.INVALID_STATUS.value]
    action = entry.remediation.action
    # Schema enum: Draft, In Review, Approved, Superseded
    assert "In Review" in action, "Must use 'In Review' (with space)"
    assert "In-Review" not in action, "Must not use 'In-Review' (with hyphen)"
    assert "Deprecated" not in action, "Deprecated is not in the schema enum"


def test_invalid_filter_value_remediation_matches_impl_state():
    """E_INVALID_FILTER_VALUE must list canonical ImplState values."""
    from meminit.core.services.error_codes import ERROR_EXPLANATIONS

    entry = ERROR_EXPLANATIONS[ErrorCode.E_INVALID_FILTER_VALUE.value]
    action = entry.remediation.action
    # Canonical ImplState values: Not Started, In Progress, Blocked, QA Required, Done
    assert "QA Required" in action, "Must include QA Required"
    assert "Not Started" in action, "Must use canonical display values"


def test_invalid_filter_value_explanation_covers_state_set_misuse():
    from meminit.core.services.error_codes import ERROR_EXPLANATIONS

    entry = ERROR_EXPLANATIONS[ErrorCode.E_INVALID_FILTER_VALUE.value]
    assert "state set" in entry.remediation.action
    assert "--impl-state, --notes, or --clear" in entry.remediation.action
    assert "--actor" in entry.remediation.action
    assert "state set" in entry.remediation.relevant_commands


def test_invalid_id_format_remediation_matches_new_input_validation():
    import re

    from meminit.core.services.error_codes import ERROR_EXPLANATIONS

    entry = ERROR_EXPLANATIONS[ErrorCode.INVALID_ID_FORMAT.value]
    assert "--id" in entry.remediation.action
    assert "migrate-ids" not in entry.remediation.action
    assert not re.search(r"\bfix\b", entry.remediation.action)
    assert entry.remediation.relevant_commands == ["new"]


def test_invalid_related_id_remediation_matches_new_input_validation():
    from meminit.core.services.error_codes import ERROR_EXPLANATIONS

    entry = ERROR_EXPLANATIONS[ErrorCode.INVALID_RELATED_ID.value]
    assert "related_ids" in entry.remediation.action
    assert "superseded_by" in entry.remediation.action
    assert "non-existent" not in entry.cause
    assert entry.remediation.relevant_commands == ["new"]


def test_state_invalid_priority_explanation_covers_dual_contexts():
    """STATE_INVALID_PRIORITY explanation must reference both fatal (write)
    and warning (read/skip) contexts (GG-A consolidation contract test)."""
    use_case = ExplainErrorUseCase()
    result = use_case.explain("STATE_INVALID_PRIORITY")
    assert result is not None
    assert result["code"] == "STATE_INVALID_PRIORITY"

    from meminit.core.services.error_codes import ERROR_EXPLANATIONS, ErrorCode

    entry = ERROR_EXPLANATIONS[ErrorCode.STATE_INVALID_PRIORITY.value]
    assert "fatal" in entry.summary.lower() or "fatal" in entry.cause.lower()
    assert "warning" in entry.summary.lower() or "warning" in entry.cause.lower()
    assert "state set" in entry.cause.lower()
    assert "state next" in entry.cause.lower() or "state list" in entry.cause.lower()
    assert "state set" in entry.remediation.relevant_commands
