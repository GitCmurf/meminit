"""Frontmatter port for parsing document frontmatter."""
from typing import Protocol, Any


class FrontmatterPort(Protocol):
    """Protocol for parsing frontmatter from documents."""

    def load(self, path: str) -> tuple[dict[str, Any], str]:
        """Load a file and split into frontmatter (dict) and content (str)."""
        ...

    def loads(self, text: str) -> tuple[dict[str, Any], str]:
        """Parse text and split into frontmatter (dict) and content (str)."""
        ...