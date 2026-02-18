import json
from pathlib import Path

import frontmatter

from meminit.core.use_cases.index_repository import IndexRepositoryUseCase


def test_index_repository_builds_index(tmp_path):
    docs_dir = tmp_path / "docs" / "45-adr"
    docs_dir.mkdir(parents=True)
    doc_path = docs_dir / "adr-001-test.md"
    doc_path.write_text(
        "---\n"
        "document_id: EXAMPLE-ADR-001\n"
        "type: ADR\n"
        "title: Test\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-21\n"
        "owner: Test\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# ADR: Test\n",
        encoding="utf-8",
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    assert report.document_count == 1
    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    assert report.index_path == index_path
    text = index_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    payload = json.loads(text)
    assert payload["output_schema_version"] == "2.0"
    assert payload["documents"][0]["document_id"] == "EXAMPLE-ADR-001"


def test_index_repository_excludes_wip(tmp_path):
    docs_dir = tmp_path / "docs" / "45-adr"
    docs_dir.mkdir(parents=True)
    doc_path = docs_dir / "WIP-adr-002.md"
    doc_path.write_text(
        "---\n"
        "document_id: EXAMPLE-ADR-002\n"
        "type: ADR\n"
        "title: WIP\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-21\n"
        "owner: Test\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# ADR: WIP\n",
        encoding="utf-8",
    )

    use_case = IndexRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    assert report.document_count == 0
