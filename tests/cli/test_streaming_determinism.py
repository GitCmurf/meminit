from __future__ import annotations

import json

from click.testing import CliRunner

from meminit.cli.main import cli


def _stable_non_header_lines(output: str) -> list[str]:
    lines: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            lines.append(line)
            continue
        if record.get("record_type") != "header":
            lines.append(line)
    return lines


def test_streaming_outputs_are_deterministic_modulo_run_id(initialized_repo):
    commands = [
        ["index", "--root", str(initialized_repo), "--format", "ndjson"],
        ["scan", "--root", str(initialized_repo), "--format", "ndjson"],
        ["context", "--root", str(initialized_repo), "--deep", "--format", "ndjson"],
    ]
    runner = CliRunner()

    for command in commands:
        warmup = runner.invoke(cli, command)
        first = runner.invoke(cli, command)
        second = runner.invoke(cli, command)

        assert warmup.exit_code == 0, warmup.output
        assert first.exit_code == 0, first.output
        assert second.exit_code == 0, second.output
        assert _stable_non_header_lines(first.output) == _stable_non_header_lines(
            second.output
        )
