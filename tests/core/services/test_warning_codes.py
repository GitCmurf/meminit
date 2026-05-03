"""Tests for warning_codes module (PRD-007).

Verifies the warning code constants are importable and have expected values.
"""

from meminit.core.services.warning_codes import WarningCode


def test_warning_code_constants_exist():
    """All PRD-007 warning codes are defined."""
    assert WarningCode.W_STATE_UNKNOWN_DOC_ID == "W_STATE_UNKNOWN_DOC_ID"
    assert WarningCode.W_STATE_UNKNOWN_IMPL_STATE == "W_STATE_UNKNOWN_IMPL_STATE"
    assert WarningCode.W_FIELD_SANITIZATION_FAILED == "W_FIELD_SANITIZATION_FAILED"
    assert WarningCode.W_STATE_UNSORTED_KEYS == "W_STATE_UNSORTED_KEYS"
    assert WarningCode.GRAPH_DANGLING_RELATED_ID == "GRAPH_DANGLING_RELATED_ID"
    assert WarningCode.GRAPH_DANGLING_SUPERSEDED_BY == "GRAPH_DANGLING_SUPERSEDED_BY"
    assert WarningCode.GRAPH_SUPERSESSION_STATUS_MISMATCH == "GRAPH_SUPERSESSION_STATUS_MISMATCH"
    assert WarningCode.PROTOCOL_SYNC_FORCE_USED == "PROTOCOL_SYNC_FORCE_USED"


def test_legacy_warning_codes_prefixed_with_w():
    """Legacy warning codes (historical) start with W_ prefix."""
    for attr in dir(WarningCode):
        if attr.startswith("W_"):
            value = getattr(WarningCode, attr)
            assert isinstance(value, str)
            assert value.startswith("W_"), f"{attr} value should start with W_"
