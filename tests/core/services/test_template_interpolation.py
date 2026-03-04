"""Unit tests for the TemplateInterpolator service."""

import pytest

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.template_interpolation import TemplateInterpolator


class TestTemplateInterpolatorPreferredSyntax:
    """Test preferred {{variable}} syntax."""

    def test_preferred_syntax(self):
        """Test that {{variable}} placeholders are replaced correctly."""
        interpolator = TemplateInterpolator()
        template = "# {{title}}\nOwner: {{owner}}\nStatus: {{status}}"
        result = interpolator.interpolate(
            template,
            title="Test Feature",
            owner="Team A",
            status="Draft"
        )
        assert result == "# Test Feature\nOwner: Team A\nStatus: Draft"

    def test_all_supported_variables(self):
        """Test all supported {{variable}} placeholders."""
        interpolator = TemplateInterpolator()
        template = """---
document_id: {{document_id}}
type: {{type}}
title: {{title}}
status: {{status}}
date: {{date}}
owner: {{owner}}
repo_prefix: {{repo_prefix}}
seq: {{seq}}
area: {{area}}
description: {{description}}
keywords: {{keywords}}
related_ids: {{related_ids}}
---
"""

        result = interpolator.interpolate(
            template,
            document_id="REPO-PRD-001",
            doc_type="PRD",
            title="Test Feature",
            owner="__TBD__",  # Pass owner explicitly
            status="Draft",
            repo_prefix="REPO",
            seq="001",
            area="Engineering",
            description="A test feature",
            keywords=["agile", "scrum"],
            related_ids=["REPO-ADR-001", "REPO-ADR-002"],
        )

        # Verify all substitutions were made
        assert "document_id: REPO-PRD-001" in result
        assert "type: PRD" in result
        assert "title: Test Feature" in result
        assert "status: Draft" in result
        # Date is in ISO format (YYYY-MM-DD)
        assert len(result.split('date: ')[1].split('\n')[0]) == 10  # ISO date length
        assert "owner: __TBD__" in result  # Default value
        assert "repo_prefix: REPO" in result
        assert "seq: 001" in result
        assert "area: Engineering" in result
        assert "description: A test feature" in result
        assert "keywords: agile, scrum" in result
        assert "related_ids: REPO-ADR-001, REPO-ADR-002" in result

    def test_empty_optional_fields(self):
        """Test that optional fields are handled when empty."""
        interpolator = TemplateInterpolator()
        template = "# {{title}}\nArea: {{area}}\nDescription: {{description}}"

        result = interpolator.interpolate(template, title="Test", area=None, description=None)

        # Empty optional fields should result in empty strings
        assert result == "# Test\nArea: \nDescription: "

    def test_list_handling_empty(self):
        """Test list-type fields when empty."""
        interpolator = TemplateInterpolator()
        template = "Keywords: {{keywords}}\nRelated: {{related_ids}}"

        result = interpolator.interpolate(template, keywords=[], related_ids=[])

        assert result == "Keywords: \nRelated: "


class TestTemplateInterpolatorLegacyRejection:
    """Test rejection of legacy placeholder syntax."""

    def test_legacy_placeholder_syntax_rejected(self):
        """Legacy {title} syntax is rejected with INVALID_TEMPLATE_PLACEHOLDER."""
        interpolator = TemplateInterpolator()
        template = "# {title}\nOwner: {{owner}}"

        with pytest.raises(MeminitError) as exc_info:
            interpolator.interpolate(template, title="Test", owner="Team A")

        assert exc_info.value.code == ErrorCode.INVALID_TEMPLATE_PLACEHOLDER
        assert "legacy" in str(exc_info.value).lower()
        assert "{title}" in exc_info.value.details["legacy_syntax"]

    def test_legacy_angle_bracket_rejected(self):
        """Legacy <REPO> syntax is rejected."""
        interpolator = TemplateInterpolator()
        template = "# {{title}}\nPrefix: <REPO>"

        with pytest.raises(MeminitError) as exc_info:
            interpolator.interpolate(template, title="Test")

        assert exc_info.value.code == ErrorCode.INVALID_TEMPLATE_PLACEHOLDER
        assert "<REPO>" in exc_info.value.details["legacy_syntax"]

    def test_legacy_seq_placeholder_rejected(self):
        """Legacy <SEQ> syntax is rejected."""
        interpolator = TemplateInterpolator()
        template = "ID: REPO-PRD-<SEQ>"

        with pytest.raises(MeminitError) as exc_info:
            interpolator.interpolate(template)

        assert exc_info.value.code == ErrorCode.INVALID_TEMPLATE_PLACEHOLDER
        assert "<SEQ>" in exc_info.value.details["legacy_syntax"]


class TestTemplateInterpolatorUnknownVariables:
    """Test rejection of unknown variables."""

    def test_unknown_variables_raise_error(self):
        """Unknown {{variable}} placeholders raise UNKNOWN_TEMPLATE_VARIABLE."""
        interpolator = TemplateInterpolator()
        template = "# {{title}}\nUnknown: {{unknown_var}}"

        with pytest.raises(MeminitError) as exc_info:
            interpolator.interpolate(template, title="Test")

        assert exc_info.value.code == ErrorCode.UNKNOWN_TEMPLATE_VARIABLE
        assert "unknown_var" in exc_info.value.details["unknown_variables"]

    def test_multiple_unknown_variables_listed(self):
        """Multiple unknown variables are all listed in the error."""
        interpolator = TemplateInterpolator()
        template = "{{foo}} {{bar}} {{title}}"

        with pytest.raises(MeminitError) as exc_info:
            interpolator.interpolate(template, title="Test")

        assert exc_info.value.code == ErrorCode.UNKNOWN_TEMPLATE_VARIABLE
        unknown = exc_info.value.details["unknown_variables"]
        assert "foo" in unknown
        assert "bar" in unknown
        assert "title" not in unknown


class TestTemplateInterpolatorNoneHandling:
    """Test handling of None values."""

    def test_none_title_becomes_empty_string(self):
        """None value for title becomes empty string, not literal 'None'."""
        interpolator = TemplateInterpolator()
        template = "# {{title}}"

        result = interpolator.interpolate(template, title=None)

        # Should be empty string, not "None"
        assert result == "# "

    def test_none_description_becomes_empty_string(self):
        """None value for description becomes empty string."""
        interpolator = TemplateInterpolator()
        template = "Description: {{description}}"

        result = interpolator.interpolate(template, description=None)

        assert result == "Description: "

    def test_empty_list_becomes_empty_string(self):
        """Empty list results in empty string for that field."""
        interpolator = TemplateInterpolator()
        template = "Keywords: {{keywords}}"

        result = interpolator.interpolate(template, keywords=[])

        assert result == "Keywords: "
