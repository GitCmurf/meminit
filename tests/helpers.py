"""Shared test utilities."""

import json


def parse_first_json_line(output: str) -> dict:
    """Parse the first line of CLI output as JSON.

    CLI output may contain trailing stderr noise; this helper extracts
    just the JSON envelope.
    """
    return json.loads(output.strip().splitlines()[0])
