import tempfile
from datetime import date
from pathlib import Path

import frontmatter
import pytest

from meminit.core.domain.entities import Severity
from meminit.core.use_cases.check_repository import CheckRepositoryUseCase
from meminit.core.use_cases.fix_repository import FixRepositoryUseCase


@pytest.fixture
def repo_for_fix():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)

        # Setup schema
        gov = repo / "docs" / "00-governance"
        gov.mkdir(parents=True)
        (gov / "metadata.schema.json").write_text(
            '{"type": "object", "required": ["last_updated", "docops_version"], "properties": {"document_id": {"type": "string"}, "last_updated": {"type": "string", "format": "date"}, "docops_version": {"type": "string"}}}'
        )

        docs = repo / "docs" / "45-adr"
        docs.mkdir(parents=True)

        # Doc causing Frontmatter (Missing last_updated) and Filename violations
        bad_file = docs / "Bad Name.md"
        bad_file.write_text(
            """---
document_id: MEMINIT-ADR-005
type: ADR
title: Fix Me
status: Draft
version: 0.1
owner: Me
---
# Fix Me
"""
        )
        yield repo


def test_fix_dry_run(repo_for_fix):
    fixer = FixRepositoryUseCase(root_dir=str(repo_for_fix))
    report = fixer.execute(dry_run=True)

    # Check that fixes were proposed
    assert len(report.fixed_violations) > 0
    assert any("Rename" in f.action for f in report.fixed_violations)
    assert any("Update last_updated" in f.action for f in report.fixed_violations)

    # Verify NO changes made
    assert (repo_for_fix / "docs" / "45-adr" / "Bad Name.md").exists()
    assert not (repo_for_fix / "docs" / "45-adr" / "bad-name.md").exists()

    post = frontmatter.load(repo_for_fix / "docs" / "45-adr" / "Bad Name.md")
    assert "last_updated" not in post.metadata


def test_fix_apply(repo_for_fix):
    fixer = FixRepositoryUseCase(root_dir=str(repo_for_fix))
    report = fixer.execute(dry_run=False)

    # 1. Check Rename
    old_file = repo_for_fix / "docs" / "45-adr" / "Bad Name.md"
    new_file = repo_for_fix / "docs" / "45-adr" / "bad-name.md"

    assert not old_file.exists()
    assert new_file.exists()

    # 2. Check Content Updates
    post = frontmatter.load(new_file)
    assert "last_updated" in post.metadata
    assert isinstance(post.metadata["last_updated"], str)
    # Should be today's date
    # Normalize date for comparison
    actual_date = post.metadata["last_updated"]
    if hasattr(actual_date, "date"):
        actual_date = actual_date.date()
    elif isinstance(actual_date, str):
        actual_date = date.fromisoformat(actual_date)

    assert actual_date == date.today()

    # 3. Check DocOps Version Update
    assert post.metadata.get("docops_version") == "2.0"


def test_fix_rename_sanitizes_symbols(tmp_path):
    # Setup schema
    gov = tmp_path / "docs" / "00-governance"
    gov.mkdir(parents=True)
    (gov / "metadata.schema.json").write_text(
        '{"type": "object", "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],'
        ' "properties": {"document_id": {"type": "string"}, "type": {"type": "string"}, "title": {"type": "string"},'
        ' "status": {"type": "string"}, "version": {"type": "string"}, "last_updated": {"type": "string", "format": "date"},'
        ' "owner": {"type": "string"}, "docops_version": {"type": "string"}}}'
    )

    docs = tmp_path / "docs" / "45-adr"
    docs.mkdir(parents=True)

    bad_file = docs / "Bad_Name(2).md"
    bad_file.write_text(
        """---
document_id: MEMINIT-ADR-123
type: ADR
title: Fix Symbols
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: Me
docops_version: 2.0
---
# Fix Symbols
"""
    )

    fixer = FixRepositoryUseCase(root_dir=str(tmp_path))
    report = fixer.execute(dry_run=False)

    assert not bad_file.exists()
    sanitized = docs / "bad-name-2.md"
    assert sanitized.exists()

    # Should not leave underscores/parentheses behind
    checker = CheckRepositoryUseCase(root_dir=str(tmp_path))
    violations = checker.execute()
    assert all(
        v.file != str(sanitized.relative_to(tmp_path)) or v.rule != "FILENAME_CONVENTION"
        for v in violations
    )


