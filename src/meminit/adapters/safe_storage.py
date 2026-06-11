"""Local safe storage adapter implementing SafeStoragePort."""
from pathlib import Path

from meminit.core.ports.safe_storage import SafeStoragePort
from meminit.core.services.safe_fs import atomic_write, ensure_safe_write_path


class LocalSafeStorage:
    """Concrete safe storage adapter using safe_fs functions."""

    def atomic_write(
        self,
        target_path: str,
        content: str,
        encoding: str = "utf-8",
        file_mode: int | None = None,
    ) -> None:
        return atomic_write(Path(target_path), content, encoding=encoding, file_mode=file_mode)

    def ensure_safe_write_path(self, root_dir: str, target_path: str) -> None:
        return ensure_safe_write_path(root_dir=Path(root_dir), target_path=Path(target_path))
