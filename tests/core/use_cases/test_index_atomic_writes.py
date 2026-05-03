import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from meminit.core.use_cases.index_repository import IndexRepositoryUseCase


def _setup_doc(
    root: Path,
    doc_id: str,
    doc_type: str = "ADR",
    title: str = "Test Document",
) -> Path:
    docs_dir = root / "docs" / "45-adr"
    docs_dir.mkdir(parents=True, exist_ok=True)
    doc_path = docs_dir / f"adr-{doc_id.split('-')[-1]}.md"
    content = f"""---
document_id: {doc_id}
type: {doc_type}
title: {title}
status: Draft
docops_version: 2.0
---
# {title}
"""
    doc_path.write_text(content, encoding="utf-8")
    return doc_path


def test_index_writes_are_atomic(tmp_path):
    """BG-1: Proves index-side writes call atomic_write for all four artifacts."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")

    # We want to verify that atomic_write is called for:
    # 1. meminit.index.json
    # 2. catalogue.md
    # 3. kanban.md
    # 4. kanban.css

    with patch("meminit.core.use_cases.index_repository.atomic_write") as mock_atomic:
        use_case = IndexRepositoryUseCase(
            str(tmp_path),
            output_catalog=True,
            output_kanban=True
        )
        use_case.execute()

        # Check that atomic_write was called
        assert mock_atomic.call_count == 4

        # Verify the paths passed to atomic_write
        called_paths = [call.args[0] for call in mock_atomic.call_args_list]
        names = [p.name for p in called_paths]

        assert "meminit.index.json" in names
        assert "catalogue.md" in names
        assert "kanban.md" in names
        assert "kanban.css" in names


def test_index_atomic_write_failure_preserves_old_content(tmp_path):
    """BG-1: Proves a failed atomic write leaves the previous target bytes intact."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")

    # Run once to create the index
    use_case = IndexRepositoryUseCase(str(tmp_path))
    use_case.execute()

    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    assert index_path.exists()
    original_bytes = index_path.read_bytes()

    # Now simulate a failure during atomic_write
    with patch("meminit.core.use_cases.index_repository.atomic_write", side_effect=RuntimeError("Atomic write failed")):
        with pytest.raises(RuntimeError, match="Atomic write failed"):
            use_case.execute()

    # The file should still have the original content
    assert index_path.read_bytes() == original_bytes
