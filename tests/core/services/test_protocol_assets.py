"""Tests for protocol asset registry, normalizer, marker parser, drift classifier."""

import hashlib
import re
from pathlib import Path

import pytest

from meminit.core.services.protocol_assets import (
    PROTOCOL_ASSET_VERSION,
    AssetOwnership,
    DriftOutcome,
    ProtocolAsset,
    ProtocolAssetRegistry,
    classify_drift,
    normalize_protocol_payload,
    parse_protocol_markers,
    resolve_repo_metadata,
)
from meminit.core.services.error_codes import ErrorCode, MeminitError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_asset(*, ownership=AssetOwnership.GENERATED, asset_id="test-asset"):
    return ProtocolAsset(
        id=asset_id,
        target_path="test.txt",
        package_resource="AGENTS.md",
        ownership=ownership,
    )


def _render_with_markers(asset, project_name="", repo_prefix=""):
    """Render a mixed asset and return both render and the wrapped content."""
    render = asset.render(project_name=project_name, repo_prefix=repo_prefix)
    return render


def _hash(content: str) -> str:
    return hashlib.sha256(
        normalize_protocol_payload(content).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# normalize_protocol_payload
# ---------------------------------------------------------------------------


class TestNormalizeProtocolPayload:
    def test_crlf_to_lf(self):
        assert normalize_protocol_payload("a\r\nb\r\n") == "a\nb\n"

    def test_cr_to_lf(self):
        assert normalize_protocol_payload("a\rb\n") == "a\nb\n"

    def test_trailing_whitespace_stripped(self):
        assert normalize_protocol_payload("a  \nb  \n") == "a\nb\n"

    def test_single_trailing_newline(self):
        assert normalize_protocol_payload("a\nb\n") == "a\nb\n"

    def test_double_trailing_newlines_collapsed(self):
        assert normalize_protocol_payload("a\nb\n\n") == "a\nb\n"

    def test_no_trailing_newline_added(self):
        assert normalize_protocol_payload("a\nb") == "a\nb\n"

    def test_empty_string(self):
        assert normalize_protocol_payload("") == "\n"

    def test_only_whitespace(self):
        assert normalize_protocol_payload("   \n  \n") == "\n"


# ---------------------------------------------------------------------------
# parse_protocol_markers
# ---------------------------------------------------------------------------


class TestParseProtocolMarkers:
    def _make_content(self, managed_body, version=PROTOCOL_ASSET_VERSION, asset_id="agents-md"):
        sha = _hash(managed_body)
        begin = f"<!-- MEMINIT_PROTOCOL: begin id={asset_id} version={version} sha256={sha} -->"
        end = f"<!-- MEMINIT_PROTOCOL: end id={asset_id} -->"
        return f"{begin}\n{managed_body}{end}"

    def test_valid_markers(self):
        body = "# Generated\nRules here.\n"
        content = self._make_content(body)
        parsed = parse_protocol_markers(content)
        assert parsed is not None
        assert parsed.asset_id == "agents-md"
        assert parsed.version == PROTOCOL_ASSET_VERSION
        assert parsed.managed_payload == body.rstrip("\n")

    def test_no_markers_returns_none(self):
        assert parse_protocol_markers("# Just a file\n") is None

    def test_prose_mention_of_token_returns_none(self):
        content = "This document mentions MEMINIT_PROTOCOL in prose only.\n"
        assert parse_protocol_markers(content) is None

    def test_duplicate_begin_raises(self):
        body = "content"
        sha = _hash(body)
        begin = f"<!-- MEMINIT_PROTOCOL: begin id=x version=1.0 sha256={sha} -->"
        content = f"{begin}\n{body}<!-- MEMINIT_PROTOCOL: end id=x -->\n{begin}\n"
        with pytest.raises(ValueError, match="Multiple"):
            parse_protocol_markers(content)

    def test_missing_end_raises(self):
        body = "content"
        sha = _hash(body)
        begin = f"<!-- MEMINIT_PROTOCOL: begin id=x version=1.0 sha256={sha} -->"
        content = f"{begin}\n{body}"
        with pytest.raises(ValueError, match="Missing"):
            parse_protocol_markers(content)

    def test_mismatched_end_id_raises(self):
        body = "content"
        sha = _hash(body)
        begin = f"<!-- MEMINIT_PROTOCOL: begin id=x version=1.0 sha256={sha} -->"
        end = "<!-- MEMINIT_PROTOCOL: end id=y -->"
        content = f"{begin}\n{body}\n{end}"
        with pytest.raises(ValueError, match="does not match"):
            parse_protocol_markers(content)

    def test_preamble_before_begin_raises(self):
        body = "content"
        sha = _hash(body)
        begin = f"<!-- MEMINIT_PROTOCOL: begin id=x version=1.0 sha256={sha} -->"
        end = "<!-- MEMINIT_PROTOCOL: end id=x -->"
        content = f"# Preamble\n{begin}\n{body}\n{end}"
        with pytest.raises(ValueError, match="Non-blank content before"):
            parse_protocol_markers(content)

    def test_blank_lines_before_begin_allowed(self):
        body = "content"
        sha = _hash(body)
        begin = f"<!-- MEMINIT_PROTOCOL: begin id=x version=1.0 sha256={sha} -->"
        end = "<!-- MEMINIT_PROTOCOL: end id=x -->"
        content = f"\n\n{begin}\n{body}\n{end}"
        parsed = parse_protocol_markers(content)
        assert parsed is not None

    def test_duplicate_end_marker_raises(self):
        body = "content"
        sha = _hash(body)
        begin = f"<!-- MEMINIT_PROTOCOL: begin id=x version=1.0 sha256={sha} -->"
        end = "<!-- MEMINIT_PROTOCOL: end id=x -->"
        content = f"{begin}\n{body}\n{end}\n{end}"
        with pytest.raises(ValueError, match="outside the managed region"):
            parse_protocol_markers(content)

    def test_end_marker_after_end_raises(self):
        body = "content"
        sha = _hash(body)
        begin = f"<!-- MEMINIT_PROTOCOL: begin id=x version=1.0 sha256={sha} -->"
        end = "<!-- MEMINIT_PROTOCOL: end id=x -->"
        content = f"{begin}\n{body}\n{end}\nUser section\n{end}"
        with pytest.raises(ValueError, match="outside the managed region"):
            parse_protocol_markers(content)

    def test_end_only_marker_raises(self):
        content = "Some content\n<!-- MEMINIT_PROTOCOL: end id=x -->\nMore content\n"
        with pytest.raises(ValueError, match="marker syntax found without valid begin marker"):
            parse_protocol_markers(content)

    def test_end_marker_with_garbage_before_it_raises(self):
        content = "Header\n<!-- MEMINIT_PROTOCOL: end id=x -->\nBody\n"
        with pytest.raises(ValueError, match="marker syntax found without valid begin marker"):
            parse_protocol_markers(content)

    def test_malformed_begin_marker_without_valid_begin_raises(self):
        content = "Header\n<!-- MEMINIT_PROTOCOL: begin id=x version=1.0 -->\nBody\n"
        with pytest.raises(ValueError, match="marker syntax found without valid begin marker"):
            parse_protocol_markers(content)

    def test_malformed_protocol_comment_after_end_is_rejected(self):
        body = "content"
        sha = _hash(body)
        begin = f"<!-- MEMINIT_PROTOCOL: begin id=x version=1.0 sha256={sha} -->"
        end = "<!-- MEMINIT_PROTOCOL: end id=x -->"
        content = f"{begin}\n{body}\n{end}\n<!-- MEMINIT_PROTOCOL: malformed -->\n"
        with pytest.raises(ValueError, match="outside the managed region"):
            parse_protocol_markers(content)

    def test_prose_mention_after_end_is_allowed(self):
        body = "content"
        sha = _hash(body)
        begin = f"<!-- MEMINIT_PROTOCOL: begin id=x version=1.0 sha256={sha} -->"
        end = "<!-- MEMINIT_PROTOCOL: end id=x -->"
        content = f"{begin}\n{body}\n{end}\nThis mentions MEMINIT_PROTOCOL in prose.\n"
        result = parse_protocol_markers(content)
        assert result is not None
        assert result.asset_id == "x"

# ---------------------------------------------------------------------------
# classify_drift
# ---------------------------------------------------------------------------


class TestClassifyDrift:
    def test_missing(self):
        asset = _make_asset(ownership=AssetOwnership.GENERATED)
        canonical = asset.render()
        status = classify_drift(asset, canonical, None)
        assert status.status == DriftOutcome.MISSING
        assert status.auto_fixable is True

    def test_generated_aligned(self):
        asset = _make_asset(ownership=AssetOwnership.GENERATED)
        canonical = asset.render()
        status = classify_drift(asset, canonical, canonical)
        assert status.status == DriftOutcome.ALIGNED
        assert status.auto_fixable is False

    def test_generated_stale(self):
        asset = _make_asset(ownership=AssetOwnership.GENERATED)
        canonical = asset.render()
        status = classify_drift(asset, canonical, "different content\n")
        assert status.status == DriftOutcome.STALE
        assert status.auto_fixable is True

    def test_mixed_legacy(self):
        asset = _make_asset(ownership=AssetOwnership.MIXED)
        canonical = asset.render(project_name="Test")
        status = classify_drift(asset, canonical, "# Old AGENTS.md\nNo markers.\n")
        assert status.status == DriftOutcome.LEGACY
        assert status.auto_fixable is True

    def test_mixed_aligned(self):
        asset = _make_asset(ownership=AssetOwnership.MIXED)
        canonical = asset.render(project_name="Test", repo_prefix="TEST")
        status = classify_drift(asset, canonical, canonical)
        assert status.status == DriftOutcome.ALIGNED

    def test_mixed_aligned_with_uppercase_hex(self):
        asset = _make_asset(ownership=AssetOwnership.MIXED)
        canonical = asset.render(project_name="Test", repo_prefix="TEST")
        lines = canonical.split("\n")
        modified_lines = list(lines)
        for i, line in enumerate(modified_lines):
            if "sha256=" in line:
                modified_lines[i] = re.sub(
                    r"(sha256=)([0-9a-f]{64})",
                    lambda m: m.group(1) + m.group(2).upper(),
                    line,
                )
        uppercase_content = "\n".join(modified_lines)
        status = classify_drift(asset, canonical, uppercase_content)
        assert status.status == DriftOutcome.ALIGNED

    def test_mixed_tampered(self):
        asset = _make_asset(ownership=AssetOwnership.MIXED)
        canonical = asset.render(project_name="Test", repo_prefix="TEST")
        # Parse canonical to get markers, then modify managed content
        parsed = parse_protocol_markers(canonical)
        assert parsed is not None
        # Rebuild with edited content but original hash
        lines = canonical.split("\n")
        edited_lines = lines[: parsed.begin_line + 1] + ["TAMPERED LINE"] + lines[parsed.end_line:]
        edited = "\n".join(edited_lines)
        status = classify_drift(asset, canonical, edited)
        assert status.status == DriftOutcome.TAMPERED
        assert status.auto_fixable is False

    def test_mixed_marker_id_mismatch_is_stale(self):
        asset = _make_asset(ownership=AssetOwnership.MIXED)
        canonical = asset.render(project_name="Test", repo_prefix="TEST")
        parsed = parse_protocol_markers(canonical)
        assert parsed is not None
        # Replace the asset id in markers with a wrong one
        lines = canonical.split("\n")
        lines[parsed.begin_line] = lines[parsed.begin_line].replace(
            f"id={parsed.asset_id}", "id=wrong-asset-id"
        )
        lines[parsed.end_line] = lines[parsed.end_line].replace(
            f"id={parsed.asset_id}", "id=wrong-asset-id"
        )
        mismatched = "\n".join(lines)
        status = classify_drift(asset, canonical, mismatched)
        assert status.status == DriftOutcome.STALE
        assert status.auto_fixable is True

    def test_mixed_unparseable_duplicate_begin(self):
        asset = _make_asset(ownership=AssetOwnership.MIXED)
        canonical = asset.render(project_name="Test")
        content = canonical.replace("<!-- MEMINIT_PROTOCOL:", "<!-- MEMINIT_PROTOCOL: begin id=x version=0.1 sha256=" + "0" * 64 + " -->\n<!-- MEMINIT_PROTOCOL:")
        status = classify_drift(asset, canonical, content)
        assert status.status == DriftOutcome.UNPARSEABLE
        assert status.auto_fixable is False

    def test_mixed_unparseable_missing_end(self):
        asset = _make_asset(ownership=AssetOwnership.MIXED)
        canonical = asset.render(project_name="Test")
        # Strip everything after begin marker (including end)
        parsed = parse_protocol_markers(canonical)
        assert parsed is not None
        content = "\n".join(canonical.split("\n")[: parsed.begin_line + 1])
        status = classify_drift(asset, canonical, content)
        assert status.status == DriftOutcome.UNPARSEABLE

    def test_mixed_stale_old_version(self):
        asset = _make_asset(ownership=AssetOwnership.MIXED)
        canonical = asset.render(project_name="Test", repo_prefix="TEST")
        # Build a file with correct old hash but old version
        parsed = parse_protocol_markers(canonical)
        assert parsed is not None
        # Change version in begin marker to simulate old version
        old_begin = f"<!-- MEMINIT_PROTOCOL: begin id={parsed.asset_id} version=0.9 sha256={parsed.recorded_sha256} -->"
        lines = canonical.split("\n")
        lines[parsed.begin_line] = old_begin
        old_content = "\n".join(lines)
        status = classify_drift(asset, canonical, old_content)
        # Self-consistent but canonical has changed version -> stale
        assert status.status == DriftOutcome.STALE
        assert status.auto_fixable is True


# ---------------------------------------------------------------------------
# ProtocolAssetRegistry
# ---------------------------------------------------------------------------


class TestProtocolAssetRegistry:
    def test_default_has_three_assets(self):
        registry = ProtocolAssetRegistry.default()
        assert len(registry.assets) == 3

    def test_default_ids(self):
        registry = ProtocolAssetRegistry.default()
        assert registry.ids == (
            "agents-md",
            "meminit-docops-skill",
            "meminit-brownfield-script",
        )

    def test_get_by_id(self):
        registry = ProtocolAssetRegistry.default()
        asset = registry.get_by_id("agents-md")
        assert asset is not None
        assert asset.ownership == AssetOwnership.MIXED
        assert asset.target_path == "AGENTS.md"

    def test_get_by_id_unknown(self):
        registry = ProtocolAssetRegistry.default()
        assert registry.get_by_id("nonexistent") is None

    def test_duplicate_ids_rejected(self):
        asset = ProtocolAsset(id="dup", target_path="a", package_resource="AGENTS.md", ownership=AssetOwnership.GENERATED)
        with pytest.raises(ValueError, match="Duplicate"):
            ProtocolAssetRegistry(assets=(asset, asset))

    def test_generated_file_mode(self):
        registry = ProtocolAssetRegistry.default()
        script = registry.get_by_id("meminit-brownfield-script")
        assert script is not None
        assert script.file_mode == 0o755


# ---------------------------------------------------------------------------
# ProtocolAsset.render
# ---------------------------------------------------------------------------


class TestProtocolAssetRender:
    def test_mixed_has_markers(self):
        asset = _make_asset(ownership=AssetOwnership.MIXED, asset_id="test-mixed")
        render = asset.render(project_name="Proj", repo_prefix="PROJ")
        assert "MEMINIT_PROTOCOL: begin" in render
        assert "MEMINIT_PROTOCOL: end" in render
        assert "id=test-mixed" in render
        assert f"version={PROTOCOL_ASSET_VERSION}" in render

    def test_generated_no_markers(self):
        asset = _make_asset(ownership=AssetOwnership.GENERATED, asset_id="test-gen")
        render = asset.render()
        assert "MEMINIT_PROTOCOL" not in render

    def test_hash_is_deterministic(self):
        asset = _make_asset(ownership=AssetOwnership.MIXED, asset_id="det")
        r1 = asset.render(project_name="P", repo_prefix="R")
        r2 = asset.render(project_name="P", repo_prefix="R")
        assert r1 == r2

    def test_interpolation(self):
        asset = _make_asset(ownership=AssetOwnership.GENERATED)
        render = asset.render(project_name="MyProject", repo_prefix="MY")
        # AGENTS.md template has {{PROJECT_NAME}} and {{REPO_PREFIX}}
        assert "{{PROJECT_NAME}}" not in render
        assert "{{REPO_PREFIX}}" not in render
        assert "MyProject" in render
        assert "MY" in render


# ---------------------------------------------------------------------------
# resolve_repo_metadata
# ---------------------------------------------------------------------------


class TestResolveRepoMetadata:
    def test_with_config(self, tmp_path):
        (tmp_path / "docops.config.yaml").write_text(
            "project_name: MyRepo\nrepo_prefix: MYREPO\ndocops_version: '2.0'\n",
            encoding="utf-8",
        )
        name, prefix = resolve_repo_metadata(tmp_path)
        assert name == "MyRepo"
        assert prefix == "MYREPO"

    def test_without_config_uses_dirname(self, tmp_path):
        name, prefix = resolve_repo_metadata(tmp_path)
        assert name == tmp_path.name
        clean = re.sub(r"[^a-zA-Z]", "", tmp_path.name)
        expected_prefix = clean[:10].upper() if len(clean) >= 3 else "REPO"
        assert prefix == expected_prefix

    def test_malformed_config_falls_back(self, tmp_path):
        (tmp_path / "docops.config.yaml").write_text("{{{invalid yaml", encoding="utf-8")
        name, _prefix = resolve_repo_metadata(tmp_path)
        assert name == tmp_path.name

    def test_empty_project_name_in_config(self, tmp_path):
        (tmp_path / "docops.config.yaml").write_text(
            "project_name: ''\nrepo_prefix: ''\ndocops_version: '2.0'\n",
            encoding="utf-8",
        )
        name, _prefix = resolve_repo_metadata(tmp_path)
        assert name == tmp_path.name
