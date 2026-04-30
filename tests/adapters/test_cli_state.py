
import json
from pathlib import Path

import pytest
import yaml
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
        "namespaces:\n  default:\n    docs_root: docs\n    prefix: TEST\n"
        "    type_directories:\n      ADR: adr\n"
    )
    
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "adr-001.md").write_text("---\ndocument_id: TEST-ADR-001\ntitle: ADR 1\nstatus: Approved\n---\nBody")
    (adr_dir / "adr-002.md").write_text("---\ndocument_id: TEST-ADR-002\ntitle: ADR 2\nstatus: Draft\n---\nBody")
    
    return tmp_path

def test_cli_state_list_accepts_templates_v2_list_namespaces(tmp_path):
    """State commands accept the normal Templates v2 list-form namespaces config."""
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text("{}")
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Test\n"
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "schema_path: docs/00-governance/metadata.schema.json\n"
        "namespaces:\n"
        "  - name: default\n"
        "    repo_prefix: TEST\n"
        "    docs_root: docs\n"
        "document_types:\n"
        "  ADR:\n"
        "    directory: adr\n"
        "    description: Architecture Decision Record\n",
        encoding="utf-8",
    )

    result = runner_no_mixed_stderr().invoke(
        cli, ["state", "list", "--root", str(tmp_path), "--format", "json"]
    )

    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert data["data"]["entries"] == []

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
    assert data["data"]["impl_state"] == "In Progress"
    assert data["data"]["notes"] == "Updated notes"

def test_cli_index_filtering_does_not_persist(repo_with_docs):
    """P1 Regression: Filtered index run should not overwrite the canonical index file with a subset."""
    runner = runner_no_mixed_stderr()
    
    # 1. Run full index
    runner.invoke(cli, ["index", "--root", str(repo_with_docs)])
    index_path = repo_with_docs / "docs" / "01-indices" / "meminit.index.json"
    full_data = json.loads(index_path.read_text())
    assert len(full_data["data"]["nodes"]) == 2

    # 2. Run filtered index
    result = runner.invoke(cli, ["index", "--status", "Draft", "--root", str(repo_with_docs), "--format", "json"])
    assert result.exit_code == 0

    # Check JSON output in stdout (should be filtered)
    stdout_data = json.loads(result.output.strip().splitlines()[-1])
    assert stdout_data["data"]["node_count"] == 1
    assert stdout_data["data"]["filtered"] is True
    assert stdout_data["data"]["nodes"][0]["document_id"] == "TEST-ADR-002"

    # Edges in stdout must only reference visible nodes.
    visible_ids = {n["document_id"] for n in stdout_data["data"]["nodes"]}
    for edge in stdout_data["data"]["edges"]:
        assert edge["source"] in visible_ids, f"Edge source {edge['source']} not in visible nodes"
        assert edge["target"] in visible_ids, f"Edge target {edge['target']} not in visible nodes"

    # Check index file on disk (should NOT be filtered)
    disk_data = json.loads(index_path.read_text())
    assert len(disk_data["data"]["nodes"]) == 2, "Canonical index file was incorrectly filtered!"


def test_cli_index_filtered_md_output(repo_with_docs):
    """Filtered index in md format reports correct node and edge counts."""
    runner = runner_no_mixed_stderr()

    result = runner.invoke(cli, ["index", "--status", "Draft", "--root", str(repo_with_docs), "--format", "md"])
    assert result.exit_code == 0
    # MD output should show 1 node (only TEST-ADR-002 has status Draft).
    assert "Nodes: 1" in result.output
    # Edge count should match the filtered edges (0 if no edges between visible nodes).
    assert "Edges: 0" in result.output


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
    assert data["data"]["ready"] is False
    assert data["data"]["open_blockers"] == []
    assert data["data"]["unblocks"] == []


