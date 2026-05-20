"""Pytest-discoverable E2E integration tests for meminit CLI.

These tests exercise the full meminit workflow in a temporary repository.
They import run_e2e from the standalone scripts/e2e_integration_test.py to
avoid duplicating the core test logic.
"""

import tempfile
from pathlib import Path

import pytest

from scripts.e2e_integration_test import run_e2e


@pytest.mark.slow
def test_e2e_functional():
    """Functional E2E test: init, generate 500 docs, index, verify correctness."""
    with tempfile.TemporaryDirectory(prefix="meminit_e2e_") as temp_dir:
        results = run_e2e(Path(temp_dir))
        assert results["success"] is True


@pytest.mark.slow
@pytest.mark.benchmark
def test_e2e_performance_sla():
    """Performance SLA: index generation must complete within 10 seconds."""
    with tempfile.TemporaryDirectory(prefix="meminit_e2e_") as temp_dir:
        results = run_e2e(Path(temp_dir))
        assert results["success"] is True
        assert results["index_duration"] <= 10.0, (
            f"SLA FAILED: Index generation took {results['index_duration']:.2f}s "
            f"(target <= 10.0s)"
        )
