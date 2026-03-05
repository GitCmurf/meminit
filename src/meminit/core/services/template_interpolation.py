"""Template interpolation engine for Meminit Templates v2.

This module provides the TemplateInterpolator class which implements
single {{variable}} syntax interpolation with legacy syntax rejection.

See PRD-006 FR-3 for the complete interpolation specification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

from meminit.core.services.error_codes import ErrorCode, MeminitError


class TemplateInterpolator:
    """Interpolates template variables using {{variable}} syntax only.

    Supported variables (FR-3):
    - {{title}} - Document title
    - {{document_id}} - Full document ID
    - {{owner}} - Document owner
    - {{status}} - Document status
    - {{date}} - Current date (ISO 8601)
    - {{repo_prefix}} - Repository prefix from document ID
    - {{seq}} - Document sequence number
    - {{type}} - Document type
    - {{area}} - Document area
    - {{description}} - Document description (optional)
    - {{keywords}} - Comma-separated keywords (optional)
    - {{related_ids}} - Comma-separated related IDs (optional)

    Legacy syntax ({title}, <REPO>, etc.) is rejected with
    INVALID_TEMPLATE_PLACEHOLDER.

    Unknown variables are rejected with UNKNOWN_TEMPLATE_VARIABLE.
    """

    # Preferred {{variable}} patterns - compiled on initialization
    _PREFERRED_PATTERNS: List[tuple[re.Pattern[str], str]] = [
        (re.compile(r'\{\{\s*title\s*\}\}'), 'title'),
        (re.compile(r'\{\{\s*document_id\s*\}\}'), 'document_id'),
        (re.compile(r'\{\{\s*owner\s*\}\}'), 'owner'),
        (re.compile(r'\{\{\s*status\s*\}\}'), 'status'),
        (re.compile(r'\{\{\s*date\s*\}\}'), 'date'),
        (re.compile(r'\{\{\s*repo_prefix\s*\}\}'), 'repo_prefix'),
        (re.compile(r'\{\{\s*seq\s*\}\}'), 'seq'),
        (re.compile(r'\{\{\s*type\s*\}\}'), 'type'),
        (re.compile(r'\{\{\s*area\s*\}\}'), 'area'),
        (re.compile(r'\{\{\s*description\s*\}\}'), 'description'),
        (re.compile(r'\{\{\s*keywords\s*\}\}'), 'keywords'),
        (re.compile(r'\{\{\s*related_ids\s*\}\}'), 'related_ids'),
    ]

    # Legacy patterns to detect and reject - compiled on initialization
    _LEGACY_PATTERNS: List[re.Pattern[str]] = [
        re.compile(r'(?<!\{)\{title\}(?!\})'),
        re.compile(r'(?<!\{)\{status\}(?!\})'),
        re.compile(r'(?<!\{)\{owner\}(?!\})'),
        re.compile(r'(?<!\{)\{area\}(?!\})'),
        re.compile(r'(?<!\{)\{description\}(?!\})'),
        re.compile(r'(?<!\{)\{keywords\}(?!\})'),
        re.compile(r'(?<!\{)\{related_ids\}(?!\})'),
        re.compile(r'<REPO>'),
        re.compile(r'<PROJECT>'),
        re.compile(r'<SEQ>'),
        re.compile(r'<YYYY-MM-DD>'),
        re.compile(r'<Decision Title>'),
        re.compile(r'<Feature Title>'),
        re.compile(r'<Team or Person>'),
        re.compile(r'<AREA>'),
    ]

    # Pattern to find unknown {{...}} variables
    _UNKNOWN_PATTERN = re.compile(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}')

    def __init__(self) -> None:
        """Initialize the interpolator with compiled patterns."""
        self._preferred = self._PREFERRED_PATTERNS
        self._legacy = self._LEGACY_PATTERNS
        self._unknown = self._UNKNOWN_PATTERN

    def interpolate(
        self,
        template: str,
        **kwargs: Any
    ) -> str:
        """Interpolate variables in a template.

        Replaces all {{variable}} placeholders with their values.
        Raises errors for legacy syntax or unknown variables.

        **Security note:** Substitution is safe against injection because:
        1. Only an explicit allowlist of variable names is matched
           (compiled regexes in ``_PREFERRED_PATTERNS``).
        2. Replacement uses ``re.sub`` with a *lambda* callable, so
           replacement strings cannot trigger backreference expansion.
        3. Any ``{{...}}`` token not in the allowlist is rejected by
           ``_raise_on_unknown_variables``.

        Args:
            template: The template content with {{variable}} placeholders.
            **kwargs: Variable values. Supported keys:
                title, document_id, owner, status, repo_prefix, seq,
                doc_type, area, description, keywords (list), related_ids (list)

        Returns:
            The interpolated template content.

        Raises:
            MeminitError: With INVALID_TEMPLATE_PLACEHOLDER if legacy syntax found.
            MeminitError: With UNKNOWN_TEMPLATE_VARIABLE if unknown variables found.
        """
        # Validate template tokens before injecting user-provided values.
        # This prevents false positives if user data (e.g. title) contains placeholders.
        self._raise_on_legacy_tokens(template)
        self._raise_on_unknown_variables(template)

        substitutions: Dict[str, str] = self._build_substitutions(**kwargs)
        result = template

        # Apply preferred {{variable}} patterns
        # Use lambda to avoid backreference interpretation in replacement string
        # Sanitize values to prevent injection into markdown comments and markers
        for pattern, key in self._preferred:
            value = substitutions.get(key, '')
            # Sanitize to prevent injection attacks
            sanitized_value = value.replace("<!--", "&lt;!--").replace("-->", "--&gt;").replace("\n", " ").replace("\r", " ")
            result = pattern.sub(lambda m, v=sanitized_value: v, result)

        return result

    def _build_substitutions(self, **kwargs: Any) -> Dict[str, str]:
        """Build the substitution dictionary from kwargs.

        Handles list-type fields (keywords, related_ids) by joining them.
        Coerces None values to empty strings to avoid literal "None" in output.
        """
        keywords = kwargs.get('keywords', [])
        related_ids = kwargs.get('related_ids', [])

        return {
            'title': str(kwargs.get('title') or ''),
            'document_id': str(kwargs.get('document_id') or ''),
            'owner': str(kwargs.get('owner') or ''),
            'status': str(kwargs.get('status') or ''),
            'date': date.today().isoformat(),
            'repo_prefix': str(kwargs.get('repo_prefix') or ''),
            'seq': str(kwargs.get('seq')) if kwargs.get('seq') is not None else '',
            'type': str(kwargs.get('doc_type') or ''),
            'area': str(kwargs.get('area') or ''),
            'description': str(kwargs.get('description') or ''),
            'keywords': ', '.join(keywords) if keywords else '',
            'related_ids': ', '.join(related_ids) if related_ids else '',
        }

    def _raise_on_legacy_tokens(self, content: str) -> None:
        """Check for legacy placeholder syntax and raise error if found.

        Scans for patterns like {title}, <REPO>, <SEQ>, etc.
        """
        for pattern in self._legacy:
            match = pattern.search(content)
            if match:
                raise MeminitError(
                    code=ErrorCode.INVALID_TEMPLATE_PLACEHOLDER,
                    message=f"Legacy placeholder syntax detected: {match.group(0)}",
                    details={
                        "legacy_syntax": match.group(0),
                        "use_syntax": "{{variable}}",
                        "line": self._find_line_number(content, match.start())
                    }
                )

    def _raise_on_unknown_variables(self, content: str) -> None:
        """Check for unknown {{variable}} placeholders and raise error if found.

        Scans for any {{...}} patterns that weren't substituted.
        """
        # Compute known vars set inline from _PREFERRED_PATTERNS
        known_vars = {key for _, key in self._preferred}
        unknown = set()
        for match in self._unknown.finditer(content):
            var_name = match.group(1)
            if var_name not in known_vars:
                unknown.add(var_name)

        if unknown:
            raise MeminitError(
                code=ErrorCode.UNKNOWN_TEMPLATE_VARIABLE,
                message=f"Unknown template variables: {', '.join(sorted(unknown))}",
                details={
                    "unknown_variables": sorted(unknown),
                    "known_variables": sorted(known_vars)
                }
            )

    def _find_line_number(self, content: str, pos: int) -> int:
        """Find the line number for a position in the content."""
        return content[:pos].count('\n') + 1


@dataclass(frozen=True)
class InterpolationResult:
    """Result of template interpolation.

    Attributes:
        content: The interpolated template content.
        warnings: Optional list of warnings (e.g., empty optional fields).
    """
    content: str
    warnings: List[str]
