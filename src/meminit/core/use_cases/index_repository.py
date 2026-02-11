from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import frontmatter

from meminit.core.services.output_contracts import OUTPUT_SCHEMA_VERSION
from meminit.core.services.repo_config import load_repo_layout
from meminit.core.services.safe_fs import ensure_safe_write_path


@dataclass(frozen=True)
class IndexBuildReport:
    index_path: Path
    document_count: int


class IndexRepositoryUseCase:
    def __init__(self, root_dir: str):
        self._layout = load_repo_layout(root_dir)
        self._root_dir = self._layout.root_dir

    def execute(self) -> IndexBuildReport:
        any_docs = any(ns.docs_dir.exists() for ns in self._layout.namespaces)
        if not any_docs:
            raise FileNotFoundError("No configured docs roots exist on disk; cannot build index.")

        index_path = self._layout.index_file
        ensure_safe_write_path(root_dir=self._root_dir, target_path=index_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)

        entries: List[Dict[str, Any]] = []
        for ns in self._layout.namespaces:
            if not ns.docs_dir.exists():
                continue
            for path in ns.docs_dir.rglob("*.md"):
                owner = self._layout.namespace_for_path(path)
                if owner is None or owner.namespace.lower() != ns.namespace.lower():
                    continue
                if ns.is_excluded(path):
                    continue
                try:
                    post = frontmatter.load(path)
                except Exception:
                    continue

                doc_id = post.metadata.get("document_id")
                if not isinstance(doc_id, str) or not doc_id.strip():
                    continue
                doc_id = doc_id.strip()

                rel_path = path.relative_to(self._root_dir).as_posix()
                entries.append(
                    {
                        "document_id": doc_id,
                        "path": rel_path,
                        "namespace": ns.namespace,
                        "repo_prefix": ns.repo_prefix,
                        "type": post.metadata.get("type"),
                        "title": post.metadata.get("title"),
                        "status": post.metadata.get("status"),
                    }
                )

        payload = {
            "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "index_version": "0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "namespaces": [
                {
                    "namespace": ns.namespace,
                    "docs_root": ns.docs_root,
                    "repo_prefix": ns.repo_prefix,
                }
                for ns in self._layout.namespaces
            ],
            "documents": sorted(entries, key=lambda e: e["document_id"]),
        }
        # End with a newline for git/formatter ergonomics.
        index_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return IndexBuildReport(index_path=index_path, document_count=len(entries))
