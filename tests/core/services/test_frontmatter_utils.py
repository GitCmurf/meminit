"""Test frontmatter_utils module."""
from pathlib import Path

import pytest

from meminit.core.services.frontmatter_utils import extract_document_id


def test_extract_document_id_valid():
    """Extract document_id from valid frontmatter."""
    path = Path(__file__).parent.parent / "fixtures" / "valid_doc.md"
    if path.exists():
        result = extract_document_id(path)
        assert result is not None
        assert isinstance(result, str)


def test_extract_document_id_missing_id():
    """Return None when document_id is missing."""
    path = Path(__file__).parent.parent / "fixtures" / "no_id_doc.md"
    if path.exists():
        result = extract_document_id(path)
        assert result is None


def test_extract_document_id_corrupted_frontmatter():
    """Return None for corrupted frontmatter."""
    path = Path(__file__).parent.parent / "fixtures" / "corrupted_doc.md"
    if path.exists():
        result = extract_document_id(path)
        assert result is None


def test_extract_document_id_no_frontmatter():
    """Return None for files without frontmatter."""
    path = Path(__file__).parent.parent / "fixtures" / "plain_doc.md"
    if path.exists():
        result = extract_document_id(path)
        assert result is None


def test_extract_document_id_not_exist():
    """Return None for non-existent files."""
    result = extract_document_id(Path("/non/existent/path.md"))
    assert result is None