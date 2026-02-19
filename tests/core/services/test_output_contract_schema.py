import inspect
import json
from pathlib import Path

from click.testing import CliRunner
from jsonschema import Draft7Validator

from meminit.cli.main import cli


def test_check_json_output_conforms_to_agent_schema_v2(tmp_path):
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)

    (tmp_path / "docops.config.yaml").write_text(
        """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
type_directories:
  ADR: 45-adr
""",
        encoding="utf-8",
    )

    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
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

    (tmp_path / "docs" / "45-adr" / "adr-001-valid.md").write_text(
        """---
document_id: TEST-ADR-001
type: ADR
title: Valid
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: TestOwner
docops_version: 2.0
---
# Valid
""",
        encoding="utf-8",
    )

    schema_path = (
        Path(__file__).resolve().parents[3] / "docs" / "20-specs" / "agent-output.schema.v2.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    runner_kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        runner_kwargs["mix_stderr"] = False
    runner = CliRunner(**runner_kwargs)
    result = runner.invoke(
        cli,
        [
            "check",
            "docs/45-adr/adr-001-valid.md",
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    errors = sorted(Draft7Validator(schema).iter_errors(payload), key=str)
    assert not errors


def test_check_json_failure_without_error_conforms_to_agent_schema_v2(tmp_path):
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)

    (tmp_path / "docops.config.yaml").write_text(
        """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
type_directories:
  ADR: 45-adr
""",
        encoding="utf-8",
    )

    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
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

    (tmp_path / "docs" / "45-adr" / "adr-001-invalid.md").write_text(
        """---
document_id: BAD-ID
type: ADR
title: Invalid
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: TestOwner
docops_version: 2.0
---
# Invalid
""",
        encoding="utf-8",
    )

    schema_path = (
        Path(__file__).resolve().parents[3] / "docs" / "20-specs" / "agent-output.schema.v2.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    runner_kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        runner_kwargs["mix_stderr"] = False
    runner = CliRunner(**runner_kwargs)
    result = runner.invoke(
        cli,
        [
            "check",
            "docs/45-adr/adr-001-invalid.md",
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["success"] is False
    assert "error" not in payload
    assert "violations" in payload
    errors = sorted(Draft7Validator(schema).iter_errors(payload), key=str)
    assert not errors


def test_operational_error_envelope_conforms_to_agent_schema_v2(tmp_path):
    schema_path = (
        Path(__file__).resolve().parents[3] / "docs" / "20-specs" / "agent-output.schema.v2.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    runner_kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        runner_kwargs["mix_stderr"] = False
    runner = CliRunner(**runner_kwargs)
    result = runner.invoke(
        cli,
        [
            "check",
            "--root",
            str(tmp_path / "does-not-exist"),
            "--format",
            "json",
        ],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["success"] is False
    assert "error" in payload
    errors = sorted(Draft7Validator(schema).iter_errors(payload), key=str)
    assert not errors


def test_non_error_v2_payload_requires_check_counters():
    schema_path = (
        Path(__file__).resolve().parents[3] / "docs" / "20-specs" / "agent-output.schema.v2.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    payload = {"output_schema_version": "2.0", "success": True, "run_id": "test-run"}
    errors = sorted(Draft7Validator(schema).iter_errors(payload), key=str)
    assert errors
