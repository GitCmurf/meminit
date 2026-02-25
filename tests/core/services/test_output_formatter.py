import json

from meminit.core.services.output_formatter import format_envelope, format_error_envelope
from meminit.core.services.error_codes import ErrorCode


def test_format_envelope_is_deterministic_and_sorted(tmp_path):
    root = tmp_path
    run_id = "00000000-0000-4000-8000-000000000000"

    output = format_envelope(
        command="check",
        root=root,
        success=False,
        data={"b": 1, "a": {"z": 2, "y": 1}},
        warnings=[
            {"path": "b.md", "line": 2, "message": "bbb"},
            {"path": "a.md", "line": None, "message": "aaa"},
            {"path": "a.md", "line": 1, "message": "aaa"},
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
        command="check",
        root=root,
        success=False,
        data={"b": 1, "a": {"z": 2, "y": 1}},
        warnings=[
            {"path": "b.md", "line": 2, "message": "bbb"},
            {"path": "a.md", "line": None, "message": "aaa"},
            {"path": "a.md", "line": 1, "message": "aaa"},
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
        {"line": None, "message": "aaa", "path": "a.md"},
        {"line": 1, "message": "aaa", "path": "a.md"},
        {"line": 2, "message": "bbb", "path": "b.md"},
    ]
    assert payload["violations"] == [
        {"code": "Z", "line": None, "message": "zzz", "path": "docs/0.md", "severity": "error"},
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
        command="check",
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
