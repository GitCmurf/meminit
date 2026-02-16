import json
import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from meminit.cli.main import cli
from meminit.core.domain.entities import CheckResult, Severity, Violation
from meminit.core.services.error_codes import ErrorCode, MeminitError


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "meminit" in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_clean(mock_use_case):
    instance = mock_use_case.return_value
    instance.execute.return_value = []

    runner = CliRunner()
    result = runner.invoke(cli, ["check"])

    assert result.exit_code == 0
    assert "No violations found" in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_violations_text(mock_use_case):
    instance = mock_use_case.return_value
    instance.execute.return_value = [
        Violation("docs/bad.md", 1, "TEST_RULE", "Bad Thing", Severity.ERROR)
    ]

    runner = CliRunner()
    result = runner.invoke(cli, ["check"])

    assert result.exit_code == 65
    assert "docs/bad.md" in result.output
    assert "TEST_RULE" in result.output
    assert "ERROR" in result.output or "error" in result.output
    assert "Severity.ERROR" not in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_violations_json(mock_use_case):
    instance = mock_use_case.return_value
    instance.execute.return_value = [
        Violation("docs/bad.md", 1, "TEST_RULE", "Bad Thing", Severity.ERROR)
    ]

    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--format", "json"])

    assert result.exit_code == 65
    try:
        data = json.loads(result.output)
    except json.JSONDecodeError:
        pytest.fail(f"Output is not valid JSON: {result.output}")

    assert data["success"] is False
    assert data["output_schema_version"] == "1.0"
    assert len(data["violations"]) == 1
    assert data["violations"][0]["severity"] == "error"
    assert data["violations"][0]["file"] == "docs/bad.md"


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_violations_md(mock_use_case):
    instance = mock_use_case.return_value
    instance.execute.return_value = [
        Violation("docs/bad.md", 1, "TEST_RULE", "Bad Thing", Severity.ERROR)
    ]

    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--format", "md"])

    assert result.exit_code == 65
    assert "# Meminit Compliance Check" in result.output
    assert "## Violations" in result.output
    assert "TEST_RULE" in result.output
    assert "docs/bad.md" in result.output


def test_cli_scan_invalid_root_json_contract(tmp_path):
    runner = CliRunner()
    missing = tmp_path / "does-not-exist"
    result = runner.invoke(cli, ["scan", "--format", "json", "--root", str(missing)])

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["success"] is False
    assert data["error"]["code"] == "CONFIG_MISSING"
    assert data["output_schema_version"] == "1.0"


@patch("meminit.cli.main.ScanRepositoryUseCase")
def test_cli_scan_text_does_not_crash_on_ambiguous_types(mock_use_case, tmp_path):
    # Regression: text scan previously crashed with UnboundLocalError when ambiguous types existed.
    instance = mock_use_case.return_value
    report = MagicMock()
    report.docs_root = "docs"
    report.markdown_count = 42
    report.governed_markdown_count = 84
    report.suggested_type_directories = {"ADR": "45-adr"}
    report.ambiguous_types = {"PLAN": ["05-planning", "planning"]}
    report.suggested_namespaces = [
        {"name": "core", "docs_root": "docs", "repo_prefix_suggestion": "EXAMPLE"}
    ]
    report.configured_namespaces = [
        {
            "namespace": "repo",
            "docs_root": "docs",
            "repo_prefix": "EXAMPLE",
            "docs_root_exists": True,
            "governed_markdown_count": 42,
        }
    ]
    report.overlapping_namespaces = []
    report.notes = ["hello", "world"]
    report.as_dict.return_value = {"docs_root": "docs"}
    instance.execute.return_value = report

    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "--format", "text", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Meminit Scan" in result.output
    assert "Ambiguous" in result.output


