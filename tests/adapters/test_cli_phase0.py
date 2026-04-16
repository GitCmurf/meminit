import inspect
import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from jsonschema import Draft7Validator

from meminit.cli.main import cli


def runner_no_mixed_stderr() -> CliRunner:
    kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        kwargs["mix_stderr"] = False
    return CliRunner(**kwargs)


@pytest.fixture(scope="module")
def agent_output_schema():
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "20-specs"
        / "agent-output.schema.v3.json"
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _write_initialized_repo(root: Path) -> None:
    (root / "docs" / "00-governance").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "01-indices").mkdir(parents=True, exist_ok=True)

    (root / "docops.config.yaml").write_text(
        """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
document_types:
  ADR:
    directory: 45-adr
""",
        encoding="utf-8",
    )

    (root / "docs" / "00-governance" / "metadata.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "required": [
                    "document_id",
                    "type",
                    "title",
                    "status",
                    "version",
                    "last_updated",
                    "owner",
                    "docops_version",
                ],
                "properties": {
                    "document_id": {"type": "string"},
                    "type": {"type": "string"},
                    "title": {"type": "string"},
                    "status": {"type": "string"},
                    "version": {"type": "string"},
                    "last_updated": {"type": "string", "format": "date"},
                    "owner": {"type": "string"},
                    "docops_version": {"type": "string"},
                },
            }
        ),
        encoding="utf-8",
    )

    (root / "docs" / "45-adr" / "adr-001-existing.md").write_text(
        """---
document_id: TEST-ADR-001
type: ADR
title: Existing ADR
status: Draft
version: "0.1"
last_updated: 2026-04-14
owner: TestOwner
docops_version: "2.0"
---
# Existing ADR
""",
        encoding="utf-8",
    )


def _write_legacy_templates_repo(root: Path) -> None:
    (root / "docs" / "00-governance").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)

    (root / "docops.config.yaml").write_text(
        """project_name: LegacyTemplates
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
type_directories:
  ADR: 45-adr
""",
        encoding="utf-8",
    )

    (root / "docs" / "00-governance" / "metadata.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}}),
        encoding="utf-8",
    )


def _stdout_text(result) -> str:
    if hasattr(result, "stdout"):
        return result.stdout
    return result.output


def _stderr_text(result) -> str:
    if hasattr(result, "stderr"):
        return result.stderr
    return ""


def _parse_json_stdout(result, schema):
    lines = [line for line in _stdout_text(result).splitlines() if line.strip()]
    assert len(lines) == 1, result.output
    payload = json.loads(lines[0])
    errors = sorted(Draft7Validator(schema).iter_errors(payload), key=str)
    assert not errors
    return payload


