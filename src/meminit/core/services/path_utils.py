import re
import hashlib
from pathlib import Path


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
