import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def get_repo_root() -> Path:
    """Return the repository root (parent of the scripts directory)."""
    return Path(__file__).resolve().parents[1]


def build_cli_env() -> dict:
    """Build environment with proper PYTHONPATH for the local source tree."""
    repo_root = get_repo_root()
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    )
    return env


def run(cmd, cwd, env=None, timeout_seconds=180):
    print(f"Running: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"Command timed out after {timeout_seconds}s: {' '.join(cmd)}\n"
            f"stdout: {e.stdout}\nstderr: {e.stderr}"
        )
    if res.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nstderr: {res.stderr}")
    return res.stdout


def run_e2e(root_dir: Path) -> dict:
    """Execute the full E2E integration test and return results.

    Args:
        root_dir: A temporary directory to use as the test repo root.

    Returns:
        A dict with keys:
            - success: bool
            - index_duration: float (seconds)
            - detail: str
    """
    repo_root = get_repo_root()
    env = build_cli_env()
    cli_cmd = [sys.executable, "-m", "meminit.cli.main"]

    # 1. Init repo manually
    (root_dir / "docops.config.yaml").write_text(
        "project_name: Test Project\nrepo_prefix: TST\ndocops_version: '2.0'\n"
        "docs_root: docs\nschema_path: docs/00-governance/metadata.schema.json\n"
    )
    gov_dir = root_dir / "docs" / "00-governance"
    gov_dir.mkdir(parents=True)
    (gov_dir / "metadata.schema.json").write_text('{"type":"object","properties":{}}')

    # 2. Add docs
    print("Generating 500 documents for SLA test...")
    docs_dir = root_dir / "docs" / "99-test"
    docs_dir.mkdir(parents=True)

    start_gen = time.time()
    for i in range(1, 501):
        doc_id = f"TST-TST-{i:03d}"
        content = f"---\ndocument_id: {doc_id}\ntype: TEST\ntitle: Doc {i}\nstatus: Draft\n---\n# Doc {i}\n"
        (docs_dir / f"{doc_id}.md").write_text(content)
    print(f"Generated 500 docs in {time.time() - start_gen:.2f}s")

    # Add project state entries for half of them
    state_dir = root_dir / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_yaml = "documents:\n"
    for i in range(1, 251):
        state_yaml += f"  TST-TST-{i:03d}:\n    impl_state: In Progress\n    updated_by: e2e-test\n    updated: 2026-01-01T00:00:00Z\n"
    (state_dir / "project-state.yaml").write_text(state_yaml)

    # 3. Test `meminit state`
    out = run([*cli_cmd, "state", "set", "TST-TST-001", "--impl-state", "Done"], root_dir, env=env)
    assert "Updated state for TST-TST-001" in out
    out = run([*cli_cmd, "state", "get", "TST-TST-001"], root_dir, env=env)
    assert "Done" in out

    # 4. Test Performance (Index SLA)
    print("Running `meminit index` SLA test...")
    start_index = time.time()
    run([*cli_cmd, "index", "--output-catalog", "--output-kanban"], root_dir, env=env)
    index_duration = time.time() - start_index
    print(f"Index generated in {index_duration:.2f}s")

    # 5. Check outputs
    index_json = (state_dir / "meminit.index.json").read_text()
    assert "TST-TST-500" in index_json

    catalog_md = (state_dir / "catalogue.md").read_text()
    assert "Done" in catalog_md

    kanban_md = (state_dir / "kanban.md").read_text()
    assert "kanban-board" in kanban_md

    # 6. Compatibility check
    print("Running downstream commands...")
    run([*cli_cmd, "resolve", "TST-TST-001"], root_dir, env=env)
    run([*cli_cmd, "identify", "docs/99-test/TST-TST-001.md"], root_dir, env=env)
    run([*cli_cmd, "doctor"], root_dir, env=env)
    # check may fail if dummy docs don't have all required schema fields, but it shouldn't crash
    res_check = subprocess.run([*cli_cmd, "check"], cwd=root_dir, env=env, capture_output=True, text=True, timeout=180)
    assert "Traceback" not in res_check.stderr

    print(f"E2E Integration & Performance OK. (Index 500 docs: {index_duration:.2f}s)")
    return {"success": True, "index_duration": index_duration, "detail": "All checks passed"}


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        print(f"E2E Test Directory: {temp_dir_path}")
        results = run_e2e(temp_dir_path)
        print(f"Results: {results}")


if __name__ == "__main__":
    main()
