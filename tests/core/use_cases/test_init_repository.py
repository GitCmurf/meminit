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
    assert "# Agentic Coding Rules" in agents
    assert "docs/45-adr/" in agents
    assert "docs/00-governance/templates/template-001-adr.md" in agents
    assert config["repo_prefix"] in agents

    template_content = (
        resources.files("meminit.core.assets")
        .joinpath("AGENTS.md")
        .read_text(encoding="utf-8")
        .replace("{{PROJECT_NAME}}", config["project_name"])
        .replace("{{REPO_PREFIX}}", config["repo_prefix"])
    )
    assert agents == template_content

    # Check Schema Existence
    schema_path = empty_repo / "docs/00-governance/metadata.schema.json"
    assert schema_path.exists()
    assert "$schema" in schema_path.read_text()
    assert "docops.config.yaml" in report.created_paths
    assert "AGENTS.md" in report.created_paths
    assert "docs/00-governance" in report.created_paths


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
