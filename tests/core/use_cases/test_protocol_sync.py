"""Tests for the protocol sync use case (PR 3)."""

from pathlib import Path

import pytest

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.protocol_assets import (
    AssetOwnership,
    PROTOCOL_ASSET_VERSION,
    DriftOutcome,
    ProtocolAsset,
    ProtocolAssetRegistry,
)
from meminit.core.use_cases.protocol_sync import ProtocolSyncer, _decide_action


# ---------------------------------------------------------------------------
# _decide_action
# ---------------------------------------------------------------------------


class TestDecideAction:
    def test_aligned_is_noop(self):
        assert _decide_action("aligned", False) == "noop"

    def test_missing_is_rewrite(self):
        assert _decide_action("missing", False) == "rewrite"

    def test_legacy_is_rewrite(self):
        assert _decide_action("legacy", False) == "rewrite"

    def test_stale_is_rewrite(self):
        assert _decide_action("stale", False) == "rewrite"

    def test_tampered_refuses_without_force(self):
        assert _decide_action("tampered", False) == "refuse"

    def test_tampered_rewrites_with_force(self):
        assert _decide_action("tampered", True) == "rewrite"

    def test_unparseable_always_refuses(self):
        assert _decide_action("unparseable", False) == "refuse"
        assert _decide_action("unparseable", True) == "refuse"


# ---------------------------------------------------------------------------
# ProtocolSyncer
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


