import json
from pathlib import Path
import pytest
from jsonschema import Draft7Validator, FormatChecker

from meminit.core.use_cases.index_repository import IndexRepositoryUseCase

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUNDLED_SCHEMA = _REPO_ROOT / "src" / "meminit" / "core" / "assets" / "index-artifact.schema.json"
_DOCS_SCHEMA = _REPO_ROOT / "docs" / "20-specs" / "index-artifact.schema.json"


@pytest.fixture(scope="module")
def index_artifact_schema():
    """Load the index-artifact schema, asserting bundled/docs parity."""
    bundled_text = _BUNDLED_SCHEMA.read_text(encoding="utf-8")
    docs_text = _DOCS_SCHEMA.read_text(encoding="utf-8")
    assert bundled_text == docs_text, "Bundled and docs index-artifact schema copies have drifted"
    return json.loads(bundled_text)


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


def _setup_incomplete_doc(root: Path, doc_id: str) -> Path:
    """Create a brownfield document with missing type/title frontmatter."""
    docs_dir = root / "docs" / "45-adr"
    docs_dir.mkdir(parents=True, exist_ok=True)
    doc_path = docs_dir / f"adr-{doc_id.split('-')[-1]}.md"
    content = f"""---
document_id: {doc_id}
status: Draft
docops_version: 2.0
---
# Incomplete document
"""
    doc_path.write_text(content, encoding="utf-8")
    return doc_path


def test_persisted_index_matches_schema(tmp_path, index_artifact_schema):
    """CG-4: Proves the written meminit.index.json artifact conforms to its published schema."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    use_case.execute()

    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    assert index_path.exists()

    payload = json.loads(index_path.read_text(encoding="utf-8"))

    validator = Draft7Validator(index_artifact_schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(payload))

    if errors:
        pytest.fail(f"Index artifact failed schema validation: {errors[0].message}")


def test_persisted_index_allows_brownfield_nodes_with_missing_type_and_title(
    tmp_path, index_artifact_schema
):
    """CG-4: Brownfield docs with partial metadata still validate against the published schema."""
    _setup_incomplete_doc(tmp_path, "EXAMPLE-ADR-002")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    use_case.execute()

    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    node = payload["data"]["nodes"][0]

    assert node["type"] is None
    assert node["title"] is None

    validator = Draft7Validator(index_artifact_schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(payload))

    if errors:
        pytest.fail(f"Brownfield index artifact failed schema validation: {errors[0].message}")


def test_index_schema_fails_on_malformed_payload(index_artifact_schema):
    """CG-4: Proves the schema correctly identifies invalid index artifacts."""
    validator = Draft7Validator(index_artifact_schema, format_checker=FormatChecker())

    # Missing required field 'command'
    bad_payload = {
        "output_schema_version": "2.0",
        "success": True,
        "data": {},
        "warnings": [],
        "violations": [],
        "advice": []
    }
    assert validator.is_valid(bad_payload) is False

    # Wrong command
    bad_payload["command"] = "wrong"
    assert validator.is_valid(bad_payload) is False

    # Correct command but data missing required fields
    bad_payload["command"] = "index"
    assert validator.is_valid(bad_payload) is False


def test_index_schema_fails_on_wrong_field_type(index_artifact_schema):
    """CG-4: Proves the hardened schema identifies invalid field types in nodes."""
    validator = Draft7Validator(index_artifact_schema, format_checker=FormatChecker())

    payload = {
        "output_schema_version": "2.0",
        "success": True,
        "command": "index",
        "data": {
            "index_version": "1.0",
            "graph_schema_version": "1.0",
            "node_count": 1,
            "edge_count": 0,
            "document_count": 1,
            "namespaces": [],
            "nodes": [
                {
                    "document_id": 123,  # Invalid: should be string
                    "path": "docs/test.md",
                    "type": "ADR",
                    "title": "Test"
                }
            ],
            "edges": []
        },
        "warnings": [],
        "violations": [],
        "advice": []
    }
    assert validator.is_valid(payload) is False
    errors = list(validator.iter_errors(payload))
    assert any("is not of type 'string'" in e.message for e in errors)
