"""Utility functions for working with frontmatter documents."""
from pathlib import Path
from typing import Any, Optional

import frontmatter


def extract_document_id(path: Path) -> Optional[str]:
    """Extract document_id from a file's frontmatter.

    Defensively handles:
    - Missing or corrupted frontmatter
    - Missing document_id field
    - None metadata

    Args:
        path: Path to the markdown file.

    Returns:
        Document ID as string if found, None otherwise.
    """
    try:
        post = frontmatter.load(str(path))
    except Exception:
        return None

    metadata = getattr(post, "metadata", None)
    if not metadata:
        return None

    doc_id = metadata.get("document_id")
    if doc_id:
        return str(doc_id)
    return None