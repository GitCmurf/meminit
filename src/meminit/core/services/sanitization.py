"""Output sanitization for user-controlled fields (PRD-007 FR-8).

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

# Maximum notes length.
MAX_NOTES_LENGTH = 500

# Maximum title/description length.
MAX_TITLE_LENGTH = 200


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
    """
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    if max_length is not None and len(value) > max_length:
        value = value[:max_length]
    if html_escape:
        value = sanitize_html(value)
    return value
