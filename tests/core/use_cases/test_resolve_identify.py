import json
from pathlib import Path

import pytest

from meminit.core.use_cases.identify_document import IdentifyDocumentUseCase
from meminit.core.use_cases.resolve_document import ResolveDocumentUseCase


def _write_index(tmp_path: Path):
    index_path = tmp_path / "docs" / "01-indices"
    index_path.mkdir(parents=True)
    (index_path / "meminit.index.json").write_text(
        json.dumps(
            {
                "index_version": "0.1",
                "generated_at": "2025-12-21T00:00:00Z",
                "documents": [
                    {"document_id": "EXAMPLE-ADR-001", "path": "docs/45-adr/adr-001-test.md"}
                ],
            }
        ),
        encoding="utf-8",
    )


def test_resolve_document_found(tmp_path):
    _write_index(tmp_path)
    use_case = ResolveDocumentUseCase(str(tmp_path))
    result = use_case.execute("EXAMPLE-ADR-001")
    assert result.path == "docs/45-adr/adr-001-test.md"


def test_resolve_document_missing(tmp_path):
    _write_index(tmp_path)
    use_case = ResolveDocumentUseCase(str(tmp_path))
    result = use_case.execute("EXAMPLE-ADR-999")
    assert result.path is None


def test_identify_document_found(tmp_path):
    _write_index(tmp_path)
    use_case = IdentifyDocumentUseCase(str(tmp_path))
    result = use_case.execute("docs/45-adr/adr-001-test.md")
    assert result.document_id == "EXAMPLE-ADR-001"


def test_identify_document_not_governed(tmp_path):
    _write_index(tmp_path)
    use_case = IdentifyDocumentUseCase(str(tmp_path))
    result = use_case.execute("docs/45-adr/adr-404.md")
    assert result.document_id is None


def test_resolve_document_invalid_index(tmp_path):
    index_path = tmp_path / "docs" / "01-indices"
    index_path.mkdir(parents=True)
    (index_path / "meminit.index.json").write_text("{bad json", encoding="utf-8")

    use_case = ResolveDocumentUseCase(str(tmp_path))
    with pytest.raises(ValueError):
        use_case.execute("EXAMPLE-ADR-001")


def test_identify_document_invalid_index(tmp_path):
    index_path = tmp_path / "docs" / "01-indices"
    index_path.mkdir(parents=True)
    (index_path / "meminit.index.json").write_text("{bad json", encoding="utf-8")

    use_case = IdentifyDocumentUseCase(str(tmp_path))
    with pytest.raises(ValueError):
        use_case.execute("docs/45-adr/adr-001-test.md")
