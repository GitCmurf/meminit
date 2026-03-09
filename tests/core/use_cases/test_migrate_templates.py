import re
from pathlib import Path

from meminit.core.use_cases.migrate_templates import (
    LEGACY_PLACEHOLDER_MAPPINGS,
    LEGACY_PLACEHOLDER_PATTERN,
    MigrateTemplatesUseCase,
    TemplateMigrationReport,
)


def test_migrate_templates_converts_type_directories(tmp_path: Path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "type_directories:\n"
        "  ADR: '45-adr'\n"
        "  PRD: '10-prd'\n",
        encoding="utf-8",
    )

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report = use_case.execute(dry_run=True)

    assert report.config_entries_found == 2
    assert report.config_entries_migrated == 2


def test_migrate_templates_converts_templates_config(tmp_path: Path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "templates:\n"
        "  ADR: 'docs/00-governance/templates/template-001-adr.md'\n"
        "  PRD: 'docs/00-governance/templates/template-001-prd.md'\n",
        encoding="utf-8",
    )

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report = use_case.execute(dry_run=True)

    assert report.config_entries_found == 2
    assert report.config_entries_migrated == 2


def test_migrate_templates_templates_only_preserves_default_directory(tmp_path: Path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "templates:\n"
        "  ADR: 'docs/00-governance/templates/template-001-adr.md'\n",
        encoding="utf-8",
    )

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report = use_case.execute(dry_run=False, backup=False)

    assert report.config_entries_migrated == 1
    config_content = (tmp_path / "docops.config.yaml").read_text(encoding="utf-8")
    assert "document_types:" in config_content
    assert "ADR:" in config_content
    assert "directory: 45-adr" in config_content
    assert "template: docs/00-governance/templates/adr.template.md" in config_content


def test_migrate_templates_dry_run_does_not_modify_files(tmp_path: Path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "type_directories:\n"
        "  ADR: '45-adr'\n",
        encoding="utf-8",
    )

    original_config = (tmp_path / "docops.config.yaml").read_text()

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report = use_case.execute(dry_run=True)

    current_config = (tmp_path / "docops.config.yaml").read_text()
    assert original_config == current_config
    assert report.dry_run is True


def test_migrate_templates_applies_changes_when_not_dry_run(tmp_path: Path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "type_directories:\n"
        "  ADR: '45-adr'\n",
        encoding="utf-8",
    )

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report = use_case.execute(dry_run=False, backup=False)

    config_content = (tmp_path / "docops.config.yaml").read_text()
    assert "document_types:" in config_content
    assert "ADR:" in config_content


def test_migrate_templates_placeholder_replacement(tmp_path: Path):
    templates_dir = tmp_path / "docs" / "00-governance" / "templates"
    templates_dir.mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    template_file = templates_dir / "template-001-adr.md"
    template_file.write_text(
        "---\n"
        "document_id: {title}\n"
        "type: {type}\n"
        "title: {title}\n"
        "---\n"
        "\n"
        "# {title}\n"
        "\n"
        "Owner: {owner}\n"
        "Unknown: @unknown\n",
        encoding="utf-8",
    )

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report = use_case.execute(dry_run=True, rename_files=False)

    assert report.placeholder_replacements > 0
    assert report.warnings == []


def test_migrate_templates_placeholder_replacement_apply(tmp_path: Path):
    templates_dir = tmp_path / "docs" / "00-governance" / "templates"
    templates_dir.mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    template_file = templates_dir / "template-001-adr.md"
    template_file.write_text(
        "---\ndocument_id: {title}\ntitle: {title}\n---\n\n# {title}\n",
        encoding="utf-8",
    )

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report = use_case.execute(dry_run=False, backup=False, rename_files=False)

    content = template_file.read_text()
    assert "{{title}}" in content
    # Check that standalone {title} patterns are gone (not inside {{title}})
    # Use word boundary pattern to avoid matching {title} inside {{title}}
    assert not re.search(r'(?<!{){title}(?!})', content), "Standalone {title} placeholder should be replaced"


def test_migrate_templates_idempotent_rerun(tmp_path: Path):
    templates_dir = tmp_path / "docs" / "00-governance" / "templates"
    templates_dir.mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "type_directories:\n"
        "  ADR: '45-adr'\n",
        encoding="utf-8",
    )

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report1 = use_case.execute(dry_run=True)
    report2 = use_case.execute(dry_run=True)

    assert report1.config_entries_migrated == report2.config_entries_migrated


def test_migrate_templates_skips_existing_document_types(tmp_path: Path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\n"
        "docops_version: '2.0'\n"
        "document_types:\n"
        "  ADR:\n"
        "    directory: '45-adr'\n"
        "    template: 'docs/00-governance/templates/custom.md'\n"
        "type_directories:\n"
        "  ADR: 'different-dir'\n",
        encoding="utf-8",
    )

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report = use_case.execute(dry_run=True)

    assert len(report.warnings) > 0
    assert any("already exists" in w for w in report.warnings)


def test_migrate_templates_rename_files(tmp_path: Path):
    templates_dir = tmp_path / "docs" / "00-governance" / "templates"
    templates_dir.mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    template_file = templates_dir / "template-001-adr.md"
    template_file.write_text("---\ntitle: Test\n---\n", encoding="utf-8")

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report = use_case.execute(dry_run=True)

    assert report.template_files_found == 1
    assert report.template_files_renamed == 1

    renamed_file = templates_dir / "adr.template.md"
    assert not renamed_file.exists()


def test_legacy_placeholder_mappings_complete():
    expected_mappings = {
        "{title}",
        "{type}",
        "{status}",
        "{owner}",
        "{area}",
        "{description}",
        "{keywords}",
        "{related_ids}",
        "<REPO>",
        "<PROJECT>",
        "<SEQ>",
        "<YYYY-MM-DD>",
        "<AREA>",
        "<Decision Title>",
        "<Feature Title>",
        "<Team or Person>",
    }
    assert set(LEGACY_PLACEHOLDER_MAPPINGS.keys()) == expected_mappings


def test_template_migration_report_as_dict(tmp_path: Path):
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "repo_prefix: TEST\ndocops_version: '2.0'\n",
        encoding="utf-8",
    )

    use_case = MigrateTemplatesUseCase(str(tmp_path))
    report = use_case.execute(dry_run=True)

    report_dict = report.as_dict()
    assert "config_file" in report_dict
    assert "templates_dir" in report_dict
    assert "dry_run" in report_dict
    assert "summary" in report_dict
    assert "changes" in report_dict
