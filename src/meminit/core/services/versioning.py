"""Helpers for resolving the Meminit CLI version."""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Final

import tomllib


PACKAGE_NAME: Final[str] = "meminit"


@lru_cache(maxsize=1)
def get_cli_version() -> str:
    """Return the installed package version, or fall back to pyproject.toml."""
    try:
        return package_version(PACKAGE_NAME)
    except PackageNotFoundError:
        return _read_pyproject_version()


def _read_pyproject_version() -> str:
    """Resolve the project version from the nearest pyproject.toml."""
    for parent in Path(__file__).resolve().parents:
        pyproject_path = parent / "pyproject.toml"
        if not pyproject_path.is_file():
            continue

        with pyproject_path.open("rb") as handle:
            pyproject = tomllib.load(handle)

        project = pyproject.get("project", {})
        version = project.get("version")
        if isinstance(version, str) and version.strip():
            return version

    raise RuntimeError(
        "Unable to determine Meminit version from package metadata or pyproject.toml."
    )
