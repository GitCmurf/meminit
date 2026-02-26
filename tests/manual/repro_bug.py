
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


def _run_cli_and_assert_error(cmd: list[str], output_file: Path, env: dict[str, str], cwd: Path) -> dict:
    if output_file.exists():
        output_file.unlink()

    result = subprocess.run(
        cmd,
        env=env,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )

    if not output_file.exists():
        raise AssertionError("Output file was not created.")

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert result.returncode != 0
    assert "error" in payload
    return payload

def test_repro():
    output_file = Path(__file__).parent / "repro_error.json"
    repo_root = Path(__file__).resolve().parents[2]
    src_path = str(repo_root / "src")
    
    # Run meminit check on non-existent directory
    # Using python -m meminit.cli.main if installed, or direct path
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{src_path}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else src_path
    )
    missing_root = Path(tempfile.gettempdir()) / f"meminit-missing-{uuid.uuid4().hex}"
    cmd = [
        sys.executable,
        "-m",
        "meminit.cli.main",
        "check",
        "--root",
        str(missing_root),
        "--format",
        "json",
        "--output",
        str(output_file),
    ]

    payload = _run_cli_and_assert_error(cmd, output_file, env, repo_root)
    print(f"SUCCESS: {output_file.name} was created.")
    print(f"File content: {payload}")

def test_repro_adr():
    output_file = Path(__file__).parent / "repro_adr_error.json"
    repo_root = Path(__file__).resolve().parents[2]
    src_path = str(repo_root / "src")
    
    # Run meminit adr new on non-existent directory
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{src_path}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else src_path
    )
    missing_root = Path(tempfile.gettempdir()) / f"meminit-missing-{uuid.uuid4().hex}"
    cmd = [
        sys.executable,
        "-m",
        "meminit.cli.main",
        "adr",
        "new",
        "SomeTitle",
        "--root",
        str(missing_root),
        "--format",
        "json",
        "--output",
        str(output_file),
    ]

    payload = _run_cli_and_assert_error(cmd, output_file, env, repo_root)
    print(f"SUCCESS: {output_file.name} was created.")
    print(f"File content: {payload}")

if __name__ == "__main__":
    test_repro()
    test_repro_adr()
