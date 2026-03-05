"""Unit tests for the TemplateResolver service."""

import tempfile
from pathlib import Path

import pytest

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.repo_config import RepoConfig, load_repo_config
from meminit.core.services.template_resolver import (
    SOURCE_BUILTIN,
    SOURCE_CONFIG,
    SOURCE_CONVENTION,
    SOURCE_NONE,
    TemplateResolver,
    TemplateResolution,
)


class TestTemplateResolution:
    """Test TemplateResolution dataclass."""

    def test_template_resolution_fields(self):
        """Test that TemplateResolution has all required fields."""
        resolution = TemplateResolution(
            source=SOURCE_CONFIG,
            path=Path("/test/template.md"),
            content="# Test\n\nContent here."
        )
        assert resolution.source == SOURCE_CONFIG
        assert resolution.path == Path("/test/template.md")
        assert resolution.content == "# Test\n\nContent here."


class TestTemplateResolverPrecedence:
    """Test template resolution precedence chain."""

    def test_resolution_precedence_config_first(self, tmp_path):
        """Configured template takes precedence over convention and built-in."""
        # tmp_path is the repo root
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Create configured template in templates directory
        templates_dir = docs_dir / "templates"
        templates_dir.mkdir()
        config_template = templates_dir / "custom.template.md"
        config_template.write_text("# CONFIG TEMPLATE")

        # Create convention template in 00-governance/templates
        gov_templates_dir = docs_dir / "00-governance" / "templates"
        gov_templates_dir.mkdir(parents=True)
        convention_template = gov_templates_dir / "prd.template.md"
        convention_template.write_text("# CONVENTION TEMPLATE")

        # Create config file with document_types pointing to config template
        config_file = tmp_path / "docops.config.yaml"
        config_file.write_text(f"""
project_name: Test
repo_prefix: TEST
docops_version: "2.0"
schema_path: docs/00-governance/metadata.schema.json
document_types:
  PRD:
    directory: "10-prd"
    template: docs/templates/custom.template.md
""")

        # Load config
        repo_config = load_repo_config(str(tmp_path))
        resolver = TemplateResolver(repo_config)

        # Config should take precedence
        resolution = resolver.resolve("PRD")
        assert resolution.source == SOURCE_CONFIG
        assert resolution.content == "# CONFIG TEMPLATE"

    def test_resolution_fallback_to_convention(self, tmp_path):
        """Convention template used when no config template."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Create convention template only
        templates_dir = docs_dir / "00-governance" / "templates"
        templates_dir.mkdir(parents=True)
        convention_template = templates_dir / "prd.template.md"
        convention_template.write_text("# CONVENTION TEMPLATE")

        # Create config file without explicit template
        config_file = tmp_path / "docops.config.yaml"
        config_file.write_text("""
project_name: Test
repo_prefix: TEST
docops_version: "2.0"
document_types:
  PRD:
    directory: "10-prd"
""")

        repo_config = load_repo_config(str(tmp_path))
        resolver = TemplateResolver(repo_config)

        resolution = resolver.resolve("PRD")
        assert resolution.source == SOURCE_CONVENTION
        assert resolution.content == "# CONVENTION TEMPLATE"

    def test_resolution_fallback_to_builtin(self, tmp_path):
        """Built-in template used when no config or convention template."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        config_file = tmp_path / "docops.config.yaml"
        config_file.write_text("""
project_name: Test
repo_prefix: TEST
docops_version: "2.0"
document_types:
  PRD:
    directory: "10-prd"
""")

        repo_config = load_repo_config(str(tmp_path))
        resolver = TemplateResolver(repo_config)

        # PRD has a built-in template
        resolution = resolver.resolve("PRD")
        assert resolution.source == SOURCE_BUILTIN
        assert resolution.content is not None
        assert "# PRD:" in resolution.content

    def test_resolution_fallback_to_skeleton(self, tmp_path):
        """Skeleton used when no template found."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        config_file = tmp_path / "docops.config.yaml"
        config_file.write_text("""
project_name: Test
repo_prefix: TEST
docops_version: "2.0"
document_types:
  UNKNOWN:
    directory: "99-unknown"
