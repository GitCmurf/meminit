import json

from meminit.core.services.repo_config import load_repo_layout
from meminit.core.use_cases.check_repository import CheckRepositoryUseCase
from meminit.core.use_cases.identify_document import IdentifyDocumentUseCase
from meminit.core.use_cases.index_repository import IndexRepositoryUseCase
from meminit.core.use_cases.resolve_document import ResolveDocumentUseCase


SCHEMA_JSON = (
    '{"type": "object", "required": ["document_id", "type", "title", "status", "version", "last_updated", "owner", "docops_version"],'
    ' "properties": {"document_id": {"type": "string"}, "type": {"type": "string"}, "title": {"type": "string"},'
    ' "status": {"type": "string"}, "version": {"type": "string"}, "last_updated": {"type": "string", "format": "date"},'
    ' "owner": {"type": "string"}, "docops_version": {"type": "string"}}}'
)


def test_load_repo_layout_supports_namespaces_and_index_path(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        """
project_name: Example
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
index_path: .meminit/meminit.index.json
namespaces:
  - name: root
    repo_prefix: AIDHA
    docs_root: docs
  - name: phyla
    repo_prefix: PHYLA
    docs_root: packages/phyla/docs
""".lstrip(),
        encoding="utf-8",
    )

    layout = load_repo_layout(tmp_path)
    assert layout.index_path == ".meminit/meminit.index.json"
    assert len(layout.namespaces) == 2
    assert layout.get_namespace("root").repo_prefix == "AIDHA"
    assert layout.get_namespace("phyla").docs_root == "packages/phyla/docs"


def test_monorepo_check_and_index_and_resolve(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        """
project_name: Example
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
index_path: .meminit/meminit.index.json
namespaces:
  - name: root
    repo_prefix: AIDHA
    docs_root: docs
  - name: phyla
    repo_prefix: PHYLA
    docs_root: packages/phyla/docs
""".lstrip(),
        encoding="utf-8",
    )

    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(SCHEMA_JSON, encoding="utf-8")

    root_doc = tmp_path / "docs" / "45-adr" / "adr-001-root.md"
    root_doc.parent.mkdir(parents=True)
    root_doc.write_text(
        "---\n"
        "document_id: AIDHA-ADR-001\n"
        "type: ADR\n"
        "title: Root\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-28\n"
        "owner: GitCmurf\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# ADR: Root\n",
        encoding="utf-8",
    )

    pkg_doc = tmp_path / "packages" / "phyla" / "docs" / "45-adr" / "adr-001-phyla.md"
    pkg_doc.parent.mkdir(parents=True)
    pkg_doc.write_text(
        "---\n"
        "document_id: PHYLA-ADR-001\n"
        "type: ADR\n"
        "title: Phyla\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-28\n"
        "owner: GitCmurf\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# ADR: Phyla\n",
        encoding="utf-8",
    )

    violations = CheckRepositoryUseCase(str(tmp_path)).execute()
    assert violations == []

    report = IndexRepositoryUseCase(str(tmp_path)).execute()
    assert report.document_count == 2

    index_path = tmp_path / ".meminit" / "meminit.index.json"
    assert report.index_path == index_path
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["output_schema_version"] == "2.0"
    assert {d["namespace"] for d in payload["documents"]} == {"root", "phyla"}

    resolved = ResolveDocumentUseCase(str(tmp_path)).execute("PHYLA-ADR-001")
    assert resolved.path == "packages/phyla/docs/45-adr/adr-001-phyla.md"

    identified = IdentifyDocumentUseCase(str(tmp_path)).execute("docs/45-adr/adr-001-root.md")
    assert identified.document_id == "AIDHA-ADR-001"


def test_check_enforces_namespace_repo_prefix(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        """
project_name: Example
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
namespaces:
  - name: root
    repo_prefix: AIDHA
    docs_root: docs
  - name: phyla
    repo_prefix: PHYLA
    docs_root: packages/phyla/docs
""".lstrip(),
        encoding="utf-8",
    )

    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(SCHEMA_JSON, encoding="utf-8")

    pkg_doc = tmp_path / "packages" / "phyla" / "docs" / "45-adr" / "adr-001-phyla.md"
    pkg_doc.parent.mkdir(parents=True)
    pkg_doc.write_text(
        "---\n"
        "document_id: AIDHA-ADR-001\n"
        "type: ADR\n"
        "title: Wrong Prefix\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-28\n"
        "owner: GitCmurf\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# ADR: Wrong Prefix\n",
        encoding="utf-8",
    )

    violations = CheckRepositoryUseCase(str(tmp_path)).execute()
    assert any(v.rule == "ID_PREFIX" for v in violations)


def test_nested_namespaces_do_not_double_scan(tmp_path):
    """
    If a namespace docs_root is nested within another namespace docs_root, files must only be
    "owned" by the most-specific namespace to avoid duplicate validation and false ID_UNIQUE errors.
    """
    (tmp_path / "docops.config.yaml").write_text(
        """
project_name: Example
docops_version: '2.0'
schema_path: docs/00-governance/metadata.schema.json
namespaces:
  - name: root
    repo_prefix: MEMINIT
    docs_root: docs
  - name: org
    repo_prefix: ORG
    docs_root: docs/00-governance/org
""".lstrip(),
        encoding="utf-8",
    )

    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "metadata.schema.json").write_text(SCHEMA_JSON, encoding="utf-8")

    org_doc = tmp_path / "docs" / "00-governance" / "org" / "org-gov-001.md"
    org_doc.parent.mkdir(parents=True)
    org_doc.write_text(
        "---\n"
        "document_id: ORG-GOV-001\n"
        "type: GOV\n"
        "title: Org\n"
        "status: Draft\n"
        "version: 0.1\n"
        "last_updated: 2025-12-28\n"
        "owner: GitCmurf\n"
        "docops_version: 2.0\n"
        "---\n\n"
        "# GOV: Org\n",
        encoding="utf-8",
    )

    violations = CheckRepositoryUseCase(str(tmp_path)).execute()
    assert not any(v.rule == "ID_UNIQUE" for v in violations)
