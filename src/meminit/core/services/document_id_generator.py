"""Service for generating document IDs with sequential numbering."""

import re
from pathlib import Path
from typing import Optional

import frontmatter
import yaml

from meminit.core.domain.document_ids import document_id_type_segment
from meminit.core.services.repo_config import RepoConfig
from meminit.core.services.observability import log_debug


class DocumentIdGenerator:
    """Service for generating sequential document IDs within a namespace."""

    @staticmethod
    def generate_id(doc_type: str, target_dir: Path, ns: RepoConfig) -> str:
        """Generate a new sequential document ID for the given type.

        Args:
            doc_type: Document type (e.g., "ADR", "PRD")
            target_dir: Directory to scan for existing documents
            ns: Namespace configuration containing repo_prefix

        Returns:
            New document ID in REPO-TYPE-### format (e.g., "EXAMPLE-ADR-001")
        """
        repo_prefix = ns.repo_prefix
        id_type = document_id_type_segment(doc_type)

        max_id = 0
        scanned_files = 0
        regex = re.compile(rf"^{re.escape(id_type.lower())}-(\d{{3}})-", re.IGNORECASE)
        frontmatter_regex = re.compile(
            rf"^[A-Z]{{3,10}}-{re.escape(id_type)}-(\d{{3}})$", re.IGNORECASE
        )

        for p in target_dir.glob("*.md"):
            scanned_files += 1
            match = regex.match(p.name)
            if match:
                num = int(match.group(1))
                if num > max_id:
                    max_id = num
            else:
                try:
                    post = frontmatter.load(p)
                except (OSError, UnicodeDecodeError, yaml.YAMLError):
                    continue

                doc_id = post.metadata.get("document_id")
                if not isinstance(doc_id, str):
                    continue

                doc_id = doc_id.strip()
                match = frontmatter_regex.match(doc_id)
                if match:
                    num = int(match.group(1))
                    if num > max_id:
                        max_id = num

        next_id = max_id + 1
        log_debug(
            operation="debug.id_generation",
            details={
                "doc_type": doc_type,
                "target_dir": str(target_dir),
                "scanned_files": scanned_files,
                "max_id": max_id,
                "next_id": next_id,
            },
        )
        return f"{repo_prefix}-{id_type}-{next_id:03d}"