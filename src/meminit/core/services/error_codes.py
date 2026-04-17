"""Error codes, exception handling, and error explanations for the Meminit CLI.

This module defines the CLI-wide ErrorCode enum, the MeminitError exception
class, and the ERROR_EXPLANATIONS registry used by `meminit explain`. Error
explanations are co-located with the canonical error code source to prevent
drift between the enum and its documentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


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
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

    # Templates v2 error codes
    LEGACY_CONFIG_UNSUPPORTED = "LEGACY_CONFIG_UNSUPPORTED"
    INVALID_TEMPLATE_PLACEHOLDER = "INVALID_TEMPLATE_PLACEHOLDER"
    UNKNOWN_TEMPLATE_VARIABLE = "UNKNOWN_TEMPLATE_VARIABLE"
    INVALID_TEMPLATE_FILE = "INVALID_TEMPLATE_FILE"
    DUPLICATE_SECTION_ID = "DUPLICATE_SECTION_ID"
    AMBIGUOUS_SECTION_BOUNDARY = "AMBIGUOUS_SECTION_BOUNDARY"

    # Project State Dashboard error codes
    E_STATE_YAML_MALFORMED = "E_STATE_YAML_MALFORMED"
    E_STATE_SCHEMA_VIOLATION = "E_STATE_SCHEMA_VIOLATION"
    E_INVALID_FILTER_VALUE = "E_INVALID_FILTER_VALUE"

    # Agent interface error codes
    UNKNOWN_ERROR_CODE = "UNKNOWN_ERROR_CODE"
    INVALID_ROOT_PATH = "INVALID_ROOT_PATH"

    # Graph integrity error codes (Phase 2)
    GRAPH_DUPLICATE_DOCUMENT_ID = "GRAPH_DUPLICATE_DOCUMENT_ID"
    GRAPH_SUPERSESSION_CYCLE = "GRAPH_SUPERSESSION_CYCLE"


# ---------------------------------------------------------------------------
# Error explanation registry (co-located with ErrorCode per MEMINIT-PLAN-010 §3.4.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RemediationInfo:
    """Structured remediation guidance for an error code."""

    action: str
    resolution_type: str  # "manual" | "auto_fixable" | "retryable" | "config_change"
    automatable: bool
    relevant_commands: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ErrorExplanation:
    """Full explanation metadata for a single ErrorCode member."""

    code: str
    category: str
    summary: str
    cause: str
    remediation: RemediationInfo
    spec_reference: str = ""


ERROR_EXPLANATIONS: dict[str, ErrorExplanation] = {
    # -- Shared error codes --
    ErrorCode.DUPLICATE_ID.value: ErrorExplanation(
        code=ErrorCode.DUPLICATE_ID.value,
        category="shared",
        summary="A document_id collision was detected.",
        cause="Two or more documents share the same REPO-TYPE-SEQ identifier, typically from copying a document without updating its frontmatter.",
        remediation=RemediationInfo(
            action="Rename or re-sequence one of the conflicting documents using meminit migrate-ids.",
            resolution_type="manual",
            automatable=True,
            relevant_commands=["migrate-ids"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.INVALID_ID_FORMAT.value: ErrorExplanation(
        code=ErrorCode.INVALID_ID_FORMAT.value,
        category="shared",
        summary="A document_id does not match the REPO-TYPE-SEQ pattern.",
        cause="The requested --id value is malformed or does not match the repository prefix and document type.",
        remediation=RemediationInfo(
            action="Provide a valid --id matching the repository prefix and document type, or omit --id and let meminit allocate one.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["new"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.INVALID_FLAG_COMBINATION.value: ErrorExplanation(
        code=ErrorCode.INVALID_FLAG_COMBINATION.value,
        category="shared",
        summary="Mutually exclusive or invalid flag combination detected.",
        cause="Two or more CLI flags were used together that cannot coexist, or a flag value is invalid.",
        remediation=RemediationInfo(
            action="Check the command help for valid flag combinations.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=[],
        ),
        spec_reference="MEMINIT-PRD-005",
    ),
    ErrorCode.CONFIG_MISSING.value: ErrorExplanation(
        code=ErrorCode.CONFIG_MISSING.value,
        category="shared",
        summary="The DocOps configuration file is missing.",
        cause="docops.config.yaml does not exist or is not a regular file in the repository root.",
        remediation=RemediationInfo(
            action="Run meminit init to scaffold the configuration.",
            resolution_type="auto_fixable",
            automatable=True,
            relevant_commands=["init"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.INVALID_ROOT_PATH.value: ErrorExplanation(
        code=ErrorCode.INVALID_ROOT_PATH.value,
        category="shared",
        summary="The specified root path is invalid.",
        cause="The --root path either does not exist or is not a directory.",
        remediation=RemediationInfo(
            action="Verify the path exists and points to a directory. Use meminit context to discover the repository root.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["context"],
        ),
        spec_reference="MEMINIT-PLAN-010",
    ),
    ErrorCode.PATH_ESCAPE.value: ErrorExplanation(
        code=ErrorCode.PATH_ESCAPE.value,
        category="shared",
        summary="An operation attempted to write outside the repository root.",
        cause="A symlink or path traversal would cause files to be created outside the repo boundary.",
        remediation=RemediationInfo(
            action="Remove or fix the symlink causing the path escape.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["doctor", "check"],
        ),
        spec_reference="MEMINIT-GOV-003",
    ),
    ErrorCode.UNKNOWN_TYPE.value: ErrorExplanation(
        code=ErrorCode.UNKNOWN_TYPE.value,
        category="shared",
        summary="An unrecognized document type was requested.",
        cause="The type argument does not match any configured type in docops.config.yaml.",
        remediation=RemediationInfo(
            action="Run meminit context to see available types, or check the configuration.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["context"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.UNKNOWN_NAMESPACE.value: ErrorExplanation(
        code=ErrorCode.UNKNOWN_NAMESPACE.value,
        category="shared",
        summary="An unrecognized namespace was referenced.",
        cause="The namespace is not defined in docops.config.yaml namespaces configuration.",
        remediation=RemediationInfo(
            action="Check available namespaces in the configuration.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["context"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.FILE_EXISTS.value: ErrorExplanation(
        code=ErrorCode.FILE_EXISTS.value,
        category="shared",
        summary="A file already exists at the target path.",
        cause="meminit new attempted to create a document but the output path is occupied.",
        remediation=RemediationInfo(
            action="Choose a different title or remove the existing file.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["new"],
        ),
        spec_reference="MEMINIT-PRD-003",
    ),
    ErrorCode.INVALID_STATUS.value: ErrorExplanation(
        code=ErrorCode.INVALID_STATUS.value,
        category="shared",
        summary="An invalid document status was specified.",
        cause="The status value does not match the allowed values in the metadata schema.",
        remediation=RemediationInfo(
            action="Use a valid status: Draft, In Review, Approved, Superseded.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["fix"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.INVALID_RELATED_ID.value: ErrorExplanation(
        code=ErrorCode.INVALID_RELATED_ID.value,
        category="shared",
        summary="A related document ID reference is invalid.",
        cause="The provided related_ids or superseded_by value does not match the required REPO-TYPE-SEQ pattern.",
        remediation=RemediationInfo(
            action="Correct related_ids and superseded_by to valid document IDs, or remove the field until the target document exists.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["new"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.TEMPLATE_NOT_FOUND.value: ErrorExplanation(
        code=ErrorCode.TEMPLATE_NOT_FOUND.value,
        category="shared",
        summary="The requested template could not be resolved.",
        cause="No template file was found at the configured, conventional, or built-in paths.",
        remediation=RemediationInfo(
            action="Create a template at the conventional path or configure an explicit template in docops.config.yaml.",
            resolution_type="config_change",
            automatable=False,
            relevant_commands=["new", "context"],
        ),
        spec_reference="MEMINIT-SPEC-007",
    ),
    ErrorCode.SCHEMA_INVALID.value: ErrorExplanation(
        code=ErrorCode.SCHEMA_INVALID.value,
        category="shared",
        summary="A document's frontmatter does not conform to the metadata schema.",
        cause="One or more required fields are missing, or field values violate type/format constraints.",
        remediation=RemediationInfo(
            action="Run meminit check to see specific violations, then fix manually or with meminit fix.",
            resolution_type="manual",
            automatable=True,
            relevant_commands=["check", "fix"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.LOCK_TIMEOUT.value: ErrorExplanation(
        code=ErrorCode.LOCK_TIMEOUT.value,
        category="shared",
        summary="Failed to acquire a file lock within the timeout.",
        cause="Another process holds a lock on the target file, or a stale lock file exists.",
        remediation=RemediationInfo(
            action="Wait for the other process to finish, or remove stale .lock files.",
            resolution_type="retryable",
            automatable=False,
            relevant_commands=[],
        ),
        spec_reference="MEMINIT-PRD-003",
    ),
    ErrorCode.FILE_NOT_FOUND.value: ErrorExplanation(
        code=ErrorCode.FILE_NOT_FOUND.value,
        category="shared",
        summary="A referenced file does not exist.",
        cause="The target file was deleted or moved after the reference was created.",
        remediation=RemediationInfo(
            action="Restore the file or update the reference.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["check"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.MISSING_FRONTMATTER.value: ErrorExplanation(
        code=ErrorCode.MISSING_FRONTMATTER.value,
        category="shared",
        summary="A governed document has no YAML frontmatter block.",
        cause="The file exists but does not start with the required YAML fence delimiter.",
        remediation=RemediationInfo(
            action="Add proper YAML frontmatter or run meminit fix to generate it.",
            resolution_type="auto_fixable",
            automatable=True,
            relevant_commands=["fix"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.MISSING_FIELD.value: ErrorExplanation(
        code=ErrorCode.MISSING_FIELD.value,
        category="shared",
        summary="A required frontmatter field is missing.",
        cause="The document's YAML frontmatter does not include all required metadata fields.",
        remediation=RemediationInfo(
            action="Add the missing field or run meminit fix.",
            resolution_type="auto_fixable",
            automatable=True,
            relevant_commands=["fix", "check"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.INVALID_FIELD.value: ErrorExplanation(
        code=ErrorCode.INVALID_FIELD.value,
        category="shared",
        summary="A frontmatter field has an invalid value.",
        cause="A field's value does not match the expected type, format, or allowed values.",
        remediation=RemediationInfo(
            action="Correct the field value or run meminit fix.",
            resolution_type="manual",
            automatable=True,
            relevant_commands=["fix", "check"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.OUTSIDE_DOCS_ROOT.value: ErrorExplanation(
        code=ErrorCode.OUTSIDE_DOCS_ROOT.value,
        category="shared",
        summary="A governed document is located outside the configured docs root.",
        cause="The document's directory path does not match any configured namespace.",
        remediation=RemediationInfo(
            action="Move the document to the correct namespace directory.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["check"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.DIRECTORY_MISMATCH.value: ErrorExplanation(
        code=ErrorCode.DIRECTORY_MISMATCH.value,
        category="shared",
        summary="A document's directory does not match its type.",
        cause="The document type in frontmatter does not match the directory it resides in.",
        remediation=RemediationInfo(
            action="Move the document to the correct type directory or update its type.",
            resolution_type="manual",
            automatable=True,
            relevant_commands=["fix", "check"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.VALIDATION_ERROR.value: ErrorExplanation(
        code=ErrorCode.VALIDATION_ERROR.value,
        category="shared",
        summary="A generic validation error occurred.",
        cause="A document failed one or more validation rules.",
        remediation=RemediationInfo(
            action="Run meminit check for detailed violation information.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["check", "doctor"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.UNKNOWN_ERROR.value: ErrorExplanation(
        code=ErrorCode.UNKNOWN_ERROR.value,
        category="shared",
        summary="An unexpected internal error occurred.",
        cause="An unhandled exception was caught by the error handler.",
        remediation=RemediationInfo(
            action="Check stderr for the full traceback. If persistent, report as a bug.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["doctor"],
        ),
        spec_reference="MEMINIT-PRD-005",
    ),
    # -- Templates v2 error codes --
    ErrorCode.LEGACY_CONFIG_UNSUPPORTED.value: ErrorExplanation(
        code=ErrorCode.LEGACY_CONFIG_UNSUPPORTED.value,
        category="templates",
        summary="A legacy template configuration format is not supported.",
        cause="The docops.config.yaml uses a pre-Templates-v2 configuration structure.",
        remediation=RemediationInfo(
            action="Run meminit migrate-templates to upgrade to Templates v2 format.",
            resolution_type="auto_fixable",
            automatable=True,
            relevant_commands=["migrate-templates"],
        ),
        spec_reference="MEMINIT-SPEC-007",
    ),
    ErrorCode.INVALID_TEMPLATE_PLACEHOLDER.value: ErrorExplanation(
        code=ErrorCode.INVALID_TEMPLATE_PLACEHOLDER.value,
        category="templates",
        summary="A template uses an unsupported placeholder syntax.",
        cause="The template contains legacy {variable} or <VARIABLE> syntax instead of {{variable}}.",
        remediation=RemediationInfo(
            action="Replace legacy placeholders with {{variable}} syntax.",
            resolution_type="manual",
            automatable=True,
            relevant_commands=["fix", "migrate-templates"],
        ),
        spec_reference="MEMINIT-SPEC-007",
    ),
    ErrorCode.UNKNOWN_TEMPLATE_VARIABLE.value: ErrorExplanation(
        code=ErrorCode.UNKNOWN_TEMPLATE_VARIABLE.value,
        category="templates",
        summary="A template references an undefined variable.",
        cause="The template uses a {{variable}} that is not in the supported set.",
        remediation=RemediationInfo(
            action="Remove the unknown variable or use a supported one.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["new"],
        ),
        spec_reference="MEMINIT-SPEC-007",
    ),
    ErrorCode.INVALID_TEMPLATE_FILE.value: ErrorExplanation(
        code=ErrorCode.INVALID_TEMPLATE_FILE.value,
        category="templates",
        summary="A template file could not be parsed.",
        cause="The template file has encoding issues, is not readable, or contains malformed YAML frontmatter.",
        remediation=RemediationInfo(
            action="Fix the template file encoding and structure.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["doctor"],
        ),
        spec_reference="MEMINIT-SPEC-007",
    ),
    ErrorCode.DUPLICATE_SECTION_ID.value: ErrorExplanation(
        code=ErrorCode.DUPLICATE_SECTION_ID.value,
        category="templates",
        summary="A template contains duplicate section markers.",
        cause="Two or more MEMINIT_SECTION markers share the same ID.",
        remediation=RemediationInfo(
            action="Rename duplicate section markers to unique IDs.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=[],
        ),
        spec_reference="MEMINIT-SPEC-007",
    ),
    ErrorCode.AMBIGUOUS_SECTION_BOUNDARY.value: ErrorExplanation(
        code=ErrorCode.AMBIGUOUS_SECTION_BOUNDARY.value,
        category="templates",
        summary="A template section boundary could not be determined.",
        cause="A MEMINIT_SECTION marker is missing its closing counterpart or is malformed.",
        remediation=RemediationInfo(
            action="Fix the section markers to have proper opening and closing delimiters.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=[],
        ),
        spec_reference="MEMINIT-SPEC-007",
    ),
    # -- Project State Dashboard error codes --
    ErrorCode.E_STATE_YAML_MALFORMED.value: ErrorExplanation(
        code=ErrorCode.E_STATE_YAML_MALFORMED.value,
        category="state",
        summary="The project-state.yaml file contains malformed YAML.",
        cause="The YAML syntax is invalid, preventing parsing.",
        remediation=RemediationInfo(
            action="Fix the YAML syntax in project-state.yaml.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["doctor"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.E_STATE_SCHEMA_VIOLATION.value: ErrorExplanation(
        code=ErrorCode.E_STATE_SCHEMA_VIOLATION.value,
        category="state",
        summary="The project-state.yaml violates the expected schema.",
        cause="A field has the wrong type, is missing, or contains an invalid value.",
        remediation=RemediationInfo(
            action="Correct the schema violation in project-state.yaml.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["doctor", "check"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    ErrorCode.E_INVALID_FILTER_VALUE.value: ErrorExplanation(
        code=ErrorCode.E_INVALID_FILTER_VALUE.value,
        category="state",
        summary="An invalid state-related value was provided.",
        cause=(
            "A state query filter or state update argument used an unsupported "
            "implementation state or actor value, or omitted the required "
            "state-set update flags."
        ),
        remediation=RemediationInfo(
            action=(
                "For state queries, use a valid implementation state value: Not "
                "Started, In Progress, Blocked, QA Required, Done. For state set, "
                "provide at least one of --impl-state, --notes, or --clear, and "
                "ensure any --impl-state or --actor value is valid."
            ),
            resolution_type="manual",
            automatable=False,
            relevant_commands=["state list", "state set"],
        ),
        spec_reference="MEMINIT-SPEC-006",
    ),
    # -- Agent interface error codes --
    ErrorCode.UNKNOWN_ERROR_CODE.value: ErrorExplanation(
        code=ErrorCode.UNKNOWN_ERROR_CODE.value,
        category="agent",
        summary="The requested error code is not recognized.",
        cause="An invalid or misspelled error code was passed to meminit explain.",
        remediation=RemediationInfo(
            action="Run meminit explain --list to see all valid error codes.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["explain"],
        ),
        spec_reference="MEMINIT-PRD-005",
    ),
    # -- Graph integrity error codes --
    ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID.value: ErrorExplanation(
        code=ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID.value,
        category="graph",
        summary="Two or more files declare the same document_id.",
        cause="A document_id collision was detected during index build. Edges become ambiguous when multiple files share the same identifier.",
        remediation=RemediationInfo(
            action="Rename or re-sequence one of the conflicting documents so each document_id is unique.",
            resolution_type="manual",
            automatable=True,
            relevant_commands=["migrate-ids"],
        ),
        spec_reference="MEMINIT-PLAN-011",
    ),
    ErrorCode.GRAPH_SUPERSESSION_CYCLE.value: ErrorExplanation(
        code=ErrorCode.GRAPH_SUPERSESSION_CYCLE.value,
        category="graph",
        summary="A supersession chain forms a cycle.",
        cause="Following superseded_by links produces a loop (e.g., A superseded by B, B superseded by C, C superseded by A).",
        remediation=RemediationInfo(
            action="Break the cycle by correcting the superseded_by values so the chain is acyclic.",
            resolution_type="manual",
            automatable=False,
            relevant_commands=["fix", "check"],
        ),
        spec_reference="MEMINIT-PLAN-011",
    ),
}


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
