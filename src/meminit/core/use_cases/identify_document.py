from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from meminit.core.services.repo_config import load_repo_layout


@dataclass(frozen=True)
class IdentifyResult:
    path: str
    document_id: Optional[str]


class IdentifyDocumentUseCase:
    def __init__(self, root_dir: str):
        self._layout = load_repo_layout(root_dir)
        self._root_dir = self._layout.root_dir

    def execute(self, path: str) -> IdentifyResult:
        index_path = self._layout.index_file
        if not index_path.exists():
            raise FileNotFoundError(f"Index not found: {index_path}")

        target = Path(path)
        if not target.is_absolute():
            target = (self._root_dir / target).resolve()
        try:
            rel_path = target.relative_to(self._root_dir).as_posix()
        except ValueError as exc:
            raise ValueError(f"Path {target} is outside root directory {self._root_dir}") from exc

        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Invalid JSON in index file: {index_path}") from exc
        documents = data.get("documents", [])
        for entry in documents:
            if not isinstance(entry, dict):
                continue
            if entry.get("path") == rel_path:
                return IdentifyResult(path=rel_path, document_id=entry.get("document_id"))

        return IdentifyResult(path=rel_path, document_id=None)
