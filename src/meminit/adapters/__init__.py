"""Adapters for Protocol ports.

This package provides concrete implementations of the Protocol interfaces
defined in core/ports, enabling better testability and future flexibility.
"""

from meminit.adapters.filesystem import LocalFileSystem
from meminit.adapters.config import YamlConfigAdapter
from meminit.adapters.frontmatter_adapter import PythonFrontmatterAdapter
from meminit.adapters.safe_storage import LocalSafeStorage

__all__ = [
    "LocalFileSystem",
    "YamlConfigAdapter",
    "PythonFrontmatterAdapter",
    "LocalSafeStorage",
]