def test_fix_does_not_rename_readme_md(tmp_path):
    gov = tmp_path / "docs" / "00-governance"
    gov.mkdir(parents=True)
    (gov / "metadata.schema.json").write_text(
        '{"type": "object", "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],'
        ' "properties": {"document_id": {"type": "string"}, "type": {"type": "string"}, "title": {"type": "string"},'
        ' "status": {"type": "string"}, "version": {"type": "string"}, "last_updated": {"type": "string", "format": "date"},'
        ' "owner": {"type": "string"}, "docops_version": {"type": "string"}}}'
    )

    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\nschema_path: docs/00-governance/metadata.schema.json\n",
        encoding="utf-8",
    )

    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    readme = docs / "README.md"
    readme.write_text(
        """---
document_id: TEST-REF-001
type: REF
title: Readme
status: Draft
version: 0.1
last_updated: 2025-01-01
owner: __TBD__
docops_version: 2.0
---
# Readme
""",
        encoding="utf-8",
    )

    fixer = FixRepositoryUseCase(root_dir=str(tmp_path))
    fixer.execute(dry_run=False)

    assert readme.exists()
    assert not (docs / "readme.md").exists()


def test_fix_namespace_only_applies_in_that_namespace(tmp_path):
    gov = tmp_path / "docs" / "00-governance"
    gov.mkdir(parents=True)
    (gov / "metadata.schema.json").write_text(
        '{"type": "object", "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],'
        ' "properties": {"document_id": {"type": "string"}, "type": {"type": "string"}, "title": {"type": "string"},'
        ' "status": {"type": "string"}, "version": {"type": "string"}, "last_updated": {"type": "string", "format": "date"},'
        ' "owner": {"type": "string"}, "docops_version": {"type": "string"}}}'
    )

    (tmp_path / "docops.config.yaml").write_text(
        """
project_name: Example
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
namespaces:
  - name: root
    repo_prefix: AIDHA
    docs_root: docs
  - name: phyla
    repo_prefix: PHYLA
    docs_root: packages/phyla/docs
""".lstrip(),
        encoding="utf-8",
    )

    root_docs = tmp_path / "docs" / "45-adr"
    root_docs.mkdir(parents=True)
    bad_root = root_docs / "Bad Name.md"
    bad_root.write_text(
        """---
document_id: AIDHA-ADR-001
type: ADR
title: Root
status: Draft
version: 0.1
last_updated: 2025-12-28
owner: GitCmurf
docops_version: 2.0
---
# Root
""",
        encoding="utf-8",
    )

    pkg_docs = tmp_path / "packages" / "phyla" / "docs" / "45-adr"
    pkg_docs.mkdir(parents=True)
    bad_pkg = pkg_docs / "Also Bad.md"
    bad_pkg.write_text(
        """---
document_id: PHYLA-ADR-001
type: ADR
title: Pkg
status: Draft
version: 0.1
last_updated: 2025-12-28
owner: GitCmurf
docops_version: 2.0
---
# Pkg
""",
        encoding="utf-8",
    )


