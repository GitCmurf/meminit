import json
import os
import pytest
from meminit.cli.main import cli
from tests.adapters.test_cli import TestCliSinglePathNotFound
from click.testing import CliRunner

def test_runner():
    class CustomRunner(CliRunner):
        def invoke(self, *args, **kwargs):
            kwargs["mix_stderr"] = False
            return super().invoke(*args, **kwargs)
            
    # Mock the fixture manually
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        gov = tmp_path / "docs" / "00-governance"
        gov.mkdir(parents=True)
        (gov / "metadata.schema.json").write_text("{}")
        (tmp_path / "docops.config.yaml").write_text(
            "project_name: TestProject\nrepo_prefix: TEST\ndocops_version: '2.0'\ntype_directories:\n  ADR: 45-adr\n"
        )
        (tmp_path / "docs" / "45-adr").mkdir(parents=True)
        
        runner = CustomRunner()
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
        print("EXIT CODE:", result.exit_code)
        print("STDOUT:", repr(result.stdout))
        print("STDERR:", repr(result.stderr))
        print("EXCEPTION:", result.exception)

if __name__ == "__main__":
    test_runner()
