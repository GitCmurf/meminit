"""Shared v2 output envelope formatter for the Meminit CLI.

This module builds deterministic, single-line JSON envelopes that conform to
the v2 agent output contract defined in SPEC-004 and PRD-003.

Key guarantees:
- Deterministic key ordering (§16.1 of PRD-003)
- Recursive key sorting on all nested dicts
- Sorted arrays for warnings, violations, and advice
- Always-present arrays (warnings, violations, advice default to [])
- data always present (defaults to {})
- timestamp only included when explicitly requested
- run_id is a full UUIDv4
- root is always an absolute path
- Single-line JSON output
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

from meminit.core.services.error_codes import ErrorCode
from meminit.core.services.output_contracts import OUTPUT_SCHEMA_VERSION_V2

# Canonical key ordering for the top-level v2 envelope.
# Keys not in this list are appended in sorted order after `error`.
_ENVELOPE_KEY_ORDER = [
    "output_schema_version",
    "success",
    "command",
    "run_id",
    "timestamp",
    "root",
    "files_checked",
    "files_passed",
    "files_failed",
    "missing_paths_count",
    "schema_failures_count",
    "warnings_count",
    "violations_count",
    "files_with_warnings",
    "files_outside_docs_root_count",
    "checked_paths_count",
    "checked_paths",
    "data",
    "warnings",
    "violations",
    "advice",
    "error",
]

_SCHEMA_VALIDATOR: Draft7Validator | None = None
_SCHEMA_LOAD_FAILED: bool = False
_SCHEMA_WARNING_EMITTED: bool = False

logger = logging.getLogger(__name__)


def _find_schema_path(start: Path) -> Path | None:
    for parent in (start, *start.parents):
        candidate = parent / "docs" / "20-specs" / "agent-output.schema.v2.json"
        if candidate.exists():
            return candidate
    return None


def _get_schema_validator() -> Draft7Validator | None:
    global _SCHEMA_VALIDATOR, _SCHEMA_LOAD_FAILED
    if _SCHEMA_VALIDATOR is not None or _SCHEMA_LOAD_FAILED:
        return _SCHEMA_VALIDATOR

    schema_path = _find_schema_path(Path(__file__).resolve().parent)
    if schema_path is None:
        _SCHEMA_LOAD_FAILED = True
        return None

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        _SCHEMA_VALIDATOR = Draft7Validator(schema)
    except (OSError, json.JSONDecodeError, SchemaError, ValueError):
        _SCHEMA_LOAD_FAILED = True
        return None
    return _SCHEMA_VALIDATOR


def _reset_schema_cache() -> None:
    """Reset the module-level schema validator cache (for testing only)."""
    global _SCHEMA_VALIDATOR, _SCHEMA_LOAD_FAILED, _SCHEMA_WARNING_EMITTED
    _SCHEMA_VALIDATOR = None
    _SCHEMA_LOAD_FAILED = False
    _SCHEMA_WARNING_EMITTED = False


def _validate_envelope(envelope: dict[str, Any]) -> None:
    validator = _get_schema_validator()
    if validator is None:
        global _SCHEMA_WARNING_EMITTED
        if not _SCHEMA_WARNING_EMITTED:
            logger.warning("Schema validator unavailable, skipping envelope validation.")
            _SCHEMA_WARNING_EMITTED = True
        return
    errors = sorted(validator.iter_errors(envelope), key=str)
    if errors:
        messages = "; ".join(error.message for error in errors[:3])
        raise ValueError(f"output envelope failed schema validation: {messages}")


def _sort_key_index(key: str) -> tuple[int, str]:
    """Return a sort key that preserves canonical order for known keys."""
    try:
        return (_ENVELOPE_KEY_ORDER.index(key), key)
    except ValueError:
        return (len(_ENVELOPE_KEY_ORDER), key)


def _recursively_sort_keys(obj: Any) -> Any:
    """Recursively sort dictionary keys for deterministic output."""
    if isinstance(obj, dict):
        return {k: _recursively_sort_keys(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_recursively_sort_keys(item) for item in obj]
    return obj


def _get_line_key(line: Any) -> tuple:
    """Helper to sort None after numeric lines."""
    if line is None:
        return (1, 0.0)
    try:
        return (0, float(line))
    except (TypeError, ValueError):
        return (2, str(line))


def _strip_none_line(item: dict[str, Any]) -> dict[str, Any]:
    """Remove line key when value is None to satisfy schema expectations."""
    if "line" in item and item.get("line") is None:
        cleaned = dict(item)
        cleaned.pop("line", None)
        return cleaned
    return item


def _sort_warnings(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort warnings by (path, line, code, message) per PRD §16.1."""

    cleaned = [_strip_none_line(w) for w in warnings]

    def _key(w: dict[str, Any]) -> tuple:
        return (
            w.get("path", ""),
            *_get_line_key(w.get("line")),
            w.get("code", ""),
            w.get("message", ""),
        )

    return sorted(cleaned, key=_key)


