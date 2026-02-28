import inspect
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from meminit.cli.main import cli
from meminit.core.domain.entities import CheckResult, NewDocumentResult
from meminit.core.services.error_codes import ErrorCode, MeminitError


def runner_no_mixed_stderr() -> CliRunner:
    kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        kwargs["mix_stderr"] = False
    return CliRunner(**kwargs)


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "meminit" in result.output


def test_cli_no_color_sets_env(tmp_path, monkeypatch):
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )
    # Ensure variables are cleared before and restored after the test
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("RICH_NO_COLOR", raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["--no-color", "context", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert os.environ.get("NO_COLOR") == "1"
    assert os.environ.get("RICH_NO_COLOR") == "1"


def test_cli_verbose_sets_debug_env(tmp_path, monkeypatch):
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )
    # Ensure variable is cleared before and restored after the test
    monkeypatch.delenv("MEMINIT_DEBUG", raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["--verbose", "context", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert os.environ.get("MEMINIT_DEBUG") == "1"


def test_cli_init_json_outputs_created_and_skipped_paths(tmp_path):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, ["init", "--root", str(tmp_path), "--format", "json"])

    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["success"] is True
    payload = data["data"]
    assert "created_paths" in payload
    assert "skipped_paths" in payload
    assert "docops.config.yaml" in payload["created_paths"]
    assert "AGENTS.md" in payload["created_paths"]


def test_cli_init_md_outputs_created_and_skipped_paths(tmp_path):
    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, ["init", "--root", str(tmp_path), "--format", "md"])

    assert result.exit_code == 0
    assert "# Meminit Init" in result.output
    assert "Created Paths" in result.output
    assert "docops.config.yaml" in result.output
    assert "AGENTS.md" in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_clean(mock_use_case):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=True,
        files_checked=0,
        files_passed=0,
        files_failed=0,
        violations=[],
        warnings=[],
        checked_paths=[],
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check"])

    assert result.exit_code == 0
    assert "No violations found" in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_clean_quiet_is_silent(mock_use_case, tmp_path):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=True,
        files_checked=0,
        files_passed=0,
        files_failed=0,
        violations=[],
        warnings=[],
        checked_paths=[],
    )
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Test\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--quiet", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Success! No violations found." not in result.output
    assert "Meminit Compliance Check" not in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_violations_text(mock_use_case):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=False,
        files_checked=1,
        files_passed=0,
        files_failed=1,
        violations=[
            {
                "path": "docs/bad.md",
                "violations": [{"code": "TEST_RULE", "message": "Bad Thing", "line": 1}],
            }
        ],
        warnings=[],
        checked_paths=["docs/bad.md"],
        violations_count=1,
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check"])

    assert result.exit_code == 1
    assert "docs/bad.md" in result.output
    assert "TEST_RULE" in result.output
    assert "ERROR" in result.output or "error" in result.output
    assert "Severity.ERROR" not in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_violations_json(mock_use_case):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=False,
        files_checked=1,
        files_passed=0,
        files_failed=1,
        violations=[
            {
                "path": "docs/bad.md",
                "violations": [{"code": "TEST_RULE", "message": "Bad Thing", "line": 1}],
            }
        ],
        warnings=[],
        checked_paths=["docs/bad.md"],
        violations_count=1,
    )

    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, ["check", "--format", "json"])

    assert result.exit_code == 1
    try:
        data = json.loads(result.output.strip().splitlines()[-1])
    except json.JSONDecodeError:
        pytest.fail(f"Output is not valid JSON: {result.output}")

    assert data["success"] is False
    assert data["output_schema_version"] == "2.0"
    assert data["files_checked"] == 1
    assert data["violations_count"] == 1
    assert len(data["violations"]) == 1
    assert data["violations"][0]["path"] == "docs/bad.md"
    assert data["violations"][0]["violations"][0]["code"] == "TEST_RULE"


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_json_output_write_failure_returns_json_error(mock_use_case, tmp_path):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=True,
        files_checked=0,
        files_passed=0,
        files_failed=0,
        violations=[],
        warnings=[],
        checked_paths=[],
    )
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Test\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "outdir"
    output_dir.mkdir()

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        [
            "check",
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code == getattr(os, "EX_CANTCREAT", 73)
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["success"] is False
    assert payload["output_schema_version"] == "2.0"
    assert payload["error"]["code"] == ErrorCode.UNKNOWN_ERROR.value
    assert payload["error"]["details"]["output_path"] == str(output_dir)


def test_cli_new_text_output_invalid_root_writes_error_file(tmp_path):
    output_path = tmp_path / "new-error.txt"
    missing_root = tmp_path / "does-not-exist"

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        [
            "new",
            "ADR",
            "Bad Root",
            "--root",
            str(missing_root),
            "--format",
            "text",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == getattr(os, "EX_NOINPUT", 66)
    assert result.output == ""
    content = output_path.read_text(encoding="utf-8")
    assert "CONFIG_MISSING" in content
    assert "Path does not exist:" in content
    assert str(missing_root) in content


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_text_output_writes_file_and_not_stdout(mock_use_case, tmp_path):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=True,
        files_checked=0,
        files_passed=0,
        files_failed=0,
        violations=[],
        warnings=[],
        checked_paths=[],
    )
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Test\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "check-output.txt"

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        [
            "check",
            "--root",
            str(tmp_path),
            "--format",
            "text",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Meminit Compliance Check" not in result.output
    assert f"Scanning root: {tmp_path}" not in result.output
    assert "Success! No violations found." not in result.output
    content = output_path.read_text(encoding="utf-8")
    assert "Meminit Compliance Check" in content
    assert f"Scanning root: {tmp_path}" in content
    assert "Success! No violations found." in content


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_violations_md(mock_use_case):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=False,
        files_checked=1,
        files_passed=0,
        files_failed=1,
        violations=[
            {
                "path": "docs/bad.md",
                "violations": [{"code": "TEST_RULE", "message": "Bad Thing", "line": 1}],
            }
        ],
        warnings=[],
        checked_paths=["docs/bad.md"],
        violations_count=1,
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--format", "md"])

    assert result.exit_code == 1
    assert "# Meminit Compliance Check" in result.output
    assert "## Findings" in result.output
    assert "TEST_RULE" in result.output
    assert "docs/bad.md" in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_warnings_non_strict(mock_use_case):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=True,
        files_checked=1,
        files_passed=1,
        files_failed=0,
        violations=[],
        warnings=[
            {
                "path": "docs/warn.md",
                "warnings": [{"code": "WARN_RULE", "message": "Needs attention", "line": 0}],
            }
        ],
        checked_paths=["docs/warn.md"],
        warnings_count=1,
        files_with_warnings=1,
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check"])

    assert result.exit_code == 0
    assert "Compliance Warnings" in result.output
    assert "warning" in result.output.lower()


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_warnings_quiet_is_silent(mock_use_case, tmp_path):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=True,
        files_checked=1,
        files_passed=1,
        files_failed=0,
        violations=[],
        warnings=[
            {
                "path": "docs/warn.md",
                "warnings": [{"code": "WARN_RULE", "message": "Needs attention", "line": 0}],
            }
        ],
        checked_paths=["docs/warn.md"],
        warnings_count=1,
        files_with_warnings=1,
    )
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Test\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--quiet", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Compliance Warnings" not in result.output
    assert "WARN_RULE" not in result.output
    assert "Found 1 warning" not in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_quiet_outputs_failures_only(mock_use_case, tmp_path):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=False,
        files_checked=1,
        files_passed=0,
        files_failed=1,
        violations=[
            {
                "path": "docs/bad.md",
                "violations": [{"code": "ID_REGEX", "message": "Bad ID", "line": 3}],
            }
        ],
        warnings=[
            {
                "path": "docs/bad.md",
                "warnings": [{"code": "WARN_RULE", "message": "Needs attention", "line": 5}],
            }
        ],
        checked_paths=["docs/bad.md"],
        warnings_count=1,
        violations_count=1,
    )
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Test\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--quiet", "--root", str(tmp_path)])

    assert result.exit_code == 1
    assert "FAIL docs/bad.md" in result.output
    assert "ID_REGEX" in result.output
    assert "WARN_RULE" not in result.output


