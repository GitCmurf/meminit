"""Protocol fixture scenarios for check/sync tests (F01–F13, F16–F17)."""

from pathlib import Path
from typing import Callable, Dict, List, Optional

from meminit.core.services.protocol_assets import (
    PROTOCOL_ASSET_VERSION,
    ProtocolAssetRegistry,
)


def _previous_version() -> str:
    parts = PROTOCOL_ASSET_VERSION.split(".")
    major, minor = int(parts[0]), int(parts[1])
    if minor > 0:
        minor -= 1
    else:
        major -= 1
        minor = 9
    return f"{major}.{minor}"


_PREVIOUS_VERSION = _previous_version()


def _setup_config(tmp_path: Path, project_name: str = "TestProject", repo_prefix: str = "TEST") -> None:
    (tmp_path / "docops.config.yaml").write_text(
        f"project_name: {project_name}\nrepo_prefix: {repo_prefix}\n"
        f"docops_version: '2.0'\n",
        encoding="utf-8",
    )


def _write_canonical(tmp_path: Path, asset) -> None:
    canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
    target = tmp_path / asset.target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(canonical, encoding="utf-8")
    if asset.file_mode is not None:
        target.chmod(asset.file_mode)


def _write_asset(tmp_path: Path, asset_id: str, content: str) -> None:
    registry = ProtocolAssetRegistry.default()
    asset = registry.get_by_id(asset_id)
    assert asset is not None
    target = tmp_path / asset.target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _canonical(tmp_path: Path, asset_id: str) -> str:
    registry = ProtocolAssetRegistry.default()
    asset = registry.get_by_id(asset_id)
    assert asset is not None
    return asset.render(project_name="TestProject", repo_prefix="TEST")


def _build_aligned_content(tmp_path: Path, asset_id: str) -> str:
    return _canonical(tmp_path, asset_id)


# ---------------------------------------------------------------------------
# Fixture setup functions — each returns the tmp_path with the repo state
# ---------------------------------------------------------------------------


def setup_f01_aligned(tmp_path: Path) -> Dict[str, str]:
    """F01: Freshly-initialized, all assets aligned."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "true", "expected_drifted": "0"}


def setup_f02_missing_agents_md(tmp_path: Path) -> Dict[str, str]:
    """F02: Missing AGENTS.md."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "agents-md":
            continue
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "false", "expected_drifted": "1", "expected_missing": "agents-md"}


def setup_f03_missing_skill_manifest(tmp_path: Path) -> Dict[str, str]:
    """F03: Missing skill manifest."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "meminit-docops-skill":
            continue
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "false", "expected_drifted": "1", "expected_missing": "meminit-docops-skill"}


def setup_f04_legacy_agents_md(tmp_path: Path) -> Dict[str, str]:
    """F04: Pre-v0.4 AGENTS.md without markers (legacy)."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "agents-md":
            _write_asset(tmp_path, asset.id, "# Legacy AGENTS.md\n\nOld content here.\n")
            continue
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "false", "expected_drifted": "1", "expected_legacy": "agents-md"}


