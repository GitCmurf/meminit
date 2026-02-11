import json
from pathlib import Path

import pytest

from meminit.core.domain.entities import Violation
from meminit.core.services.validators import SchemaValidator


@pytest.fixture
def mock_schema(tmp_path):
    schema = {
        "type": "object",
        "required": ["document_id", "title"],
        "properties": {"document_id": {"type": "string"}, "title": {"type": "string"}},
    }
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps(schema))
    return schema_file


def test_schema_validator_valid(mock_schema):
    validator = SchemaValidator(schema_path=str(mock_schema))
    data = {"document_id": "ABC", "title": "Test"}
    assert validator.validate_data(data) is None


def test_schema_validator_invalid_missing_field(mock_schema):
    validator = SchemaValidator(schema_path=str(mock_schema))
    data = {"document_id": "ABC"}  # Missing title
    violation = validator.validate_data(data)
    assert isinstance(violation, Violation)
    assert violation.rule == "SCHEMA_VALIDATION"
    assert "title" in violation.message


def test_schema_validator_invalid_type(mock_schema):
    validator = SchemaValidator(schema_path=str(mock_schema))
    data = {"document_id": "ABC", "title": 123}  # Bad type
    violation = validator.validate_data(data)
    assert isinstance(violation, Violation)
    assert violation.rule == "SCHEMA_VALIDATION"
    assert "title" in violation.message
