"""CLI integration tests for protocol check and sync commands."""

import re
from pathlib import Path

from click.testing import CliRunner

from meminit.cli.main import cli


def _init_repo(tmp_path: Path) -> None:
    """Create a minimal initialized repo."""
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\nrepo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "00-governance").mkdir()
    (docs / "00-governance" / "metadata.schema.json").write_text(
        '{"$schema": "http://json-schema.org/draft-07/schema#"}',
        encoding="utf-8",
    )


class TestProtocolCheckCLI:
    def test_json_output_single_line(self, tmp_path):
        _init_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "check", "--root", str(tmp_path), "--format", "json"])
        assert result.exit_code != 2
        non_empty = [line for line in result.output.splitlines() if line.strip()]
        assert len(non_empty) == 1

    def test_text_output_not_empty(self, tmp_path):
        _init_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "check", "--root", str(tmp_path), "--format", "text"])
        assert result.exit_code != 2
        assert "Protocol" in result.output

    def test_md_output_is_markdown_table_only(self, tmp_path):
        _init_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "check", "--root", str(tmp_path), "--format", "md"])
        assert result.exit_code != 2
        non_empty = [line for line in result.output.splitlines() if line.strip()]
        # Markdown table: header row + separator + data rows
        assert non_empty[0].startswith("|")
        assert non_empty[1].startswith("|")
        # No extra text output beyond the table
        for line in non_empty:
            assert line.startswith("|"), f"Non-table line in md output: {line!r}"

    def test_missing_assets_exit_nonzero(self, tmp_path):
        _init_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "check", "--root", str(tmp_path), "--format", "json"])
        assert result.exit_code != 0


class TestProtocolSyncCLI:
    def test_json_output_single_line(self, tmp_path):
        _init_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "sync", "--root", str(tmp_path), "--format", "json"])
        assert result.exit_code != 2
        non_empty = [line for line in result.output.splitlines() if line.strip()]
        assert len(non_empty) == 1

    def test_text_output_not_empty(self, tmp_path):
        _init_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "sync", "--root", str(tmp_path), "--format", "text"])
        assert result.exit_code != 2
        assert "Protocol" in result.output

    def test_md_output_is_markdown_table_only(self, tmp_path):
        _init_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "sync", "--root", str(tmp_path), "--format", "md"])
        assert result.exit_code != 2
        non_empty = [line for line in result.output.splitlines() if line.strip()]
        assert non_empty[0].startswith("|")
        assert non_empty[1].startswith("|")
        for line in non_empty:
            assert line.startswith("|"), f"Non-table line in md output: {line!r}"

    def test_dry_run_missing_assets_exit_nonzero(self, tmp_path):
        _init_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "sync", "--root", str(tmp_path), "--format", "json"])
        # Dry-run with missing assets should be non-zero (fix 2)
        assert result.exit_code != 0


class TestProtocolCheckSyncCycle:
    """End-to-end check -> sync -> check cycle."""

    def test_sync_then_check_is_aligned(self, tmp_path):
        _init_repo(tmp_path)
        runner = CliRunner()

        # Check: should show drift
        r_check = runner.invoke(cli, ["protocol", "check", "--root", str(tmp_path), "--format", "json"])
        assert r_check.exit_code != 0

        # Sync: apply fixes
        r_sync = runner.invoke(cli, ["protocol", "sync", "--root", str(tmp_path), "--no-dry-run", "--format", "json"])
        assert r_sync.exit_code == 0

        # Check again: should be aligned
        r_check2 = runner.invoke(cli, ["protocol", "check", "--root", str(tmp_path), "--format", "json"])
        assert r_check2.exit_code == 0


class TestProtocolSyncViolationCodes:
    """Verify sync JSON emits correct violation codes from prior_status."""

    def _setup_asset(self, tmp_path: Path, asset_id: str, content: str) -> None:
        from meminit.core.services.protocol_assets import ProtocolAssetRegistry
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id(asset_id)
        assert asset is not None
        target = tmp_path / asset.target_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def _json(self, result) -> dict:
        import json
        lines = [line for line in result.output.splitlines() if line.strip()]
        return json.loads(lines[0])

    def test_missing_emits_missing_code(self, tmp_path):
        _init_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "sync", "--root", str(tmp_path), "--asset", "agents-md", "--format", "json"])
        data = self._json(result)
        codes = [v["code"] for v in data["violations"]]
        assert "PROTOCOL_ASSET_MISSING" in codes
        assert "PROTOCOL_ASSET_TAMPERED" not in codes

    def test_legacy_emits_legacy_code(self, tmp_path):
        _init_repo(tmp_path)
        self._setup_asset(tmp_path, "agents-md", "# Legacy content\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "sync", "--root", str(tmp_path), "--asset", "agents-md", "--format", "json"])
        data = self._json(result)
        codes = [v["code"] for v in data["violations"]]
        assert "PROTOCOL_ASSET_LEGACY" in codes

    def test_unparseable_emits_unparseable_code(self, tmp_path):
        _init_repo(tmp_path)
        from meminit.core.services.protocol_assets import ProtocolAssetRegistry
        asset = ProtocolAssetRegistry.default().get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        lines = canonical.split("\n")
        lines.insert(0, "Preamble\n")
        self._setup_asset(tmp_path, "agents-md", "\n".join(lines))
        runner = CliRunner()
        result = runner.invoke(cli, ["protocol", "sync", "--root", str(tmp_path), "--asset", "agents-md", "--force", "--format", "json"])
        data = self._json(result)
        codes = [v["code"] for v in data["violations"]]
        assert "PROTOCOL_ASSET_UNPARSEABLE" in codes
        assert "PROTOCOL_ASSET_TAMPERED" not in codes
