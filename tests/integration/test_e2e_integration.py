"""Pytest-discoverable E2E integration tests for meminit CLI.

These tests exercise the full meminit workflow in a temporary repository.
They import run_e2e from the standalone scripts/e2e_integration_test.py to
avoid duplicating the core test logic.
"""

import os
import tempfile
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


def test_stranger_simulation_readme_quickstart():
    """Stranger simulation: validate README quickstart works without maintainer context.

    This test simulates an external agent starting from README only and executing
    the documented workflow on a greenfield repository.
    """
    import subprocess
    import sys

    with tempfile.TemporaryDirectory(prefix="meminit_stranger_") as temp_dir:
        repo_dir = Path(temp_dir)

        # Build CLI environment (mimics a stranger with uv installed)
        repo_root = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        src_path = str(repo_root / "src")
        env["PYTHONPATH"] = src_path

        cli_cmd = [sys.executable, "-m", "meminit.cli.main"]

        # Execute README quickstart (Section: New repository greenfield)
        # 1. uv run meminit init
        result = subprocess.run(
            [*cli_cmd, "init", "--root", str(repo_dir)],
            cwd=repo_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"init failed: {result.stderr}"

        # 2. uv run meminit new ADR "My Decision"
        result = subprocess.run(
            [*cli_cmd, "new", "ADR", "My Decision", "--root", str(repo_dir), "--dry-run", "--format", "json"],
            cwd=repo_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"new ADR failed: {result.stderr}"
        assert "success" in result.stdout, "Expected JSON success indicator"

        # 3. uv run meminit check
        result = subprocess.run(
            [*cli_cmd, "check", "--root", str(repo_dir), "--format", "json"],
            cwd=repo_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"check failed: {result.stderr}"
        assert '"success":true' in result.stdout, "Expected check success"
