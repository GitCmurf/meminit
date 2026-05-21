"""Tests for repo_config.py service."""

from meminit.core.services.repo_config import _normalize_type_directories


class TestNormalizeTypeDirectories:
    """Tests for _normalize_type_directories (Finding #18)."""

    def test_basic_normalization(self):
        """Standard type directories are normalized correctly."""
        result = _normalize_type_directories("docs", {"ADR": "adr", "PRD": "prd"})
        assert result == {"ADR": "adr", "PRD": "prd"}

    def test_strips_leading_docs_root(self):
        """Leading docs_root prefix is stripped."""
        result = _normalize_type_directories("docs", {"ADR": "docs/adr"})
        assert result == {"ADR": "adr"}

    def test_strips_leading_dot_slash(self):
        """Leading ./ is stripped."""
        result = _normalize_type_directories("docs", {"ADR": "./adr"})
        assert result == {"ADR": "adr"}

    def test_skips_absolute_paths(self):
        """Absolute paths are skipped."""
        result = _normalize_type_directories("docs", {"ADR": "/etc/adr"})
        assert result == {}

    def test_rejects_parent_traversal_simple(self):
        """Simple ../ reference is rejected."""
        result = _normalize_type_directories("docs", {"ADR": "../adr"})
        assert result == {}

    def test_rejects_parent_traversal_nested(self):
        """Nested ../ reference is rejected."""
        result = _normalize_type_directories("docs", {"ADR": "foo/../adr"})
        assert result == {}

    def test_rejects_deep_parent_traversal(self):
        """Deep ../ traversal is rejected."""
        result = _normalize_type_directories("docs", {"ADR": "../../etc/adr"})
        assert result == {}

    def test_skips_non_string_values(self):
        """Non-string values are skipped."""
        result = _normalize_type_directories("docs", {"ADR": 42})
        assert result == {}

    def test_skips_non_string_keys(self):
        """Non-string keys are skipped."""
        result = _normalize_type_directories("docs", {1: "adr"})
        assert result == {}

    def test_mixed_valid_and_invalid(self):
        """Valid entries survive alongside rejected traversal entries."""
        result = _normalize_type_directories("docs", {"ADR": "adr", "PRD": "../prd", "GOV": "gov"})
        assert result == {"ADR": "adr", "GOV": "gov"}
        assert "PRD" not in result