def test_fix_refuses_symlink_escape_on_write(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    gov = repo_root / "docs" / "00-governance"
    gov.mkdir(parents=True, exist_ok=True)
    (gov / "metadata.schema.json").write_text(
        '{"type": "object", "required": ["last_updated", "docops_version"],'
        ' "properties": {"document_id": {"type": "string"},'
        ' "last_updated": {"type": "string", "format": "date"},'
        ' "docops_version": {"type": "string"}}}',
        encoding="utf-8",
    )

    docs = repo_root / "docs" / "45-adr"
    docs.mkdir(parents=True, exist_ok=True)

    outside = tmp_path / "outside.md"
    outside_content = """---
document_id: MEMINIT-ADR-999
type: ADR
title: Outside
status: Draft
version: 0.1
owner: Me
---
# Outside
"""
    outside.write_text(outside_content, encoding="utf-8")

    # Symlink inside the repo points to a file outside the repo root.
    link = docs / "Bad Name.md"
    link.symlink_to(outside)

    fixer = FixRepositoryUseCase(root_dir=str(repo_root))
    report = fixer.execute(dry_run=False)

    # Critical: the outside file must not be modified.
    assert outside.read_text(encoding="utf-8") == outside_content
    assert any(v.rule == "UNSAFE_PATH" for v in report.remaining_violations)


def test_fix_frontmatter_missing_makes_doc_compliant(tmp_path):
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
    target = docs / "no-frontmatter.md"
    target.write_text("# My Missing Frontmatter Doc\n\nHello.\n")

    fixer = FixRepositoryUseCase(root_dir=str(tmp_path))
    report = fixer.execute(dry_run=False)
    assert any(
        a.action == "Add frontmatter" and "no-frontmatter.md" in a.file
        for a in report.fixed_violations
    )

    post = frontmatter.load(target)
    assert post.metadata.get("type") == "ADR"
    assert post.metadata.get("title") == "My Missing Frontmatter Doc"
    assert post.metadata.get("status") == "Draft"
    assert post.metadata.get("version") == "0.1"
    assert post.metadata.get("owner") == "__TBD__"
    assert "document_id" in post.metadata
    assert "last_updated" in post.metadata
    assert post.metadata.get("docops_version") == "2.0"

    checker = CheckRepositoryUseCase(root_dir=str(tmp_path))
    violations = checker.execute()
    rel = str(target.relative_to(tmp_path))
    assert not any(
        v.file == rel and v.rule in {"FRONTMATTER_MISSING", "SCHEMA_VALIDATION"} for v in violations
    )


def test_fix_schema_validation_fills_missing_required_fields(tmp_path):
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
    target = docs / "missing-fields.md"
    target.write_text(
        """---
document_id: MEMINIT-ADR-777
type: ADR
status: Draft
version: 0.1
---
# Filled By Fix
"""
    )

    fixer = FixRepositoryUseCase(root_dir=str(tmp_path))
    report = fixer.execute(dry_run=False)
    assert any("missing-fields.md" in a.file for a in report.fixed_violations)

    post = frontmatter.load(target)
    assert post.metadata.get("title") == "Filled By Fix"
    assert post.metadata.get("owner") == "__TBD__"
    assert post.metadata.get("docops_version") == "2.0"
    assert "last_updated" in post.metadata

    checker = CheckRepositoryUseCase(root_dir=str(tmp_path))
    violations = checker.execute()
    rel = str(target.relative_to(tmp_path))
    assert not any(v.file == rel and v.rule == "SCHEMA_VALIDATION" for v in violations)


def test_fix_infers_type_from_configured_type_directory(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        """project_name: Example
repo_prefix: EXAMPLE
docops_version: '2.0'
docs_root: docs
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

    adrs = tmp_path / "docs" / "adrs"
    adrs.mkdir(parents=True)
    target = adrs / "no-frontmatter.md"
    target.write_text("# Inferred ADR\n\nHello.\n")

    fixer = FixRepositoryUseCase(root_dir=str(tmp_path))
    report = fixer.execute(dry_run=False)
    assert any(
        a.action == "Add frontmatter" and "no-frontmatter.md" in a.file
        for a in report.fixed_violations
    )

    post = frontmatter.load(target)
    assert post.metadata.get("type") == "ADR"
