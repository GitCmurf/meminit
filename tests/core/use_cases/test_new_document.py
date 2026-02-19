import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None
import frontmatter
import pytest
import yaml

from meminit.core.domain.entities import NewDocumentParams, NewDocumentResult
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.use_cases.init_repository import InitRepositoryUseCase
from meminit.core.use_cases.new_document import NewDocumentUseCase


@pytest.fixture
def repo_with_init(tmp_path):
    InitRepositoryUseCase(str(tmp_path)).execute()
    return tmp_path


SCHEMA_JSON = """{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://meminit.io/schemas/metadata.schema.json",
  "title": "Test Schema",
  "type": "object",
  "required": ["document_id", "type", "title", "status", "owner"],
  "properties": {
    "document_id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": { "type": "string" },
    "version": { "type": "string" },
    "last_updated": { "type": "string" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" },
    "area": { "type": "string" },
    "description": { "type": "string" },
    "keywords": { "type": "array", "items": { "type": "string" } },
    "related_ids": { "type": "array", "items": { "type": "string" } },
    "superseded_by": { "type": "string" }
  },
  "additionalProperties": true
}
"""


@pytest.fixture
def repo_with_config_and_template(tmp_path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "templates" / "adr.md").write_text(
        "# ADR: {title}\n\n## Context\n"
    )
    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
        SCHEMA_JSON, encoding="utf-8"
    )
    (tmp_path / "docops.config.yaml").write_text(
        """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
templates:
  adr: docs/00-governance/templates/adr.md
type_directories:
  ADR: 45-adr
"""
    )
    (tmp_path / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)
    return tmp_path


class TestNewDocumentParams:
    def test_instantiation_with_required_fields(self):
        params = NewDocumentParams(doc_type="ADR", title="Test Decision")
        assert params.doc_type == "ADR"
        assert params.title == "Test Decision"
        assert params.status == "Draft"
        assert params.dry_run is False
        assert params.namespace is None
        assert params.owner is None
        assert params.area is None
        assert params.description is None
        assert params.keywords is None
        assert params.related_ids is None
        assert params.document_id is None

    def test_instantiation_with_all_fields(self):
        params = NewDocumentParams(
            doc_type="PRD",
            title="Full Test",
            namespace="phyla",
            owner="Alice",
            area="Backend",
            description="A test document",
            status="In Review",
            keywords=["api", "test"],
            related_ids=["TEST-ADR-001"],
            document_id="TEST-PRD-042",
            dry_run=True,
        )
        assert params.doc_type == "PRD"
        assert params.title == "Full Test"
        assert params.namespace == "phyla"
        assert params.owner == "Alice"
        assert params.area == "Backend"
        assert params.description == "A test document"
        assert params.status == "In Review"
        assert params.keywords == ["api", "test"]
        assert params.related_ids == ["TEST-ADR-001"]
        assert params.document_id == "TEST-PRD-042"
        assert params.dry_run is True


class TestNewDocumentResult:
    def test_instantiation_success_result(self):
        result = NewDocumentResult(
            success=True,
            path=Path("/tmp/test.md"),
            document_id="TEST-ADR-001",
            doc_type="ADR",
            title="Test",
            status="Draft",
            version="0.1",
            owner="Bob",
            area="Frontend",
            last_updated="2024-01-15",
            docops_version="2.0",
            description="Description",
            keywords=["key"],
            related_ids=["TEST-PRD-001"],
            dry_run=False,
        )
        assert result.success is True
        assert result.path == Path("/tmp/test.md")
        assert result.document_id == "TEST-ADR-001"
        assert result.owner == "Bob"
        assert result.area == "Frontend"
        assert result.description == "Description"
        assert result.keywords == ["key"]
        assert result.related_ids == ["TEST-PRD-001"]
        assert result.dry_run is False
        assert result.content is None
        assert result.error is None

    def test_instantiation_failure_result(self):
        error = MeminitError(
            code=ErrorCode.INVALID_STATUS,
            message="Invalid status",
            details={"status": "Invalid"},
        )
        result = NewDocumentResult(
            success=False,
            doc_type="ADR",
            title="Test",
            status="Invalid",
            owner="Alice",
            area=None,
            description=None,
            keywords=None,
            related_ids=None,
            dry_run=False,
            error=error,
        )
        assert result.success is False
        assert result.error.code == ErrorCode.INVALID_STATUS


