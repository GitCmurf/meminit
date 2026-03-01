"""Exit code mapping for Meminit CLI (PRD-003 §13.2)."""

from __future__ import annotations

import os

from meminit.core.services.error_codes import ErrorCode

EX_SUCCESS = 0
EX_COMPLIANCE_FAIL = 1
EX_USAGE = getattr(os, "EX_USAGE", 64)
EX_DATAERR = getattr(os, "EX_DATAERR", 65)
EX_NOINPUT = getattr(os, "EX_NOINPUT", 66)
EX_CANTCREAT = getattr(os, "EX_CANTCREAT", 73)
EX_NOPERM = getattr(os, "EX_NOPERM", 77)


def exit_code_for_error(error_code: ErrorCode) -> int:
    """Map ErrorCode to PRD-003 exit codes."""
    mapping = {
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
    return mapping.get(error_code, EX_DATAERR)
