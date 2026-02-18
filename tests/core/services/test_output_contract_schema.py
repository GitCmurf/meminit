import json
from pathlib import Path
import inspect

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
        Path(__file__).resolve().parents[3]
        / "docs"
        / "20-specs"
        / "agent-output.schema.v2.json"
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
