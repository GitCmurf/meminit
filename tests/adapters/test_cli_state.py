
import json
import pytest
from pathlib import Path
from click.testing import CliRunner
from meminit.cli.main import cli

def runner_no_mixed_stderr() -> CliRunner:
    import inspect
    kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        kwargs["mix_stderr"] = False
    return CliRunner(**kwargs)

@pytest.fixture
def repo_with_docs(tmp_path):
    # Setup a minimal repo with some docs
    gov_dir = tmp_path / "docs" / "00-governance"
    gov_dir.mkdir(parents=True)
    (gov_dir / "metadata.schema.json").write_text("{}")
    
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Test\nrepo_prefix: TEST\ndocops_version: '2.0'\n"
        "document_types:\n  ADR: {directory: docs/adr}\n"
    )
    
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "adr-001.md").write_text("---\ndocument_id: TEST-ADR-001\ntitle: ADR 1\nstatus: Approved\n---\nBody")
    (adr_dir / "adr-002.md").write_text("---\ndocument_id: TEST-ADR-002\ntitle: ADR 2\nstatus: Draft\n---\nBody")
    
    return tmp_path

def test_cli_state_set_notes_only(repo_with_docs):
    """P2 Regression: Allow state set --notes without --impl-state."""
    runner = runner_no_mixed_stderr()
    
    # First set a state
    runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--impl-state", "In Progress", "--root", str(repo_with_docs)])
    
    # Now update only notes
    result = runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--notes", "Updated notes", "--root", str(repo_with_docs), "--format", "json"])
    
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert data["data"]["entry"]["impl_state"] == "In Progress"
    assert data["data"]["entry"]["notes"] == "Updated notes"

def test_cli_index_filtering_does_not_persist(repo_with_docs):
    """P1 Regression: Filtered index run should not overwrite the canonical index file with a subset."""
    runner = runner_no_mixed_stderr()
    
    # 1. Run full index
    runner.invoke(cli, ["index", "--root", str(repo_with_docs)])
    index_path = repo_with_docs / "docs" / "01-indices" / "meminit.index.json"
    full_data = json.loads(index_path.read_text())
    assert len(full_data["data"]["documents"]) == 2
    
    # 2. Run filtered index
    result = runner.invoke(cli, ["index", "--status", "Draft", "--root", str(repo_with_docs), "--format", "json"])
    assert result.exit_code == 0
    
    # Check JSON output in stdout (should be filtered)
    stdout_data = json.loads(result.output.strip().splitlines()[-1])
    assert stdout_data["data"]["document_count"] == 1
    assert stdout_data["data"]["documents"][0]["document_id"] == "TEST-ADR-002"
    
    # Check index file on disk (should NOT be filtered)
    disk_data = json.loads(index_path.read_text())
    assert len(disk_data["data"]["documents"]) == 2, "Canonical index file was incorrectly filtered!"

def test_cli_state_list_json(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--impl-state", "Done", "--root", str(repo_with_docs)])
    
    result = runner.invoke(cli, ["state", "list", "--root", str(repo_with_docs), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert len(data["data"]["entries"]) == 1
    assert data["data"]["entries"][0]["document_id"] == "TEST-ADR-001"

def test_cli_state_get_json(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--impl-state", "Blocked", "--root", str(repo_with_docs)])
    
    result = runner.invoke(cli, ["state", "get", "TEST-ADR-001", "--root", str(repo_with_docs), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert data["data"]["impl_state"] == "Blocked"

def test_cli_state_clear_json(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--impl-state", "Done", "--root", str(repo_with_docs)])
    
    result = runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--clear", "--root", str(repo_with_docs), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["data"]["action"] == "clear"
    
    # Verify it's gone from list
    list_result = runner.invoke(cli, ["state", "list", "--root", str(repo_with_docs), "--format", "json"])
    list_data = json.loads(list_result.output.strip().splitlines()[-1])
    assert len(list_data["data"]["entries"]) == 0
