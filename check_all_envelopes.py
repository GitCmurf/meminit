import json
import subprocess
import os
from pathlib import Path

REPO_ROOT = os.getcwd()
VENV_PYTHON = REPO_ROOT + "/.venv/bin/python3"

def check_command(cmd_args, expected_data_keys=None):
    print(f"Checking: {' '.join(cmd_args)}")
    env = os.environ.copy()
    env["PYTHONPATH"] = REPO_ROOT + "/src"
    
    full_cmd = [VENV_PYTHON, "-m", "meminit.cli.main"] + cmd_args + ["--format", "json"]
    result = subprocess.run(full_cmd, env=env, capture_output=True, text=True)
    
    # Try to parse JSON from stdout
    try:
        envelope = json.loads(result.stdout)
    except Exception as e:
        print(f"  FAILED: could not parse JSON: {e}")
        print(f"  STDOUT: {result.stdout}")
        print(f"  STDERR: {result.stderr}")
        return False

    required_fields = ["output_schema_version", "success", "command", "run_id", "root", "data", "warnings", "violations", "advice"]
    missing = [f for f in required_fields if f not in envelope]
    if missing:
        print(f"  FAILED: missing fields: {missing}")
        return False
    
    if envelope["output_schema_version"] != "2.0":
        print(f"  FAILED: wrong schema version: {envelope['output_schema_version']}")
        return False

    if expected_data_keys:
        missing_data = [k for k in expected_data_keys if k not in envelope["data"]]
        if missing_data:
            print(f"  FAILED: missing data keys: {missing_data}")
            print(f"  DATA: {envelope['data']}")
            return False

    print("  OK")
    return True

# Setup test repo
test_dir = Path("/tmp/meminit_test_envelope")
if test_dir.exists():
    import shutil
    shutil.rmtree(test_dir)
test_dir.mkdir()
os.chdir(test_dir)

# Initialize
env = os.environ.copy()
env["PYTHONPATH"] = REPO_ROOT + "/src"
subprocess.run([VENV_PYTHON, "-m", "meminit.cli.main", "init"], env=env)

# Create index directory to avoid early error
(test_dir / "docs" / "01-indices").mkdir(parents=True, exist_ok=True)
(test_dir / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)

# Run index to create index file
subprocess.run([VENV_PYTHON, "-m", "meminit.cli.main", "index"], env=env)

# List of commands to test
commands = [
    (["check"], []),
    (["context"], ["namespaces", "repo_prefix"]),
    (["doctor"], ["issues"]),
    (["scan"], ["report"]),
    (["index"], ["index_path"]),
    (["resolve", "MEMINIT-ADR-001"], []), 
    (["identify", "docs/45-adr/adr-001-test.md"], []),
    (["link", "MEMINIT-ADR-001"], []),
    (["migrate-ids"], ["report"]),
    (["install-precommit"], ["installed"]),
    (["new", "ADR", "TestADR", "--dry-run"], ["document_id", "path"]),
    (["adr", "new", "TestADR2"], ["path"]),
    (["org", "install", "--dry-run"], ["installed"]),
    (["org", "status"], ["profile_name"]),
    (["org", "vendor", "--dry-run"], ["profile_name"]),
]

all_ok = True
for cmd, keys in commands:
    if not check_command(cmd, keys):
        all_ok = False

if all_ok:
    print("\nALL COMMANDS CONFORM TO ENVELOPE")
else:
    print("\nSOME COMMANDS FAILED")
    exit(1)
