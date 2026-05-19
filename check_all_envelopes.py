import json
import shutil
import subprocess
import os
import sys
import tempfile
from pathlib import Path

from packaging.version import InvalidVersion, Version

from meminit.core.services.output_contracts import OUTPUT_SCHEMA_VERSION_V3

REPO_ROOT = Path(os.getcwd())
TIMEOUT = 300
VENV_PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python3")

MIN_SUPPORTED_SCHEMA_VERSION = OUTPUT_SCHEMA_VERSION_V3


def check_command(cmd_args, expected_data_keys=None):
    print(f"Checking: {' '.join(cmd_args)}")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    
    full_cmd = [VENV_PYTHON, "-m", "meminit.cli.main"] + cmd_args + ["--format", "json"]
    try:
        result = subprocess.run(full_cmd, env=env, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        print(f"  FAILED: command timed out after {TIMEOUT}s")
        return False
    
    # Check command exit status (Finding #2)
    if result.returncode != 0:
        print(f"  FAILED: command exited with code {result.returncode}")
        print(f"  STDOUT: {result.stdout}")
        print(f"  STDERR: {result.stderr}")
        return False
    
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
    
    # Check success field (Finding #2)
    if not envelope.get("success", False):
        print(f"  FAILED: envelope indicates failure (success=false)")
        print(f"  DATA: {envelope}")
        return False
    
    try:
        ver_current = Version(envelope["output_schema_version"])
    except InvalidVersion:
        print(f"  FAILED: invalid schema version '{envelope['output_schema_version']}'")
        return False
    if ver_current < Version(MIN_SUPPORTED_SCHEMA_VERSION):
        print(f"  FAILED: schema version {envelope['output_schema_version']} is below minimum supported {MIN_SUPPORTED_SCHEMA_VERSION}")
        return False

    if expected_data_keys:
        missing_data = [k for k in expected_data_keys if k not in envelope["data"]]
        if missing_data:
            print(f"  FAILED: missing data keys: {missing_data}")
            print(f"  DATA: {envelope['data']}")
            return False

    print("  OK")
    return True

# Setup test repo with unique temp directory (Finding #12)
_test_dir_ctx = tempfile.TemporaryDirectory(prefix="meminit_test_envelope_")
test_dir = Path(_test_dir_ctx.name)
os.chdir(test_dir)

# Initialize
env = os.environ.copy()
env["PYTHONPATH"] = str(REPO_ROOT / "src")
result = subprocess.run([VENV_PYTHON, "-m", "meminit.cli.main", "init"],
                        env=env, capture_output=True, text=True, timeout=TIMEOUT)
if result.returncode != 0:
    print(f"init failed (exit {result.returncode}): {result.stderr}")
    sys.exit(1)

# Create index directory to avoid early error
(test_dir / "docs" / "01-indices").mkdir(parents=True, exist_ok=True)
(test_dir / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)

# Run index to create index file
result = subprocess.run([VENV_PYTHON, "-m", "meminit.cli.main", "index"],
                        env=env, capture_output=True, text=True, timeout=TIMEOUT)
if result.returncode != 0:
    print(f"index failed (exit {result.returncode}): {result.stderr}")
    sys.exit(1)

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

# Clean up test directory (Finding #12)
_test_dir_ctx.cleanup()

if all_ok:
    print("\nALL COMMANDS CONFORM TO ENVELOPE")
else:
    print("\nSOME COMMANDS FAILED")
    exit(1)
