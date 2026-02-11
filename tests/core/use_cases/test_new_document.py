from pathlib import Path

import frontmatter
import pytest
import yaml

from meminit.core.use_cases.init_repository import InitRepositoryUseCase
from meminit.core.use_cases.new_document import NewDocumentUseCase


@pytest.fixture
def repo_with_init(tmp_path):
    InitRepositoryUseCase(str(tmp_path)).execute()
    return tmp_path


def test_new_adr_creates_file(repo_with_init):
    use_case = NewDocumentUseCase(str(repo_with_init))
    config = yaml.safe_load((repo_with_init / "docops.config.yaml").read_text())
    repo_prefix = config["repo_prefix"]

    # 1. Create first ADR
    doc_path = use_case.execute("ADR", "My First Decision")

    # Check filename
    assert doc_path.name == "adr-001-my-first-decision.md"
    assert "00-governance/templates/adr.md" not in str(doc_path)  # Should be in 45-adr

    # Check content
    content = doc_path.read_text()
    assert f"# {repo_prefix}-ADR-001: My First Decision" in content
    assert f"document_id: {repo_prefix}-ADR-001" in content
    post = frontmatter.load(doc_path)
    assert post.metadata.get("docops_version") == "2.0"


def test_new_prd_auto_increment_id(repo_with_init):
    use_case = NewDocumentUseCase(str(repo_with_init))
    config = yaml.safe_load((repo_with_init / "docops.config.yaml").read_text())
    repo_prefix = config["repo_prefix"]

    # Manually create PRD-001
    prd_dir = repo_with_init / "docs/10-prd"
    (prd_dir / "prd-001-fake.md").write_text(f"---\ndocument_id: {repo_prefix}-PRD-001\n---")

    # 2. Create second PRD
    doc_path = use_case.execute("PRD", "Second Product")

    assert doc_path.name == "prd-002-second-product.md"
    content = doc_path.read_text()
    assert f"document_id: {repo_prefix}-PRD-002" in content


def test_new_refuses_symlink_escape(tmp_path: Path):
    InitRepositoryUseCase(str(tmp_path)).execute()

    outside = tmp_path / "outside-docs"
    outside.mkdir(parents=True, exist_ok=True)

    real_docs = tmp_path / "docs"
    real_docs.rename(tmp_path / "docs-real")
    real_docs.symlink_to(outside, target_is_directory=True)

    use_case = NewDocumentUseCase(str(tmp_path))
    with pytest.raises(ValueError):
        use_case.execute("ADR", "Symlink Escape")


def test_new_fdd_uses_template(repo_with_init):
    use_case = NewDocumentUseCase(str(repo_with_init))

    doc_path = use_case.execute("FDD", "Feature ABC")

    content = doc_path.read_text()
    assert "# FDD: Feature ABC" in content
    assert "## Feature Description" in content


def test_unknown_type_fails(repo_with_init):
    use_case = NewDocumentUseCase(str(repo_with_init))
    with pytest.raises(ValueError):
        use_case.execute("UNKNOWN", "Fail")


def test_new_adr_template_angle_bracket_placeholders(tmp_path):
    # Minimal config + custom template that uses legacy placeholder tokens.
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    template = tmp_path / "docs" / "00-governance" / "templates" / "custom-adr.md"
    template.write_text(
        "# <REPO>-ADR-<SEQ>: <Decision Title>\n\n- Date: <YYYY-MM-DD>\n- Owner: <Team or Person>\n"
    )

    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Meminit
repo_prefix: MEMINIT
docops_version: '2.0'
templates:
  adr: docs/00-governance/templates/custom-adr.md
"""
    )

    use_case = NewDocumentUseCase(str(tmp_path))
    doc_path = use_case.execute("ADR", "Placeholder Substitution Works")
    content = doc_path.read_text()
    assert "MEMINIT-ADR-001" in content
    assert "Placeholder Substitution Works" in content
    assert "Owner: __TBD__" in content


def test_new_uses_uppercase_template_key(tmp_path):
    # Uppercase keys in docops.config.yaml should be honored (case-insensitive template lookup).
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    template = tmp_path / "docs" / "00-governance" / "templates" / "custom-adr.md"
    template.write_text("# ADR: {title}\n\n## Custom Template Marker\n", encoding="utf-8")

    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
repo_prefix: EXAMPLE
docops_version: '2.0'
templates:
  ADR: docs/00-governance/templates/custom-adr.md
""",
        encoding="utf-8",
    )

    use_case = NewDocumentUseCase(str(tmp_path))
    doc_path = use_case.execute("ADR", "Uses Uppercase Key")
    content = doc_path.read_text(encoding="utf-8")
    assert "## Custom Template Marker" in content


def test_new_does_not_overwrite_existing_file(repo_with_init, monkeypatch):
    use_case = NewDocumentUseCase(str(repo_with_init))
    first = use_case.execute("ADR", "Unique Title")
    post = frontmatter.load(first)
    existing_id = post.metadata["document_id"]

    # Force the same ID to be generated again to guarantee the same target path.
    monkeypatch.setattr(use_case, "_generate_id", lambda _doc_type, _target_dir, _ns: existing_id)
    with pytest.raises(FileExistsError):
        use_case.execute("ADR", "Unique Title")


def test_new_uses_configured_type_directory(tmp_path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "templates" / "custom-adr.md").write_text(
        "# ADR: {title}\n"
    )

    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
repo_prefix: EXAMPLE
docops_version: '2.0'
docs_root: docs
type_directories:
  ADR: adrs
templates:
  adr: docs/00-governance/templates/custom-adr.md
"""
    )

    use_case = NewDocumentUseCase(str(tmp_path))
    doc_path = use_case.execute("ADR", "Goes To ADRs Folder")
    assert str(doc_path).replace("\\", "/").endswith("/docs/adrs/adr-001-goes-to-adrs-folder.md")


def test_new_title_slug_fallback_when_empty(repo_with_init):
    use_case = NewDocumentUseCase(str(repo_with_init))
    doc_path = use_case.execute("ADR", "@#$%")
    assert doc_path.name.startswith("adr-001-")
    assert doc_path.name.endswith("-untitled.md")


def test_new_can_target_namespace(tmp_path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "packages" / "phyla" / "docs").mkdir(parents=True)

    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
namespaces:
  - name: root
    repo_prefix: AIDHA
    docs_root: docs
  - name: phyla
    repo_prefix: PHYLA
    docs_root: packages/phyla/docs
""",
        encoding="utf-8",
    )

    use_case = NewDocumentUseCase(str(tmp_path))
    doc_path = use_case.execute("ADR", "Package ADR", namespace="phyla")
    normalized = str(doc_path).replace("\\", "/")
    assert "/packages/phyla/docs/" in normalized
    assert doc_path.name.startswith("adr-001-")
    content = doc_path.read_text(encoding="utf-8")
    assert "document_id: PHYLA-ADR-001" in content
