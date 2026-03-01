from datetime import datetime, timezone
from typing import Dict, Any
from meminit.core.services.repo_config import RepoConfig


DEFAULT_DOCOPS_VERSION = "2.0"
DEFAULT_STATUS = "Draft"
DEFAULT_VERSION = "0.1"
DEFAULT_OWNER = "__TBD__"


def extract_title_from_markdown(body: str, fallback_stem: str) -> str:
    """Extract the first heading from markdown content as the title."""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if title:
                return title
    return fallback_stem.replace("-", " ").strip().title() or "Untitled"


def build_default_frontmatter_patch(ns: RepoConfig, doc_type: str, inferred_title: str) -> Dict[str, Any]:
    """Build a default frontmatter patch with all required fields."""
    patch = {
        "document_id": DEFAULT_OWNER,
        "type": doc_type,
        "title": inferred_title,
        "status": DEFAULT_STATUS,
        "version": DEFAULT_VERSION,
        "owner": DEFAULT_OWNER,
        "docops_version": ns.docops_version or DEFAULT_DOCOPS_VERSION,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    return patch
