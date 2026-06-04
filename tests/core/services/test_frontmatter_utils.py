"""Test frontmatter_utils module."""
from pathlib import Path

from meminit.core.services.frontmatter_utils import extract_document_id


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_extract_document_id_valid(tmp_path):
    """Extract document_id from valid frontmatter."""
    path = _write(
        tmp_path / "valid_doc.md",
        "---\ndocument_id: MEMINIT-ADR-001\ntype: ADR\n---\n\n# Body\n",
    )
    result = extract_document_id(path)
    assert result == "MEMINIT-ADR-001"


def test_extract_document_id_missing_id(tmp_path):
    """Return None when document_id is missing."""
    path = _write(tmp_path / "no_id_doc.md", "---\ntype: ADR\n---\n\n# Body\n")
    assert extract_document_id(path) is None


def test_extract_document_id_corrupted_frontmatter(tmp_path):
    """Return None for corrupted frontmatter."""
    path = _write(
        tmp_path / "corrupted_doc.md",
        "---\ndocument_id: [unclosed\n  : : :\n---\n\n# Body\n",
    )
    assert extract_document_id(path) is None


def test_extract_document_id_no_frontmatter(tmp_path):
    """Return None for files without frontmatter."""
    path = _write(tmp_path / "plain_doc.md", "# Just a heading\n\nNo frontmatter here.\n")
    assert extract_document_id(path) is None


def test_extract_document_id_not_exist():
    """Return None for non-existent files."""
    result = extract_document_id(Path("/non/existent/path.md"))
    assert result is None
