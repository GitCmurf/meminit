
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

def test_repro():
    output_file = Path(__file__).parent / "repro_error.json"
    if output_file.exists():
        output_file.unlink()
    
    # Run meminit check on non-existent directory
    # Using python -m meminit.cli.main if installed, or direct path
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"src{os.pathsep}{existing_pythonpath}" if existing_pythonpath else "src"
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

    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    
    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")
    
    if output_file.exists():
        print(f"SUCCESS: {output_file.name} was created.")
        payload = json.loads(output_file.read_text(encoding="utf-8"))
        assert result.returncode != 0
        assert "error" in payload
        print(f"File content: {payload}")
    else:
        print(f"FAILURE: {output_file.name} was NOT created.")
        assert False, "Output file was not created."

def test_repro_adr():
    output_file = Path(__file__).parent / "repro_adr_error.json"
    if output_file.exists():
        output_file.unlink()
    
    # Run meminit adr new on non-existent directory
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"src{os.pathsep}{existing_pythonpath}" if existing_pythonpath else "src"
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

    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)

    if output_file.exists():
        print(f"SUCCESS: {output_file.name} was created.")
        payload = json.loads(output_file.read_text(encoding="utf-8"))
        assert result.returncode != 0
        assert "error" in payload
        print(f"File content: {payload}")
    else:
        print(f"FAILURE: {output_file.name} was NOT created.")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        assert False, "Output file was not created."

if __name__ == "__main__":
    test_repro()
    test_repro_adr()
