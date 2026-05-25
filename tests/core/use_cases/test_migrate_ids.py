from pathlib import Path

import frontmatter

from meminit.core.use_cases.migrate_ids import MigrateIdsUseCase


def test_migrate_ids_rewrites_frontmatter_and_metadata_block(tmp_path: Path):
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)

    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: AIDHA\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    doc = tmp_path / "docs" / "45-adr" / "adr-legacy.md"
    doc.write_text(
        "---\n"
        "document_id: TAX-PRD\n"
        "type: ADR\n"
        "title: Legacy\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-26\n"
        "owner: __TBD__\n"
        "docops_version: 2.0\n"
        "---\n"
        "\n"
        "<!-- MEMINIT_METADATA_BLOCK -->\n"
        "> **Document ID:** TAX-PRD\n"
        "\n"
        "# TAX-PRD: Legacy\n",
        encoding="utf-8",
    )

    use_case = MigrateIdsUseCase(str(tmp_path))
    report = use_case.execute(dry_run=False, rewrite_references=False)
    assert len(report.actions) == 1
    action = report.actions[0]
    assert action.old_id == "TAX-PRD"
    assert action.new_id == "AIDHA-ADR-001"

    post = frontmatter.load(doc)
    assert post.metadata["document_id"] == "AIDHA-ADR-001"
    assert isinstance(post.metadata.get("last_updated"), str)
    assert isinstance(post.metadata.get("version"), str)
    assert isinstance(post.metadata.get("docops_version"), str)
    assert "AIDHA-ADR-001" in post.content


def test_migrate_ids_rewrite_references_optional(tmp_path: Path):
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text("repo_prefix: AIDHA\n", encoding="utf-8")

    doc = tmp_path / "docs" / "45-adr" / "adr-legacy.md"
    doc.write_text(
        "---\n"
        "document_id: OLD-ID\n"
        "type: ADR\n"
        "title: Legacy\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-26\n"
        "owner: __TBD__\n"
        "docops_version: 2.0\n"
        "---\n"
        "\n"
        "References OLD-ID in body.\n",
        encoding="utf-8",
    )

    use_case = MigrateIdsUseCase(str(tmp_path))
    report = use_case.execute(dry_run=False, rewrite_references=True)
    assert report.actions[0].rewritten_reference_count >= 1
    content = doc.read_text(encoding="utf-8")
    assert "OLD-ID" not in content


def test_migrate_ids_infers_type_from_directory_when_missing(tmp_path: Path):
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text("repo_prefix: AIDHA\n", encoding="utf-8")

    doc = tmp_path / "docs" / "45-adr" / "adr-legacy.md"
    doc.write_text(
        "---\n"
        "document_id: LEGACY\n"
        "title: Legacy\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-26\n"
        "owner: __TBD__\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# LEGACY: Legacy\n",
        encoding="utf-8",
    )

    report = MigrateIdsUseCase(str(tmp_path)).execute(dry_run=False, rewrite_references=False)
    assert report.actions[0].new_id == "AIDHA-ADR-001"


def test_migrate_ids_dry_run_no_mutation(tmp_path: Path):
    """P1-01: Verify migrate_ids dry-run does not modify files."""
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text("repo_prefix: AIDHA\n", encoding="utf-8")

    doc = tmp_path / "docs" / "45-adr" / "adr-legacy.md"
    doc.write_text(
        "---\n"
        "document_id: LEGACY\n"
        "type: ADR\n"
        "title: Legacy\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-26\n"
        "owner: __TBD__\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# LEGACY: Legacy\n",
        encoding="utf-8",
    )

    original_content = doc.read_text(encoding="utf-8")

    report = MigrateIdsUseCase(str(tmp_path)).execute(dry_run=True, rewrite_references=False)

    assert len(report.actions) == 1
    assert report.actions[0].old_id == "LEGACY"

    post_content = doc.read_text(encoding="utf-8")
    assert post_content == original_content, "Dry-run should not modify file"


def test_migrate_ids_duplicate_id_collision(tmp_path: Path):
    """P1-01: Verify migrate_ids handles duplicate ID collisions."""
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text("repo_prefix: AIDHA\n", encoding="utf-8")

    doc1 = tmp_path / "docs" / "45-adr" / "adr-001.md"
    doc1.write_text(
        "---\n"
        "document_id: AIDHA-ADR-001\n"
        "type: ADR\n"
        "title: First\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-26\n"
        "owner: __TBD__\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# AIDHA-ADR-001: First\n",
        encoding="utf-8",
    )

    doc2 = tmp_path / "docs" / "45-adr" / "adr-002.md"
    doc2.write_text(
        "---\n"
        "document_id: AIDHA-ADR-001\n"
        "type: ADR\n"
        "title: Second (duplicate)\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-26\n"
        "owner: __TBD__\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# AIDHA-ADR-001: Second (duplicate)\n",
        encoding="utf-8",
    )

    report = MigrateIdsUseCase(str(tmp_path)).execute(dry_run=True, rewrite_references=False)

    assert len(report.actions) == 2
    assert report.actions[0].new_id != report.actions[1].new_id, "Should allocate different IDs"
    assert report.actions[0].new_id.startswith("AIDHA-ADR-")
    assert report.actions[1].new_id.startswith("AIDHA-ADR-")


def test_migrate_ids_missing_frontmatter_inference(tmp_path: Path):
    """P1-01: Verify migrate_ids handles missing frontmatter."""
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text("repo_prefix: AIDHA\n", encoding="utf-8")

    doc = tmp_path / "docs" / "45-adr" / "adr-legacy.md"
    doc.write_text(
        "# Some Document\n\nThis has no frontmatter.\n",
        encoding="utf-8",
    )

    report = MigrateIdsUseCase(str(tmp_path)).execute(dry_run=False, rewrite_references=False)

    assert len(report.actions) == 0, "Should skip documents without frontmatter"
