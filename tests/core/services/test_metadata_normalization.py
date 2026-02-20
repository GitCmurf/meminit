from datetime import date

from meminit.core.services.metadata_normalization import normalize_yaml_scalar_footguns


def test_coerces_known_string_version_fields_only():
    metadata = {
        "version": 2,
        "docops_version": 2.0,
        "template_version": 1.1,
    }

    normalized = normalize_yaml_scalar_footguns(metadata)

    assert normalized["version"] == "2.0"
    assert normalized["docops_version"] == "2.0"
    assert normalized["template_version"] == "1.1"


def test_preserves_custom_numeric_version_fields():
    metadata = {
        "api_version": 2,
        "schema_version": 3.1,
        "custom_version": 4,
    }

    normalized = normalize_yaml_scalar_footguns(metadata)

    assert normalized["api_version"] == 2
    assert normalized["schema_version"] == 3.1
    assert normalized["custom_version"] == 4


def test_normalizes_last_updated_date_object():
    metadata = {"last_updated": date(2026, 2, 19)}

    normalized = normalize_yaml_scalar_footguns(metadata)

    assert normalized["last_updated"] == "2026-02-19"
