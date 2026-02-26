
import os
import subprocess
from pathlib import Path

def test_repro():
    output_file = Path(__file__).parent / "repro_error.json"
    if output_file.exists():
        output_file.unlink()
    
    # Run meminit check on non-existent directory
    # Using python -m meminit.cli.main if installed, or direct path
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    cmd = [
        "python3",
        "-m",
        "meminit.cli.main",
        "check",
        "--root",
        "/tmp/non_existent_dir_12345",
        "--format",
        "json",
        "--output",
        str(output_file),
    ]
    
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")
    
    if output_file.exists():
        print(f"SUCCESS: {output_file.name} was created.")
        print(f"File content: {output_file.read_text(encoding='utf-8')}")
    else:
        print(f"FAILURE: {output_file.name} was NOT created.")

def test_repro_adr():
    output_file = Path(__file__).parent / "repro_adr_error.json"
    if output_file.exists():
        output_file.unlink()
    
    # Run meminit adr new on non-existent directory
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    cmd = [
        "python3",
        "-m",
        "meminit.cli.main",
        "adr",
        "new",
        "SomeTitle",
        "--root",
        "/tmp/non_existent_dir_54321",
        "--format",
        "json",
        "--output",
        str(output_file),
    ]
    
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    if output_file.exists():
        print(f"SUCCESS: {output_file.name} was created.")
        print(f"File content: {output_file.read_text(encoding='utf-8')}")
    else:
        print(f"FAILURE: {output_file.name} was NOT created.")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")

if __name__ == "__main__":
    test_repro()
    test_repro_adr()
