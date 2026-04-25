
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

def test_cli_state_clear_json(repo_with_docs):
    runner = runner_no_mixed_stderr()
    runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--impl-state", "Done", "--root", str(repo_with_docs)])
    
    result = runner.invoke(cli, ["state", "set", "TEST-ADR-001", "--clear", "--root", str(repo_with_docs), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["data"]["action"] == "clear"
    
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
    assert data["data"]["entry"]["priority"] == "P0"


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
    assert data["data"]["entry"]["assignee"] == "agent:codex"
    assert data["data"]["entry"]["next_action"] == "Implement schema"


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
    assert "TEST-ADR-002" in data["data"]["entry"]["depends_on"]
    assert "TEST-ADR-003" in data["data"]["entry"]["depends_on"]


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
        ["--blocked-by", "A", "--add-blocked-by", "B"],
        ["--blocked-by", "A", "--clear-blocked-by"],
        ["--add-blocked-by", "B", "--clear-blocked-by"],
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
