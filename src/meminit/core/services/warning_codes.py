"""Non-fatal warning codes for the Meminit CLI envelope.

These are separate from ErrorCode (which backs MeminitError for fatal errors).
Warning codes are emitted in the envelope `warnings` array and do not cause
non-zero exit codes.
"""


class WarningCode:
    """Registry of non-fatal warning code constants.

    Severity is not encoded in the code name — it is carried on the
    diagnostic object instead.  Historical codes use a ``W_`` prefix
    (e.g. ``W_STATE_UNKNOWN_DOC_ID``); newer graph codes intentionally
    omit it (``GRAPH_DANGLING_RELATED_ID``).  New codes should not add
    the ``W_`` prefix — set severity on the diagnostic object.

    These are intentionally *not* part of the ErrorCode enum to avoid
    conflating exception codes with advisory diagnostics.
    """

    W_STATE_UNKNOWN_DOC_ID = "W_STATE_UNKNOWN_DOC_ID"
    W_STATE_UNKNOWN_IMPL_STATE = "W_STATE_UNKNOWN_IMPL_STATE"
    W_FIELD_SANITIZATION_FAILED = "W_FIELD_SANITIZATION_FAILED"
    W_STATE_UNSORTED_KEYS = "W_STATE_UNSORTED_KEYS"

    # Graph integrity warnings (Phase 2)
    GRAPH_DANGLING_RELATED_ID = "GRAPH_DANGLING_RELATED_ID"
    GRAPH_DANGLING_SUPERSEDED_BY = "GRAPH_DANGLING_SUPERSEDED_BY"
    GRAPH_SUPERSESSION_STATUS_MISMATCH = "GRAPH_SUPERSESSION_STATUS_MISMATCH"
