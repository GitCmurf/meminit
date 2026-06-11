"""Helpers for resolving the Meminit CLI version."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Final

PACKAGE_NAME: Final[str] = "meminit"


@lru_cache(maxsize=1)
def get_cli_version() -> str:
    """Return the installed package version, or fall back to pyproject.toml."""
    try:
        return package_version(PACKAGE_NAME)
    except PackageNotFoundError:
        return _read_pyproject_version()


def _read_pyproject_version() -> str:
    """Resolve the project version from the nearest Meminit pyproject.toml."""
    search_roots = [Path(__file__).resolve(), Path.cwd().resolve()]
    seen: set[Path] = set()

    for root in search_roots:
        for parent in (root, *root.parents):
            if parent in seen:
                continue
            seen.add(parent)

            version = _version_from_pyproject(parent / "pyproject.toml")
            if version is not None:
                return version

    raise RuntimeError(
        "Unable to determine Meminit version from package metadata or pyproject.toml."
    )


def _version_from_pyproject(pyproject_path: Path) -> str | None:
    if not pyproject_path.is_file():
        return None

    with pyproject_path.open("rb") as handle:
        pyproject = tomllib.load(handle)

    project = pyproject.get("project", {})
    if project.get("name") != PACKAGE_NAME:
        return None

    version = project.get("version")
    if isinstance(version, str) and version.strip():
        return version

    return None