""")

        repo_config = load_repo_config(str(tmp_path))
        resolver = TemplateResolver(repo_config)

        # UNKNOWN type has no built-in template
        resolution = resolver.resolve("UNKNOWN")
        assert resolution.source == SOURCE_NONE
        assert resolution.path is None
        assert resolution.content is None


class TestTemplateResolverSecurity:
    """Test template validation and security."""

    def test_path_traversal_rejected(self, tmp_path):
        """Path traversal via .. in template path is rejected."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        config_file = tmp_path / "docops.config.yaml"
        # Use ../ to attempt escape
        config_file.write_text(f"""
project_name: Test
repo_prefix: TEST
docops_version: "2.0"
document_types:
  PRD:
    directory: "10-prd"
    template: ../../etc/passwd
""")

        repo_config = load_repo_config(str(tmp_path))
        resolver = TemplateResolver(repo_config)

        # Should not resolve (path validation prevents escape)
        resolution = resolver.resolve("PRD")
        # Falls through to builtin since config path doesn't exist
        assert resolution.source != SOURCE_CONFIG

    def test_symlink_rejected(self, tmp_path):
        """Symlink template files are rejected."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Create a regular file as the target
        target_file = tmp_path / "target.md"
        target_file.write_text("# Target")

        # Create symlink to target
        link_file = tmp_path / "link.md"
        link_file.symlink_to(target_file)

        config_file = tmp_path / "docops.config.yaml"
        config_file.write_text("""
project_name: Test
repo_prefix: TEST
docops_version: "2.0"
document_types:
  PRD:
    directory: "10-prd"
    template: link.md
""")

        repo_config = load_repo_config(str(tmp_path))
        resolver = TemplateResolver(repo_config)

        # Should raise error for symlink
        with pytest.raises(MeminitError) as exc_info:
            resolver.resolve("PRD")

        assert exc_info.value.code == ErrorCode.INVALID_TEMPLATE_FILE
        assert "symbolic link" in str(exc_info.value).lower()

    def test_oversized_template_rejected(self, tmp_path):
        """Templates larger than 256 KiB are rejected."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Create a template larger than 256 KiB
        large_template = tmp_path / "large.template.md"
        large_template.write_text("x" * (256 * 1024 + 1))

        config_file = tmp_path / "docops.config.yaml"
        config_file.write_text(f"""
project_name: Test
repo_prefix: TEST
docops_version: "2.0"
document_types:
  PRD:
    directory: "10-prd"
    template: large.template.md
""")

        repo_config = load_repo_config(str(tmp_path))
        resolver = TemplateResolver(repo_config)

        with pytest.raises(MeminitError) as exc_info:
            resolver.resolve("PRD")

        assert exc_info.value.code == ErrorCode.INVALID_TEMPLATE_FILE
        assert "size limit" in str(exc_info.value).lower()

    def test_non_md_template_rejected(self, tmp_path):
        """Templates without .md extension are rejected."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Create template with wrong extension
        bad_template = tmp_path / "bad.txt"
        bad_template.write_text("# Bad Template")

        config_file = tmp_path / "docops.config.yaml"
        config_file.write_text(f"""
project_name: Test
repo_prefix: TEST
docops_version: "2.0"
document_types:
  PRD:
    directory: "10-prd"
    template: bad.txt
""")

        repo_config = load_repo_config(str(tmp_path))
        resolver = TemplateResolver(repo_config)

        with pytest.raises(MeminitError) as exc_info:
            resolver.resolve("PRD")

        assert exc_info.value.code == ErrorCode.INVALID_TEMPLATE_FILE
        assert ".md file" in str(exc_info.value)


class TestTemplateResolverCaseInsensitivity:
    """Test case-insensitive type lookup."""

    def test_type_lookup_case_insensitive(self, tmp_path):
        """Document type lookup is case-insensitive."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Create convention template
        templates_dir = docs_dir / "00-governance" / "templates"
        templates_dir.mkdir(parents=True)
        template = templates_dir / "prd.template.md"
        template.write_text("# PRD Template")

        config_file = tmp_path / "docops.config.yaml"
        config_file.write_text("""
project_name: Test
repo_prefix: TEST
docops_version: "2.0"
document_types:
  PRD:
    directory: "10-prd"
""")

        repo_config = load_repo_config(str(tmp_path))
        resolver = TemplateResolver(repo_config)

        # All of these should resolve to the same template
        for variant in ["PRD", "prd", "Prd"]:
            resolution = resolver.resolve(variant)
            assert resolution.source == SOURCE_CONVENTION
            assert "# PRD Template" in resolution.content
