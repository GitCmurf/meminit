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


def load_index_documents(index_path: Path) -> List[Dict[str, Any]]:
    """Load documents from a meminit index JSON file.

    Supports both v2 envelope (documents nested under ``data``) and
    v1 format (documents at top level) for backward compatibility.

    Args:
        index_path: Path to the ``meminit.index.json`` file.

    Returns:
        List of document dicts from the index.

    Raises:
        FileNotFoundError: If the index file does not exist.
        ValueError: If the index file is not valid JSON.
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
    if "documents" in data:
        docs = data.get("documents")
        return docs if isinstance(docs, list) else []
    return []
