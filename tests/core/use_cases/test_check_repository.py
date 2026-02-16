import tempfile
from pathlib import Path

import pytest

from meminit.core.domain.entities import Violation
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.use_cases.check_repository import CheckRepositoryUseCase


@pytest.fixture
def repo_with_docs():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)

        (repo / "docops.config.yaml").write_text(
            "project_name: Meminit\nrepo_prefix: MEMINIT\ndocops_version: '2.0'\n",
            encoding="utf-8",
        )

        # Setup schema (required by validator)
        gov = repo / "docs" / "00-governance"
        gov.mkdir(parents=True)
        # Require string fields so we can catch YAML scalar coercions (date/float) that should be normalized.
        (gov / "metadata.schema.json").write_text(
            """
{
  "type": "object",
  "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],
  "properties": {
    "document_id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": { "type": "string" },
    "version": { "type": "string" },
    "last_updated": { "type": "string" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" }
  },
  "additionalProperties": true
}
""".strip()
        )
        # Templates are not governed docs and should be excluded from checks
        templates_dir = gov / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "Bad Template.md").write_text(
            "# Placeholder template without governed frontmatter\n"
        )

        docs = repo / "docs" / "45-adr"
        docs.mkdir(parents=True)

        # Valid Doc
        (docs / "adr-001.md").write_text(
            """---
document_id: MEMINIT-ADR-001
type: ADR
title: Valid
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: Me
docops_version: 2.0
---
# Valid Doc
"""
        )

        # Invalid Doc (Bad ID)
        (docs / "adr-002.md").write_text(
            """---
document_id: BAD-ID
type: ADR
title: Invalid
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: Me
docops_version: 2.0
---
# Invalid Doc
"""
        )
        yield repo


def test_check_repository(repo_with_docs):
    use_case = CheckRepositoryUseCase(root_dir=str(repo_with_docs))
    violations = use_case.execute()

    assert len(violations) > 0
    assert all(
        "docs/00-governance/templates" not in v.file.replace("\\", "/")
        for v in violations
    )
    ids_failed = [v.message for v in violations if "BAD-ID" in v.message]
    assert len(ids_failed) > 0

    # Ensure valid doc didn't error
    valid_failed = [v for v in violations if "MEMINIT-ADR-001" in v.message]
    assert len(valid_failed) == 0


def test_check_repository_schema_type_errors_include_field(tmp_path):
    gov = tmp_path / "docs" / "00-governance"
    gov.mkdir(parents=True)
    (gov / "metadata.schema.json").write_text(
        '{"type":"object","required":["title"],"properties":{"title":{"type":"string"}}}'
    )
    docs = tmp_path / "docs" / "45-adr"
    docs.mkdir(parents=True)
    (docs / "adr-001.md").write_text(
        """---
title: 123
---
# Doc
"""
    )

    use_case = CheckRepositoryUseCase(root_dir=str(tmp_path))
    violations = use_case.execute()
    schema = [v for v in violations if v.rule == "SCHEMA_VALIDATION"]
    assert len(schema) == 1
    assert "title" in schema[0].message


