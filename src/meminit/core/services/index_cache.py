"""Repo-local index cache surface.

This service owns the cache directory and manifest-inspection behavior
currently exposed by the CLI. It deliberately does not implement
changed-file reuse; that remains MEMINIT-PLAN-014 Workstream D.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.path_utils import relative_path_string
from meminit.core.services.safe_fs import ensure_safe_write_path


class IndexCache:
    """Manage the repo-local index cache directory."""

    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path.resolve()
        self.cache_dir = self._root_path / ".meminit" / "cache" / "index"
        self.manifest_path = self.cache_dir / "manifest.json"

    def clear(self) -> bool:
        """Remove the index cache directory or file if it exists."""
        if not self.cache_dir.exists():
            return False

        ensure_safe_write_path(root_dir=self._root_path, target_path=self.cache_dir)
        try:
            if self.cache_dir.is_dir():
                shutil.rmtree(self.cache_dir)
            else:
                self.cache_dir.unlink()
        except OSError as exc:
            raise MeminitError(
                ErrorCode.CACHE_WRITE_FAILED,
                f"Unable to clear the cache directory at '{self.cache_dir}'.",
                details={"cache_path": str(self.cache_dir)},
            ) from exc
        return True

    def explain(self) -> dict[str, Any]:
        """Return a stable manifest summary without mutating the cache."""
        summary: dict[str, Any] = {
            "cache_path": relative_path_string(self.manifest_path, self._root_path),
            "exists": self.manifest_path.is_file(),
        }
        if not self.manifest_path.is_file():
            return summary

        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            summary["warning"] = {
                "code": ErrorCode.CACHE_ENTRY_INVALID.value,
                "message": (
                    "Cache manifest is not readable JSON: "
                    f"{exc.__class__.__name__}"
                ),
            }
            return summary

        files = manifest.get("files", [])
        summary.update(
            {
                "manifest_schema_version": manifest.get("manifest_schema_version"),
                "file_count": len(files) if isinstance(files, list) else 0,
                "config_sha256": manifest.get("config_sha256"),
                "schema_sha256": manifest.get("schema_sha256"),
            }
        )
        return summary
