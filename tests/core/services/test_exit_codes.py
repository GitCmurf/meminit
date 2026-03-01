"""Tests for the exit_codes module."""

import pytest
from meminit.core.services.error_codes import ErrorCode
from meminit.core.services.exit_codes import (
    EX_CANTCREAT,
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
