"""Repo-local index cache surface."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Iterable

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.path_utils import relative_path_string
from meminit.core.services.safe_fs import (
    atomic_write,
    ensure_safe_write_path,
)

MANIFEST_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class FileFingerprint:
    path: str
    size: int
    mtime_ns: int
    sha256: str
    document_id: str | None = None
    cache_node_size: int | None = None
    cache_node_mtime_ns: int | None = None

    def as_manifest_entry(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "path": self.path,
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "sha256": self.sha256,
        }
        if self.document_id:
            data["document_id"] = self.document_id
        if self.cache_node_size is not None:
            data["cache_node_size"] = self.cache_node_size
        if self.cache_node_mtime_ns is not None:
            data["cache_node_mtime_ns"] = self.cache_node_mtime_ns
        return data


@dataclass(frozen=True)
class CachePlan:
    mode: str
    added: set[str] = field(default_factory=set)
    changed: set[str] = field(default_factory=set)
    removed: set[str] = field(default_factory=set)
    unchanged: set[str] = field(default_factory=set)
    fingerprints: dict[str, FileFingerprint] = field(default_factory=dict)
    manifest_warning: dict[str, Any] | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "added": len(self.added),
            "changed": len(self.changed),
            "removed": len(self.removed),
            "unchanged": len(self.unchanged),
        }


class IndexCache:
    """Manage the repo-local index cache directory."""

    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path.resolve()
        self.cache_dir = self._root_path / ".meminit" / "cache" / "index"
        self.manifest_path = self.cache_dir / "manifest.json"
        self.nodes_dir = self.cache_dir / "nodes"
        self.lock_path = self.cache_dir / ".lock"

    def acquire_lock(self) -> "IndexCacheLock":
        return IndexCacheLock(self)

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
        ensure_safe_write_path(root_dir=self._root_path, target_path=self.manifest_path)
        manifest_exists = self.manifest_path.exists()
        summary: dict[str, Any] = {
            "cache_path": relative_path_string(self.manifest_path, self._root_path),
            "exists": manifest_exists,
        }
        if not manifest_exists:
            return summary

        if not self.manifest_path.is_file():
            raise MeminitError(
                ErrorCode.NOT_A_REGULAR_FILE,
                f"Path '{self.manifest_path}' is not a regular file",
                details={
                    "target_path": str(self.manifest_path),
                    "root_dir": str(self._root_path),
                    "required": "regular file (not directory/symlink)",
                },
            )

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

        if not isinstance(manifest, dict):
            summary["warning"] = {
                "code": ErrorCode.CACHE_ENTRY_INVALID.value,
                "message": (
                    "Cache manifest JSON must be an object, "
                    f"got {type(manifest).__name__}."
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

    def build_plan(
        self,
        *,
        doc_paths: Iterable[Path],
        context: dict[str, Any],
        use_cache: bool,
    ) -> CachePlan:
        paths = sorted(Path(path) for path in doc_paths)
        current_by_path: dict[str, FileFingerprint] = {}
        manifest, warning = self._read_manifest()
        previous_by_path = self._manifest_files(manifest)

        global_valid = (
            use_cache
            and manifest is not None
            and all(manifest.get(key) == value for key, value in context.items())
        )
        if not global_valid:
            previous_by_path = {}

        for path in paths:
            rel = _fast_relative_path(path, self._root_path)
            previous = previous_by_path.get(rel)
            current_by_path[rel] = self.fingerprint(path, previous, rel_path=rel)

        current_paths = set(current_by_path)
        previous_paths = set(previous_by_path)
        added = current_paths - previous_paths
        removed = previous_paths - current_paths
        unchanged: set[str] = set()
        changed: set[str] = set()
        for rel in current_paths & previous_paths:
            if current_by_path[rel].sha256 == previous_by_path[rel].sha256:
                unchanged.add(rel)
            else:
                changed.add(rel)

        return CachePlan(
            mode="incremental" if global_valid else "full",
            added=added,
            changed=changed,
            removed=removed,
            unchanged=unchanged,
            fingerprints=current_by_path,
            manifest_warning=warning,
        )

    def fingerprint(
        self,
        path: Path,
        previous: FileFingerprint | None = None,
        *,
        rel_path: str | None = None,
    ) -> FileFingerprint:
        stat = path.stat()
        rel = rel_path or _fast_relative_path(path, self._root_path)
        if (
            previous is not None
            and previous.size == stat.st_size
            and previous.mtime_ns == stat.st_mtime_ns
        ):
            sha256 = previous.sha256
        else:
            sha256 = _sha256_file(path)
        return FileFingerprint(
            path=rel,
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            sha256=sha256,
            document_id=previous.document_id if previous else None,
            cache_node_size=previous.cache_node_size if previous else None,
            cache_node_mtime_ns=previous.cache_node_mtime_ns if previous else None,
        )

    def read_node(self, document_id: str) -> dict[str, Any] | None:
        path = self.nodes_dir / f"{_cache_key(document_id)}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def write(
        self,
        *,
        context: dict[str, Any],
        fingerprints: dict[str, FileFingerprint],
        entries: Iterable[dict[str, Any]],
        rewrite_paths: set[str] | None = None,
    ) -> None:
        try:
            self.nodes_dir.mkdir(parents=True, exist_ok=True)
            ensure_safe_write_path(root_dir=self._root_path, target_path=self.nodes_dir)
            entry_by_id = {
                str(entry["document_id"]): entry
                for entry in entries
                if isinstance(entry.get("document_id"), str)
            }
            doc_id_by_path = {
                str(entry["path"]): doc_id
                for doc_id, entry in entry_by_id.items()
                if isinstance(entry.get("path"), str)
            }
            manifest_files = []
            for rel_path, fingerprint in sorted(fingerprints.items()):
                doc_id = doc_id_by_path.get(rel_path)
                should_write_fragment = (
                    rewrite_paths is None or rel_path in rewrite_paths
                )
                cache_node_size = fingerprint.cache_node_size
                cache_node_mtime_ns = fingerprint.cache_node_mtime_ns
                if should_write_fragment and doc_id and doc_id in entry_by_id:
                    node_path = self.nodes_dir / f"{_cache_key(doc_id)}.json"
                    _write_cache_json(
                        node_path,
                        entry_by_id[doc_id],
                    )
                    node_stat = node_path.stat()
                    cache_node_size = node_stat.st_size
                    cache_node_mtime_ns = node_stat.st_mtime_ns
                fp = FileFingerprint(
                    path=fingerprint.path,
                    size=fingerprint.size,
                    mtime_ns=fingerprint.mtime_ns,
                    sha256=fingerprint.sha256,
                    document_id=doc_id,
                    cache_node_size=cache_node_size,
                    cache_node_mtime_ns=cache_node_mtime_ns,
                )
                manifest_files.append(fp.as_manifest_entry())
            self._remove_stale_fragments(set(entry_by_id))

            manifest = {
                "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
                **context,
                "files": manifest_files,
            }
            _write_json(self.manifest_path, manifest, self._root_path)
        except OSError as exc:
            raise MeminitError(
                ErrorCode.CACHE_WRITE_FAILED,
                "Failed to write index cache.",
                details={"cache_path": str(self.cache_dir)},
            ) from exc

    def _remove_stale_fragments(self, live_doc_ids: set[str]) -> None:
        live_names = {f"{_cache_key(doc_id)}.json" for doc_id in live_doc_ids}
        for directory in (self.nodes_dir, self.cache_dir / "edges"):
            if not directory.exists():
                continue
            for path in directory.glob("*.json"):
                if path.name not in live_names:
                    path.unlink(missing_ok=True)

    def _read_manifest(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if not self.manifest_path.exists():
            return None, None
        if not self.manifest_path.is_file():
            return None, _cache_warning("Cache manifest is not a regular file.")
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return None, _cache_warning(
                f"Cache manifest is not readable JSON: {exc.__class__.__name__}"
            )
        if not isinstance(data, dict):
            return None, _cache_warning("Cache manifest JSON must be an object.")
        return data, None

    def _manifest_files(
        self, manifest: dict[str, Any] | None
    ) -> dict[str, FileFingerprint]:
        if manifest is None:
            return {}
        files = manifest.get("files")
        if not isinstance(files, list):
            return {}
        parsed: dict[str, FileFingerprint] = {}
        for item in files:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            sha256 = item.get("sha256")
            size = item.get("size")
            mtime_ns = item.get("mtime_ns")
            if (
                isinstance(path, str)
                and isinstance(sha256, str)
                and isinstance(size, int)
                and isinstance(mtime_ns, int)
            ):
                doc_id = item.get("document_id")
                parsed[path] = FileFingerprint(
                    path=path,
                    size=size,
                    mtime_ns=mtime_ns,
                    sha256=sha256,
                    document_id=doc_id if isinstance(doc_id, str) else None,
                    cache_node_size=item.get("cache_node_size")
                    if isinstance(item.get("cache_node_size"), int)
                    else None,
                    cache_node_mtime_ns=item.get("cache_node_mtime_ns")
                    if isinstance(item.get("cache_node_mtime_ns"), int)
                    else None,
                )
        return parsed


class IndexCacheLock:
    def __init__(self, cache: IndexCache) -> None:
        self._cache = cache
        self._fd: int | None = None

    def __enter__(self) -> "IndexCacheLock":
        self._cache.cache_dir.mkdir(parents=True, exist_ok=True)
        ensure_safe_write_path(
            root_dir=self._cache._root_path,
            target_path=self._cache.lock_path,
        )
        try:
            self._fd = os.open(
                self._cache.lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            os.write(self._fd, str(os.getpid()).encode("utf-8"))
        except FileExistsError as exc:
            raise MeminitError(
                ErrorCode.CACHE_LOCK_HELD,
                "Index cache lock is already held.",
                details={"lock_path": str(self._cache.lock_path)},
            ) from exc
        except OSError as exc:
            raise MeminitError(
                ErrorCode.CACHE_WRITE_FAILED,
                "Failed to create index cache lock.",
                details={"lock_path": str(self._cache.lock_path)},
            ) from exc
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self._cache.lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _cache_key(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in value)
    return safe or hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cache_warning(message: str) -> dict[str, Any]:
    return {
        "code": ErrorCode.CACHE_ENTRY_INVALID.value,
        "message": message,
        "severity": "warning",
        "path": ".meminit/cache/index/manifest.json",
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fast_relative_path(path: Path, root_path: Path) -> str:
    path_text = str(path)
    root_text = str(root_path).rstrip(os.sep) + os.sep
    if path_text.startswith(root_text):
        return path_text[len(root_text) :].replace(os.sep, "/")
    return relative_path_string(path, root_path)


def _write_json(path: Path, data: Any, root_path: Path) -> None:
    ensure_safe_write_path(root_dir=root_path, target_path=path)
    _write_cache_json(path, data)


def _write_cache_json(path: Path, data: Any) -> None:
    atomic_write(
        path,
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