def test_cli_state_get_json_propagates_warnings(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--impl-state", "Not Started", "--root", str(repo_with_docs)])
    runner.invoke(cli, ["state", "set", "TEST-ADR-002", "--impl-state", "Not Started", "--root", str(repo_with_docs)])

    state_file = repo_with_docs / "docs" / "01-indices" / "project-state.yaml"
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["TEST-ADR-001"]["depends_on"] = ["TEST-ADR-002"]
    raw["documents"]["TEST-ADR-002"]["depends_on"] = ["TEST-ADR-001"]
    state_file.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True)
    )

    result = runner.invoke(cli, ["state", "get", "TEST-ADR-001", "--root", str(repo_with_docs), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert data["warnings"]
    assert any(w["code"] == "STATE_DEPENDENCY_CYCLE" for w in data["warnings"])

def test_cli_state_clear_json(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--impl-state", "Done", "--root", str(repo_with_docs)])
    
    result = runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--clear", "--root", str(repo_with_docs), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["data"]["action"] == "clear"
    assert data["data"]["document_id"] == "TEST-ADR-001"
    
    list_result = runner.invoke(cli, ["state", "list", "--root", str(repo_with_docs), "--format", "json"])
    list_data = json.loads(list_result.output.strip().splitlines()[-1])
    assert len(list_data["data"]["entries"]) == 0


def test_cli_state_set_priority(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--priority", "P0", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert data["data"]["priority"] == "P0"


def test_cli_state_set_text_shows_planning_fields(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--priority", "P0", "--assignee", "agent:codex",
        "--next-action", "Review PR",
        "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "Priority: P0" in result.output
    assert "Assignee: agent:codex" in result.output
    assert "Next Action: Review PR" in result.output


def test_cli_state_set_invalid_priority(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--priority", "P9", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code != 0


def test_cli_state_set_assignee_and_next_action(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--assignee", "agent:codex", "--next-action", "Implement schema",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["data"]["assignee"] == "agent:codex"
    assert data["data"]["next_action"] == "Implement schema"


def test_cli_state_next_empty_queue(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "next", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert data["data"]["entry"] is None
    assert data["data"]["reason"] == "state_missing"


def test_cli_state_next_with_ready_item(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--priority", "P1", "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "next", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["data"]["entry"] is not None
    assert data["data"]["entry"]["document_id"] == "TEST-ADR-001"
    assert data["data"]["selection"]["rule"] == "priority > unblocks > updated > document_id"
    assert data["data"]["reason"] is None


def test_cli_state_blockers_empty(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "blockers", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["data"]["blocked"] == []
    assert data["data"]["summary"]["ready"] >= 1


def test_cli_state_blockers_with_blocked_entry(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--add-depends-on", "TEST-ADR-002", "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "blockers", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert len(data["data"]["blocked"]) == 1
    assert data["data"]["blocked"][0]["document_id"] == "TEST-ADR-001"


def test_cli_state_set_depends_on_additive(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--add-depends-on", "TEST-ADR-002", "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001",
        "--add-depends-on", "TEST-ADR-003",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert "TEST-ADR-002" in data["data"]["depends_on"]
    assert "TEST-ADR-003" in data["data"]["depends_on"]


def test_cli_state_next_rejects_invalid_priority_at_least(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "next", "--priority-at-least", "P9",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code != 0
    assert "E_INVALID_FILTER_VALUE" in result.output


def test_cli_state_list_ready_filter(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs),
    ])
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-002", "--impl-state", "In Progress",
        "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "list", "--ready", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    ready_ids = [e["document_id"] for e in data["data"]["entries"]]
    assert "TEST-ADR-001" in ready_ids
    assert "TEST-ADR-002" not in ready_ids


def test_cli_state_list_blocked_filter(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--add-depends-on", "TEST-ADR-002", "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "list", "--blocked", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert len(data["data"]["entries"]) == 1
    assert data["data"]["entries"][0]["document_id"] == "TEST-ADR-001"


def test_cli_state_list_priority_filter(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--priority", "P0", "--root", str(repo_with_docs),
    ])
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-002", "--impl-state", "Not Started",
        "--priority", "P3", "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "list", "--priority", "P0",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert len(data["data"]["entries"]) == 1
    assert data["data"]["entries"][0]["document_id"] == "TEST-ADR-001"


def test_cli_state_list_assignee_filter(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--assignee", "agent:codex", "--root", str(repo_with_docs),
    ])
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-002", "--impl-state", "Not Started",
        "--assignee", "human:alice", "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "list", "--assignee", "agent:codex",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert len(data["data"]["entries"]) == 1
    assert data["data"]["entries"][0]["assignee"] == "agent:codex"


def test_cli_state_list_includes_derived_fields(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    entry = data["data"]["entries"][0]
    assert "ready" in entry
    assert "open_blockers" in entry
    assert "unblocks" in entry


def test_cli_state_list_includes_summary(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert "summary" in data["data"]
    assert data["data"]["summary"]["total"] == 1
    assert data["data"]["summary"]["returned"] == 1


def test_cli_state_list_conflicting_ready_flags(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "list", "--ready", "--no-ready",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code != 0
    assert "E_INVALID_FILTER_VALUE" in result.output


def test_cli_state_list_conflicting_blocked_flags(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "list", "--blocked", "--no-blocked",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code != 0
    assert "E_INVALID_FILTER_VALUE" in result.output


def test_cli_state_list_ready_and_blocked_rejected(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "list", "--ready", "--blocked",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code != 0
    assert "E_INVALID_FILTER_VALUE" in result.output


def test_cli_state_list_impl_state_filter(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "In Progress",
        "--root", str(repo_with_docs),
    ])
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-002", "--impl-state", "Done",
        "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "list", "--impl-state", "In Progress",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert len(data["data"]["entries"]) == 1
    assert data["data"]["entries"][0]["document_id"] == "TEST-ADR-001"
    assert data["data"]["entries"][0]["impl_state"] == "In Progress"


def test_cli_state_list_impl_state_repeatable(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "In Progress",
        "--root", str(repo_with_docs),
    ])
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-002", "--impl-state", "Blocked",
        "--root", str(repo_with_docs),
    ])
    result = runner.invoke(cli, [
        "state", "list", "--impl-state", "In Progress", "--impl-state", "Blocked",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert len(data["data"]["entries"]) == 2


class TestCliStateSetMixedMutationModeRejection:
    """BV-1: CLI must reject conflicting mutation flags per field family."""

    @pytest.mark.parametrize("flags", [
        ["--depends-on", "A", "--add-depends-on", "B"],
        ["--depends-on", "A", "--remove-depends-on", "B"],
        ["--depends-on", "A", "--clear-depends-on"],
        ["--add-depends-on", "B", "--clear-depends-on"],
        ["--remove-depends-on", "B", "--clear-depends-on"],
        ["--blocked-by", "A", "--add-blocked-by", "B"],
        ["--blocked-by", "A", "--remove-blocked-by", "B"],
        ["--add-blocked-by", "B", "--clear-blocked-by"],
        ["--remove-blocked-by", "B", "--clear-blocked-by"],
    ])
    def test_cli_rejects_mixed_modes(self, repo_with_docs, flags):
        runner = runner_no_mixed_stderr()
        result = runner.invoke(cli, [
            "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
            *flags, "--root", str(repo_with_docs), "--format", "json",
        ])
        assert result.exit_code != 0
        assert "STATE_MIXED_MUTATION_MODE" in result.output

    def test_cli_single_replace_mode_succeeds(self, repo_with_docs):
        runner = runner_no_mixed_stderr()
        result = runner.invoke(cli, [
            "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
            "--depends-on", "TEST-ADR-002",
            "--root", str(repo_with_docs), "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output.strip().splitlines()[-1])
        assert data["success"] is True

    def test_cli_single_additive_mode_succeeds(self, repo_with_docs):
        runner = runner_no_mixed_stderr()
        result = runner.invoke(cli, [
            "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
            "--add-depends-on", "TEST-ADR-002",
            "--root", str(repo_with_docs), "--format", "json",
        ])
        assert result.exit_code == 0


def test_cli_state_next_invalid_priority_warning_has_path(repo_with_docs):
    """BV-2 regression: invalid priority warnings must include 'path' for schema compliance."""
    import jsonschema
    from pathlib import Path as P

    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs),
    ])
    state_file = repo_with_docs / "docs" / "01-indices" / "project-state.yaml"
    import yaml
    raw = yaml.safe_load(state_file.read_text())
    raw["documents"]["TEST-ADR-001"]["priority"] = "P9"
    state_file.write_text(yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True))

    result = runner.invoke(cli, [
        "state", "next", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    envelope = json.loads(result.output.strip().splitlines()[-1])
    assert envelope["success"] is True
    assert envelope["warnings"] is not None
    pip_w = [w for w in envelope["warnings"] if w["code"] == "STATE_INVALID_PRIORITY"]
    assert len(pip_w) == 1
    warning = pip_w[0]
    assert "code" in warning
    assert "message" in warning
    assert "path" in warning
    assert warning["code"] == "STATE_INVALID_PRIORITY"
    assert warning["path"] == "docs/01-indices/project-state.yaml"

    schema_path = P(__file__).resolve().parents[2] / "src" / "meminit" / "core" / "assets" / "agent-output.schema.v3.json"
    schema = json.loads(schema_path.read_text())
    issue_schema = schema["definitions"]["issue"]
    jsonschema.validate(warning, issue_schema)


def test_cli_state_next_invalid_priority_uses_dynamic_path(tmp_path):
    """Finding 3 regression: warning path must reflect the actual docs_root, not a hardcoded value."""
    import yaml

    custom_docs = tmp_path / "documentation"
    custom_docs.mkdir()
    (custom_docs / "00-governance").mkdir()
    (custom_docs / "00-governance" / "metadata.schema.json").write_text("{}", encoding="utf-8")
    (custom_docs / "45-adr").mkdir()
    (custom_docs / "01-indices").mkdir(parents=True)

    (tmp_path / "docops.config.yaml").write_text(
        "project_name: CustomRoot\nrepo_prefix: CST\ndocops_version: '2.0'\n"
        "docs_root: documentation\n"
        "namespaces:\n  default:\n    docs_root: documentation\n    prefix: CST\n"
        "    type_directories:\n      ADR: '45-adr'\n",
        encoding="utf-8",
    )

    state_file = custom_docs / "01-indices" / "project-state.yaml"
    state_file.write_text(
        "state_schema_version: '2.0'\n"
        "documents:\n  CST-ADR-001:\n    impl_state: Not Started\n"
        "    updated_by: test\n    updated: '2026-04-15T00:00:00+00:00'\n"
        "    priority: P9\n",
        encoding="utf-8",
    )

    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "next", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    envelope = json.loads(result.output.strip().splitlines()[-1])
    warning = envelope["warnings"][0]
    assert warning["path"] == "documentation/01-indices/project-state.yaml"


# ---------------------------------------------------------------------------
# --clear exclusivity: --clear + other flags must be rejected
# ---------------------------------------------------------------------------

def test_cli_state_set_clear_with_impl_state_rejected(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--clear", "--impl-state", "Done",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code != 0
    assert "STATE_CLEAR_MUTATION_CONFLICT" in result.output


def test_cli_state_set_clear_with_notes_rejected(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--clear", "--notes", "x",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code != 0
    assert "STATE_CLEAR_MUTATION_CONFLICT" in result.output


def test_cli_state_set_clear_with_priority_rejected(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--clear", "--priority", "P0",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code != 0
    assert "STATE_CLEAR_MUTATION_CONFLICT" in result.output


def test_cli_state_set_clear_alone_succeeds(repo_with_docs):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--clear",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["data"]["action"] == "clear"
    assert data["data"]["document_id"] == "TEST-ADR-001"


# ---------------------------------------------------------------------------
# Markdown escaping for user-controlled planning fields (Issue 2)
# ---------------------------------------------------------------------------

def test_cli_state_next_md_escapes_assignee_bold(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--assignee", "**bold**", "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "next", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "\\*\\*bold\\*\\*" in result.output
    assert "**bold**" not in result.output.replace("\\*", "")


def test_cli_state_next_md_escapes_next_action_link(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--next-action", "[click](http://evil)", "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "next", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "\\[click\\]" in result.output
    raw_markdown_link = "[click](http://evil)"
    assert raw_markdown_link not in result.output


def test_cli_state_blockers_md_escapes_assignee_html(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--assignee", "<img onerror=alert(1)>",
        "--add-depends-on", "TEST-ADR-002",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "blockers", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "<img" not in result.output
    assert "&lt;img" in result.output


def test_cli_state_list_md_escapes_assignee_html(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--assignee", "<img src=x onerror=alert(1)>",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "<img" not in result.output
    assert "&lt;img" in result.output


def test_cli_state_next_md_escapes_backslash(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--next-action", "test \\ text", "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "next", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "\\\\ text" in result.output


def test_cli_state_list_md_escapes_warning_message(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    _corrupt_priority_in_state(repo_with_docs, priority="P*bold*")
    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "\\*bold\\*" in result.output
    assert "P*bold*" not in result.output.replace("\\*", "")


def test_cli_state_next_md_escapes_warning_message(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    _corrupt_priority_in_state(repo_with_docs, priority="P*bold*")
    result = runner.invoke(cli, [
        "state", "next", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "\\*bold\\*" in result.output
    assert "P*bold*" not in result.output.replace("\\*", "")


def test_cli_state_blockers_md_escapes_warning_message(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--add-depends-on", "TEST-ADR-002",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    _corrupt_priority_in_state(repo_with_docs, priority="P*bold*")
    result = runner.invoke(cli, [
        "state", "blockers", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "\\*bold\\*" in result.output
    assert "P*bold*" not in result.output.replace("\\*", "")


def test_cli_state_blockers_md_escapes_document_id_heading(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--add-depends-on", "TEST-ADR-002",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "blockers", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    heading_line = [l for l in result.output.splitlines() if l.startswith("## ") and "Blocked" not in l and "Warnings" not in l]
    assert any("TEST-ADR-001" in l for l in heading_line)


def test_cli_state_blockers_md_escapes_impl_state_in_blocker_detail(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "In Progress",
        "--add-depends-on", "TEST-ADR-002",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "blockers", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    blocker_lines = [l for l in result.output.splitlines() if "TEST-ADR-002" in l and "unknown" in l]
    assert len(blocker_lines) >= 1


# ---------------------------------------------------------------------------
# Read-path validation: warnings in JSON envelope (PR-U)
# ---------------------------------------------------------------------------

def _corrupt_priority_in_state(repo_with_docs, doc_id="TEST-ADR-001", priority="P9"):
    state_file = repo_with_docs / "docs" / "01-indices" / "project-state.yaml"
    import yaml as _yaml
    raw = _yaml.safe_load(state_file.read_text())
    raw["documents"][doc_id]["priority"] = priority
    state_file.write_text(_yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=True))


def test_cli_state_list_json_includes_validation_warnings(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    _corrupt_priority_in_state(repo_with_docs)
    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert "warnings" in data
    codes = [w["code"] for w in data["warnings"]]
    assert "STATE_INVALID_PRIORITY" in codes


def test_cli_state_blockers_json_includes_validation_warnings(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--add-depends-on", "TEST-ADR-002",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    _corrupt_priority_in_state(repo_with_docs)
    result = runner.invoke(cli, [
        "state", "blockers", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert "warnings" in data
    codes = [w["code"] for w in data["warnings"]]
    assert "STATE_INVALID_PRIORITY" in codes


def test_cli_state_list_md_includes_validation_warnings(repo_with_docs):
    """Human-readable md output surfaces validation warnings."""
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    _corrupt_priority_in_state(repo_with_docs)
    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "STATE\\_INVALID\\_PRIORITY" in result.output
    assert "## Warnings" in result.output


def test_cli_state_blockers_md_includes_validation_warnings(repo_with_docs):
    """Human-readable md blockers output surfaces validation warnings."""
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--add-depends-on", "TEST-ADR-002",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    _corrupt_priority_in_state(repo_with_docs)
    result = runner.invoke(cli, [
        "state", "blockers", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "STATE\\_INVALID\\_PRIORITY" in result.output
    assert "## Warnings" in result.output


def test_cli_state_list_output_file_orders_text_before_warnings(repo_with_docs, tmp_path):
    """state list --output keeps warnings after the main text artifact."""
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    _corrupt_priority_in_state(repo_with_docs)
    output_file = tmp_path / "state-list.txt"

    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs), "--output", str(output_file),
    ])

    assert result.exit_code == 0
    artifact = output_file.read_text(encoding="utf-8")
    assert artifact.index("No entries found") < artifact.index("Warning (STATE_INVALID_PRIORITY)")


def test_cli_state_next_output_file_orders_text_before_warnings(repo_with_docs, tmp_path):
    """state next --output keeps warnings after the main text artifact."""
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    _corrupt_priority_in_state(repo_with_docs)
    output_file = tmp_path / "state-next.txt"

    result = runner.invoke(cli, [
        "state", "next", "--root", str(repo_with_docs), "--output", str(output_file),
    ])

    assert result.exit_code == 0
    artifact = output_file.read_text(encoding="utf-8")
    assert artifact.index("No ready items") < artifact.index("Warning (STATE_INVALID_PRIORITY)")


def test_cli_state_blockers_output_file_orders_text_before_warnings(repo_with_docs, tmp_path):
    """state blockers --output keeps warnings after the main text artifact."""
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--add-depends-on", "TEST-ADR-002",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    _corrupt_priority_in_state(repo_with_docs)
    output_file = tmp_path / "state-blockers.txt"

    result = runner.invoke(cli, [
        "state", "blockers", "--root", str(repo_with_docs), "--output", str(output_file),
    ])

    assert result.exit_code == 0
    artifact = output_file.read_text(encoding="utf-8")
    assert artifact.index("Summary:") < artifact.index("Warning (STATE_INVALID_PRIORITY)")


def test_cli_state_set_md_escapes_assignee(repo_with_docs):
    """User-controlled fields in state set md output are escaped."""
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--assignee", "**bold**",
        "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "\\*\\*bold\\*\\*" in result.output


def test_cli_state_list_tolerates_broken_repo_layout(repo_with_docs):
    """state list succeeds with canonical fallback vocabularies when layout fails."""
    from unittest import mock

    runner = runner_no_mixed_stderr()
    with mock.patch(
        "meminit.core.services.repo_config.load_repo_layout",
        side_effect=ValueError("broken config"),
    ):
        result = runner.invoke(cli, [
            "state", "list", "--root", str(repo_with_docs), "--format", "json",
        ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert "Not Started" in data["data"]["valid_impl_states"]


def test_cli_state_set_clears_notes_with_empty_string(repo_with_docs):
    """--notes '' clears an existing notes field."""
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--notes", "some notes",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--notes", "",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert data["data"]["notes"] == ""


def test_cli_state_set_md_renders_warnings(repo_with_docs):
    """state set --format md surfaces warnings (e.g. undefined dependency)."""
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--add-depends-on", "TEST-ADR-999",
        "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "## Warnings" in result.output
    assert "STATE_UNDEFINED_DEPENDENCY" in result.output or "STATE\\_UNDEFINED\\_DEPENDENCY" in result.output


def test_cli_state_set_console_renders_warnings(repo_with_docs):
    """state set default (console) format surfaces warnings."""
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--add-depends-on", "TEST-ADR-999",
        "--root", str(repo_with_docs),
    ])
    assert result.exit_code == 0
    assert "Warning" in result.output
    assert "STATE_UNDEFINED_DEPENDENCY" in result.output


def test_cli_state_list_json_puts_advisories_in_envelope(repo_with_docs):
    """state list --format json exposes advisories at the envelope level."""
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Done",
        "--add-depends-on", "TEST-ADR-002",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-002", "--impl-state", "In Progress",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    advice_codes = [a["code"] for a in data["advice"]]
    assert "STATE_DEPENDENCY_STATUS_CONFLICT" in advice_codes
    assert "advice" not in data["data"]


def test_cli_state_list_md_renders_advisories(repo_with_docs):
    """state list --format md surfaces advisories (e.g. status conflict)."""
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Done",
        "--add-depends-on", "TEST-ADR-002",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-002", "--impl-state", "In Progress",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs), "--format", "md",
    ])
    assert result.exit_code == 0
    assert "## Advisories" in result.output
    assert "STATE_DEPENDENCY_STATUS_CONFLICT" in result.output or "STATE\\_DEPENDENCY\\_STATUS\\_CONFLICT" in result.output


def test_cli_state_list_console_renders_advisories(repo_with_docs):
    """state list default (console) format surfaces advisories."""
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Done",
        "--add-depends-on", "TEST-ADR-002",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-002", "--impl-state", "In Progress",
        "--root", str(repo_with_docs), "--format", "json",
    ])
    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs),
    ])
    assert result.exit_code == 0
    assert "Advisory" in result.output


def test_cli_state_list_accepts_initialized_top_level_templates_v2_config(tmp_path):
    """State commands accept the top-level Templates v2 config written by init."""
    gov_dir = tmp_path / "docs" / "00-governance"
    gov_dir.mkdir(parents=True)
    (gov_dir / "metadata.schema.json").write_text("{}")
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Test\n"
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "document_types:\n"
        "  ADR:\n"
        "    directory: adr\n"
        "    description: Architecture Decision Record\n",
        encoding="utf-8",
    )
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, [
        "state", "list", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    assert data["data"]["entries"] == []


def test_cli_state_list_summary_counts_respect_filters(repo_with_docs):
    """Summary counts (ready, blocked) should be scoped to the active filter."""
    runner = runner_no_mixed_stderr()
    # Entry 1: Ready, Assignee Alice
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-001", "--impl-state", "Not Started",
        "--assignee", "Alice", "--root", str(repo_with_docs),
    ])
    # Entry 2: Ready, Assignee Bob
    runner.invoke(cli, [
        "state", "set", "TEST-ADR-002", "--impl-state", "Not Started",
        "--assignee", "Bob", "--root", str(repo_with_docs),
    ])

    # Unfiltered: 2 ready
    result = runner.invoke(cli, [
        "state", "list", "--root", str(repo_with_docs), "--format", "json",
    ])
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["data"]["summary"]["ready"] == 2

    # Filtered by Bob: 1 ready (TEST-ADR-002 only)
    # BEFORE FIX: this returns ready=2 because counts are global
    result = runner.invoke(cli, [
        "state", "list", "--assignee", "Bob", "--root", str(repo_with_docs), "--format", "json",
    ])
    data = json.loads(result.output.strip().splitlines()[-1])
    assert len(data["data"]["entries"]) == 1
    assert data["data"]["entries"][0]["document_id"] == "TEST-ADR-002"
    assert data["data"]["summary"]["ready"] == 1
