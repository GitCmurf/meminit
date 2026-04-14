from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from meminit.core.services.path_utils import load_index_documents


@dataclass(frozen=True)
class ResolveResult:
    document_id: str
    path: Optional[str]


class ResolveDocumentUseCase:
    def __init__(self, root_dir: str):
        from meminit.core.services.repo_config import load_repo_layout

        layout = load_repo_layout(root_dir)
        self._index_file = layout.index_file

    def execute(self, document_id: str) -> ResolveResult:
        doc_id = document_id.strip()
        documents = load_index_documents(self._index_file)
        for entry in documents:
            if not isinstance(entry, dict):
                continue
            if entry.get("document_id") == doc_id:
                path_value = entry.get("path")
                path = path_value if isinstance(path_value, str) else None
                return ResolveResult(document_id=doc_id, path=path)
        return ResolveResult(document_id=doc_id, path=None)
