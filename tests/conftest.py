"""Shared pytest fixtures."""

import pytest
from meminit.core.services.output_formatter import _reset_schema_cache


@pytest.fixture(autouse=True)
def reset_schema_validator_cache():
    """Ensure schema validator cache is reset before each test."""
    _reset_schema_cache()
    yield
    _reset_schema_cache()