def setup_f05_stale_version(tmp_path: Path) -> Dict[str, str]:
    """F05: Stale version in begin marker."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "agents-md":
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            content = canonical.replace(
                f"version={PROTOCOL_ASSET_VERSION}", f"version={_PREVIOUS_VERSION}"
            )
            _write_asset(tmp_path, asset.id, content)
            continue
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "false", "expected_drifted": "1", "expected_stale": "agents-md"}


def setup_f06_stale_hash(tmp_path: Path) -> Dict[str, str]:
    """F06: Self-consistent metadata but old content hash (canonical changed)."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "agents-md":
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            lines = canonical.split("\n")
            # Edit the managed payload (line after begin marker) to change the hash
            # but keep markers self-consistent by updating the sha256 in the begin marker
            modified_lines = list(lines)
            # Find begin and end markers
            begin_idx = next(i for i, line in enumerate(lines) if "MEMINIT_PROTOCOL: begin" in line)
            end_idx = next(i for i, line in enumerate(lines) if "MEMINIT_PROTOCOL: end" in line)
            # Modify the managed payload
            modified_lines[begin_idx + 1] = modified_lines[begin_idx + 1] + " (old version)"
            # Recompute sha256 for the modified managed payload
            from meminit.core.services.protocol_assets import normalize_protocol_payload
            modified_payload = "\n".join(modified_lines[begin_idx + 1:end_idx])
            normalized = normalize_protocol_payload(modified_payload)
            import hashlib
            new_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            # Update the begin marker with new hash
            modified_lines[begin_idx] = modified_lines[begin_idx].replace(
                "sha256=" + lines[begin_idx].split("sha256=")[1][:64],
                "sha256=" + new_hash,
            )
            _write_asset(tmp_path, asset.id, "\n".join(modified_lines))
            continue
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "false", "expected_drifted": "1", "expected_stale": "agents-md"}


def setup_f07_tampered(tmp_path: Path) -> Dict[str, str]:
    """F07: Managed region edited — tampered."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "agents-md":
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            lines = canonical.split("\n")
            lines.insert(2, "TAMPERED LINE")
            _write_asset(tmp_path, asset.id, "\n".join(lines))
            continue
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "false", "expected_drifted": "1", "expected_tampered": "agents-md"}


def setup_f08_duplicate_begin_marker(tmp_path: Path) -> Dict[str, str]:
    """F08: Duplicate begin marker — unparseable."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "agents-md":
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            lines = canonical.split("\n")
            lines.insert(1, lines[0])  # duplicate begin marker
            _write_asset(tmp_path, asset.id, "\n".join(lines))
            continue
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "false", "expected_drifted": "0", "expected_unparseable": "agents-md"}


def setup_f09_missing_end_marker(tmp_path: Path) -> Dict[str, str]:
    """F09: Missing end marker — unparseable."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "agents-md":
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            lines = canonical.split("\n")
            filtered = [line for line in lines if "MEMINIT_PROTOCOL: end" not in line]
            _write_asset(tmp_path, asset.id, "\n".join(filtered))
            continue
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "false", "expected_drifted": "0", "expected_unparseable": "agents-md"}


def setup_f10_stale_with_user_content(tmp_path: Path) -> Dict[str, str]:
    """F10: Stale generated region with user content below it."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "agents-md":
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            lines = canonical.split("\n")
            end_idx = next(i for i, line in enumerate(lines) if "MEMINIT_PROTOCOL: end" in line)
            # Bump version to make it stale
            content_lines = list(lines[: end_idx + 1])
            content_lines[0] = content_lines[0].replace(
                f"version={PROTOCOL_ASSET_VERSION}", f"version={_PREVIOUS_VERSION}"
            )
            user_section = "\n## Custom\nUser notes here.\n"
            full_content = "\n".join(content_lines) + user_section
            _write_asset(tmp_path, asset.id, full_content)
            continue
        _write_canonical(tmp_path, asset)
    return {
        "expected_check_success": "false",
        "expected_drifted": "1",
        "expected_stale": "agents-md",
        "has_user_content": "true",
    }


def setup_f11_crlf_normalized(tmp_path: Path) -> Dict[str, str]:
    """F11: CRLF line endings — normalized to aligned."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        # Write with CRLF
        crlf_content = canonical.replace("\n", "\r\n")
        target = tmp_path / asset.target_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(crlf_content, encoding="utf-8")
        if asset.file_mode is not None:
            target.chmod(asset.file_mode)
    return {"expected_check_success": "true", "expected_drifted": "0"}


def setup_f12_trailing_whitespace_normalized(tmp_path: Path) -> Dict[str, str]:
    """F12: Trailing whitespace — normalized to aligned."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
        # Add trailing whitespace to each line
        lines = canonical.split("\n")
        padded = "\n".join(line + "  " for line in lines) + "\n"
        target = tmp_path / asset.target_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(padded, encoding="utf-8")
        if asset.file_mode is not None:
            target.chmod(asset.file_mode)
    return {"expected_check_success": "true", "expected_drifted": "0"}