def test_check_directory_and_filename(repo_with_docs):
    # Setup violation scenarios

    # 1. Filename violation (spaces, uppercase)
    bad_name_file = repo_with_docs / "docs" / "45-adr" / "Bad Name.md"
    bad_name_file.write_text(
        """---
document_id: MEMINIT-ADR-003
type: ADR
title: Bad Name
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: Me
docops_version: 2.0
---
# Content
"""
    )

    # 1b. Missing frontmatter should not drop filename violation
    no_frontmatter_file = repo_with_docs / "docs" / "45-adr" / "No Frontmatter.md"
    no_frontmatter_file.write_text("# No frontmatter here\n")

    # 2. Directory Mismatch (Type: ADR in wrong folder)
    wrong_dir = repo_with_docs / "docs" / "10-prd"
    wrong_dir.mkdir()
    wrong_loc_file = wrong_dir / "adr-004.md"
    wrong_loc_file.write_text(
        """---
document_id: MEMINIT-ADR-004
type: ADR
title: Wrong Location
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: Me
docops_version: 2.0
---
# Content
"""
    )

    use_case = CheckRepositoryUseCase(root_dir=str(repo_with_docs))
    violations = use_case.execute()

    # Check Filename Rule
    filename_violations = [v for v in violations if v.rule == "FILENAME_CONVENTION"]
    assert len(filename_violations) == 2
    assert any("Bad Name.md" in v.file for v in filename_violations)
    assert any("No Frontmatter.md" in v.file for v in filename_violations)

    # Check Frontmatter missing still reported alongside filename issue
    fm_violations = [v for v in violations if v.rule == "FRONTMATTER_MISSING"]
    assert len(fm_violations) == 1
    assert "No Frontmatter.md" in fm_violations[0].file

    # Check Location Rule
    location_violations = [v for v in violations if v.rule == "DIRECTORY_MATCH"]
    assert len(location_violations) == 1
    assert "adr-004.md" in location_violations[0].file