@patch("meminit.cli.main.ScanRepositoryUseCase")
def test_cli_scan_md_includes_ambiguous_types_and_namespaces(mock_use_case, tmp_path):
    instance = mock_use_case.return_value
    report = MagicMock()
    report.docs_root = "docs"
    report.markdown_count = 42
    report.governed_markdown_count = 84
    report.suggested_type_directories = {"ADR": "45-adr"}
    report.ambiguous_types = {"PLAN": ["05-planning", "planning"]}
    report.suggested_namespaces = [
        {"name": "core", "docs_root": "docs", "repo_prefix_suggestion": "EXAMPLE"}
    ]
    report.configured_namespaces = [
        {
            "namespace": "repo",
            "docs_root": "docs",
            "repo_prefix": "EXAMPLE",
            "docs_root_exists": True,
            "governed_markdown_count": 42,
        }
    ]
    report.overlapping_namespaces = [
        {
            "parent_namespace": "repo",
            "parent_docs_root": "docs",
            "child_namespace": "org",
            "child_docs_root": "docs/00-governance/org",
        }
    ]
    report.notes = ["note 1"]
    report.as_dict.return_value = {"docs_root": "docs"}
    instance.execute.return_value = report

    runner = CliRunner()
    result = runner.invoke(cli, ["scan", "--format", "md", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "# Meminit Scan" in result.output
    assert "## Configured Namespaces" in result.output
    assert "## Ambiguous Types" in result.output
    assert "## Suggested Namespaces" in result.output
    assert "## Overlapping Namespace Roots" in result.output


def test_cli_index_json_contract(tmp_path):
    docs_dir = tmp_path / "docs" / "45-adr"
    docs_dir.mkdir(parents=True)
    (docs_dir / "adr-001.md").write_text(
        "---\n"
        "document_id: EXAMPLE-ADR-001\n"
        "type: ADR\n"
        "title: Test\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-21\n"
        "owner: Test\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# ADR: Test\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["index", "--root", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert data["output_schema_version"] == "1.0"
    assert data["report"]["document_count"] == 1


class TestCliNewJsonOutput:
    """Tests for F1: JSON output for meminit new"""

    @pytest.fixture
    def repo_for_new(self, tmp_path):
        (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
        (tmp_path / "docs" / "00-governance" / "templates" / "adr.md").write_text(
            "# ADR: {title}\n"
        )
        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
templates:
  adr: docs/00-governance/templates/adr.md
type_directories:
  ADR: 45-adr
"""
        )
        (tmp_path / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)
        return tmp_path

    def test_new_format_json_output(self, repo_for_new):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "ADR",
                "Test Decision",
                "--root",
                str(repo_for_new),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["output_schema_version"] == "1.0"
        assert data["success"] is True
        assert "path" in data
        assert data["document_id"] == "TEST-ADR-001"
        assert data["type"] == "ADR"
        assert data["title"] == "Test Decision"
        assert data["status"] == "Draft"
        assert "owner" in data
        assert "keywords" in data
        assert "related_ids" in data

    def test_new_format_json_with_metadata(self, repo_for_new):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "ADR",
                "Enhanced Decision",
                "--root",
                str(repo_for_new),
                "--owner",
                "TestOwner",
                "--area",
                "Backend",
                "--description",
                "Test description",
                "--keywords",
                "api",
                "--keywords",
                "test",
                "--related-ids",
                "TEST-PRD-001",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["success"] is True
        assert data["owner"] == "TestOwner"
        assert data["area"] == "Backend"
        assert data["description"] == "Test description"
        assert data["keywords"] == ["api", "test"]
        assert data["related_ids"] == ["TEST-PRD-001"]

    def test_new_format_json_error(self, repo_for_new):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "UNKNOWN_TYPE",
                "Test",
                "--root",
                str(repo_for_new),
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        data = json.loads(result.output)

        assert data["output_schema_version"] == "1.0"
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "UNKNOWN_TYPE"


class TestCliNewListTypes:
    """Tests for F4: Type Discovery"""

    @pytest.fixture
    def repo_with_types(self, tmp_path):
        (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
type_directories:
  ADR: 45-adr
  PRD: 10-prd
  FDD: 50-fdd
"""
        )
        return tmp_path

    def test_new_list_types_text(self, repo_with_types):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["new", "--list-types", "--root", str(repo_with_types)],
        )

        assert result.exit_code == 0
        assert "ADR" in result.output
        assert "PRD" in result.output
        assert "FDD" in result.output

    def test_new_list_types_json(self, repo_with_types):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["new", "--list-types", "--root", str(repo_with_types), "--format", "json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["output_schema_version"] == "1.0"
        assert data["success"] is True
        assert "types" in data

        types_dict = {t["type"]: t["directory"] for t in data["types"]}
        assert "ADR" in types_dict
        assert "PRD" in types_dict
        assert "FDD" in types_dict

    def test_list_types_with_type_arg_errors(self, repo_with_types):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["new", "--list-types", "ADR", "Title", "--root", str(repo_with_types)],
        )

        assert result.exit_code != 0


class TestCliNewDryRun:
    """Tests for F3: Dry-Run Mode"""

    @pytest.fixture
    def repo_for_dry_run(self, tmp_path):
        (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
        (tmp_path / "docs" / "00-governance" / "templates" / "adr.md").write_text(
            "# ADR: {title}\n"
        )
        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
templates:
  adr: docs/00-governance/templates/adr.md
type_directories:
  ADR: 45-adr
"""
        )
        (tmp_path / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)
        return tmp_path

    def test_new_dry_run_no_file_created(self, repo_for_dry_run):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "ADR",
                "Dry Run Test",
                "--root",
                str(repo_for_dry_run),
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Would create" in result.output

        doc_path = repo_for_dry_run / "docs" / "45-adr" / "adr-001-dry-run-test.md"
        assert not doc_path.exists()

    def test_new_dry_run_json_output(self, repo_for_dry_run):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "ADR",
                "Dry Run JSON",
                "--root",
                str(repo_for_dry_run),
                "--dry-run",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["output_schema_version"] == "1.0"
        assert data["success"] is True
        assert data["dry_run"] is True
        assert "would_create" in data
        assert data["would_create"]["document_id"] == "TEST-ADR-001"

    def test_new_dry_run_with_metadata_preview(self, repo_for_dry_run):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "ADR",
                "Dry Run With Metadata",
                "--root",
                str(repo_for_dry_run),
                "--dry-run",
                "--format",
                "json",
                "--owner",
                "TestOwner",
                "--area",
                "Backend",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["owner"] == "TestOwner"
        assert data["area"] == "Backend"


class TestCliCheckTargeted:
    """Tests for F10: Targeted Check"""

    @pytest.fixture
    def repo_for_targeted_check(self, tmp_path):
        gov = tmp_path / "docs" / "00-governance"
        gov.mkdir(parents=True)
        (gov / "metadata.schema.json").write_text(
            """
{
  "type": "object",
  "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],
  "properties": {
    "document_id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": { "type": "string" },
    "version": { "type": "string" },
    "last_updated": { "type": "string" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" }
  }
}
""".strip()
        )

        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
type_directories:
  ADR: 45-adr
"""
        )

        adr_dir = tmp_path / "docs" / "45-adr"
        adr_dir.mkdir(parents=True)

        (adr_dir / "adr-001-valid.md").write_text(
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
"""
        )

        (adr_dir / "adr-002-invalid.md").write_text(
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
"""
        )

        return tmp_path

    def test_check_single_file_json(self, repo_for_targeted_check):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "check",
                "docs/45-adr/adr-001-valid.md",
                "--root",
                str(repo_for_targeted_check),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data["output_schema_version"] == "1.0"
        assert data["success"] is True
        assert data["files_checked"] == 1
        assert data["files_passed"] == 1
        assert data["files_failed"] == 0

    def test_check_multiple_files_json(self, repo_for_targeted_check):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "check",
                "docs/45-adr/adr-001-valid.md",
                "docs/45-adr/adr-002-invalid.md",
                "--root",
                str(repo_for_targeted_check),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 65
        data = json.loads(result.output)

        assert data["success"] is False
        assert data["files_checked"] == 2
        assert data["files_failed"] == 1
        assert len(data["violations"]) == 1

    def test_check_glob_pattern_json(self, repo_for_targeted_check):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "check",
                "docs/45-adr/*.md",
                "--root",
                str(repo_for_targeted_check),
                "--format",
                "json",
            ],
        )

        data = json.loads(result.output)
        assert data["files_checked"] == 2
        assert data["files_failed"] == 1

    def test_check_file_not_found_json(self, repo_for_targeted_check):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "check",
                "docs/45-adr/nonexistent.md",
                "--root",
                str(repo_for_targeted_check),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 65
        data = json.loads(result.output)
        assert data["success"] is False
        assert data["files_checked"] == 1
        assert data["files_failed"] == 1
        assert len(data["violations"]) == 1
        assert data["violations"][0]["violations"][0]["code"] == "FILE_NOT_FOUND"


class TestCliFlagIncompatibilities:
    """Tests for INVALID_FLAG_COMBINATION errors"""

    @pytest.fixture
    def repo_for_flags(self, tmp_path):
        (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
type_directories:
  ADR: 45-adr
"""
        )
        return tmp_path

    def test_interactive_and_json_incompatible(self, repo_for_flags):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "ADR",
                "Test",
                "--root",
                str(repo_for_flags),
                "--interactive",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["error"]["code"] == "INVALID_FLAG_COMBINATION"

    def test_edit_and_dry_run_incompatible(self, repo_for_flags):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "ADR",
                "Test",
                "--root",
                str(repo_for_flags),
                "--edit",
                "--dry-run",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["error"]["code"] == "INVALID_FLAG_COMBINATION"

    def test_edit_and_json_incompatible(self, repo_for_flags):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "ADR",
                "Test",
                "--root",
                str(repo_for_flags),
                "--edit",
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["error"]["code"] == "INVALID_FLAG_COMBINATION"

    def test_list_types_with_positional_args_incompatible(self, repo_for_flags):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "--list-types",
                "ADR",
                "Test",
                "--root",
                str(repo_for_flags),
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["error"]["code"] == "INVALID_FLAG_COMBINATION"


class TestCliJsonOutputFormat:
    """Tests for F1.2: JSON output must be single-line."""

    @pytest.fixture
    def repo_for_json_check(self, tmp_path):
        gov = tmp_path / "docs" / "00-governance"
        gov.mkdir(parents=True)
        (gov / "metadata.schema.json").write_text(
            """
{
  "type": "object",
  "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],
  "properties": {
    "document_id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": { "type": "string" },
    "version": { "type": "string" },
    "last_updated": { "type": "string" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" }
  }
}
""".strip()
        )

        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
type_directories:
  ADR: 45-adr
"""
        )

        adr_dir = tmp_path / "docs" / "45-adr"
        adr_dir.mkdir(parents=True)

        (adr_dir / "adr-001-valid.md").write_text(
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
"""
        )

        return tmp_path

    def test_json_output_is_single_line(self, repo_for_json_check):
        """Per F1.2, JSON output must be single-line."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "check",
                "docs/45-adr/adr-001-valid.md",
                "--root",
                str(repo_for_json_check),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert "\n" not in result.output.strip()

    def test_json_output_error_is_single_line(self, repo_for_json_check):
        """Per F1.2, JSON error output must be single-line."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "check",
                "docs/45-adr/nonexistent.md",
                "--root",
                str(repo_for_json_check),
                "--format",
                "json",
            ],
        )

        assert "\n" not in result.output.strip()