@patch("meminit.cli.main.CheckRepositoryUseCase")
def test_cli_check_warnings_strict(mock_use_case):
    instance = mock_use_case.return_value
    instance.execute_full_summary.return_value = CheckResult(
        success=False,
        files_checked=1,
        files_passed=0,
        files_failed=1,
        violations=[
            {
                "path": "docs/warn.md",
                "violations": [{"code": "WARN_RULE", "message": "Needs attention", "line": 0}],
            }
        ],
        warnings=[],
        checked_paths=["docs/warn.md"],
        violations_count=1,
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--strict"])

    assert result.exit_code == 1
    assert "Compliance Violations" in result.output


def test_cli_scan_invalid_root_json_contract(tmp_path):
    runner = CliRunner()
    missing = tmp_path / "does-not-exist"
    result = runner.invoke(cli, ["scan", "--format", "json", "--root", str(missing)])

    assert result.exit_code == getattr(os, "EX_NOINPUT", 66)
    data = json.loads(result.output)
    assert data["success"] is False
    assert data["error"]["code"] == "CONFIG_MISSING"
    assert data["output_schema_version"] == "2.0"


@patch("meminit.cli.main.InstallPrecommitUseCase")
def test_cli_install_precommit_md_output(mock_use_case, tmp_path):
    instance = mock_use_case.return_value
    report = MagicMock()
    report.status = "created"
    report.config_path = tmp_path / ".git" / "hooks" / "pre-commit"
    instance.execute.return_value = report

    runner = CliRunner()
    result = runner.invoke(cli, ["install-precommit", "--root", str(tmp_path), "--format", "md"])

    assert result.exit_code == 0
    assert "# Meminit Install Precommit" in result.output
    assert "Hook path" in result.output


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


def test_cli_context_json_output(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\n"
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "default_owner: TeamA\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["context", "--root", str(tmp_path), "--format", "json"])

    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["output_schema_version"] == "2.0"
    assert data["success"] is True
    assert data["data"]["project_name"] == "TestProject"
    assert data["data"]["default_owner"] == "TeamA"


def test_cli_context_deep_counts_documents(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\n"
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n",
        encoding="utf-8",
    )
    docs_dir = tmp_path / "docs" / "00-governance"
    docs_dir.mkdir(parents=True)
    (docs_dir / "a.md").write_text("# A\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["context", "--root", str(tmp_path), "--format", "json", "--deep"],
    )

    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data["data"]["deep_incomplete"] is False
    namespaces = data["data"]["namespaces"]
    default_ns = next(ns for ns in namespaces if ns.get("name") == "default")
    assert default_ns["document_count"] == 1


def test_cli_context_md_output(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["context", "--root", str(tmp_path), "--format", "md"])

    assert result.exit_code == 0
    assert "# Meminit Context" in result.output
    assert "- Project: `TestProject`" in result.output


@patch("meminit.cli.main.ContextRepositoryUseCase")
def test_cli_context_md_emits_warnings(mock_use_case, tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    instance = mock_use_case.return_value
    instance.execute.return_value = SimpleNamespace(
        data={
            "project_name": "TestProject",
            "config_path": "docops.config.yaml",
            "namespaces": [
                {"name": "default", "docs_root": "docs", "document_count": None}
            ],
        },
        warnings=[
            {
                "code": "DEEP_BUDGET_EXCEEDED",
                "message": "Deep scan performance budget (10s) exceeded; some namespace counts are incomplete.",
                "path": ".",
            }
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        cli, ["context", "--root", str(tmp_path), "--format", "md", "--deep"]
    )

    assert result.exit_code == 0
    assert "## Warnings" in result.output
    assert "DEEP_BUDGET_EXCEEDED" in result.output


@patch("meminit.cli.main.ContextRepositoryUseCase")
def test_cli_context_text_emits_warnings(mock_use_case, tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    instance = mock_use_case.return_value
    instance.execute.return_value = SimpleNamespace(
        data={
            "project_name": "TestProject",
            "config_path": "docops.config.yaml",
            "namespaces": [
                {"name": "default", "docs_root": "docs", "document_count": None}
            ],
        },
        warnings=[
            {
                "code": "DEEP_BUDGET_EXCEEDED",
                "message": "Deep scan performance budget (10s) exceeded; some namespace counts are incomplete.",
                "path": ".",
            }
        ],
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["context", "--root", str(tmp_path), "--deep"])

    assert result.exit_code == 0
    assert "Warnings:" in result.output
    assert "DEEP_BUDGET_EXCEEDED" in result.output


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

    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, ["index", "--root", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["output_schema_version"] == "2.0"
    assert data["data"]["document_count"] == 1


class TestCliNewJsonOutput:
    """Tests for F1: JSON output for meminit new"""

    @pytest.fixture
    def repo_for_new(self, tmp_path):
        (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
        (tmp_path / "docs" / "00-governance" / "templates" / "adr.md").write_text(
            "# ADR: {title}\n"
        )
        (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
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
    "docops_version": { "type": "string" },
    "area": { "type": "string" },
    "description": { "type": "string" },
    "keywords": { "type": "array", "items": { "type": "string" } },
    "related_ids": { "type": "array", "items": { "type": "string" } },
    "superseded_by": { "type": "string" }
  }
}
""".strip()
        )
        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
templates:
  adr: docs/00-governance/templates/adr.md
type_directories:
  ADR: 45-adr
"""
        )
        (tmp_path / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)
        return tmp_path

    def test_new_format_json_output(self, repo_for_new):
        runner_kwargs = {}
        if "mix_stderr" in inspect.signature(CliRunner).parameters:
            runner_kwargs["mix_stderr"] = False
        runner = CliRunner(**runner_kwargs)
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
        lines = result.output.strip().split("\n")
        json_line = lines[-1]
        data = json.loads(json_line)

        assert data["output_schema_version"] == "2.0"
        assert data["success"] is True
        assert "path" in data["data"]
        assert data["data"]["document_id"] == "TEST-ADR-001"
        assert data["data"]["type"] == "ADR"
        assert data["data"]["title"] == "Test Decision"
        assert data["data"]["status"] == "Draft"
        assert "owner" in data["data"]
        assert "keywords" in data["data"]
        assert "related_ids" in data["data"]

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
        lines = result.output.strip().split("\n")
        json_line = lines[-1]
        data = json.loads(json_line)

        assert data["success"] is True
        assert data["data"]["owner"] == "TestOwner"
        assert data["data"]["area"] == "Backend"
        assert data["data"]["description"] == "Test description"
        assert data["data"]["keywords"] == ["api", "test"]
        assert data["data"]["related_ids"] == ["TEST-PRD-001"]

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
        lines = result.output.strip().split("\n")
        json_line = lines[-1]
        data = json.loads(json_line)

        assert data["output_schema_version"] == "2.0"
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
        runner = runner_no_mixed_stderr()
        result = runner.invoke(
            cli,
            ["new", "--list-types", "--root", str(repo_with_types), "--format", "json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output.strip().splitlines()[-1])

        assert data["output_schema_version"] == "2.0"
        assert data["success"] is True
        assert "types" in data["data"]

        types_dict = {t["type"]: t["directory"] for t in data["data"]["types"]}
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
        (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
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
    "docops_version": { "type": "string" },
    "area": { "type": "string" },
    "description": { "type": "string" },
    "keywords": { "type": "array", "items": { "type": "string" } },
    "related_ids": { "type": "array", "items": { "type": "string" } },
    "superseded_by": { "type": "string" }
  }
}
""".strip()
        )
        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
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
        lines = result.output.strip().split("\n")
        json_line = lines[-1]
        data = json.loads(json_line)

        assert data["output_schema_version"] == "2.0"
        assert data["success"] is True
        assert data["data"]["dry_run"] is True
        assert "would_create" in data["data"]
        assert data["data"]["would_create"]["document_id"] == "TEST-ADR-001"

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
        lines = result.output.strip().split("\n")
        json_line = lines[-1]
        data = json.loads(json_line)

        assert data["data"]["owner"] == "TestOwner"
        assert data["data"]["area"] == "Backend"

    def test_new_dry_run_md_format_writes_output(self, repo_for_dry_run, tmp_path):
        output_path = tmp_path / "new-md-error.md"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "ADR",
                "MD Not Supported",
                "--root",
                str(repo_for_dry_run),
                "--format",
                "md",
                "--dry-run",
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0
        assert result.output == ""
        content = output_path.read_text(encoding="utf-8")
        assert "# Meminit New" in content
        assert "- Status: dry-run" in content
        assert "Would Create" in content


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
        runner = runner_no_mixed_stderr()
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
        data = json.loads(result.output.strip().splitlines()[-1])

        assert data["output_schema_version"] == "2.0"
        assert data["success"] is True
        assert data["files_checked"] == 1
        assert data["files_passed"] == 1
        assert data["files_failed"] == 0
        assert data["missing_paths_count"] == 0
        assert data["schema_failures_count"] == 0
        assert data["violations_count"] == 0
        assert data["warnings_count"] == 0

    def test_check_multiple_files_text_summary(self, repo_for_targeted_check):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "check",
                "docs/45-adr/*.md",
                "--root",
                str(repo_for_targeted_check),
            ],
        )

        assert result.exit_code == 1
        assert "Checking 2 existing files..." in result.output
        assert "OK docs/45-adr/adr-001-valid.md" in result.output
        assert "FAIL docs/45-adr/adr-002-invalid.md" in result.output
        assert "[ID_REGEX]" in result.output

    def test_check_multiple_files_json(self, repo_for_targeted_check):
        runner = runner_no_mixed_stderr()
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

        assert result.exit_code == 1
        data = json.loads(result.output.strip().splitlines()[-1])

        assert data["success"] is False
        assert data["files_checked"] == 2
        assert data["files_failed"] == 1
        assert data["violations_count"] >= 1
        assert len(data["violations"]) == 1

    def test_check_glob_pattern_json(self, repo_for_targeted_check):
        runner = runner_no_mixed_stderr()
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

        data = json.loads(result.output.strip().splitlines()[-1])
        assert data["files_checked"] == 2
        assert data["files_failed"] == 1
        assert data["missing_paths_count"] == 0

    def test_check_directory_target_json(self, repo_for_targeted_check):
        runner = runner_no_mixed_stderr()
        result = runner.invoke(
            cli,
            [
                "check",
                "docs/45-adr",
                "--root",
                str(repo_for_targeted_check),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 1
        data = json.loads(result.output.strip().splitlines()[-1])
        assert data["success"] is False
        assert data["files_checked"] == 2
        assert data["files_failed"] == 1
        assert data["missing_paths_count"] == 0

    def test_check_recursive_glob_json_honors_exclusions(self, repo_for_targeted_check):
        templates_dir = repo_for_targeted_check / "docs" / "00-governance" / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        (templates_dir / "bad-template.md").write_text(
            "# Template with no governed frontmatter\n",
            encoding="utf-8",
        )

        runner = runner_no_mixed_stderr()
        result = runner.invoke(
            cli,
            [
                "check",
                "docs/**/*.md",
                "--root",
                str(repo_for_targeted_check),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 1
        data = json.loads(result.output.strip().splitlines()[-1])
        assert data["files_checked"] == 2
        assert all(
            "docs/00-governance/templates" not in entry["path"] for entry in data["violations"]
        )
        assert all(
            "docs/00-governance/templates" not in warning["path"] for warning in data["warnings"]
        )

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

        assert result.exit_code != 0
        lines = result.output.strip().split("\n")
        json_line = lines[-1]
        data = json.loads(json_line)
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "FILE_NOT_FOUND"


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

    def test_invalid_flag_incompatibility_works_without_os_ex_constants(
        self, repo_for_flags, monkeypatch
    ):
        monkeypatch.delattr(os, "EX_USAGE", raising=False)
        monkeypatch.delattr(os, "EX_DATAERR", raising=False)
        monkeypatch.delattr(os, "EX_CANTCREAT", raising=False)

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

        assert result.exit_code == 64
        data = json.loads(result.output)
        assert data["error"]["code"] == "INVALID_FLAG_COMBINATION"


@patch("subprocess.run")
@patch("meminit.cli.main.NewDocumentUseCase")
def test_new_edit_parses_editor_command_with_args(
    mock_new_document_use_case,
    mock_subprocess_run,
    tmp_path,
    monkeypatch,
):
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Test\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )
    result_path = tmp_path / "docs" / "45-adr" / "adr-001-test.md"
    mock_new_document_use_case.return_value.execute_with_params.return_value = NewDocumentResult(
        success=True,
        path=result_path,
        document_id="TEST-ADR-001",
        doc_type="ADR",
        title="Test",
        status="Draft",
        version="0.1",
        owner="TestOwner",
        last_updated="2026-02-19",
        docops_version="2.0",
    )
    monkeypatch.setenv("EDITOR", "code --wait")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["new", "ADR", "Test", "--root", str(tmp_path), "--edit"],
    )

    assert result.exit_code == 0
    mock_subprocess_run.assert_called_once_with(
        ["code", "--wait", str(result_path)],
        check=False,
    )


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
        runner = runner_no_mixed_stderr()
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
        json_line = result.output.strip().splitlines()[-1]
        assert "\n" not in json_line

    def test_json_output_error_is_single_line(self, repo_for_json_check):
        """Per F1.2, JSON error output must be single-line."""
        runner = runner_no_mixed_stderr()
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

        json_line = result.output.strip().splitlines()[-1]
        assert "\n" not in json_line


class TestCliSinglePathNotFound:
    """Tests for F10.6: Single missing path should return error envelope."""

    @pytest.fixture
    def repo_for_single_path_check(self, tmp_path):
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

        return tmp_path

    def test_single_path_not_found_returns_error_envelope(self, repo_for_single_path_check):
        """F10.6: Single missing path should return error envelope."""
        runner = runner_no_mixed_stderr()
        result = runner.invoke(
            cli,
            [
                "--verbose",
                "check",
                "docs/45-adr/nonexistent.md",
                "--root",
                str(repo_for_single_path_check),
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        data = json.loads(result.output.strip().splitlines()[-1])
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "FILE_NOT_FOUND"

    def test_single_path_not_found_logs_failed_operation(self, repo_for_single_path_check):
        runner = runner_no_mixed_stderr()
        result = runner.invoke(
            cli,
            [
                "--verbose",
                "check",
                "docs/45-adr/nonexistent.md",
                "--root",
                str(repo_for_single_path_check),
                "--format",
                "json",
            ],
            env={"MEMINIT_LOG_FORMAT": "text"},
        )

        assert result.exit_code == getattr(os, "EX_NOINPUT", 66)
        stderr_output = result.stderr if getattr(result, "stderr", None) else ""
        if not stderr_output:
            stderr_output = result.output

        assert "check_targeted" in stderr_output
        assert "FAILED" in stderr_output
        assert "FILE_NOT_FOUND" in stderr_output


class TestCliAbsolutePathEscape:
    """Tests for F10.4: Absolute paths outside root should return PATH_ESCAPE."""

    @pytest.fixture
    def repo_for_path_escape_check(self, tmp_path):
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

        return tmp_path

    def test_absolute_path_outside_root_returns_path_escape(self, repo_for_path_escape_check):
        """F10.4: Absolute path outside root should return PATH_ESCAPE error."""
        runner = runner_no_mixed_stderr()
        result = runner.invoke(
            cli,
            [
                "check",
                "/nonexistent/path.md",
                "--root",
                str(repo_for_path_escape_check),
                "--format",
                "json",
            ],
        )

        assert result.exit_code != 0
        data = json.loads(result.output.strip().splitlines()[-1])
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "PATH_ESCAPE"


def test_config_missing_when_docs_exists_but_no_config(tmp_path):
    """F9.1: CONFIG_MISSING when docops.config.yaml is missing even if docs/ exists."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "test.md").write_text("# Test")

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "ADR", "Test", "--root", str(tmp_path), "--format", "json"])

    data = json.loads(result.output)
    assert data["success"] is False
    assert data["error"]["code"] == "CONFIG_MISSING"


def test_config_missing_when_config_path_is_directory(tmp_path):
    """F9.1: CONFIG_MISSING when docops.config.yaml exists but is not a file."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docops.config.yaml").mkdir()

    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--root", str(tmp_path), "--format", "json"])

    data = json.loads(result.output)
    assert data["success"] is False
    assert data["error"]["code"] == "CONFIG_MISSING"
    assert data["error"]["details"]["required"] == "regular file (not directory/symlink)"


def test_new_rejects_non_file_config_path(tmp_path):
    """F9.1: new must reject directory docops.config.yaml."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docops.config.yaml").mkdir()

    runner = CliRunner()
    result = runner.invoke(cli, ["new", "ADR", "Test", "--root", str(tmp_path), "--format", "json"])

    data = json.loads(result.output)
    assert data["success"] is False
    assert data["error"]["code"] == "CONFIG_MISSING"


def test_config_missing_when_config_path_is_symlink(tmp_path):
    """F9.1: CONFIG_MISSING when docops.config.yaml exists as a symlink."""
    if not hasattr(os, "symlink"):
        pytest.skip("Symlinks are not supported on this platform")

    target = tmp_path / "real-config.yaml"
    target.write_text(
        "project_name: Test\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    link_path = tmp_path / "docops.config.yaml"
    try:
        os.symlink(target, link_path)
    except OSError as exc:
        pytest.skip(f"Unable to create symlink on this platform: {exc}")

    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--root", str(tmp_path), "--format", "json"])

    data = json.loads(result.output)
    assert data["success"] is False
    assert data["error"]["code"] == "CONFIG_MISSING"


def test_adr_new_requires_initialized_repo(tmp_path):
    (tmp_path / "docs").mkdir()

    runner = CliRunner()
    result = runner.invoke(cli, ["adr", "new", "Alias Test", "--root", str(tmp_path)])

    assert result.exit_code == getattr(os, "EX_NOINPUT", 66)
    assert "CONFIG_MISSING" in result.output


@patch("meminit.cli.main.DoctorRepositoryUseCase")
def test_cli_doctor_json_output(mock_use_case, tmp_path):
    issues = [
        SimpleNamespace(
            severity=SimpleNamespace(value="warning"),
            rule="DOCOPS_WARN",
            file="docs/a.md",
            line=1,
            message="Warning message",
        ),
        SimpleNamespace(
            severity=SimpleNamespace(value="error"),
            rule="DOCOPS_ERR",
            file="docs/b.md",
            line=2,
            message="Error message",
        ),
    ]
    mock_use_case.return_value.execute.return_value = issues

    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, ["doctor", "--root", str(tmp_path), "--format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["command"] == "doctor"
    assert payload["success"] is False
    assert len(payload["warnings"]) == 1
    assert len(payload["violations"]) == 1
    assert payload["warnings"][0]["code"] == "DOCOPS_WARN"
    assert payload["violations"][0]["code"] == "DOCOPS_ERR"


@patch("meminit.cli.main.DoctorRepositoryUseCase")
def test_cli_doctor_json_strict_warnings_fail(mock_use_case, tmp_path):
    mock_use_case.return_value.execute.return_value = [
        SimpleNamespace(
            severity=SimpleNamespace(value="warning"),
            rule="DOCOPS_WARN",
            file="docs/a.md",
            line=1,
            message="Warning message",
        )
    ]

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        ["doctor", "--root", str(tmp_path), "--format", "json", "--strict"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["command"] == "doctor"
    assert payload["success"] is False
    assert payload["data"]["status"] == "warn"
    assert len(payload["warnings"]) == 1
    assert payload["violations"] == []


@patch("meminit.cli.main.FixRepositoryUseCase")
def test_cli_fix_json_output(mock_use_case, tmp_path):
    report = SimpleNamespace(
        fixed_violations=[1, 2],
        remaining_violations=[
            SimpleNamespace(
                rule="SCHEMA_VALIDATION",
                message="Still broken",
                file="docs/bad.md",
                line=3,
                severity=SimpleNamespace(value="error"),
            )
        ],
    )
    mock_use_case.return_value.execute.return_value = report

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        ["fix", "--root", str(tmp_path), "--format", "json", "--dry-run"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["command"] == "fix"
    assert payload["success"] is False
    assert payload["data"]["fixed"] == 2
    assert payload["data"]["remaining"] == 1
    assert payload["data"]["dry_run"] is True
    assert payload["violations"][0]["code"] == "SCHEMA_VALIDATION"
    assert payload["violations"][0]["path"] == "docs/bad.md"


@patch("meminit.cli.main.MigrateIdsUseCase")
def test_cli_migrate_ids_json_output(mock_use_case, tmp_path):
    report = SimpleNamespace(as_dict=lambda: {"actions": [], "skipped_files": []})
    mock_use_case.return_value.execute.return_value = report

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        ["migrate-ids", "--root", str(tmp_path), "--format", "json", "--dry-run"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["command"] == "migrate-ids"
    assert payload["data"]["report"]["actions"] == []


@patch("meminit.cli.main.IdentifyDocumentUseCase")
def test_cli_identify_json_output(mock_use_case, tmp_path):
    mock_use_case.return_value.execute.return_value = SimpleNamespace(
        document_id="TEST-ADR-001",
        path="docs/45-adr/adr-001.md",
    )

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        ["identify", "docs/45-adr/adr-001.md", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["command"] == "identify"
    assert payload["data"]["document_id"] == "TEST-ADR-001"


@patch("meminit.cli.main.ResolveDocumentUseCase")
def test_cli_resolve_json_output(mock_use_case, tmp_path):
    mock_use_case.return_value.execute.return_value = SimpleNamespace(
        path="docs/45-adr/adr-001.md"
    )

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        ["resolve", "TEST-ADR-001", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["command"] == "resolve"
    assert payload["data"]["document_id"] == "TEST-ADR-001"


@patch("meminit.cli.main.ResolveDocumentUseCase")
def test_cli_link_json_output(mock_use_case, tmp_path):
    mock_use_case.return_value.execute.return_value = SimpleNamespace(
        path="docs/45-adr/adr-001.md"
    )

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        ["link", "TEST-ADR-001", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["command"] == "link"
    assert payload["data"]["document_id"] == "TEST-ADR-001"
    assert payload["data"]["link"].startswith("[TEST-ADR-001]")


@patch("meminit.cli.main.InstallOrgProfileUseCase")
def test_cli_org_install_json_output(mock_use_case):
    report = SimpleNamespace(as_dict=lambda: {"profile": "default"})
    mock_use_case.return_value.execute.return_value = report

    runner = runner_no_mixed_stderr()
    result = runner.invoke(cli, ["org", "install", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["command"] == "org install"
    assert payload["data"]["profile"] == "default"


@patch("meminit.cli.main.VendorOrgProfileUseCase")
def test_cli_org_vendor_json_output(mock_use_case, tmp_path):
    report = SimpleNamespace(as_dict=lambda: {"profile": "default"})
    mock_use_case.return_value.execute.return_value = report

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        ["org", "vendor", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["command"] == "org vendor"
    assert payload["data"]["profile"] == "default"


@patch("meminit.cli.main.OrgStatusUseCase")
def test_cli_org_status_json_output(mock_use_case, tmp_path):
    report = SimpleNamespace(as_dict=lambda: {"profile": "default", "status": "ok"})
    mock_use_case.return_value.execute.return_value = report

    runner = runner_no_mixed_stderr()
    result = runner.invoke(
        cli,
        ["org", "status", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["command"] == "org status"
    assert payload["data"]["status"] == "ok"


class TestCliVerboseJsonStderr:
    """Tests for F3.3: Verbose reasoning should go to stderr with --format json."""

    @pytest.fixture
    def repo_for_verbose_json(self, tmp_path):
        (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
        (tmp_path / "docs" / "00-governance" / "templates" / "adr.md").write_text(
            "# ADR: {title}\n"
        )
        (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
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
schema_path: docs/00-governance/metadata.schema.json
templates:
  adr: docs/00-governance/templates/adr.md
type_directories:
  ADR: 45-adr
"""
        )
        (tmp_path / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)
        return tmp_path

    def test_verbose_json_routes_reasoning_to_stderr(self, repo_for_verbose_json):
        """F3.3: Verbose reasoning should go to stderr with --format json."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                "ADR",
                "Test",
                "--root",
                str(repo_for_verbose_json),
                "--dry-run",
                "--verbose",
                "--format",
                "json",
            ],
            catch_exceptions=False,
        )

        lines = [line for line in result.output.splitlines() if line.strip()]
        json_index = next(i for i, line in enumerate(lines) if line.lstrip().startswith("{"))
        data = json.loads(lines[json_index])
        stderr_output = result.stderr if getattr(result, "stderr", None) else ""
        if not stderr_output:
            stderr_output = "\n".join(lines[:json_index] + lines[json_index + 1 :])
        assert "reasoning" not in data
        assert data["success"] is True

        assert "directory_selected" in stderr_output or "owner_resolved" in stderr_output
