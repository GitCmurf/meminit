"""Tests for the exit_codes module."""

import pytest
from meminit.core.services.error_codes import ErrorCode
from meminit.core.services.exit_codes import (
    EX_CANTCREAT,
    EX_COMPLIANCE_FAIL,
    EX_DATAERR,
    EX_NOINPUT,
    EX_NOPERM,
    EX_USAGE,
    exit_code_for_error,
)


def test_exit_code_for_error_mappings():
    """Verify that every ErrorCode member maps to the expected exit code."""
    expected_mappings = {
        ErrorCode.INVALID_FLAG_COMBINATION: EX_USAGE,
        ErrorCode.CONFIG_MISSING: EX_NOINPUT,
        ErrorCode.FILE_NOT_FOUND: EX_NOINPUT,
        ErrorCode.TEMPLATE_NOT_FOUND: EX_NOINPUT,
        ErrorCode.PATH_ESCAPE: EX_NOPERM,
        ErrorCode.UNKNOWN_TYPE: EX_DATAERR,
        ErrorCode.UNKNOWN_NAMESPACE: EX_DATAERR,
        ErrorCode.INVALID_ID_FORMAT: EX_DATAERR,
        ErrorCode.INVALID_STATUS: EX_DATAERR,
        ErrorCode.INVALID_RELATED_ID: EX_DATAERR,
        ErrorCode.DUPLICATE_ID: EX_CANTCREAT,
        ErrorCode.FILE_EXISTS: EX_CANTCREAT,
        ErrorCode.SCHEMA_INVALID: EX_DATAERR,
        ErrorCode.LOCK_TIMEOUT: EX_CANTCREAT,
        ErrorCode.MISSING_FRONTMATTER: EX_DATAERR,
        ErrorCode.MISSING_FIELD: EX_DATAERR,
        ErrorCode.INVALID_FIELD: EX_DATAERR,
        ErrorCode.OUTSIDE_DOCS_ROOT: EX_DATAERR,
        ErrorCode.DIRECTORY_MISMATCH: EX_DATAERR,
        ErrorCode.VALIDATION_ERROR: EX_DATAERR,
        ErrorCode.UNKNOWN_ERROR: EX_DATAERR,
        # Templates v2 error codes
        ErrorCode.LEGACY_CONFIG_UNSUPPORTED: EX_USAGE,
        ErrorCode.INVALID_TEMPLATE_PLACEHOLDER: EX_DATAERR,
        ErrorCode.UNKNOWN_TEMPLATE_VARIABLE: EX_DATAERR,
        ErrorCode.INVALID_TEMPLATE_FILE: EX_DATAERR,
        ErrorCode.DUPLICATE_SECTION_ID: EX_DATAERR,
        ErrorCode.AMBIGUOUS_SECTION_BOUNDARY: EX_DATAERR,
        # Project State Dashboard error codes (PRD-007)
        ErrorCode.E_STATE_YAML_MALFORMED: EX_DATAERR,
        ErrorCode.E_STATE_SCHEMA_VIOLATION: EX_DATAERR,
        ErrorCode.E_INVALID_FILTER_VALUE: EX_USAGE,
        ErrorCode.STATE_INVALID_PRIORITY: EX_DATAERR,
        ErrorCode.STATE_INVALID_DEPENDENCY_ID: EX_DATAERR,
        ErrorCode.STATE_SELF_DEPENDENCY: EX_DATAERR,
        ErrorCode.STATE_DEPENDENCY_CYCLE: EX_DATAERR,
        ErrorCode.STATE_FIELD_TOO_LONG: EX_DATAERR,
        ErrorCode.STATE_MIXED_MUTATION_MODE: EX_USAGE,
        ErrorCode.STATE_CLEAR_MUTATION_CONFLICT: EX_USAGE,
        ErrorCode.STATE_UNDEFINED_DEPENDENCY: EX_DATAERR,
        ErrorCode.STATE_DEPENDENCY_STATUS_CONFLICT: EX_DATAERR,
        # Agent interface error codes
        ErrorCode.UNKNOWN_ERROR_CODE: EX_DATAERR,
        ErrorCode.INVALID_ROOT_PATH: EX_NOINPUT,
        ErrorCode.NOT_A_REGULAR_FILE: EX_NOINPUT,
        # Graph integrity error codes
        ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID: EX_DATAERR,
        ErrorCode.GRAPH_SUPERSESSION_CYCLE: EX_DATAERR,
        # Protocol governance error codes
        ErrorCode.PROTOCOL_ASSET_MISSING: EX_COMPLIANCE_FAIL,
        ErrorCode.PROTOCOL_ASSET_LEGACY: EX_COMPLIANCE_FAIL,
        ErrorCode.PROTOCOL_ASSET_STALE: EX_COMPLIANCE_FAIL,
        ErrorCode.PROTOCOL_ASSET_TAMPERED: EX_COMPLIANCE_FAIL,
        ErrorCode.PROTOCOL_ASSET_UNPARSEABLE: EX_COMPLIANCE_FAIL,
        ErrorCode.PROTOCOL_SYNC_WRITE_FAILED: EX_NOPERM,
    }

    # Verify every defined ErrorCode is in our test expectation
    # This ensures we don't forget to test any newly added ErrorCodes
    for code in ErrorCode:
        assert code in expected_mappings, f"ErrorCode.{code.name} is not covered in tests"

    # Verify the mapping itself
    for code, expected_exit_code in expected_mappings.items():
        actual_exit_code = exit_code_for_error(code)
        assert actual_exit_code == expected_exit_code, (
            f"ErrorCode.{code.name} mapped to {actual_exit_code}, "
            f"expected {expected_exit_code}"
        )


def test_exit_code_for_error_fallback():
    """Verify the fallback behavior for unmapped error codes."""
    # Using an invalid value that is not in ErrorCode
    # type: ignore is used because we're intentionally passing a non-ErrorCode value
    assert exit_code_for_error(None) == EX_DATAERR  # type: ignore
    assert exit_code_for_error("NOT_A_CODE") == EX_DATAERR  # type: ignore
    assert exit_code_for_error(object()) == EX_DATAERR  # type: ignore
