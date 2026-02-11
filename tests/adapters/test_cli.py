import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from meminit.cli.main import cli
from meminit.core.domain.entities import Severity, Violation


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "meminit" in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_clean(mock_use_case):
    # Setup Mock
    instance = mock_use_case.return_value
    instance.execute.return_value = []  # No violations

    runner = CliRunner()
    result = runner.invoke(cli, ["check"])

    assert result.exit_code == 0
    assert "No violations found" in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_violations_text(mock_use_case):
    # Setup Mock
    instance = mock_use_case.return_value
    instance.execute.return_value = [
        Violation("docs/bad.md", 1, "TEST_RULE", "Bad Thing", Severity.ERROR)
    ]

    runner = CliRunner()
    result = runner.invoke(cli, ["check"])

    assert result.exit_code == 1
    assert "docs/bad.md" in result.output
    assert "TEST_RULE" in result.output
    # Check that severity is printed correctly (not as Enum repr)
    assert "ERROR" in result.output or "error" in result.output
    assert "Severity.ERROR" not in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_violations_json(mock_use_case):
    # Setup Mock
    instance = mock_use_case.return_value
    instance.execute.return_value = [
        Violation("docs/bad.md", 1, "TEST_RULE", "Bad Thing", Severity.ERROR)
    ]

    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--format", "json"])

    assert result.exit_code == 1
    # Should be parseable JSON
    try:
        data = json.loads(result.output)
    except json.JSONDecodeError:
        pytest.fail(f"Output is not valid JSON: {result.output}")

    assert data["status"] == "failed"
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

    assert result.exit_code == 1
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
    assert data["status"] == "error"
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