def test_check_respects_configured_exclusions_and_type_directories(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
repo_prefix: EXAMPLE
docops_version: '2.0'
docs_root: docs
excluded_paths:
  - docs/templates
type_directories:
  ADR: adrs
"""
    )

    gov = tmp_path / "docs" / "00-governance"
    gov.mkdir(parents=True)
    (gov / "metadata.schema.json").write_text(
        """
{
  "type": "object",
  "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],
  "properties": {
    "document_id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": { "type": "string" },
    "version": { "type": "string" },
    "last_updated": { "type": "string" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" }
  }
}
""".strip()
    )

    (tmp_path / "docs" / "templates").mkdir(parents=True)
    (tmp_path / "docs" / "templates" / "ignored.md").write_text("# Not governed\n")

    adrs = tmp_path / "docs" / "adrs"
    adrs.mkdir(parents=True)
    (adrs / "adr-001.md").write_text(
        """---
document_id: EXAMPLE-ADR-001
type: ADR
title: Example ADR
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: Me
docops_version: 2.0
---
# Example
"""
    )

    use_case = CheckRepositoryUseCase(root_dir=str(tmp_path))
    violations = use_case.execute()
    assert not any(
        "docs/templates/ignored.md" in v.file.replace("\\", "/") for v in violations
    )
    assert not any(
        v.rule == "DIRECTORY_MATCH" and "adr-001.md" in v.file for v in violations
    )


def test_check_repository_reports_missing_schema_once(tmp_path):
    docs = tmp_path / "docs" / "45-adr"
    docs.mkdir(parents=True)
    (docs / "adr-001.md").write_text(
        """---
document_id: EXAMPLE-ADR-001
type: ADR
title: Example ADR
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: Me
docops_version: 2.0
---
# Example
"""
    )

    use_case = CheckRepositoryUseCase(root_dir=str(tmp_path))
    violations = use_case.execute()
    schema = [v for v in violations if v.rule == "SCHEMA_MISSING"]
    assert len(schema) == 1


def test_check_repository_reports_invalid_schema_once(tmp_path):
    gov = tmp_path / "docs" / "00-governance"
    gov.mkdir(parents=True)
    (gov / "metadata.schema.json").write_text("{ this is not valid json")

    docs = tmp_path / "docs" / "45-adr"
    docs.mkdir(parents=True)
    (docs / "adr-001.md").write_text(
        """---
document_id: EXAMPLE-ADR-001
type: ADR
title: Example ADR
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: Me
docops_version: 2.0
---
# Example
"""
    )
    (docs / "adr-002.md").write_text(
        """---
document_id: EXAMPLE-ADR-002
type: ADR
title: Example ADR 2
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: Me
docops_version: 2.0
---
# Example
"""
    )

    use_case = CheckRepositoryUseCase(root_dir=str(tmp_path))
    violations = use_case.execute()
    schema = [v for v in violations if v.rule == "SCHEMA_INVALID"]
    assert len(schema) == 1


def test_check_excludes_wip_prefix_by_default(tmp_path):
    gov = tmp_path / "docs" / "00-governance"
    gov.mkdir(parents=True)
    (gov / "metadata.schema.json").write_text(
        """
{
  "type": "object",
  "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],
  "properties": {
    "document_id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": { "type": "string" },
    "version": { "type": "string" },
    "last_updated": { "type": "string" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" }
  }
}
""".strip()
    )

    docs = tmp_path / "docs" / "45-adr"
    docs.mkdir(parents=True)
    (docs / "WIP-My Scratch.md").write_text("# no frontmatter\n")

    use_case = CheckRepositoryUseCase(root_dir=str(tmp_path))
    violations = use_case.execute()
    assert not violations


def test_check_excludes_wip_directories_by_default(tmp_path):
    gov = tmp_path / "docs" / "00-governance"
    gov.mkdir(parents=True)
    (gov / "metadata.schema.json").write_text(
        """
{
  "type": "object",
  "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],
  "properties": {
    "document_id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": { "type": "string" },
    "version": { "type": "string" },
    "last_updated": { "type": "string" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" }
  }
}
""".strip()
    )

    wip_dir = tmp_path / "docs" / "45-adr" / "WIP-screenshots"
    wip_dir.mkdir(parents=True)
    (wip_dir / "notes.md").write_text("# no frontmatter\n")

    use_case = CheckRepositoryUseCase(root_dir=str(tmp_path))
    violations = use_case.execute()
    assert not violations


class TestTargetedCheck:
    """Tests for F10: Targeted File Validation"""

    @pytest.fixture
    def repo_for_targeted_check(self, tmp_path):
        gov = tmp_path / "docs" / "00-governance"
        gov.mkdir(parents=True)
        (gov / "metadata.schema.json").write_text(
            """
{
  "type": "object",
  "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],
  "properties": {
    "document_id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": { "type": "string" },
    "version": { "type": "string" },
    "last_updated": { "type": "string" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" }
  },
  "additionalProperties": true
}
""".strip()
        )

        (tmp_path / "docops.config.yaml").write_text(
            """project_name: TestProject
repo_prefix: TEST
docops_version: '2.0'
type_directories:
  ADR: 45-adr
  PRD: 10-prd
"""
        )

        adr_dir = tmp_path / "docs" / "45-adr"
        adr_dir.mkdir(parents=True)

        (adr_dir / "adr-001-valid.md").write_text(
            """---
document_id: TEST-ADR-001
type: ADR
title: Valid Doc
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: TestOwner
docops_version: 2.0
---
# Valid
"""
        )

        (adr_dir / "adr-002-invalid.md").write_text(
            """---
document_id: BAD-ID
type: ADR
title: Invalid Doc
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: TestOwner
docops_version: 2.0
---
# Invalid
"""
        )

        prd_dir = tmp_path / "docs" / "10-prd"
        prd_dir.mkdir(parents=True)

        (prd_dir / "prd-001-valid.md").write_text(
            """---
document_id: TEST-PRD-001
type: PRD
title: Valid PRD
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: TestOwner
docops_version: 2.0
---
# Valid PRD
"""
        )

        return tmp_path

    def test_execute_targeted_with_single_file(self, repo_for_targeted_check):
        use_case = CheckRepositoryUseCase(root_dir=str(repo_for_targeted_check))
        result = use_case.execute_targeted(["docs/45-adr/adr-001-valid.md"])

        assert result.success is True
        assert result.files_checked == 1
        assert result.files_passed == 1
        assert result.files_failed == 0
        assert result.violations == []

    def test_execute_targeted_with_invalid_file(self, repo_for_targeted_check):
        use_case = CheckRepositoryUseCase(root_dir=str(repo_for_targeted_check))
        result = use_case.execute_targeted(["docs/45-adr/adr-002-invalid.md"])

        assert result.success is False
        assert result.files_checked == 1
        assert result.files_passed == 0
        assert result.files_failed == 1
        assert len(result.violations) == 1
        assert "adr-002-invalid.md" in result.violations[0]["path"]

    def test_execute_targeted_with_glob_patterns(self, repo_for_targeted_check):
        use_case = CheckRepositoryUseCase(root_dir=str(repo_for_targeted_check))
        result = use_case.execute_targeted(["docs/45-adr/*.md"])

        assert result.files_checked == 2
        assert result.files_failed == 1
        assert result.files_passed == 1

    def test_execute_targeted_with_multiple_files(self, repo_for_targeted_check):
        use_case = CheckRepositoryUseCase(root_dir=str(repo_for_targeted_check))
        result = use_case.execute_targeted(
            [
                "docs/45-adr/adr-001-valid.md",
                "docs/10-prd/prd-001-valid.md",
            ]
        )

        assert result.success is True
        assert result.files_checked == 2
        assert result.files_passed == 2
        assert result.files_failed == 0

    def test_execute_targeted_missing_file_reports_file_not_found(
        self, repo_for_targeted_check
    ):
        """Per F10.6, single missing path should raise FILE_NOT_FOUND error envelope."""
        use_case = CheckRepositoryUseCase(root_dir=str(repo_for_targeted_check))

        with pytest.raises(MeminitError) as exc_info:
            use_case.execute_targeted(["docs/45-adr/nonexistent.md"])

        assert exc_info.value.code == ErrorCode.FILE_NOT_FOUND
        assert "nonexistent.md" in exc_info.value.message

    def test_execute_targeted_outside_docs_root_warning(self, repo_for_targeted_check):
        outside_file = repo_for_targeted_check / "README.md"
        outside_file.write_text("# README\n")

        use_case = CheckRepositoryUseCase(root_dir=str(repo_for_targeted_check))
        result = use_case.execute_targeted(["README.md"])

        assert result.success is True
        assert result.files_checked == 1
        assert result.files_passed == 1
        assert len(result.warnings) == 1
        assert "OUTSIDE_DOCS_ROOT" in result.warnings[0]["warnings"][0]["code"]

    def test_check_result_structure(self, repo_for_targeted_check):
        use_case = CheckRepositoryUseCase(root_dir=str(repo_for_targeted_check))
        result = use_case.execute_targeted(["docs/45-adr/adr-002-invalid.md"])

        assert hasattr(result, "success")
        assert hasattr(result, "files_checked")
        assert hasattr(result, "files_passed")
        assert hasattr(result, "files_failed")
        assert hasattr(result, "violations")
        assert hasattr(result, "warnings")

        assert isinstance(result.violations, list)
        assert isinstance(result.warnings, list)

        if result.violations:
            assert "path" in result.violations[0]
            assert "violations" in result.violations[0]
            violation_entry = result.violations[0]["violations"][0]
            assert "code" in violation_entry
            assert "message" in violation_entry

    def test_execute_targeted_recursive_glob(self, repo_for_targeted_check):
        use_case = CheckRepositoryUseCase(root_dir=str(repo_for_targeted_check))
        result = use_case.execute_targeted(["docs/**/*.md"])

        assert result.files_checked == 3
        assert result.files_failed == 1

    def test_execute_targeted_path_escape_is_fatal(self, repo_for_targeted_check):
        """Per F10.5, PATH_ESCAPE should raise MeminitError, not per-file violation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Outside Repo\n")
            outside_file = Path(f.name)

        try:
            use_case = CheckRepositoryUseCase(root_dir=str(repo_for_targeted_check))
            with pytest.raises(Exception) as exc_info:
                use_case.execute_targeted([str(outside_file)])

            from meminit.core.services.error_codes import ErrorCode, MeminitError

            assert isinstance(exc_info.value, MeminitError)
            assert exc_info.value.code == ErrorCode.PATH_ESCAPE
        finally:
            outside_file.unlink()
