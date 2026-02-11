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
