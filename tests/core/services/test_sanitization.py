"""Tests for sanitization module (PRD-007 FR-8)."""

from meminit.core.services.sanitization import (
    escape_markdown_table,
    sanitize_actor,
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


# ---------------------------------------------------------------------------
# sanitize_actor
# ---------------------------------------------------------------------------


def test_sanitize_actor_spaces_to_hyphens():
    assert sanitize_actor("john doe") == "john-doe"


def test_sanitize_actor_removes_invalid_chars():
    assert sanitize_actor("a b!@#c") == "a-bc"


def test_sanitize_actor_truncates_to_100():
    long_input = "a" * 150
    assert len(sanitize_actor(long_input)) == 100


def test_sanitize_actor_stringifies_non_string():
    assert sanitize_actor(123) == "123"


def test_sanitize_actor_empty_result_returns_unknown():
    assert sanitize_actor("!@#") == "unknown"
    assert sanitize_actor("") == "unknown"
    assert sanitize_actor(None) == "unknown"


# ---------------------------------------------------------------------------
# escape_markdown_table
# ---------------------------------------------------------------------------


def test_escape_markdown_table_pipes():
    assert escape_markdown_table("a|b") == "a&#124;b"


def test_escape_markdown_table_newlines():
    assert escape_markdown_table("line1\nline2") == "line1 line2"


def test_escape_markdown_table_carriage_returns():
    assert escape_markdown_table("line1\rline2") == "line1 line2"


def test_escape_markdown_table_trims():
    assert escape_markdown_table("  hello  ") == "hello"


def test_escape_markdown_table_empty():
    assert escape_markdown_table("") == ""
    assert escape_markdown_table(None) == ""
