from pathlib import Path
import tempfile

from click.testing import CliRunner

from meminit.cli.main import cli
from tests.helpers import parse_json_envelope


def _runner():
    import inspect
    kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        kwargs["mix_stderr"] = False
    return CliRunner(**kwargs)


def test_runner():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        gov = tmp_path / "docs" / "00-governance"
        gov.mkdir(parents=True)
        (gov / "metadata.schema.json").write_text("{}")
        (tmp_path / "docops.config.yaml").write_text(
            "project_name: TestProject\nrepo_prefix: TEST\ndocops_version: '2.0'\n"
            "type_directories:\n  ADR: 45-adr\n"
        )
        (tmp_path / "docs" / "45-adr").mkdir(parents=True)

        runner = _runner()
        result = runner.invoke(
            cli,
            [
                "--verbose",
                "check",
                "docs/45-adr/nonexistent.md",
                "--root",
                str(tmp_path),
                "--format",
                "json",
            ],
            env={"MEMINIT_LOG_FORMAT": "text"},
            standalone_mode=False,
        )

        assert result.exit_code != 0
        data = parse_json_envelope(result.output)
        assert data["success"] is False
        assert data["command"] == "check"
        assert data["output_schema_version"] == "3.0"
        assert data["error"]["code"] == "FILE_NOT_FOUND"
        assert data["error"]["details"]["path"] == "docs/45-adr/nonexistent.md"
        assert "data" in data

        if hasattr(result, "stderr") and result.stderr:
            assert "output_schema_version" not in result.stderr


if __name__ == "__main__":
    test_runner()
