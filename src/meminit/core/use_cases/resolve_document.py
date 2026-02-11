from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from meminit.core.services.repo_config import load_repo_layout


@dataclass(frozen=True)
class ResolveResult:
    document_id: str
    path: Optional[str]


class ResolveDocumentUseCase:
    def __init__(self, root_dir: str):
        self._layout = load_repo_layout(root_dir)
        self._root_dir = self._layout.root_dir

    def execute(self, document_id: str) -> ResolveResult:
        doc_id = document_id.strip()
        index_path = self._layout.index_file
        if not index_path.exists():
            raise FileNotFoundError(f"Index not found: {index_path}")

        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Failed to load index from {index_path}: {exc}") from exc
        documents = data.get("documents", [])
        for entry in documents:
            if not isinstance(entry, dict):
                continue
            if entry.get("document_id") == doc_id:
                path_value = entry.get("path")
                path = path_value if isinstance(path_value, str) else None
                return ResolveResult(document_id=doc_id, path=path)
        return ResolveResult(document_id=doc_id, path=None)
