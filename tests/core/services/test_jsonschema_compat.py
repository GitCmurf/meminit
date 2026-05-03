from pathlib import Path

import jsonschema
import pytest


def test_jsonschema_resolves_to_installed_dependency_not_repo_copy():
    repo_jsonschema_dir = Path(__file__).resolve().parents[3] / "src" / "jsonschema"
    imported_path = Path(jsonschema.__file__).resolve()

    assert not imported_path.is_relative_to(repo_jsonschema_dir)
    assert imported_path.exists()


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
            format_checker=jsonschema.FormatChecker(),
        )


def test_jsonschema_unknown_type_rejects_instances():
    """An unknown schema type must not match any instance (defensive)."""
    schema = {"type": "strnig"}
    with pytest.raises(jsonschema.exceptions.SchemaError, match="strnig"):
        jsonschema.Draft7Validator.check_schema(schema)
