import json
import os
import subprocess
import tempfile
from pathlib import Path

from packaging.version import InvalidVersion, Version

from meminit.core.services.output_contracts import OUTPUT_SCHEMA_VERSION_V3

REPO_ROOT = Path(__file__).resolve().parent
TIMEOUT = 300

MIN_SUPPORTED_SCHEMA_VERSION = OUTPUT_SCHEMA_VERSION_V3


def build_command(cmd_args, root=None):
    full_cmd = ["uv", "run", "meminit"] + cmd_args
    if root is not None and not (len(cmd_args) >= 2 and cmd_args[0] == "org" and cmd_args[1] == "install"):
        full_cmd += ["--root", str(root)]
    full_cmd += ["--format", "json"]
    return full_cmd


def check_command(cmd_args, expected_data_keys=None, root=None):
    print(f"Checking: {' '.join(cmd_args)}")
    env = os.environ.copy()

    full_cmd = build_command(cmd_args, root=root)
    try:
        result = subprocess.run(
            full_cmd,
            env=env,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
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

    required_fields = [
        "output_schema_version",
        "success",
        "command",
        "run_id",
        "data",
        "warnings",
        "violations",
        "advice",
    ]
    missing = [f for f in required_fields if f not in envelope]
    if missing:
        print(f"  FAILED: missing fields: {missing}")
        return False

    # root is conditional: present for repo-aware commands, absent for repo-agnostic (org install)
    is_repo_agnostic = len(cmd_args) >= 2 and cmd_args[0] == "org" and cmd_args[1] == "install"
    if is_repo_agnostic:
        if "root" in envelope:
            print("  FAILED: root field should be absent for repo-agnostic command")
            return False
    else:
        if "root" not in envelope:
            print("  FAILED: root field is required for repo-aware command")
            return False

    # Check success field (Finding #2)
    if not envelope.get("success", False):
        print("  FAILED: envelope indicates failure (success=false)")
        print(f"  DATA: {envelope}")
        return False

    try:
        ver_current = Version(envelope["output_schema_version"])
    except InvalidVersion:
        print(f"  FAILED: invalid schema version '{envelope['output_schema_version']}'")
        return False
    if ver_current < Version(MIN_SUPPORTED_SCHEMA_VERSION):
        print(
            f"  FAILED: schema version {envelope['output_schema_version']} is below minimum supported {MIN_SUPPORTED_SCHEMA_VERSION}"
        )
        return False

    if expected_data_keys:
        missing_data = [k for k in expected_data_keys if k not in envelope["data"]]
        if missing_data:
            print(f"  FAILED: missing data keys: {missing_data}")
            print(f"  DATA: {envelope['data']}")
            return False

    print("  OK")
    return True


def build_test_repo(test_dir):
    env = os.environ.copy()

    # Initialize
    try:
        result = subprocess.run(
            build_command(["init"], root=test_dir),
            env=env,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print(f"init failed: command timed out after {TIMEOUT}s")
        return False
    if result.returncode != 0:
        print(f"init failed (exit {result.returncode}): {result.stderr}")
        return False

    # Create index directory to avoid early error
    (test_dir / "docs" / "01-indices").mkdir(parents=True, exist_ok=True)
    (test_dir / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)

    adr_path = test_dir / "docs" / "45-adr" / "adr-001-test.md"

    # Create a governed document for the identify test
    adr_path.write_text(
        "---\n"
        "document_id: MEMINIT-ADR-001\n"
        "type: ADR\n"
        "title: Test ADR\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2024-01-01\n"
        "owner: test\n"
        "docops_version: 2.0\n"
        "---\n"
        "\n"
        "# MEMINIT-ADR-001: Test ADR\n"
    )

    # Run index to create index file
    try:
        result = subprocess.run(
            build_command(["index"], root=test_dir),
            env=env,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print(f"index failed: command timed out after {TIMEOUT}s")
        return False
    if result.returncode != 0:
        print(f"index failed (exit {result.returncode}): {result.stderr}")
        return False

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

    for cmd, keys in commands:
        if not check_command(cmd, keys, root=test_dir):
            return False

    return True


def main():
    _test_dir_ctx = tempfile.TemporaryDirectory(prefix="meminit_test_envelope_")
    try:
        test_dir = Path(_test_dir_ctx.name)
        if build_test_repo(test_dir):
            print("\nALL COMMANDS CONFORM TO ENVELOPE")
            return 0
        print("\nSOME COMMANDS FAILED")
        return 1
    finally:
        _test_dir_ctx.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
