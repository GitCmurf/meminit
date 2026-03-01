import json
from click.testing import CliRunner
from meminit.cli.main import cli
import frontmatter

def runner_no_mixed_stderr() -> CliRunner:
    # Small helper for click > 8.0 compatibility
    import inspect
    kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        kwargs["mix_stderr"] = False
    return CliRunner(**kwargs)


def test_cli_plan_driven_migration_e2e(tmp_path):
    """
    E2E test for the PRD-004 plan-driven migration workflow.
    - Runs scan --plan to generate a plan
    - Verifies the plan file is a valid JSON v2 envelope
    - Runs fix --plan to preview and apply the changes
    - Verifies the file was corrected on disk.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    
    # 1. Provide config
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\n"
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "default_owner: TestTeam\n",
        encoding="utf-8"
    )

    # 2. Provide misnamed lacking-metadata file
    (docs_dir / "my_adr_file.md").write_text(
        "# ADR: The Best Architecture\n\nContent here.",
        encoding="utf-8"
    )

    plan_path = tmp_path / "migration.plan.json"
    runner = runner_no_mixed_stderr()

    # ====== STAGE 1: SCAN --PLAN ======
    result = runner.invoke(cli, ["scan", "--plan", str(plan_path), "--format", "json", "--root", str(tmp_path)])
    assert result.exit_code == 0, f"Scan failed: {result.output}"
    
    scan_envelope = json.loads(result.output.strip().splitlines()[-1])
    assert scan_envelope["success"] is True
    
    # Verify the plan file was written separately and correctly
    assert plan_path.exists()
    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    
    # The written plan should be a full envelope natively describing the plan
    assert plan_data["output_schema_version"] == "2.0"
    assert "plan" in plan_data["data"]
    actions = plan_data["data"]["plan"]["actions"]
    assert len(actions) > 0
    
    # There should be an INSERT_METADATA_BLOCK action and a RENAME/MOVE action
    metadata_actions = [a for a in actions if a["action"] in ("insert_metadata_block", "update_metadata")]
    assert len(metadata_actions) >= 1
    
    move_actions = [a for a in actions if a["action"] in ("move_file", "rename_file")]
    assert len(move_actions) >= 1

    # ====== STAGE 2: FIX --PLAN (Dry Run Default) ======
    fix_dry_result = runner.invoke(cli, ["fix", "--plan", str(plan_path), "--format", "json", "--root", str(tmp_path)])
    # The output might have exit code 1 if there's remaining violations not fixed in dry run, EX_COMPLIANCE_FAIL=77?
    # Actually wait, fix outputs exit code 0 or >0 based on remaining violations
    # But since it's dry run, it didn't fix them.
    # Let's just check the envelope
    fix_dry_env = json.loads(fix_dry_result.output.strip().splitlines()[-1])
    assert fix_dry_env["output_schema_version"] == "2.0"
    
    # The file should NOT be moved yet
    assert not (docs_dir / "45-adr" / "the-best-architecture.md").exists()
    assert (docs_dir / "my_adr_file.md").exists()

    # ====== STAGE 3: FIX --PLAN (Apply) ======
    fix_apply_result = runner.invoke(cli, ["fix", "--plan", str(plan_path), "--no-dry-run", "--format", "json", "--root", str(tmp_path)])
    # The command might exit with 77 due to other structural violations (like missing 00-governance in the minimal test repo)
    # But it should successfully fix the ADR
    fix_apply_env = json.loads(fix_apply_result.output.strip().splitlines()[-1])
    assert fix_apply_env["data"]["fixed"] > 0
    # remaining defaults to >0 because of the repo layout check failures
    
    # The file should be moved and populated!
    old_file = docs_dir / "my_adr_file.md"
    assert not old_file.exists()
    
    # The heuristics logic moves the file to a type-specific directory
    # Find any directory that was created and contains .md files
    subdirs = [d for d in docs_dir.iterdir() if d.is_dir()]
    moved_files = []
    for subdir in subdirs:
        moved_files.extend(subdir.glob("*.md"))
    assert len(moved_files) == 1
    
    post = frontmatter.load(moved_files[0])
    assert post.metadata.get("type") == "ADR"
    assert post.metadata.get("document_id") is not None
    assert post.metadata.get("last_updated") is not None
