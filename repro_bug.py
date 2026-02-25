
import os
import subprocess
import json
from pathlib import Path

def test_repro():
    output_file = "repro_error.json"
    if os.path.exists(output_file):
        os.remove(output_file)
    
    # Run meminit check on non-existent directory
    # Using python -m meminit.cli.main if installed, or direct path
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    cmd = ["python3", "-m", "meminit.cli.main", "check", "--root", "/tmp/non_existent_dir_12345", "--format", "json", "--output", output_file]
    
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")
    
    if os.path.exists(output_file):
        print(f"SUCCESS: {output_file} was created.")
        with open(output_file, "r") as f:
            print(f"File content: {f.read()}")
    else:
        print(f"FAILURE: {output_file} was NOT created.")

def test_repro_adr():
    output_file = "repro_adr_error.json"
    if os.path.exists(output_file):
        os.remove(output_file)
    
    # Run meminit adr new on non-existent directory
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    cmd = ["python3", "-m", "meminit.cli.main", "adr", "new", "SomeTitle", "--root", "/tmp/non_existent_dir_54321", "--format", "json", "--output", output_file]
    
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    if os.path.exists(output_file):
        print(f"SUCCESS: {output_file} was created.")
        with open(output_file, "r") as f:
            print(f"File content: {f.read()}")
    else:
        print(f"FAILURE: {output_file} was NOT created.")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")

if __name__ == "__main__":
    test_repro()
    test_repro_adr()
