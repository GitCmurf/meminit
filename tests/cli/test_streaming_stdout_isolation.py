from __future__ import annotations

import inspect

from click.testing import CliRunner

from meminit.cli.main import cli
from tests.cli.streaming_helpers import records


def _runner() -> CliRunner:
    kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        kwargs["mix_stderr"] = False
    return CliRunner(**kwargs)


def test_streaming_commands_emit_only_json_lines_on_stdout(
    initialized_repo, monkeypatch, stream_schema_validator
):
    monkeypatch.setenv("MEMINIT_LOG_FILE", "-")
    commands = [
        ["index", "--root", str(initialized_repo), "--format", "ndjson"],
        ["scan", "--root", str(initialized_repo), "--format", "ndjson"],
        ["context", "--root", str(initialized_repo), "--deep", "--format", "ndjson"],
    ]

    for command in commands:
        result = _runner().invoke(cli, command)
        assert result.exit_code == 0, result.output
        parsed = records(result.output)
        assert parsed
        assert parsed[0]["record_type"] == "header"
        assert parsed[-1]["record_type"] == "summary"
        assert all(
            not list(stream_schema_validator.iter_errors(record))
            for record in parsed
        )
