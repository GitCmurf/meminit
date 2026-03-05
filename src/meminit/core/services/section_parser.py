"""Section parser for Meminit Templates v2.

This module provides the SectionParser class which implements
code-fence-aware section marker parsing with duplicate detection.

See PRD-006 FR-5, FR-12, FR-13, FR-15 for the complete specification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, List, Optional, Tuple

from meminit.core.services.error_codes import ErrorCode, MeminitError

# Max lines to search for heading around section marker
_HEADING_SEARCH_RANGE: Final = 5


@dataclass(frozen=True)
class SectionMarker:
    """Represents a parsed section marker with its bounds and content.

    Attributes:
        id: The section identifier from the MEMINIT_SECTION comment.
        heading: The nearest ## heading before/after the marker.
        line: The line number of the heading (1-based).
        marker_line: The line number of the <!-- MEMINIT_SECTION: --> marker (1-based).
        content_start_line: The line number where editable content starts (1-based).
        content_end_line: The line number where editable content ends (1-based).
            This is the line before the next section marker or end of file.
        required: Whether this section is required (non-optional).
        agent_prompt: The combined text from all <!-- AGENT: --> prompts in this section.
        initial_content: The initial template content in the editable span
            (excluding agent prompts).
    """
    id: str
    heading: str
    line: int
    marker_line: int
    content_start_line: int
    content_end_line: int
    required: bool
    agent_prompt: Optional[str]
    initial_content: Optional[str]


class SectionParser:
    """Parses section markers from template content.

    Features:
    - Code-fence-aware: Ignores markers inside triple-backtick code blocks (FR-12)
    - Duplicate detection: Raises error for duplicate section IDs (FR-13)
    - Marker-to-marker boundaries: Content span is from one marker to the next (FR-15)
    - Agent prompt extraction: Captures <!-- AGENT: --> prompts
    """

    # Patterns for section markers and agent prompts
    SECTION_MARKER_PATTERN = re.compile(r'^\s*<!--\s*MEMINIT_SECTION:\s*([a-zA-Z0-9_-]+)\s*-->\s*$')
    AGENT_PROMPT_PATTERN = re.compile(r'^\s*<!--\s*AGENT:\s*(.*?)\s*-->\s*$')
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$')

    # Pattern for code fences (supports various backtick counts)
    CODE_FENCE_PATTERN = re.compile(r'^(`{3,})')

    def parse_sections(self, content: str) -> List[SectionMarker]:
        """Parse section markers from template content.

        Args:
            content: The template content to parse.

        Returns:
            A list of SectionMarker objects for each section found.

        Raises:
            MeminitError: With DUPLICATE_SECTION_ID if duplicate IDs are found.
        """
        lines = content.splitlines()
        sections: List[SectionMarker] = []
        section_ids_seen: dict[str, int] = {}  # Maps section_id -> first line number

        # Parser state
        in_code_fence = False
        current_fence_char: str = ''
        current_fence_len: int = 0

        # Current section being built
        current_id: Optional[str] = None
        current_marker_line: int = 0
        current_agent_prompts: List[str] = []
        current_content_start: int = 0

        for i, line in enumerate(lines, start=1):
            # Track code fence state (FR-12)
            fence_match = self.CODE_FENCE_PATTERN.match(line)
            if fence_match:
                fence_char = fence_match.group(1)[0]  # First char (should be `)
                fence_len = len(fence_match.group(1))

                if in_code_fence and fence_char == current_fence_char and fence_len >= current_fence_len:
                    # Closing fence
                    in_code_fence = False
                    current_fence_char = ''
                    current_fence_len = 0
                elif not in_code_fence:
                    # Opening fence
                    in_code_fence = True
                    current_fence_char = fence_char
                    current_fence_len = fence_len
                continue

            # Skip everything inside code fences
            if in_code_fence:
                continue

            # Check for section marker
            marker_match = self.SECTION_MARKER_PATTERN.match(line)
            if marker_match:
                section_id = marker_match.group(1)

                # Check for duplicate IDs (FR-13)
                if section_id in section_ids_seen:
                    raise MeminitError(
                        code=ErrorCode.DUPLICATE_SECTION_ID,
                        message=f"Duplicate section ID: {section_id}",
                        details={
                            "section_id": section_id,
                            "first_line": section_ids_seen[section_id],
                            "duplicate_line": i
                        }
                    )
                section_ids_seen[section_id] = i

                # Finalize previous section if exists
                if current_id is not None:
                    sections.append(self._finalize_section(
                        lines=lines,
                        section_id=current_id,
                        marker_line=current_marker_line,
                        agent_prompts=current_agent_prompts,
                        content_start=current_content_start,
                        content_end=i - 1,  # Content ends before this marker
                        heading_pattern=self.HEADING_PATTERN
                    ))

                # Start new section
                current_id = section_id
                current_marker_line = i
                current_agent_prompts = []
                current_content_start = 0  # Will be set when we find non-prompt content
                continue

            # Check for AGENT prompt (only if we're in a section)
            if current_id is not None:
                agent_match = self.AGENT_PROMPT_PATTERN.match(line)
                if agent_match:
                    current_agent_prompts.append(agent_match.group(1).strip())
                    continue

            # Track content start (first non-empty, non-marker, non-agent line after marker)
            if current_id is not None and current_content_start == 0:
                stripped = line.strip()
                # Skip empty lines, markers, and agent prompts
                if stripped and not self.SECTION_MARKER_PATTERN.match(line) and not self.AGENT_PROMPT_PATTERN.match(line):
                    current_content_start = i

        # Don't forget the last section
        if current_id is not None:
            sections.append(self._finalize_section(
                lines=lines,
                section_id=current_id,
                marker_line=current_marker_line,
                agent_prompts=current_agent_prompts,
                content_start=current_content_start,
                content_end=len(lines),  # End of file
                heading_pattern=self.HEADING_PATTERN
            ))

        return sections

    def _finalize_section(
        self,
        lines: List[str],
        section_id: str,
        marker_line: int,
        agent_prompts: List[str],
        content_start: int,
        content_end: int,
        heading_pattern: re.Pattern[str]
    ) -> SectionMarker:
        """Finalize a section by extracting heading and initial content.

        Args:
            lines: All lines in the document.
            section_id: The section identifier.
            marker_line: The line number of the section marker.
            agent_prompts: List of agent prompt texts.
            content_start: The line number where content starts (0 if none).
            content_end: The line number where content ends.
            heading_pattern: The heading regex pattern.

        Returns:
            A SectionMarker object with all fields populated.
        """
        # Find the heading (scan backwards first, then forwards, within a reasonable range)
        heading = ""
        heading_line = marker_line

        # First scan backwards from marker
        for i in range(marker_line - 2, max(-1, marker_line - 2 - _HEADING_SEARCH_RANGE), -1):
            if i < 0 or i >= len(lines):
                continue
            heading_match = heading_pattern.match(lines[i])
            if heading_match:
                heading = lines[i].rstrip()
                heading_line = i + 1
                break

        # If not found backwards, scan forwards from marker
        if not heading:
            for i in range(marker_line - 1, min(marker_line + _HEADING_SEARCH_RANGE, len(lines))):
                if i < 0 or i >= len(lines):
                    continue
                heading_match = heading_pattern.match(lines[i])
                if heading_match:
                    heading = lines[i].rstrip()
                    heading_line = i + 1
                    break

        # Extract initial content (excluding agent prompts)
        initial_content = None
        if content_start > 0 and content_end >= content_start:
            content_lines = []
            for i in range(content_start - 1, content_end):
                if i < 0 or i >= len(lines):
                    continue
                # Skip agent prompt lines in the content
                if not self.AGENT_PROMPT_PATTERN.match(lines[i]):
                    content_lines.append(lines[i])
            initial_content = "\n".join(content_lines)

        # Calculate correct content start line (strictly after heading, falling back to marker)
        actual_start_line = content_start
        if actual_start_line > 0:
            if heading and actual_start_line <= heading_line:
                # Content must start after the heading
                actual_start_line = heading_line + 1

        return SectionMarker(
            id=section_id,
            heading=heading,
            line=heading_line,
            marker_line=marker_line,
            content_start_line=actual_start_line if actual_start_line > 0 else marker_line,
            content_end_line=content_end,
            required=True,  # Can be made configurable later
            agent_prompt="\n".join(agent_prompts) if agent_prompts else None,
            initial_content=initial_content
        )

    def extract_agent_prompts(self, content: str) -> dict[str, str]:
        """Extract all AGENT prompts keyed by section ID.

        Convenience method that parses sections and returns a mapping
        of section_id -> agent_prompt text.

        Args:
            content: The template content to parse.

        Returns:
            A dictionary mapping section IDs to their agent prompts.
            Sections without prompts are not included.
        """
        sections = self.parse_sections(content)
        return {
            s.id: s.agent_prompt
            for s in sections
            if s.agent_prompt
        }
