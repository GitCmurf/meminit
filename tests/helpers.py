"""Shared test utilities."""

import json


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
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise ValueError("No JSON envelope found in output")
