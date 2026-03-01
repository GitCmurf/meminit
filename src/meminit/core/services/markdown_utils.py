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
    """
    Build a default frontmatter patch with all required fields.

    Note: The document_id is set to a placeholder (__TBD__) because a proper
    unique document ID must be generated with knowledge of existing documents
    in the repository. The caller should replace this with a generated ID.
    """
    patch = {
        "document_id": DEFAULT_OWNER,  # Placeholder - caller should generate unique ID
        "type": doc_type,
        "title": inferred_title,
        "status": DEFAULT_STATUS,
        "version": DEFAULT_VERSION,
        "owner": DEFAULT_OWNER,
        "docops_version": ns.docops_version or DEFAULT_DOCOPS_VERSION,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    return patch