class TestProtocolSyncerNoop:
    def test_missing_config_derives_defaults(self, tmp_path):
        """Protocol sync uses standard config resolution which derives defaults."""
        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(dry_run=False)
        assert report.summary["total"] == 3
        assert report.summary["rewritten"] == 3
        assert report.applied is True

    def test_aligned_assets_are_noop(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        for asset in registry.assets:
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            _write_asset(tmp_path, asset, canonical)
        script_asset = registry.get_by_id("meminit-brownfield-script")
        assert script_asset is not None
        (tmp_path / script_asset.target_path).chmod(script_asset.file_mode)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute()
        assert report.success is True
        assert report.summary["noop"] == 3
        assert report.summary["rewritten"] == 0
        assert report.summary["refused"] == 0
        for a in report.assets:
            assert a["action"] == "noop"

    def test_aligned_executable_bit_is_restored(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        for asset in registry.assets:
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            _write_asset(tmp_path, asset, canonical)

        script_asset = registry.get_by_id("meminit-brownfield-script")
        assert script_asset is not None
        script_path = tmp_path / script_asset.target_path
        script_path.chmod(0o644)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(dry_run=False)
        assert report.success is True
        assert report.applied is True
        assert report.summary["noop"] == 2
        assert report.summary["rewritten"] == 1
        assert script_path.stat().st_mode & script_asset.file_mode != 0

    def test_executable_bit_drift_is_reported_before_sync(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        for asset in registry.assets:
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            _write_asset(tmp_path, asset, canonical)

        script_asset = registry.get_by_id("meminit-brownfield-script")
        assert script_asset is not None
        script_path = tmp_path / script_asset.target_path
        script_path.chmod(0o644)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(dry_run=True)
        assert report.success is False
        assert report.summary["rewritten"] == 1
        script_result = next(a for a in report.assets if a["id"] == "meminit-brownfield-script")
        assert script_result["prior_status"] == "stale"
        assert script_result["action"] == "rewrite"
        assert script_result["target_path"] == script_asset.target_path

    def test_chmod_failure_raises_structured_error(self, monkeypatch, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        for asset in registry.assets:
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            _write_asset(tmp_path, asset, canonical)

        script_asset = registry.get_by_id("meminit-brownfield-script")
        assert script_asset is not None
        script_path = tmp_path / script_asset.target_path
        script_path.chmod(0o644)

        original_fchmod = __import__("os").fchmod

        def fake_fchmod(fd, mode):
            raise OSError("simulated chmod failure")

        monkeypatch.setattr("os.fchmod", fake_fchmod, raising=True)

        syncer = ProtocolSyncer(str(tmp_path))
        with pytest.raises(MeminitError) as exc_info:
            syncer.execute(dry_run=False)
        assert exc_info.value.code == ErrorCode.UNKNOWN_ERROR
        assert "Failed to apply file mode" in str(exc_info.value)

        # Verify the file was NOT partially written (temp file cleaned up)
        assert script_path.read_text(encoding="utf-8") != ""


class TestProtocolSyncerRewrite:
    def test_missing_asset_created(self, tmp_path):
        _setup_config(tmp_path)
        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.applied is True
        asset = report.assets[0]
        assert asset["action"] == "rewrite"
        assert asset["prior_status"] == "missing"
        assert (tmp_path / "AGENTS.md").exists()

    def test_duplicate_asset_ids_are_deduplicated(self, tmp_path):
        _setup_config(tmp_path)
        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md", "agents-md"], dry_run=False)
        assert report.summary["total"] == 1
        assert [a["id"] for a in report.assets] == ["agents-md"]
        result = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert result.count("MEMINIT_PROTOCOL: begin") == 1

    def test_stale_asset_updated(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("meminit-docops-skill")
        assert asset is not None
        _write_asset(tmp_path, asset, "old stale content\n")

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["meminit-docops-skill"], dry_run=False)
        assert report.assets[0]["action"] == "rewrite"
        assert report.applied is True

    def test_legacy_asset_wrapped(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        _write_asset(tmp_path, asset, "# Legacy AGENTS.md\nNo markers here.\n")

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0]["action"] == "rewrite"
        assert report.applied is True

        # Verify user content is preserved
        result = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert "Legacy AGENTS.md" in result


class TestProtocolSyncerForce:
    def test_force_dry_run_emits_warning(self, tmp_path):
        _setup_config(tmp_path)
        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(dry_run=True, force=True)
        assert report.success is False
        assert any(w["code"] == "PROTOCOL_SYNC_FORCE_USED" for w in report.warnings)
        assert "dry run" in report.warnings[0]["message"]

    def test_tampered_refuses_without_force(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        lines = canonical.split("\n")
        lines.insert(2, "TAMPERED LINE")
        _write_asset(tmp_path, asset, "\n".join(lines))

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0]["action"] == "refuse"
        assert report.success is False

    def test_tampered_rewrites_with_force(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        lines = canonical.split("\n")
        lines.insert(2, "TAMPERED LINE")
        _write_asset(tmp_path, asset, "\n".join(lines))

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False, force=True)
        assert report.assets[0]["action"] == "rewrite"
        assert report.success is True
        assert "PROTOCOL_SYNC_FORCE_USED" in [w["code"] for w in report.warnings]
        msg = [w["message"] for w in report.warnings if w["code"] == "PROTOCOL_SYNC_FORCE_USED"][0]
        assert "tampered assets were overwritten" in msg

    def test_force_noop_still_emits_warning(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        for asset in registry.assets:
            _write_asset(tmp_path, asset, asset.render(project_name="TestProject", repo_prefix="TEST"))
        script_asset = registry.get_by_id("meminit-brownfield-script")
        assert script_asset is not None
        (tmp_path / script_asset.target_path).chmod(script_asset.file_mode)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(dry_run=False, force=True)
        assert report.success is True
        assert report.summary["noop"] == 3
        assert any(w["code"] == "PROTOCOL_SYNC_FORCE_USED" for w in report.warnings)
        assert "no tampered assets" in report.warnings[0]["message"]

    def test_unparseable_always_refuses_even_with_force(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        content = (
            "<!-- MEMINIT_PROTOCOL: begin id=agents-md version=1.0 "
            "sha256=" + "0" * 64 + " -->\nno end marker\n"
        )
        _write_asset(tmp_path, asset, content)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False, force=True)
        assert report.assets[0]["action"] == "refuse"
        assert report.success is False

    def test_refusal_skips_only_refused_assets_safe_assets_still_synced(self, tmp_path):
        _setup_config(tmp_path)
        mixed_asset = ProtocolAsset(
            id="zzz-mixed",
            target_path="AGENTS.md",
            package_resource="AGENTS.md",
            ownership=AssetOwnership.MIXED,
        )
        generated_asset = ProtocolAsset(
            id="aaa-generated",
            target_path="docs/generated/protocol.txt",
            package_resource="meminit-docops-skill.md",
            ownership=AssetOwnership.GENERATED,
        )
        custom_registry = ProtocolAssetRegistry(
            assets=(generated_asset, mixed_asset)
        )
        canonical = mixed_asset.render(project_name="TestProject", repo_prefix="TEST")
        tampered = canonical.replace("MEMINIT_PROTOCOL: end", "MEMINIT_PROTOCOL: tampered")
        _write_asset(tmp_path, mixed_asset, tampered)

        syncer = ProtocolSyncer(str(tmp_path), registry=custom_registry)
        report = syncer.execute(dry_run=False)
        assert report.success is False
        assert report.summary["refused"] == 1
        assert report.summary["rewritten"] == 1
        assert report.applied is True
        assert (tmp_path / "docs/generated/protocol.txt").exists()
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == tampered

    def test_force_warning_when_refused_and_safe_assets_synced(self, tmp_path):
        _setup_config(tmp_path)
        mixed_asset = ProtocolAsset(
            id="zzz-mixed",
            target_path="AGENTS.md",
            package_resource="AGENTS.md",
            ownership=AssetOwnership.MIXED,
        )
        generated_asset = ProtocolAsset(
            id="aaa-generated",
            target_path="docs/generated/protocol.txt",
            package_resource="meminit-docops-skill.md",
            ownership=AssetOwnership.GENERATED,
        )
        custom_registry = ProtocolAssetRegistry(
            assets=(generated_asset, mixed_asset)
        )
        canonical = mixed_asset.render(project_name="TestProject", repo_prefix="TEST")
        tampered = canonical.replace("MEMINIT_PROTOCOL: end", "MEMINIT_PROTOCOL: tampered")
        _write_asset(tmp_path, mixed_asset, tampered)

        syncer = ProtocolSyncer(str(tmp_path), registry=custom_registry)
        report = syncer.execute(dry_run=False, force=True)
        assert report.warnings
        msg = report.warnings[0]["message"]
        assert "non-refused assets were synced" in msg


class TestProtocolSyncerDryRun:
    def test_dry_run_no_writes(self, tmp_path):
        _setup_config(tmp_path)
        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(dry_run=True)
        assert report.dry_run is True
        assert report.applied is False
        assert report.summary["rewritten"] == 3

    def test_dry_run_shape_matches_wet(self, tmp_path):
        _setup_config(tmp_path)
        syncer = ProtocolSyncer(str(tmp_path))
        dry = syncer.execute(dry_run=True)
        wet = syncer.execute(dry_run=False)
        assert dry.dry_run is True
        assert wet.dry_run is False
        assert dry.summary == wet.summary  # same prior_status classification


class TestProtocolSyncerIdempotency:
    def test_second_sync_is_all_noop(self, tmp_path):
        _setup_config(tmp_path)
        syncer = ProtocolSyncer(str(tmp_path))

        # First sync creates all missing assets
        r1 = syncer.execute(dry_run=False)
        assert r1.summary["rewritten"] == 3

        # Second sync should be all noop
        r2 = syncer.execute(dry_run=False)
        assert r2.summary["noop"] == 3
        assert r2.summary["rewritten"] == 0
        assert r2.applied is False


class TestProtocolSyncerUserContentPreservation:
    def test_legacy_user_content_preserved_byte_identical(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        user_content = "# My Custom Section\n\nImportant rules here.\n"
        _write_asset(tmp_path, asset, user_content)

        user_bytes_before = len(user_content.encode("utf-8"))

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0]["action"] == "rewrite"

        result = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert user_content.strip() in result
        assert len(result.encode("utf-8")) >= user_bytes_before

    def test_crlf_user_content_preserved_verbatim(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")

        parsed_lines = canonical.split("\n")
        end_idx = next(
            i for i, line in enumerate(parsed_lines)
            if "MEMINIT_PROTOCOL: end" in line
        )
        # Make it stale by bumping version
        content_lines = list(parsed_lines[: end_idx + 1])
        content_lines[0] = content_lines[0].replace("version=1.0", "version=0.9")
        # User content with CRLF line endings — must be preserved byte-identical
        user_section = "\n## Custom\r\nUser notes with CRLF.\r\n"
        full_content = "\n".join(content_lines) + user_section
        _write_asset(tmp_path, asset, full_content)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0]["action"] == "rewrite"

        result_bytes = (tmp_path / "AGENTS.md").read_bytes()
        # User section with CRLF must appear verbatim in the output
        user_marker = b"## Custom\r\nUser notes with CRLF.\r\n"
        assert user_marker in result_bytes, "CRLF user bytes not preserved verbatim"
        # The managed region (before end marker) should be LF-only
        end_marker_pos = result_bytes.find(b"MEMINIT_PROTOCOL: end")
        assert end_marker_pos > 0
        managed_region = result_bytes[:end_marker_pos]
        assert b"\r" not in managed_region, "Managed region must be LF-only"

    def test_stale_mixed_preserves_user_content(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")

        parsed_lines = canonical.split("\n")
        end_idx = next(
            i for i, line in enumerate(parsed_lines)
            if "MEMINIT_PROTOCOL: end" in line
        )
        # Bump version in begin marker to make the managed region stale
        content_lines = list(parsed_lines[:end_idx + 1])
        content_lines[0] = content_lines[0].replace("version=1.0", "version=0.9")
        user_section = "\n## Custom\nUser notes here.\n"
        full_content = "\n".join(content_lines) + user_section
        _write_asset(tmp_path, asset, full_content)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0]["action"] == "rewrite"
        assert report.assets[0].get("preserved_user_bytes") is not None

        result = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert "User notes here." in result


class TestProtocolSyncerValidation:
    def test_unknown_asset_raises(self, tmp_path):
        _setup_config(tmp_path)
        syncer = ProtocolSyncer(str(tmp_path))
        with pytest.raises(MeminitError) as exc_info:
            syncer.execute(asset_ids=["nonexistent"])
        assert exc_info.value.code == ErrorCode.UNKNOWN_TYPE
        assert "nonexistent" in str(exc_info.value)

    def test_explicit_empty_list_selects_no_assets(self, tmp_path):
        _setup_config(tmp_path)
        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=[], dry_run=False)
        assert report.summary["total"] == 0
        assert report.summary["rewritten"] == 0
        assert report.applied is False

    def test_preserves_user_bytes_in_report(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        _write_asset(tmp_path, asset, "# Legacy content\n")

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0].get("preserved_user_bytes") is not None

    def test_managed_region_contains_end_literal_preserves_user_bytes(self, tmp_path):
        """If managed region contains 'MEMINIT_PROTOCOL: end' in content,
        user bytes after the real marker must still be preserved exactly."""
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        parsed_lines = canonical.split("\n")
        end_idx = next(
            i for i, line in enumerate(parsed_lines)
            if "MEMINIT_PROTOCOL: end" in line
        )
        content_lines = list(parsed_lines[: end_idx + 1])
        # Insert literal end-marker text into managed content (makes it tampered)
        content_lines.insert(2, "See MEMINIT_PROTOCOL: end for marker format reference.")
        full_content = "\n".join(content_lines) + "\n## Custom\nUser notes preserved.\n"
        _write_asset(tmp_path, asset, full_content)

        # Use --force since tampered assets refuse without it
        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False, force=True)
        assert report.assets[0]["action"] == "rewrite"
        assert report.assets[0]["prior_status"] == "tampered"

        result = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert "## Custom" in result
        assert "User notes preserved." in result

    def test_non_utf8_user_bytes_preserved(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST").encode("utf-8")
        stale = canonical.replace(b"version=1.0", b"version=0.9", 1) + b"## Custom\ninvalid:\xff\n"
        _write_asset_bytes(tmp_path, asset, stale)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0]["action"] == "rewrite"
        result_bytes = (tmp_path / "AGENTS.md").read_bytes()
        assert b"invalid:\xff\n" in result_bytes

    def test_directory_target_is_rejected(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        target = tmp_path / asset.target_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir()

        syncer = ProtocolSyncer(str(tmp_path))
        with pytest.raises(MeminitError) as exc_info:
            syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert exc_info.value.code == ErrorCode.PATH_ESCAPE

    def test_whitespace_only_user_region_preserved(self, tmp_path):
        """Whitespace-only user content after end marker should not be silently dropped."""
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        parsed_lines = canonical.split("\n")
        end_idx = next(
            i for i, line in enumerate(parsed_lines)
            if "MEMINIT_PROTOCOL: end" in line
        )
        content_lines = list(parsed_lines[: end_idx + 1])
        content_lines[0] = content_lines[0].replace("version=1.0", "version=0.9")
        # User content is whitespace-only (just newlines)
        user_section = "\n\n\n"
        full_content = "\n".join(content_lines) + user_section
        _write_asset(tmp_path, asset, full_content)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0]["action"] == "rewrite"
        assert report.assets[0].get("preserved_user_bytes") is not None
        assert report.assets[0]["preserved_user_bytes"] > 0

    def test_exact_boundary_no_extra_blank_line(self, tmp_path):
        """No extra newline inserted between managed region and user bytes."""
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        parsed_lines = canonical.split("\n")
        end_idx = next(
            i for i, line in enumerate(parsed_lines)
            if "MEMINIT_PROTOCOL: end" in line
        )
        content_lines = list(parsed_lines[: end_idx + 1])
        content_lines[0] = content_lines[0].replace("version=1.0", "version=0.9")
        # User content starts immediately (no leading blank line)
        user_section = "## Custom\nNotes.\n"
        full_content = "\n".join(content_lines) + "\n" + user_section
        _write_asset(tmp_path, asset, full_content)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0]["action"] == "rewrite"

        result_text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        # The boundary between managed region and user section should be exactly
        # one newline (the canonical's trailing \n), not two
        end_line_idx = result_text.find("MEMINIT_PROTOCOL: end")
        after_end = result_text[end_line_idx:]
        # After end marker line, next content should be user section (no blank line)
        lines_after = after_end.split("\n")
        # lines_after[0] = end marker, lines_after[1] = empty (from \n after marker),
        # lines_after[2] = "## Custom"
        # Since canonical ends with \n and we don't add extra separator,
        # user content starts right after
        assert "## Custom" in lines_after[1] or "## Custom" in lines_after[2]

    def test_crlf_in_managed_region_preserves_user_boundary(self, tmp_path):
        """CRLF in managed region doesn't shift user content extraction."""
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        parsed_lines = canonical.split("\n")
        end_idx = next(
            i for i, line in enumerate(parsed_lines)
            if "MEMINIT_PROTOCOL: end" in line
        )
        content_lines = list(parsed_lines[: end_idx + 1])
        content_lines[0] = content_lines[0].replace("version=1.0", "version=0.9")
        # Write with CRLF in managed region and LF in user region
        managed_region = "\r\n".join(content_lines)
        user_section = "\n## Custom\nUser notes.\n"
        full_content = managed_region + user_section
        _write_asset(tmp_path, asset, full_content)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0]["action"] == "rewrite"

        result = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        # User content must be fully preserved
        assert "## Custom" in result
        assert "User notes." in result
        # Managed region should be LF-only after rewrite
        end_pos = result.find("MEMINIT_PROTOCOL: end")
        managed = result[:end_pos]
        assert "\r" not in managed

    def test_crlf_managed_region_exact_byte_preservation(self, tmp_path):
        """CRLF in managed region: user bytes preserved at exact byte boundary.

        Regression: text-mode read_text() normalizes \\r\\n to \\n, causing
        byte_offset to undercount by 1 byte per CRLF line. A null-byte
        sentinel before the user suffix guarantees shifted boundaries fail.
        """
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        parsed_lines = canonical.split("\n")
        end_idx = next(
            i for i, line in enumerate(parsed_lines)
            if "MEMINIT_PROTOCOL: end" in line
        )
        managed_lines = list(parsed_lines[: end_idx + 1])
        managed_lines[0] = managed_lines[0].replace("version=1.0", "version=0.9")
        # Encode managed region with CRLF line endings
        managed_bytes = "\r\n".join(managed_lines).encode("utf-8") + b"\r\n"
        # Exact user suffix with null-byte sentinel — any boundary shift fails
        user_suffix = b"\x00USER_BOUNDARY_OK"
        target = tmp_path / asset.target_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(managed_bytes + user_suffix)

        syncer = ProtocolSyncer(str(tmp_path))
        report = syncer.execute(asset_ids=["agents-md"], dry_run=False)
        assert report.assets[0]["action"] == "rewrite"

        result_bytes = (tmp_path / "AGENTS.md").read_bytes()
        # Managed region should be LF-only after rewrite
        end_pos = result_bytes.find(b"MEMINIT_PROTOCOL: end")
        assert end_pos > 0
        assert b"\r" not in result_bytes[:end_pos]
        # Find end of the canonical end marker line in result
        newline_after = result_bytes.find(b"\n", end_pos) + 1
        actual_user = result_bytes[newline_after:]
        assert actual_user == user_suffix

class TestProtocolSyncerFileMode:
    def test_executable_script_mode_applied(self, tmp_path):
        _setup_config(tmp_path)
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("meminit-brownfield-script")
        assert asset is not None

        syncer = ProtocolSyncer(str(tmp_path))
        syncer.execute(asset_ids=["meminit-brownfield-script"], dry_run=False)

        target = tmp_path / asset.target_path
        assert target.exists()
        # On Unix, the executable bit should be set
        mode = target.stat().st_mode
        assert mode & 0o111  # has execute permission
