from __future__ import annotations

from click.testing import CliRunner

from meminit.cli.main import cli
from tests.cli.streaming_helpers import normalize_stream


def test_streaming_outputs_are_deterministic_modulo_run_id(initialized_repo):
    commands = [
        ["index", "--root", str(initialized_repo), "--format", "ndjson"],
        ["scan", "--root", str(initialized_repo), "--format", "ndjson"],
        ["context", "--root", str(initialized_repo), "--deep", "--format", "ndjson"],
    ]
    runner = CliRunner()

    for command in commands:
        first = runner.invoke(cli, command)
        second = runner.invoke(cli, command)

        assert first.exit_code == 0, first.output
        assert second.exit_code == 0, second.output
        assert normalize_stream(first.output) == normalize_stream(second.output)
