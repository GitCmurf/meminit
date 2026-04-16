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


def stdout_text(result: "Result") -> str:
    """Extract pure stdout from a Click test result.

    Click 8.2+ provides ``result.stdout`` separated from ``result.stderr``.
    Falls back to ``result.output`` (stdout+stderr mixed) for older versions.
    """
    if hasattr(result, "stdout"):
        return result.stdout
    return result.output
