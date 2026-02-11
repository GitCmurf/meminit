from __future__ import annotations

import json
from pathlib import Path

import yaml

from meminit.core.services.org_profiles import global_profile_dir, resolve_org_profile
from meminit.core.use_cases.init_repository import InitRepositoryUseCase
from meminit.core.use_cases.install_org_profile import InstallOrgProfileUseCase
from meminit.core.use_cases.org_status import OrgStatusUseCase
from meminit.core.use_cases.vendor_org_profile import VendorOrgProfileUseCase


def _xdg_env(tmp_path: Path) -> dict[str, str]:
    return {
        "XDG_CONFIG_HOME": str(tmp_path / "xdg-config"),
        "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
    }


def test_org_install_dry_run_does_not_write(tmp_path: Path):
    env = _xdg_env(tmp_path)
    report = InstallOrgProfileUseCase(env=env).execute(profile_name="default", dry_run=True)
    assert report.dry_run is True
    assert report.installed is False
    assert not (Path(report.target_dir) / "profile.json").exists()


def test_org_install_writes_profile_and_refuses_overwrite_without_force(tmp_path: Path):
    env = _xdg_env(tmp_path)
    use_case = InstallOrgProfileUseCase(env=env)

    first = use_case.execute(profile_name="default", dry_run=False)
    assert first.dry_run is False
    assert first.installed is True

    target = Path(first.target_dir)
    assert (target / "profile.json").exists()

    # Second install should refuse unless forced.
    second = use_case.execute(profile_name="default", dry_run=False, force=False)
    assert second.installed is False
    assert "already installed" in second.message.lower()

    forced = use_case.execute(profile_name="default", dry_run=False, force=True)
    assert forced.installed is True


def test_org_profile_resolution_prefers_global_when_present(tmp_path: Path):
    env = _xdg_env(tmp_path)

    # Create a custom global profile so we can distinguish it from the packaged one.
    root = global_profile_dir("default", env=env)
    root.mkdir(parents=True, exist_ok=True)

    manifest = {
        "profile_name": "default",
        "profile_version": "9.9",
        "docops_version": "2.0",
        "files": [
            "metadata.schema.json",
            "templates/template-001-adr.md",
            "templates/template-001-fdd.md",
            "templates/template-001-prd.md",
        ],
    }
    (root / "profile.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "metadata.schema.json").write_text(json.dumps({"$schema": "GLOBAL"}), encoding="utf-8")
    (root / "templates").mkdir(parents=True, exist_ok=True)
    (root / "templates/template-001-adr.md").write_text("ADR TEMPLATE (GLOBAL)\n", encoding="utf-8")
    (root / "templates/template-001-fdd.md").write_text("FDD TEMPLATE (GLOBAL)\n", encoding="utf-8")
    (root / "templates/template-001-prd.md").write_text("PRD TEMPLATE (GLOBAL)\n", encoding="utf-8")

    profile = resolve_org_profile(profile_name="default", env=env, prefer_global=True)
    assert profile.source == "global"
    assert profile.version == "9.9"
    assert profile.files["metadata.schema.json"] == b'{"$schema": "GLOBAL"}'


def test_org_vendor_writes_lock_and_refuses_overwrite_without_force(tmp_path: Path):
    env = _xdg_env(tmp_path)

    # Ensure there is a global profile installed (determinism: vendor should prefer it).
    InstallOrgProfileUseCase(env=env).execute(profile_name="default", dry_run=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    dry = VendorOrgProfileUseCase(root_dir=str(repo_root), env=env).execute(profile_name="default", dry_run=True)
    assert dry.dry_run is True
    assert not (repo_root / "docs/00-governance/metadata.schema.json").exists()

    applied = VendorOrgProfileUseCase(root_dir=str(repo_root), env=env).execute(profile_name="default", dry_run=False)
    assert applied.dry_run is False
    assert (repo_root / "docs/00-governance/metadata.schema.json").exists()
    assert (repo_root / ".meminit/org-profile.lock.json").exists()

    config = yaml.safe_load((repo_root / "docops.config.yaml").read_text(encoding="utf-8"))
    assert config.get("schema_path") == "docs/00-governance/metadata.schema.json"
    assert any(isinstance(ns, dict) and ns.get("repo_prefix") == "ORG" for ns in (config.get("namespaces") or []))

    refused = VendorOrgProfileUseCase(root_dir=str(repo_root), env=env).execute(profile_name="default", dry_run=False)
    assert "refusing" in refused.message.lower()

    forced = VendorOrgProfileUseCase(root_dir=str(repo_root), env=env).execute(profile_name="default", dry_run=False, force=True)
    assert forced.dry_run is False


def test_org_status_reports_lock_matches_current_profile(tmp_path: Path):
    env = _xdg_env(tmp_path)
    InstallOrgProfileUseCase(env=env).execute(profile_name="default", dry_run=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    VendorOrgProfileUseCase(root_dir=str(repo_root), env=env).execute(profile_name="default", dry_run=False)

    report = OrgStatusUseCase(root_dir=str(repo_root), env=env).execute(profile_name="default")
    assert report.global_installed is True
    assert report.repo_lock_present is True
    assert report.current_profile_source == "global"
    assert report.repo_lock_matches_current is True


def test_init_repository_uses_global_profile_when_installed(tmp_path: Path):
    env = _xdg_env(tmp_path)

    # Install a custom global profile that differs from the packaged default.
    root = global_profile_dir("default", env=env)
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "profile_name": "default",
        "profile_version": "1.2",
        "docops_version": "2.0",
        "files": [
            "metadata.schema.json",
            "templates/template-001-adr.md",
            "templates/template-001-fdd.md",
            "templates/template-001-prd.md",
        ],
    }
    (root / "profile.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "metadata.schema.json").write_text(json.dumps({"$schema": "FROM_GLOBAL"}), encoding="utf-8")
    (root / "templates").mkdir(parents=True, exist_ok=True)
    (root / "templates/template-001-adr.md").write_text("ADR TEMPLATE\n", encoding="utf-8")
    (root / "templates/template-001-fdd.md").write_text("FDD TEMPLATE\n", encoding="utf-8")
    (root / "templates/template-001-prd.md").write_text("PRD TEMPLATE\n", encoding="utf-8")

    repo_root = tmp_path / "new-repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    InitRepositoryUseCase(root_dir=str(repo_root), env=env).execute()

    schema = repo_root / "docs/00-governance/metadata.schema.json"
    assert schema.exists()
    assert "FROM_GLOBAL" in schema.read_text(encoding="utf-8")


def test_org_vendor_refuses_symlink_escape(tmp_path: Path):
    import pytest

    env = _xdg_env(tmp_path)
    InstallOrgProfileUseCase(env=env).execute(profile_name="default", dry_run=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    outside_docs = tmp_path / "outside-docs"
    outside_docs.mkdir(parents=True, exist_ok=True)
    (repo_root / "docs").symlink_to(outside_docs, target_is_directory=True)

    with pytest.raises(ValueError):
        VendorOrgProfileUseCase(root_dir=str(repo_root), env=env).execute(
            profile_name="default", dry_run=False
        )
