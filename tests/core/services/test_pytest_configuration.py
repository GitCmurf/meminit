from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_pytest_runs_without_implicit_coverage_plugin(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[3]
    sample_test = tmp_path / "test_sample.py"
    sample_test.write_text(
        "def test_sample():\n"
        "    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:pytest_cov",
                str(sample_test),
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        pytest.fail(f"pytest subprocess timed out after 120s\nstdout: {stdout}\nstderr: {stderr}")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
