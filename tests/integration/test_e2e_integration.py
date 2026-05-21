"""Pytest-discoverable E2E integration tests for meminit CLI.

These tests exercise the full meminit workflow in a temporary repository.
They import run_e2e from the standalone scripts/e2e_integration_test.py to
avoid duplicating the core test logic.
"""

import tempfile
import os
from pathlib import Path

import pytest

from scripts.e2e_integration_test import run_e2e

E2E_INDEX_SLA_SECONDS = 15.0


@pytest.mark.slow
def test_e2e_functional():
    """Functional E2E test: init, generate 500 docs, index, verify correctness."""
    with tempfile.TemporaryDirectory(prefix="meminit_e2e_") as temp_dir:
        results = run_e2e(Path(temp_dir))
        assert results["success"] is True


@pytest.mark.slow
@pytest.mark.benchmark
@pytest.mark.skipif(
    os.environ.get("MEMINIT_RUN_BENCHMARKS") != "1",
    reason="Performance SLA is opt-in; set MEMINIT_RUN_BENCHMARKS=1 to run.",
)
def test_e2e_performance_sla():
    """Performance benchmark: index generation should stay comfortably under
    the 15-second guardrail even with subprocess and filesystem variance."""
    with tempfile.TemporaryDirectory(prefix="meminit_e2e_") as temp_dir:
        results = run_e2e(Path(temp_dir))
        assert results["success"] is True
        assert results["index_duration"] <= E2E_INDEX_SLA_SECONDS, (
            f"SLA FAILED: Index generation took {results['index_duration']:.2f}s "
            f"(target <= {E2E_INDEX_SLA_SECONDS:.1f}s)"
        )