def _sort_violations(violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort violations by path, then sub-keys per PRD §16.1.

    Supports both flat Issue objects and grouped violations.
    """

    def _outer_key(v: dict[str, Any]) -> tuple:
        path = v.get("path", "")
        if "violations" in v:
            # Grouped item: (path, 0, ...)
            # Sorts before flat items for the same path
            return (path, 0, "", "", 0, 0, "")
        # Flat item: (path, 1, code, severity, line_key[0], line_key[1], message)
        line_key = _get_line_key(v.get("line"))
        severity = v.get("severity") or "error"
        return (
            path,
            1,
            v.get("code", ""),
            severity,
            line_key[0],
            line_key[1],
            v.get("message", ""),
        )

    def _inner_violation_key(v: dict[str, Any]) -> tuple:
        # Grouped inner items: sort by code, severity, line, then message per PRD §16.1
        line_key = _get_line_key(v.get("line"))
        severity = v.get("severity") or "error"
        return (
            v.get("code", ""),
            severity,
            line_key[0],
            line_key[1],
            v.get("message", ""),
        )

    # Sort the outer list
    cleaned_outer = []
    for item in violations:
        if "violations" in item and isinstance(item["violations"], list):
            new_item = item.copy()
            new_item["violations"] = [_strip_none_line(v) for v in item["violations"]]
            cleaned_outer.append(new_item)
        else:
            cleaned_outer.append(_strip_none_line(item))

    sorted_outer = sorted(cleaned_outer, key=_outer_key)

    # Sort inner violations for grouped items
    result = []
    for item in sorted_outer:
        if "violations" in item and isinstance(item["violations"], list):
            new_item = item.copy()
            new_item["violations"] = sorted(item["violations"], key=_inner_violation_key)
            result.append(new_item)
        else:
            result.append(item)
    return result


def _sort_advice(advice: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort advice by (code, message) per SPEC-004 §9.3."""

    def _key(a: dict[str, Any]) -> tuple:
        return (a.get("code", ""), a.get("message", ""))

    return sorted(advice, key=_key)


def generate_run_id() -> str:
    """Generate a UUIDv4 run_id (Decision 20.5)."""
    return str(uuid.uuid4())


def _normalize_run_id(run_id: str | None) -> str:
    """Validate or generate a UUIDv4 run_id."""
    if run_id is None:
        return generate_run_id()
    try:
        parsed = uuid.UUID(str(run_id))
    except (ValueError, AttributeError, TypeError):
        return generate_run_id()
    if parsed.version != 4:
        return generate_run_id()
    return str(parsed)


def format_envelope(
    *,
    command: str,
    root: str | Path,
    success: bool,
    data: dict | None = None,
    warnings: list | None = None,
    violations: list | None = None,
    advice: list | None = None,
    error: dict | None = None,
    include_timestamp: bool = False,
    run_id: str | None = None,
    extra_top_level: dict | None = None,
) -> str:
    """Build a v2 JSON envelope as a deterministic single-line string.

    Args:
        command: CLI subcommand name (e.g. "check", "context").
        root: Repository root path (will be resolved to absolute).
        success: Whether the command completed without fatal error.
        data: Command-specific payload. Defaults to {}.
        warnings: Non-fatal issues. Defaults to [].
        violations: Fatal issues. Defaults to [].
        advice: Non-binding recommendations. Defaults to [].
        error: Operational error object (code, message, optional details).
        include_timestamp: If True, include ISO 8601 UTC timestamp.
        run_id: Override run_id (must be a UUIDv4).
        extra_top_level: Additional top-level fields (e.g. check counters).
            These are placed after the standard envelope keys in sorted order.

    Returns:
        A single-line JSON string with no trailing newline.
    """
    # Resolve root to absolute path.
    root_str = Path(root).resolve().as_posix()

    envelope: dict[str, Any] = {
        "output_schema_version": OUTPUT_SCHEMA_VERSION_V2,
        "success": success,
        "command": command,
        "run_id": _normalize_run_id(run_id),
    }

    if include_timestamp:
        envelope["timestamp"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

    envelope["root"] = root_str
    envelope["data"] = _recursively_sort_keys(data if data is not None else {})
    envelope["warnings"] = [
        _recursively_sort_keys(w) for w in _sort_warnings(warnings or [])
    ]
    envelope["violations"] = [
        _recursively_sort_keys(v) for v in _sort_violations(violations or [])
    ]
    envelope["advice"] = [
        _recursively_sort_keys(a) for a in _sort_advice(advice or [])
    ]

    if error is not None:
        envelope["error"] = _recursively_sort_keys(error)

    # Add extra top-level fields (e.g. check counters) in sorted order.
    if extra_top_level:
        reserved = {
            "output_schema_version",
            "success",
            "command",
            "run_id",
            "timestamp",
            "root",
            "data",
            "warnings",
            "violations",
            "advice",
            "error",
        }
        overlap = reserved.intersection(extra_top_level.keys())
        if overlap:
            raise ValueError(f"extra_top_level contains reserved keys: {sorted(overlap)}")
        for k in sorted(extra_top_level.keys()):
            envelope[k] = _recursively_sort_keys(extra_top_level[k])

    # Build final ordered dict respecting canonical key order.
    ordered: dict[str, Any] = {}
    for key in sorted(envelope.keys(), key=_sort_key_index):
        ordered[key] = envelope[key]

    try:
        _validate_envelope(ordered)
    except ValueError as e:
        logger.exception("Envelope schema validation failed")
        # Ensure the error is visible on stderr in CLI contexts
        click.echo(f"WARN: Envelope schema validation failed: {e}", err=True)

    return json.dumps(ordered, separators=(",", ":"), default=str)


def format_error_envelope(
    *,
    command: str,
    root: str | Path,
    error_code: ErrorCode,
    message: str,
    details: dict | None = None,
    include_timestamp: bool = False,
    run_id: str | None = None,
) -> str:
    """Build a v2 error envelope as a deterministic single-line string.

    Convenience wrapper around format_envelope for operational error responses.

    Args:
        command: CLI subcommand name.
        root: Repository root path.
        error_code: ErrorCode enum value.
        message: Human-readable error description.
        details: Optional structured error context.
        include_timestamp: If True, include ISO 8601 UTC timestamp.
        run_id: Override run_id.

    Returns:
        A single-line JSON string with no trailing newline.
    """
    error_obj: dict[str, Any] = {"code": error_code.value, "message": message}
    if details is not None:
        error_obj["details"] = details

    return format_envelope(
        command=command,
        root=root,
        success=False,
        error=error_obj,
        include_timestamp=include_timestamp,
        run_id=run_id,
    )
