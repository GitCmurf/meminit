"""Safe storage port for atomic writes and path validation."""
from typing import Protocol


class SafeStoragePort(Protocol):
    """Protocol for safe storage operations."""

    def atomic_write(
        self,
        target_path: str,
        content: str,
        encoding: str = "utf-8",
        file_mode: int | None = None,
    ) -> None:
        """Write content to a file atomically."""
        ...

    def ensure_safe_write_path(self, root_dir: str, target_path: str) -> None:
        """Validate that a write path is safe (no path traversal)."""
        ...