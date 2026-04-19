"""Tests for the protocol check use case (PR 2)."""

from pathlib import Path

import pytest

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.protocol_assets import (
    PROTOCOL_ASSET_VERSION,
    DriftOutcome,
    ProtocolAsset,
    ProtocolAssetRegistry,
)
from meminit.core.use_cases.protocol_check import ProtocolChecker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _setup_config(tmp_path: Path, project_name: str = "TestProject", repo_prefix: str = "TEST") -> None:
    (tmp_path / "docops.config.yaml").write_text(
        f"project_name: {project_name}\nrepo_prefix: {repo_prefix}\n"
        f"docops_version: '2.0'\n",
        encoding="utf-8",
    )


def _write_asset(tmp_path: Path, asset: ProtocolAsset, content: str) -> None:
    target = tmp_path / asset.target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _write_asset_bytes(tmp_path: Path, asset: ProtocolAsset, content: bytes) -> None:
    target = tmp_path / asset.target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


# ---------------------------------------------------------------------------
# ProtocolChecker tests
# ---------------------------------------------------------------------------


class TestProtocolCheckerFreshRepo:
    def test_all_aligned_on_fresh_repo(self, tmp_path):
        """A freshly initialized repo with no assets should report all missing."""
        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute()
        assert report.success is False
        assert report.summary["total"] == 3
        assert report.summary["drifted"] == 3
        statuses = {a["status"] for a in report.assets}
        assert statuses == {"missing"}

    def test_aligned_with_canonical_assets(self, tmp_path):
        """When all assets match canonical render, all are aligned."""
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        for asset in registry.assets:
            content = asset.render(project_name="TestProject", repo_prefix="TEST")
            _write_asset(tmp_path, asset, content)

        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute()
        assert report.success is True
        assert report.summary["aligned"] == 3
        assert report.summary["drifted"] == 0
        assert report.summary["unparseable"] == 0

    def test_assets_sorted_by_id(self, tmp_path):
        """Assets in report are sorted lexicographically by ID."""
        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute()
        ids = [a["id"] for a in report.assets]
        assert ids == sorted(ids)


class TestProtocolCheckAssetFilter:
    def test_filter_single_asset(self, tmp_path):
        _setup_config(tmp_path)
        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["agents-md"])
        assert report.summary["total"] == 1
        assert report.assets[0]["id"] == "agents-md"

    def test_filter_multiple_assets(self, tmp_path):
        _setup_config(tmp_path)
        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["agents-md", "meminit-docops-skill"])
        assert report.summary["total"] == 2

    def test_duplicate_asset_ids_are_deduplicated(self, tmp_path):
        _setup_config(tmp_path)
        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["agents-md", "agents-md"])
        assert report.summary["total"] == 1
        assert [a["id"] for a in report.assets] == ["agents-md"]

    def test_unknown_asset_raises(self, tmp_path):
        _setup_config(tmp_path)
        checker = ProtocolChecker(str(tmp_path))
        with pytest.raises(Exception) as exc_info:
            checker.execute(asset_ids=["nonexistent"])
        assert "nonexistent" in str(exc_info.value)

    def test_unknown_asset_among_valid(self, tmp_path):
        _setup_config(tmp_path)
        checker = ProtocolChecker(str(tmp_path))
        with pytest.raises(Exception):
            checker.execute(asset_ids=["agents-md", "bogus"])


class TestProtocolCheckDriftOutcomes:
    def test_stale_generated_asset(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("meminit-docops-skill")
        assert asset is not None
        _write_asset(tmp_path, asset, "stale content\n")

        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["meminit-docops-skill"])
        assert report.success is False
        assert report.assets[0]["status"] == "stale"
        assert report.assets[0]["auto_fixable"] is True

    def test_legacy_mixed_asset(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        _write_asset(tmp_path, asset, "# Old AGENTS.md with no markers\n")

        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["agents-md"])
        assert report.assets[0]["status"] == "legacy"
        assert report.assets[0]["auto_fixable"] is True

    def test_tampered_mixed_asset(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        # Insert tampered content between markers
        lines = canonical.split("\n")
        lines.insert(2, "TAMPERED LINE")
        tampered = "\n".join(lines)
        _write_asset(tmp_path, asset, tampered)

        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["agents-md"])
        assert report.assets[0]["status"] == "tampered"
        assert report.assets[0]["auto_fixable"] is False

    def test_unparseable_asset(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        # Valid begin marker but no end marker
        content = "<!-- MEMINIT_PROTOCOL: begin id=agents-md version=1.0 sha256=" + "0" * 64 + " -->\nno end marker\n"
        _write_asset(tmp_path, asset, content)

        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["agents-md"])
        assert report.assets[0]["status"] == "unparseable"
        assert report.assets[0]["auto_fixable"] is False
        assert report.success is False

    def test_non_utf8_user_bytes_do_not_crash(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        payload = canonical.encode("utf-8") + b"## Custom\ninvalid:\xff\n"
        _write_asset_bytes(tmp_path, asset, payload)

        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["agents-md"])
        assert report.assets[0]["status"] == "aligned"
        assert report.success is True

    def test_symlink_asset_is_rejected(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        outside = tmp_path.parent / "outside-agents.md"
        outside.write_text("outside\n", encoding="utf-8")
        target = tmp_path / asset.target_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(outside)

        checker = ProtocolChecker(str(tmp_path))
        with pytest.raises(MeminitError) as exc_info:
            checker.execute(asset_ids=["agents-md"])
        assert exc_info.value.code == ErrorCode.PATH_ESCAPE


class TestProtocolCheckReportShape:
    def test_report_has_required_fields(self, tmp_path):
        _setup_config(tmp_path)
        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["agents-md"])

        assert report.summary["total"] == 1
        assert report.summary["aligned"] == 0
        assert report.summary["drifted"] == 1
        assert report.summary["unparseable"] == 0

        assert len(report.assets) == 1
        asset = report.assets[0]
        assert asset["id"] == "agents-md"
        assert asset["target_path"] == "AGENTS.md"
        assert asset["ownership"] == "mixed"
        assert "status" in asset
        assert "auto_fixable" in asset

    def test_aligned_asset_has_version_and_hash(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("meminit-docops-skill")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        _write_asset(tmp_path, asset, canonical)

        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["meminit-docops-skill"])
        assert report.assets[0]["expected_version"] == PROTOCOL_ASSET_VERSION
        assert report.assets[0]["expected_sha256"] is not None

    def test_missing_asset_has_expected_hash_but_not_recorded(self, tmp_path):
        _setup_config(tmp_path)
        checker = ProtocolChecker(str(tmp_path))
        report = checker.execute(asset_ids=["agents-md"])

        assert report.assets[0]["status"] == "missing"
        assert report.assets[0]["expected_version"] == PROTOCOL_ASSET_VERSION
        assert report.assets[0]["expected_sha256"] is not None
        assert report.assets[0].get("recorded_version") is None
        assert report.assets[0].get("recorded_sha256") is None
        assert report.assets[0].get("actual_sha256") is None
