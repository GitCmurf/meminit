import json
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List


FILENAME_EXCEPTIONS = frozenset({
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "LICENSE.md",
    "LICENCE",
    "LICENCE.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "NOTICE",
    "NOTICE.md",
})


def normalize_filename_to_kebab_case(original_path: Path) -> Path:
    """Compute the target path after applying filename conventions."""
    if original_path.name in FILENAME_EXCEPTIONS:
        return original_path
    stem = original_path.stem.lower()
    suffix = original_path.suffix.lower()

    stem = stem.replace(" ", "-").replace("_", "-")
    stem = re.sub(r"[^a-z0-9-]", "-", stem)
    stem = re.sub(r"-{2,}", "-", stem).strip("-")
    if not stem:
        stem = "doc"

    return original_path.parent / f"{stem}{suffix}"


def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of a file efficiently using chunked reading."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def relative_path_string(path: Path, base: Path) -> str:
    """Return path relative to base as a string, or absolute path if not relative.

    This is a common pattern throughout the codebase for error messages and
    output formatting. It avoids exposing full absolute paths when a relative
    path is more meaningful to the user.

    Args:
        path: The path to convert.
        base: The base directory for relative path computation.

    Returns:
        A string path - either relative to base (with forward slashes) or absolute.
    """
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


_SENSITIVE_HOME_DIRS = frozenset({".ssh", ".gnupg", ".aws", ".kube"})


def is_safe_cli_output_path(path: Path) -> bool:
    """Return whether a CLI output path avoids protected system locations."""
    forbidden = [
        "/etc", "/bin", "/sbin", "/usr/bin", "/usr/sbin", "/root", "/var",
        "/proc", "/sys", "/dev", "/boot",
    ]
    try:
        abs_path = path.resolve()
        path_str = abs_path.as_posix()
        for prefix in forbidden:
            if path_str == prefix or path_str.startswith(prefix + "/"):
                return False
        try:
            home = Path.home().resolve()
            try:
                rel = abs_path.relative_to(home)
            except ValueError:
                return True
            if abs_path.name.startswith(".") and abs_path.name != ".meminit":
                return False
            for part in rel.parts[:-1]:
                if part in _SENSITIVE_HOME_DIRS:
                    return False
        except (RuntimeError, OSError):
            pass
    except (OSError, ValueError):
        if path.is_absolute():
            path_str = path.as_posix()
            for prefix in forbidden:
                if path_str == prefix or path_str.startswith(prefix + "/"):
                    return False
    return True


def load_index_documents(index_path: Path) -> List[Dict[str, Any]]:
    """Load documents from a meminit index JSON file.

    Supports the v1.0 graph schema (``nodes`` under ``data``), the v0.2
    envelope (``documents`` under ``data``), and the v1 top-level format
    for backward compatibility.

    A malformed or truncated envelope (e.g. ``data`` is a dict but
    contains neither ``nodes`` nor ``documents``) raises ``ValueError``
    so callers do not misinterpret an empty return as a valid zero-document
    index.

    Args:
        index_path: Path to the ``meminit.index.json`` file.

    Returns:
        List of document dicts from the index.

    Raises:
        FileNotFoundError: If the index file does not exist.
        ValueError: If the index file is not valid JSON or the envelope is malformed.
    """
    import json

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Index not found: {index_path}") from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Invalid JSON in index file: {index_path}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid index structure in {index_path}: "
            f"expected a JSON object at the top level, got {type(data).__name__}"
        )

    # v1.0 graph schema: nodes under data; v0.2: documents under data; v1: documents at top level
    data_field = data.get("data")
    if isinstance(data_field, dict):
        if "nodes" in data_field:
            docs = data_field.get("nodes")
            return docs if isinstance(docs, list) else []
        if "documents" in data_field:
            docs = data_field.get("documents")
            return docs if isinstance(docs, list) else []
        raise ValueError(
            f"Malformed index envelope in {index_path}: "
            f"'data' dict contains neither 'nodes' nor 'documents'"
        )
    if "documents" in data:
        docs = data.get("documents")
        return docs if isinstance(docs, list) else []
    return []
