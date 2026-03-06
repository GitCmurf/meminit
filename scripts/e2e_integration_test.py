import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def run(cmd, cwd):
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED: {res.stderr}")
        exit(1)
    return res.stdout


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        print(f"E2E Test Directory: {temp_dir_path}")

        # Build base command to use local source tree
        cli_cmd = [sys.executable, "-m", "meminit.cli.main"]

        # 1. Init repo manually
        (temp_dir_path / "docops.config.yaml").write_text(
            "project_name: Test Project\nrepo_prefix: TST\ndocops_version: '2.0'\n"
            "docs_root: docs\nschema_path: docs/00-governance/metadata.schema.json\n"
        )
        gov_dir = temp_dir_path / "docs" / "00-governance"
        gov_dir.mkdir(parents=True)
        (gov_dir / "metadata.schema.json").write_text('{"type":"object","properties":{}}')

        # 2. Add docs
        print("Generating 500 documents for SLA test...")
        docs_dir = temp_dir_path / "docs" / "99-test"
        docs_dir.mkdir(parents=True)
        
        start_gen = time.time()
        for i in range(1, 501):
            doc_id = f"TST-{i:03d}"
            content = f"---\ndocument_id: {doc_id}\ntype: TEST\ntitle: Doc {i}\nstatus: Draft\n---\n# Doc {i}\n"
            (docs_dir / f"{doc_id}.md").write_text(content)
        print(f"Generated 500 docs in {time.time() - start_gen:.2f}s")
        
        # Add project state entries for half of them
        state_dir = temp_dir_path / "docs" / "01-indices"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_yaml = "documents:\n"
        for i in range(1, 251):
            state_yaml += f"  TST-{i:03d}:\n    impl_state: In Progress\n    updated_by: e2e-test\n"
        (state_dir / "project-state.yaml").write_text(state_yaml)

        # 3. Test `meminit state`
        out = run(cli_cmd + ["state", "set", "TST-001", "--impl-state", "Done"], temp_dir)
        assert "Updated state for TST-001" in out
        out = run(cli_cmd + ["state", "get", "TST-001"], temp_dir)
        assert "Done" in out

        # 4. Test Performance (Index SLA)
        print("Running `meminit index` SLA test...")
        start_index = time.time()
        run(cli_cmd + ["index", "--output-catalog", "--output-kanban"], temp_dir)
        index_duration = time.time() - start_index
        print(f"Index generated in {index_duration:.2f}s")
        assert index_duration <= 5.0, f"SLA FAILED: Index generation took {index_duration:.2f}s (target <= 5.0s)"
        
        # 5. Check outputs
        index_json = (state_dir / "meminit.index.json").read_text()
        assert "TST-500" in index_json
        
        catalog_md = (state_dir / "catalog.md").read_text()
        assert "Done" in catalog_md
        
        kanban_md = (state_dir / "kanban.md").read_text()
        assert "kanban-board" in kanban_md
        
        # 6. Compatibility check
        print("Running downstream commands...")
        run(cli_cmd + ["resolve", "TST-001"], temp_dir)
        run(cli_cmd + ["identify", "docs/99-test/TST-001.md"], temp_dir)
        run(cli_cmd + ["doctor"], temp_dir)
        # check will fail (exit 1) because dummy docs don't have all required schema fields, but it shouldn't crash
        res_check = subprocess.run(cli_cmd + ["check"], cwd=temp_dir, capture_output=True, text=True)
        assert res_check.returncode != 0, "The 'check' command was expected to fail but succeeded."

        print(f"E2E Integration & Performance OK. (Index 500 docs: {index_duration:.2f}s)")

if __name__ == "__main__":
    main()
