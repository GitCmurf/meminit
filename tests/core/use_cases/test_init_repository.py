from importlib import resources
from pathlib import Path

import pytest
import yaml

from meminit.core.services.error_codes import MeminitError
from meminit.core.services.protocol_assets import ProtocolAsset, ProtocolAssetRegistry
from meminit.core.services.repo_config import derive_repo_prefix
from meminit.core.use_cases.check_repository import CheckRepositoryUseCase
from meminit.core.use_cases.init_repository import InitRepositoryUseCase


@pytest.fixture
def empty_repo(tmp_path):
    return tmp_path


def test_init_creates_structure(empty_repo):
    use_case = InitRepositoryUseCase(str(empty_repo))
    report = use_case.execute()

    # Check Directories
    assert (empty_repo / "docs").is_dir()
    assert (empty_repo / "docs/00-governance").is_dir()
    assert (empty_repo / "docs/45-adr").is_dir()
    assert (empty_repo / "docs/10-prd").is_dir()
    assert (empty_repo / "docs/20-specs").is_dir()
    assert (empty_repo / "docs/30-design").is_dir()

    # Check Files
    assert (empty_repo / "docops.config.yaml").exists()
    assert (empty_repo / ".gitignore").exists()
    assert (empty_repo / "AGENTS.md").exists()

    # Check Config Content
    config = yaml.safe_load((empty_repo / "docops.config.yaml").read_text())
    assert config.get("project_name")
    assert config.get("repo_prefix")

    # Check AGENTS.md content
    agents = (empty_repo / "AGENTS.md").read_text()
    assert "Meminit DocOps" in agents
    assert "{{PROJECT_NAME}}" not in agents
    assert "{{REPO_PREFIX}}" not in agents
    assert config["repo_prefix"] in agents

    # Check Schema Existence
    schema_path = empty_repo / "docs/00-governance/metadata.schema.json"
    assert schema_path.exists()
    assert "$schema" in schema_path.read_text()
    assert "docops.config.yaml" in report.created_paths
    assert ".gitignore" in report.created_paths
    assert "AGENTS.md" in report.created_paths
    assert "docs/00-governance" in report.created_paths
    assert ".meminit/cache/" in (empty_repo / ".gitignore").read_text(encoding="utf-8")


def test_init_appends_meminit_cache_to_existing_gitignore(empty_repo):
    (empty_repo / ".gitignore").write_text("dist/\n", encoding="utf-8")
    report = InitRepositoryUseCase(str(empty_repo)).execute()

    gitignore = (empty_repo / ".gitignore").read_text(encoding="utf-8")
    assert "dist/" in gitignore
    assert ".meminit/cache/" in gitignore
    assert ".gitignore" in report.created_paths


def test_init_creates_12_notes_directory(empty_repo):
    use_case = InitRepositoryUseCase(str(empty_repo))
    report = use_case.execute()

    assert (empty_repo / "docs/12-notes").is_dir()
    assert "docs/12-notes" in report.created_paths


def test_init_creates_agent_skills_directory(empty_repo):
    use_case = InitRepositoryUseCase(str(empty_repo))
    use_case.execute()

    # Codex expects .agents/skills/
    skill_path = empty_repo / ".agents/skills/meminit-docops/SKILL.md"
    assert skill_path.exists()
    assert "meminit-docops" in skill_path.read_text()

    # Verify brownfield helper script is installed with executable permissions
    script_path = (
        empty_repo / ".agents/skills/meminit-docops/scripts/meminit_brownfield_plan.sh"
    )
    assert script_path.exists()
    assert script_path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
    # Check script is executable (owner has execute permission)
    assert script_path.stat().st_mode & 0o100 != 0


