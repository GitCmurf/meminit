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
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
