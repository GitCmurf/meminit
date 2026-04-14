from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from meminit.core.services.path_utils import load_index_documents


@dataclass(frozen=True)
class IdentifyResult:
    path: str
    document_id: Optional[str]


class IdentifyDocumentUseCase:
    def __init__(self, root_dir: str):
        from meminit.core.services.repo_config import load_repo_layout

        layout = load_repo_layout(root_dir)
        self._index_file = layout.index_file
        self._root_dir = layout.root_dir

    def execute(self, path: str) -> IdentifyResult:
        target = Path(path)
        if not target.is_absolute():
            target = (self._root_dir / target).resolve()
        try:
            rel_path = target.relative_to(self._root_dir).as_posix()
        except ValueError as exc:
            raise ValueError(f"Path {target} is outside root directory {self._root_dir}") from exc

        documents = load_index_documents(self._index_file)
        for entry in documents:
            if not isinstance(entry, dict):
                continue
            if entry.get("path") == rel_path:
                return IdentifyResult(path=rel_path, document_id=entry.get("document_id"))

        return IdentifyResult(path=rel_path, document_id=None)
