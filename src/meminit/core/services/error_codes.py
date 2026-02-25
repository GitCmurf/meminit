"""Error codes and exception handling for the Meminit CLI.

This module defines the CLI-wide ErrorCode enum and the MeminitError exception
class as specified in PRD section 5.4. Error codes are organized into three
categories: shared (used by both 'new' and 'check' commands), 'new'-only,
and 'check'-only.
"""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """CLI-wide error code enumeration.

    Error codes are defined as a single CLI-wide enum covering all meminit
    subcommands. Individual commands use a subset of these codes.

    Categories:
        Shared: Used by both 'meminit new' and 'meminit check'
        New-only: Specific to 'meminit new' command (F9.1)
        Check-only: Specific to 'meminit check' command (Section 11.5)
    """

    DUPLICATE_ID = "DUPLICATE_ID"
    INVALID_ID_FORMAT = "INVALID_ID_FORMAT"
    INVALID_FLAG_COMBINATION = "INVALID_FLAG_COMBINATION"
    CONFIG_MISSING = "CONFIG_MISSING"
    PATH_ESCAPE = "PATH_ESCAPE"
    UNKNOWN_TYPE = "UNKNOWN_TYPE"
    UNKNOWN_NAMESPACE = "UNKNOWN_NAMESPACE"
    FILE_EXISTS = "FILE_EXISTS"
    INVALID_STATUS = "INVALID_STATUS"
    INVALID_RELATED_ID = "INVALID_RELATED_ID"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    LOCK_TIMEOUT = "LOCK_TIMEOUT"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    MISSING_FRONTMATTER = "MISSING_FRONTMATTER"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_FIELD = "INVALID_FIELD"
    OUTSIDE_DOCS_ROOT = "OUTSIDE_DOCS_ROOT"
    DIRECTORY_MISMATCH = "DIRECTORY_MISMATCH"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class MeminitError(Exception):
    """Base exception for Meminit CLI errors.

    Wraps an ErrorCode with a human-readable message and optional structured
    details for machine-parseable error responses.

    Attributes:
        code: The ErrorCode enum value for this error.
        message: Human-readable error description.
        details: Optional dictionary of additional structured context.

    Example:
        >>> error = MeminitError(
        ...     code=ErrorCode.UNKNOWN_TYPE,
        ...     message="Unknown document type: XYZ",
        ...     details={"valid_types": ["ADR", "PRD", "FDD"]}
        ... )
        >>> error.code
        <ErrorCode.UNKNOWN_TYPE: 'UNKNOWN_TYPE'>
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a MeminitError.

        Args:
            code: The ErrorCode enum value identifying this error type.
            message: Human-readable error description.
            details: Optional dictionary of additional structured context
                (e.g., valid values, file paths, etc.).
        """
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the error."""
        return f"MeminitError(code={self.code.value!r}, message={self.message!r}, details={self.details!r})"