def _run_success_json(runner: CliRunner, args: list[str], schema: dict):
    result = runner.invoke(cli, args, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return _parse_json_stdout(result, schema)


def _prepare_index(runner: CliRunner, root: Path, schema: dict) -> None:
    _run_success_json(runner, ["index", "--root", str(root), "--format", "json"], schema)


def _prepare_state(runner: CliRunner, root: Path, schema: dict) -> None:
    _run_success_json(
        runner,
        [
            "state",
            "set",
            "TEST-ADR-001",
            "--impl-state",
            "In Progress",
            "--root",
            str(root),
            "--format",
            "json",
        ],
        schema,
    )


def _case_check(root: Path) -> list[str]:
    return ["check", "--root", str(root), "--format", "json"]


def _case_init(root: Path) -> list[str]:
    return ["init", "--root", str(root), "--format", "json"]


def _case_context(root: Path) -> list[str]:
    return ["context", "--root", str(root), "--format", "json"]


def _case_doctor(root: Path) -> list[str]:
    return ["doctor", "--root", str(root), "--format", "json"]


def _case_fix(root: Path) -> list[str]:
    return ["fix", "--root", str(root), "--dry-run", "--format", "json"]


def _case_scan(root: Path) -> list[str]:
    return ["scan", "--root", str(root), "--format", "json"]


def _case_install_precommit(root: Path) -> list[str]:
    return ["install-precommit", "--root", str(root), "--format", "json"]


def _case_index(root: Path) -> list[str]:
    return ["index", "--root", str(root), "--format", "json"]


def _case_resolve(root: Path) -> list[str]:
    return ["resolve", "TEST-ADR-001", "--root", str(root), "--format", "json"]


def _case_identify(root: Path) -> list[str]:
    return [
        "identify",
        "docs/45-adr/adr-001-existing.md",
        "--root",
        str(root),
        "--format",
        "json",
    ]


def _case_link(root: Path) -> list[str]:
    return ["link", "TEST-ADR-001", "--root", str(root), "--format", "json"]


def _case_migrate_ids(root: Path) -> list[str]:
    return ["migrate-ids", "--root", str(root), "--dry-run", "--format", "json"]


def _case_migrate_templates(root: Path) -> list[str]:
    return [
        "migrate-templates",
        "--root",
        str(root),
        "--dry-run",
        "--format",
        "json",
    ]


def _case_new(root: Path) -> list[str]:
    return [
        "new",
        "ADR",
        "Matrix ADR",
        "--root",
        str(root),
        "--dry-run",
        "--format",
        "json",
    ]


def _case_adr_new(root: Path) -> list[str]:
    return ["adr", "new", "Matrix ADR Alias", "--root", str(root), "--format", "json"]


def _case_org_install(_root: Path) -> list[str]:
    return ["org", "install", "--profile", "default", "--dry-run", "--format", "json"]


def _case_org_vendor(root: Path) -> list[str]:
    return ["org", "vendor", "--root", str(root), "--profile", "default", "--dry-run", "--format", "json"]


def _case_org_status(root: Path) -> list[str]:
    return ["org", "status", "--root", str(root), "--profile", "default", "--format", "json"]


def _case_state_set(root: Path) -> list[str]:
    return [
        "state",
        "set",
        "TEST-ADR-001",
        "--impl-state",
        "Done",
        "--root",
        str(root),
        "--format",
        "json",
    ]


def _case_state_get(root: Path) -> list[str]:
    return ["state", "get", "TEST-ADR-001", "--root", str(root), "--format", "json"]


def _case_state_list(root: Path) -> list[str]:
    return ["state", "list", "--root", str(root), "--format", "json"]


COMMAND_CASES = [
    ("init", "init", "empty", _case_init, None),
    ("check", "check", "initialized", _case_check, None),
    ("context", "context", "initialized", _case_context, None),
    ("doctor", "doctor", "initialized", _case_doctor, None),
    ("fix", "fix", "initialized", _case_fix, None),
    ("scan", "scan", "initialized", _case_scan, None),
    ("install-precommit", "install-precommit", "initialized", _case_install_precommit, None),
    ("index", "index", "initialized", _case_index, None),
    ("resolve", "resolve", "initialized", _case_resolve, _prepare_index),
    ("identify", "identify", "initialized", _case_identify, _prepare_index),
    ("link", "link", "initialized", _case_link, _prepare_index),
    ("migrate-ids", "migrate-ids", "initialized", _case_migrate_ids, None),
    ("migrate-templates", "migrate-templates", "legacy", _case_migrate_templates, None),
    ("new", "new", "initialized", _case_new, None),
    ("adr new", "adr new", "initialized", _case_adr_new, None),
    ("org install", "org install", "empty", _case_org_install, None),
    ("org vendor", "org vendor", "initialized", _case_org_vendor, None),
    ("org status", "org status", "initialized", _case_org_status, None),
    ("state set", "state set", "initialized", _case_state_set, None),
    ("state get", "state get", "initialized", _case_state_get, _prepare_state),
    ("state list", "state list", "initialized", _case_state_list, _prepare_state),
]


@pytest.mark.parametrize(
    "case_name,expected_command,repo_kind,args_fn,prepare_fn",
    COMMAND_CASES,
    ids=[case[0] for case in COMMAND_CASES],
)
def test_cli_json_command_matrix_emits_schema_valid_envelopes(
    tmp_path,
    agent_output_schema,
    case_name,
    expected_command,
    repo_kind,
    args_fn,
    prepare_fn,
):
    root = tmp_path / case_name.replace(" ", "-")
    root.mkdir(parents=True, exist_ok=True)

    if repo_kind == "initialized":
        _write_initialized_repo(root)
    elif repo_kind == "legacy":
        _write_legacy_templates_repo(root)

    runner = runner_no_mixed_stderr()
    if prepare_fn is not None:
        prepare_fn(runner, root, agent_output_schema)

    payload = _run_success_json(runner, args_fn(root), agent_output_schema)
    assert payload["command"] == expected_command


@pytest.mark.parametrize(
    "args",
    [
        ["--verbose", "context"],
        ["--verbose", "index"],
    ],
    ids=["context", "index"],
)
def test_verbose_json_keeps_stdout_machine_safe_for_representative_commands(
    tmp_path,
    agent_output_schema,
    args,
):
    _write_initialized_repo(tmp_path)
    runner = runner_no_mixed_stderr()

    result = runner.invoke(
        cli,
        [*args, "--root", str(tmp_path), "--format", "json"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = _parse_json_stdout(result, agent_output_schema)
    assert payload["success"] is True
    assert "debug.config_loaded" in _stderr_text(result)
    assert "debug.config_loaded" not in _stdout_text(result)
