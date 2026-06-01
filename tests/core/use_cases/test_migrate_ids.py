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

    report = MigrateIdsUseCase(str(tmp_path)).execute(dry_run=False, rewrite_references=False)

    assert (
        len(report.actions) == 1
    ), "First duplicate should keep its ID, second should be renumbered"
    action = report.actions[0]
    assert action.old_id == "AIDHA-ADR-001"
    assert action.new_id != "AIDHA-ADR-001", "Second doc should get a new ID"
    assert action.new_id.startswith("AIDHA-ADR-")

    post1 = frontmatter.load(doc1)
    post2 = frontmatter.load(doc2)
    assert post1.metadata["document_id"] == "AIDHA-ADR-001"
    assert post2.metadata["document_id"] == action.new_id


def test_migrate_ids_idempotent_apply(tmp_path: Path):
    """Verify apply is idempotent: second run produces empty report."""
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: AIDHA\ndocops_version: '2.0'\n", encoding="utf-8"
    )

    doc = tmp_path / "docs" / "45-adr" / "legacy-adr.md"
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

    report1 = MigrateIdsUseCase(str(tmp_path)).execute(dry_run=False, rewrite_references=False)
    assert len(report1.actions) == 1

    report2 = MigrateIdsUseCase(str(tmp_path)).execute(dry_run=False, rewrite_references=False)
    assert len(report2.actions) == 0, "Second apply should find no documents needing migration"


def test_migrate_ids_restamps_wrong_repo_prefix(tmp_path: Path):
    """Canonical IDs with the wrong prefix should be brought onto the configured prefix."""
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: AIDHA\ndocops_version: '2.0'\n", encoding="utf-8"
    )

    doc = tmp_path / "docs" / "45-adr" / "adr-legacy-prefix.md"
    doc.write_text(
        "---\n"
        "document_id: OLDPRJ-ADR-001\n"
        "type: ADR\n"
        "title: Legacy Prefix\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-26\n"
        "owner: __TBD__\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "<!-- MEMINIT_METADATA_BLOCK -->\n"
        "> **Document ID:** OLDPRJ-ADR-001\n\n"
        "# OLDPRJ-ADR-001: Legacy Prefix\n",
        encoding="utf-8",
    )

    report = MigrateIdsUseCase(str(tmp_path)).execute(dry_run=False, rewrite_references=True)

    assert len(report.actions) == 1
    action = report.actions[0]
    assert action.old_id == "OLDPRJ-ADR-001"
    assert action.new_id == "AIDHA-ADR-001"
    assert report.advice[0]["code"] == "ID_PREFIX_MISMATCH"

    post = frontmatter.load(doc)
    assert post.metadata["document_id"] == "AIDHA-ADR-001"
    assert "OLDPRJ-ADR-001" not in post.content
    assert "AIDHA-ADR-001" in post.content


def test_migrate_ids_duplicate_noncanonical_collision(tmp_path: Path):
    """Test that non-canonical duplicates get different new IDs."""
    (tmp_path / "docs" / "45-adr").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: AIDHA\ndocops_version: '2.0'\n", encoding="utf-8"
    )

    # Two docs with same non-canonical ID
    for i in range(1, 3):
        doc = tmp_path / "docs" / "45-adr" / f"adr-{i:03d}.md"
        doc.write_text(
            f"""---
document_id: DUP-ADR
type: ADR
title: Duplicate {i}
status: Draft
version: 0.1
last_updated: 2025-12-26
owner: __TBD__
docops_version: 2.0
---

# DUP-ADR: Duplicate {i}
""",
            encoding="utf-8",
        )

    report = MigrateIdsUseCase(str(tmp_path)).execute(dry_run=False, rewrite_references=False)

    assert len(report.actions) == 2, "Both files should be migrated"
    assert report.actions[0].new_id != report.actions[1].new_id, "Should allocate different new IDs"
    assert report.actions[0].old_id == report.actions[1].old_id == "DUP-ADR"

    post1 = frontmatter.load(tmp_path / "docs" / "45-adr" / f"adr-001.md")
    post2 = frontmatter.load(tmp_path / "docs" / "45-adr" / f"adr-002.md")
    assert post1.metadata["document_id"] == report.actions[0].new_id
    assert post2.metadata["document_id"] == report.actions[1].new_id


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
