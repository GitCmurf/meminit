"""Shared pytest fixtures."""

import pytest
from meminit.core.services.output_formatter import _reset_schema_cache

from tests.helpers import parse_first_json_line  # noqa: F401 — re-export for backward compat


@pytest.fixture(autouse=True)
def reset_schema_cache():
    """Ensure schema cache is reset before each test."""
    _reset_schema_cache()
    yield
    _reset_schema_cache()
