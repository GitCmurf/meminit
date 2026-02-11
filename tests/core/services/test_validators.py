import pytest

from meminit.core.domain.entities import Violation
from meminit.core.services.validators import IdValidator


def test_id_validator_regex_valid():
    validator = IdValidator()
    assert validator.validate_format("MEMINIT-ADR-001") is None
    assert validator.validate_format("OZYS-PRD-023") is None


def test_id_validator_regex_invalid():
    validator = IdValidator()
    # Bad Prefix Length
    assert validator.validate_format("M-ADR-001") is not None
    assert validator.validate_format("VERYLONGPREFIX-ADR-001") is not None
    # Bad Type Length
    assert validator.validate_format("MEMINIT-AB-001") is not None
    assert validator.validate_format("MEMINIT-ABCDEFGHIJK-001") is not None
    # Bad Seq
    assert validator.validate_format("MEMINIT-ADR-1") is not None
    assert validator.validate_format("MEMINIT-ADR-001a") is not None
    # Mutable Area
    assert validator.validate_format("MEMINIT-INGEST-ADR-001") is not None


def test_id_validator_uniqueness():
    validator = IdValidator()
    existing_ids = {"MEMINIT-ADR-001", "MEMINIT-PRD-002"}

    assert validator.validate_uniqueness("MEMINIT-ADR-003", existing_ids) is None

    violation = validator.validate_uniqueness("MEMINIT-ADR-001", existing_ids)
    assert isinstance(violation, Violation)
    assert violation.rule == "ID_UNIQUE"
    assert violation.severity == "error"
