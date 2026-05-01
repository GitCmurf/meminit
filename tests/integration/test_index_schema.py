import json
from pathlib import Path
import pytest
from jsonschema import Draft7Validator, FormatChecker

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


def test_persisted_index_matches_schema(tmp_path):
    """CG-4: Proves the written meminit.index.json artifact conforms to its published schema."""
    _setup_doc(tmp_path, "EXAMPLE-ADR-001")

    use_case = IndexRepositoryUseCase(str(tmp_path))
    use_case.execute()

    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    assert index_path.exists()

    payload = json.loads(index_path.read_text(encoding="utf-8"))

    # Load the schema
    schema_path = Path("docs/20-specs/index-artifact.schema.json")
    assert schema_path.exists()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(payload))

    if errors:
        pytest.fail(f"Index artifact failed schema validation: {errors[0].message}")


def test_index_schema_fails_on_malformed_payload():
    """CG-4: Proves the schema correctly identifies invalid index artifacts."""
    schema_path = Path("docs/20-specs/index-artifact.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema, format_checker=FormatChecker())

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


def test_index_schema_fails_on_wrong_field_type():
    """CG-4: Proves the hardened schema identifies invalid field types in nodes."""
    schema_path = Path("docs/20-specs/index-artifact.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema, format_checker=FormatChecker())

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