def test_init_installs_gov_001_constitution(empty_repo):
    use_case = InitRepositoryUseCase(str(empty_repo))
    use_case.execute()

    constitution_path = empty_repo / "docs/00-governance/docops-constitution.md"
    assert constitution_path.exists()
    content = constitution_path.read_text()
    assert "DocOps Constitution" in content
    config = yaml.safe_load((empty_repo / "docops.config.yaml").read_text())
    repo_prefix = config["repo_prefix"]
    assert f"{repo_prefix}-GOV-001" in content


def test_init_idempotent(empty_repo):
    use_case = InitRepositoryUseCase(str(empty_repo))
    use_case.execute()

    # Run again, should not fail
    report = use_case.execute()

    assert (empty_repo / "docops.config.yaml").exists()
    assert report.created_paths == []


def test_init_raises_when_docs_subdir_is_file(empty_repo):
    docs_dir = empty_repo / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    conflict = docs_dir / "00-governance"
    conflict.write_text("not a directory", encoding="utf-8")

    use_case = InitRepositoryUseCase(str(empty_repo))
    with pytest.raises(FileExistsError):
        use_case.execute()


def test_init_refuses_symlink_escape(tmp_path: Path):
    from meminit.core.services.error_codes import ErrorCode, MeminitError

    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(parents=True, exist_ok=True)

    # If a repo contains a symlinked docs root, init must refuse to write outside the repo.
    (tmp_path / "docs").symlink_to(outside, target_is_directory=True)

    use_case = InitRepositoryUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.execute()
    assert exc_info.value.code == ErrorCode.PATH_ESCAPE


def test_init_derives_repo_prefix_from_dir_name(tmp_path: Path):
    """derive_repo_prefix is used when config doesn't exist yet."""
    repo_dir = tmp_path / "myproject"
    repo_dir.mkdir()
    use_case = InitRepositoryUseCase(str(repo_dir))
    use_case.execute()

    config = yaml.safe_load((repo_dir / "docops.config.yaml").read_text())
    assert config["repo_prefix"] == "MYPROJECT"


def test_init_short_dir_name_falls_back_to_REPO(tmp_path: Path):
    """derive_repo_prefix returns 'REPO' for names shorter than 3 chars."""
    repo_dir = tmp_path / "ab"
    repo_dir.mkdir()
    use_case = InitRepositoryUseCase(str(repo_dir))
    use_case.execute()

    config = yaml.safe_load((repo_dir / "docops.config.yaml").read_text())
    assert config["repo_prefix"] == "REPO"


def test_init_writes_canonical_protocol_assets(empty_repo):
    """All protocol assets from the registry must match canonical renders after init."""
    use_case = InitRepositoryUseCase(str(empty_repo))
    use_case.execute()

    config = yaml.safe_load((empty_repo / "docops.config.yaml").read_text())
    project_name = config["project_name"]
    repo_prefix = config["repo_prefix"]
    registry = ProtocolAssetRegistry.default()

    for asset in registry.assets:
        target = empty_repo / asset.target_path
        assert target.exists(), f"Missing protocol asset: {asset.target_path}"

        canonical = asset.render(project_name=project_name, repo_prefix=repo_prefix)
        on_disk = target.read_text(encoding="utf-8")
        assert on_disk == canonical, (
            f"Asset {asset.id} on-disk content does not match canonical render"
        )


