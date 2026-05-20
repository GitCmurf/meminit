"""Shared test utilities."""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from click.testing import Result


def parse_first_json_line(output: str) -> dict:
    """Parse the first JSON line from CLI output.

    CLI output may contain non-JSON lines (e.g., stderr noise). This helper
    skips empty lines and non-JSON lines, returning the first valid JSON dict.
    """
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            result = json.loads(line)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue
    raise ValueError("No JSON envelope found in output")


def parse_json_envelope(output: str) -> dict:
    """Parse exactly one JSON envelope from CLI output.

    Strict variant: asserts exactly one JSON dict is present in the output.
    Raises ValueError if zero or multiple JSON objects are found.
    """
    candidates: list[dict] = []
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                candidates.append(obj)
        except json.JSONDecodeError:
            continue
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError("No JSON envelope found in output")
    raise ValueError(
        f"Expected exactly 1 JSON envelope, found {len(candidates)}"
    )


def stdout_text(result: "Result") -> str:
    """Extract pure stdout from a Click test result.

    Click 8.2+ provides ``result.stdout`` separated from ``result.stderr``.
    Falls back to ``result.output`` (stdout+stderr mixed) for older versions.
    """
    if hasattr(result, "stdout"):
        return result.stdout
    return result.output
