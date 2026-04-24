"""Output sanitization for user-controlled fields.

All user-controlled fields rendered in HTML or JSON output MUST be sanitised.
Fields failing sanitisation are omitted from ALL channels (HTML and JSON)
and reported with ``W_FIELD_SANITIZATION_FAILED``.
"""

from __future__ import annotations

import html
import re
from typing import Optional

# Valid actor pattern: alphanumeric, dots, underscores, hyphens (PRD strict).
ACTOR_REGEX = re.compile(r"^[a-zA-Z0-9._-]+$")
_SAFE_RE = re.compile(r"^[^<>&\"']+$")

MAX_NOTES_LENGTH = 500
MAX_TITLE_LENGTH = 200
MAX_ASSIGNEE_LENGTH = 120


def sanitize_html(value: str) -> str:
    """HTML-entity-escape a string for safe rendering.

    Converts characters like ``<``, ``>``, ``&``, ``"`` to their
    HTML entity equivalents.
    """
    return html.escape(value, quote=True)


def validate_actor(value: str) -> bool:
    """Check whether *value* is a valid actor/updated_by string."""
    if not value or len(value) > 100:
        return False
    return bool(ACTOR_REGEX.match(value))


def sanitize_actor(value: Optional[str]) -> str:
    """Sanitize an actor/updated_by string to valid format.

    Converts spaces to hyphens, removes invalid characters, and truncates
    to 100 characters. Returns "unknown" if the result is empty or value is None.
    """
    if value is None:
        return "unknown"
    val = str(value).strip().replace(" ", "-")
    val = re.sub(r"[^a-zA-Z0-9._-]", "", val)
    return val[:100] or "unknown"


def escape_markdown_table(value: str) -> str:
    """Escape Markdown table characters (pipe) and newlines.

    Converts pipe characters to their HTML entity and replaces newlines
    with spaces for safe rendering in Markdown tables.
    """
    if not value:
        return ""
    return str(value).replace("|", "&#124;").replace("\r", " ").replace("\n", " ").strip()


def truncate_notes(value: str, max_len: int = MAX_NOTES_LENGTH) -> str:
    """Truncate *value* to *max_len* characters."""
    if len(value) <= max_len:
        return value
    return value[:max_len]


def sanitize_field(
    value: Optional[str],
    *,
    max_length: Optional[int] = MAX_TITLE_LENGTH,
    html_escape: bool = True,
) -> Optional[str]:
    """Sanitize a user-controlled text field.

    Returns the sanitized string or ``None`` if the field is empty.
    Does NOT raise — callers should check the return value and emit
    ``W_FIELD_SANITIZATION_FAILED`` if needed.

    Note: Truncation is applied before HTML escaping. This means the final
    output may exceed ``max_length`` when HTML entities are expanded (e.g.,
    ``<`` becomes ``&lt;``). This behavior is acceptable for current use cases
    where the output is written to files, but callers rendering to HTML should
    account for entity expansion if strict length limits are required.
    """
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    if max_length is not None and len(value) > max_length:
        value = value[:max_length]
    if html_escape:
        if _SAFE_RE.fullmatch(value):
            return value
        value = sanitize_html(value)
    return value
