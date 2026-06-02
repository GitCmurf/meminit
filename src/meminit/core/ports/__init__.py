"""Protocol ports for dependency injection.

This module defines Protocol interfaces for external dependencies,
enabling better testability and future flexibility in storage backends.
"""
from typing import Protocol


class FileSystemPort(Protocol):
    """Protocol for filesystem operations."""

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """Read a file as text."""
        ...

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> None:
        """Write content to a file."""
        ...

    def exists(self, path: str) -> bool:
        """Check if a path exists."""
        ...

    def is_file(self, path: str) -> bool:
        """Check if a path is a file."""
        ...

    def is_dir(self, path: str) -> bool:
        """Check if a path is a directory."""
        ...

    def resolve(self, path: str) -> str:
        """Resolve a path to an absolute path."""
        ...

    def mkdir(self, path: str, parents: bool = True, exist_ok: bool = True) -> None:
        """Create a directory."""
        ...

    def iterdir(self, path: str) -> list[str]:
        """List entries in a directory."""
        ...

    def read_bytes(self, path: str) -> bytes:
        """Read a file as bytes."""
        ...

    def write_bytes(self, path: str, data: bytes) -> None:
        """Write bytes to a file."""
        ...