def setup_f13_asset_filter(tmp_path: Path) -> Dict[str, str]:
    """F13: Multi-drift repo, filtered to single asset."""
    _setup_config(tmp_path)
    # Write all as legacy (no markers)
    _write_asset(tmp_path, "agents-md", "# Legacy\n")
    _write_asset(tmp_path, "meminit-docops-skill", "# Legacy skill\n")
    # Write brownfield script as canonical (aligned)
    registry = ProtocolAssetRegistry.default()
    asset = registry.get_by_id("meminit-brownfield-script")
    assert asset is not None
    _write_canonical(tmp_path, asset)
    return {
        "expected_check_success": "false",
        "expected_drifted": "2",
        "filter_asset": "agents-md",
        "filter_expected_drifted": "1",
    }


def setup_f16_preamble_before_begin(tmp_path: Path) -> Dict[str, str]:
    """F16: Preamble before begin marker — unparseable."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "agents-md":
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            # Insert preamble before begin marker
            lines = canonical.split("\n")
            lines.insert(0, "# User preamble\n")
            _write_asset(tmp_path, asset.id, "\n".join(lines))
            continue
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "false", "expected_drifted": "0", "expected_unparseable": "agents-md"}


def setup_f17_duplicate_end_marker(tmp_path: Path) -> Dict[str, str]:
    """F17: Duplicate end marker — unparseable."""
    _setup_config(tmp_path)
    registry = ProtocolAssetRegistry.default()
    for asset in registry.assets:
        if asset.id == "agents-md":
            canonical = asset.render(project_name="TestProject", repo_prefix="TEST")
            # Duplicate the end marker
            lines = canonical.split("\n")
            end_idx = next(i for i, line in enumerate(lines) if "MEMINIT_PROTOCOL: end" in line)
            lines.insert(end_idx + 1, lines[end_idx])
            _write_asset(tmp_path, asset.id, "\n".join(lines))
            continue
        _write_canonical(tmp_path, asset)
    return {"expected_check_success": "false", "expected_drifted": "0", "expected_unparseable": "agents-md"}


# Fixture registry: name → (setup_fn, description)
FIXTURE_SCENARIOS: Dict[str, tuple] = {
    "F01": (setup_f01_aligned, "Freshly-initialized, all aligned"),
    "F02": (setup_f02_missing_agents_md, "Missing AGENTS.md"),
    "F03": (setup_f03_missing_skill_manifest, "Missing skill manifest"),
    "F04": (setup_f04_legacy_agents_md, "Legacy AGENTS.md (no markers)"),
    "F05": (setup_f05_stale_version, "Stale version in marker"),
    "F06": (setup_f06_stale_hash, "Stale hash (canonical changed)"),
    "F07": (setup_f07_tampered, "Tampered managed region"),
    "F08": (setup_f08_duplicate_begin_marker, "Duplicate begin marker (unparseable)"),
    "F09": (setup_f09_missing_end_marker, "Missing end marker (unparseable)"),
    "F10": (setup_f10_stale_with_user_content, "Stale with user content below region"),
    "F11": (setup_f11_crlf_normalized, "CRLF normalized to aligned"),
    "F12": (setup_f12_trailing_whitespace_normalized, "Trailing whitespace normalized"),
    "F13": (setup_f13_asset_filter, "Asset filter on multi-drift repo"),
    "F16": (setup_f16_preamble_before_begin, "Preamble before begin marker (unparseable)"),
    "F17": (setup_f17_duplicate_end_marker, "Duplicate end marker (unparseable)"),
}
