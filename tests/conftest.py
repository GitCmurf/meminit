"""Shared pytest fixtures."""

import json

import pytest
from meminit.core.services.output_formatter import _reset_schema_cache


@pytest.fixture(autouse=True)
def reset_schema_cache():
    """Ensure schema cache is reset before each test."""
    _reset_schema_cache()
    yield
    _reset_schema_cache()


def parse_first_json_line(output: str) -> dict:
    """Parse the first line of CLI output as JSON.

    CLI output may contain trailing stderr noise; this helper extracts
    just the JSON envelope.
    """
    return json.loads(output.strip().splitlines()[0])
