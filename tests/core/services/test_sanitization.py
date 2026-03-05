"""Tests for sanitization module (PRD-007 FR-8)."""

from meminit.core.services.sanitization import (
    sanitize_field,
    sanitize_html,
    truncate_notes,
    validate_actor,
)


def test_sanitize_html_escapes_tags():
    """<script> is escaped to prevent XSS."""
    assert sanitize_html("<script>alert('xss')</script>") == (
        "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
    )


def test_sanitize_html_escapes_ampersand():
    assert sanitize_html("A & B") == "A &amp; B"


def test_sanitize_html_escapes_quotes():
    assert sanitize_html('said "hello"') == "said &quot;hello&quot;"


def test_validate_actor_valid():
    """Valid actors pass."""
    assert validate_actor("GitCmurf") is True
    assert validate_actor("user.name") is True
    assert validate_actor("ci-bot-v2") is True
    assert validate_actor("user_name") is True


def test_validate_actor_invalid():
    """Invalid actors fail."""
    assert validate_actor("foo<bar>") is False
    assert validate_actor("") is False
    assert validate_actor("a" * 101) is False


def test_truncate_notes():
    """Notes exceeding max_len are truncated."""
    assert truncate_notes("short", max_len=500) == "short"
    assert len(truncate_notes("x" * 501, max_len=500)) == 500


def test_sanitize_field_none():
    assert sanitize_field(None) is None


def test_sanitize_field_empty():
    assert sanitize_field("   ") is None


def test_sanitize_field_escapes():
    result = sanitize_field("<b>bold</b>")
    assert "&lt;b&gt;" in result


def test_sanitize_field_truncates():
    result = sanitize_field("x" * 300, max_length=200)
    assert len(result) <= 200
