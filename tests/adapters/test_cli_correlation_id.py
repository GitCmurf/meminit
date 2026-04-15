"""Tests for --correlation-id flag across CLI commands."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from meminit.cli.main import cli


@pytest.fixture
def initialized_repo(tmp_path):
    """Create a minimal initialized repo for CLI tests."""
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "00-governance").mkdir()
    return tmp_path


def test_correlation_id_echoed_in_json_output(initialized_repo):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["context", "--format", "json", "--root", str(initialized_repo),
         "--correlation-id", "trace-abc-42"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output.strip())
    assert data["correlation_id"] == "trace-abc-42"


def test_correlation_id_omitted_when_not_provided(initialized_repo):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["context", "--format", "json", "--root", str(initialized_repo)],
    )
    assert result.exit_code == 0
    data = json.loads(result.output.strip())
    assert "correlation_id" not in data


def test_correlation_id_from_env_var(initialized_repo):
    runner = CliRunner(env={"MEMINIT_CORRELATION_ID": "env-trace-99"})
    result = runner.invoke(
        cli,
        ["context", "--format", "json", "--root", str(initialized_repo)],
    )
    assert result.exit_code == 0
    data = json.loads(result.output.strip())
    assert data["correlation_id"] == "env-trace-99"


def test_correlation_id_cli_flag_overrides_env_var(initialized_repo):
    runner = CliRunner(env={"MEMINIT_CORRELATION_ID": "env-trace-99"})
    result = runner.invoke(
        cli,
        ["context", "--format", "json", "--root", str(initialized_repo),
         "--correlation-id", "cli-trace-77"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output.strip())
    assert data["correlation_id"] == "cli-trace-77"


def test_correlation_id_whitespace_rejected_as_json_envelope(initialized_repo):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["context", "--format", "json", "--root", str(initialized_repo),
         "--correlation-id", "has space"],
    )
    assert result.exit_code != 0
    data = json.loads(result.output.strip().splitlines()[0])
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_FLAG_COMBINATION"
    assert "whitespace" in data["error"]["message"]


def test_correlation_id_too_long_rejected_as_json_envelope(initialized_repo):
    runner = CliRunner()
    long_cid = "a" * 129
    result = runner.invoke(
        cli,
        ["context", "--format", "json", "--root", str(initialized_repo),
         "--correlation-id", long_cid],
    )
    assert result.exit_code != 0
    data = json.loads(result.output.strip().splitlines()[0])
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_FLAG_COMBINATION"
    assert "128" in data["error"]["message"]


def test_correlation_id_appears_after_run_id_in_key_order(initialized_repo):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["context", "--format", "json", "--root", str(initialized_repo),
         "--correlation-id", "order-test"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output.strip())
    keys = list(data.keys())
    assert keys.index("correlation_id") == keys.index("run_id") + 1


def test_correlation_id_echoed_in_error_envelope(initialized_repo):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["context", "--format", "json", "--root", str(initialized_repo) + "/nonexistent",
         "--correlation-id", "err-trace-1"],
    )
    assert result.exit_code != 0
    data = json.loads(result.output.strip())
    assert data["correlation_id"] == "err-trace-1"
    assert data["success"] is False
