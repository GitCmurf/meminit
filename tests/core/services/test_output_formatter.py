import json
import re
from pathlib import Path

from meminit.core.services.output_formatter import format_envelope, format_error_envelope
from meminit.core.services.error_codes import ErrorCode


def test_format_envelope_is_deterministic_and_sorted(tmp_path):
    root = tmp_path
    run_id = "00000000-0000-4000-8000-000000000000"

    output = format_envelope(
        command="context",
        root=root,
        success=False,
        data={"b": 1, "a": {"z": 2, "y": 1}},
        warnings=[
            {"path": "b.md", "line": 2, "code": "WARN_B", "message": "bbb"},
            {"path": "a.md", "line": None, "code": "WARN_A", "message": "aaa"},
            {"path": "a.md", "line": 1, "code": "WARN_A", "message": "aaa"},
        ],
        violations=[
            {"path": "docs/a.md", "code": "B", "severity": "error", "line": 2, "message": "bbb"},
            {"path": "docs/a.md", "code": "A", "severity": "error", "line": 1, "message": "aaa"},
            {"path": "docs/0.md", "code": "Z", "severity": "error", "line": None, "message": "zzz"},
        ],
        advice=[
            {"code": "B", "message": "bbb"},
            {"code": "A", "message": "aaa"},
        ],
        include_timestamp=False,
        run_id=run_id,
        extra_top_level={"zeta": 1, "alpha": 2},
    )
    assert "\n" not in output

    output2 = format_envelope(
        command="context",
        root=root,
        success=False,
        data={"b": 1, "a": {"z": 2, "y": 1}},
        warnings=[
            {"path": "b.md", "line": 2, "code": "WARN_B", "message": "bbb"},
            {"path": "a.md", "line": None, "code": "WARN_A", "message": "aaa"},
            {"path": "a.md", "line": 1, "code": "WARN_A", "message": "aaa"},
        ],
        violations=[
            {"path": "docs/a.md", "code": "B", "severity": "error", "line": 2, "message": "bbb"},
            {"path": "docs/a.md", "code": "A", "severity": "error", "line": 1, "message": "aaa"},
            {"path": "docs/0.md", "code": "Z", "severity": "error", "line": None, "message": "zzz"},
        ],
        advice=[
            {"code": "B", "message": "bbb"},
            {"code": "A", "message": "aaa"},
        ],
        include_timestamp=False,
        run_id=run_id,
        extra_top_level={"zeta": 1, "alpha": 2},
    )
    assert output2 == output

    payload = json.loads(output)

    # Canonical key order (timestamp + error omitted when not requested).
    assert list(payload.keys()) == [
        "output_schema_version",
        "success",
        "command",
        "run_id",
        "root",
        "data",
        "warnings",
        "violations",
        "advice",
        "alpha",
        "zeta",
    ]

    # Data dicts are recursively key-sorted.
    assert list(payload["data"].keys()) == ["a", "b"]
    assert list(payload["data"]["a"].keys()) == ["y", "z"]

    # Arrays are deterministically sorted.
    assert payload["warnings"] == [
        {"code": "WARN_A", "line": 1, "message": "aaa", "path": "a.md"},
        {"code": "WARN_A", "message": "aaa", "path": "a.md"},
        {"code": "WARN_B", "line": 2, "message": "bbb", "path": "b.md"},
    ]
    assert payload["violations"] == [
        {"code": "Z", "message": "zzz", "path": "docs/0.md", "severity": "error"},
        {"code": "A", "line": 1, "message": "aaa", "path": "docs/a.md", "severity": "error"},
        {"code": "B", "line": 2, "message": "bbb", "path": "docs/a.md", "severity": "error"},
    ]
    assert payload["advice"] == [
        {"code": "A", "message": "aaa"},
        {"code": "B", "message": "bbb"},
    ]


def test_format_error_envelope_sorts_details_keys(tmp_path):
    run_id = "00000000-0000-4000-8000-000000000000"
    output = format_error_envelope(
        command="check",
        root=tmp_path,
        error_code=ErrorCode.CONFIG_MISSING,
        message="missing config",
        details={"b": 1, "a": 2},
        include_timestamp=False,
        run_id=run_id,
    )
    payload = json.loads(output)
    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.CONFIG_MISSING.value
    assert list(payload["error"]["details"].keys()) == ["a", "b"]


def test_format_envelope_sorts_warnings_with_code_tiebreaker(tmp_path):
    output = format_envelope(
        command="context",
        root=tmp_path,
        success=True,
        warnings=[
            {"path": "docs/a.md", "line": 10, "code": "WARN_B", "message": "same"},
            {"path": "docs/a.md", "line": 10, "code": "WARN_A", "message": "same"},
        ],
        include_timestamp=False,
        run_id="00000000-0000-4000-8000-000000000000",
    )
    payload = json.loads(output)
    assert payload["warnings"] == [
        {"code": "WARN_A", "line": 10, "message": "same", "path": "docs/a.md"},
        {"code": "WARN_B", "line": 10, "message": "same", "path": "docs/a.md"},
    ]


def test_format_envelope_sorts_violations_by_severity(tmp_path):
    output = format_envelope(
        command="context",
        root=tmp_path,
        success=False,
        violations=[
            {
                "path": "docs/a.md",
                "code": "RULE",
                "severity": "warning",
                "line": 2,
                "message": "warn",
            },
            {
                "path": "docs/a.md",
                "code": "RULE",
                "severity": "error",
                "line": 1,
                "message": "err",
            },
        ],
        include_timestamp=False,
        run_id="00000000-0000-4000-8000-000000000000",
    )
    payload = json.loads(output)
    assert payload["violations"] == [
        {
            "code": "RULE",
            "line": 1,
            "message": "err",
            "path": "docs/a.md",
            "severity": "error",
        },
        {
            "code": "RULE",
            "line": 2,
            "message": "warn",
            "path": "docs/a.md",
            "severity": "warning",
        },
    ]


def test_format_envelope_normalizes_invalid_run_id(tmp_path):
    output = format_envelope(
        command="context",
        root=tmp_path,
        success=True,
        run_id="not-a-uuid",
    )
    payload = json.loads(output)
    assert payload["run_id"] != "not-a-uuid"
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        payload["run_id"],
    )


def test_format_envelope_rejects_reserved_extra_keys(tmp_path):
    try:
        format_envelope(
            command="context",
            root=tmp_path,
            success=True,
            extra_top_level={"success": True},
        )
    except ValueError as exc:
        assert "reserved keys" in str(exc)
    else:
        raise AssertionError("Expected ValueError for reserved extra_top_level keys")


def test_format_envelope_includes_expected_fields_and_single_line(tmp_path):
    output = format_envelope(
        command="context",
        root=tmp_path,
        success=True,
        data={"project_name": "Test"},
        warnings=[],
        violations=[],
        advice=[],
        include_timestamp=False,
        run_id="00000000-0000-4000-8000-000000000000",
    )
    assert "\n" not in output
    payload = json.loads(output)
    assert payload["output_schema_version"] == "2.0"
    assert payload["command"] == "context"
    assert payload["success"] is True
    assert payload["data"]["project_name"] == "Test"
    assert "timestamp" not in payload
    for key in ("run_id", "root", "warnings", "violations", "advice", "data"):
        assert key in payload
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["violations"], list)
    assert isinstance(payload["advice"], list)
    assert Path(payload["root"]).is_absolute()

