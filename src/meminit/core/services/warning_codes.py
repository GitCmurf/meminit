"""Non-fatal warning codes for the Meminit CLI envelope.

These are separate from ErrorCode (which backs MeminitError for fatal errors).
Warning codes are emitted in the envelope `warnings` array and do not cause
non-zero exit codes.

Added by PRD-007 (Project State Dashboard).
"""


class WarningCode:
    """Registry of non-fatal warning code constants.

    Codes prefixed ``W_`` are warnings (exit code 0, reported in envelope
    ``warnings`` array).  They are intentionally *not* part of the ErrorCode
    enum to avoid conflating exception codes with advisory diagnostics.
    """

    W_STATE_UNKNOWN_DOC_ID = "W_STATE_UNKNOWN_DOC_ID"
    W_STATE_UNKNOWN_IMPL_STATE = "W_STATE_UNKNOWN_IMPL_STATE"
    W_FIELD_SANITIZATION_FAILED = "W_FIELD_SANITIZATION_FAILED"
    W_STATE_UNSORTED_KEYS = "W_STATE_UNSORTED_KEYS"
