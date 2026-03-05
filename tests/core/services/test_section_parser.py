"""Unit tests for the SectionParser service."""

import pytest

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.section_parser import SectionParser, SectionMarker


class TestSectionParserBasicParsing:
    """Test basic section marker parsing."""

    def test_section_markers_parsed(self):
        """Basic section markers are parsed correctly."""
        parser = SectionParser()
        content = """<!-- MEMINIT_SECTION: title -->

# Title

<!-- MEMINIT_SECTION: context -->

## Context

Content here.
"""
        sections = parser.parse_sections(content)

        assert len(sections) == 2
        assert sections[0].id == "title"
        assert sections[1].id == "context"

    def test_section_marker_fields_populated(self):
        """All SectionMarker fields are populated correctly."""
        parser = SectionParser()
        content = """<!-- MEMINIT_SECTION: test_section -->

## Test Section

Some content.

<!-- MEMINIT_SECTION: next_section -->

## Next Section

More content.
"""
        sections = parser.parse_sections(content)

        assert len(sections) == 2

        test_section = sections[0]
        assert test_section.id == "test_section"
        assert test_section.heading == "## Test Section"
        assert test_section.marker_line == 1
        assert test_section.content_start_line > 0
        assert test_section.content_end_line > test_section.content_start_line
        assert test_section.required is True


class TestSectionParserCodeFenceProtection:
    """Test code-fence-aware marker detection."""

    def test_section_markers_inside_code_fences_ignored(self):
        """Section markers inside code fences are ignored."""
        parser = SectionParser()
        content = '''# Document

<!-- MEMINIT_SECTION: real_section -->

## Real Section

This is real.

```markdown
<!-- MEMINIT_SECTION: fake_section -->

## Fake Section

This is example code, not a real section.
```

## More Real Content

<!-- MEMINIT_SECTION: another_section -->

## Another Section
'''

        sections = parser.parse_sections(content)

        # Should only parse real sections (not the one inside code fence)
        section_ids = [s.id for s in sections]
        assert "real_section" in section_ids
        assert "another_section" in section_ids
        assert "fake_section" not in section_ids

    def test_multiple_code_blocks_handled(self):
        """Multiple code blocks are tracked correctly."""
        parser = SectionParser()
        content = '''<!-- MEMINIT_SECTION: section1 -->

## Section 1

```
Code block 1
```

```
Code block 2
```

<!-- MEMINIT_SECTION: section2 -->

## Section 2
'''

        sections = parser.parse_sections(content)
        assert len(sections) == 2
        assert sections[0].id == "section1"
        assert sections[1].id == "section2"


class TestSectionParserDuplicateDetection:
    """Test duplicate section ID detection."""

    def test_duplicate_section_id_raises_error(self):
        """Duplicate section IDs raise DUPLICATE_SECTION_ID error."""
        parser = SectionParser()
        content = """<!-- MEMINIT_SECTION: title -->

## Title 1

<!-- MEMINIT_SECTION: title -->

## Title 2
"""

        with pytest.raises(MeminitError) as exc_info:
            parser.parse_sections(content)

        assert exc_info.value.code == ErrorCode.DUPLICATE_SECTION_ID
        assert exc_info.value.details["section_id"] == "title"


class TestSectionParserAgentPrompts:
    """Test AGENT prompt extraction."""

    def test_agent_prompt_extracted(self):
        """AGENT prompts are captured correctly."""
        parser = SectionParser()
        content = """<!-- MEMINIT_SECTION: section1 -->

<!-- AGENT: Write a clear summary -->

## Section 1

Content.
"""

        sections = parser.parse_sections(content)
        assert len(sections) == 1
        assert sections[0].agent_prompt == "Write a clear summary"

    def test_multiple_agent_prompts_combined(self):
        """Multiple AGENT prompts in a section are combined."""
        parser = SectionParser()
        content = """<!-- MEMINIT_SECTION: section1 -->

<!-- AGENT: First instruction -->
<!-- AGENT: Second instruction -->
<!-- AGENT: Third instruction -->

## Section 1
"""

        sections = parser.parse_sections(content)
        assert len(sections) == 1
        expected_prompts = "First instruction\nSecond instruction\nThird instruction"
        assert sections[0].agent_prompt == expected_prompts


class TestSectionParserBoundaries:
    """Test marker-to-marker section boundaries."""

    def test_section_boundaries_marker_to_marker(self):
        """Section content spans from one marker to the next."""
        parser = SectionParser()
        content = """<!-- MEMINIT_SECTION: section1 -->

## Section 1

Content for section 1.

<!-- MEMINIT_SECTION: section2 -->

## Section 2

Content for section 2.
"""

        sections = parser.parse_sections(content)
        assert len(sections) == 2

        section1 = sections[0]
        section2 = sections[1]

        # section1 content should end before section2 marker
        assert section1.content_end_line < section2.marker_line

        # section2 content should extend to end of file
        assert section2.content_end_line > section2.marker_line


class TestSectionParserInitialContent:
    """Test initial content extraction."""

    def test_initial_content_extracted(self):
        """Initial content excludes AGENT prompts."""
        parser = SectionParser()
        content = """<!-- MEMINIT_SECTION: section1 -->

<!-- AGENT: Guidance for agent -->

Placeholder content here.

More placeholder.
"""

        sections = parser.parse_sections(content)
        assert len(sections) == 1

        # Initial content should exclude AGENT prompts
        initial = sections[0].initial_content
        assert "Guidance for agent" not in initial
        assert "Placeholder content here" in initial


class TestSectionParserEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_content(self):
        """Empty content returns empty section list."""
        parser = SectionParser()
        sections = parser.parse_sections("")
        assert len(sections) == 0

    def test_content_without_markers(self):
        """Content without markers returns empty list."""
        parser = SectionParser()
        content = "# Just a heading\n\nSome content"
        sections = parser.parse_sections(content)
        assert len(sections) == 0

    def test_heading_search_range(self):
        """Heading search is limited to reasonable range."""
        parser = SectionParser()
        # Create content with heading far from marker (>5 lines)
        content = """<!-- MEMINIT_SECTION: section1 -->

Line 1
Line 2
Line 3
Line 4
Line 5
Line 6
Line 7
Line 8

## Far Heading

Content.
"""

        sections = parser.parse_sections(content)
        assert len(sections) == 1
        # Heading should not be found (too far)
        assert sections[0].heading == ""
        # When no heading found, line defaults to marker_line
        assert sections[0].marker_line == 1
        assert sections[0].line == sections[0].marker_line


class TestSectionParserIDValidation:
    """Test section ID format validation."""

    def test_section_id_with_hyphen(self):
        """Section IDs with hyphens are valid."""
        parser = SectionParser()
        content = """<!-- MEMINIT_SECTION: test-section -->

## Test Section
"""
        sections = parser.parse_sections(content)
        assert len(sections) == 1
        assert sections[0].id == "test-section"

    def test_section_id_with_underscore(self):
        """Section IDs with underscores are valid."""
        parser = SectionParser()
        content = """<!-- MEMINIT_SECTION: test_section -->

## Test Section
"""
        sections = parser.parse_sections(content)
        assert len(sections) == 1
        assert sections[0].id == "test_section"

    def test_section_id_with_numbers(self):
        """Section IDs with numbers are valid."""
        parser = SectionParser()
        content = """<!-- MEMINIT_SECTION: section1 -->

## Section 1
"""
        sections = parser.parse_sections(content)
        assert len(sections) == 1
        assert sections[0].id == "section1"