def test_init_agents_md_has_protocol_markers(empty_repo):
    """AGENTS.md must contain MEMINIT_PROTOCOL begin/end markers after init."""
    use_case = InitRepositoryUseCase(str(empty_repo))
    use_case.execute()

    agents = (empty_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "MEMINIT_PROTOCOL: begin" in agents
    assert "MEMINIT_PROTOCOL: end" in agents
    assert "id=agents-md" in agents
    assert "version=1.0" in agents
    assert "sha256=" in agents


def test_init_agents_md_fallback_stays_protocol_governed(monkeypatch, empty_repo):
    """If mixed-asset rendering fails, init must still write protocol markers."""
    original_render = ProtocolAsset.render

    def fake_render(self, *args, **kwargs):
        if self.id == "agents-md":
            raise OSError("simulated render failure")
        return original_render(self, *args, **kwargs)

    monkeypatch.setattr(ProtocolAsset, "render", fake_render)

    use_case = InitRepositoryUseCase(str(empty_repo))
    report = use_case.execute()

    agents = (empty_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "MEMINIT_PROTOCOL: begin" in agents
    assert "MEMINIT_PROTOCOL: end" in agents
    assert "id=agents-md" in agents
    assert "version=1.0" in agents
    assert "sha256=" in agents
    assert "AGENTS.md" in report.created_paths


def test_init_brownfield_script_is_executable(empty_repo):
    """Brownfield helper script must have executable permission set via registry."""
    use_case = InitRepositoryUseCase(str(empty_repo))
    use_case.execute()

    registry = ProtocolAssetRegistry.default()
    script_asset = registry.get_by_id("meminit-brownfield-script")
    assert script_asset is not None

    target = empty_repo / script_asset.target_path
    assert target.exists()
    actual_mode = target.stat().st_mode & 0o777
    assert actual_mode == script_asset.file_mode, (
        f"Expected mode {oct(script_asset.file_mode)}, got {oct(actual_mode)}"
    )


# --- Golden-path fixes (greenfield dogfood run #0) ---


def test_fresh_init_passes_check_cleanly(empty_repo):
    """A freshly initialized repo must pass check with zero violations AND zero warnings."""
    InitRepositoryUseCase(str(empty_repo)).execute()

    result = CheckRepositoryUseCase(root_dir=str(empty_repo)).execute_full_summary()

    assert result.violations_count == 0, result.violations
    assert result.warnings_count == 0, result.warnings


def test_init_constitution_filename_is_kebab_case(empty_repo):
    """The scaffolded constitution must use a kebab-case filename, not PascalCase/underscore."""
    InitRepositoryUseCase(str(empty_repo)).execute()

    gov = empty_repo / "docs/00-governance"
    assert (gov / "docops-constitution.md").exists()
    assert not (gov / "DocOps_Constitution.md").exists()


def test_init_accepts_explicit_repo_prefix(tmp_path: Path):
    """An explicit repo_prefix must be used in config and stamped into the constitution ID."""
    repo = tmp_path / "bedtime-alexa"
    repo.mkdir()

    InitRepositoryUseCase(str(repo), repo_prefix="BEDTIME").execute()

    config = yaml.safe_load((repo / "docops.config.yaml").read_text())
    assert config["repo_prefix"] == "BEDTIME"
    content = (repo / "docs/00-governance/docops-constitution.md").read_text()
    assert "BEDTIME-GOV-001" in content


def test_init_explicit_prefix_is_normalized(tmp_path: Path):
    """A lowercase explicit prefix is normalized to uppercase."""
    repo = tmp_path / "proj"
    repo.mkdir()

    InitRepositoryUseCase(str(repo), repo_prefix="bedtime").execute()

    config = yaml.safe_load((repo / "docops.config.yaml").read_text())
    assert config["repo_prefix"] == "BEDTIME"


def test_init_rejects_invalid_repo_prefix(tmp_path: Path):
    """An explicit prefix that cannot satisfy the ID schema must be rejected."""
    repo = tmp_path / "proj"
    repo.mkdir()

    with pytest.raises(MeminitError):
        InitRepositoryUseCase(str(repo), repo_prefix="A1").execute()


def test_derive_repo_prefix_uses_word_boundaries():
    """Derivation should prefer whole words over a mid-word truncation."""
    assert derive_repo_prefix("bedtime-alexa") == "BEDTIME"


def test_derive_repo_prefix_preserves_existing_cases():
    """Existing derivation contracts must still hold."""
    assert derive_repo_prefix("myproject") == "MYPROJECT"
    assert derive_repo_prefix("ab") == "REPO"
