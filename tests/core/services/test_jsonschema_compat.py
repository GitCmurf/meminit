import jsonschema
import pytest


def test_jsonschema_compat_validate_supports_refs_formats_and_constraints():
    schema = {
        "type": "object",
        "required": ["document_id", "created_at"],
        "properties": {
            "document_id": {"$ref": "#/definitions/document_id"},
            "created_at": {"type": "string", "format": "date"},
        },
        "definitions": {
            "document_id": {
                "type": "string",
                "pattern": "^MEM-ADR-\\d{3}$",
            }
        },
        "additionalProperties": False,
    }

    validator = jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker())
    assert validator.is_valid({"document_id": "MEM-ADR-001", "created_at": "2025-01-01"})

    with pytest.raises(jsonschema.ValidationError, match="document_id"):
        jsonschema.validate(
            {"document_id": "bad", "created_at": "2025-01-01"},
            schema,
        )
