"""Service for generating filesystem-safe document filenames."""

import re
from typing import Optional


class FilenameBuilder:
    """Service for building document filenames from IDs and titles."""

    @staticmethod
    def generate_filename(doc_id: str, title: Optional[str] = None) -> str:
        """Generate a filesystem-safe filename for a document.

        The filename format is: {type-segment}-{sequence}-{slugified-title}.md
        For example, 'ADR-042-use-hexagonal-architecture.md'.

        Title is slugified: lowercase, spaces to hyphens, non-alphanumeric
        characters removed, consecutive hyphens collapsed.

        Args:
            doc_id: Full document ID (e.g., 'MEMINIT-ADR-042').
            title: Document title to slugify (optional).

        Returns:
            Filename string ending in '.md'.
        """
        if title:
            safe_title = title.lower().replace(" ", "-")
            safe_title = re.sub(r"[^a-z0-9-]", "", safe_title)
            safe_title = re.sub(r"-{2,}", "-", safe_title).strip("-")
            if not safe_title:
                safe_title = "untitled"
        else:
            safe_title = "untitled"

        parts = doc_id.split("-")
        short_id = doc_id.lower()
        if len(parts) >= 3:
            short_id = f"{parts[-2].lower()}-{parts[-1].lower()}"
        return f"{short_id}-{safe_title}.md"
