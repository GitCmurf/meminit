from importlib import resources
from pathlib import Path

import pytest
import yaml

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
    assert "AGENTS.md" in report.created_paths
    assert "docs/00-governance" in report.created_paths


def test_init_creates_12_notes_directory(empty_repo):
    use_case = InitRepositoryUseCase(str(empty_repo))
    report = use_case.execute()

    assert (empty_repo / "docs/12-notes").is_dir()
    assert "docs/12-notes" in report.created_paths


def test_init_creates_agent_skills_directory(empty_repo):
    use_case = InitRepositoryUseCase(str(empty_repo))
    report = use_case.execute()

    # Codex expects .agents/skills/
    skill_path = empty_repo / ".agents/skills/meminit-docops/SKILL.md"
    assert skill_path.exists()
    assert "meminit-docops" in skill_path.read_text()


def test_init_installs_gov_001_constitution(empty_repo):
    use_case = InitRepositoryUseCase(str(empty_repo))
    report = use_case.execute()

    constitution_path = empty_repo / "docs/00-governance/DocOps_Constitution.md"
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