class TestStatusValidation:
    def test_valid_status_draft(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", status="Draft")
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert result.status == "Draft"

    def test_valid_status_in_review(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", status="In Review")
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert result.status == "In Review"

    def test_valid_status_approved(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", status="Approved")
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert result.status == "Approved"

    def test_valid_status_superseded(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", status="Superseded")
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert result.status == "Superseded"

    def test_invalid_status_raises_error(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", status="Invalid")
        result = use_case.execute_with_params(params)
        assert result.success is False
        assert result.error.code == ErrorCode.INVALID_STATUS
        assert "Invalid status" in result.error.message

    def test_invalid_status_lowercase_raises_error(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", status="draft")
        result = use_case.execute_with_params(params)
        assert result.success is False
        assert result.error.code == ErrorCode.INVALID_STATUS


class TestRelatedIdsValidation:
    def test_valid_related_ids_single(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", related_ids=["TEST-ADR-001"])
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert result.related_ids == ["TEST-ADR-001"]

    def test_valid_related_ids_multiple(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(
            doc_type="ADR",
            title="Test",
            related_ids=["TEST-ADR-001", "TEST-PRD-042", "MEMINIT-GOV-003"],
        )
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert len(result.related_ids) == 3

    def test_invalid_related_id_format_raises_error(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", related_ids=["invalid-id"])
        result = use_case.execute_with_params(params)
        assert result.success is False
        assert result.error.code == ErrorCode.INVALID_RELATED_ID
        assert "invalid-id" in result.error.message

    def test_invalid_related_id_lowercase_raises_error(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", related_ids=["test-adr-001"])
        result = use_case.execute_with_params(params)
        assert result.success is False
        assert result.error.code == ErrorCode.INVALID_RELATED_ID

    def test_invalid_related_id_missing_segment_raises_error(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", related_ids=["TEST-ADR"])
        result = use_case.execute_with_params(params)
        assert result.success is False
        assert result.error.code == ErrorCode.INVALID_RELATED_ID

    def test_empty_related_ids_is_valid(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", related_ids=[])
        result = use_case.execute_with_params(params)
        assert result.success is True


class TestOwnerResolutionChain:
    def test_cli_flag_takes_precedence(self, repo_with_config_and_template, monkeypatch):
        monkeypatch.setenv("MEMINIT_DEFAULT_OWNER", "EnvOwner")
        (repo_with_config_and_template / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
default_owner: ConfigOwner
templates:
  adr: docs/00-governance/templates/adr.md
type_directories:
  ADR: 45-adr
"""
        )
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", owner="CliOwner")
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert result.owner == "CliOwner"

    def test_environment_variable_works(self, repo_with_config_and_template, monkeypatch):
        monkeypatch.setenv("MEMINIT_DEFAULT_OWNER", "EnvOwner")
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test")
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert result.owner == "EnvOwner"

    def test_config_file_default_owner_works(self, repo_with_config_and_template, monkeypatch):
        monkeypatch.delenv("MEMINIT_DEFAULT_OWNER", raising=False)
        (repo_with_config_and_template / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
default_owner: ConfigOwner
templates:
  adr: docs/00-governance/templates/adr.md
type_directories:
  ADR: 45-adr
"""
        )
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test")
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert result.owner == "ConfigOwner"

    def test_falls_back_to_tbd(self, repo_with_config_and_template, monkeypatch):
        monkeypatch.delenv("MEMINIT_DEFAULT_OWNER", raising=False)
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test")
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert result.owner == "__TBD__"


class TestDeterministicIdMode:
    def test_id_flag_works_with_matching_type(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", document_id="TEST-ADR-042")
        result = use_case.execute_with_params(params)
        assert result.success is True
        assert result.document_id == "TEST-ADR-042"

        doc_path = repo_with_config_and_template / "docs" / "45-adr" / "adr-042-test.md"
        assert doc_path.exists()

    def test_id_flag_with_mismatched_type_raises_error(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", document_id="TEST-PRD-042")
        result = use_case.execute_with_params(params)
        assert result.success is False
        assert result.error.code == ErrorCode.INVALID_ID_FORMAT
        assert "PRD" in result.error.message
        assert "ADR" in result.error.message

    def test_id_flag_with_wrong_prefix_raises_error(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", document_id="WRONG-ADR-042")
        result = use_case.execute_with_params(params)
        assert result.success is False
        assert result.error.code == ErrorCode.INVALID_ID_FORMAT
        assert "prefix segment" in result.error.message
        assert result.error.details["expected_prefix"] == "TEST"

    def test_id_flag_with_existing_id_allows_idempotent_create(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))

        params1 = NewDocumentParams(doc_type="ADR", title="Same Title", document_id="TEST-ADR-001")
        result1 = use_case.execute_with_params(params1)
        assert result1.success is True

        params2 = NewDocumentParams(doc_type="ADR", title="Same Title", document_id="TEST-ADR-001")
        result2 = use_case.execute_with_params(params2)
        assert result2.success is True

    def test_id_flag_allows_last_updated_differences(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))

        params1 = NewDocumentParams(doc_type="ADR", title="Same Title", document_id="TEST-ADR-004")
        result1 = use_case.execute_with_params(params1)
        assert result1.success is True

        doc_path = repo_with_config_and_template / "docs" / "45-adr" / "adr-004-same-title.md"
        content = doc_path.read_text(encoding="utf-8")
        updated = re.sub(
            r"last_updated: ['\"]?\d{4}-\d{2}-\d{2}['\"]?",
            "last_updated: '2020-01-01'",
            content,
            count=1,
        )
        doc_path.write_text(updated, encoding="utf-8")

        params2 = NewDocumentParams(doc_type="ADR", title="Same Title", document_id="TEST-ADR-004")
        result2 = use_case.execute_with_params(params2)
        assert result2.success is True
        assert result2.last_updated == "2020-01-01"

    def test_id_flag_with_existing_id_different_content_raises_error(
        self, repo_with_config_and_template
    ):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))

        params1 = NewDocumentParams(
            doc_type="ADR",
            title="Same Title",
            document_id="TEST-ADR-002",
            owner="owner1",
        )
        result1 = use_case.execute_with_params(params1)
        assert result1.success is True

        params2 = NewDocumentParams(
            doc_type="ADR",
            title="Same Title",
            document_id="TEST-ADR-002",
            owner="owner2",
        )
        result2 = use_case.execute_with_params(params2)
        assert result2.success is False
        assert result2.error.code == ErrorCode.FILE_EXISTS

    def test_id_flag_with_existing_id_different_title_raises_duplicate(
        self, repo_with_config_and_template
    ):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))

        params1 = NewDocumentParams(
            doc_type="ADR",
            title="Old Title",
            document_id="TEST-ADR-003",
        )
        result1 = use_case.execute_with_params(params1)
        assert result1.success is True

        params2 = NewDocumentParams(
            doc_type="ADR",
            title="New Title",
            document_id="TEST-ADR-003",
        )
        result2 = use_case.execute_with_params(params2)
        assert result2.success is False
        assert result2.error.code == ErrorCode.DUPLICATE_ID

    def test_id_flag_with_invalid_format_raises_error(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", document_id="invalid-id-format")
        result = use_case.execute_with_params(params)
        assert result.success is False
        assert result.error.code == ErrorCode.INVALID_ID_FORMAT


class TestDryRunMode:
    def test_no_file_is_created(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Dry Run Test", dry_run=True)
        result = use_case.execute_with_params(params)

        assert result.success is True
        doc_path = repo_with_config_and_template / "docs" / "45-adr" / "adr-001-dry-run-test.md"
        assert not doc_path.exists()

    def test_content_is_returned_in_result(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Dry Run Test", dry_run=True)
        result = use_case.execute_with_params(params)

        assert result.success is True
        assert result.content is not None
        assert "---" in result.content
        assert "document_id:" in result.content
        assert "Dry Run Test" in result.content

    def test_result_has_dry_run_true(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Dry Run Test", dry_run=True)
        result = use_case.execute_with_params(params)

        assert result.success is True
        assert result.dry_run is True

    def test_dry_run_with_extended_metadata(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(
            doc_type="ADR",
            title="Extended Dry Run",
            owner="TestOwner",
            area="Backend",
            description="Test description",
            keywords=["api", "test"],
            related_ids=["TEST-PRD-001"],
            dry_run=True,
        )
        result = use_case.execute_with_params(params)

        assert result.success is True
        assert result.owner == "TestOwner"
        assert result.area == "Backend"
        assert result.description == "Test description"
        assert result.keywords == ["api", "test"]
        assert result.related_ids == ["TEST-PRD-001"]


class TestExtendedMetadataFields:
    def test_owner_is_included_in_frontmatter(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", owner="Alice Smith")
        result = use_case.execute_with_params(params)

        assert result.success is True
        post = frontmatter.load(result.path)
        assert post.metadata.get("owner") == "Alice Smith"

    def test_area_is_included_when_provided(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Test", area="Backend Services")
        result = use_case.execute_with_params(params)

        assert result.success is True
        post = frontmatter.load(result.path)
        assert post.metadata.get("area") == "Backend Services"

    def test_description_is_included_when_provided(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(
            doc_type="ADR", title="Test", description="This is a detailed description."
        )
        result = use_case.execute_with_params(params)

        assert result.success is True
        post = frontmatter.load(result.path)
        assert post.metadata.get("description") == "This is a detailed description."

    def test_keywords_array_is_included_when_provided(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(
            doc_type="ADR", title="Test", keywords=["api", "database", "migration"]
        )
        result = use_case.execute_with_params(params)

        assert result.success is True
        post = frontmatter.load(result.path)
        assert post.metadata.get("keywords") == ["api", "database", "migration"]

    def test_related_ids_array_is_included_when_provided(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(
            doc_type="ADR", title="Test", related_ids=["TEST-PRD-001", "TEST-FDD-002"]
        )
        result = use_case.execute_with_params(params)

        assert result.success is True
        post = frontmatter.load(result.path)
        assert post.metadata.get("related_ids") == ["TEST-PRD-001", "TEST-FDD-002"]

    def test_all_extended_metadata_together(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(
            doc_type="ADR",
            title="Complete Test",
            owner="Bob Jones",
            area="Infrastructure",
            description="Complete metadata test",
            keywords=["ci", "cd", "deployment"],
            related_ids=["TEST-ADR-001"],
        )
        result = use_case.execute_with_params(params)

        assert result.success is True
        post = frontmatter.load(result.path)
        assert post.metadata.get("owner") == "Bob Jones"
        assert post.metadata.get("area") == "Infrastructure"
        assert post.metadata.get("description") == "Complete metadata test"
        assert post.metadata.get("keywords") == ["ci", "cd", "deployment"]
        assert post.metadata.get("related_ids") == ["TEST-ADR-001"]

    def test_optional_fields_absent_when_not_provided(self, repo_with_config_and_template):
        use_case = NewDocumentUseCase(str(repo_with_config_and_template))
        params = NewDocumentParams(doc_type="ADR", title="Minimal Test")
        result = use_case.execute_with_params(params)

        assert result.success is True
        post = frontmatter.load(result.path)
        assert "area" not in post.metadata
        assert "description" not in post.metadata
        assert "keywords" not in post.metadata
        assert "related_ids" not in post.metadata


def test_new_adr_creates_file(repo_with_init):
    use_case = NewDocumentUseCase(str(repo_with_init))
    config = yaml.safe_load((repo_with_init / "docops.config.yaml").read_text())
    repo_prefix = config["repo_prefix"]

    doc_path = use_case.execute("ADR", "My First Decision")

    assert doc_path.name == "adr-001-my-first-decision.md"
    assert "00-governance/templates/adr.md" not in str(doc_path)

    content = doc_path.read_text()
    assert f"# {repo_prefix}-ADR-001: My First Decision" in content
    assert f"document_id: {repo_prefix}-ADR-001" in content
    post = frontmatter.load(doc_path)
    assert post.metadata.get("docops_version") == "2.0"


def test_new_prd_auto_increment_id(repo_with_init):
    use_case = NewDocumentUseCase(str(repo_with_init))
    config = yaml.safe_load((repo_with_init / "docops.config.yaml").read_text())
    repo_prefix = config["repo_prefix"]

    prd_dir = repo_with_init / "docs/10-prd"
    (prd_dir / "prd-001-fake.md").write_text(f"---\ndocument_id: {repo_prefix}-PRD-001\n---")

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
    from meminit.core.services.error_codes import ErrorCode, MeminitError

    with pytest.raises(MeminitError) as exc_info:
        use_case.execute("ADR", "Symlink Escape")
    assert exc_info.value.code == ErrorCode.PATH_ESCAPE


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
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    template = tmp_path / "docs" / "00-governance" / "templates" / "custom-adr.md"
    template.write_text(
        "# <REPO>-ADR-<SEQ>: <Decision Title>\n\n- Date: <YYYY-MM-DD>\n- Owner: <Team or Person>\n"
    )
    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
        SCHEMA_JSON, encoding="utf-8"
    )

    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Meminit
repo_prefix: MEMINIT
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
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
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    template = tmp_path / "docs" / "00-governance" / "templates" / "custom-adr.md"
    template.write_text("# ADR: {title}\n\n## Custom Template Marker\n", encoding="utf-8")
    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
        SCHEMA_JSON, encoding="utf-8"
    )

    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
repo_prefix: EXAMPLE
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
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

    monkeypatch.setattr(use_case, "_generate_id", lambda _doc_type, _target_dir, _ns: existing_id)
    with pytest.raises(FileExistsError):
        use_case.execute("ADR", "Unique Title")


def test_new_uses_configured_type_directory(tmp_path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "templates" / "custom-adr.md").write_text(
        "# ADR: {title}\n"
    )
    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
        SCHEMA_JSON, encoding="utf-8"
    )

    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
repo_prefix: EXAMPLE
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
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
    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
        SCHEMA_JSON, encoding="utf-8"
    )
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


class TestVisibleMetadataBlock:
    """Tests for F6: Visible Metadata Block Generation"""

    @pytest.fixture
    def repo_with_metadata_block_template(self, tmp_path):
        (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
        (tmp_path / "docs" / "00-governance" / "templates" / "adr.md").write_text(
            """# {title}

<!-- MEMINIT_METADATA_BLOCK -->

## Context

## Decision
""",
            encoding="utf-8",
        )
        (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
            SCHEMA_JSON, encoding="utf-8"
        )
        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
templates:
  adr: docs/00-governance/templates/adr.md
type_directories:
  ADR: 45-adr
"""
        )
        (tmp_path / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)
        return tmp_path

    def test_metadata_block_placeholder_is_replaced(self, repo_with_metadata_block_template):
        use_case = NewDocumentUseCase(str(repo_with_metadata_block_template))
        params = NewDocumentParams(doc_type="ADR", title="Test Decision")
        result = use_case.execute_with_params(params)

        assert result.success is True
        content = result.path.read_text(encoding="utf-8")
        assert "<!-- MEMINIT_METADATA_BLOCK -->" not in content
        assert "> **Document ID:**" in content

    def test_metadata_block_contains_all_expected_fields(self, repo_with_metadata_block_template):
        use_case = NewDocumentUseCase(str(repo_with_metadata_block_template))
        params = NewDocumentParams(
            doc_type="ADR",
            title="Test Decision",
            owner="TestOwner",
            area="Backend",
        )
        result = use_case.execute_with_params(params)

        assert result.success is True
        content = result.path.read_text(encoding="utf-8")

        assert "> **Document ID:** TEST-ADR-001" in content
        assert "> **Owner:** TestOwner" in content
        assert "> **Status:** Draft" in content
        assert "> **Version:** 0.1" in content
        assert "> **Type:** ADR" in content
        assert "> **Area:** Backend" in content

    def test_metadata_block_excludes_empty_fields(self, repo_with_metadata_block_template):
        use_case = NewDocumentUseCase(str(repo_with_metadata_block_template))
        params = NewDocumentParams(
            doc_type="ADR",
            title="Test Decision",
            owner="TestOwner",
            area=None,
            description=None,
        )
        result = use_case.execute_with_params(params)

        assert result.success is True
        content = result.path.read_text(encoding="utf-8")

        assert "> **Document ID:**" in content
        assert "> **Owner:**" in content
        assert "> **Area:**" not in content
        assert "> **Description:**" not in content


class TestTemplateFrontmatterMerge:
    """Tests for F7: Template Frontmatter Merge"""

    @pytest.fixture
    def repo_with_frontmatter_template(self, tmp_path):
        (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
        (tmp_path / "docs" / "00-governance" / "templates" / "prd.md").write_text(
            """---
custom_field: preserved-value
another_field: from-template
owner: TemplateOwner
area: TemplateArea
---

# {title}

<!-- MEMINIT_METADATA_BLOCK -->

## Problem Statement

## Proposed Solution
""",
            encoding="utf-8",
        )
        (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
            SCHEMA_JSON, encoding="utf-8"
        )
        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
templates:
  prd: docs/00-governance/templates/prd.md
type_directories:
  PRD: 10-prd
"""
        )
        (tmp_path / "docs" / "10-prd").mkdir(parents=True, exist_ok=True)
        return tmp_path

    def test_template_frontmatter_fields_preserved(self, repo_with_frontmatter_template):
        use_case = NewDocumentUseCase(str(repo_with_frontmatter_template))
        params = NewDocumentParams(doc_type="PRD", title="New Feature")
        result = use_case.execute_with_params(params)

        assert result.success is True
        post = frontmatter.load(result.path)
        assert post.metadata.get("custom_field") == "preserved-value"
        assert post.metadata.get("another_field") == "from-template"

    def test_generated_metadata_overrides_template_metadata(self, repo_with_frontmatter_template):
        use_case = NewDocumentUseCase(str(repo_with_frontmatter_template))
        params = NewDocumentParams(
            doc_type="PRD",
            title="New Feature",
            owner="CliOwner",
            area="CliArea",
        )
        result = use_case.execute_with_params(params)

        assert result.success is True
        post = frontmatter.load(result.path)
        assert post.metadata.get("owner") == "CliOwner"
        assert post.metadata.get("area") == "CliArea"

    def test_placeholder_substitution_in_template_frontmatter(self, tmp_path):
        (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
        (tmp_path / "docs" / "00-governance" / "templates" / "fdd.md").write_text(
            """---
custom_title: "{title}"
custom_owner: "<Team or Person>"
---

# {title}

## Feature Description
""",
            encoding="utf-8",
        )
        (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
            SCHEMA_JSON, encoding="utf-8"
        )
        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
templates:
  fdd: docs/00-governance/templates/fdd.md
type_directories:
  FDD: 50-fdd
"""
        )
        (tmp_path / "docs" / "50-fdd").mkdir(parents=True, exist_ok=True)

        use_case = NewDocumentUseCase(str(tmp_path))
        params = NewDocumentParams(
            doc_type="FDD",
            title="User Authentication",
            owner="DevTeam",
        )
        result = use_case.execute_with_params(params)

        assert result.success is True
        post = frontmatter.load(result.path)
        assert post.metadata.get("custom_title") == "User Authentication"
        assert post.metadata.get("custom_owner") == "DevTeam"


@pytest.mark.skipif(
    fcntl is None or sys.platform == "win32", reason="fcntl not available on Windows"
)
class TestFileLocking:
    """Tests for N7: File Locking for Concurrency Safety"""

    @pytest.fixture
    def repo_for_locking(self, tmp_path):
        (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
        (tmp_path / "docs" / "00-governance" / "templates" / "adr.md").write_text(
            "# ADR: {title}\n"
        )
        (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(
            SCHEMA_JSON, encoding="utf-8"
        )
        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
templates:
  adr: docs/00-governance/templates/adr.md
type_directories:
  ADR: 45-adr
"""
        )
        (tmp_path / "docs" / "45-adr").mkdir(parents=True, exist_ok=True)
        return tmp_path

    def test_lock_acquired_before_id_generation(self, repo_for_locking):
        use_case = NewDocumentUseCase(str(repo_for_locking))

        with patch.object(use_case, "_acquire_lock", wraps=use_case._acquire_lock) as mock_acquire:
            with patch.object(
                use_case, "_release_lock", wraps=use_case._release_lock
            ) as mock_release:
                params = NewDocumentParams(doc_type="ADR", title="Test")
                result = use_case.execute_with_params(params)

                assert result.success is True
                mock_acquire.assert_called_once()
                mock_release.assert_called_once()

    def test_lock_released_after_file_creation(self, repo_for_locking):
        use_case = NewDocumentUseCase(str(repo_for_locking))

        params = NewDocumentParams(doc_type="ADR", title="Test Lock Release")
        result = use_case.execute_with_params(params)

        assert result.success is True
        lock_file = repo_for_locking / "docs" / "45-adr" / ".meminit.lock"
        assert not lock_file.exists() or lock_file.stat().st_size == 0

    def test_lock_timeout_error_when_cannot_acquire(self, repo_for_locking):
        use_case = NewDocumentUseCase(str(repo_for_locking))

        target_dir = repo_for_locking / "docs" / "45-adr"
        target_dir.mkdir(parents=True, exist_ok=True)
        lock_path = target_dir / ".meminit.lock"

        with open(lock_path, "w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            try:
                with patch.dict("os.environ", {"MEMINIT_LOCK_TIMEOUT_MS": "100"}):
                    params = NewDocumentParams(doc_type="ADR", title="Lock Test")
                    result = use_case.execute_with_params(params)

                    assert result.success is False
                    assert result.error.code == ErrorCode.LOCK_TIMEOUT
                    assert "Could not acquire lock" in result.error.message
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def test_dry_run_does_not_acquire_lock(self, repo_for_locking):
        use_case = NewDocumentUseCase(str(repo_for_locking))

        with patch.object(use_case, "_acquire_lock") as mock_acquire:
            params = NewDocumentParams(doc_type="ADR", title="Dry Run", dry_run=True)
            result = use_case.execute_with_params(params)

            assert result.success is True
            mock_acquire.assert_not_called()
