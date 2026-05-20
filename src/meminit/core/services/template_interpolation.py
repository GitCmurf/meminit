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

    # All known variable names for single-pass regex and validation.
    _KNOWN_VARIABLES = (
        'title', 'document_id', 'owner', 'status', 'date',
        'repo_prefix', 'seq', 'type', 'area', 'description',
        'keywords', 'related_ids',
    )

    # Single regex matching all known {{variable}} patterns.
    # Captures the variable name as group 1 for lookup-based replacement.
    _ALL_VARIABLES_PATTERN = re.compile(
        r'\{\{\s*(' + '|'.join(_KNOWN_VARIABLES) + r')\s*\}\}'
    )

    # Legacy patterns to detect and reject - compiled on initialization
    _LEGACY_PATTERNS: tuple[re.Pattern[str], ...] = (
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
    )

    # Pattern to find all {{...}} variables to reject unknown or malformed ones
    _UNKNOWN_PATTERN = re.compile(r'\{\{\s*([^{}]*?)\s*\}\}')

    def __init__(self) -> None:
        """Initialize the interpolator with compiled patterns."""
        self._known_vars = set(self._KNOWN_VARIABLES)
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
         1. Only an explicit allowlist of variable names is matched via a
            single regex (``_ALL_VARIABLES_PATTERN``).
         2. Replacement uses ``re.sub`` with a lookup *function*, so
            replacement strings cannot trigger backreference expansion
            or re-substitution of injected placeholder-like text.
         3. Any ``{{...}}`` token not in the allowlist is rejected by
            ``_raise_on_unknown_variables`` **before** any substitution.

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

        def _replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            value = substitutions.get(var_name, '')
            # Sanitize to prevent injection attacks
            return value.replace("<!--", "&lt;!--").replace("-->", "--&gt;").replace("\n", " ").replace("\r", " ")

        return self._ALL_VARIABLES_PATTERN.sub(_replacer, template)

    def _build_substitutions(self, **kwargs: Any) -> Dict[str, str]:
        """Build the substitution dictionary from kwargs.

        Handles list-type fields (keywords, related_ids) by joining them.
        Validates list fields are actually lists of strings to prevent
        silent mangling (e.g. a string being iterated character-by-character).
        Coerces None values to empty strings to avoid literal "None" in output.
        """
        keywords = kwargs.get('keywords', [])
        related_ids = kwargs.get('related_ids', [])

        def _validate_list_field(value: Any, name: str) -> list[str]:
            if value is None:
                return []
            if not isinstance(value, list):
                raise MeminitError(
                    ErrorCode.INVALID_TEMPLATE_PLACEHOLDER,
                    f"'{name}' must be a list of strings, got {type(value).__name__}",
                    details={"field": name, "type": type(value).__name__},
                )
            for i, item in enumerate(value):
                if not isinstance(item, str):
                    raise MeminitError(
                        ErrorCode.INVALID_TEMPLATE_PLACEHOLDER,
                        f"'{name}' must contain only strings, "
                        f"item at index {i} is {type(item).__name__}",
                        details={"field": name, "index": i, "type": type(item).__name__},
                    )
            return value

        validated_keywords = _validate_list_field(keywords, 'keywords')
        validated_related_ids = _validate_list_field(related_ids, 'related_ids')

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
            'keywords': ', '.join(validated_keywords) if validated_keywords else '',
            'related_ids': ', '.join(validated_related_ids) if validated_related_ids else '',
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
        unknown = set()
        for match in self._unknown.finditer(content):
            var_name = match.group(1).strip()
            if var_name not in self._known_vars:
                unknown.add(var_name or "<empty>")

        if unknown:
            raise MeminitError(
                code=ErrorCode.UNKNOWN_TEMPLATE_VARIABLE,
                message=f"Unknown template variables: {', '.join(sorted(unknown))}",
                details={
                    "unknown_variables": sorted(unknown),
                    "known_variables": sorted(self._known_vars)
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
